@echo off
chcp 65001 >nul
title Сборка JARVIS.exe
cd /d "%~dp0"

echo Сборка настоящего JARVIS.exe (как у обычных программ)...
echo Нужен Windows + установленные зависимости.
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo Сначала запустите "Установить JARVIS.bat"
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
pip install -q pyinstaller

pyinstaller --noconfirm --clean ^
  --name JARVIS ^
  --windowed ^
  --onefile ^
  --hidden-import=jarvis ^
  --hidden-import=jarvis.commands ^
  --hidden-import=jarvis.listen ^
  --hidden-import=jarvis.speak ^
  --hidden-import=jarvis.autostart ^
  --hidden-import=jarvis.actions.system ^
  --hidden-import=jarvis.ui.hud ^
  --hidden-import=jarvis.ui.tray ^
  --collect-all=speech_recognition ^
  --collect-all=edge_tts ^
  --collect-all=pystray ^
  jarvis\__main__.py

if errorlevel 1 (
  echo Сборка не удалась.
  pause
  exit /b 1
)

echo.
echo Готово: dist\JARVIS.exe
echo.
echo Скопируйте JARVIS.exe куда угодно и запустите.
echo Для автозапуска: положите exe в папку и выполните:
echo   JARVIS.exe --install-app
echo.
explorer dist
pause
