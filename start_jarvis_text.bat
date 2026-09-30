@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo J.A.R.V.I.S. text mode
python -m jarvis --text --no-ui
pause
