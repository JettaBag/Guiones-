# Proyecto: prospección de clientes para Jetta_Sk (cajas para zapatos)

## Regla obligatoria: revisar duplicados antes de entregar clientes

Antes de entregar cualquier lista de clientes nuevos:

1. Compara cada candidato contra `historial-contactos.json` con:
   `python3 scripts/revisar_duplicados.py revisar candidatos.json`
2. Normaliza los números antes de comparar: quita espacios, guiones, puntos y paréntesis,
   y el `+57` o `57` del inicio ("+57 312 123 4567", "3121234567" y "57-312-123-4567" son el mismo).
3. **Repetido** (no se entrega): el mismo número normalizado (incluidos los "otros números"
   del contacto), la misma cuenta de Instagram, TikTok o Facebook en cualquier red, o el mismo
   link de perfil. No entregues ninguno que ya esté en el historial, aunque lo hayas encontrado
   en otra red social.
4. **Posible repetido** (no se entrega como nuevo; se marca para que el usuario decida): el mismo
   nombre de negocio normalizado, un nombre muy parecido, o un usuario que solo cambia en
   puntos o guiones bajos.
   Al limpiar una lista ya entregada: de cada grupo repetido deja solo uno; si alguno ya tiene
   estado (enviado, respondió…) consérvalo y borra el duplicado vacío. Los borrados pasan a
   `descartados` del historial y siguen bloqueando búsquedas futuras.
5. Al entregar, guarda los nuevos y los posibles en el historial con
   `python3 scripts/revisar_duplicados.py agregar candidatos.json --lista "Lista N"`.
   Los repetidos quedan anotados en `descartados`.
6. Dile al usuario: "X contactos nuevos · Y repetidos descartados · Z posibles repetidos",
   y cuáles fueron los repetidos.
7. Para auditar el historial completo: `python3 scripts/revisar_duplicados.py auditar`.

## Página de seguimiento

- Artifact: https://claude.ai/artifact/QNzXoKSgVDP3QV7FvtADkg (copia local: `seguimiento_envios.html`).
- Guarda el estado en localStorage y en la base de datos de la página (colección `seguimiento`).
  El historial de contactos entregados también se guarda en localStorage (`jetta_historial_contactos`).
- Al agregar una lista nueva, mantén los ids de los contactos existentes: el estado guardado depende de ellos.

## Sistema semanal de la tienda de tenis ("corre el sistema de la semana")

Tienda de tenis en Medellín (marca Jetta Sk, Shopify "Mi tienda"). Vende por TikTok, Instagram y Facebook y cierra por WhatsApp. Precios de 180.000 a 220.000 COP.
Cuando el usuario diga **"corre el sistema de la semana"**, haz estos 3 pasos en orden y guarda todo en `sistema-tenis/`. Trabaja por pasos y explica en español sencillo.

1. **PRODUCTO** → `sistema-tenis/productos-semana.md`
   - Tendencias de las últimas semanas en Colombia: Google Trends (Colombia, últimos 3 meses) con `python3 scripts/google_trends.py "termino1,termino2,..."` (máximo 5 términos por consulta), TikTok Creative Center (si hay acceso) y búsquedas web.
   - Cruza con el catálogo de Shopify (productos "Ref. 0XX") y con la tabla de equivalencias referencia → estilo que dé el usuario (`sistema-tenis/catalogo-estilos.md` cuando exista).
   - Elige 3 referencias que YA tenga y explica por qué.
   - Margen = precio − costo del par − envío − caja − bolsa (− comisión de contraentrega). Pregunta los costos que no sepas.
2. **ANUNCIO** → `sistema-tenis/anuncios-semana.md`
   - Biblioteca de anuncios de Meta (Colombia, tenis): prioriza los anuncios con más días activos. Para los 10 mejores: días activos, gancho, ángulo (precio, comodidad, estilo, regalo, novia, trabajo), oferta y llamado a la acción.
   - Lo mismo en TikTok Creative Center → Top Ads, Colombia.
   - 5 guiones: gancho → problema → solución → por qué nosotros → precio exacto con beneficio ("180 mil con envío incluido") → 2 llamados a la acción (WhatsApp / sígueme). Tono de paisa joven, natural, para teleprompter.
   - NO copies anuncios textuales de otras marcas; usa solo los patrones.
3. **CAMPAÑA** → `sistema-tenis/campana-semana.md`
   - Meta Ads por Windsor.ai (conector `facebook`) o la API oficial.
   - Campaña de mensajes a WhatsApp, Medellín y alrededores, 3 conjuntos de anuncios (uno por ángulo), presupuesto de prueba pequeño.
   - **NUNCA** crear, activar ni subir presupuesto sin mostrar antes el resumen (presupuesto diario, público y anuncios) y que el usuario diga **"aprobado"**.
   - Tarea programada cada mañana a las 7:00 (hora Colombia): reporte del día anterior (costo por mensaje, mensajes recibidos, gasto) con recomendaciones de qué apagar y a cuál pasarle presupuesto. Solo recomienda; el usuario decide.

Reglas del sistema:
- Ahorra tokens: no mires imágenes salvo que sea necesario; máximo 5 capturas por búsqueda y en baja resolución.
- Explica todo en español sencillo.

## Otras reglas del proyecto

- Nunca inventes números: si no aparece, escribe "no encontrado".
- Verifica el WhatsApp en el perfil, la bio, el link de la bio o la web antes de marcarlo como verificado.
- Separa las marcas que fabrican su propio calzado (cuero, tacones, botas, "hecho en Colombia") con el mensaje de cajas personalizadas con su marca.
- Primer mensaje: corto, una pregunta, sin precios ni links. La oferta solo cuando la tienda responda.
