#!/usr/bin/env python3
"""Transcripción local palabra por palabra con faster-whisper (sin API keys, sin nube).

Escribe un JSON con la misma forma que ElevenLabs Scribe:
  {"language_code", "text", "words": [{"text","start","end","type":"word"|"spacing","speaker_id"}]}
para que lo consuman video-use (pack_transcripts / render), cut-silences, cut-mistakes
y ffmpeg-skill. También puede escribir un .srt.

Uso:
  python3 transcribe_local.py VIDEO [-o salida.json] [--edit-dir DIR] [--model small]
                              [--language es] [--srt salida.srt] [--prompt "Nombres, marcas"]
"""
import argparse, json, sys
from pathlib import Path


def fmt_srt(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out")
    ap.add_argument("--edit-dir", help="escribe en <edit-dir>/transcripts/<stem>.json (caché de video-use)")
    ap.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3 (default small)")
    ap.add_argument("--language", default=None, help="código ISO, p.ej. es; vacío = autodetectar")
    ap.add_argument("--prompt", default=None, help="vocabulario/nombres propios para mejorar precisión")
    ap.add_argument("--srt", help="además escribe subtítulos SRT por frases")
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()

    video = Path(a.video).resolve()
    if a.out:
        out = Path(a.out)
    elif a.edit_dir:
        out = Path(a.edit_dir) / "transcripts" / f"{video.stem}.json"
    else:
        out = video.with_suffix(".json")
    if out.exists() and out.stat().st_mtime > video.stat().st_mtime:
        print(f"cached: {out}"); return

    from faster_whisper import WhisperModel
    compute = "int8"
    model = WhisperModel(a.model, device=a.device, compute_type=compute)
    # Decodifica con ffmpeg (evita incompatibilidades de PyAV) a 16 kHz mono float32
    import subprocess, numpy as np
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
                          "-ar", "16000", "-f", "f32le", "-"], check=True, capture_output=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    segments, info = model.transcribe(audio, language=a.language, word_timestamps=True,
                                      vad_filter=False, initial_prompt=a.prompt, beam_size=5)
    words, segs = [], []
    prev_end = None
    for seg in segments:
        segs.append((seg.start, seg.end, seg.text.strip()))
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            if prev_end is not None and w.start > prev_end:
                words.append({"text": " ", "start": round(prev_end, 3), "end": round(w.start, 3),
                              "type": "spacing", "speaker_id": "speaker_0"})
            words.append({"text": text, "start": round(w.start, 3), "end": round(w.end, 3),
                          "type": "word", "speaker_id": "speaker_0", "logprob": round(w.probability, 3)})
            prev_end = w.end
    doc = {"language_code": info.language, "language_probability": round(info.language_probability, 3),
           "text": " ".join(s[2] for s in segs), "words": words, "engine": f"faster-whisper/{a.model}"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"wrote {out} ({sum(1 for w in words if w['type']=='word')} palabras, idioma {info.language})")
    if a.srt:
        lines = [f"{i}\n{fmt_srt(s)} --> {fmt_srt(e)}\n{t}\n" for i, (s, e, t) in enumerate(segs, 1)]
        Path(a.srt).write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {a.srt}")


if __name__ == "__main__":
    sys.exit(main())
