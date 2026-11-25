#!/usr/bin/env python3
"""FASE 1 – Analiza los videos de referencia y escribe estilo.json.

Uso:  python3 herramientas/analizar_estilo.py referencias/ -o estilo.json [--model small]

Por video mide: formato (ffprobe), cortes (PySceneDetect), punch-ins/zooms (ORB + afinidad entre
frames), subtítulos (zona de texto en frames a mitad de cada palabra: posición, alto de letra,
colores, contorno, palabras por bloque, animación), color (luma, contraste, saturación, temperatura,
puntos negro/blanco), audio (LUFS, nivel de música en huecos sin voz, efectos de sonido detectados
y emparejados contra la biblioteca /sonidos), gancho (primeros 3 s). Guarda además recortes de
subtítulos y hojas de contacto en analisis/<video>/ para revisión visual.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIBE = ROOT / ".claude/skills/transcribir-local/scripts/transcribe_local.py"
SFX_LIB = ROOT / "assets/sonidos-retencion"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- formato
def formato(p):
    j = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)]).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    num, den = map(int, v["avg_frame_rate"].split("/"))
    w, h = int(v["width"]), int(v["height"])
    rot = int((v.get("side_data_list") or [{}])[0].get("rotation", 0) or 0)
    if abs(rot) == 90: w, h = h, w
    return {"ancho": w, "alto": h, "aspecto": f"{w}:{h}", "es_9_16": abs(w / h - 9 / 16) < 0.01,
            "fps": round(num / den, 3) if den else None, "codec_video": v["codec_name"],
            "pix_fmt": v.get("pix_fmt"), "bitrate_video_kbps": round(int(v.get("bit_rate", 0) or 0) / 1000),
            "bitrate_total_kbps": round(int(j["format"].get("bit_rate", 0)) / 1000),
            "duracion_s": round(float(j["format"]["duration"]), 3),
            "codec_audio": a.get("codec_name"), "audio_hz": int(a.get("sample_rate", 0) or 0),
            "canales": a.get("channels"), "color": v.get("color_primaries") or v.get("color_space")}


# ---------------------------------------------------------------- cortes
def cortes(p):
    from scenedetect import detect, ContentDetector
    escenas = detect(str(p), ContentDetector(threshold=27.0, min_scene_len=6))
    t = [round(s[0].get_seconds(), 3) for s in escenas[1:]]
    return t


def frames_en(p, tiempos, ancho=360):
    cap = cv2.VideoCapture(str(p)); out = []
    for t in tiempos:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, t) * 1000); ok, f = cap.read()
        out.append(cv2.resize(f, (ancho, int(f.shape[0] * ancho / f.shape[1]))) if ok else None)
    cap.release(); return out


def escala_entre(a, b, orb=cv2.ORB_create(800)):
    """Escala relativa b/a con ORB + afinidad parcial; None si no hay correspondencia."""
    if a is None or b is None: return None
    ga, gb = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    # excluye subtítulos/textos quemados (no se escalan con el zoom y anclan la estimación)
    ma = (cv2.dilate(mascara_texto(a), np.ones((25, 25), np.uint8)) == 0).astype(np.uint8) * 255
    mb = (cv2.dilate(mascara_texto(b), np.ones((25, 25), np.uint8)) == 0).astype(np.uint8) * 255
    ka, da = orb.detectAndCompute(ga, ma); kb, db = orb.detectAndCompute(gb, mb)
    if da is None or db is None or len(ka) < 15 or len(kb) < 15: return None
    m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db), key=lambda x: x.distance)[:200]
    if len(m) < 15: return None
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, ransacReprojThreshold=3)
    if M is None or inl.sum() < 12: return None
    return float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))


def zooms(p, cuts, dur, paso=0.1):
    """Punch-ins en cortes (mismo plano, otra escala) y zooms continuos dentro de cada plano."""
    eventos = []
    # 1) en cada corte: último frame antes vs primero después
    for t in cuts:
        a, b = frames_en(p, [t - 0.07, t + 0.05])
        s = escala_entre(a, b)
        if s and abs(s - 1) > 0.04:
            eventos.append({"t": t, "tipo": "punch_in_en_corte" if s > 1 else "punch_out_en_corte", "escala": round(s, 3)})
    # 2) dentro de cada plano: escala acumulada en saltos de `paso`
    limites = [0.0] + cuts + [dur]
    for i in range(len(limites) - 1):
        a0, a1 = limites[i] + 0.05, limites[i + 1] - 0.08
        if a1 - a0 < 0.4: continue
        ts = list(np.arange(a0, a1, paso)); fr = frames_en(p, ts); acum, inicio = 1.0, None
        for k in range(1, len(fr)):
            s = escala_entre(fr[k - 1], fr[k])
            if s is None: continue
            if abs(s - 1) > 0.035:                                    # salto brusco dentro del plano
                kk = min(k + 3, len(fr) - 1); s2 = escala_entre(fr[k - 1], fr[kk])
                if s2 and abs(s2 - s) < 0.03 and (s > 1) == (s2 > 1):  # persiste → zoom real, no ruido
                    eventos.append({"t": round(ts[k], 3), "tipo": "punch_in" if s > 1 else "punch_out", "escala": round(s, 3)})
            elif abs(s - 1) > 0.002:                                 # zoom lento
                if inicio is None: inicio, acum = ts[k - 1], 1.0
                acum *= s
            elif inicio is not None:
                if abs(acum - 1) > 0.03:
                    eventos.append({"t": round(inicio, 3), "fin": round(ts[k], 3), "tipo": "zoom_lento", "escala": round(acum, 3)})
                inicio = None
        if inicio is not None and abs(acum - 1) > 0.03:
            eventos.append({"t": round(inicio, 3), "fin": round(a1, 3), "tipo": "zoom_lento", "escala": round(acum, 3)})
    return sorted(eventos, key=lambda e: e["t"])


# ---------------------------------------------------------------- color
def color(p, dur, n=24):
    fr = [f for f in frames_en(p, np.linspace(0.3, dur - 0.3, n), ancho=270) if f is not None]
    Y, S, rb, p2, p98, hue = [], [], [], [], [], []
    for f in fr:
        lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB).astype(np.float32); hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        L = lab[..., 0] * 100 / 255; Y.append((L.mean(), L.std()))
        S.append(hsv[..., 1].mean() / 255)
        b, g, r = [f[..., c].astype(np.float32).mean() for c in range(3)]; rb.append(r / max(b, 1))
        p2.append(np.percentile(L, 2)); p98.append(np.percentile(L, 98))
        hue.append((lab[..., 1].mean() - 128, lab[..., 2].mean() - 128))
    Y = np.array(Y); hue = np.array(hue)
    return {"brillo_L_medio": round(float(Y[:, 0].mean()), 1), "contraste_L_std": round(float(Y[:, 1].mean()), 1),
            "saturacion_media": round(float(np.mean(S)), 3), "ratio_rojo_azul": round(float(np.mean(rb)), 3),
            "lab_a_medio": round(float(hue[:, 0].mean()), 2), "lab_b_medio": round(float(hue[:, 1].mean()), 2),
            "negro_p2": round(float(np.mean(p2)), 1), "blanco_p98": round(float(np.mean(p98)), 1),
            "temperatura": "cálida" if hue[:, 1].mean() > 6 else "fría" if hue[:, 1].mean() < -2 else "neutra"}


# ---------------------------------------------------------------- subtítulos
def mascara_texto(f):
    """Texto de subtítulo: píxeles muy claros o muy saturados rodeados de borde oscuro."""
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    brillante = ((hsv[..., 2] > 150) & (hsv[..., 1] < 60)) | ((hsv[..., 1] > 150) & (hsv[..., 2] > 200))
    oscuro = cv2.dilate((hsv[..., 2] < 60).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m = (brillante & oscuro).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))


def subtitulos(p, palabras, dur, outdir):
    if not palabras: return {"detectados": False}
    ts = [(w["start"] + w["end"]) / 2 for w in palabras]
    fr = frames_en(p, ts, ancho=1080); H = None; cajas, alt_letra, colores, recortes, firmas = [], [], [], [], []
    for idx, (f, w) in enumerate(zip(fr, palabras)):
        if f is None: continue
        H, W = f.shape[:2]; m = mascara_texto(f)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        comps = [tuple(int(x) for x in st[i]) for i in range(1, n) if st[i, 4] > 25 and st[i, 3] > H * 0.012]
        if not comps: firmas.append((idx, set())); continue
        # agrupa en la fila con más área (la línea de subtítulos)
        filas = {}
        for c in comps: filas.setdefault(int((c[1] + c[3] / 2) / (H * 0.06)), []).append(c)
        fila = max(filas.values(), key=lambda cs: sum(c[4] for c in cs))
        x0 = min(c[0] for c in fila); y0 = min(c[1] for c in fila)
        x1 = max(c[0] + c[2] for c in fila); y1 = max(c[1] + c[3] for c in fila)
        # incluye filas vecinas (2 líneas)
        for cs in filas.values():
            for c in cs:
                if abs(c[1] - y0) < H * 0.12 and not any(c == q for q in fila):
                    x0, y0 = min(x0, c[0]), min(y0, c[1]); x1, y1 = max(x1, c[0] + c[2]), max(y1, c[1] + c[3])
        cajas.append((x0 / W, y0 / H, x1 / W, y1 / H)); alt_letra.append(np.median([c[3] for c in fila]) / H)
        zona = f[y0:y1, x0:x1]; mz = m[y0:y1, x0:x1] > 0
        if mz.sum() > 20: colores.append(zona[mz].reshape(-1, 3))
        if len(recortes) < 12: recortes.append(f[max(0, y0 - 15):y1 + 15, :])
        firmas.append((idx, palabras_visibles(f[max(0, y0 - 12):y1 + 12], palabras, idx)))
    if not cajas: return {"detectados": False}
    cajas = np.array(cajas)
    # palabras por bloque: OCR del recorte → rango de palabras de la transcripción en pantalla
    rangos = [(i, (min(v), max(v))) for i, v in firmas if v]
    bloques, vistos = [], set()
    for i, r in rangos:
        if r not in vistos and r[0] <= i <= r[1]:
            vistos.add(r); bloques.append(r[1] - r[0] + 1)
    # funde rangos solapados (OCR parcial del mismo bloque)
    bloques = sorted(bloques)[len(bloques) // 4:] or bloques or [1]
    # colores: blanco base + color de resaltado (tono saturado más frecuente)
    allc = np.vstack(colores) if colores else np.zeros((1, 3), np.uint8)
    hsv = cv2.cvtColor(allc.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    sat = hsv[hsv[:, 1] > 150]
    resaltado = None
    if len(sat) > 0.03 * len(hsv):
        h = int(np.bincount(sat[:, 0] // 5).argmax() * 5 + 2)
        bgr = cv2.cvtColor(np.uint8([[[h, 230, 245]]]), cv2.COLOR_HSV2BGR)[0, 0]
        resaltado = "#%02X%02X%02X" % (bgr[2], bgr[1], bgr[0])
    # animación: alto de la caja al inicio vs a mitad del bloque (pop/escala)
    anim = animacion_texto(p, palabras[: min(25, len(palabras))])
    if recortes:
        hoja = np.vstack([cv2.copyMakeBorder(r, 2, 2, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 255)) for r in recortes])
        cv2.imwrite(str(outdir / "subtitulos_recortes.png"), hoja)
    cy = float(np.median((cajas[:, 1] + cajas[:, 3]) / 2))
    return {"detectados": True, "cobertura_palabras": round(len(cajas) / len(palabras), 2),
            "centro_vertical_pct": round(cy * 100, 1),
            "posicion": "centro" if 0.38 < cy < 0.62 else "abajo" if cy >= 0.62 else "arriba",
            "ancho_bloque_pct": round(float(np.median(cajas[:, 2] - cajas[:, 0])) * 100, 1),
            "alto_letra_pct_alto": round(float(np.median(alt_letra)) * 100, 2),
            "alto_mayuscula_px_1920": round(float(np.median(alt_letra)) * 1920),
            "palabras_por_bloque_mediana": float(np.median(bloques)), "palabras_por_bloque_max": int(max(bloques)),
            "color_resaltado": resaltado, "color_base": "#FFFFFF", "contorno": "negro (detectado por borde oscuro)",
            "animacion": anim, "fuente": "ver analisis/<video>/subtitulos_recortes.png (identificación visual)"}


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if c.isalpha())


def palabras_visibles(crop, palabras, idx, ventana=14):
    """OCR (Tesseract, español) del recorte; devuelve índices de palabras cercanas que aparecen."""
    import pytesseract
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    txt = ((hsv[..., 2] > 150) & ((hsv[..., 1] < 60) | (hsv[..., 1] > 150))).astype(np.uint8) * 255
    o = _norm(pytesseract.image_to_string(255 - txt, lang="spa", config="--psm 6"))
    vis = set()
    for j in range(max(0, idx - ventana), min(len(palabras), idx + ventana + 1)):
        n = _norm(palabras[j]["text"])
        if len(n) >= 3 and (n in o or n[:-1] in o or n[1:] in o): vis.add(j)
    if vis:                                       # palabras cortas ("a", "y") dentro del rango cuentan
        vis = set(range(min(vis), max(vis) + 1))
    return vis


def animacion_texto(p, palabras):
    """Mide la caja del texto en 0, 2, 4, 6 frames tras el inicio de la palabra → pop/escala o corte seco."""
    escalas = []
    for w in palabras[::3]:
        fr = frames_en(p, [w["start"] + k / 30 for k in (0, 2, 4, 8)], ancho=540); hs = []
        for f in fr:
            if f is None: hs.append(None); continue
            m = mascara_texto(f); ys, xs = np.where(m > 0)
            hs.append((xs.max() - xs.min()) if len(xs) > 30 else None)
        if all(h for h in hs) and hs[-1] > 0: escalas.append([h / hs[-1] for h in hs])
    if not escalas: return {"tipo": "desconocida"}
    e = np.median(np.array(escalas), axis=0)
    tipo = "pop (crece/rebota)" if e[0] < 0.92 or e[1] > 1.04 else "corte seco por palabra/bloque"
    return {"tipo": tipo, "escala_relativa_frames_0_2_4_8": [round(float(x), 3) for x in e]}


# ---------------------------------------------------------------- audio
def pcm(p, sr=22050):
    return np.frombuffer(subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", str(sr),
                                         "-f", "f32le", "-"], capture_output=True).stdout, np.float32)


def lufs_tramo(p, a=None, b=None):
    cmd = ["ffmpeg", "-nostdin", "-nostats"] + (["-ss", f"{a:.3f}", "-to", f"{b:.3f}"] if a is not None else []) + \
          ["-i", str(p), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    o = run(cmd).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", o); P = re.findall(r"Peak:\s+(-?[\d.inf]+) dBFS", o)
    LRA = re.findall(r"LRA:\s+([\d.]+) LU", o)
    return (float(I[-1]) if I else None, float(P[-1]) if P and P[-1] != "-inf" else None, float(LRA[-1]) if LRA else None)


HOP = 512


def logmel(y, sr=22050):
    import librosa
    return np.log10(librosa.feature.melspectrogram(y=y, sr=sr, n_mels=40, hop_length=HOP, fmin=60) + 1e-7)


NFFT, HOPF = 1024, 256


def picos_espectrales(y, sr=22050, top=None, piso_db=-60):
    """Mapa de picos (estilo Shazam): máximos locales del espectrograma en dB."""
    from scipy.ndimage import maximum_filter
    import librosa
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOPF)), ref=np.max)
    D = D[8:380]                                             # ~170 Hz – 8 kHz
    loc = (D == maximum_filter(D, size=(9, 5))) & (D > piso_db)
    if top:
        f, t = np.where(loc); v = D[f, t]; o = np.argsort(-v)[:top]; return f[o], t[o], D
    return loc, D


def biblioteca_sfx(sr=22050):
    cat = json.loads((SFX_LIB / "catalogo.json").read_text())["sonidos"]; out = {}
    for k, v in cat.items():
        x = pcm(SFX_LIB / k, sr)
        a, b = int(v["inicio_audible_s"] * sr), int(min(v["fin_audible_s"], v["inicio_audible_s"] + 1.2) * sr)
        if b - a < sr * 0.08: continue
        f, t, _ = picos_espectrales(x[a:b], sr, top=60, piso_db=-40)
        if len(f) < 12: continue
        out[k] = (f, t, int((v["pico_s"] - v["inicio_audible_s"]) * sr / HOPF), v)
    return out


def emparejar_biblioteca(y, lib, umbral=0.45, sr=22050):
    """Fracción de picos de la plantilla presentes en la mezcla (±1 bin/frame) en cada desfase.
    Exige además que destaque sobre su propio fondo (z robusto > 6). Devuelve [(t_pico_s, clave, score)]."""
    from scipy.ndimage import binary_dilation
    loc, _ = picos_espectrales(y, sr)
    P = binary_dilation(loc, structure=np.ones((3, 3), bool)).astype(np.float32)
    T = P.shape[1]; hits = []
    for k, (f, t, pf, v) in lib.items():
        L = T - t.max()
        if L <= 0: continue
        sc = P[f[:, None], t[:, None] + np.arange(L)[None, :]].mean(0)
        med = np.median(sc); mad = np.median(np.abs(sc - med)) + 1e-3
        for i in np.where((sc > umbral) & ((sc - med) / mad > 6))[0]:
            if sc[i] == sc[max(0, i - 10):i + 11].max():
                hits.append(((i + pf) * HOPF / sr, k, float(sc[i])))
    hits.sort(key=lambda h: -h[2]); final = []
    for h in hits:
        if all(abs(h[0] - f[0]) > 0.25 for f in final): final.append(h)
    return sorted(final)


def separar_musica(p, outdir, sr=22050):
    """Demucs (htdemucs, 2 pistas): voz vs resto. Nivel continuo del resto = música de fondo."""
    wav = outdir / "audio.wav"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(p), "-vn", "-ac", "2", "-ar", "44100", str(wav)])
    run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", str(outdir / "sep"), str(wav)])
    d = outdir / "sep" / "htdemucs" / "audio"
    if not (d / "vocals.wav").exists(): return None
    def nivel(f, pct):
        x = pcm(f, sr); n = int(0.4 * sr)
        v = [20 * np.log10(np.sqrt(np.mean(x[i:i + n] ** 2)) + 1e-9) for i in range(0, len(x) - n, n)]
        return float(np.percentile(v, pct)) if v else None
    voz = nivel(d / "vocals.wav", 70); resto_cont = nivel(d / "no_vocals.wav", 30)
    hay = bool(resto_cont and resto_cont > -55 and voz and resto_cont - voz > -24)   # < -24 dB = solo fuga de voz/efectos
    return {"musica_de_fondo": hay, "voz_db": round(voz, 1) if voz else None,
            "musica_continua_db": round(resto_cont, 1) if resto_cont else None,
            "musica_bajo_voz_db": round(resto_cont - voz, 1) if hay else None,
            "musica_lufs": lufs_tramo(d / "no_vocals.wav")[0] if hay else None,
            "pistas": str(d)}


def audio(p, palabras, dur, lib):
    import librosa
    sr = 22050; y = pcm(p, sr)
    I, P, LRA = lufs_tramo(p)
    huecos, prev = [], 0.0
    for w in palabras:
        if w["start"] - prev >= 0.5: huecos.append((prev + 0.15, w["start"] - 0.12))
        prev = w["end"]
    if dur - prev >= 0.5: huecos.append((prev + 0.15, dur - 0.05))
    def rms_db(a, b):
        s_ = y[int(a * sr):int(b * sr)]; return 20 * np.log10(np.sqrt(np.mean(s_ ** 2)) + 1e-9) if len(s_) else None
    voz = [rms_db(w["start"], w["end"]) for w in palabras if w["end"] - w["start"] > 0.15]
    # fondo continuo = percentil 20 de ventanas de 50 ms dentro de las pausas (los efectos son transitorios)
    vent = []
    for a_, b_ in huecos:
        seg = y[int(a_ * sr):int(b_ * sr)]; n = int(0.05 * sr)
        vent += [20 * np.log10(np.sqrt(np.mean(seg[i:i + n] ** 2)) + 1e-9) for i in range(0, len(seg) - n, n)]
    fondo = [float(np.percentile(vent, 20))] if vent else []
    voz_db = float(np.median([v for v in voz if v])) if voz else None
    fondo_db = float(np.median([f for f in fondo if f])) if fondo else None
    musica = bool(fondo_db and fondo_db > -45 and (voz_db is None or fondo_db - voz_db < -6))
    if fondo_db and voz_db and fondo_db - voz_db >= -6: musica = "incierto (pausas demasiado cortas o con cola de voz)"
    eventos = []
    for t, k, sc in emparejar_biblioteca(y, lib, umbral=0.45):
        eventos.append({"t": round(t, 3), "tipo": k.split("/")[0], "coincide_biblioteca": k, "similitud": round(sc, 2),
                        "confianza": "seguro" if sc >= 0.6 else "probable",
                        "sobre_voz": any(w["start"] - 0.02 <= t <= w["end"] + 0.02 for w in palabras)})
    # efectos que no están en la biblioteca: transitorios fuertes fuera de la voz
    HOP = 512
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    pk = librosa.util.peak_pick(onset, pre_max=4, post_max=4, pre_avg=10, post_avg=10, delta=np.percentile(onset, 95) * 0.6, wait=6)
    for f in pk:
        t = f * HOP / sr
        if any(abs(t - e["t"]) < 0.3 for e in eventos): continue
        if any(w["start"] - 0.08 <= t <= w["end"] + 0.05 for w in palabras): continue
        tipo = clasificar_sfx(y, sr, t)
        if tipo != "voz/otro":
            eventos.append({"t": round(t, 3), "tipo": tipo, "coincide_biblioteca": None, "similitud": None, "confianza": "probable", "sobre_voz": False})
    eventos.sort(key=lambda e: e["t"])
    return {"lufs_integrado": I, "true_peak_db": P, "rango_lra": LRA, "voz_rms_db": round(voz_db, 1) if voz_db else None,
            "fondo_en_pausas_rms_db": round(fondo_db, 1) if fondo_db else None, "musica_de_fondo": musica,
            "musica_bajo_voz_db": round(fondo_db - voz_db, 1) if (musica is True and voz_db) else None,
            "efectos": eventos, "efectos_por_minuto": round(len(eventos) / dur * 60, 1)}


def clasificar_sfx(y, sr, t):
    import librosa
    a, b = int(max(0, t - 0.6) * sr), int(min(len(y) / sr, t + 0.6) * sr); s = y[a:b]
    if len(s) < sr * 0.2: return "voz/otro"
    cent = librosa.feature.spectral_centroid(y=s, sr=sr)[0]; flat = librosa.feature.spectral_flatness(y=s)[0]
    rms = librosa.feature.rms(y=s)[0]; i = int(np.argmax(rms))
    subida = rms[: i + 1]; ataque = (i - np.argmax(subida > rms[i] * 0.2)) * 512 / sr
    caida = (np.argmax(rms[i:] < rms[i] * 0.2) or len(rms) - i) * 512 / sr
    c, fl = float(np.median(cent)), float(np.median(flat))
    if ataque > 0.45: return "riser"
    if fl > 0.15 and 0.08 < ataque + caida < 0.9: return "whoosh"
    if c < 1500 and ataque < 0.05: return "impacto/golpe"
    if c > 2500 and caida < 0.25: return "pop/click"
    if fl < 0.02 and caida > 0.4: return "ding/tono"
    return "voz/otro"


# ---------------------------------------------------------------- gancho
def gancho(palabras, cuts, zms, sfx, subs):
    p3 = [w["text"] for w in palabras if w["start"] < 3.0]
    return {"primera_palabra_s": palabras[0]["start"] if palabras else None, "texto_3s": " ".join(p3),
            "palabras_en_3s": len(p3), "cortes_en_3s": sum(1 for t in cuts if t < 3),
            "zooms_en_3s": sum(1 for z in zms if z["t"] < 3), "efectos_en_3s": [e["tipo"] for e in sfx if e["t"] < 3],
            "subtitulo_desde_inicio": bool(subs.get("detectados"))}


def contacto(p, dur, outdir):
    ts = np.linspace(0.2, dur - 0.2, 12); fr = [f for f in frames_en(p, ts, 240) if f is not None]
    filas = [np.hstack(fr[i:i + 6]) for i in range(0, len(fr) - len(fr) % 6, 6)]
    if filas: cv2.imwrite(str(outdir / "hoja_contacto.jpg"), np.vstack(filas))
    g = [f for f in frames_en(p, np.arange(0, min(3, dur), 0.5), 240) if f is not None]
    if g: cv2.imwrite(str(outdir / "gancho_0-3s.jpg"), np.hstack(g))


# ---------------------------------------------------------------- main
def analizar(p, model, lib):
    out = ROOT / "analisis" / p.stem; out.mkdir(parents=True, exist_ok=True)
    tj = out / "transcripcion.json"
    run([sys.executable, str(TRANSCRIBE), str(p), "--language", "es", "--model", model, "-o", str(tj), "--srt", str(out / "transcripcion.srt")])
    palabras = [w for w in json.loads(tj.read_text())["words"] if w.get("type", "word") == "word"]
    fmt = formato(p); dur = fmt["duracion_s"]
    cuts = cortes(p); planos = np.diff([0.0] + cuts + [dur])
    zms = zooms(p, cuts, dur)
    subs = subtitulos(p, palabras, dur, out)
    aud = audio(p, palabras, dur, lib)
    sep = separar_musica(p, out)
    if sep:
        aud["musica_de_fondo"], aud["musica_bajo_voz_db"] = sep["musica_de_fondo"], sep["musica_bajo_voz_db"]
        aud["separacion_demucs"] = sep
    for e in aud["efectos"]:
        e["junto_a_corte_o_zoom"] = any(abs(e["t"] - t) < 0.25 for t in cuts + [z["t"] for z in zms])
    contacto(p, dur, out)
    r = {"archivo": p.name, "formato": fmt,
         "ritmo": {"cortes": cuts, "num_cortes": len(cuts), "cortes_por_minuto": round(len(cuts) / dur * 60, 1),
                   "plano_medio_s": round(float(planos.mean()), 2), "plano_mediana_s": round(float(np.median(planos)), 2),
                   "plano_min_s": round(float(planos.min()), 2), "plano_max_s": round(float(planos.max()), 2),
                   "palabras_por_minuto": round(len(palabras) / dur * 60)},
         "zooms": {"eventos": zms, "por_minuto": round(len(zms) / dur * 60, 1),
                   "escala_media_punch_in": round(float(np.mean([z["escala"] for z in zms if z["escala"] > 1] or [1])), 3)},
         "subtitulos": subs, "color": color(p, dur), "audio": aud, "gancho": gancho(palabras, cuts, zms, aud["efectos"], subs)}
    (out / "analisis.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def resumen(rs):
    def med(f):
        v = [f(r) for r in rs]; v = [x for x in v if isinstance(x, (int, float))]
        return round(float(np.median(v)), 3) if v else None
    return {"n_videos": len(rs),
            "formato": {"resolucion": f"{med(lambda r: r['formato']['ancho'])}x{med(lambda r: r['formato']['alto'])}",
                        "fps": med(lambda r: r["formato"]["fps"]), "bitrate_video_kbps": med(lambda r: r["formato"]["bitrate_video_kbps"]),
                        "duracion_s": med(lambda r: r["formato"]["duracion_s"])},
            "ritmo": {"plano_medio_s": med(lambda r: r["ritmo"]["plano_medio_s"]), "cortes_por_minuto": med(lambda r: r["ritmo"]["cortes_por_minuto"]),
                      "palabras_por_minuto": med(lambda r: r["ritmo"]["palabras_por_minuto"])},
            "zooms": {"por_minuto": med(lambda r: r["zooms"]["por_minuto"]), "escala_punch_in": med(lambda r: r["zooms"]["escala_media_punch_in"])},
            "subtitulos": {k: med(lambda r, k=k: r["subtitulos"].get(k)) for k in
                           ("centro_vertical_pct", "alto_letra_pct_alto", "alto_mayuscula_px_1920", "palabras_por_bloque_mediana", "ancho_bloque_pct")}
                          | {"color_resaltado": [r["subtitulos"].get("color_resaltado") for r in rs],
                             "animacion": [r["subtitulos"].get("animacion", {}).get("tipo") for r in rs]},
            "color": {k: med(lambda r, k=k: r["color"][k]) for k in rs[0]["color"] if k != "temperatura"},
            "audio": {"lufs": med(lambda r: r["audio"]["lufs_integrado"]), "true_peak": med(lambda r: r["audio"]["true_peak_db"]),
                      "musica_bajo_voz_db": med(lambda r: r["audio"]["musica_bajo_voz_db"]),
                      "efectos_por_minuto": med(lambda r: r["audio"]["efectos_por_minuto"]),
                      "tipos_efectos": sorted({e["tipo"] for r in rs for e in r["audio"]["efectos"]}),
                      "sonidos_de_biblioteca_usados": sorted({e["coincide_biblioteca"] for r in rs for e in r["audio"]["efectos"] if e["coincide_biblioteca"]})},
            "gancho": {"primera_palabra_s": med(lambda r: r["gancho"]["primera_palabra_s"]),
                       "cortes_en_3s": med(lambda r: r["gancho"]["cortes_en_3s"]), "zooms_en_3s": med(lambda r: r["gancho"]["zooms_en_3s"])}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("carpeta"); ap.add_argument("-o", "--out", default="estilo.json")
    ap.add_argument("--model", default="small"); a = ap.parse_args()
    vids = sorted(x for x in Path(a.carpeta).iterdir() if x.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm", ".mkv"))
    if not vids: sys.exit(f"no hay videos en {a.carpeta}")
    lib = biblioteca_sfx(); rs = []
    for v in vids:
        print(f"analizando {v.name} ...", flush=True); rs.append(analizar(v, a.model, lib))
    Path(a.out).write_text(json.dumps({"resumen": resumen(rs), "videos": rs}, ensure_ascii=False, indent=1))
    print(f"wrote {a.out}")
