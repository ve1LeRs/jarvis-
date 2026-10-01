@echo off
chcp 65001 >nul
title JARVIS — обновление без перекачки
cd /d "%~dp0"

echo ========================================================
echo   JARVIS update — подтянуть свежий код ^(без zip^)
echo ========================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [ОШИБКА] Git не найден.
  echo Установите: https://git-scm.com/download/win
  echo Затем один раз: git clone https://github.com/ve1LeRs/jarvis-.git
  pause
  exit /b 1
)

if not exist ".git" (
  echo [ОШИБКА] Это не git-клон.
  echo.
  echo Один раз:
  echo   git clone https://github.com/ve1LeRs/jarvis-.git
  echo   cd jarvis-
  echo   Установить JARVIS.bat
  echo.
  echo Дальше только этот update.bat — архив скачивать не нужно.
  pause
  exit /b 1
)

REM Optional: set JARVIS_UPDATE_BRANCH=cursor/jarvis-features-polish-b8e8
if "%JARVIS_UPDATE_BRANCH%"=="" (
  for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set JARVIS_UPDATE_BRANCH=%%b
)

echo Ветка: %JARVIS_UPDATE_BRANCH%
echo.

echo [1/3] git fetch + pull...
git fetch --prune origin
git pull --ff-only origin %JARVIS_UPDATE_BRANCH%
if errorlevel 1 (
  echo.
  echo Fast-forward не вышел. Пробую checkout + pull...
  git checkout %JARVIS_UPDATE_BRANCH%
  git pull --ff-only origin %JARVIS_UPDATE_BRANCH%
  if errorlevel 1 (
    echo Не удалось обновить. Есть локальные правки?
    pause
    exit /b 1
  )
)

echo.
echo [2/3] Зависимости ^(только если нужно^)...
if not exist ".venv\Scripts\activate.bat" (
  echo Создаю .venv один раз...
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python не найден в PATH.
    pause
    exit /b 1
  )
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo pip сообщил ошибку — можно продолжить, если раньше всё работало.
)

echo.
echo [3/3] Готово.
git log -1 --oneline
echo.
echo Запуск:
echo   start_jarvis_text.bat   — быстрый тест командами
echo   start_jarvis.bat        — голос + HUD
echo   dev.bat                 — текст без TTS ^(ещё быстрее^)
echo.
choice /C YN /M "Запустить текстовый режим сейчас"
if errorlevel 2 goto end
if errorlevel 1 call "%~dp0start_jarvis_text.bat"

:end
pause
