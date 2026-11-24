#!/usr/bin/env python3
"""FASE 2 – Edita un video crudo de lista "Top N de zapatillas" con el estilo de estilo.json.

Uso:  python3 herramientas/editar.py crudos/mi_video.json [--preview]

Config (crudos/<nombre>.json):
{
  "video": "crudos/mi_video.mp4",
  "titulo": ["5 ZAPATILLAS", "QUE SI TE VEO USANDO", "TIENES BUEN GUSTO"],
  "titulo_imagen": "crudos/titulo.png",            (opcional: foto de zapatillas detrás del título; se recorta sola)
  "items": [
     {"numero": 5, "nombre": "Asics Gel Kayano 14", "claves": ["asics", "kayano"],
      "broll": ["crudos/broll/asics1.mp4", "crudos/broll/asics2.mp4"],   (opcional)
      "recorte": "crudos/asics.png"}                                  (opcional: foto → recorte que entra con pop)
  ],
  "musica": null | "ruta/pista.mp3",                (solo suena en los montajes de B-roll)
  "subtitulos": true,
  "salida": "salida/mi_video.mp4"
}

Pasos: transcribe → quita silencios/muletillas/repeticiones → bloques hablados con zoom lento +
LUT de color hacia estilo.json → montajes B-roll (0,75 s por plano, a ritmo de la música si hay) →
ASS (título, lista, subtítulos, nombre en B-roll) → música → sonidos de retención → -14 LUFS → 1080x1920 H.264.
"""
import argparse, json, re, subprocess, sys, unicodedata
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
ESTILO = json.loads((ROOT / "estilo.json").read_text())
FONTS = ROOT / "assets/fuentes"
SFX = ROOT / ".claude/skills/sonidos-retencion/scripts/aplicar_sfx.py"
TRANS = ROOT / ".claude/skills/transcribir-local/scripts/transcribe_local.py"
LOUD = ROOT / ".claude/skills/ffmpeg-skill/scripts/loudness.py"
W, H, FPS = 1080, 1920, 30
MUL = {"eh", "ehh", "em", "emm", "mmm", "mm", "ehm", "este...", "eeh"}
GAP_MAX, PAD = 0.22, 0.07         # pausas > 0,22 s se recortan; margen alrededor de cada palabra


LOG = None                                                # trabajo/<video>/editar.log


def sh(cmd, **kw):
    cmd = [str(c) for c in cmd]
    if cmd[0] == "ffmpeg" and "-hide_banner" not in cmd: cmd.insert(1, "-hide_banner")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if LOG:
        with open(LOG, "a") as f: f.write(f"$ {' '.join(cmd)[:400]}\n{r.stderr[-4000:]}\n")
    if r.returncode:
        cola = "\n".join(r.stderr.strip().splitlines()[-20:])
        sys.exit(f"FALLÓ: {' '.join(cmd)[:200]}\n{cola}\n(log completo: {LOG})")
    return r.stdout


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower()); return "".join(c for c in t if c.isalnum())


def dur(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


# ------------------------------------------------------------------ 1-2. transcripción y limpieza
def transcribir(video, work):
    out = work / "transcripcion.json"
    sh([sys.executable, str(TRANS), str(video), "--language", "es", "--model", "small", "-o", str(out),
        "--prompt", "Eh, em, mmm... Bueno, número cinco: las burbuja negras, Jordan Retro 4 Black Cat, Off White, On Cloud, Asics Gel, Nike, Salomon XT-6, New Balance."])
    return [w for w in json.loads(out.read_text())["words"] if w.get("type", "word") == "word"]


def limpiar(words):
    """Quita muletillas y repeticiones/arranques en falso; devuelve palabras conservadas."""
    ws = [w for w in words if norm(w["text"]) not in {norm(m) for m in MUL}]
    keep = [True] * len(ws)
    for n in (4, 3, 2, 1):                                  # "hoy vamos a, hoy vamos a ..." → quita el primero
        for i in range(len(ws) - 2 * n + 1):
            a = [norm(w["text"]) for w in ws[i:i + n]]; b = [norm(w["text"]) for w in ws[i + n:i + 2 * n]]
            if a == b and all(keep[i:i + 2 * n]) and (n > 1 or len(a[0]) > 2):
                for j in range(i, i + n): keep[j] = False
    return [w for w, k in zip(ws, keep) if k]


def rangos_hablados(ws, total):
    """Rangos del crudo a conservar: cada palabra con margen; pausas largas se comprimen a ~0,14 s."""
    rs = []
    for w in ws:
        a, b = max(0, w["start"] - PAD), min(total, w["end"] + PAD)
        if rs and a - rs[-1][1] <= GAP_MAX: rs[-1][1] = max(rs[-1][1], b)
        else: rs.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in rs if b - a > 0.12]


# ------------------------------------------------------------------ 3. color (LUT por video)
def lab_stats(frames):
    L = np.concatenate([cv2.cvtColor(f, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32) for f in frames])
    L[:, 0] *= 100 / 255; L[:, 1:] -= 128
    return L.mean(0), L.std(0)


def crear_lut(video, rangos, path, fuerza=0.7):
    cap = cv2.VideoCapture(str(video)); fr = []
    for a, b in rangos[:: max(1, len(rangos) // 12)]:
        cap.set(cv2.CAP_PROP_POS_MSEC, (a + b) / 2 * 1000); ok, f = cap.read()
        if ok: fr.append(cv2.resize(f, (270, 480)))
    mu, sd = lab_stats(fr); c = ESTILO["color"]["medido_promedio"]
    tmu = np.array([c["brillo_L"], c["lab_a"], c["lab_b"]], np.float32)
    k = fuerza
    # L: media y contraste hacia la referencia (con tope para no oscurecer de más); a/b: desplazamiento parcial
    escala_L = np.clip(1 + k * (c["contraste_L_std"] / max(sd[0], 1) - 1), 0.85, 1.25)
    obj_L = mu[0] + k * np.clip(tmu[0] - mu[0], -12, 8)
    sat = np.clip(1 + k * (c["saturacion"] / 0.33 - 1), 0.85, 1.1)
    N = 33; g = np.linspace(0, 1, N)
    b_, g_, r_ = np.meshgrid(g, g, g, indexing="ij")             # .cube: R varía más rápido
    rgb = np.stack([r_.ravel(), g_.ravel(), b_.ravel()], 1).astype(np.float32)
    lab = cv2.cvtColor(rgb[None, :, ::-1].copy(), cv2.COLOR_BGR2LAB)[0]   # float: L 0-100, a/b ±
    lab[:, 0] = (lab[:, 0] - mu[0]) * escala_L + obj_L
    lab[:, 1] = (lab[:, 1] + k * (tmu[1] - mu[1]) * 0.6) * sat
    lab[:, 2] = (lab[:, 2] + k * (tmu[2] - mu[2]) * 0.6) * sat
    lab[:, 0] = np.clip(lab[:, 0], 0, 100)
    out = np.clip(cv2.cvtColor(lab[None], cv2.COLOR_LAB2BGR)[0][:, ::-1], 0, 1)
    with open(path, "w") as f:
        f.write(f"LUT_3D_SIZE {N}\n"); f.writelines(f"{x:.5f} {y:.5f} {z:.5f}\n" for x, y, z in out)
    return {"crudo_L": round(float(mu[0]), 1), "crudo_contraste": round(float(sd[0]), 1),
            "objetivo_L": round(float(obj_L), 1), "escala_contraste": round(float(escala_L), 3), "saturacion": round(float(sat), 3)}


# ------------------------------------------------------------------ 4. timeline
def ubicar_items(items, ws):
    """Momento (en el crudo) en que se anuncia cada item: 'número N' o sus palabras clave."""
    nums = {1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez"}
    out = {}
    for it in items:
        claves = [norm(c) for c in it.get("claves", [])] + [norm(x) for x in it["nombre"].split()[:2]]
        t_num = t_cla = None
        for i, w in enumerate(ws):
            n = norm(w["text"])
            if n in ("numero", "top", "puesto") and i + 1 < len(ws) and norm(ws[i + 1]["text"]) in (str(it["numero"]), nums.get(it["numero"])):
                t_num = t_num or w["start"]
            if any(c and c in n for c in claves if len(c) > 2) and t_cla is None and (t_num is None or w["start"] >= t_num):
                t_cla = w["start"]
        out[it["numero"]] = {"anuncio": t_num if t_num is not None else t_cla, "nombre_dicho": t_cla if t_cla is not None else t_num}
    return out


def construir_timeline(rangos, items, marcas, total, ws):
    """Lista de entradas: ('habla', a, b) del crudo o ('broll', item). El B-roll de cada item va justo antes del
    anuncio del siguiente; el del último, tras la frase donde se nombra (siguiente pausa > 4 s después)."""
    con_broll = [it for it in items if it.get("broll")]
    cortes = {}
    orden = sorted(items, key=lambda it: marcas[it["numero"]]["anuncio"] or 1e9)
    for k, it in enumerate(orden):
        if not it.get("broll"): continue
        if k + 1 < len(orden) and marcas[orden[k + 1]["numero"]]["anuncio"]:
            t = marcas[orden[k + 1]["numero"]]["anuncio"]
        else:
            t0 = marcas[it["numero"]]["nombre_dicho"] or 0
            fin_frase = next((w["end"] for w in ws if w["start"] > t0 + 1.0 and re.search(r"[.!?]$", w["text"])), None)
            t = min(total, fin_frase + PAD) if fin_frase else next((b for a, b in rangos if b > t0 + 4), total)
        cortes[round(t - 0.01, 3)] = it
    tl = []
    for a, b in rangos:
        for t in sorted(c for c in cortes if a < c <= b + 0.3 and c in cortes):
            if t > a + 0.15: tl.append(("habla", a, min(t, b)))
            tl.append(("broll", cortes.pop(t))); a = min(t, b)
        if b - a > 0.12: tl.append(("habla", a, b))
    for it in cortes.values(): tl.append(("broll", it))
    return tl


# ------------------------------------------------------------------ 5. render de segmentos
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS)]
AENC = ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]


def encuadre(z):
    """scale+crop a 1080x1920 con zoom z (expresión en t)."""
    return (f"scale=w='trunc({W}*({z})/2)*2':h='trunc({H}*({z})/2)*2':eval=frame:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2")


def render_habla(video, a, b, z0, z1, lut, out, preview):
    d = b - a; z = f"{z0:.4f}+({z1 - z0:.4f})*t/{d:.3f}"
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},lut3d='{lut}',{encuadre(z)},setsar=1,fps={FPS}"
    af = f"aresample=48000,afade=t=in:d=0.025,afade=t=out:st={max(0, d - 0.025):.3f}:d=0.025"
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(video),
        "-vf", vf, "-af", af, *VENC, *(["-preset", "ultrafast"] if preview else []), *AENC, str(out)])


def tomas_broll(clips, n, dur_toma):
    """Reparte n tomas entre los clips, eligiendo los tramos con más movimiento de cada uno."""
    tomas = []
    for i in range(n):
        c = clips[i % len(clips)]; D = dur(c); k = i // len(clips); m = max(1, -(-n // len(clips)))
        ini = min(max(0.2, (k + 0.5) * D / m - dur_toma / 2), max(0, D - dur_toma - 0.05))
        tomas.append((c, ini))
    return tomas


def render_broll(it, lut, out, duraciones, preview, work):
    tomas = tomas_broll(it["broll"], len(duraciones), max(duraciones))
    partes = []
    for j, ((c, ini), d) in enumerate(zip(tomas, duraciones)):
        p = work / f"broll_{it['numero']}_{j}.mov"
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},lut3d='{lut}',setsar=1,fps={FPS}"
        sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-t", f"{d:.3f}", "-i", str(c),
            "-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a", "-vf", vf, *VENC, *(["-preset", "ultrafast"] if preview else []), *AENC, str(p)])
        partes.append(p)
    concat(partes, out)


def concat(partes, out):
    lst = out.with_suffix(".txt"); lst.write_text("".join(f"file '{p}'\n" for p in partes))
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


def beats(musica, n, d_toma):
    """Duraciones de toma siguiendo los golpes de la música (≈0,75 s); sin música: 0,75 fijo."""
    if not musica: return [d_toma] * n
    import librosa
    y, sr = librosa.load(str(musica), sr=22050, duration=60)
    _, bt = librosa.beat.beat_track(y=y, sr=sr); t = librosa.frames_to_time(bt, sr=sr)
    per = np.median(np.diff(t)) if len(t) > 2 else 0.5
    paso = max(1, round(d_toma / per)); return [round(per * paso, 3)] * n


# ------------------------------------------------------------------ 6. ASS
def ass_t(s):
    s = max(0, s); return f"{int(s // 3600)}:{int(s % 3600 // 60):02}:{s % 60:05.2f}"


def bgr(hexc):
    h = hexc.lstrip("#"); return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}"


def generar_ass(cfg, plan, subs, path):
    Y = ESTILO["textos"]
    amar, amar_num = bgr("#F2D21B"), bgr("#EABD1B")
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T1,Montserrat ExtraBold,118,&H00FFFFFF,&H00FFFFFF,&H50000000,&H00000000,0,0,0,0,100,100,1,0,1,9,0,8,40,40,0,1
Style: T2,Anton,232,{amar},{amar},&H50000000,&H00000000,0,0,0,0,86,100,0,0,1,9,0,8,30,30,0,1
Style: NUM,Montserrat ExtraBold,150,{amar_num},{amar_num},&H40000000,&H00000000,0,0,0,0,100,100,0,0,1,7,0,7,0,0,0,1
Style: ITEM,Montserrat ExtraBold,108,&H00FFFFFF,&H00FFFFFF,&H40000000,&H00000000,0,0,0,0,100,100,0,0,1,7,0,4,0,0,0,1
Style: SUB,Montserrat ExtraBold,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,6,2,5,60,60,0,1
Style: BR,Anton,200,&H00FFFFFF,&H00FFFFFF,&H60000000,&H00000000,0,0,0,0,100,100,2,0,1,8,0,8,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    glow = r"\blur9"
    # --- título del gancho: entra con desenfoque → nítido (0,3 s); se va con fundido al empezar la lista
    t_fin = plan["fin_titulo"]; ys = [300, 428, 556]
    for k, (txt, est) in enumerate(zip(cfg["titulo"], ["T1", "T2", "T1"])):
        d0 = 0.05 + 0.12 * k
        ancho_est = len(txt) * (232 * 0.86 * 0.25 if est == "T2" else 118 * 0.45)
        fs = f"\\fs{int((232 if est == 'T2' else 118) * min(1, 950 / ancho_est))}" if ancho_est > 950 else ""
        txt = fs and "{" + fs + "}" + txt or txt
        ev.append(f"Dialogue: 1,{ass_t(d0)},{ass_t(t_fin)},{est},,0,0,0,,{{\\an5\\pos(540,{ys[k]})\\fad(0,180)\\alpha&HFF&\\blur30"
                  f"\\fscx115\\fscy115\\t(0,280,\\alpha&H00&\\blur9\\fscx100\\fscy100)}}{txt}")
    # --- lista numerada (visible solo en tramos hablados después del título)
    N = len(cfg["items"]); paso = 115; y0 = 128 if N <= 5 else 110
    if N > 5: paso = int(590 / (N - 1))
    for a, b in plan["tramos_lista"]:
        for i, it in enumerate(sorted(cfg["items"], key=lambda x: x["numero"])):
            y = y0 + i * paso
            ev.append(f"Dialogue: 2,{ass_t(a)},{ass_t(b)},NUM,,0,0,0,,{{\\an4\\pos(118,{y}){glow}}}{it['numero']}.")
            t_rev = plan["revelado"].get(it["numero"])
            if t_rev is not None and t_rev < b:
                ini = max(a, t_rev); anim = r"\fscx70\fscy70\t(0,90,\fscx108\fscy108)\t(90,160,\fscx100\fscy100)" if t_rev >= a else ""
                ev.append(f"Dialogue: 2,{ass_t(ini)},{ass_t(b)},ITEM,,0,0,0,,{{\\an4\\pos(228,{y}){glow}{anim}}}{it['nombre']}")
    # --- subtítulos: 3 palabras por bloque, palabra a palabra con pop; marcas/números en amarillo
    claves = {norm(c) for it in cfg["items"] for c in it.get("claves", []) + it["nombre"].split()}
    ventanas = list(plan.get("recortes", {}).values())
    if cfg.get("subtitulos", True):
        for bloque in subs:
            fin = bloque[-1]["fin_bloque"]
            for j, w in enumerate(bloque):
                ini = w["t"]; fin_w = bloque[j + 1]["t"] if j + 1 < len(bloque) else fin
                for t0, t1, _ in ventanas:                    # la foto del producto ocupa esa zona
                    if t0 - 0.02 <= ini < t1: fin_w = ini
                    elif ini < t0 < fin_w: fin_w = t0
                if fin_w - ini < 0.04: continue
                partes = []
                for q, x in enumerate(bloque[: j + 1]):
                    txt = x["text"].upper().strip(",.;:¡!¿?")
                    col = amar if (norm(x["text"]) in claves or re.fullmatch(r"\d+", norm(x["text"]))) else "&H00FFFFFF"
                    pop = r"\fscx75\fscy75\t(0,70,\fscx112\fscy112)\t(70,140,\fscx100\fscy100)" if q == j else ""
                    partes.append(f"{{\\c{col}{pop}}}{txt}{{\\fscx100\\fscy100}}")
                ev.append(f"Dialogue: 0,{ass_t(ini)},{ass_t(fin_w)},SUB,,0,0,0,,{{\\an5\\pos(540,1395)}}{' '.join(partes)}")
    # --- nombre grande al inicio de cada montaje
    for t, nombre in plan["nombres_broll"]:
        ev.append(f"Dialogue: 3,{ass_t(t)},{ass_t(t + 1.4)},BR,,0,0,0,,{{\\an8\\pos(540,300)\\fad(0,150)\\alpha&HFF&\\blur25"
                  f"\\t(0,200,\\alpha&H00&\\blur6)}}{nombre.upper()}")
    Path(path).write_text(cab + "\n".join(ev) + "\n", encoding="utf-8")


def bloques_subs(ws_final, tramos_habla, maxp=3):
    """Agrupa palabras (tiempo final) en bloques de ≤3; corta en pausas, puntuación o cambio de tramo."""
    out, cur = [], []
    for w in ws_final:
        if cur and (len(cur) >= maxp or w["t"] - cur[-1]["fin"] > 0.35 or re.search(r"[.,?!]$", cur[-1]["text"])):
            out.append(cur); cur = []
        cur.append(dict(w))
    if cur: out.append(cur)
    for b in out:
        fin = b[-1]["fin"] + 0.15
        for a_, b_ in tramos_habla:
            if a_ <= b[0]["t"] < b_: fin = min(fin, b_)
        for w in b: w["fin_bloque"] = fin
    for i in range(len(out) - 1):                      # sin huecos ni solapes entre bloques
        sig = out[i + 1][0]["t"]
        if out[i][-1]["fin_bloque"] > sig or sig - out[i][-1]["fin_bloque"] < 0.3:
            for w in out[i]: w["fin_bloque"] = sig
    return out


NUMS = {"uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
ART = {"las", "los", "el", "la", "unas", "unos", "son", "es", "estas", "estos"}


def config_auto(video, words):
    """Arma el .json del video a partir de lo que se dice: título = 1ª frase; items = 'número N, las X'."""
    txt = [w["text"] for w in limpiar(words)]             # sin muletillas ni repeticiones
    fin = next((i for i, t in enumerate(txt) if re.search(r"[.!?]$", t)), min(9, len(txt) - 1))
    frase = [t.strip(",.!?¿¡").upper() for t in txt[: fin + 1]][:12]
    if frase and norm(frase[0]) in NUMS: frase[0] = str(NUMS[norm(frase[0])])
    titulo = [" ".join(frase[:2]), " ".join(frase[2:7]), " ".join(frase[7:])]
    titulo = [t for t in titulo if t] or ["TOP 5"]
    items = []
    for i, t in enumerate(txt[:-1]):
        if norm(t) in ("numero", "top", "puesto"):
            n = NUMS.get(norm(txt[i + 1])) or (int(norm(txt[i + 1])) if norm(txt[i + 1]).isdigit() else None)
            if not n or any(x["numero"] == n for x in items): continue
            nombre = []
            for t2 in txt[i + 2: i + 9]:
                if not nombre and (norm(t2) in ART or norm(t2) in {norm(m) for m in MUL}): continue
                nombre.append(t2.strip(",.!?¿¡"))
                if re.search(r"[.,!?]$", t2) or len(nombre) >= 5: break
            nombre = " ".join(nombre).title() or f"Zapatilla {n}"
            items.append({"numero": n, "nombre": nombre, "claves": [norm(x) for x in nombre.split() if len(norm(x)) > 2]})
    st = Path(video).stem
    for it in items:                                        # tomas y foto por convención de nombres
        n = it["numero"]
        br = sorted(ROOT.glob(f"crudos/{st}_broll/{n}*.mp4")) + sorted(ROOT.glob(f"crudos/{st}_broll/{n}*.mov")) + \
             sorted(ROOT.glob(f"crudos/broll/{n}-*.mp4")) + sorted(ROOT.glob(f"crudos/broll/{n}-*.mov"))
        if br: it["broll"] = [str(b.relative_to(ROOT)) for b in br]
        foto = sorted(ROOT.glob(f"assets/productos/{n}-*.png"))
        if foto: it["recorte"] = str(foto[0].relative_to(ROOT))
    return {"video": str(Path(video).resolve().relative_to(ROOT)), "titulo": titulo, "items": items,
            "musica": None, "subtitulos": True, "salida": f"salida/{st}.mp4"}


def revisar(salida, plan, work):
    """Hoja de revisión: 3 fotogramas a 480 px (gancho, tramo con lista, montaje o final)."""
    T = dur(salida); m = plan["montajes"]
    ts = [1.5, (plan["fin_titulo"] + (m[0][0] if m else T)) / 2, (m[0][0] + 1.5) if m else T - 1]
    fr = []
    cap = cv2.VideoCapture(str(salida))
    for t in ts:
        cap.set(cv2.CAP_PROP_POS_MSEC, min(t, T - 0.2) * 1000); ok, f = cap.read()
        if ok: fr.append(cv2.resize(f, (480, 853)))
    if fr: cv2.imwrite(str(work / "revision.jpg"), np.hstack(fr), [cv2.IMWRITE_JPEG_QUALITY, 70])
    return work / "revision.jpg"


# ------------------------------------------------------------------ principal
def main():
    global LOG
    ap = argparse.ArgumentParser(); ap.add_argument("entrada", help="crudos/video.mp4 o crudos/video.json")
    ap.add_argument("--preview", action="store_true"); a = ap.parse_args()
    ent = (ROOT / a.entrada) if not Path(a.entrada).is_absolute() else Path(a.entrada)
    if ent.suffix.lower() == ".json":
        cfg_path = ent
    else:
        cfg_path = ent.with_suffix(".json")
    nombre = ent.stem; work = ROOT / "trabajo" / nombre; work.mkdir(parents=True, exist_ok=True)
    LOG = work / "editar.log"; LOG.write_text("")
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
    else:
        print("0/8 sin .json: armo título y lista desde lo que dices…", flush=True)
        cfg = config_auto(ent, transcribir(ent, work))
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    video = ROOT / cfg["video"]
    salida = ROOT / cfg.get("salida", f"salida/{nombre}.mp4"); salida.parent.mkdir(exist_ok=True)
    rep = {"video": cfg["video"]}

    print("1/8 transcribiendo…", flush=True)
    words = transcribir(video, work); total = dur(video)
    ws = limpiar(words); rep["palabras"] = len(words); rep["quitadas_muletillas_repeticiones"] = len(words) - len(ws)
    rangos = rangos_hablados(ws, total)
    rep["duracion_crudo_s"] = round(total, 2); rep["hablado_tras_limpieza_s"] = round(sum(b - a for a, b in rangos), 2)

    print("2/8 color…", flush=True)
    lut = work / "color.cube"; rep["color"] = crear_lut(video, rangos, lut)

    print("3/8 estructura…", flush=True)
    marcas = ubicar_items(cfg["items"], ws); rep["items_detectados"] = marcas
    tl = construir_timeline(rangos, cfg["items"], marcas, total, ws)

    print("4/8 render de segmentos…", flush=True)
    musica = cfg.get("musica"); musica = ROOT / musica if musica else None
    partes, t, plan = [], 0.0, {"tramos_lista": [], "revelado": {}, "nombres_broll": [], "montajes": []}
    bloque_ini, z_por_s = None, 0.06 / 9.0                   # zoom lento: +6 % cada ~9 s de bloque hablado
    mapa = []                                                # (crudo_a, crudo_b, final_a)
    for i, e in enumerate(tl):
        p = work / f"seg_{i:03}.mov"
        if e[0] == "habla":
            _, ca, cb = e; d = cb - ca
            if bloque_ini is None: bloque_ini = t
            z0 = 1 + (t - bloque_ini) * z_por_s; z1 = 1 + (t + d - bloque_ini) * z_por_s
            render_habla(video, ca, cb, z0, z1, lut, p, a.preview); mapa.append((ca, cb, t))
        else:
            it = e[1]; dd = beats(musica, 8, 0.75); bloque_ini = None
            render_broll(it, lut, p, dd, a.preview, work)
            plan["montajes"].append((t, t + sum(dd))); plan["nombres_broll"].append((t, it["nombre"]))
        partes.append(p); t += dur(p)
    base = work / "base.mov"; concat(partes, base); T = dur(base)

    def a_final(tc):
        for ca, cb, fa in mapa:
            if ca - 0.05 <= tc <= cb + 0.05: return fa + max(0, tc - ca)
        prev = [fa + (cb - ca) for ca, cb, fa in mapa if cb < tc]
        return prev[-1] if prev else 0.0

    ws_final = [{"text": w["text"], "t": round(a_final(w["start"]), 3), "fin": round(a_final(w["end"]), 3)} for w in ws]
    plan["fin_titulo"] = min(5.0, next((x["t"] for x in ws_final if x["t"] > 3.4 and re.search(r"[.?!]$", x["text"])), 4.5) + 0.3)
    for it in cfg["items"]:
        m = marcas[it["numero"]]["nombre_dicho"]
        if m is not None: plan["revelado"][it["numero"]] = round(a_final(m), 3)
    plan["recortes"] = {}
    for it in cfg["items"]:
        tr = plan["revelado"].get(it["numero"])
        if it.get("recorte") and tr is not None:
            t1 = min([tr + 2.6] + [ma for ma, mb in plan["montajes"] if ma > tr] + [T])
            if t1 - tr > 0.6:
                png = recortar(ROOT / it["recorte"], work / f"recorte_{it['numero']}.png", ancho=820, alto_max=520)
                plan["recortes"][it["numero"]] = (tr, t1, png)
    huecos = sorted(plan["montajes"]); cur = plan["fin_titulo"]
    for ma, mb in huecos:
        if ma > cur: plan["tramos_lista"].append((cur, ma))
        cur = max(cur, mb)
    if cur < T: plan["tramos_lista"].append((cur, T))
    tramos_habla = [(fa, fa + cb - ca) for ca, cb, fa in mapa]
    subs = bloques_subs(ws_final, tramos_habla)

    print("5/8 textos (ASS)…", flush=True)
    ass = work / "textos.ass"; generar_ass(cfg, plan, subs, ass)
    vid = work / "con_textos.mov"
    ins, cadena, ult, k = ["-i", str(base)], [], "0:v", 0
    if cfg.get("titulo_imagen"):                              # foto de zapatillas detrás del título (recortada)
        png = recortar(ROOT / cfg["titulo_imagen"], work / "titulo_recorte.png", ancho=860)
        ft = plan["fin_titulo"]; k += 1
        ins += ["-loop", "1", "-t", f"{ft:.2f}", "-i", str(png)]
        cadena.append(f"[{k}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={ft - 0.2:.2f}:d=0.2:alpha=1[i{k}];"
                      f"[{ult}][i{k}]overlay=(W-w)/2:140:eof_action=pass[v{k}]"); ult = f"v{k}"
    for num, (t0, t1, png) in sorted(plan["recortes"].items()):   # foto del producto: entra con pop, sale con fundido
        d = t1 - t0; k += 1
        pop = "if(lt(t,0.09),0.55+t/0.09*0.53,if(lt(t,0.18),1.08-(t-0.09)/0.09*0.08,1))"
        ins += ["-loop", "1", "-t", f"{d:.2f}", "-i", str(png)]
        cadena.append(f"[{k}:v]format=rgba,scale=w='trunc(iw*{pop}/2)*2':h=-2:eval=frame,"
                      f"fade=t=out:st={d - 0.15:.2f}:d=0.15:alpha=1,setpts=PTS+{t0:.3f}/TB[i{k}];"
                      f"[{ult}][i{k}]overlay=x=(W-w)/2:y=1330-h/2:eof_action=pass[v{k}]"); ult = f"v{k}"
    cadena.append(f"[{ult}]subtitles='{ass}':fontsdir='{FONTS}'[vout]")
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(cadena), "-map", "[vout]", "-map", "0:a",
        *VENC, *(["-preset", "ultrafast"] if a.preview else []), *AENC, str(vid)])

    print("6/8 música…", flush=True)
    if musica and plan["montajes"]:
        con_m = work / "con_musica.mov"; partes_m = []; filt = []
        for k, (ma, mb) in enumerate(plan["montajes"]):
            d = mb - ma
            filt.append(f"[1:a]atrim={k * 0.0}:{d:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={d - 0.12:.3f}:d=0.12,"
                        f"volume=-9dB,adelay={int(ma * 1000)}:all=1[m{k}]"); partes_m.append(f"[m{k}]")
        filt.append(f"[0:a]{''.join(partes_m)}amix=inputs={len(partes_m) + 1}:normalize=0:duration=first[a]")
        sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(vid), "-stream_loop", "-1", "-i", str(musica),
            "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AENC, str(con_m)])
        vid = con_m
    rep["musica"] = str(musica) if musica else "sin música"

    print("7/8 sonidos de retención…", flush=True)
    cues = [{"t": 0.12, "sonido": "whoosh/whoosh-clean.mp3", "vol_db": 2}]
    for num, tr in sorted(plan["revelado"].items(), key=lambda x: x[1]):
        cues.append({"t": tr, "sonido": "clicks-ui/animal-crossing-03.mp3", "vol_db": 4})
        if num == 1: cues += [{"t": tr, "sonido": "risers/riser-reverse.wav", "alinear": "fin"},
                              {"t": tr, "sonido": "impactos/thud-instagram.mp3", "vol_db": -4}]
    for ma, mb in plan["montajes"]:
        cues.append({"t": ma, "sonido": "whoosh/pack-12.mp3", "vol_db": 2})
        if not musica: cues.append({"t": ma + 0.02, "sonido": "impactos/bamboo-hit.mp3"})
        cues.append({"t": mb, "sonido": "whoosh/whoosh-wind.mp3"})
    # pop en palabras clave dentro de los subtítulos (máx. 1 cada 4 s, fuera de los revelados)
    ult = -9
    for b in subs:
        for w in b:
            if norm(w["text"]) in {norm(c) for it in cfg["items"] for c in it.get("claves", [])} and w["t"] - ult > 4 \
                    and all(abs(w["t"] - x) > 1.2 for x in plan["revelado"].values()):
                cues.append({"t": w["t"], "sonido": "clicks-ui/animal-crossing-03.mp3", "vol_db": 0}); ult = w["t"]
    cues = [c for c in cues if c["t"] < T - 0.1]
    cj = work / "cues.json"; cj.write_text(json.dumps(cues, indent=1))
    con_sfx = work / "con_sfx.mp4"
    sh([sys.executable, str(SFX), str(vid), "-o", str(con_sfx), "--cues", str(cj)])
    rep["efectos"] = len(cues); rep["efectos_por_min"] = round(len(cues) / T * 60, 1)

    print("8/8 -14 LUFS y exportación…", flush=True)
    sh([sys.executable, str(LOUD), str(con_sfx), "-o", str(salida), "-I", "-14", "--tp", "-1.5",
        "--sample-rate", "48000", "--overwrite"])
    rep.update({"salida": str(salida.relative_to(ROOT)), "duracion_final_s": round(dur(salida), 2),
                "montajes": [(round(x, 2), round(y, 2)) for x, y in plan["montajes"]],
                "revelados_lista": plan["revelado"], "fin_titulo": plan["fin_titulo"]})
    (work / "reporte.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    rep["revision"] = str(revisar(salida, plan, work).relative_to(ROOT))
    (work / "reporte.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(f"OK {rep['salida']} | {rep['duracion_crudo_s']}s → {rep['duracion_final_s']}s | items {len(cfg['items'])} "
          f"(revelados {len(plan['revelado'])}) | montajes {len(plan['montajes'])} | fotos {len(plan['recortes'])} | "
          f"efectos {rep['efectos']} | revisión {rep['revision']} | config {cfg_path.relative_to(ROOT)}")


def recortar(src, dst, ancho, alto_max=None):
    from rembg import remove, new_session
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    if im.getextrema()[3][0] == 255:                         # sin transparencia → quitar fondo
        im = remove(im, session=new_session("isnet-general-use"))
    im = im.crop(im.getbbox()); r = ancho / im.width
    if alto_max and im.height * r > alto_max: r = alto_max / im.height
    im = im.resize((int(im.width * r) // 2 * 2, int(im.height * r) // 2 * 2)); im.save(dst); return dst


if __name__ == "__main__":
    main()
