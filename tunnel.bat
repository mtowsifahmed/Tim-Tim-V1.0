@echo off
REM Makes your backend reachable from your phone over the internet for free (Cloudflare quick tunnel, no account).
REM Install once:  winget install Cloudflare.cloudflared    Then run run-backend.bat in another window, then this one.
REM Copy the https://....trycloudflare.com address it prints; on the phone use it as the server (wss://....trycloudflare.com/ws).
cloudflared tunnel --url http://127.0.0.1:8000
pause
