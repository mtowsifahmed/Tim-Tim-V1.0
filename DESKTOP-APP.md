# Turn Tim-Tim into a Windows desktop app

You get one installer file: `release\Tim-Tim_1.0.0_x64-setup.exe`. Anyone can double-click it to install Tim-Tim like a normal app (no admin rights needed).
The desktop app can do things the website cannot: **open and close apps, read and write files, type, click, lock the screen, floating orb** (always after asking you).

## One-time setup (about 20 minutes, mostly downloading)
1. **Node.js LTS**: https://nodejs.org (accept the defaults).
2. **Rust**: https://rustup.rs → run `rustup-init.exe`, accept the defaults.
3. **Visual Studio Build Tools**: https://visualstudio.microsoft.com/visual-cpp-build-tools/ → tick **"Desktop development with C++"** → Install.
4. **Restart your PC** (so Windows finds the new tools).
Windows 10 and 11 already include WebView2; the installer adds it if a PC is missing it.

## Build the installer
1. Make sure `desktop\src\config.js` is filled in (it already points at your Supabase and your hosted backend).
2. Double-click **`build-desktop.bat`**. The first build takes 5 to 15 minutes. Later builds are quick.
3. When it says DONE, open the **`release`** folder: your installer is there.
If it fails, copy the last 30 lines of the window and send them to your developer (usually a missing tool from the list above).

## Try it before building
Double-click **`run-desktop.bat`**: runs the real desktop app straight from the source.

## Share it with users
1. Create a GitHub Release (your repo → Releases → "Draft a new release" → tag `v1.0.0`).
2. Drag the installer `.exe` into it and publish. Share the link.
3. **Windows SmartScreen** will warn "unknown publisher" for new unsigned apps: users click *More info → Run anyway*. A code-signing certificate (paid) removes this; it is optional for a first launch, but tell users in your announcement.

## Updating later
Change the code, raise `version` in `desktop/src-tauri/tauri.conf.json` (and `Cargo.toml`, `package.json`), build again, publish the new installer. (The website and phone app update by themselves when you push to GitHub.)

## The web version has less power on purpose
Browsers cannot open apps or read your files, so those skills only work in the desktop app. Everything else (chat, voice, memory, live search, reminders, web pages, settings) works everywhere.
