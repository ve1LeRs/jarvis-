@echo off
chcp 65001 >nul
title Сборка JARVIS.exe
cd /d "%~dp0"

echo ========================================================
echo   Сборка JARVIS.exe — один файл как у обычных программ
echo ========================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python не найден. Установите с python.org ^(Add to PATH^).
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Создаю окружение...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Собираю exe ^(это займёт несколько минут^)...
pyinstaller --noconfirm jarvis.spec

if errorlevel 1 (
  echo.
  echo Сборка не удалась. Смотрите ошибки выше.
  pause
  exit /b 1
)

if not exist "dist\JARVIS.exe" (
  echo Файл dist\JARVIS.exe не найден.
  pause
  exit /b 1
)

echo.
echo ========================================================
echo   ГОТОВО: dist\JARVIS.exe
echo.
echo   1. Скопируйте JARVIS.exe куда удобно
echo   2. Запустите один раз:  JARVIS.exe --install-app
echo      ^(ярлык + меню Пуск + автозапуск^)
echo   3. Дальше просто открывайте JARVIS с ярлыка
echo ========================================================
echo.
explorer dist
pause
