@echo off
chcp 65001 >nul
title JARVIS — установка exe
cd /d "%~dp0"

if not exist "dist\JARVIS.exe" if not exist "JARVIS.exe" (
  echo Сначала соберите программу: build_exe.bat
  echo Или положите JARVIS.exe рядом с этим файлом.
  pause
  exit /b 1
)

set EXE=JARVIS.exe
if exist "dist\JARVIS.exe" set EXE=dist\JARVIS.exe

echo Устанавливаю %EXE% как программу Windows...
"%EXE%" --install-app

echo.
echo Запустить сейчас?
choice /C YN /M "Y = да, N = нет"
if errorlevel 2 goto end
if errorlevel 1 start "" "%EXE%"

:end
pause
