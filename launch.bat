@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Install uv from https://docs.astral.sh/uv/getting-started/installation/ and reopen your terminal.
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo Install FFmpeg and add its bin folder to PATH.
  pause
  exit /b 1
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo FFprobe must also be available on PATH with FFmpeg.
  pause
  exit /b 1
)
uv sync --locked
if errorlevel 1 (
  pause
  exit /b 1
)
echo Open http://127.0.0.1:7888 after the server starts.
uv run --locked --no-sync app.py
pause
