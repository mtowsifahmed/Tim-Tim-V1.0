# PC patch 3: live web search and research

Fixes "I only have data up to 2024". Tim-Tim now looks things up on the live web before answering news, weather, prices,
scores, "latest" questions and anything you ask it to search, and shows the sources under the answer.

## Apply (3 minutes)
1. Extract this zip into your project folder (say yes to overwrite). It replaces ONLY `backend\app\agents.py`
   (it already includes the date/time feature from patch 2) and adds new files.
2. In that folder run:  `python apply_patch_3.py`   (small safe edits to 5 files, `.bak` backups, skips anything you changed)
3. In `backend` with the venv active:  `pip install -r requirements.txt`   (adds the keyless DuckDuckGo search library)
4. Restart the backend, then try:  `python check_search.py "today's latest news"`  to see which source answers on YOUR network.

## How it finds things (first source that works is used)
| Question type | Order |
|---|---|
| News ("latest news", "news about X") | Tavily (if you add a key) → Google News → GDELT → DuckDuckGo news |
| Anything else that needs fresh info | Tavily → Brave (if you add a key) → DuckDuckGo |
| "Who/what is …" | also adds a Wikipedia summary |
Works with NO keys. For the most reliable results add a free Tavily key (1,000 searches a month, no card): https://tavily.com
then put it in `backend\.env` as `TAVILY_API_KEY=...`. Brave is optional and may ask for a card.
When it searches, the agent card shows "Searching the web…", and clickable source chips appear under the reply.
If no source answers, Tim-Tim says plainly that it couldn't check live sources instead of guessing.

## Settings
Settings → Live web: **Auto** (default: only when the question needs fresh info), **Always**, **Off**. It is saved to your account.
News follows your browser language/region (for example en-IN gives Indian headlines).

## Safety
Web pages are treated as untrusted: they are fenced in the prompt, and instructions found inside them are never followed.
The server only downloads public web pages (never your PC, router or cloud addresses), re-checks every redirect, and limits size.

## Files
New: `backend\app\websearch.py` · `backend\check_search.py` · `backend\tests\test_websearch.py` · `desktop\src\sources.js` · `desktop\src\websettings.js` · `apply_patch_3.py`
Replaced: `backend\app\agents.py`
Edited by the script: `desktop\src\app.js` · `desktop\src\index.html` · `backend\app\turn.py` · `backend\requirements.txt` · `backend\.env.example`
