@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

echo Включаю автозапуск J.A.R.V.I.S. при входе в Windows...
python -m jarvis --install-autostart
echo.
echo Готово. После перезагрузки JARVIS стартует сам (иконка в трее).
echo Чтобы отключить: disable_autostart.bat
pause
