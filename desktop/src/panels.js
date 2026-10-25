/* Panels backed by the backend: API keys (own key, required on the free plan), memory notes, skill permissions,
   admin panel, phone pairing. */
(function () {
  const TT = window.TT, $ = s => document.querySelector(s), api = (p, o) => TT.net.api(p, o);
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const P = TT.panels = {};
  const ago = iso => { const m = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000)); return m < 1 ? 'just now' : m < 60 ? m + 'm ago' : m < 1440 ? Math.round(m / 60) + 'h ago' : Math.round(m / 1440) + 'd ago'; };

  // ───────── API keys (everyone: the free plan runs only on your own key) ─────────
  const CAPS = [['llm', 'Language model (chat)'], ['stt', 'Speech-to-text'], ['tts', 'Text-to-speech']];
  const SHARED_ROLES = ['pro', 'moderator', 'owner'];
  P.renderKeys = async role => {
    const shared = SHARED_ROLES.includes(role);           // Pro/staff may keep using the app's providers
    $('#keys-locked').hidden = true;
    $('#keys-tag').textContent = shared ? 'Optional' : 'Required';
    $('#keys-box').innerHTML = '';
    let provs = {}, saved = [];
    try { [provs, saved] = await Promise.all([api('/providers'), api('/keys')]); } catch (e) { $('#keys-box').innerHTML = `<p class="hint">Could not load keys: ${esc(e.message)}</p>`; return; }
    const oneCard = shared ? '' : `<div class="keyone"><b>Your own free Google key<span class="st" id="one-st">Covers chat, speech and voice</span></b>
      <p class="hint">Get one in about a minute at <b>aistudio.google.com/apikey</b> → <b>Create API key</b>. It costs nothing, and your usage stays yours: the free plan never uses the owner's keys.</p>
      <div class="kr"><input type="password" id="one-key" placeholder="Paste your key (starts with AIza…)" autocomplete="off"><button class="primary" id="one-save" type="button">Save key</button></div></div>`;
    $('#keys-box').innerHTML = oneCard + CAPS.map(([cap, label]) => { const s = saved.find(k => k.capability === cap);
      const state = s ? 'Using your ' + esc(s.provider) + ' key ' + esc(s.masked) : shared ? 'Using the shared free providers' : 'No key yet';
      return `<div class="keyrow" data-cap="${cap}"><b>${label}<span class="st ${s ? 'ok' : ''}" data-st>${state}</span></b>
        <div class="kr"><select data-prov>${(provs[cap] || []).map(p => `<option ${s && s.provider === p ? 'selected' : ''}>${p}</option>`).join('')}</select><input type="password" data-key placeholder="${s ? 'Paste a new key to replace' : 'Paste your API key'}" autocomplete="off"></div>
        <div class="ka"><button class="ghost" data-act="validate">Validate</button><button class="ghost" data-act="save">Save</button>${s ? '<button class="ghost danger" data-act="remove">Remove key</button>' : ''}</div></div>`; }).join('');
    const saveOne = $('#one-save');
    if (saveOne) saveOne.addEventListener('click', async () => {
      const key = $('#one-key').value.trim(), st = $('#one-st');
      const say = (t, cls) => { st.textContent = t; st.className = 'st ' + (cls || ''); };
      if (key.length < 8) { say('Paste your key first', 'bad'); return; }
      saveOne.disabled = true; say('Checking with Google…');
      try { const r = await api('/keys/one-key', { method: 'POST', body: { key } }); say('Saved ' + r.masked + ' ✓', 'ok'); $('#one-key').value = '';
        setTimeout(() => P.renderKeys(role), 700); P.refreshStatus(); }
      catch (err) { say(err.message, 'bad'); }
      finally { saveOne.disabled = false; }
    });
    $('#keys-box').querySelectorAll('.keyrow').forEach(row => row.addEventListener('click', async e => {
      const act = e.target.dataset.act; if (!act) return; const cap = row.dataset.cap, st = row.querySelector('[data-st]'), key = row.querySelector('[data-key]').value.trim(), provider = row.querySelector('[data-prov]').value;
      const say = (t, cls) => { st.textContent = t; st.className = 'st ' + (cls || ''); };
      try {
        if (act === 'remove') { await api('/keys/' + cap, { method: 'DELETE' }); say('Key removed', 'ok'); setTimeout(() => P.renderKeys(role), 600); P.refreshStatus(); return; }
        if (key.length < 8) { say('Paste a key first', 'bad'); return; }
        say('Checking…'); if (act === 'validate') { await api(`/keys/${cap}/validate`, { method: 'POST', body: { provider, key } }); say('Key works ✓ (not saved yet)', 'ok'); }
        else { const r = await api('/keys/' + cap, { method: 'PUT', body: { provider, key } }); say('Saved ' + r.masked, 'ok'); row.querySelector('[data-key]').value = ''; setTimeout(() => P.renderKeys(role), 700); P.refreshStatus(); }
      } catch (err) { say(err.message, 'bad'); }
    }));
  };
  P.refreshStatus = async () => { try { TT.emit('status', await api('/me')); } catch (_) {} };

  // ───────── memory notes ─────────
  let noteT = null;
  P.loadNotes = async (q = '') => {
    const ul = $('#note-list'); if (!TimAuth.getToken()) { ul.innerHTML = '<li class="muted">Sign in to see your memory.</li>'; return; }
    try { const { facts } = await api('/memory' + (q ? '?q=' + encodeURIComponent(q) : '')); if (!q) { $('#sat-mem-s').textContent = facts.length + (facts.length === 1 ? ' fact remembered' : ' facts remembered'); }
      ul.innerHTML = facts.length ? facts.map(f => `<li data-id="${f.id}"><span>${esc(f.fact)}<small>${f.scope === 'global' ? 'Everyone' : esc(f.scope)} · ${ago(f.created_at)}</small></span><button data-a="edit" title="Edit"><svg><use href="#i-edit"/></svg></button><button data-a="del" title="Delete"><svg><use href="#i-trash"/></svg></button></li>`).join('') : '<li class="muted">Nothing yet. Say “remember that …” in chat, or add a note above.</li>';
    } catch (e) { ul.innerHTML = `<li class="muted">${esc(e.message)}</li>`; }
  };
  P.initNotes = () => {
    $('#note-form').addEventListener('submit', async e => { e.preventDefault(); const fact = $('#note-in').value.trim(); if (!fact) return;
      try { await api('/memory', { method: 'POST', body: { fact, scope: $('#note-scope').value } }); $('#note-in').value = ''; P.loadNotes(); } catch (err) { TT.toast(err.message); } });
    $('#note-q').addEventListener('input', e => { clearTimeout(noteT); noteT = setTimeout(() => P.loadNotes(e.target.value.trim()), 300); });
    $('#note-list').addEventListener('click', async e => { const b = e.target.closest('button'); if (!b) return; const li = b.closest('li'), id = li.dataset.id;
      try {
        if (b.dataset.a === 'del') { await api('/memory/' + id, { method: 'DELETE' }); P.loadNotes(); }
        else if (b.dataset.a === 'edit') { const span = li.querySelector('span'), old = span.firstChild.textContent, inp = document.createElement('input'); inp.value = old; span.replaceChildren(inp); inp.focus();
          const commit = async () => { const v = inp.value.trim(); if (v && v !== old) { try { await api('/memory/' + id, { method: 'PATCH', body: { fact: v } }); } catch (err) { TT.toast(err.message); } } P.loadNotes(); };
          inp.addEventListener('keydown', k => { if (k.key === 'Enter') commit(); if (k.key === 'Escape') P.loadNotes(); }); inp.addEventListener('blur', commit); }
      } catch (err) { TT.toast(err.message); } });
  };

  // ───────── skills & permissions ─────────
  P.renderSkills = () => {
    const A = TT.actions, ul = $('#skill-list');
    ul.innerHTML = Object.entries(A.SKILLS).map(([k, m]) => { const p = A.perm(k), hi = m.risk === 'high';
      return `<li data-k="${k}"><div><b>${m.title}<span class="risk ${m.risk}">${m.risk}</span></b><span>${k}</span></div><div class="seg"><button data-v="ask" class="${p === 'ask' ? 'on' : ''}">Ask</button>${hi ? '' : `<button data-v="always" class="${p === 'always' ? 'on' : ''}">Always</button>`}<button data-v="never" class="${p === 'never' ? 'on' : ''}">Never</button></div></li>`; }).join('');
    $('#sat-skill-s').textContent = Object.keys(A.SKILLS).filter(k => A.perm(k) !== 'never').length + ' of ' + Object.keys(A.SKILLS).length + ' skills allowed';
  };
  P.initSkills = () => { $('#skill-list').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; A_set(b.closest('li').dataset.k, b.dataset.v); }); TT.on('perms', P.renderSkills); P.renderSkills(); };
  const A_set = (k, v) => TT.actions.setPerm(k, v);

  // ───────── admin panel ─────────
  const isOrdinary = r => r === 'free' || r === 'pro';
  async function search() {
    const q = $('#admin-q').value.trim(), ul = $('#admin-users'); ul.innerHTML = '<li class="muted">Searching…</li>';
    try { const rows = await api('/admin/users?email=' + encodeURIComponent(q)), me = TT.me || {};
      ul.innerHTML = rows.length ? rows.map(u => { const btns = [];
        if (isOrdinary(u.role)) btns.push(u.role === 'pro' ? `<button class="ghost danger" data-a="plan" data-v="free">Revoke Pro</button>` : `<button class="primary" data-a="plan" data-v="pro">Grant Pro</button>`);
        if (me.role === 'owner' && isOrdinary(u.role)) btns.push(`<button class="ghost" data-a="mod" data-v="1">Make moderator</button>`);
        if (me.role === 'owner' && u.role === 'moderator') btns.push(`<button class="ghost danger" data-a="mod" data-v="0">Remove moderator</button>`);
        return `<li data-id="${u.id}"><div><b>${esc(u.email)}<span class="badge-role ${u.role}">${u.role}</span></b><span>${u.granted_at ? 'Pro granted ' + ago(u.granted_at) : 'No grant on record'}</span></div><div class="btns">${btns.join('')}</div></li>`; }).join('') : '<li class="muted">No users match.</li>';
    } catch (e) { ul.innerHTML = `<li class="muted">${esc(e.message)}</li>`; }
  }
  async function audit() { try { const rows = await api('/admin/audit'); $('#admin-audit').innerHTML = rows.slice(0, 12).map(r => `<li>${esc(r.actor)} → <b>${r.action.replace('_', ' ')}</b> → ${esc(r.target)} · ${ago(r.at)}</li>`).join('') || '<li>No changes yet.</li>'; } catch (_) {} }
  P.openAdmin = () => { $('#sheet-admin').hidden = false; search(); audit(); };
  P.initAdmin = () => {
    $('#admin-form').addEventListener('submit', e => { e.preventDefault(); search(); });
    $('#admin-users').addEventListener('click', async e => { const b = e.target.closest('button'); if (!b || !b.dataset.a) return; const id = b.closest('li').dataset.id; b.disabled = true;
      try { if (b.dataset.a === 'plan') await api(`/admin/users/${id}/plan`, { method: 'POST', body: { plan: b.dataset.v } }); else await api(`/admin/users/${id}/moderator`, { method: 'POST', body: { enabled: b.dataset.v === '1' } });
        TT.toast('Updated'); search(); audit(); } catch (err) { TT.toast(err.message); b.disabled = false; } });
  };

  // ───────── phone pairing ─────────
  let pairTimer = null;
  P.openPair = async () => {
    const cfg = window.TIMTIM_CONFIG || {};
    const url = /^https?:$/.test(location.protocol) ? location.origin + location.pathname.replace(/[^/]*$/, '') : (cfg.WEB_URL || '');
    if (!url) { TT.toast('Set WEB_URL in config.js to your hosted app address first.'); return; }
    const qr = qrcode(0, 'M'); qr.addData(url); qr.make();
    $('#qr').innerHTML = `<img alt="QR code for ${url}" src="${qr.createDataURL(6, 2)}">`; $('#pair-code').textContent = ''; $('#pair-exp').textContent = url.replace(/^https?:\/\//, '');
    $('#pair').hidden = false; clearInterval(pairTimer);
  };
  $('#pair-close').onclick = () => { $('#pair').hidden = true; clearInterval(pairTimer); };
})();
