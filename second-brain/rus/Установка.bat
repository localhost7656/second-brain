@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Второй мозг — установка
echo Установка «Второго мозга»: всё нужное для работы программы и плагин для Obsidian.
echo Запускать можно сколько угодно раз: повторный запуск чинит установку и ставит плагин заново.
echo Настройки, ключи и заметки он не трогает.
echo.
set "HERE=%~dp0"
if /i not "%HERE:\AppData\Local\Temp\=%"=="%HERE%" goto fromzip

rem ---------- 1. Python ----------
set PY=
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set PY=py -3
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set PY=python
if not defined PY goto nopython
echo [1 из 4] Python найден.

rem ---------- 2. окружение .venv (сломанное — например, после переустановки Python — создаётся заново) ----------
if not exist .venv\Scripts\python.exe goto mkvenv
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto venvok
echo Окружение .venv повреждено — создаю его заново ...
rmdir /s /q .venv
:mkvenv
echo [2 из 4] Создаю окружение .venv ...
%PY% -m venv .venv
if errorlevel 1 goto venvfail
:venvok
echo [2 из 4] Окружение .venv готово.

rem ---------- 3. библиотеки ----------
echo [3 из 4] Ставлю библиотеки, нужен интернет ...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q --upgrade pip
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pipfail
if not exist api_key.txt type nul > api_key.txt
if not exist settings.yaml if exist settings.template.yaml copy /y settings.template.yaml settings.yaml >nul

rem ---------- 4. плагин в хранилище Obsidian, модель для поиска, запуск Obsidian ----------
echo.
echo [4 из 4] Плагин для Obsidian
.venv\Scripts\python.exe -m brain setup
if errorlevel 1 goto setupfail
echo.
pause
exit /b 0

:fromzip
echo Похоже, файл запущен прямо из архива (из временной папки Windows).
echo Сначала распакуйте архив в постоянную папку, например D:\Программы\Второй мозг,
echo и запустите «Установка.bat» уже оттуда.
pause
exit /b 1
:nopython
echo Не найден Python 3.10 или новее.
echo Скачайте его с сайта python.org (кнопка Download), при установке отметьте галочку
echo «Add python.exe to PATH», затем запустите этот файл снова.
pause
exit /b 1
:venvfail
echo Не удалось создать окружение .venv. Попробуйте переустановить Python и запустить этот файл снова.
pause
exit /b 1
:pipfail
echo Не удалось поставить библиотеки. Проверьте интернет и запустите этот файл снова.
pause
exit /b 1
:setupfail
echo.
echo Плагин не установлен — причина написана выше. Исправьте её и запустите «Установка.bat» снова.
pause
exit /b 1
