@echo off
setlocal
cd /d "%~dp0"

set "BASE_PYTHON="

py -3.11 -c "import sys; print(sys.version)" >nul 2>nul
if not errorlevel 1 set "BASE_PYTHON=py -3.11"

if not defined BASE_PYTHON (
  python -c "import sys; print(sys.version)" >nul 2>nul
  if not errorlevel 1 set "BASE_PYTHON=python"
)

if not defined BASE_PYTHON (
  echo Python 3.11 is required but was not found.
  echo Install the official 64-bit Python 3.11 for Windows, then run this script again.
  exit /b 1
)

echo Using %BASE_PYTHON%

if exist venv (
  echo Removing broken virtual environment...
  rmdir /s /q venv
)

echo Creating virtual environment...
call %BASE_PYTHON% -m venv venv
if errorlevel 1 exit /b 1

echo Upgrading pip...
call venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo Installing project dependencies...
call venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Environment rebuilt successfully.
echo Start the app with: start_local.cmd
