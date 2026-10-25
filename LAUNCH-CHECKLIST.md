# Launch checklist: Tim-Tim 1.0

Tick every box before you announce. About 45 minutes the first time.

## A. Accounts and services
- [ ] **Supabase**: all three files in `supabase/migrations` have been run, in order (`0001_schema.sql`, `0002_rls.sql`, `0003_search_keys.sql`).
- [ ] **Supabase email sign-in**: Authentication → Email Templates (Confirm signup and Magic Link) contain `{{ .Token }}`; custom SMTP is on (Gmail allows roughly 500 emails a day, so at most about 400 sign-ins a day; Brevo's free plan allows 300 a day). Plan for the busiest launch day.
- [ ] **Backend on Render** is live: `https://tim-tim-v1-backend.onrender.com/health` shows `{"ok":true}`. Environment has `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL` (the *pooler* address), `KEY_ENCRYPTION_SECRET`, and at least **three AI provider keys** (for example `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `GEMINI_API_KEY`), a speech key (`GROQ_API_KEY` covers speech recognition; `DEEPGRAM_API_KEY` is a fast voice) and, ideally, `TAVILY_API_KEY` for live search.
- [ ] **UptimeRobot** pings `/health` every 5 minutes.
- [ ] **Website on Render** (static site) is live and the address is saved as `WEB_URL` in `desktop/src/config.js` (see RENDER-DEPLOY.md, part 6).
- [ ] You signed in with **m.towsifoffical2013@gmail.com first**; the top bar says *Owner*.

## B. Limits, so the free services last
Each chat turn uses one AI call (two for "research" requests or actions), one speech-recognition call for voice, and one voice call per spoken sentence. Free providers have daily caps (see README-PROVIDERS.md).
- [ ] Set **`FREE_DAILY_CAP=20`** on Render for launch week (default is 30). You can raise it once you see real usage.
- [ ] Run `check-providers.bat` on your PC and fix any red line before launch.
- [ ] If people see "limits reached" messages, add another provider key, lower `FREE_DAILY_CAP`, and invite heavy users to add their own keys (Pro).

## C. Legal and support
- [ ] Read `desktop/src/privacy.html` and `terms.html`. They are templates: fill in the governing law at the end of the Terms, and have a lawyer review them for your country before you rely on them.
- [ ] You answer email at the contact address shown in the policies (the same one shown on the "Contact to upgrade" screen).
- [ ] Decide how Pro works: users pay you outside the app, you open the admin panel (shield icon) → search their email → Grant Pro.

## D. 15-minute test with two accounts (yours and a friend's or a spare email)
- [ ] New email signs in with the 6-digit code; the legal links on the sign-in screen open.
- [ ] Typing "hello" gets an answer; the top bar shows plan, remaining turns and the provider.
- [ ] Hold the mic (or Space) and say a sentence; Tim-Tim answers out loud; talking again interrupts it.
- [ ] "What's the latest news today?" shows source chips under the answer. "Research the best budget phones" gives a longer answer with sources.
- [ ] "Remember that my favorite color is blue" appears under Notes; ask later "what's my favorite color?".
- [ ] "Remind me in 1 minute to stretch" speaks and notifies on time.
- [ ] Desktop app only: "open notepad" asks for permission first; Deny does nothing.
- [ ] Admin panel: grant Pro to the test account; it can now add its own key under Settings → API keys.
- [ ] Settings → Your data: Copy my data works; delete the test account (it signs out).
- [ ] Phone: open the website, install it (Add to Home Screen), chat and talk; no duplicated messages.
- [ ] Turn off Wi-Fi on the phone: the app shows "Can't reach Tim-Tim" and recovers when you turn it back on.

## E. Launch day
- [ ] Watch the Render logs. Healthy: `first word after … ms`. Worth a look: `web source … paused`, `limit reached`, provider errors.
- [ ] Watch Supabase usage (database size and email count).
- [ ] Announce with the website address, the installer link (GitHub Release) and the Android APK. Tell Windows users to click **More info → Run anyway** because the installer is not code-signed yet.

## Honest limits of version 1 (say these in your announcement if you like)
- It runs on free AI services: busy times can be slower, and daily limits apply.
- The Render free server can take up to a minute to wake after a long quiet spell; UptimeRobot keeps this rare.
- Computer actions (open apps, files, typing, clicking) work on Windows in the desktop app only.
- "Hey Tim" wake phrase listens through the speech service (uses your daily allowance); push-to-talk is the most reliable.
- AI can be wrong; for anything important check the sources shown.
