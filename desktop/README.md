# Tim-Tim desktop (Tauri 2)

Requires Windows 10+ (WebView2), Node.js, Rust (rustup) and the MSVC "Desktop development with C++" build tools.

## Preview the UI without installing anything
Double-click `src/index.html` (opens in any browser). Without a `src/config.js` it runs as an offline demo.
Microphone, voice and computer actions need the backend and (for actions) the desktop app.

## First-time config
Copy `src/config.example.js` to `src/config.js` and fill in your Supabase URL and anon key (see ../START-HERE.md).
`config.js` is never overwritten by updates.

## Run as a desktop app
```
cd desktop
npm install
npm run icons        # one-time: generates src-tauri/icons from app-icon.png
npm run dev
```
The first Rust build downloads and compiles crates and takes several minutes.

## What the desktop app adds over the browser preview
- Computer actions (open/close apps, open links, run commands, read/write files) with per-skill permission and a confirmation.
- A floating always-on-top orb (Settings → Floating orb).
