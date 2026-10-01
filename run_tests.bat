@echo off
chcp 65001 >nul
title JARVIS — unit tests
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Сначала: Установить JARVIS.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo Running tests...
python -m unittest discover -s tests -v
echo.
pause
