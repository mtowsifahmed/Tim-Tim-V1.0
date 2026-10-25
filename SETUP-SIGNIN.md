# Sign-in setup (Supabase) — do this once

Tim-Tim signs users in with an **email + 6-digit code** (desktop apps can't reliably catch magic-link redirects).

1. **Supabase → Authentication → Providers → Email**: enabled. Keep "Confirm email" on.
2. **Authentication → Email Templates**: edit BOTH "Magic Link" and "Confirm signup" so the body contains the code:

   ```
   <h2>Your Tim-Tim code</h2>
   <p>Enter this code in the app: <b>{{ .Token }}</b></p>
   ```
   Without `{{ .Token }}` the email only has a link and sign-in in the app will not work.
3. **Email sending limit (important):** Supabase's built-in email service allows only a few emails per hour.
   For more than a couple of testers, add a free SMTP sender under Authentication → SMTP Settings
   (Brevo, Resend, or a Gmail app password all have free tiers; check their current limits).
4. Put your **Project URL** and **anon (public) key** into `desktop/src/config.js`.
   Never put the service role key or database password in any app file.
5. Backend `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL`, `KEY_ENCRYPTION_SECRET`.
6. First sign-in with m.towsifoffical2013@gmail.com creates the owner account (unlimited, admin rights).
   Sign in as the owner FIRST, before anyone else.
7. Set your contact for the upgrade screen: `OWNER_CONTACT` in `desktop/src/config.js`.

Session note: the app keeps a refresh token in the app's local storage so you stay signed in. Sign out in Settings clears it.
