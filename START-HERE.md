# Tim-Tim: setup, step by step (Windows 10, Python 3.11)

Updating an existing install? Extract this zip over your folder. **Your `backend\.env` and `desktop\src\config.js` are NOT in the zip, so they are never overwritten.**

> **Keep a copy of those two files somewhere else.** If you delete or replace the whole folder instead of extracting over it
> (or extract into a new folder), both files disappear with it: then nothing can sign in and no AI answers, even though
> the code is fine. `backend\.env` holds your Supabase URL/keys, the database URL, `KEY_ENCRYPTION_SECRET` and your AI keys;
> `desktop\src\config.js` holds the Supabase URL + anon key that the app signs in with.
> If the files are gone you can rebuild them from `backend\.env.example` and `desktop\src\config.example.js`; the
> Supabase and provider keys come from the Supabase dashboard and the provider consoles, and a new
> `KEY_ENCRYPTION_SECRET` is generated with the `Fernet` command in step C (old saved BYOK keys must be re-entered after that).
> Lost files may still be in the Windows Recycle Bin.

## A. Supabase (browser)  [skip if already done]
1. https://supabase.com → New project (free). Save the database password (letters and numbers only).
2. SQL Editor → run `supabase\migrations\0001_schema.sql`, then `0002_rls.sql`.
   Already ran them before? Run only this small update instead (new agent scope names are just text, nothing to change).
3. Authentication → Email Templates → edit **Confirm signup** and **Magic Link** so the body contains `{{ .Token }}` (the 6-digit code).
4. Copy: Project URL, anon/publishable key, and Connect → **Session pooler** URI (with your password filled in).

## B. Free AI key (browser)
Get ONE of: Gemini https://aistudio.google.com/apikey · Groq https://console.groq.com/keys.
**A Gemini key alone covers everything**: chat, speech recognition (`gemini-3.5-transcribe`) and the spoken voice
(`gemini-3.8-flash-tts`) are all free tier and all use that one key.
Optional extras: Deepgram https://console.deepgram.com ($200 one-time credit) for its faster, more natural voices and
recognizer, plus ElevenLabs if you want its voices. With no voice key at all you still get the free fallback voice (edge-tts).
Free limits are per model, so when one model runs out Tim-Tim moves to the next one instead of stopping.

## C. Backend (PC)
Use **Python 3.11** (your 3.14 is too new for some libraries). In `Tim-Tim by claude\backend` open cmd:
```
rmdir /s /q .venv
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Edit `.env`: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_DB_URL, KEY_ENCRYPTION_SECRET (the long text printed above), and your AI key(s).
Then check your keys (this prints a clear OK or the exact problem for each provider):
```
python check_providers.py
```
If something was stuck on "limit reached", clear it with `python check_providers.py --reset`.
Start the server and leave the window open:
```
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/health → `{"ok":true}`.

## D. App config
Copy `desktop\src\config.example.js` to `desktop\src\config.js` (skip if you already have one). Fill SUPABASE_URL and SUPABASE_ANON_KEY.
Double-click `desktop\src\index.html` to open the app in your browser.

## E. First sign-in = owner
Sign in with **m.towsifoffical2013@gmail.com** first. Bottom-right of the top bar shows "Connected"; click it to see your plan and which AI is answering.

## What to try
Type a message · hold Space and talk · say "remember that my favorite color is blue" · "open notepad" (needs the desktop app) · open Settings → Pair a phone.

## If something goes wrong
| You see | Do this |
|---|---|
| "No AI key is set up on the server" | Add a key to `.env`, restart the backend. |
| "returned errors" | Run `python check_providers.py` and read the line for your provider. |
| "reached their limits… about N min" | Wait, or add another provider key. `--reset` clears stuck cooldowns. |
| Logged out right after signing in | Update to this version (it keeps you signed in through temporary rate limits). |
| Backend won't start / "No module" | Make sure the window says `(.venv)` and you used Python 3.11, then `pip install -r requirements.txt`. |
