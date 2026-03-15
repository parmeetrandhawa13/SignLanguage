@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="

if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0venv\Scripts\python.exe"

if not defined PYTHON_CMD (
  py -3.11 -c "import sys; print(sys.version)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)

if not defined PYTHON_CMD (
  python -c "import sys; print(sys.version)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD if exist "C:\msys64\ucrt64\bin\python.exe" set "PYTHON_CMD=C:\msys64\ucrt64\bin\python.exe"

if not defined PYTHON_CMD (
  echo No usable Python interpreter was found.
  exit /b 1
)

set "SIGN_APP_OPEN_BROWSER=0"

echo Starting Sign Language app on http://127.0.0.1:5000 using %PYTHON_CMD%
call %PYTHON_CMD% app.py
