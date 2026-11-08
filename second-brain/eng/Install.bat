@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Second Brain - Setup
echo Second Brain setup: install the program dependencies and the Obsidian plugin.
echo You can run setup again to repair the installation and reinstall the plugin.
echo Your settings, keys, and notes will not be changed.
echo.
set "HERE=%~dp0"
if /i not "%HERE:\AppData\Local\Temp\=%"=="%HERE%" goto fromzip

rem ---------- 1. Find Python or offer to install it with consent ----------
call :findpy
if defined PY goto pyok
echo Python 3.10 or newer is required but was not found.
echo Setup can install Python 3.12 from python.org for your Windows user only.
echo Administrator rights are not required. Internet access is required: about 25 MB.
echo You can uninstall Python like any other program.
set /a ASKED=0
:askpy
set /a ASKED+=1
if %ASKED% GTR 5 goto nopython
set "ANS="
set /p "ANS=Install Python now? Enter Y for yes or N for no: "
if not defined ANS goto askpy
set "ANS=%ANS:"=%"
for %%A in (y Y yes Yes YES) do if "%ANS%"=="%%A" goto installpy
for %%A in (n N no No NO) do if "%ANS%"=="%%A" goto nopython
echo Please enter Y or N.
goto askpy
:installpy
where winget >nul 2>nul
if errorlevel 1 goto pydirect
echo.
echo Installing Python 3.12 using Windows Package Manager...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :findpy
if defined PY goto pyinstalled
echo Winget installation failed. Downloading the installer from python.org...
:pydirect
set "PYSETUP=%TEMP%\python-3.12.10-amd64.exe"
echo.
echo Downloading the Python installer from python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference = 'SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $env:PYSETUP } catch { exit 1 }"
if errorlevel 1 goto pydlfail
if not exist "%PYSETUP%" goto pydlfail
echo Installing Python. A progress window will appear; no action is required...
"%PYSETUP%" /passive InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
del "%PYSETUP%" >nul 2>nul
call :findpy
if not defined PY goto pyinstfail
:pyinstalled
echo Python installed.
:pyok
echo [1 of 4] Python found.

rem ---------- 2. Create or repair the virtual environment ----------
if not exist .venv\Scripts\python.exe goto mkvenv
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto venvok
echo The .venv environment is damaged. Recreating it...
rmdir /s /q .venv
:mkvenv
echo [2 of 4] Creating the .venv environment...
%PY% -m venv .venv
if errorlevel 1 goto venvfail
:venvok
echo [2 of 4] The .venv environment is ready.

rem ---------- 3. Install dependencies ----------
echo [3 of 4] Installing dependencies. Internet access is required...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q --upgrade pip
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pipfail
if not exist api_key.txt type nul > api_key.txt
if not exist settings.yaml if exist settings.template.yaml copy /y settings.template.yaml settings.yaml >nul

rem ---------- 4. Set up the Obsidian plugin ----------
echo.
echo [4 of 4] Obsidian plugin
.venv\Scripts\python.exe -m brain setup
if errorlevel 1 goto setupfail
echo.
pause
exit /b 0

:fromzip
echo This file appears to have been launched directly from an archive.
echo Extract the archive to a permanent folder, for example D:\Programs\Second Brain,
echo then run Install.bat from that folder.
pause
exit /b 1
:nopython
echo.
echo Python is not installed. Install it yourself from python.org and select
echo "Add python.exe to PATH" during setup. Then run this file again.
pause
exit /b 1
:pydlfail
echo.
echo Could not download the Python installer. Check your internet connection and retry,
echo or install Python from python.org and select "Add python.exe to PATH".
pause
exit /b 1
:pyinstfail
echo.
echo Python could not be installed, or installation was cancelled.
echo Install it from python.org and select "Add python.exe to PATH", then retry.
pause
exit /b 1

rem ---------- Find Python 3.10 or newer ----------
:findpy
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3" && goto :eof
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python" && goto :eof
for %%P in ("%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" "%SystemRoot%\py.exe") do if exist %%P %%P -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set PY=%%P -3 && goto :eof
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do if exist "%%~D\python.exe" "%%~D\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set PY="%%~D\python.exe" && goto :eof
goto :eof
:venvfail
echo Could not create the .venv environment. Reinstall Python and run this file again.
pause
exit /b 1
:pipfail
echo Could not install dependencies. Check your internet connection and try again.
pause
exit /b 1
:setupfail
echo.
echo The plugin was not installed. See the error above, fix it, then run Install.bat again.
pause
exit /b 1
