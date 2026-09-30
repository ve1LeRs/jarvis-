@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === J.A.R.V.I.S. installer ===
where python >nul 2>&1
if errorlevel 1 (
  echo Python не найден. Установите Python 3.10+ с python.org и отметьте "Add to PATH".
  pause
  exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Готово. Запуск: start_jarvis.bat
echo Текстовый режим для проверки: start_jarvis_text.bat
pause
