/* Email one-time-code sign-in against Supabase Auth (GoTrue REST). No SDK.
   "Sticky" sessions: a failed token refresh caused by rate limits (429), server trouble (5xx) or no internet NEVER signs the
   user out. We keep the session and retry quietly. Only a refresh token that Supabase explicitly rejects ends the session. */
(function () {
  const cfg = window.TIMTIM_CONFIG || {};
  const configured = !!(cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY);
  const KEY = 'timtim.session';
  let session = null, timer = null, listeners = [], refreshing = null, failures = 0;

  const base = () => cfg.SUPABASE_URL.replace(/\/$/, '') + '/auth/v1';
  const hdr = extra => ({ 'Content-Type': 'application/json', apikey: cfg.SUPABASE_ANON_KEY, ...(extra || {}) });
  async function call(path, body, extraHeaders) {
    let r;
    try { r = await fetch(base() + path, { method: 'POST', headers: hdr(extraHeaders), body: JSON.stringify(body) }); }
    catch (_) { const e = new Error('Cannot reach the sign-in service. Check your internet connection.'); e.transient = true; throw e; }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const e = new Error(r.status === 429 ? 'Too many requests. Wait a minute, then try again.' : (j.msg || j.error_description || j.message || 'Sign-in failed'));
      e.status = r.status; e.transient = r.status === 429 || r.status >= 500; throw e;
    }
    return j;
  }
  const saved = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (_) { return null; } };
  const notify = () => listeners.forEach(f => f(session));

  function schedule(sec) { clearTimeout(timer); timer = setTimeout(() => A.refreshNow(), Math.max(20, sec) * 1000); }
  function setSession(j, email, announce) {
    const wasIn = !!session;
    session = { access_token: j.access_token, email: email || (j.user && j.user.email) || '', expires_in: j.expires_in || 3600 };
    try { localStorage.setItem(KEY, JSON.stringify({ refresh_token: j.refresh_token, email: session.email })); } catch (_) {}
    failures = 0; schedule(session.expires_in - 90);
    if (announce || !wasIn) notify();                                      // token refreshes are silent; only sign-in announces
  }

  const A = window.TimAuth = {
    configured,
    onChange(f) { listeners.push(f); },
    getToken: () => (session ? session.access_token : null),
    getEmail: () => (session ? session.email : ''),
    async sendCode(email) { await call('/otp', { email: email.trim().toLowerCase(), create_user: true }); },
    async verify(email, code) {
      const j = await call('/verify', { type: 'email', email: email.trim().toLowerCase(), token: code.trim() });
      setSession(j, email.trim().toLowerCase(), true); return session;
    },
    /* Refresh the access token. Resolves true on success, false if the session is kept but couldn't refresh right now,
       and signs out only when Supabase explicitly rejects the refresh token. */
    refreshNow() {
      if (refreshing) return refreshing;
      refreshing = (async () => {
        const s = saved();
        if (!s || !s.refresh_token) { await A.signOut(true); return false; }
        try {
          const j = await call('/token?grant_type=refresh_token', { refresh_token: s.refresh_token });
          setSession(j, s.email, false); return true;
        } catch (e) {
          if (e.transient || e.status === undefined) {                    // rate limit / outage / offline: keep the session, retry with backoff
            failures++; schedule(Math.min(300, 15 * 2 ** Math.min(failures, 5)));
            if (!session) { session = null; }
            return false;
          }
          await A.signOut(true); return false;                           // 400/401: the refresh token is really dead
        }
      })().finally(() => { refreshing = null; });
      return refreshing;
    },
    /* On app start: use the saved refresh token. If we are only offline/rate-limited, keep trying instead of showing the login screen. */
    async restore() {
      const s = saved(); if (!s) return null;
      for (let i = 0; i < 40 && !session; i++) {
        const ok = await A.refreshNow(); if (ok || !saved()) break;
        await new Promise(r => setTimeout(r, Math.min(15000, 2000 * (i + 1))));
      }
      return session;
    },
    async signOut(silent) {
      const t = session && session.access_token;
      session = null; clearTimeout(timer); try { localStorage.removeItem(KEY); } catch (_) {}
      if (t && configured && !silent) fetch(base() + '/logout', { method: 'POST', headers: hdr({ Authorization: 'Bearer ' + t }) }).catch(() => {});
      notify();
    },
  };
})();
