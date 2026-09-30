@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo Starting J.A.R.V.I.S...
python -m jarvis
if errorlevel 1 pause
