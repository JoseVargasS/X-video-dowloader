# X Video Downloader

Aplicacion web para descargar videos de X/Twitter con tema oscuro, calidad seleccionable, vista previa, boton de pegar y recorte por tiempo.

La app prioriza enlaces MP4 directos de `video.twimg.com` mediante el resolver tipo X2Twitter. Eso hace que la descarga completa empiece casi al instante en el navegador y evita usar CPU local. Si no hay MP4 directo, usa `yt-dlp` como respaldo. Si eliges recorte por tiempo, usa `ffmpeg`.

## Caracteristicas

- Interfaz oscura con acento celeste estilo Twitter/X.
- Favicon propio en SVG.
- Boton `Pegar` para reemplazar el input con el contenido del portapapeles.
- Vista previa con controles propios visibles en videos horizontales, cuadrados y verticales.
- Proxy `/preview` con soporte `Range` para reproducir videos restringidos sin 403 del navegador.
- Seleccion de calidades detectadas.
- Descarga directa por formulario, no por `fetch`/blob, para que el dialogo del navegador aparezca rapido.
- Nombre de archivo generado con descripcion, usuario, fecha y duracion.
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
4. Elige calidad.
5. Opcionalmente define inicio y fin para recortar.
6. Presiona `Descargar`.

La descarga se guarda donde tu navegador tenga configuradas sus descargas.

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

## Arquitectura

Backend:

- `app.py`: servidor HTTP con `http.server`.
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
| `/api/info` | POST | Metadata, calidades y preview |
| `/api/preview-status` | GET | Estado de preparacion de preview |
| `/download` | GET/POST | Descarga directa o procesada |
| `/preview` | GET | Proxy de video con soporte `Range` |
| `/health`, `/healthz` | GET | Health checks para deploy |

Flujo de resolucion:

```text
URL de X
  -> X2Twitter / MP4 directo
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
