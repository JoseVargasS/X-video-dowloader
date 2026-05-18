# X Video Downloader

Aplicación web local para descargar videos de X/Twitter con interfaz oscura, selección de calidad, vista previa y recorte por tiempo.

![Tema](https://img.shields.io/badge/tema-oscuro-1a1a2e?style=flat)
![Backend](https://img.shields.io/badge/backend-Python%20http.server-3776ab?style=flat)
![Frontend](https://img.shields.io/badge/frontend-HTML%2FCSS%2FJS%20sin%20framework-0d1117?style=flat)
![Extracción](https://img.shields.io/badge/extracción-yt--dlp%20%2B%20fallback-1da1f2?style=flat)

## Características

- **Interfaz oscura** con acento celeste tipo Twitter
- **Vista previa** con controles propios (play, pausa, progreso, volumen)
- **Selección de calidad** disponible para cada video
- **Recorte por tiempo** usando ffmpeg
- **Descarga directa** al navegador sin pasar por memoria del servidor
- **Fallback inteligente**: intenta MP4 directo antes de usar yt-dlp
- **Proxy de vista previa** con soporte `Range` para evitar 403

## Instalación

### Requisitos previos

- Python 3.8+
- ffmpeg (para recorte de videos)

### Pasos

```powershell
# Instalar dependencias
python -m pip install -U -r requirements.txt

# Verificar ffmpeg (ya debería estar en PATH)
ffmpeg -version
```

> **Nota sobre ffmpeg**: Si el sistema no lo encuentra al mezclar audio/video, agrégalo al `PATH` de Windows.

## Uso

### Interfaz gráfica (recomendado)

```powershell
# Opción 1: Usar el batch file
.\abrir_interfaz.bat

# Opción 2: Ejecutar directamente
python .\app.py
```

Luego abre tu navegador en `http://localhost:8000` (o el puerto que indique la consola).

**Flujo de uso:**

1. Pega un enlace de X/Twitter (o usa el botón `Pegar` para copiar desde clipboard)
2. La app carga el video y muestra la vista previa
3. Selecciona la calidad deseada
4. Opcional: configura recorte por tiempo (inicio y fin en segundos)
5. Haz clic en `Descargar`

El archivo se guarda en la carpeta de descargas configurada en tu navegador.

### Línea de comandos

```powershell
# Descargar con enlace por defecto
python .\x_video_downloader.py

# Descargar un enlace específico
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881"

# Ver calidades disponibles sin descargar
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --list

# Descargar en mejor calidad
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --quality best

# Descargar hasta 720p (mejor variante disponible)
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --quality 720p

# Usar cookies del navegador (para contenido restringido)
python .\x_video_downloader.py "https://x.com/i/status/2056229877867536881" --cookies-from-browser chrome
```

Los archivos descargados se guardan en la carpeta `downloads`.

## Formato de nombres de archivo

Los videos descargados usan este formato:

```
primeras-seis-palabras @usuario ddmmyy mm-ss.mp4
```

Ejemplo: `Video increible de la nueva funcion @usuario 150526 03-42.mp4`

- **Primeras 6 palabras**: Extracto de la descripción del tweet
- **@usuario**: Nombre de usuario del autor
- **ddmmyy**: Fecha en formato día-mes-año
- **mm-ss**: Duración en minutos-segundos (Windows no permite `:` en nombres)

## Arquitectura

### Backend (`app.py`)

Servidor HTTP Python con los siguientes endpoints:

| Endpoint    | Método | Descripción                                                    |
| ----------- | ------ | -------------------------------------------------------------- |
| `/`         | GET    | Sirve la interfaz web (`web/index.html`)                       |
| `/app.js`   | GET    | Sirve el frontend JavaScript                                   |
| `/info`     | POST   | Obtiene información del video (calidades, duración, thumbnail) |
| `/download` | POST   | Descarga el video (streaming directo o procesado)              |
| `/preview`  | GET    | Proxy para vista previa con soporte `Range`                    |
| `/health`   | GET    | Endpoint de salud para deploy                                  |

### Flujo de descarga

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Usuario   │────▶│   Frontend   │────▶│    Backend      │
│   (browser) │     │  (HTML/JS)   │     │   (Python)      │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │                    │
                           │                    ▼
                           │           ┌─────────────────┐
                           │           │ 1. Intenta MP4  │
                           │           │    directo      │
                           │           └────────┬────────┘
                           │                    │
                           │           ┌────────▼────────┐
                           │           │ 2. Si falla,    │
                           │           │    yt-dlp/HLS   │
                           │           └────────┬────────┘
                           │                    │
                           │           ┌────────▼────────┐
                           │           │ 3. Si hay       │
                           │           │    recorte,     │
                           │           │    ffmpeg       │
                           │           └────────┬────────┘
                           │                    │
                           ▼           ┌────────▼────────┐
                    ◀───────────────── │  Streaming     │
                    (download directo) │  directo        │
                                       └─────────────────┘
```

### Estrategia de extracción

1. **Primero**: Intenta resolver MP4 directo (estilo X2Twitter desde `video.twimg.com`)
   - ✅ Evita CPU local
   - ✅ Descarga más rápida
   - ✅ Sin procesamiento HLS

2. **Segundo**: Si no hay MP4 directo, usa `yt-dlp` como fallback
   - Descarga fragments HLS
   - Mezcla audio/video con ffmpeg si es necesario

3. **Recorte**: Si el usuario especifica tiempos, usa `ffmpeg` para cortar el video

### Frontend (`web/`)

- **index.html**: Estructura de la interfaz oscura
- **app.js**: Lógica de comunicación con backend, controles de video y descarga

**Controles de video propios:**

- Play/Pausa
- Barra de progreso scrubable
- Control de volumen
- Funciona con videos verticales y horizontales

## Docker

Para usar con ffmpeg disponible sin instalarlo en el sistema:

```powershell
# Construir imagen
docker build -t x-video-downloader .

# Ejecutar
docker run -p 8000:8000 x-video-downloader
```

## Deploy

Para acceder desde cualquier lugar, despliega como Web Service:

### Plataformas soportadas

- **Render**: Usa `render.yaml` incluido
- **Railway**: Detecta Python automáticamente
- **Fly.io**: Sigue instrucciones en `DEPLOY.md`
- **VPS propio**: Docker o instalación manual

### Consideraciones

- Requiere backend Python (no funciona solo con GitHub Pages)
- ffmpeg debe estar disponible para recorte de videos
- Ver [DEPLOY.md](DEPLOY.md) para instrucciones completas

## Estructura del proyecto

```
X video dowloader/
├── app.py                    # Servidor backend
├── x_video_downloader.py     # CLI downloader
├── requirements.txt          # Dependencias Python
├── web/
│   ├── index.html           # Interfaz web
│   └── app.js               # Lógica frontend
├── abrir_interfaz.bat       # Batch para abrir interfaz
├── descargar_x_video.bat    # Batch para CLI
├── Dockerfile               # Configuración Docker
├── render.yaml              # Configuración Render
└── DEPLOY.md                # Guía de deploy
```

## Solución de problemas

### Error 403 en vista previa

La vista previa usa `/preview` como proxy para evitar errores CORS y 403 de `video.twimg.com`. Si persiste:

1. Verifica que el servidor esté corriendo
2. Revisa la consola del navegador por errores

### ffmpeg no encontrado

```powershell
# Windows: verificar PATH
where ffmpeg

# Si no existe, instalar desde https://ffmpeg.org/download.html
# o usar Docker que ya lo incluye
```

### yt-dlp falla al extraer

Para contenido restringido que requiere login:

```powershell
python .\x_video_downloader.py "URL" --cookies-from-browser chrome
```

### La descarga tarda mucho

- Videos HLS requieren descargar y mezclar fragments
- Recorte con ffmpeg añade tiempo de procesamiento
- Primero intenta MP4 directo (más rápido), luego fallback

## Licencia

Código disponible para uso personal y educativo.

## Créditos

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Extracción de videos
- [ffmpeg](https://ffmpeg.org/) - Recorte y procesamiento de video
