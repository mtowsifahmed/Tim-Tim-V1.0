@echo off
setlocal
REM Builds the Tim-Tim Windows installer. Needs Node.js (LTS) and Rust. The first build takes several minutes.
cd /d "%~dp0desktop"
where node >nul 2>nul || ( echo Node.js was not found. Install the LTS version from https://nodejs.org , then run this file again. & pause & exit /b 1 )
where cargo >nul 2>nul || ( echo Rust was not found. Install it from https://rustup.rs , then CLOSE this window, open a new one and run this file again. & pause & exit /b 1 )
if not exist node_modules ( call npm install || ( echo npm install failed. Check your internet connection. & pause & exit /b 1 ) )
call npm run build || ( echo. & echo BUILD FAILED. Copy the last 30 lines above and send them to your developer. & pause & exit /b 1 )
if not exist "..\release" mkdir "..\release"
copy /y "src-tauri\target\release\bundle\nsis\*.exe" "..\release\" >nul
echo.
echo DONE. Your installer is in the "release" folder next to this file.
pause
