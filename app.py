from __future__ import annotations

import base64
import copy
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, download_range_func


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
CACHE_DIR = Path(tempfile.gettempdir()) / "x-video-downloader-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
X2_CACHE: dict[str, tuple[float, dict]] = {}
X2_CACHE_LOCK = threading.Lock()
X2_CACHE_TTL_SECONDS = 600


def find_ffmpeg_dir() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return str(Path(ffmpeg).parent)

    winget = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "WinGet"
        / "Packages"
    )
    if winget.exists():
        matches = sorted(winget.rglob("ffmpeg.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return str(matches[0].parent)
    return None


FFMPEG_DIR = find_ffmpeg_dir()


class AppError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def json_response(handler: BaseHTTPRequestHandler, data: dict, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def clean_error(value: Exception | str) -> str:
    text = str(value)
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = text.replace("ERROR:", "").strip()
    text = re.sub(r"\s+", " ", text)
    if "No video could be found in this tweet" in text:
        return (
            "No encontre un video descargable en ese post. Si en X si lo ves como video, "
            "puede ser un post privado, restringido o que requiere iniciar sesion."
        )
    if "This tweet is unavailable" in text or "not available" in text.lower():
        return "Ese post no esta disponible publicamente o X lo esta bloqueando sin sesion."
    if "login" in text.lower() or "auth" in text.lower():
        return "X esta pidiendo sesion para ese contenido. Prueba con otro enlace publico o usa la version local con cookies."
    return text or "No se pudo procesar el enlace."


def clean_filename(value: str) -> str:
    value = re.sub(r"[^\w\s.@()_-]", "", value, flags=re.UNICODE).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:140] or "x-video"


def parse_time(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Formato de tiempo invalido")
    total = 0.0
    for part in parts:
        if not re.fullmatch(r"\d+(\.\d+)?", part):
            raise ValueError("Formato de tiempo invalido")
        total = total * 60 + float(part)
    return total


def parse_duration(value: str | None) -> float | None:
    try:
        return parse_time(value)
    except ValueError:
        return None


def format_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def tweet_id_from_url(url: str) -> str | None:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def username_from_url(url: str) -> str | None:
    match = re.search(r"(?:x|twitter)\.com/([^/?#]+)/status/\d+", url)
    if not match or match.group(1) == "i":
        return None
    return match.group(1)


def tweet_date_from_id(tweet_id: str | None) -> str | None:
    if not tweet_id:
        return None
    try:
        timestamp_ms = (int(tweet_id) >> 22) + 1288834974657
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%d%m%y")
    except (TypeError, ValueError, OSError):
        return None


def upload_date(value: dict, url: str) -> str:
    raw_date = value.get("upload_date")
    if raw_date and re.fullmatch(r"\d{8}", str(raw_date)):
        return datetime.strptime(str(raw_date), "%Y%m%d").strftime("%d%m%y")
    timestamp = value.get("timestamp")
    if timestamp:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).strftime("%d%m%y")
    return tweet_date_from_id(tweet_id_from_url(url)) or datetime.now(timezone.utc).strftime("%d%m%y")


def first_words(value: str, count: int = 6) -> str:
    value = re.sub(r"https?://\S+", "", value)
    words = re.findall(r"[\w@#]+", value, flags=re.UNICODE)
    return " ".join(words[:count]) or "video de x"


def download_basename(job: dict) -> str:
    description = first_words(job.get("description") or job.get("title") or "video de x")
    user = str(job.get("uploader_id") or job.get("uploader") or "x").lstrip("@")
    date = job.get("upload_date") or datetime.now(timezone.utc).strftime("%d%m%y")
    # Windows does not allow ":" in filenames, so the visible mm:ss duration is saved as mm-ss.
    duration = (job.get("durationLabel") or "0:00").replace(":", "-")
    return clean_filename(f"{description} @{user} {date} {duration}") + ".mp4"


def ydl_base_options() -> dict:
    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "merge_output_format": "mp4",
    }
    if FFMPEG_DIR:
        options["ffmpeg_location"] = FFMPEG_DIR
    return options


def video_formats(info: dict) -> list[dict]:
    formats = []
    for fmt in info.get("formats") or []:
        if fmt.get("vcodec") in (None, "none"):
            continue
        width = fmt.get("width")
        height = fmt.get("height")
        label = f"{height}p" if height else fmt.get("format_id", "Video")
        if width and height:
            label = f"{height}p ({width}x{height})"
        tbr = fmt.get("tbr")
        if tbr:
            label = f"{label} - {round(float(tbr))} kbps"
        formats.append(
            {
                "id": str(fmt.get("format_id")),
                "label": label,
                "width": width,
                "height": height,
                "fps": fmt.get("fps"),
                "ext": fmt.get("ext"),
                "tbr": tbr,
                "note": fmt.get("format_note") or "",
                "source": fmt.get("source") or "yt-dlp",
                "url": fmt.get("url"),
                "filename": fmt.get("filename"),
            }
        )
    formats.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0), reverse=True)
    return formats


def newest_mp4(directory: Path) -> Path:
    files = sorted(directory.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        files = sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("No se genero ningun archivo descargable")
    return files[0]


def extract_info(url: str) -> dict:
    direct = extract_info_from_x2twitter(url)
    if direct:
        return direct

    try:
        with yt_dlp.YoutubeDL({**ydl_base_options(), "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except (DownloadError, ExtractorError) as exc:
        raise AppError(clean_error(exc), 422) from exc


def decode_snapcdn_url(value: str) -> dict | None:
    parsed = urlparse(html.unescape(value))
    token = parse_qs(parsed.query).get("token", [""])[0]
    if not token or token.count(".") < 2:
        return None
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload).decode("utf-8")
        data = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None
    if not data.get("url"):
        return None
    return data


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def extract_info_from_x2twitter(url: str) -> dict | None:
    now = time.time()
    with X2_CACHE_LOCK:
        cached = X2_CACHE.get(url)
        if cached and now - cached[0] < X2_CACHE_TTL_SECONDS:
            return copy.deepcopy(cached[1])

    body = urlencode({"q": url, "lang": "en"}).encode("utf-8")
    request = Request(
        "https://x2twitter.com/api/ajaxSearch",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://x2twitter.com/en4",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if payload.get("status") != "ok" or not payload.get("data"):
        return None

    markup = payload["data"]
    formats = []
    for index, match in enumerate(
        re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', markup, re.IGNORECASE | re.DOTALL),
        start=1,
    ):
        label = html.unescape(strip_tags(match.group(2))).strip()
        if "Download MP4" not in label:
            continue
        token_data = decode_snapcdn_url(match.group(1))
        if not token_data:
            continue
        direct_url = token_data["url"]
        height_match = re.search(r"\((\d+)p\)", label)
        height = int(height_match.group(1)) if height_match else None
        parsed_path = Path(urlparse(direct_url).path)
        width = None
        size_match = re.search(r"/(\d+)x(\d+)/", direct_url)
        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))
        formats.append(
            {
                "format_id": f"x2-{index}",
                "ext": parsed_path.suffix.lstrip(".") or "mp4",
                "width": width,
                "height": height,
                "vcodec": "avc1",
                "acodec": "unknown",
                "url": direct_url,
                "source": "x2twitter",
                "filename": token_data.get("filename"),
            }
        )

    if not formats:
        return None

    thumbnail_match = re.search(r'<img[^>]+src="([^"]+)"', markup, re.IGNORECASE)
    title_match = re.search(r"<h3>(.*?)</h3>", markup, re.IGNORECASE | re.DOTALL)
    duration_match = re.search(r"<p>\s*(\d+(?::\d+){1,2})\s*</p>", markup, re.IGNORECASE)
    title = html.unescape(strip_tags(title_match.group(1))).strip() if title_match else "Video de X"
    duration = parse_duration(duration_match.group(1)) if duration_match else None
    metadata = twitter_oembed_metadata(url)

    result = {
        "id": tweet_id_from_url(url) or uuid.uuid4().hex,
        "title": metadata.get("description") or title,
        "description": metadata.get("description") or title,
        "uploader": metadata.get("uploader"),
        "uploader_id": metadata.get("uploader_id") or username_from_url(url),
        "upload_date": metadata.get("upload_date") or upload_date({}, url),
        "thumbnail": html.unescape(thumbnail_match.group(1)) if thumbnail_match else None,
        "duration": duration,
        "formats": formats,
        "extractor_key": "X2TwitterFallback",
    }
    with X2_CACHE_LOCK:
        X2_CACHE[url] = (now, copy.deepcopy(result))
    return result


def twitter_oembed_metadata(url: str) -> dict:
    request_url = "https://publish.twitter.com/oembed?" + urlencode({"url": url})
    request = Request(request_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}

    metadata: dict[str, str] = {}
    html_text = payload.get("html") or ""
    paragraph = re.search(r"<p[^>]*>(.*?)</p>", html_text, re.IGNORECASE | re.DOTALL)
    if paragraph:
        description = html.unescape(strip_tags(paragraph.group(1))).strip()
        metadata["description"] = re.sub(r"\s+", " ", description)
    author_url = payload.get("author_url") or ""
    user_match = re.search(r"(?:twitter|x)\.com/([^/?#]+)", author_url)
    if user_match:
        metadata["uploader_id"] = user_match.group(1)
    if payload.get("author_name"):
        metadata["uploader"] = payload["author_name"]
    date_match = re.search(r">([A-Z][a-z]+ \d{1,2}, \d{4})<", html_text)
    if date_match:
        metadata["upload_date"] = datetime.strptime(date_match.group(1), "%B %d, %Y").strftime("%d%m%y")
    return metadata


def download_to_file(url: str, fmt: str, start: float | None, end: float | None, title: str) -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="x-video-download-", dir=CACHE_DIR))
    output = workdir / f"{clean_filename(title)}.%(ext)s"
    options = {
        **ydl_base_options(),
        "format": fmt,
        "outtmpl": str(output),
        "paths": {"home": str(workdir), "temp": str(workdir)},
    }
    if start is not None or end is not None:
        ranges = [(start or 0, end)]
        options["download_ranges"] = download_range_func([], ranges)
        options["force_keyframes_at_cuts"] = True

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    return newest_mp4(workdir)


def direct_format(job: dict, fmt: str) -> dict | None:
    for item in job.get("formats") or []:
        if item.get("id") == fmt and item.get("source") == "x2twitter" and item.get("url"):
            return item
    return None


def direct_best_format(job: dict) -> dict | None:
    direct = [item for item in job.get("formats") or [] if item.get("source") == "x2twitter" and item.get("url")]
    if not direct:
        return None
    return sorted(direct, key=lambda item: item.get("height") or 0, reverse=True)[0]


def ffmpeg_trim_direct(source_url: str, start: float | None, end: float | None, title: str) -> Path:
    if not FFMPEG_DIR:
        raise AppError("Para recortar una parte del video se necesita ffmpeg disponible.", 400)
    workdir = Path(tempfile.mkdtemp(prefix="x-video-trim-", dir=CACHE_DIR))
    output = workdir / f"{clean_filename(title)}.mp4"
    ffmpeg = str(Path(FFMPEG_DIR) / "ffmpeg.exe") if os.name == "nt" else str(Path(FFMPEG_DIR) / "ffmpeg")
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if start is not None:
        command += ["-ss", str(start)]
    command += ["-i", source_url]
    if end is not None:
        if start is not None:
            command += ["-t", str(end - start)]
        else:
            command += ["-to", str(end)]
    command += ["-c", "copy", str(output)]
    subprocess.run(command, check=True, timeout=600)
    return output


def send_direct_download(handler: BaseHTTPRequestHandler, source_url: str, filename: str) -> None:
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "video/mp4")
        content_length = response.headers.get("Content-Length")
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Disposition", f'attachment; filename="{clean_filename(filename)}"')
        if content_length:
            handler.send_header("Content-Length", content_length)
        handler.end_headers()
        shutil.copyfileobj(response, handler.wfile)


def proxy_direct_preview(handler: BaseHTTPRequestHandler, source_url: str) -> None:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://x.com/"}
    range_header = handler.headers.get("Range")
    if range_header:
        headers["Range"] = range_header
    request = Request(source_url, headers=headers)
    with urlopen(request, timeout=60) as response:
        status = HTTPStatus.PARTIAL_CONTENT if response.status == 206 else HTTPStatus.OK
        handler.send_response(status)
        handler.send_header("Content-Type", response.headers.get("Content-Type", "video/mp4"))
        for name in ("Content-Length", "Content-Range", "Accept-Ranges"):
            value = response.headers.get(name)
            if value:
                handler.send_header(name, value)
        if not response.headers.get("Accept-Ranges"):
            handler.send_header("Accept-Ranges", "bytes")
        handler.end_headers()
        shutil.copyfileobj(response, handler.wfile)


def make_job(info: dict, url: str) -> dict:
    token = uuid.uuid4().hex
    formats = video_formats(info)
    if not formats:
        raise AppError(
            "No encontre calidades de video en ese post. Puede ser imagen, texto, audio, o contenido que requiere sesion.",
            422,
        )
    duration = info.get("duration")
    job = {
        "token": token,
        "url": url,
        "title": info.get("title") or info.get("fulltitle") or "Video de X",
        "description": info.get("description") or info.get("title") or info.get("fulltitle") or "Video de X",
        "uploader": info.get("uploader"),
        "uploader_id": info.get("uploader_id") or info.get("channel_id") or username_from_url(url),
        "upload_date": upload_date(info, url),
        "thumbnail": info.get("thumbnail"),
        "duration": duration,
        "durationLabel": format_seconds(duration),
        "formats": formats,
        "created": time.time(),
        "preview_path": None,
        "preview_error": None,
    }
    with JOBS_LOCK:
        JOBS[token] = job
    return job


def public_job(job: dict) -> dict:
    best = sorted(job["formats"], key=lambda item: item.get("height") or 0, reverse=True)[0]
    width = best.get("width") or 16
    height = best.get("height") or 9
    return {
        "token": job["token"],
        "title": job["title"],
        "thumbnail": job.get("thumbnail"),
        "duration": job.get("duration"),
        "durationLabel": job.get("durationLabel"),
        "downloadName": download_basename(job),
        "formats": job["formats"],
        "previewWidth": width,
        "previewHeight": height,
        "canTrim": bool(FFMPEG_DIR),
        "ffmpegFound": bool(FFMPEG_DIR),
        "resolver": "x2twitter" if any(item.get("source") == "x2twitter" for item in job["formats"]) else "yt-dlp",
    }


def start_preview(token: str) -> None:
    def worker() -> None:
        with JOBS_LOCK:
            job = JOBS.get(token)
        if not job:
            return
        try:
            direct = direct_best_format(job)
            if direct:
                with JOBS_LOCK:
                    if token in JOBS:
                        JOBS[token]["preview_direct_url"] = direct["url"]
                return
            path = download_to_file(job["url"], "bestvideo+bestaudio/best", None, None, job["title"])
            with JOBS_LOCK:
                if token in JOBS:
                    JOBS[token]["preview_path"] = str(path)
        except Exception as exc:  # noqa: BLE001
            with JOBS_LOCK:
                if token in JOBS:
                    JOBS[token]["preview_error"] = str(exc)

    threading.Thread(target=worker, daemon=True).start()


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self.serve_file(WEB_DIR / "index.html")
        if path in {"/health", "/healthz"}:
            return json_response(self, {"ok": True})
        if path.startswith("/web/"):
            return self.serve_file(WEB_DIR / path.removeprefix("/web/"))
        if path == "/api/preview-status":
            return self.preview_status(parse_qs(parsed.query).get("token", [""])[0])
        if path == "/preview":
            return self.serve_preview(parse_qs(parsed.query).get("token", [""])[0])
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/info":
            return self.api_info()
        if parsed.path == "/api/preview":
            return self.api_preview()
        if parsed.path == "/download":
            return self.download()
        self.send_error(HTTPStatus.NOT_FOUND)

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def api_info(self) -> None:
        try:
            data = read_json(self)
            url = (data.get("url") or "").strip()
            if not url:
                return json_response(self, {"error": "Pega un enlace de X primero."}, 400)
            info = extract_info(url)
            job = make_job(info, url)
            json_response(self, public_job(job))
        except AppError as exc:
            json_response(self, {"error": str(exc)}, exc.status)
        except Exception as exc:  # noqa: BLE001
            json_response(self, {"error": clean_error(exc)}, 500)

    def api_preview(self) -> None:
        data = read_json(self)
        token = data.get("token")
        with JOBS_LOCK:
            job = JOBS.get(token)
        if not job:
            return json_response(self, {"error": "Video no encontrado. Carga el enlace otra vez."}, 404)
        if not job.get("preview_path") and not job.get("preview_error"):
            start_preview(token)
        json_response(self, {"ok": True})

    def preview_status(self, token: str) -> None:
        with JOBS_LOCK:
            job = JOBS.get(token)
        if not job:
            return json_response(self, {"error": "Video no encontrado."}, 404)
        if job.get("preview_path"):
            return json_response(self, {"status": "ready", "url": f"/preview?token={token}"})
        if job.get("preview_direct_url"):
            return json_response(self, {"status": "ready", "url": f"/preview?token={token}"})
        if job.get("preview_error"):
            return json_response(self, {"status": "error", "error": job["preview_error"]})
        json_response(self, {"status": "pending"})

    def serve_preview(self, token: str) -> None:
        with JOBS_LOCK:
            job = JOBS.get(token)
        if not job:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if job.get("preview_direct_url"):
            return proxy_direct_preview(self, job["preview_direct_url"])
        if not job.get("preview_path"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = Path(job["preview_path"])
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        file_size = path.stat().st_size
        range_header = self.headers.get("Range")
        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if not match:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            start = int(match.group(1) or 0)
            end = int(match.group(2) or file_size - 1)
            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            chunk_size = end - start + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(chunk_size))
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with path.open("rb") as file:
                file.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = file.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with path.open("rb") as file:
            shutil.copyfileobj(file, self.wfile)

    def download(self) -> None:
        try:
            fields = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            token = fields.get("token", [""])[0]
            fmt = fields.get("format", ["bestvideo+bestaudio/best"])[0]
            start = parse_time(fields.get("start", [""])[0])
            end = parse_time(fields.get("end", [""])[0])
            with JOBS_LOCK:
                job = JOBS.get(token)
            if not job:
                return json_response(self, {"error": "Video no encontrado. Carga el enlace otra vez."}, 404)
            if (start is not None or end is not None) and not FFMPEG_DIR:
                return json_response(
                    self,
                    {"error": "Para recortar una parte del video se necesita ffmpeg disponible."},
                    400,
                )
            if start is not None and end is not None and end <= start:
                return json_response(self, {"error": "El tiempo final debe ser mayor que el inicial."}, 400)

            direct = direct_format(job, fmt)
            if not direct and fmt == "bestvideo+bestaudio/best":
                direct = direct_best_format(job)
            if direct:
                if start is None and end is None:
                    filename = download_basename(job)
                    return send_direct_download(self, direct["url"], filename)
                downloaded = ffmpeg_trim_direct(direct["url"], start, end, job["title"])
                filename = download_basename(job)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(downloaded.stat().st_size))
                self.end_headers()
                with downloaded.open("rb") as file:
                    shutil.copyfileobj(file, self.wfile)
                return

            downloaded = download_to_file(job["url"], fmt, start, end, job["title"])
            filename = download_basename(job)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(downloaded.stat().st_size))
            self.end_headers()
            with downloaded.open("rb") as file:
                shutil.copyfileobj(file, self.wfile)
        except AppError as exc:
            json_response(self, {"error": str(exc)}, exc.status)
        except (DownloadError, ExtractorError) as exc:
            json_response(self, {"error": clean_error(exc)}, 422)
        except Exception as exc:  # noqa: BLE001
            json_response(self, {"error": clean_error(exc)}, 500)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"X Video Downloader listo en {url}")
    if HOST in {"127.0.0.1", "localhost"}:
        print("Cierra esta ventana para detener la app.")
        webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
