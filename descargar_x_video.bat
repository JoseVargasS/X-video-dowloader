@echo off
setlocal

if "%~1"=="" (
  python "%~dp0x_video_downloader.py"
) else (
  python "%~dp0x_video_downloader.py" %*
)
