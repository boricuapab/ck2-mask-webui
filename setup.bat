@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Install uv from https://docs.astral.sh/uv/getting-started/installation/ and reopen your terminal.
  pause
  exit /b 1
)
where git >nul 2>nul
if errorlevel 1 (
  echo Install Git and add it to PATH, then run setup.bat again.
  pause
  exit /b 1
)
uv sync --locked
if errorlevel 1 (
  pause
  exit /b 1
)
echo Environment synchronized. Run launch.bat to start CorridorKey Mask WebUI.
echo Models will download automatically when you submit your first inference job.
pause
