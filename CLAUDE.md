# Reglas del proyecto editor-videos

## Trabajo
- Trabaja de forma autónoma: no preguntes decisiones creativas o técnicas de edición. Decide siguiendo `estilo.json` (plantilla ref1/ref5, subtítulos, efectos "a gusto") y explica después qué hiciste.
- Pregunta solo lo que el usuario debe decidir: si un video lleva música (si no lo dijo, sin música), y la confirmación antes de la PRIMERA publicación.
- Copia, nunca muevas ni borres originales en `referencias/`, `crudos/` y `sonidos/`. Terminados en `salida/`. Mantén `LEEME.md` al día.
- Credenciales solo en `.env` (nunca en el código ni en git). Habla en español simple.

## Ahorro de tokens (obligatorio)
- Editar un video = UN comando: `python editar.py crudos/video.mp4`. No escribas código nuevo por video; si algo falla, arregla `herramientas/editar.py` una vez.
  - Si no existe `crudos/video.json`, el script lo crea solo (título = 1ª frase; lista = "número N, las X"; tomas en `crudos/<video>_broll/N*.mp4` o `crudos/broll/N-*.mp4`; fotos en `assets/productos/N-*.png`). Para corregir nombres, edita solo ese .json y vuelve a correr.
- Las referencias ya están analizadas en `estilo.json`. NO las vuelvas a analizar salvo que el usuario lo pida.
- ffmpeg siempre con `-hide_banner -loglevel error`. Logs largos a archivo (`trabajo/<video>/editar.log`); si algo falla, lee solo las últimas 20 líneas (`tail -n 20`).
- No muestres barras de progreso: redirige la salida de pip, rembg, auto-editor, Whisper y Demucs a un .log (`> x.log 2>&1`) y mira solo el final.
- Revisión de calidad: máximo 3 fotogramas por video a 480 px de ancho, usando `trabajo/<video>/revision.jpg` (el script la genera). Una sola imagen por revisión.
- No leas ni muestres transcripciones, JSON o logs completos: usa `grep`, `head`/`tail` o `python -c` para sacar solo el dato necesario. El resumen del video es la línea `OK ...` que imprime el script.
- No re-renderices para ajustes pequeños sin necesidad: junta varias correcciones y renderiza una vez.
