@echo off
chcp 65001 >nul
title JARVIS — тест голосом
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Сначала один раз: Установить JARVIS.bat
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
echo ========================================================
echo   ТЕСТ: голос, логи в этом окне
echo   Скажите: Джарвис, открой проводник
echo   Выход: Ctrl+C или «Джарвис, пока»
echo ========================================================
echo.
python -m jarvis --no-ui
echo.
pause
