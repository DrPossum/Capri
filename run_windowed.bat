@echo off
cd /d "%~dp0"
if not exist "main.py" (
  echo main.py was not found in:
  echo %cd%
  echo.
  echo Files in this folder:
  dir /b
  echo.
  pause
  exit /b 1
)
where py >nul 2>nul
if %errorlevel%==0 (
  py main.py
) else (
  python main.py
)
if errorlevel 1 pause
