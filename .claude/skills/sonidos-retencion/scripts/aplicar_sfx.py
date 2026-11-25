#!/usr/bin/env python3
"""Mezcla sonidos de retención (assets/sonidos-retencion) sobre un video.

Cada cue coloca un sonido en un instante del video. El sonido se alinea por:
  pico  -> su momento más fuerte cae en t   (whoosh, impactos, clicks, memes)
  fin   -> termina justo en t               (risers: suben hasta el corte)
  inicio-> empieza a sonar en t
y se normaliza a su LUFS objetivo de categoría (+ vol_db opcional), así todos
quedan parejos bajo la voz. El video se copia sin recomprimir.

Uso:
  python3 aplicar_sfx.py VIDEO -o SALIDA --cues cues.json
  python3 aplicar_sfx.py VIDEO -o SALIDA --en-cortes 3.2,7.9,12.4 --categoria whoosh
  python3 aplicar_sfx.py --listar [categoria]

cues.json: [{"t": 3.2, "sonido": "whoosh/whoosh-clean.mp3", "vol_db": 0, "alinear": "pico"}, ...]
  "sonido" puede ser una ruta del catálogo o solo una categoría ("whoosh"): se elige una
  variante rotando para no repetir.
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # raíz del repo Guiones-
LIB = ROOT / "assets" / "sonidos-retencion"
CAT = json.loads((LIB / "catalogo.json").read_text())
SONIDOS = CAT["sonidos"]

# variantes por defecto al elegir solo la categoría (las más versátiles primero)
PREFERIDOS = {
    "whoosh": ["whoosh/whoosh-clean.mp3", "whoosh/whoosh-sfx.mp3", "whoosh/whoosh-wind.mp3", "whoosh/whoosh-1.mp3", "whoosh/whoosh-dark.mp3"],
    "impactos": ["impactos/thud-instagram.mp3", "impactos/bamboo-hit.mp3", "impactos/thud-dramatico.mp3"],
    "risers": ["risers/riser-reverse.wav", "risers/riser-succion-2.wav", "risers/riser-flange.wav", "risers/riser-metalico.wav"],
    "clicks-ui": ["clicks-ui/ding.mp3", "clicks-ui/camara-obturador.mp3", "clicks-ui/switch-grande.mp3"],
    "memes": ["memes/tony-hawk.mp3", "memes/rizz.mp3"],
}
_rot = {}


def elegir(nombre):
    if nombre in SONIDOS:
        return nombre
    if nombre in PREFERIDOS:
        i = _rot.get(nombre, 0); _rot[nombre] = i + 1
        return PREFERIDOS[nombre][i % len(PREFERIDOS[nombre])]
    sys.exit(f"sonido desconocido: {nombre} (usa --listar)")


def duracion(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--cues")
    ap.add_argument("--en-cortes", help="tiempos separados por coma")
    ap.add_argument("--categoria", default="whoosh")
    ap.add_argument("--vol-db", type=float, default=0.0, help="ajuste global de los SFX")
    ap.add_argument("--listar", nargs="?", const="*")
    a = ap.parse_args()

    if a.listar:
        for k, v in SONIDOS.items():
            if a.listar in ("*", v["categoria"]):
                print(f"{k:34} {v['dur']:5.2f}s alinear={v['alinear']:4} {v['descripcion']}")
        return
    if not (a.video and a.out and (a.cues or a.en_cortes)):
        ap.error("necesita VIDEO, -o y --cues o --en-cortes")

    cues = json.loads(Path(a.cues).read_text()) if a.cues else \
        [{"t": float(t), "sonido": a.categoria} for t in a.en_cortes.split(",") if t.strip()]
    vdur = duracion(a.video)

    inputs, filtros, labels, log = ["-i", a.video], [], [], []
    for n, c in enumerate(sorted(cues, key=lambda c: c["t"]), 1):
        key = elegir(c["sonido"]); s = SONIDOS[key]
        alin = c.get("alinear", s["alinear"])
        ancla = {"pico": s["pico_s"], "fin": s["fin_audible_s"], "inicio": s["inicio_audible_s"]}[alin]
        inicio = c["t"] - ancla                       # momento del video donde arranca el archivo
        recorte = max(0.0, -inicio); inicio = max(0.0, inicio)
        gain = s["lufs_objetivo"] - s["lufs"] + c.get("vol_db", 0) + a.vol_db
        inputs += ["-i", str(LIB / key)]
        filtros.append(f"[{n}:a]atrim=start={recorte:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                       f"aformat=channel_layouts=stereo,volume={gain:.2f}dB,adelay={int(inicio*1000)}:all=1[s{n}]")
        labels.append(f"[s{n}]")
        log.append(f"{c['t']:7.2f}s  {key:34} alinear={alin} ganancia={gain:+.1f} dB")

    filtros.insert(0, "[0:a]aresample=48000,aformat=channel_layouts=stereo[voz]")
    filtros.append(f"[voz]{''.join(labels)}amix=inputs={len(labels)+1}:normalize=0:duration=first,"
                   f"alimiter=limit=0.89:level=false[mix]")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filtros),
           "-map", "0:v:0", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-t", f"{vdur:.3f}", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("\n".join(log)); print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
