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

La descarga completa usa primero MP4 directo de `video.twimg.com` cuando el resolver lo encuentra. Para recortar por minuto/segundo, el servidor necesita `ffmpeg`.

El `Dockerfile` incluido instala `ffmpeg`, asi que los recortes quedan disponibles en servicios que desplieguen el contenedor.

## 4. Posts con varios videos

La interfaz soporta posts con varios videos. En esos casos muestra un grid de tarjetas: cada video tiene preview, calidad, rango de recorte y descarga propios. Tambien permite seleccionar varios videos y enviarlos al navegador como descargas separadas.

El navegador puede pedir permiso para multiples descargas si se usa `Descargar seleccionados`.

## 5. Videos restringidos

La app intenta primero resolver MP4 directo con un flujo tipo X2Twitter. Si no hay MP4 directo, usa `yt-dlp` como fallback. Las previews de MP4 directo pasan por `/preview` con soporte `Range` para evitar que el navegador apunte directo a `video.twimg.com`.

## 6. Recomendacion importante

No subas cookies personales al repositorio. Si X pide sesion para ciertos videos, usa la app local o configura un servidor privado.
