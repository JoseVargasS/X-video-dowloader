# X Video Downloader

Aplicacion web para descargar videos de X/Twitter con tema oscuro, calidad seleccionable, vista previa, boton de pegar, soporte para posts con varios videos y recorte por tiempo.

La app prioriza enlaces MP4 directos de `video.twimg.com` mediante el resolver tipo X2Twitter. Eso hace que la descarga completa empiece casi al instante en el navegador y evita usar CPU local. Si no hay MP4 directo, usa `yt-dlp` como respaldo. Si eliges recorte por tiempo, usa `ffmpeg`.

## Caracteristicas

- Interfaz oscura con acento celeste estilo Twitter/X.
- Favicon propio en SVG.
- Boton `Pegar` para reemplazar el input con el contenido del portapapeles.
- Vista previa con controles propios visibles en videos horizontales, cuadrados y verticales.
- Soporte para posts con uno o varios videos.
- Si el post tiene un solo video, se muestra en el layout amplio clasico.
- Si el post tiene varios videos, se muestran todos en un grid con reproductor, calidad, rango y descarga propios.
- Seleccion multiple para descargar uno o varios videos del mismo post.
- Titulo compacto: el texto completo del tweet se recorta para que el encabezado no crezca sin control.
- Miniatura validada: solo se aceptan imagenes reales de video de `pbs.twimg.com`; si X no la tiene, se oculta en lugar de mostrar una imagen rota.
- Proxy `/preview` con soporte `Range` para reproducir videos restringidos sin 403 del navegador.
- Seleccion de calidades detectadas.
- Descarga directa por formulario, no por `fetch`/blob, para que el dialogo del navegador aparezca rapido.
- Nombre de archivo generado con descripcion, usuario, fecha y duracion; en posts con varios videos agrega `video-1`, `video-2`, etc.
- `Content-Disposition` compatible con nombres UTF-8 y fallback ASCII para evitar errores de `latin-1`.
- Endpoints `/health` y `/healthz` para Render.

## Requisitos

- Python 3.8+
- `ffmpeg` para recortar videos
- Dependencias de `requirements.txt`

En Docker, `ffmpeg` ya se instala dentro de la imagen.

## Uso local

```powershell
python -m pip install -U -r requirements.txt
python app.py
```

Tambien puedes usar npm como lanzador comodo:

```powershell
npm run setup
npm start
```

Abre:

```text
http://127.0.0.1:8765
```

Flujo normal:

1. Pega un enlace de X/Twitter o usa `Pegar`.
2. Presiona `Cargar`.
3. Revisa la vista previa.
4. Si hay un video, elige calidad y descarga desde el panel lateral.
5. Si hay varios videos, cada tarjeta tiene su propia calidad, rango y boton `Descargar`.
6. Opcionalmente define inicio y fin en el video que quieras recortar.
7. Para descargar varios, marca `Incluir` en cada tarjeta y usa `Descargar seleccionados`.

La descarga se guarda donde tu navegador tenga configuradas sus descargas.

## Desarrollo

Comandos para trabajar en la app:

```powershell
python -m pip install -U -r requirements.txt
python app.py
node --check web/app.js
python -m py_compile .\app.py .\x_video_downloader.py
```

Variables de entorno:

- `HOST`: interfaz donde escucha el servidor (default `127.0.0.1`).
- `PORT`: puerto (default `8765`). En Render se asigna automaticamente.

Para probar metadata sin abrir el navegador, con la app corriendo:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/info -Method Post -ContentType application/json -Body '{"url":"https://x.com/i/status/2056229877867536881"}' | Select-Object title, downloadName, resolver
```

Notas utiles:

- Reinicia el servidor despues de tocar `app.py`.
- Usa `Ctrl+F5` despues de tocar `app.js` o `styles.css`; si no, el navegador puede seguir usando la version en cache.
- No hay suite automatica de tests: la verificacion es manual (cargar un post, revisar preview y descargar).
- Las reglas de desarrollo, estructura y cosas que no se deben romper estan en `AGENTS.md`.

## Descarga por CLI

```powershell
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881"
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --list
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --quality 720p
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --cookies-from-browser chrome
```

## Nombre de archivo

Formato:

```text
primeras 6 palabras @usuario ddmmyy mm-ss.mp4
```

Ejemplo:

```text
Benjamin Netanyahu hands over the script @IndiaTales7 170526 0-26.mp4
```

En Windows se usa `-` en la duracion porque `:` no es valido en nombres de archivo.

Cuando un post tiene varios videos, el nombre agrega el indice del video:

```text
primeras 6 palabras @usuario ddmmyy mm-ss video-2.mp4
```

La descripcion se recorta a las primeras 6 palabras y a 50 caracteres como maximo (`short_title()`), cortando en la ultima palabra completa. En idiomas sin espacios entre palabras (birmano, tailandes, chino) el recorte se hace por caracteres para que el nombre no se vuelva gigante.

## Titulo y miniaturas

El encabezado del post y el nombre del archivo usan el mismo texto corto: `short_title()` en `app.py` toma las primeras 6 palabras, limita a 50 caracteres, corta en el ultimo espacio disponible y agrega `…` cuando recorta.

- `web/styles.css` limita `#videoTitle` a dos lineas (`line-clamp`), habilita `overflow-wrap: anywhere` y deja que el bloque se encoja (`min-width: 0`). Ese ultimo punto es el que evita el desborde horizontal con textos largos o sin espacios.
- El nombre del archivo queda como `descripcion-corta @usuario ddmmyy mm-ss.mp4` (normalmente menos de 90 caracteres en total).
- Si recortar deja solo una palabra larguisima sin espacios, igual se corta a 50 caracteres.

Las miniaturas vienen del HTML que devuelve X2Twitter en etiquetas `<img src="...">`. Antes se tomaba cualquier imagen y se asignaba por posicion, lo que a veces terminaba mostrando publicidad, un logo o una ruta relativa. Ahora:

- `video_thumbnail_url()` solo acepta URLs absolutas `https://pbs.twimg.com/...` cuyo path contenga `_video_thumb` (cubre `amplify_video_thumb`, `ext_tw_video_thumb` y `tweet_video_thumb`).
- Se descartan logos, publicidad, rutas relativas y cualquier otro host.
- Las URLs se deduplican y se asignan una por video segun `media_index`.

En el navegador, `web/app.js` carga la miniatura con `referrerPolicy="no-referrer"`. Si la descarga de la imagen falla (X no genero la miniatura o ya no existe), oculta la imagen y limpia el `poster` del reproductor, asi nunca queda el icono de imagen rota sobre el video.

## Arquitectura

Backend:

- `app.py`: servidor HTTP con `http.server`. Resuelve metadata, agrupa videos, recorta el titulo visible (`short_title`) y valida miniaturas (`video_thumbnail_url`).
- `x_video_downloader.py`: descargador CLI con `yt-dlp`.
- `ffmpeg`: recorte cuando el usuario elige un rango.

Frontend:

- `web/index.html`: estructura.
- `web/styles.css`: tema visual.
- `web/app.js`: carga de metadata, controles de video y descarga.
- `web/favicon.svg`: icono de la app.

Endpoints principales:

| Endpoint | Metodo | Uso |
| --- | --- | --- |
| `/` | GET | Interfaz web |
| `/web/*` | GET | Archivos estaticos |
| `/api/info` | POST | Metadata, videos detectados y calidades |
| `/api/preview` | POST | Inicia preparacion de preview para un video del post |
| `/api/preview-status` | GET | Estado de preparacion de preview por `token` y `media` |
| `/download` | POST | Descarga directa o procesada; acepta `media`, `format`, `start` y `end` |
| `/preview` | GET | Proxy de video por `token` y `media` con soporte `Range` |
| `/health`, `/healthz` | GET | Health checks para deploy |

Flujo de resolucion:

```text
URL de X
  -> X2Twitter / MP4 directo
      -> agrupa calidades por video detectado en video.twimg.com
      -> descarga streaming inmediata desde video.twimg.com
  -> si no hay MP4 directo, yt-dlp
      -> descarga HLS y mezcla con ffmpeg si hace falta
  -> si hay recorte
      -> ffmpeg procesa el rango elegido
```

## Docker

```powershell
docker build -t x-video-downloader .
docker run -p 8765:8765 -e HOST=0.0.0.0 -e PORT=8765 x-video-downloader
```

Luego abre `http://127.0.0.1:8765`.

## Deploy en Render

Render puede usar el `Dockerfile` y `render.yaml` incluidos.

Configuracion recomendada:

- Runtime: `Docker`
- Branch: `main`
- Root Directory: vacio
- Dockerfile path: `./Dockerfile`
- Environment Variables: ninguna obligatoria si usas `render.yaml`; manualmente puedes poner `HOST=0.0.0.0`
- Health Check Path: `/healthz`

Render define `PORT` automaticamente. No uses GitHub Pages para esta app porque necesita backend Python.

## Solucion de problemas

Si la vista previa muestra 403 o no reproduce:

- Verifica que el `src` del video apunte a `/preview?...`, no a `video.twimg.com`.
- Recarga metadata con `Cargar`.

Si la descarga tarda:

- La descarga completa por MP4 directo debe abrir rapido el dialogo del navegador.
- El recorte siempre demora mas porque requiere `ffmpeg`.
- El fallback `yt-dlp` tambien puede tardar porque descarga y mezcla fragmentos HLS.

Si un post con varios videos no muestra todos:

- Presiona `Cargar` otra vez para renovar metadata y URLs temporales.
- Si X2Twitter solo entrega el primer media para ese post, la app puede necesitar fallback por `yt-dlp`.
- Comparte el enlace de prueba al depurar, porque X cambia el HTML y las respuestas segun el tipo de post.

Si la miniatura no aparece:

- Puede ser un post donde X no genero thumbnail. El video se reproduce igual desde `/preview`.
- Si ves el icono de imagen rota, fuerza recarga con `Ctrl+F5` para descartar un `app.js` viejo en cache.
- Si la miniatura aparece pero de otro contenido, revisa que `X2Twitter` no haya cambiado el HTML: `video_thumbnail_url()` deberia seguir filtrando solo `pbs.twimg.com`.

Si el titulo sale larguisimo:

- Verifica que `short_title()` siga aplicandose en `public_job()` y que `.collection-head h2` conserve `line-clamp` y `overflow-wrap`.

Si `ffmpeg` no existe:

```powershell
where ffmpeg
```

Instalalo en Windows o usa Docker.

## Seguridad

- No subas cookies, caches ni credenciales.
- Usa cookies del navegador solo en local y solo si necesitas acceder a contenido de tu cuenta.
- Respeta derechos de autor, terminos de servicio y privacidad del contenido que descargues.

## Licencia

Uso personal y educativo.
