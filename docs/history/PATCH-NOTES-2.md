# PC patch 2: more skills, reminders, date/time awareness

Works on top of patch 1 (or alone). Same rule as before: only files you never changed are replaced; everything else is edited by a script that backs up and skips anything you modified.

## Apply (2 minutes)
1. Extract this zip into your project folder (the one with `backend` and `desktop`), say yes to overwrite.
2. In that folder run:  `python apply_patch_2.py`   (then `pip install -r backend\requirements.txt` inside `backend` with the venv active: it adds `tzdata`.)
3. In `backend` run the tests: `.venv\Scripts\python -m pytest -q`

## New skills (22 in total, all listed under the SKILLS card where you can set Ask / Always / Never)
| Skill | What it does | Risk |
|---|---|---|
| search_web | Opens search results for a question | low |
| open_path | Opens a file or folder | low |
| list_dir | Lists what is inside a folder | medium |
| create_folder | Makes a folder | medium |
| copy_file / move_file | Copy or rename/move a file. Refuse to overwrite. Move can be undone from the Tasks tab | high |
| delete_file | Sends a file or folder to the **Recycle Bin** (restorable) | high |
| clipboard_read / clipboard_write | Read or fill the clipboard | medium |
| media_key | Volume up/down, mute, play/pause, next/previous track | low |
| system_info | OS, CPU load, memory, battery | low |
| lock_screen | Locks the computer | medium |
| set_reminder | "Remind me in 30 minutes to stretch": notification + spoken + shown. Survives restarting the app | low |
High-risk skills always ask and cannot be set to "Always". Each sub-agent only gets the skills it needs (for example Research can search but cannot delete files).

## Date, time and your name
Tim-Tim now knows today's date and time in YOUR time zone and your name (from Settings), so "remind me at 5pm" and "what's tomorrow's date" work.

## Replaced files
`backend\app\skills.py` · `desktop\src\actions.js` · `desktop\src-tauri\src\lib.rs`
## Edited by apply_patch_2.py
`backend\app\turn.py` · `backend\app\agents.py` · `desktop\src\app.js` · `backend\requirements.txt`
