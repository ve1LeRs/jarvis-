@echo off
chcp 65001 >nul
title Удаление J.A.R.V.I.S.
cd /d "%~dp0"

echo Удаляю ярлыки и автозапуск JARVIS...
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
python -m jarvis --uninstall-app 2>nul
if errorlevel 1 (
  if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m jarvis --uninstall-app
  ) else (
    python -m jarvis.autostart uninstall
  )
)

echo.
echo Ярлыки и автозапуск убраны.
echo Папку с программой можете удалить вручную, если больше не нужна:
echo   %~dp0
echo.
pause
