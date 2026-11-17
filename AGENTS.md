# AGENTS.md

Guia operativa para cualquier agente que trabaje en este repositorio. Leer completa antes de editar.

## Reglas duras (leer primero)

- No agregar frameworks, bundlers ni build step al frontend: HTML, CSS y JavaScript puro.
- No agregar dependencias nuevas sin justificar el problema real que resuelven. Hoy la unica dependencia es `yt-dlp`.
- No cambiar `http.server` por Flask/FastAPI ni reescribir el servidor.
- No commitear, crear ramas ni abrir PR sin pedido explicito del usuario.
- No subir descargas, caches, cookies, credenciales ni archivos `.mp4`.
- No romper `/health`, `/healthz`, `/preview` con `Range` ni el streaming directo de descargas.
- No cambiar nombres de endpoints, parametros ni campos JSON existentes sin actualizar `web/app.js`, `README.md` y este archivo.
- Probar siempre con reinicio del servidor y `Ctrl+F5` en el navegador, porque `app.js` y `styles.css` quedan cacheados.
- Mensajes de error visibles: espanol sin acentos, igual que el resto del codigo.

## Proyecto y alcance

Aplicacion local/web para descargar videos de X/Twitter: interfaz oscura, seleccion de calidad, vista previa, descarga directa, posts con varios videos y recorte por tiempo.

- No es una API publica ni multiusuario.
- No guarda historial, cuentas ni archivos descargados.
- Los jobs viven en memoria: al reiniciar el servidor se pierden y hay que volver a presionar `Cargar`.
- El destino de la descarga lo decide el navegador del usuario.

## Stack

- Backend: Python estandar con `http.server` (`ThreadingHTTPServer`).
- Resolver principal: flujo tipo X2Twitter (`x2twitter.com/api/ajaxSearch`) que devuelve MP4 directo de `video.twimg.com`.
- Fallback: `yt-dlp` cuando no hay MP4 directo.
- Recorte: `ffmpeg` (`-c copy`, sin reencodeo).
- Frontend: `web/index.html`, `web/app.js`, `web/styles.css` sin framework.
- Deploy recomendado: Docker en Render (`render.yaml`, `Procfile` como alternativa).

## Como empezar

```powershell
python -m pip install -U -r requirements.txt
python app.py
```

- URL local: `http://127.0.0.1:8765`.
- Variables: `HOST` (default `127.0.0.1`) y `PORT` (default `8765`).
- En Docker/Render: `HOST=0.0.0.0` y `PORT` lo asigna la plataforma.
- `ffmpeg` se busca con `shutil.which` y, en Windows, en WinGet. Si no aparece, `canTrim` queda en `false` y la UI deshabilita el rango.
- Lanzadores: `npm run setup`, `npm start`, `npm run check`.
- Sintaxis: `python -m py_compile .\app.py .\x_video_downloader.py` y `node --check web/app.js`.

## Mapa del proyecto

- `app.py`: todo el backend. Resolver, cache, jobs, endpoints, preview proxy, descarga y recorte.
- `x_video_downloader.py`: CLI independiente basado solo en `yt-dlp`. No comparte codigo con la web.
- `web/index.html`: estructura minima. La lista de videos se construye desde JS.
- `web/app.js`: render de tarjetas, controles propios, polling de preview, seleccion multiple y descarga por formulario.
- `web/styles.css`: tema oscuro, layouts `is-single` / `is-grid`, controles y miniaturas.
- `Dockerfile`, `render.yaml`, `Procfile`, `DEPLOY.md`: deploy. No tocar sin pedido.
- `README.md`: documentacion para usuarios. Mantener sincronizada si cambia el comportamiento visible.
- `AGENTS.md`: este archivo. Actualizarlo si cambian reglas o flujos.

## Flujo de datos

```text
URL de X
  -> extract_info()
       -> extract_info_from_x2twitter()  (cache 10 min)
       -> si falla: yt-dlp skip_download
  -> video_formats()  (normaliza formatos y mediaIndex)
  -> make_job()       (token nuevo en JOBS)
  -> /api/info        (public_job)
  -> /api/preview     (start_preview por media)
  -> /api/preview-status (pending | ready | error)
  -> /preview?token&media (proxy con Range para el navegador)
  -> /download        (form POST, streaming al navegador)
```

- `media_index` ("1", "2", ...) agrupa calidades del mismo video o angulo. En X2Twitter sale de `media_key` (`amplify_video:<id>`, `ext_tw_video:<id>`, `tweet_video:<id>`). En `yt-dlp` sale del orden de `entries`.
- `format_id` identifica la calidad. Los formatos `x2twitter` empiezan con `x2-`.
- `source` distingue `x2twitter` de `yt-dlp`; la UI y la descarga directa dependen de ese campo.
- `direct_format()` y `direct_best_format()` solo devuelven formatos `x2twitter` con URL valida del `media` pedido.
- `public_job()` expone el estado; `job_videos()` elige la mejor calidad por `media_index`.
- El preview descarga con `yt-dlp` solo cuando no hay MP4 directo. Con MP4 directo, `/preview` hace proxy del `video.twimg.com`.

## Contrato de endpoints

| Endpoint | Metodo | Parametros | Respuesta |
| --- | --- | --- | --- |
| `/` | GET | - | `web/index.html` |
| `/web/*` | GET | ruta estatica | archivo de `web/` |
| `/api/info` | POST | JSON `{ "url": "..." }` | job publico (token, title, videos, formats, thumbnail, canTrim, resolver) |
| `/api/preview` | POST | JSON `{ "token": "...", "media": "1" }` | `{ "ok": true }` |
| `/api/preview-status` | GET | query `token`, `media` | `pending`, `ready` con `url`, o `error` con `error` |
| `/preview` | GET | query `token`, `media` | video MP4; soporta `Range` |
| `/download` | POST | form `token`, `format`, `media`, `start`, `end` | MP4 adjunto o JSON de error |
| `/health`, `/healthz` | GET | - | `{ "ok": true }` |

- Errores: `json_response` con `{ "error": "..." }` y status adecuado. Usar `AppError` para errores controlados.
- `format` ausente o igual a `bestvideo+bestaudio/best` significa mejor calidad del `media` pedido. Si falta `media`, se usa `"1"`.
- `start` y `end` aceptan `83`, `1:23` o `00:01:23` (`parse_time`).
- Si el rango cubre todo el video, `is_full_download()` fuerza descarga directa sin recorte.

## Reglas de UI

- Tema oscuro, acento `#1d9bf0`, bordes rectos, sin animaciones decorativas.
- Un solo video: layout reproductor + panel de descarga (`is-single`).
- Varios videos: grid, cada tarjeta con preview, controles, calidad, rango y descarga propios (`is-grid`).
- Controles propios siempre visibles, incluidos videos verticales; no usar `controls` nativo del `<video>`.
- La descarga se envia por formulario a `/download` con `target="downloadFrame"`. Nunca usar `fetch`/blob para descargar.
- Seleccion multiple: cada tarjeta conserva su `media`, calidad y rango al presionar `Descargar seleccionados`.
- Estados visibles: `Listo`, `Buscando`, `Calidades encontradas`, `Descargando`, `Error`. Mantenerlos en espanol.
- El stage usa `aspect-ratio` con `width`/`height` del mejor formato de cada video y `object-fit: contain`.

## Titulo y miniaturas

- `short_title()`: 6 palabras y 50 caracteres como maximo, corta en la ultima palabra completa y agrega `…`. Se usa para el encabezado y para el nombre de archivo. No mostrar el texto completo del tweet.
- `.collection-head h2` debe conservar `line-clamp: 2`, `overflow-wrap: anywhere` y `min-width: 0` en el contenedor. Sin eso, textos largos o sin espacios desbordan el layout.
- `video_thumbnail_url()`: solo acepta `https://pbs.twimg.com/...` con `_video_thumb` en el path. Descarta logos, publicidad y rutas relativas que X2Twitter pueda mezclar.
- Las miniaturas se deduplican y se asignan por `media_index`.
- En el navegador, la miniatura usa `referrerPolicy="no-referrer"`. Si falla la carga, se oculta, se quita `src` y se limpia el `poster`; nunca dejar el icono de imagen rota.
- La preview de videos restringidos debe apuntar siempre a `/preview`, nunca directo a `video.twimg.com`.

## Nombres de archivo

Formato:

```text
6 palabras @usuario ddmmyy mm-ss.mp4
```

- En posts con varios videos se agrega ` video-N` antes de la extension.
- La duracion usa `-` en lugar de `:` porque Windows no permite `:`.
- `clean_filename()` quita caracteres invalidos y limita a 140 caracteres (incluye usuario, fecha y duracion).
- `content_disposition_attachment()` genera `filename*` UTF-8 con fallback ASCII (`ascii_header_filename`) para evitar errores de `latin-1`.
- Si cambias el formato, actualiza `README.md` y este archivo en el mismo cambio.

## Descarga, streaming y recorte

- Con formato `x2twitter`: `send_direct_download()` abre `video.twimg.com`, envia headers (UA, `Referer: https://x.com/`) y copia por chunks con `shutil.copyfileobj`.
- Sin MP4 directo: `download_to_file()` usa `yt-dlp` en un directorio temporal dentro del cache y devuelve el MP4 generado.
- Con recorte: `ffmpeg_trim_direct()` usa `-ss`, `-t`/`-to` y `-c copy`. No reencodea.
- Mantener los bytes saliendo por streaming al navegador; no cargar el archivo completo en memoria.
- En descarga directa completa, enviar headers HTTP lo antes posible.

## Rendimiento y cache

- `X2_CACHE_TTL_SECONDS = 600`: cachear metadata de X2Twitter por enlace y devolver `copy.deepcopy` para no compartir estado.
- `JOBS` y `X2_CACHE` se acceden siempre bajo `JOBS_LOCK` / `X2_CACHE_LOCK`.
- Limites conocidos (no arreglar sin pedido): `JOBS` no se limpia por antiguedad y los temporales de recorte no se borran.
- Evitar `yt-dlp` y `ffmpeg` salvo recorte o ausencia de MP4 directo.

## Seguridad

- No subir cookies, caches ni credenciales. La CLI permite cookies solo en uso local.
- Nunca loggear tokens de jobs, URLs privadas ni contenido del usuario.
- Al proxear URLs, mantener el filtro de esquema y host; no aceptar URLs arbitrarias del cliente.
- `/web/*` sirve archivos de `web/`; no agregar rutas dinamicas sin validar traversal (hoy no hay validacion explicita).
- Respetar derechos de autor y terminos de X; no agregar funciones de evasion de bloqueos.

## Que no tocar

- Endpoints, parametros y campos JSON existentes.
- Comportamiento de descarga por formulario/iframe.
- Layout single/grid y controles propios.
- `Dockerfile`, `render.yaml`, `Procfile` y `DEPLOY.md` sin pedido.
- `x_video_downloader.py` cuando el cambio es solo de la web.
- No reformatear archivos completos, no renombrar funciones existentes y no mover codigo sin necesidad.

## Mantenibilidad y estilo

- Cambios quirurgicos y diffs chicos; resolver el problema antes de agregar abstracciones.
- Reusar helpers existentes: `clean_filename`, `short_title`, `video_thumbnail_url`, `media_matches`, `download_basename`, `preview_key`.
- Funciones nuevas: nombre claro, sin dependencias globales nuevas y con lock si comparten estado.
- Comentarios solo para el "por que" no obvio. Evitar comentarios que repiten el codigo.
- Mantener compatibilidad Python 3.8+ (`from __future__ import annotations` ya esta en los modulos).
- Si agregas estado en memoria, define su clave, su TTL o su limpieza, y documentalo.
- Preferir borrar codigo muerto antes que dejarlo "por si acaso".

## Verificacion antes de entregar

- `python -m py_compile .\app.py .\x_video_downloader.py`
- `node --check web/app.js`
- Levantar `python app.py`, recargar con `Ctrl+F5` y probar:
  - un post de un solo video: titulo corto, miniatura, calidades y descarga completa;
  - un post de varios videos si se toco agrupacion o seleccion multiple;
  - un recorte si hay `ffmpeg`;
  - que `/healthz` responda `{ "ok": true }`.
- Prueba rapida de metadata:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/api/info -Method Post -ContentType application/json -Body '{"url":"https://x.com/i/status/2056229877867536881"}' | Select-Object title, downloadName, resolver
```

- No hay suite automatica de tests; la verificacion es manual y con estos comandos.

## Commits

- Commits con conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- Body corto, en bullets con guion y cada bullet en una sola linea.
- Un commit por cambio logico; no mezclar refactor con fix si se puede separar.
- Sin ramas nuevas ni PR: todo va a la rama por defecto cuando el usuario lo pida.
- Nunca commitear secretos, caches, `__pycache__` ni descargas.

## Deploy

- Docker instala `ffmpeg`, por eso el recorte funciona en Render.
- Render: runtime `Docker`, `dockerfilePath: ./Dockerfile`, health check `/healthz`, `HOST=0.0.0.0`.
- `PORT` lo asigna Render; no hardcodearlo.
- No usar GitHub Pages: la app necesita backend Python.

## Troubleshooting

- X2Twitter responde `statusCode 404`: post privado, borrado o sin video. No es un bug de la app.
- No aparecen videos: revisar que `extract_info_from_x2twitter` siga encontrando `Download MP4`; si cambio el HTML, ajustar el regex y probar con dos posts distintos.
- Miniatura ausente es normal si X no la genero; debe ocultarse sin icono roto.
- Preview 404 o "Video no encontrado": el servidor se reinicio o el token expiro; recargar el enlace.
- Recorte deshabilitado: falta `ffmpeg` en PATH.
- Descarga lenta: es esperable con `yt-dlp` o recorte; la descarga directa debe abrir el dialogo casi al instante.

## Glosario

- **Job**: metadata resuelta de un post, guardada en `JOBS` con un `token`.
- **Token**: id temporal del job; viaja en `/api/preview`, `/preview` y `/download`.
- **Media index**: indice del video dentro del post (`1`, `2`, ...).
- **Formato directo**: URL MP4 de `video.twimg.com` resuelta por X2Twitter.
- **Preview**: video que ve el usuario; siempre por `/preview` cuando es directo.
- **Recorte**: segmento generado con `ffmpeg` a partir de un rango de tiempo.
