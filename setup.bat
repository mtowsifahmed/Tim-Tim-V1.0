@echo off
REM One-time setup for Windows (needs Python 3.11 installed). Safe to run again.
cd /d "%~dp0backend"
if not exist .venv (
  py -3.11 -m venv .venv
  if errorlevel 1 ( echo. & echo Python 3.11 was not found. Install it from python.org, tick "Add python.exe to PATH", then run this again. & pause & exit /b 1 )
)
call .venv\Scripts\activate
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 ( echo. & echo Installing the libraries failed. Check your internet connection and run this again. & pause & exit /b 1 )
if not exist .env ( copy .env.example .env >nul & echo Created backend\.env )
python init_env.py
if not exist ..\desktop\src\config.js ( copy ..\desktop\src\config.example.js ..\desktop\src\config.js >nul & echo Created desktop\src\config.js )
echo.
echo Setup finished. Now open backend\.env and desktop\src\config.js in Notepad and fill in your keys (see START-HERE.md), then run check-providers.bat.
pause
