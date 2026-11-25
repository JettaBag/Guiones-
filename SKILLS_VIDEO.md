# Skills de edición de video – Fase 0

Instaladas en `.claude/skills/` el 2026-11-24 y probadas con un video vertical de 21,6 s
(voz sintética en español, pausas largas y un falso comienzo).

## Instaladas y probadas

| Skill / herramienta | Para qué | Origen | Reputación | Seguridad (código revisado) | Prueba |
|---|---|---|---|---|---|
| `remotion-*` (13 skills, router `remotion-best-practices`) | Video con código React: animaciones, subtítulos animados, render | `remotion-dev/skills` (oficial de Remotion) | ⭐ 7,9k (Remotion: 75k) | Solo Markdown. API keys solo opcionales (mapas, render en la nube) | ✅ Subtítulos TikTok palabra a palabra renderizados (plantilla en `herramientas/remotion-subtitulos`) |
| `ffmpeg-skill` | 42 herramientas FFmpeg: cortar, encuadrar 9:16, subtítulos karaoke, color, loudness, chequeo por plataforma | `kajisho5/ffmpeg-skill` | ⭐ 10,3k, MIT | Solo librería estándar de Python, sin llamadas de red | ✅ Karaoke + color + −14 LUFS; `check.py --platform tiktok` todo PASS |
| `video-use` | Editor conversacional: transcript → EDL → cortes con fundidos de 30 ms, grado de color, subtítulos al final | `browser-use/video-use` | ⭐ 31,5k, MIT | Única red: la API de ElevenLabs (de pago); la **sustituí por Whisper local** | ✅ 16,7 s → 9,5 s, grado `warm_cinematic` y subtítulos |
| `cut-silences` + `cut-mistakes` | Quitar pausas y luego tartamudeos, repeticiones y tomas repetidas (pide aprobación) | `nateherkai/herk-edit-kit` (Nate Herk) | ⭐ 3,1k, MIT | Node puro, sin red. Parcheado para FFmpeg 6.1 | ✅ 21,6 s → 11,7 s → 10,2 s. ⚠️ El detector no vio el falso comienzo; lo añadí a mano |
| `transcribir-local` (hecha aquí) | Transcripción palabra a palabra con faster-whisper, sin API key; JSON compatible con todas las anteriores + SRT | basada en `SYSTRAN/faster-whisper` (⭐ 27k, MIT) | — | Descarga el modelo de Hugging Face | ✅ 3,9 s para 21 s de audio (modelo `small`) |
| `auto-editor` (CLI) | Corte automático de silencios en un solo comando | `WyattBlue/auto-editor` | ⭐ 6k, Unlicense | Binario de los releases oficiales de GitHub | ✅ 21,6 s → 10,7 s |

## Evaluadas y NO instaladas

- **anthropics/skills** (oficial, ⭐ 199k): no tiene ninguna skill de video.
- **digitalsamba/claude-code-video-toolkit** (⭐ 2,7k): se solapa con lo anterior y varias de sus skills dependen de servicios de pago con API key (ElevenLabs, RunPod).
- **KyaniteLabs/kinocut** (servidor MCP, ⭐ 279): sirve, pero duplica a ffmpeg-skill y tiene mucha menos adopción.
- **heygen-com/skills** (⭐ 565): requiere una cuenta y una API de HeyGen.

## Flujo recomendado para las siguientes fases

1. `transcribir-local` → JSON de palabras (`--language es`, `--model medium` si hay ruido).
2. `cut-silences` → `cut-mistakes` (con revisión), o `video-use` con EDL para montar varias tomas.
3. Color: `video-use/helpers/grade.py --preset …` o `ffmpeg-skill color.py --correct …`.
4. Subtítulos: `ffmpeg-skill caption.py --karaoke` (rápido) o la plantilla Remotion (más animación).
5. Sonidos de retención (skill `sonidos-retencion`, biblioteca propia en `assets/sonidos-retencion/`).
6. Sonido y entrega: `loudness.py -I -14 --sample-rate 48000` → `check.py --platform tiktok|reels|shorts`.

## Dependencias del sistema

`pip install -r herramientas/requirements-video.txt` (fijamos `av==18.1.1`: con PyAV 19, faster-whisper falla).
Node 22 y FFmpeg 6.1 ya vienen en el entorno. Para el modelo de Whisper hay que permitir `huggingface.co`,
`us.aws.cdn.hf.co` y `cdn.hf.co` en la red del entorno (ya añadidos).
