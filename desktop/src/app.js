(function () {
  const TT = window.TT, V = TT.voice, net = TT.net;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)], CFG = window.TIMTIM_CONFIG || {};
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ago = ms => { const m = Math.max(0, Math.round((Date.now() - ms) / 60000)); return m < 1 ? 'just now' : m < 60 ? m + 'm ago' : m < 1440 ? Math.round(m / 60) + 'h ago' : Math.round(m / 1440) + 'd ago'; };
  const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // ───────── settings (local + synced to your account) ─────────
  const DEFAULTS = { tz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC', theme: 'dark', accent: 'red', figure: 'sphere', colormode: 'accent', c1: '#8b7bff', c2: '#22d3ee', voice: 'expressive_female', tone: 60, humor: 40, formal: 30, uname: '',
    mode: 'ptt', wake: 'hey tim', speak: 'on', float: 'off', micId: '' };
  let S = { ...DEFAULTS, url: CFG.BACKEND_WS_URL || 'ws://127.0.0.1:8000/ws' };
  try { S = { ...S, ...JSON.parse(localStorage.getItem('timtim.settings') || '{}') }; } catch (_) {}
  let syncT = null, applying = false;
  const persist = () => { const { url, ...rest } = S; try { localStorage.setItem('timtim.settings', JSON.stringify(rest)); } catch (_) {}
    if (applying || !TimAuth.getToken()) return; clearTimeout(syncT); syncT = setTimeout(() => net.api('/settings', { method: 'PUT', body: { persona: rest } }).catch(() => {}), 1200); };
  net.url = S.url;
  const isPhone = !window.__TAURI__ && (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.maxTouchPoints > 1 && matchMedia('(max-width: 820px)').matches));
  net.device = isPhone ? 'mobile' : 'desktop'; net.deviceName = isPhone ? 'Phone' : 'Desktop';
  TT.settings = S; TT.persistSettings = persist;

  TT.toast = t => { note(t); const d = document.createElement('div'); d.className = 'm err'; };
  const notes = [];
  function note(text) { notes.unshift({ text, at: Date.now() }); notes.length = Math.min(notes.length, 8); $('#bell-dot').hidden = false; $('#notes-list').innerHTML = notes.map(n => `<li>${esc(n.text)}<br><small class="muted">${ago(n.at)}</small></li>`).join(''); }

  // ───────── theme / orb ─────────
  const root = document.documentElement, css = n => getComputedStyle(root).getPropertyValue(n).trim();
  const orb = new TimOrb($('#orb'), { figure: S.figure, color1: S.c1, color2: S.c2, colorMode: S.colormode });
  const map = new TimMap($('#map'), { color: '#2dd4bf' }), globe = new TimGlobe($('#globe'), { color: '#3b82f6', accent: '#ef4444', speed: 0.08 });
  function look() { root.dataset.theme = S.theme; root.dataset.accent = S.accent; orb.setLight(S.theme === 'light'); orb.setAccent(css('--accent'), css('--accent2')); orb.setColorMode(S.colormode); globe.setColors(css('--accent2'), css('--accent'));
    $('#theme-t').textContent = S.theme.toUpperCase(); }
  look();

  // ───────── agents ─────────
  const AGENTS = [{ id: 'research', name: 'Research', role: 'Finds and summarizes info', icon: '🔎', color: '#3b82f6', task: 'Analyzing data…' }, { id: 'coding', name: 'Coding', role: 'Writes and fixes code', icon: '💻', color: '#10b981', task: 'Building solution…' },
    { id: 'creative', name: 'Creative', role: 'Ideas, stories and design', icon: '🎨', color: '#a855f7', task: 'Generating ideas…' }, { id: 'planner', name: 'Planner', role: 'Plans, tasks and email drafts', icon: '🗓️', color: '#f59e0b', task: 'Scheduling tasks…' }];
  TT.agentName = id => (AGENTS.find(a => a.id === id) || { name: 'Tim-Tim' }).name;
  const studio = TimStudio($('#studio-s'), AGENTS, 's'), hub = TimHub($('#hub-box'), AGENTS);
  $('#load').innerHTML = AGENTS.map(a => `<div class="pb" style="--c:${a.color}"><b>${a.name}</b><span id="pv-${a.id}">0%</span><div class="track"><div class="fill" id="pf-${a.id}" style="width:0"></div></div></div>`).join('');
  $('#agents-list').innerHTML = AGENTS.map(a => `<li id="al-${a.id}" style="--c:${a.color}"><div class="ai">${a.icon}</div><div><b>${a.name}</b><span>${a.role}</span></div><em>idle</em></li>`).join('');
  const load = Object.fromEntries(AGENTS.map(a => [a.id, 0])), working = new Set();
  function agentUI(id, st, label) {
    if (!AGENTS.some(a => a.id === id)) return;
    studio.setStatus(id, st, label); hub.setStatus(id, st); const li = $('#al-' + id); li.className = st === 'idle' ? '' : st; li.querySelector('em').textContent = st === 'working' ? (label || 'working') : st;
    st === 'working' ? working.add(id) : working.delete(id);
  }
  AGENTS.forEach(a => agentUI(a.id, 'idle'));
  setInterval(() => { AGENTS.forEach(a => { load[a.id] = working.has(a.id) ? Math.min(100, load[a.id] + 6) : Math.max(0, load[a.id] - 1.2); $('#pf-' + a.id).style.width = load[a.id] + '%'; $('#pv-' + a.id).textContent = Math.round(load[a.id]) + '%'; }); }, 600);

  // ───────── conversation ─────────
  const log = $('#log'); let bubble = null;
  function msg(cls, text) { const d = document.createElement('div'); d.className = 'm ' + cls;
    if (cls === 'err') { d.innerHTML = `<div class="bub"></div>`; d.querySelector('.bub').textContent = text; note(text); }
    else { const ini = cls === 'u' ? ((TT.me && TT.me.email || 'G')[0] || 'G').toUpperCase() : 'T'; d.innerHTML = `<div class="av">${ini}</div><div style="min-width:0"><div class="bub"></div><small>${clock()}</small></div>`; d.querySelector('.bub').textContent = text; }
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d; }
  function actCard(t) { let el = document.getElementById('act-' + t.id);
    if (!el) { el = document.createElement('div'); el.id = 'act-' + t.id; log.appendChild(el); }
    const fail = ['failed', 'denied'].includes(t.status), txt = { asking: 'Waiting for your approval…', running: 'Working…', done: String(t.output || 'Done').slice(0, 90), denied: 'You declined this action.', failed: String(t.output || 'Failed').slice(0, 90), undone: 'Undone.' }[t.status];
    el.className = 'act' + (fail ? ' fail' : ''); el.innerHTML = `<div class="ai"><svg><use href="#i-${fail ? 'x' : 'skills'}"/></svg></div><div style="min-width:0"><b>run_skill: ${esc(t.skill)}</b><span>${esc(txt)}</span></div>${t.status === 'done' ? '<span class="ck"><svg><use href="#i-check"/></svg></span>' : ''}`; log.scrollTop = log.scrollHeight; }
  $('#clear-chat').onclick = () => { log.innerHTML = ''; $('#as-menu').hidden = true; };

  // ───────── orb state machine ─────────
  let state = 'idle', turnActive = false, gotOutput = false, streaming = false, lvl = 0;
  TT.paused = false;
  function derive() { const s = TT.paused ? 'idle' : V.recording ? 'listening' : (turnActive && !gotOutput) ? 'thinking' : (streaming || V.playing) ? 'speaking' : 'idle'; const label = TT.paused ? 'PAUSED' : s.toUpperCase(); if ($('#think-t').textContent !== label) $('#think-t').textContent = label; if (s !== state) { state = s; orb.setState(s); $('#core').dataset.state = s; floatEmit(); } }
  setInterval(() => { derive(); lvl += ((V.playing ? V.level() : streaming ? 0.45 + Math.random() * 0.3 : 0) - lvl) * 0.4; orb.setLevel(state === 'speaking' ? lvl : 0); }, 60);

  // ───────── waveforms ─────────
  const wl = $('#wave-l').getContext('2d'), wr = $('#wave-r').getContext('2d'), wv = $('#vwave'); let wt = 0;
  function bars(c, w, h, amp, flip) { c.clearRect(0, 0, w, h); c.fillStyle = css('--accent'); const n = 22; for (let i = 0; i < n; i++) { const x = flip ? w - i * (w / n) - 2 : i * (w / n), fall = 1 - i / n, v = Math.abs(Math.sin(wt * 3 + i * 0.7)) * (0.35 + Math.random() * 0.65); const bh = 2 + v * amp * h * 0.9 * fall; c.globalAlpha = 0.3 + fall * 0.7; c.fillRect(x, (h - bh) / 2, 2, bh); } c.globalAlpha = 1; }
  setInterval(() => { wt += 0.06; const amp = state === 'speaking' ? 0.3 + lvl * 0.7 : state === 'listening' ? 0.4 + V.micLevel() * 0.6 : state === 'thinking' ? 0.3 : 0.08; bars(wl, 90, 30, amp, true); bars(wr, 90, 30, amp, false);
    if ($('#as-voice').classList.contains('on')) { const c = wv.getContext('2d'), w = wv.clientWidth; if (wv.width !== w) wv.width = w; c.clearRect(0, 0, w, 90); c.fillStyle = css('--accent'); const a = V.recording ? V.micLevel() : V.playing ? V.level() : 0.04; for (let x = 0, i = 0; x < w; x += 5, i++) { const v = Math.abs(Math.sin(i * 0.3 + wt * 4) * Math.sin(i * 0.09 - wt)); const bh = 3 + v * a * 80; c.fillRect(x, (90 - bh) / 2, 3, bh); } $('#vmeta').textContent = V.micError || (V.recording ? 'Listening…' : V.micOn ? (V.mode === 'wake' ? `Waiting for “${S.wake}”…` : 'Listening for you…') : 'Mic is off'); } }, 50);

  // ───────── connection status ─────────
  let conn = { state: TimAuth.configured ? 'signedout' : 'demo' }, provs = {}, presence = { desktop_online: true, mobile_online: false };
  const ROLE = { owner: 'Owner', moderator: 'Moderator', pro: 'Pro', free: 'Free' };
  function renderConn() {
    const me = TT.me, st = conn.state, ok = st === 'ok';
    $('#conn-t').textContent = { demo: 'Demo mode', signedout: 'Signed out', connecting: 'Connecting…', down: 'Reconnecting…', error: 'Reconnecting…', expired: 'Signed out', ok: 'Connected' }[st] || st;
    if (ok && me) $('#conn-t').textContent = `${ROLE[me.role] || me.role} · ${me.remaining_today == null ? 'no limit' : me.remaining_today + ' left'}${me.providers && me.providers.llm ? ' · ' + me.providers.llm : ''}`;
    $('#conn-dot').className = 'dot ' + (ok ? 'ok' : st === 'down' || st === 'error' || st === 'expired' ? 'bad' : '');
    const lim = me ? (me.remaining_today == null ? 'Unlimited' : `${me.remaining_today} of ${me.daily_cap} left today`) : '—';
    const pv = c => me && me.providers && me.providers[c] ? `${me.providers[c]} (${me.key_source[c] === 'byok' ? 'your key' : 'shared'})` : '—';
    $('#conn-kv').innerHTML = [['Account', me ? esc(me.email) : 'Not signed in'], ['Plan', me ? ROLE[me.role] : '—'], ['Daily use', lim], ['Language model', pv('llm')], ['Speech-to-text', pv('stt')], ['Text-to-speech', pv('tts')], ['Phone', presence.mobile_online ? 'Connected' : 'Not connected'], ['Latency', net.latency != null ? net.latency + ' ms' : '—']].map(([a, b]) => `<li><span>${a}</span><span>${b}</span></li>`).join('');
    $('#m-signout').hidden = !TimAuth.getToken();
    // system status
    const s = $('#sysstat'); let t, cls = '';
    if (st === 'demo') { t = 'Demo mode (offline preview)'; cls = 'warn'; } else if (st === 'signedout' || st === 'expired') { t = 'Please sign in'; cls = 'warn'; } else if (st === 'connecting') { t = 'Connecting to the backend…'; cls = 'warn'; }
    else if (!ok) { t = 'Backend unreachable. Retrying…'; cls = 'bad'; } else if (me && me.providers && !me.providers.llm) { t = 'No language model available right now'; cls = 'bad'; }
    else if (me && me.providers && !me.providers.stt) { t = 'Chat works. Speech recognition has no provider'; cls = 'warn'; } else { t = 'All systems operational'; }
    s.className = 'card sysstat ' + cls; $('#sys-t').textContent = t; $('#sys-dot').className = 'dot ' + (cls === 'bad' ? 'bad' : cls === 'warn' ? '' : 'ok');
    $('#presence').textContent = presence.mobile_online ? 'Phone: connected' : 'Phone: not connected';
    $('#sat-set-s').textContent = me ? `${ROLE[me.role]} plan` : 'Config · Security · Keys'; $('#sat-pers-s').textContent = S.voice === 'calm_male' ? 'Calm male voice' : 'Expressive female voice';
  }
  TT.on('conn', e => { conn.state = e.state === 'connecting' ? 'connecting' : e.state;
    if (['down', 'error', 'expired'].includes(e.state)) {
      // A reply that was in flight will never arrive on this socket: stop pretending to think.
      if (turnActive) { endTurn(); V.turnFinished(); msg('err', 'The connection dropped before that reply arrived. Please try again.'); }
      [...working].forEach(id => agentUI(id, 'idle'));
    }
    if (e.state === 'error' && e.first) msg('err', 'Could not reach the backend. Is it running?'); renderConn(); });
  TT.on('latency', ms => { const w = $('#wifi'); w.className = 'ibtn ' + (ms < 150 ? 'good' : ms < 400 ? 'mid' : 'bad'); w.title = 'Latency ' + ms + ' ms'; renderConn(); });
  function setStatus(s) { TT.me = s; conn.state = 'ok'; $('#admin-btn').hidden = !['owner', 'moderator'].includes(s.role); $('#acct-email').textContent = s.email; $('#acct-plan').textContent = (ROLE[s.role] || s.role) + (s.role === 'free' ? ' plan' : '');
    $('#acct-quota').textContent = s.remaining_today == null ? 'No daily limit' : `${s.remaining_today} of ${s.daily_cap} turns left today (resets midnight UTC)`; $('#acct-upgrade').hidden = s.role !== 'free'; renderConn(); }
  TT.on('status', setStatus); TT.on('provider', p => { if (TT.me) { TT.me.providers[p.capability] = p.name; TT.me.key_source[p.capability] = p.source; renderConn(); } });
  TT.on('presence', p => { presence = p; renderConn(); });
  let keysRole = null;
  TT.on('ready', async m => { conn.state = 'ok'; presence = m; if (turnActive) endTurn();   // reconnected: no stale 'thinking' orb
    setStatus(m.status); loadWorld(); TT.panels.loadNotes(); TT.panels.renderKeys(m.status.role); keysRole = m.status.role;
    try { const { persona } = await net.api('/settings'); if (persona && Object.keys(persona).length) { applying = true; Object.assign(S, persona); applyAll(); applying = false; } else persist(); } catch (_) {}
    try { const { actions } = await net.api('/automation'); TT.actions.hist = actions; } catch (_) {} });

  // ───────── chat events ─────────
  TT.on('turn_start', m => { turnActive = true; gotOutput = false; streaming = false; bubble = null; V.turnStarted(); if (m.origin && m.origin !== net.device) msg('u', m.text + (m.origin === 'mobile' ? '  (from phone)' : '  (from computer)')); });
  TT.on('transcript', m => { msg('u', m.text); });
  TT.on('agent', m => { if (m.status === 'working') agentUI(m.id, 'working', m.task); else if (m.status === 'done') { agentUI(m.id, 'done', 'Done'); setTimeout(() => agentUI(m.id, 'idle'), 2500); } });
  TT.on('token', m => { gotOutput = true; streaming = true; V.noteResponse(); if (!bubble) { bubble = msg('a', ''); bubble.classList.add('typing'); } bubble.querySelector('.bub').textContent += m.text; log.scrollTop = log.scrollHeight; });
  TT.on('audio', V.onAudio);
  const endTurn = () => { turnActive = false; streaming = false; if (bubble) bubble.classList.remove('typing'); bubble = null; };
  TT.on('done', () => { endTurn(); V.turnFinished(); });
  TT.on('interrupted', () => { endTurn(); V.turnFinished(); });
  TT.on('speech_end', () => derive());
  TT.on('error', m => { endTurn(); V.turnFinished(); V.interrupt(); msg('err', m.message); if (TT.speakLocal) TT.speakLocal(m.message); if (m.code === 'daily_cap_reached') { conn.state = 'ok'; $('#sysstat').className = 'card sysstat warn'; $('#sys-t').textContent = 'Daily limit reached. Resets at midnight UTC'; } });
  TT.on('stt_empty', () => { endTurn(); V.turnFinished(); if (V.mode === 'ptt') msg('err', "I didn't catch that. Try again a little closer to the mic."); });
  TT.on('wake_ignored', () => { endTurn(); V.turnFinished(); });
  TT.on('tts_error', m => note(m.message));
  TT.on('task', t => { actCard(t); renderTasks(); });
  TT.on('mic', e => { if (e.error) msg('err', e.error); $('#mic').classList.toggle('on', !!e.on && V.mode !== 'ptt'); });

  function renderTasks() { const rows = (TT.actions.tasks || []).slice(0, 30);
    $('#tasks-list').innerHTML = rows.length ? rows.map(t => `<li data-id="${t.id}"><span class="st-pill st-${t.status}">${t.status}</span><code>${esc(t.skill)}</code><span>${esc(Object.values(t.args)[0] ? String(Object.values(t.args)[0]).slice(0, 40) : '')}</span><small>${new Date(t.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small>${TT.actions.canUndo(t) ? '<button data-undo>Undo</button>' : ''}</li>`).join('') : '<li class="muted">No actions yet. Ask me to open an app or a page.</li>'; }
  $('#tasks-list').addEventListener('click', async e => { if (!e.target.dataset.undo) return; const t = TT.actions.tasks.find(x => x.id === e.target.closest('li').dataset.id); if (t && !(await TT.actions.undo(t))) msg('err', 'Could not undo that.'); });

  // ───────── sending + voice controls ─────────
  const demo = () => conn.state === 'demo';
  function send(text) { text = text.trim(); if (!text || TT.paused) return; msg('u', text); V.unlock();
    if (net.ready()) { turnActive = true; gotOutput = false; V.turnStarted(); net.send({ type: 'text', text, speak: V.speakReplies }); } else if (demo()) demoTurn(text); else msg('err', 'Not connected yet. Please wait a moment.'); }
  $('#composer').addEventListener('submit', e => { e.preventDefault(); const v = $('#msg').value; $('#msg').value = ''; send(v); });
  const mic = $('#mic'); let held = false;
  const down = async e => { if (S.mode !== 'ptt' || TT.paused) return; e && e.preventDefault(); if (demo()) { held = true; fakeListen(true); return; } if (!net.ready()) { msg('err', 'Not connected yet.'); return; } held = true; await V.pttStart(); };
  const up = () => { if (!held) return; held = false; if (demo()) { fakeListen(false); return; } V.pttStop(); };
  mic.addEventListener('pointerdown', down); mic.addEventListener('pointerup', up); mic.addEventListener('pointercancel', up); mic.addEventListener('pointerleave', up);
  mic.addEventListener('click', async () => { if (S.mode === 'ptt' || TT.paused) return; if (V.micOn) { V.stopMic(); } else if (net.ready()) await V.startMic(); else msg('err', 'Not connected yet.'); });
  const typing = () => ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) || document.activeElement.isContentEditable;
  // Space starts push-to-talk from anywhere, EXCEPT while typing or while a panel/modal is open (there Space is a normal key).
  const panelOpen = () => !!document.querySelector('.modal:not([hidden]), .sheet:not([hidden])') || !$('#drawer').hidden;
  addEventListener('keydown', e => { if (e.code === 'Space' && !e.repeat && !e.ctrlKey && !e.altKey && !e.metaKey && !typing() && !panelOpen()) { e.preventDefault(); down(); } if (e.key === 'Escape') { closeAll(); } });
  addEventListener('keyup', e => { if (e.code === 'Space') up(); });
  addEventListener('blur', () => up());                       // releasing the key outside the window must not leave the mic recording
  document.addEventListener('visibilitychange', () => { if (document.hidden) up(); });
  let fakeRec = false; function fakeListen(on) { fakeRec = on; V.recording = on; }

  // pause core
  $('#pause-btn').onclick = () => { TT.paused = !TT.paused; $('#core').classList.toggle('paused', TT.paused); $('#composer').classList.toggle('off', TT.paused);
    $('#pause-btn').innerHTML = TT.paused ? '<svg><use href="#i-play"/></svg><span>RESUME CORE</span>' : '<svg><use href="#i-pause"/></svg><span>PAUSE CORE</span>';
    if (TT.paused) { V.interrupt(); if (V.recording) V.pttStop(); if (V.micOn) V.stopMic(); } derive(); };

  // ───────── demo mode (no Supabase configured) ─────────
  const DEMO = ["Hey! I'm Tim-Tim. This is the offline preview, so replies are canned, but the orb and the team are live.", "Sign in and start the backend to get real answers, real voice, and your memory.", "In the full app you can interrupt me mid-sentence just by talking."];
  function demoTurn(text) { const t = text.toLowerCase(), ag = /code|bug|script/.test(t) ? 'coding' : /idea|story|poem/.test(t) ? 'creative' : /plan|remind|schedule|email/.test(t) ? 'planner' : 'research';
    turnActive = true; gotOutput = false; agentUI(ag, 'working', AGENTS.find(a => a.id === ag).task);
    setTimeout(() => { gotOutput = true; streaming = true; const b = msg('a', ''); b.classList.add('typing'); const r = DEMO[Math.floor(Math.random() * DEMO.length)]; let i = 0;
      const iv = setInterval(() => { b.querySelector('.bub').textContent += r.slice(i, i + 2); i += 2; log.scrollTop = log.scrollHeight; if (i >= r.length) { clearInterval(iv); b.classList.remove('typing'); streaming = false; turnActive = false; agentUI(ag, 'done'); setTimeout(() => agentUI(ag, 'idle'), 2500); } }, 40); }, 1400); }
  $('#demo').onclick = () => { closeAll(); AGENTS.forEach((a, i) => setTimeout(() => { agentUI(a.id, 'working', a.task); setTimeout(() => { agentUI(a.id, 'done'); setTimeout(() => agentUI(a.id, 'idle'), 1500); }, 3500); }, i * 900));
    const seq = ['listening', 'thinking', 'speaking', 'idle']; let i = 0; const step = () => { const s = seq[i++]; fakeRec = s === 'listening'; V.recording = fakeRec; turnActive = s === 'thinking'; gotOutput = false; streaming = s === 'speaking'; if (i < seq.length) setTimeout(step, 2500); }; step(); };

  // ───────── world monitor ─────────
  const SAMPLE_E = [{ title: 'Sample · M6.1 Offshore Japan', mag: 6.1, time: Date.now() - 3.6e6, lat: 36, lon: 142 }, { title: 'Sample · M5.2 Southern Peru', mag: 5.2, time: Date.now() - 9e6, lat: -15, lon: -72 }, { title: 'Sample · M4.8 Aegean Sea', mag: 4.8, time: Date.now() - 2e7, lat: 38, lon: 25 }, { title: 'Sample · M4.6 Alaska', mag: 4.6, time: Date.now() - 4e7, lat: 61, lon: -150 }];
  const SAMPLE_H = [{ title: 'Sample headline: sign in to see live world news', source: 'Tim-Tim', time: Date.now() - 6e5 }, { title: 'Sample headline: earthquakes appear on the map in real time', source: 'Tim-Tim', time: Date.now() - 18e5 }];
  const mcol = m => m >= 6 ? '#ef4444' : m >= 5 ? '#f59e0b' : '#10b981';
  function renderWorld(ev, hd, live) {
    const mk = ev.map(e => ({ lat: e.lat, lon: e.lon, color: mcol(e.mag), size: Math.min(1.8, 0.7 + (e.mag - 4) * 0.4) })); map.setMarkers(mk); globe.setMarkers(mk);
    $('#st-total').textContent = ev.length; $('#st-crit').textContent = ev.filter(e => e.mag >= 6).length; $('#st-imp').textContent = ev.filter(e => e.mag >= 5 && e.mag < 6).length; $('#st-norm').textContent = ev.filter(e => e.mag < 5).length;
    const dot = h => (Date.now() - h.time) < 36e5 ? '#ef4444' : (Date.now() - h.time) < 108e5 ? '#f59e0b' : '#10b981', item = h => `<li style="--c:${dot(h)}"><i></i><div><b>${esc(h.title)}</b><small>${esc(h.source)} · ${ago(h.time)}</small></div></li>`;
    $('#heads').innerHTML = hd.slice(0, 8).map(item).join(''); $('#heads-l').innerHTML = hd.slice(0, 10).map(item).join('');
    $('#events').innerHTML = ev.slice(0, 10).map(e => `<li><i style="background:${mcol(e.mag)}">M${e.mag.toFixed(1)}</i><div>${esc(e.title)}<small>${ago(e.time)}</small></div></li>`).join('') || '<li class="muted">No events right now</li>';
    ['#wm-live', '#wm-live2'].forEach(s => { $(s).classList.toggle('off', !live); $(s).innerHTML = `<i></i>${live ? (s === '#wm-live' ? 'Live Global Feed' : 'Live') : 'Sample data'}`; }); $('#ev-src').textContent = live ? 'Earthquakes M4.5+ · last 24h (USGS)' : 'Sample data · sign in for live events'; }
  async function loadWorld() { if (!TimAuth.getToken()) { renderWorld(SAMPLE_E, SAMPLE_H, false); return; }
    try { const [e, h] = await Promise.all([net.api('/world/events'), net.api('/world/headlines')]); renderWorld(e.events, h.headlines, true); } catch (_) { renderWorld(SAMPLE_E, SAMPLE_H, false); } }
  renderWorld(SAMPLE_E, SAMPLE_H, false); setInterval(loadWorld, 300000);
  const tickUtc = () => { const d = new Date(); $('#utc').textContent = 'UTC ' + String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0'); }; tickUtc(); setInterval(tickUtc, 15000);
  $('#mz-in').onclick = () => map.zoomBy(1.4); $('#mz-out').onclick = () => map.zoomBy(1 / 1.4); $('#mz-nav').onclick = () => map.reset();

  // ───────── menus, tabs, sheets ─────────
  const menus = ['#conn-menu', '#theme-menu', '#notes-menu', '#as-menu'];
  const toggle = id => { const el = $(id), open = el.hidden; menus.forEach(m => $(m).hidden = true); el.hidden = !open; if (id === '#conn-menu' && open) { renderConn(); if (net.ready()) { net.send({ type: 'ping' }); } } if (id === '#notes-menu') $('#bell-dot').hidden = true; };
  $('#conn-btn').onclick = () => toggle('#conn-menu'); $('#theme-btn').onclick = () => toggle('#theme-menu'); $('#bell').onclick = () => toggle('#notes-menu'); $('#as-menu-btn').onclick = () => toggle('#as-menu');
  document.addEventListener('click', e => { if (!e.target.closest('.dd')) menus.forEach(m => $(m).hidden = true); });
  function tabs(sel, prefix) { $(sel).addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; $(sel).querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); const group = prefix === 'pane-' ? '.pane' : '.as-pane'; $$(group).forEach(p => p.classList.toggle('on', p.id === prefix + b.dataset.tab)); if (b.dataset.tab === 'notes') TT.panels.loadNotes(); if (b.dataset.tab === 'tasks') renderTasks(); }); }
  tabs('#studio-tabs', 'pane-'); tabs('#as-tabs', 'as-');
  $('#as-tabs').addEventListener('click', e => { if (e.target.closest('button')?.dataset.tab === 'voice') V.listDevices(); });
  const closeAll = () => { $$('.sheet,.modal').forEach(x => { if (x.id !== 'gate') x.hidden = true; }); closeDrawer(); };
  $$('[data-close]').forEach(b => b.onclick = () => $('#' + b.dataset.close).hidden = true);
  $$('.sheet').forEach(s => s.addEventListener('click', e => { if (e.target === s) s.hidden = true; }));
  $$('[data-go="world"]').forEach(b => b.onclick = () => { $('#sheet-world').hidden = false; });
  $('#admin-btn').onclick = () => TT.panels.openAdmin();
  const openDrawer = () => { $('#drawer').hidden = false; if (TT.me) TT.panels.renderKeys(TT.me.role); }, closeDrawer = () => $('#drawer').hidden = true;
  $('#settings-btn').onclick = openDrawer; $('#close-settings').onclick = closeDrawer; $('#drawer').addEventListener('click', e => { if (e.target.id === 'drawer') closeDrawer(); });
  const toPers = () => { openDrawer(); setTimeout(() => $('#h-pers').scrollIntoView({ behavior: 'smooth' }), 60); };
  $('#sat-set').onclick = openDrawer; $('#sat-pers').onclick = toPers; $('#sat-skill').onclick = () => { TT.panels.renderSkills(); $('#sheet-skills').hidden = false; };
  $('#sat-mem').onclick = () => { $('#as-tabs button[data-tab="notes"]').click(); };
  $('#m-reconnect').onclick = () => { if (TimAuth.getToken()) net.connect(); toggle('#conn-menu'); }; $('#m-signout').onclick = () => { toggle('#conn-menu'); TimAuth.signOut(); };
  $('#spk').onclick = () => { S.speak = S.speak === 'on' ? 'off' : 'on'; applySpeak(); persist(); };
  function applySpeak() { V.speakReplies = S.speak === 'on'; $('#spk').innerHTML = `<svg><use href="#i-spk${V.speakReplies ? '' : '-off'}"/></svg>`; $$('#seg-speak button').forEach(b => b.classList.toggle('on', b.dataset.v === S.speak)); if (!V.speakReplies) V.interrupt(); }

  // ───────── settings widgets ─────────
  function seg(id, key, cb) { const el = $(id), mark = () => el.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === String(S[key])));
    el.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; S[key] = b.dataset.v; mark(); persist(); cb && cb(S[key]); }); el._mark = mark; mark(); }
  seg('#seg-theme', 'theme', () => look()); seg('#seg-accent', 'accent', () => look()); seg('#seg-figure', 'figure', v => orb.setFigure(v)); seg('#seg-colormode', 'colormode', v => { orb.setColorMode(v); $('#row-colors').style.opacity = v === 'custom' ? 1 : .4; });
  seg('#seg-voice', 'voice', () => renderConn()); seg('#seg-speak', 'speak', applySpeak); seg('#seg-float', 'float', v => setFloat(v === 'on'));
  seg('#seg-mode', 'mode', async v => { await V.setMode(v); $('#mic').title = v === 'ptt' ? 'Hold to talk (Space)' : 'Click to turn the microphone on/off'; });
  ['c1', 'c2'].forEach(k => { const el = $('#' + k); el.value = S[k]; el.addEventListener('input', () => { S[k] = el.value; orb.setColors(S.c1, S.c2); persist(); }); });
  [['tone', 'v-tone'], ['humor', 'v-humor'], ['formal', 'v-formal']].forEach(([k, v]) => { const el = $('#' + k), lab = $('#' + v); el.value = S[k]; lab.textContent = S[k]; el.addEventListener('input', () => { S[k] = +el.value; lab.textContent = el.value; persist(); }); });
  $('#uname').value = S.uname; $('#uname').addEventListener('input', e => { S.uname = e.target.value; persist(); });
  $('#wake').value = S.wake; $('#wake').addEventListener('input', e => { S.wake = e.target.value.trim() || 'hey tim'; V.wake = S.wake.toLowerCase(); persist(); });
  const micDev = $('#mic-dev');
  function renderMicDevices(list) {
    const cur = S.micId || '';
    micDev.innerHTML = '<option value="">System default</option>' + list.map(d => `<option value="${esc(d.id)}">${esc(d.label)}</option>`).join('');
    micDev.value = [...micDev.options].some(o => o.value === cur) ? cur : '';
  }
  TT.on('micdevices', renderMicDevices);
  micDev.addEventListener('change', () => { S.micId = micDev.value; V.setDevice(S.micId); persist(); });
  TT.on('toast', t => msg('a', t));
  V.setDevice(S.micId || '');
  $('#url').value = S.url; $('#url').addEventListener('input', e => { S.url = e.target.value.trim(); net.url = S.url; });
  $('#pair-btn').onclick = () => TT.panels.openPair(); $('#acct-upgrade').onclick = () => { closeDrawer(); $('#owner-contact').textContent = CFG.OWNER_CONTACT || '(ask the app owner)'; $('#up-email').textContent = TimAuth.getEmail(); $('#upgrade').hidden = false; };
  $('#close-upgrade').onclick = () => $('#upgrade').hidden = true;
  function applyAll() { look(); orb.setFigure(S.figure); orb.setColors(S.c1, S.c2); ['#seg-theme', '#seg-accent', '#seg-figure', '#seg-colormode', '#seg-voice', '#seg-speak', '#seg-float', '#seg-mode'].forEach(i => $(i)._mark());
    ['c1', 'c2'].forEach(k => $('#' + k).value = S[k]); [['tone', 'v-tone'], ['humor', 'v-humor'], ['formal', 'v-formal']].forEach(([k, v]) => { $('#' + k).value = S[k]; $('#' + v).textContent = S[k]; }); $('#uname').value = S.uname; $('#wake').value = S.wake;
    $('#row-colors').style.opacity = S.colormode === 'custom' ? 1 : .4; V.wake = S.wake.toLowerCase(); V.mode = S.mode; V.deviceId = S.micId || ''; applySpeak(); renderConn(); }
  $('#row-colors').style.opacity = S.colormode === 'custom' ? 1 : .4; V.wake = S.wake.toLowerCase(); V.mode = S.mode; applySpeak();

  // ───────── floating orb (desktop app only) ─────────
  const T = window.__TAURI__;
  if (T && T.event) $('#row-float').hidden = false;
  async function setFloat(on) { try { const w = await T.webviewWindow.WebviewWindow.getByLabel('orb'); if (w) { on ? await w.show() : await w.hide(); } } catch (_) {} }
  let lastEmit = 0; function floatEmit() { if (T && T.event && S.float === 'on') T.event.emit('tt-state', { state, level: lvl, accent: [css('--accent'), css('--accent2')] }); }
  setInterval(() => { if (state === 'speaking' && Date.now() - lastEmit > 90) { lastEmit = Date.now(); floatEmit(); } }, 100);
  if (T && T.event) { T.event.listen('orb-click', async () => { try { const w = T.webviewWindow.getCurrentWebviewWindow(); await w.show(); await w.setFocus(); } catch (_) {} }); if (S.float === 'on') setFloat(true); }

  // ───────── sign-in gate ─────────
  const gate = $('#gate'), gmsg = $('#gate-msg'); let gEmail = '';
  const gm = (t, ok) => { gmsg.textContent = t || ''; gmsg.className = 'gate-msg' + (ok ? ' ok' : ''); };
  $('#gate-email').addEventListener('submit', async e => { e.preventDefault(); gEmail = $('#g-email').value; gm('Sending…', true); try { await TimAuth.sendCode(gEmail); $('#gate-email').hidden = true; $('#gate-code').hidden = false; $('#g-code').focus(); $('#gate-sub').textContent = 'Enter the 6-digit code we emailed to ' + gEmail.trim() + '.'; gm(''); } catch (err) { gm(err.message); } });
  $('#gate-code').addEventListener('submit', async e => { e.preventDefault(); gm('Checking…', true); try { await TimAuth.verify(gEmail, $('#g-code').value); gm(''); } catch (err) { gm(/expired|invalid/i.test(err.message) ? 'That code is wrong or expired. Request a new one.' : err.message); } });
  $('#g-back').onclick = () => { $('#gate-code').hidden = true; $('#gate-email').hidden = false; $('#gate-sub').textContent = "Sign in with your email. We'll send you a 6-digit code."; gm(''); };
  let signedIn = false;
  TimAuth.onChange(sess => {
    if (sess && !signedIn) { signedIn = true; gate.hidden = true; conn.state = 'connecting'; renderConn(); net.connect(); }
    else if (!sess && signedIn !== false || (!sess && TimAuth.configured)) { signedIn = false; net.disconnect(); V.stopMic(); V.interrupt(); TT.me = null; conn.state = 'signedout'; gate.hidden = false; $('#gate-code').hidden = true; $('#gate-email').hidden = false; $('#admin-btn').hidden = true; $('#acct-email').textContent = 'Not signed in'; $('#acct-plan').textContent = ''; $('#acct-quota').textContent = ''; renderConn(); loadWorld(); } });
  if (TimAuth.configured) { const had = !!localStorage.getItem('timtim.session'); gate.hidden = had; conn.state = had ? 'connecting' : 'signedout'; if (had) { gmsg.textContent = ''; } TimAuth.restore().then(sess => { if (!sess && !localStorage.getItem('timtim.session')) gate.hidden = false; }); } else { conn.state = 'demo'; }

  TT.panels.initNotes(); TT.panels.initSkills(); TT.panels.initAdmin(); renderConn(); renderTasks();
  msg('a', "Hi, I'm Tim-Tim. Hold Space to talk, type below, or tap the cards around my core to explore. Your agent team is ready.");
  window.__timtim = { orb, setState: s => { state = s; orb.setState(s); $('#core').dataset.state = s; $('#think-t').textContent = s.toUpperCase(); }, agentUI, show: () => {} };
})();
