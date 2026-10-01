@echo off
chcp 65001 >nul
title JARVIS — тест текстом
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Сначала один раз: Установить JARVIS.bat
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
echo ========================================================
echo   БЫСТРЫЙ ТЕСТ без микрофона и без exe
echo.
echo   Пишите команды как будто сказали после «Джарвис»:
echo     открой стим
echo     открой проводник
echo     который час
echo     помощь
echo     выход
echo ========================================================
echo.
python -m jarvis --text --no-ui --no-speak
echo.
pause
