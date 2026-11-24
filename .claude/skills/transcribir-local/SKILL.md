---
name: transcribir-local
description: Transcribe video or audio locally, word by word, with faster-whisper (no API key, no cloud). Use before cutting silences or mistakes, burning subtitles or animated captions, or whenever video-use, cut-silences, cut-mistakes or Remotion captions need a word-level transcript. Outputs ElevenLabs-Scribe-shaped JSON and optional SRT. Works in Spanish (--language es).
---

# Transcribir local (faster-whisper)

Sustituye a la transcripción de pago (ElevenLabs Scribe) que piden `video-use` y `cut-silences`.
Misma forma de JSON, así que el resto de herramientas lo leen sin cambios.

```bash
S=.claude/skills/transcribir-local/scripts/transcribe_local.py
# JSON junto al video (+ SRT)
python3 $S video.mp4 --language es --srt video.srt
# Directo a la caché de video-use (<videos_dir>/edit/transcripts/<stem>.json)
python3 $S raw/toma1.mp4 --language es --edit-dir raw/edit
# Más precisión: --model medium | large-v3 (más lento). Nombres propios: --prompt "Camilo, Guiones"
```

- Primera ejecución descarga el modelo de Hugging Face (`small` ≈ 480 MB) y lo cachea.
- Con `video-use`: transcribe con este script usando `--edit-dir`, luego `pack_transcripts.py --edit-dir`;
  `transcribe.py` verá la caché y no pedirá `ELEVENLABS_API_KEY`.
- Con `cut-silences`/`cut-mistakes`: pásales el JSON resultante como `<transcript.json>`.
- Con Remotion captions: convierte `words` (type=word) a `Caption` `{text,startMs,endMs,timestampMs,confidence}`.
- Whisper deriva ~50–100 ms en los bordes: deja padding en los cortes.
