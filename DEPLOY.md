# Deploy en GitHub y Render

La interfaz necesita un backend Python para consultar X y ejecutar `yt-dlp`, asi que no funciona solo con GitHub Pages. La ruta mas simple es subir el proyecto a GitHub y desplegarlo en Render.

## 1. Subir a GitHub

Desde esta carpeta:

```powershell
git init
git add .
git commit -m "Create X video downloader app"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/x-video-downloader.git
git push -u origin main
```

Antes de `git remote add`, crea el repositorio vacio en GitHub.

## 2. Deploy en Render

1. Entra a https://render.com.
2. Crea un `New Web Service`.
3. Conecta tu repositorio de GitHub.
4. Render detectara `render.yaml` y usara el `Dockerfile`.
5. Confirma el deploy.

Si lo haces manualmente:

- Runtime: `Docker`
- Dockerfile path: `./Dockerfile`
- Environment variable: `HOST=0.0.0.0`

Render asigna `PORT` automaticamente.

## 3. Sobre recortes de video

La descarga completa funciona con Python y `yt-dlp`. Para recortar por minuto/segundo, el servidor necesita `ffmpeg`.

El `Dockerfile` incluido instala `ffmpeg`, asi que los recortes quedan disponibles en servicios que desplieguen el contenedor.

## 4. Videos restringidos

La app intenta primero `yt-dlp`. Si X no expone el video como media normal, usa un fallback compatible con enlaces directos de `video.twimg.com`, similar a los descargadores web.

## 5. Recomendacion importante

No subas cookies personales al repositorio. Si X pide sesion para ciertos videos, usa la app local o configura un servidor privado.
