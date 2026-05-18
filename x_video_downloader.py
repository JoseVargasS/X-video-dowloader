from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://x.com/i/status/2056229877867536881"


def require_yt_dlp():
    try:
        import yt_dlp  # type: ignore
    except ModuleNotFoundError:
        print(
            "Falta yt-dlp.\n\n"
            "Instalalo con:\n"
            "  python -m pip install -U -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return yt_dlp


def human_size(value: Any) -> str:
    if not value:
        return "-"
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "-"

    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size:.0f} B"
        size /= 1024
    return "-"


def resolution(fmt: dict[str, Any]) -> str:
    width = fmt.get("width")
    height = fmt.get("height")
    if width and height:
        return f"{width}x{height}"
    if height:
        return f"{height}p"
    return "-"


def is_video_format(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") not in (None, "none")


def sorted_video_formats(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    videos = [fmt for fmt in formats if is_video_format(fmt)]
    return sorted(
        videos,
        key=lambda f: (
            int(f.get("height") or 0),
            float(f.get("fps") or 0),
            float(f.get("tbr") or 0),
        ),
        reverse=True,
    )


def print_formats(formats: list[dict[str, Any]]) -> None:
    rows = []
    for idx, fmt in enumerate(sorted_video_formats(formats), start=1):
        filesize = fmt.get("filesize") or fmt.get("filesize_approx")
        rows.append(
            [
                str(idx),
                str(fmt.get("format_id") or "-"),
                str(fmt.get("ext") or "-"),
                resolution(fmt),
                str(fmt.get("fps") or "-"),
                str(fmt.get("tbr") or "-"),
                human_size(filesize),
                str(fmt.get("vcodec") or "-"),
                str(fmt.get("acodec") or "-"),
                str(fmt.get("format_note") or "-"),
            ]
        )

    headers = [
        "#",
        "format_id",
        "ext",
        "resolucion",
        "fps",
        "kbps",
        "tamano",
        "video",
        "audio",
        "nota",
    ]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]

    def render(row: list[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(row, widths))

    print(render(headers))
    print(render(["-" * width for width in widths]))
    for row in rows:
        print(render(row))


def prompt_quality(formats: list[dict[str, Any]]) -> str:
    videos = sorted_video_formats(formats)
    if not videos:
        return "bestvideo+bestaudio/best"

    print_formats(formats)
    print("\nOpciones:")
    print("  Enter  -> mejor calidad disponible")
    print("  numero -> fila de la tabla")
    print("  720p   -> mejor video hasta esa altura")
    print("  id     -> format_id exacto")
    choice = input("\nElige calidad: ").strip()

    if not choice:
        return "bestvideo+bestaudio/best"

    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(videos):
            return str(videos[index - 1]["format_id"])
        return choice

    lowered = choice.lower()
    if lowered.endswith("p") and lowered[:-1].isdigit():
        height = lowered[:-1]
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"

    return choice


def build_ydl_options(args: argparse.Namespace, *, format_selector: str | None = None) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    opts: dict[str, Any] = {
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "%(uploader|x)s-%(id)s-%(height|video)sp.%(ext)s"),
        "progress_hooks": [progress_hook],
    }

    if format_selector:
        opts["format"] = format_selector

    if args.cookies:
        opts["cookiefile"] = args.cookies

    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser,)

    if args.verbose:
        opts["verbose"] = True
    else:
        opts["quiet"] = False
        opts["no_warnings"] = False

    return opts


def progress_hook(status: dict[str, Any]) -> None:
    if status.get("status") == "downloading":
        percent = status.get("_percent_str", "").strip()
        speed = status.get("_speed_str", "").strip()
        eta = status.get("_eta_str", "").strip()
        if percent:
            print(f"\rDescargando: {percent}  {speed}  ETA {eta}", end="", flush=True)
    elif status.get("status") == "finished":
        print("\nDescarga terminada. Procesando archivo...")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga videos de X/Twitter con seleccion de calidad usando yt-dlp."
    )
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="URL del post/video de X.")
    parser.add_argument(
        "-q",
        "--quality",
        default="ask",
        help=(
            "Calidad: ask, best, un format_id, o una altura como 720p. "
            "Por defecto: ask."
        ),
    )
    parser.add_argument("--list", action="store_true", help="Solo muestra las calidades disponibles.")
    parser.add_argument("-o", "--output-dir", default="downloads", help="Carpeta de salida.")
    parser.add_argument("--cookies", help="Archivo cookies.txt exportado del navegador.")
    parser.add_argument(
        "--cookies-from-browser",
        choices=["brave", "chrome", "chromium", "edge", "firefox", "opera", "vivaldi"],
        help="Lee cookies de un navegador instalado, util si X pide sesion.",
    )
    parser.add_argument("--verbose", action="store_true", help="Muestra salida detallada de yt-dlp.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    yt_dlp = require_yt_dlp()

    if not shutil.which("ffmpeg"):
        print(
            "Aviso: no encontre ffmpeg en PATH. Ya lo tienes instalado, pero si falla el merge, "
            "agrega ffmpeg al PATH o usa winget install Gyan.FFmpeg.",
            file=sys.stderr,
        )

    info_opts = build_ydl_options(args)
    info_opts["skip_download"] = True

    with yt_dlp.YoutubeDL(info_opts) as ydl:
        info = ydl.extract_info(args.url, download=False)

    formats = info.get("formats") or []
    title = info.get("title") or info.get("fulltitle") or args.url
    print(f"\nVideo: {title}\n")

    if args.list:
        print_formats(formats)
        return 0

    quality = args.quality.strip()
    if quality == "ask":
        format_selector = prompt_quality(formats)
    elif quality == "best":
        format_selector = "bestvideo+bestaudio/best"
    elif quality.lower().endswith("p") and quality[:-1].isdigit():
        height = quality[:-1]
        format_selector = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
    else:
        format_selector = quality

    print(f"\nUsando selector: {format_selector}\n")
    download_opts = build_ydl_options(args, format_selector=format_selector)

    with yt_dlp.YoutubeDL(download_opts) as ydl:
        ydl.download([args.url])

    print(f"\nListo. Revisa la carpeta: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
