@echo off
chcp 65001 >nul
title JARVIS — обновление кода
cd /d "%~dp0"

echo ========================================================
echo   Обновляю JARVIS из git (без скачивания exe)
echo ========================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [ОШИБКА] Git не найден. Установите: https://git-scm.com/download/win
  pause
  exit /b 1
)

echo Текущая ветка:
git branch --show-current
echo.

git pull
if errorlevel 1 (
  echo.
  echo Не удалось обновить. Проверьте интернет / доступ к репо.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Виртуальное окружение ещё не создано — запускаю установку...
  call "%~dp0Установить JARVIS.bat"
  exit /b %errorlevel%
)

echo.
echo Обновляю библиотеки...
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

echo.
echo Готово. Можно тестировать:
echo   Тест голосом.bat   — микрофон + логи в окне
echo   Тест текстом.bat   — команды с клавиатуры (быстрее всего)
echo.
pause
