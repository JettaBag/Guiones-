---
name: sonidos-retencion
description: Add retention sound effects (whooshes, risers, impacts, UI clicks, meme sounds) from the project's own library in assets/sonidos-retencion to an edited video, aligned to cuts, text pop-ups and key words. Use after cutting and captioning any short/reel/TikTok/YouTube video, or whenever the user asks for sound design, SFX, "sonidos de retención", whoosh, transiciones con sonido or more dynamic audio.
---

# Sonidos de retención

Biblioteca del usuario: `assets/sonidos-retencion/` (70 sonidos, catálogo en `catalogo.json` con
duración, LUFS, momento del pico y alineación). Mezclador: `scripts/aplicar_sfx.py`.

```bash
A=.claude/skills/sonidos-retencion/scripts/aplicar_sfx.py
python3 $A --listar            # todo; o --listar whoosh|risers|impactos|clicks-ui|memes
python3 $A edit.mp4 -o edit_sfx.mp4 --cues cues.json
python3 $A edit.mp4 -o edit_sfx.mp4 --en-cortes 2.5,6.8,9.1 --categoria whoosh   # rápido
```

`cues.json`: `[{"t": 2.55, "sonido": "whoosh", "vol_db": 0}, {"t": 7.25, "sonido": "risers/riser-reverse.wav"}]`
- `t` = momento del video **final** (después de cortes) donde debe caer el golpe.
- `sonido` = ruta del catálogo o solo la categoría (rota variantes para no repetir).
- Alineación automática: whoosh/impactos/clicks/memes → su **pico** cae en `t`; risers → **terminan** en `t`.
- Cada SFX se normaliza a su LUFS de categoría (whoosh −24, risers −26, impactos −22, clicks −26, memes −22),
  queda debajo de la voz; la voz no se toca; limitador final. Video copiado sin recomprimir.

## Orden en el flujo
transcribir → cortes → subtítulos/overlays → **sonidos-retencion** → `loudness.py -I -14` → `check.py`.
Saca los tiempos de los cortes del EDL (`*-edl.json` o `edl.json` de video-use) y de las palabras clave
del transcript re-temporizado (`*.mistakes-transcript.json`).

## Criterio (qué sonido, dónde)
| Momento | Sonido | Notas |
|---|---|---|
| Primer frame / gancho | `impactos/thud-instagram` (−3 dB) o riser que termina en la primera frase | El arranque con golpe retiene los 3 primeros segundos |
| Cambio de plano, zoom, entrada de B-roll o texto | `whoosh` (clean/sfx/wind para cortes rápidos; dark/intenso para transiciones grandes) | No en *todos* los cortes: 1 cada 3–6 s como máximo |
| Antes de una revelación o dato clave | riser que **termina** en la palabra + impacto en el mismo `t` | `riser-reverse` (corto) es el más versátil |
| Aparece un número, lista, check, captura | `clicks-ui/ding`, `camara-obturador`, `nintendo-XX`, `animal-crossing-XX` | Sutil; `vol_db` −2 a −4 si satura |
| Cambio de tema / antes-después | `clicks-ui/switch-grande` | |
| Remate gracioso | `memes/*` | Máx. 1 por video y solo si encaja con el tono |

Reglas: nunca tapar una palabra importante con un impacto fuerte (ponlo en la pausa justo antes o en
el inicio de la palabra); evitar más de 2 SFX en 1 s; escuchar/medir el resultado y bajar `--vol-db`
globalmente si los efectos compiten con la voz. Después re-normaliza a −14 LUFS para la plataforma.

`_compilaciones/` guarda los packs originales (ya separados en archivos sueltos `pack-XX`,
`nintendo-XX`, `animal-crossing-XX`). Si agregas sonidos nuevos, regenera `catalogo.json`
(duración, `pico_s`, `inicio_audible_s`, `fin_audible_s`, `lufs`) con el mismo formato.
