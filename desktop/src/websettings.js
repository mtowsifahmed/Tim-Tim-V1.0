/* Adds "Live web search: Auto / Always / Off" plus a per-account Tavily key to Settings, and sends your language so
   news is local to you. Needs TT.settings (exposed by apply_patch_3.py); quietly does nothing without it.
   The owner runs on the server's own Tavily key; it is never handed to another account, so everyone else sees a
   placeholder and can paste their own. */
(function () {
  const TT = window.TT; if (!TT || !TT.settings) return;
  const S = TT.settings, anchor = document.getElementById('h-pers'); if (!anchor) return;
  let changed = false;
  if (!S.web) { S.web = 'auto'; changed = true; }
  if (!S.lang) { S.lang = navigator.language || 'en-US'; changed = true; }
  const row = document.createElement('div');
  row.innerHTML = '<h4>Live web</h4><label class="row">Live web search<div class="seg" id="seg-web"><button data-v="auto">Auto</button><button data-v="on">Always</button><button data-v="off">Off</button></div></label>' +
    '<p class="hint">Auto looks things up online for news, prices, weather and "latest" questions, and shows the sources under the answer.</p>';
  anchor.parentNode.insertBefore(row, anchor);
  const seg = row.querySelector('#seg-web'), mark = () => seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === S.web));
  seg.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; S.web = b.dataset.v; mark(); if (TT.persistSettings) TT.persistSettings(); });
  mark(); if (changed && TT.persistSettings) TT.persistSettings();

  // ───────── search key (this account only) ─────────
  const box = document.createElement('div');
  box.id = 'web-key-box';
  box.innerHTML = '<h4>Web search key</h4>' +
    '<label class="row" id="web-key-row">Tavily API key<input type="password" id="web-key" placeholder="tvly-…" autocomplete="off"></label>' +
    '<div class="keybtns"><button class="ghost" id="web-key-save">Save</button><button class="ghost danger" id="web-key-del" hidden>Remove</button></div>' +
    '<p class="hint" id="web-key-hint"></p>';
  row.parentNode.insertBefore(box, row.nextSibling);
  const inp = box.querySelector('#web-key'), rowEl = box.querySelector('#web-key-row'), save = box.querySelector('#web-key-save'),
    del = box.querySelector('#web-key-del'), hint = box.querySelector('#web-key-hint');
  const say = (t, bad) => { hint.textContent = t; hint.className = 'hint' + (bad ? ' bad' : ''); };

  async function loadKey() {
    if (!window.TimAuth || !TimAuth.getToken()) { box.hidden = true; return; }
    box.hidden = false;
    let st;
    try { st = await TT.net.api('/search/key'); } catch (e) { say('Could not load your search key: ' + e.message, true); return; }
    inp.placeholder = st.placeholder || 'tvly-…';
    if (st.shared) {                                   // the owner: the app's own key, never shown and never shared
      rowEl.hidden = save.hidden = del.hidden = true;
      say('Using the app owner’s Tavily key. No other account can use it.');
      return;
    }
    rowEl.hidden = save.hidden = false; del.hidden = !st.configured;
    say(st.configured
      ? 'Saved key ' + st.masked + ' is used for your searches. Paste a new one to replace it.'
      : 'Optional. A free Tavily key (1,000 searches a month, no card, at tavily.com) makes results more reliable. Without one the free keyless sources are used.');
  }

  save.addEventListener('click', async () => {
    const key = inp.value.trim();
    if (key.length < 8) { say('Paste a key first.', true); return; }
    say('Checking the key…'); save.disabled = true;
    try {
      const r = await TT.net.api('/search/key', { method: 'PUT', body: { key } });
      inp.value = ''; say('Saved ' + r.masked + (r.checked ? '.' : ' (Tavily could not be reached to check it, but it will be used).'));
    } catch (e) { say(e.message, true); }
    finally { save.disabled = false; loadKey(); }
  });
  del.addEventListener('click', async () => {
    try { await TT.net.api('/search/key', { method: 'DELETE' }); say('Key removed; the free keyless sources will be used.'); }
    catch (e) { say(e.message, true); }
    loadKey();
  });

  loadKey();
  TT.on('ready', loadKey);                             // the app is signed in and connected
  TT.on('status', loadKey);                            // ...or the account changed
})();
