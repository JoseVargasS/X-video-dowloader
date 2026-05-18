# AGENTS.md

## Proyecto

Aplicacion local/web para descargar videos de X/Twitter con interfaz oscura, seleccion de calidad, vista previa y recorte por tiempo.

## Stack

- Backend: Python estándar con `http.server`
- Extraccion principal: `yt-dlp`
- Fallback para videos restringidos: endpoint de X2Twitter que devuelve enlaces directos `video.twimg.com`
- Resolver MP4 directo con X2Twitter antes de usar `yt-dlp`, porque evita CPU local y acelera el dialogo de descarga.
- Recorte: `ffmpeg`
- Frontend: HTML, CSS y JavaScript sin framework

## Reglas de implementacion

- Mantener la app simple, sin build step frontend.
- No subir descargas, caches, cookies ni credenciales.
- Usar bordes rectos, tema oscuro y acento celeste tipo Twitter.
- La descarga debe usar el destino configurado por el navegador.
- Los controles de video deben ser propios y visibles tambien para videos verticales.
- La descarga debe enviarse directo al navegador, no con `fetch`/blob, para evitar esperar a que todo el archivo se cargue en memoria antes de mostrar el dialogo.
- Cuando haya formato `x2twitter`, descargar por streaming directo desde `video.twimg.com` con headers inmediatos y `Content-Disposition` propio. Evitar `yt-dlp`/`ffmpeg` salvo recorte o ausencia de MP4 directo.
- La vista previa de videos restringidos no debe apuntar directamente a `video.twimg.com`; usar `/preview` como proxy con soporte `Range` para evitar 403 y problemas de reproducción.
- Para nombres de archivo usar: primeras 6 palabras de descripcion + `@usuario` + fecha `ddmmyy` + duracion.

## Comandos utiles

```powershell
python -m pip install -U -r requirements.txt
python app.py
python -m py_compile .\app.py .\x_video_downloader.py
```

## Deploy

Preferir Docker porque instala `ffmpeg` y mantiene disponible el recorte por tiempo.
