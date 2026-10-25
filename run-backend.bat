@echo off
REM Starts the Tim-Tim server. Leave this window open while you use the app.
cd /d "%~dp0backend"
call .venv\Scripts\activate
echo Tim-Tim backend starting on http://127.0.0.1:8000 (press Ctrl+C to stop)
uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
