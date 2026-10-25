# Bug fixes after patch 5

## 1. "Reminder set kardo" never actually set a reminder
**Cause:** skills were only proposed when the message matched a small list of English action verbs (`open`, `save`, `create`…).
"1 min baar paani peene ka reminder set kardo" matched none, so the model merely *talked* about a reminder and nothing was scheduled.
**Fix:** `skills.guess_reminder()` understands reminder wording (English and Hinglish: `remind`, `reminder`, `yaad dila`, `ghante baad`)
plus a stated time (minutes or hours) and turns it straight into a validated `set_reminder` action — no router call, so it is also faster.
Reminders are local to the app, so they no longer wait behind a confirmation dialog (Settings → Skills can still set them back to Ask/Never).

## 2. The app could sit on "thinking" for minutes
**Cause (client):** if the websocket dropped mid-reply, nothing reset the turn — the orb stayed in THINKING and agents stayed "working".
**Fix:** a dropped/expired connection now ends the turn, resets the agent cards and says the reply was lost; reconnecting also clears stale state.

## 3. A stalled provider could hold a turn open forever
**Fix:** each turn now has a 90-second ceiling (`TURN_TIMEOUT`). Past it the backend aborts the turn and sends a clear "took too long, please try again" error instead of silence.

## 4. An ignored action confirmation blocked the reply for over two minutes
**Cause:** the backend waited 130s for the desktop to answer an action request; if the modal was never noticed the whole turn hung.
**Fix:** that wait is 60s, and reminders no longer require a modal at all.

## 5. Voice retried a rate-limited provider for every sentence and delayed the text reply
**Cause:** the per-turn TTS plan was built once, so a provider marked exhausted (HTTP 429) stayed in the plan and was retried for each
sentence; the reply also waited for all audio before finishing.
**Fix:** an exhausted or rejected provider is removed from the plan for the rest of the turn, a provider whose models are all retired is
skipped without a call, and speech now has a 20-second grace period — it can lag the text, never delay it.

Also: `check_search.py` now writes UTF-8, so headlines no longer print as `â€™`-style garbage on Windows.

All covered by `backend/tests/test_regressions.py`; full suite: **119 passed**.
