@echo off
chcp 65001 >nul
title JARVIS — переключить ветку PR
cd /d "%~dp0"

if not exist ".git" (
  echo Нужен git clone репозитория.
  pause
  exit /b 1
)

set BRANCH=%~1
if "%BRANCH%"=="" set BRANCH=cursor/jarvis-features-polish-b8e8

echo Переключаюсь на %BRANCH% ...
git fetch origin
git checkout %BRANCH%
if errorlevel 1 (
  git checkout -b %BRANCH% origin/%BRANCH%
)
git pull --ff-only origin %BRANCH%
set JARVIS_UPDATE_BRANCH=%BRANCH%
echo.
echo Готово. Дальше: update.bat или dev.bat
git log -1 --oneline
pause
