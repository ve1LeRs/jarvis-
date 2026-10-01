@echo off
chcp 65001 >nul
title Установка J.A.R.V.I.S.
cd /d "%~dp0"

echo ========================================================
echo   J.A.R.V.I.S. — установка как программы на Windows
echo ========================================================
echo.
echo  Один раз ставите зависимости и ярлыки.
echo  Потом обновления: update.bat ^(без перекачки zip^).
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ОШИБКА] Python не найден.
  echo.
  echo Скачайте Python 3.10+ с https://www.python.org/downloads/
  echo При установке ОБЯЗАТЕЛЬНО отметьте "Add python.exe to PATH".
  echo Затем снова запустите этот файл.
  echo.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

echo [1/3] Окружение и библиотеки...
if exist ".venv\Scripts\activate.bat" (
  echo .venv уже есть — не создаю заново.
) else (
  python -m venv .venv
  if errorlevel 1 (
    echo Не удалось создать .venv
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Некоторые пакеты не установились. Пробую PyAudio отдельно...
  pip install pipwin
  pipwin install pyaudio
  pip install -r requirements.txt
)

echo.
echo [2/3] Регистрирую как программу Windows...
python -m jarvis --install-app
if errorlevel 1 (
  echo Не удалось создать ярлыки.
  pause
  exit /b 1
)

echo.
echo [3/3] Готово!
echo.
echo ========================================================
echo   JARVIS установлен.
echo.
echo   Обновления кода ^(если клонировали через git^):
echo     update.bat
echo   Быстрый тест без микрофона:
echo     dev.bat
echo   Голос:
echo     start_jarvis.bat
echo ========================================================
echo.
echo Запустить JARVIS сейчас?
choice /C YN /M "Y = да, N = нет"
if errorlevel 2 goto end
if errorlevel 1 start "" wscript.exe "%~dp0start_jarvis_silent.vbs"

:end
pause
