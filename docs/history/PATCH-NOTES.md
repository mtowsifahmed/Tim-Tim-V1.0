# PC completion patch (October 2026)

This patch only ADDS files and replaces five files that your handoff notes say you never changed. It does **not** touch your
providers, rotation, STT/TTS adapters, `.env`, `config.js`, docs or tests.

## How to apply (2 minutes)
1. Extract this zip INTO your Tim-Tim project folder (the one that contains `backend` and `desktop`). Say yes to overwrite.
2. Open a cmd window in that folder and run:  `python apply_patch.py`
   It makes two tiny edits to `desktop\src\index.html` and `desktop\src\app.js` (backups are saved as `.bak`). If you changed those exact spots it tells you and skips them.
3. Run `backend\.venv\Scripts\python -m pytest -q` inside `backend` (should pass; one new test file was added).

## What's new
- **Typing, key presses and clicks** (Windows): `type_text`, `press_key`, `click`. Always high risk, so each one asks first and has no "Always allow".
  Tim-Tim minimizes itself, acts on the window you were using, then comes back. Click uses screen pixel coordinates you give it (it cannot see your screen).
- **Top bar always shows who you are, how much is left and who is answering**, for example "Free · 24 left · groq".
- **Limit/offline notices are spoken** with your computer's own voice (free) as well as shown.
- **App icons** are included, so the desktop app builds without the icon step.
- **One-click scripts** in the project folder: `setup.bat` (first time), `run-backend.bat`, `check-providers.bat` (add `reset` to clear cooldowns), `open-app.bat`, `run-desktop.bat`, `build-desktop.bat`, `tunnel.bat`.
- `backend\init_env.py` creates `KEY_ENCRYPTION_SECRET` for you if it is empty (`setup.bat` runs it).
- `DEPLOY.md` and `Dockerfile`: free ways to reach your backend from outside your PC (needed for the phone app).

## Files replaced (copy yours aside first if you edited any of these)
`backend\app\skills.py` · `desktop\src\actions.js` · `desktop\src-tauri\src\lib.rs` · `desktop\src-tauri\capabilities\default.json`

## To run Tim-Tim as a real desktop app (not just in the browser)
Install once: Node.js LTS (nodejs.org), Rust (rustup.rs, accept the defaults), and "Build Tools for Visual Studio" with the
"Desktop development with C++" workload. Then run `run-desktop.bat`. The first build takes several minutes. If it shows an error, send me the last 30 lines.
