@echo off
chcp 65001 >nul
title JARVIS — быстрый тест
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Сначала один раз: Установить JARVIS.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat

echo ========================================================
echo   DEV: текстовые команды, без TTS и без микрофона
echo   Введите команду без «Джарвис». Выход: выход
echo ========================================================
echo.
python -m jarvis --text --no-ui --no-speak
if errorlevel 1 pause
