# PC patch 5: the search key belongs to one account

## What changed
- `TAVILY_API_KEY` in `backend\.env` is now the **owner's** key. Only accounts whose role is `owner` use it; it is never
  sent to any client and never used for another account's searches.
- Every other account gets its own free Tavily key field in **Settings → Web search key**. The key is checked once with
  Tavily, then encrypted in `public.api_keys` (`capability='search'`), the same way the other BYOK keys are stored. Only a
  mask (`••••••••abcd`) ever comes back from the server.
- With no key, nothing breaks: search falls back to the keyless sources (Google News, GDELT, DuckDuckGo), and every
  account only ever uses a key it saved itself.

## Apply
1. Run `supabase\migrations\0003_search_keys.sql` once (it only widens the `api_keys` capability check to allow `'search'`).
2. Put the owner's key in `backend\.env` as `TAVILY_API_KEY=...`.
3. Restart the backend and rebuild the app (`build-desktop.bat`, or `npx tauri build --debug --no-bundle` for a quick exe).

## Files
New: `backend\app\routes\search.py` · `backend\tests\test_search_key.py` · `supabase\migrations\0003_search_keys.sql`
Edited: `backend\app\websearch.py` (per-account key) · `backend\app\agents.py` · `backend\app\turn.py` · `backend\app\main.py`
· `backend\.env.example` · `desktop\src\websettings.js` · `desktop\src\styles.css`
