# Reaching Tim-Tim from outside your PC (needed for the phone app)

The backend normally runs on your PC at `127.0.0.1:8000`, which only your PC can see. Pick ONE way to expose it. All are free.

## Option 1: Cloudflare quick tunnel (easiest, no account)
1. One time: `winget install Cloudflare.cloudflared` (or download it from Cloudflare's site).
2. Start the backend (`run-backend.bat`), then run `tunnel.bat` in a second window.
3. It prints an address like `https://random-words.trycloudflare.com`. Your server is `wss://random-words.trycloudflare.com/ws`.
4. The address **changes every time** you restart the tunnel, and your PC must be on. Fine for personal use.

## Option 2: free web host (always on, but sleepy)
The included `Dockerfile` runs on free container hosts (Render, Koyeb, Fly.io, Hugging Face Spaces). Steps on Render as an example:
1. Put the project in a private GitHub repo (do NOT commit `backend/.env` or `desktop/src/config.js`).
2. Render → New → Web Service → pick the repo → Runtime: Docker → Instance type: Free. Health check path: `/health`.
3. Add every value from your `backend/.env` under Environment (SUPABASE_*, KEY_ENCRYPTION_SECRET, your AI keys).
4. Your server is `wss://your-service.onrender.com/ws`.
Free instances go to sleep after a while without traffic and take about a minute to wake up. Check each host's current free-plan rules before relying on it.

## Using the address
- Desktop: put it in Settings → Developer → Backend URL (or `BACKEND_WS_URL` in `desktop/src/config.js`).
- Phone: the pairing QR code already contains the address the desktop is using, so the phone follows automatically.
- Keep `SUPABASE_URL` and the anon key identical on desktop and phone: both sign in to the same account.
