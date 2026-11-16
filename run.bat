@echo off
setlocal

cd /d "%~dp0"
set "CAIRNMARK_PYTHON=%CD%\venv\Scripts\python.exe"
set "CAIRNMARK_DISPLAY_PORT=%PORT%"
if not defined CAIRNMARK_DISPLAY_PORT set "CAIRNMARK_DISPLAY_PORT=5000"

if not exist "%CAIRNMARK_PYTHON%" (
    echo Cairnmark could not find "%CAIRNMARK_PYTHON%".
    echo Create the virtual environment and install requirements first.
    exit /b 1
)

echo Starting Cairnmark at http://127.0.0.1:%CAIRNMARK_DISPLAY_PORT%
echo Press Ctrl+C or close this terminal to stop the server.
echo.

"%CAIRNMARK_PYTHON%" app.py
exit /b %ERRORLEVEL%
