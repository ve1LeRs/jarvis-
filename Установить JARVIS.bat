@echo off
chcp 65001 >nul
title Установка J.A.R.V.I.S.
cd /d "%~dp0"

echo ========================================================
echo   J.A.R.V.I.S. — установка как программы на Windows
echo ========================================================
echo.
echo  Сейчас будет сделано всё за один раз:
echo   1. Установка зависимостей
echo   2. Ярлык на рабочем столе
echo   3. Пункт в меню Пуск
echo   4. Автозапуск при включении компьютера
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

echo [1/3] Создаю окружение и ставлю библиотеки...
python -m venv .venv
if errorlevel 1 (
  echo Не удалось создать .venv
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
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
echo   - Ярлык на рабочем столе: JARVIS
echo   - Меню Пуск → J.A.R.V.I.S.
echo   - После перезагрузки стартует сам
echo.
echo   Скажите: «Джарвис, открой проводник»
echo.
echo   Удаление: uninstall.bat
echo ========================================================
echo.
echo Запустить JARVIS сейчас?
choice /C YN /M "Y = да, N = нет"
if errorlevel 2 goto end
if errorlevel 1 start "" wscript.exe "%~dp0start_jarvis_silent.vbs"

:end
pause
