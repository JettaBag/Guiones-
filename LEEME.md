# editor-videos

Editor automático de videos "Top N de zapatillas" para TikTok, Reels y Shorts.

## Carpetas

| Carpeta | Qué va aquí |
|---|---|
| `referencias/` | Videos de ejemplo del estilo que quieres copiar (ya analizados: ref1–ref5). |
| `crudos/` | Tus videos sin editar + las tomas de cada zapatilla + un `.json` por video con título, lista y si lleva música. |
| `sonidos/` | Tus sonidos de retención (whoosh, pop, impactos, risers, memes), con `catalogo.json`. |
| `salida/` | Videos terminados, listos para subir (MP4 H.264, 1080x1920, −14 LUFS). |
| `analisis/` | Lo que se midió de cada referencia (transcripción, recortes de texto, hojas de contacto). |
| `herramientas/` | Los programas: `analizar_estilo.py` (Fase 1), `editar.py` (Fase 2), `organizar.ps1` (ordenar archivos en Windows). |
| `assets/` | Fuentes (Montserrat, Anton, Barlow Condensed), biblioteca de sonidos y `productos/` (fotos de zapatillas sin fondo que entran con pop). |
| `estilo.json` | El estilo medido de las referencias + tus decisiones. |

## Reglas
- Los archivos se **copian**, nunca se mueven: los originales quedan donde estaban.
- No se borra nada de `referencias/` ni de `crudos/`.
- Cada video terminado lleva su reporte en `trabajo/<video>/reporte.json`.

## Ordenar tus archivos en Windows
En PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File herramientas\organizar.ps1            # crea Escritorio\editor-videos y lista archivos recientes
powershell -ExecutionPolicy Bypass -File herramientas\organizar.ps1 -Copiar     # copia según la lista que marcaste
```

## Fotos de producto
`assets/productos/N-nombre.png` (sin fondo). En el `.json` del video: `"recorte": "assets/productos/...png"` en cada item. Aparece con pop al nombrar la zapatilla (~2,5 s). Plantilla: `crudos/plantilla_top5.json`.
