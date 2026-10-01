@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Сначала один раз: Установить JARVIS.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
echo Текстовый режим (с голосом TTS). Для ещё быстрее — dev.bat
python -m jarvis --text --no-ui
if errorlevel 1 pause
