# Plantilla Remotion – subtítulos estilo TikTok

Probada el 2026-11-24. Palabra activa en amarillo (#FFD200), entrada con `spring`, 1080x1920.

```bash
cd herramientas/remotion-subtitulos && npm install
mkdir -p public && cp /ruta/video.mp4 public/clip.mp4
# captions.json desde la transcripción local:
python3 ../crear_captions.py /ruta/video.json src/captions.json
# ajusta durationInFrames en src/Root.tsx (segundos × 30)
npx remotion render src/index.ts Clip out.mp4 \
  --browser-executable=/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
```
Licencia Remotion: gratis para personas y empresas de ≤3 empleados; si no, requiere licencia (skill `remotion-license`).
