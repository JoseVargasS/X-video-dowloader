# AGENTS.md

## Proyecto

Aplicacion local/web para descargar videos de X/Twitter con interfaz oscura, seleccion de calidad, vista previa, descarga directa y recorte por tiempo.

## Stack

- Backend: Python estandar con `http.server`.
- Extraccion principal rapida: resolver estilo X2Twitter para obtener MP4 directo desde `video.twimg.com`.
- Fallback: `yt-dlp` cuando no hay MP4 directo.
- Recorte: `ffmpeg`.
- Frontend: HTML, CSS y JavaScript sin framework.
- Deploy recomendado: Docker en Render.

## Reglas de implementacion

- Mantener la app simple, sin build step frontend.
- No subir descargas, caches, cookies ni credenciales.
- Usar tema oscuro, acento celeste tipo Twitter y bordes rectos.
- La descarga debe usar el destino configurado por el navegador.
- Los controles de video deben ser propios y visibles tambien para videos verticales.
- La descarga debe enviarse directo al navegador, no con `fetch`/blob, para evitar esperar a cargar todo el archivo en memoria antes de mostrar el dialogo.
- Resolver MP4 directo con X2Twitter antes de usar `yt-dlp`, porque evita CPU local y acelera la descarga.
- Cuando haya formato `x2twitter`, descargar por streaming directo desde `video.twimg.com` con headers inmediatos y `Content-Disposition` propio.
- Evitar `yt-dlp` y `ffmpeg` salvo recorte o ausencia de MP4 directo.
- La vista previa de videos restringidos no debe apuntar directamente a `video.twimg.com`; usar `/preview` como proxy con soporte `Range`.
- Para nombres de archivo usar: primeras 6 palabras de descripcion + `@usuario` + fecha `ddmmyy` + duracion.
- Mantener `/health` y `/healthz` funcionando para deploy.

## Optimizacion

- Cachear metadata resuelta por X2Twitter por un tiempo corto para evitar consultas repetidas al mismo enlace.
- Mantener streaming en chunks y no convertir descargas completas a blobs en frontend.
- En descarga completa con MP4 directo, iniciar headers HTTP de respuesta lo antes posible.
- Usar `ffmpeg` solo si el usuario pide recorte.

## Comandos utiles

```powershell
python -m pip install -U -r requirements.txt
python app.py
npm run setup
npm start
npm run check
python -m py_compile .\app.py .\x_video_downloader.py
```

## Deploy

Preferir Docker porque instala `ffmpeg` y mantiene disponible el recorte por tiempo.

En Render:

- Runtime: `Docker`.
- Root Directory: vacio.
- Health Check Path: `/healthz`.
- Environment Variables: ninguna obligatoria con `render.yaml`; si se configura manualmente usar `HOST=0.0.0.0`.

Render asigna `PORT` automaticamente.
