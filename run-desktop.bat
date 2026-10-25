@echo off
REM Runs Tim-Tim as a real desktop app (needs Node.js and Rust; the first build takes several minutes).
cd /d "%~dp0desktop"
if not exist node_modules ( call npm install )
call npm run dev
pause
