@echo off
chcp 65001 >nul
title JARVIS — обновить и тест
cd /d "%~dp0"

echo Тяну свежий код...
where git >nul 2>&1
if not errorlevel 1 (
  git pull
) else (
  echo Git не найден — тестирую то, что уже в папке.
)

if not exist ".venv\Scripts\python.exe" (
  echo Нужна первичная установка...
  call "%~dp0Установить JARVIS.bat"
  exit /b %errorlevel%
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo Как тестировать?
echo   1 = текстом (без микрофона, быстрее)
echo   2 = голосом
choice /C 12 /M "Выбор"
if errorlevel 2 goto voice
if errorlevel 1 goto text

:text
python -m jarvis --text --no-ui --no-speak
goto end

:voice
python -m jarvis --no-ui
goto end

:end
echo.
pause
