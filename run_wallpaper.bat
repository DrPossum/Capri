@echo off
cd /d "%~dp0"
if not exist "main.py" (
  echo main.py was not found in:
  echo %cd%
  echo.
  dir /b
  echo.
  pause
  exit /b 1
)
rem close any wallpaper that is already running, so two copies never play at once
call "%~dp0stop_wallpaper.bat"
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw main.py --wallpaper
) else (
  start "" pythonw main.py --wallpaper
)
