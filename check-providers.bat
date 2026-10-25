@echo off
REM Tests every AI key you have set and tells you exactly what is wrong. Add the word reset to also clear stuck cooldowns:  check-providers.bat reset
cd /d "%~dp0backend"
call .venv\Scripts\activate
if /i "%1"=="reset" ( python check_providers.py --reset ) else ( python check_providers.py )
pause
