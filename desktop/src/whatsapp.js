/* WhatsApp by voice, the official way: Tim-Tim opens WhatsApp or a chat with a person from YOUR contact list, with your message
   typed in, after you confirm. It cannot read your chats or post status (WhatsApp offers no official way to do either).
   Your contact list (names and numbers) lives only on this device. Only the name and the message you spoke ever leave it. */
(function () {
  const TT = window.TT; if (!TT) return;
  const KEY = 'timtim.wa.contacts', KAUTO = 'timtim.wa.autosend', KCC = 'timtim.wa.cc';
  const inv = () => window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const store = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  const read = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (_) { return d; } };
  const CC = { IN: '91', US: '1', CA: '1', GB: '44', AU: '61', DE: '49', FR: '33', BR: '55', JP: '81', AE: '971', PK: '92', BD: '880', NG: '234', ZA: '27', ID: '62', PH: '63', MX: '52', ES: '34', IT: '39', SA: '966', EG: '20', TR: '90', NP: '977', LK: '94' };
  const regionCC = () => { const m = /[-_]([A-Za-z]{2})\b/.exec(navigator.language || ''); return m && CC[m[1].toUpperCase()] || ''; };
  let contacts = []; try { contacts = JSON.parse(read(KEY, '[]')); } catch (_) {}
  const save = () => store(KEY, JSON.stringify(contacts));
  const autoSend = () => read(KAUTO, '1') !== '0';
  const defaultCC = () => read(KCC, regionCC());

  // ───────── numbers and names ─────────
  const norm = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
  /** Full international number as digits, or '' if it cannot be right. A 10-digit number gets your default country code. */
  function fullNumber(raw) {
    const s = String(raw || '').trim(); let d = s.replace(/\D/g, ''); if (!d) return '';
    if (!s.startsWith('+')) { d = d.replace(/^0+/, ''); const cc = defaultCC().replace(/\D/g, ''); if (cc && d.length <= 10 && !d.startsWith(cc)) d = cc + d; }
    return d.length >= 8 && d.length <= 15 ? d : '';
  }
  function resolve(name) {
    const q = norm(name); if (!q) return { missing: true };
    const hit = f => contacts.filter(f);
    let m = hit(c => norm(c.name) === q || (c.aliases || []).some(a => norm(a) === q));
    if (!m.length) m = hit(c => norm(c.name).split(' ')[0] === q || norm(c.name).startsWith(q) || (c.aliases || []).some(a => norm(a).startsWith(q)));
    if (m.length === 1) return { contact: m[0] };
    return m.length ? { ambiguous: m.map(c => c.name) } : { missing: true };
  }
  const plus = d => '+' + d;

  // shown inside the confirmation box so you can see exactly who will receive it
  TT.whatsapp = {
    contacts: () => contacts.slice(), resolve, fullNumber,
    describe(m) {
      if (!/^whatsapp_/.test(m.skill)) return '';
      if (!m.args.contact) return '\nOpens the WhatsApp app.';
      const r = resolve(m.args.contact);
      return r.contact ? `\nSent to: ${r.contact.name} (${plus(r.contact.number)})` : r.ambiguous ? `\nMore than one match: ${r.ambiguous.join(', ')}` : `\nNo saved number for "${m.args.contact}"`;
    },
    async run(skill, args) {
      let phone = '';
      if (args.contact) {
        const r = resolve(args.contact);
        if (r.ambiguous) return { ok: false, error: `More than one contact matches "${args.contact}": ${r.ambiguous.join(', ')}. Say the full name.` };
        if (!r.contact) return { ok: false, error: `I don't have a WhatsApp number saved for "${args.contact}". Add them in Settings → WhatsApp contacts.` };
        phone = r.contact.number;
      }
      const call = inv();
      if (skill === 'whatsapp_open') {
        if (call) { try { return { ok: true, output: await call('whatsapp_open', { phone: phone || null }) }; } catch (e) { return { ok: false, error: String(e) }; } }
        if (!phone) return { ok: false, error: 'Say whose chat to open. (The desktop app can also open WhatsApp itself.)' };
        window.open('https://wa.me/' + phone, '_blank', 'noopener'); return { ok: true, output: 'Opened the WhatsApp chat.' };
      }
      if (!phone) return { ok: false, error: 'Who should I message? Say the contact name.' };
      if (call) {                                                   // desktop app: step aside, open the chat with the text typed in, press Send
        let w = null; try { w = window.__TAURI__.webviewWindow.getCurrentWebviewWindow(); } catch (_) {}
        const auto = autoSend();
        try { if (w && auto) { await w.minimize(); await sleep(700); } return { ok: true, output: await call('whatsapp_send', { phone, text: args.text, autoSend: auto }) }; }
        catch (e) { return { ok: false, error: String(e) }; }
        finally { try { if (w && auto) { await sleep(600); await w.unminimize(); await w.setFocus(); } } catch (_) {} }
      }
      window.open('https://wa.me/' + phone + '?text=' + encodeURIComponent(args.text), '_blank', 'noopener');
      return { ok: true, output: 'Opened WhatsApp with your message ready. Tap Send to send it.' };   // browsers and phones cannot press Send for you
    },
  };

  // ───────── contact book in Settings ─────────
  const panel = document.querySelector('#drawer .drawer-panel'); if (!panel) return;
  const css = document.createElement('style');
  css.textContent = '.wa .list{list-style:none;padding:0;display:grid;gap:6px;max-height:190px;overflow:auto;margin:8px 0}.wa li{display:flex;gap:8px;align-items:center;padding:8px 10px;border-radius:10px;background:var(--input);font-size:13px}' +
    '.wa li span{flex:1;overflow-wrap:anywhere}.wa li small{color:var(--muted);display:block;font-size:11px}.wa li button{color:var(--muted);width:24px;height:24px}.wa li button:hover{color:var(--accent)}' +
    '.wa .add{display:grid;grid-template-columns:1fr 1fr auto;gap:6px}.wa input[type=text]{padding:8px 10px;font-size:13px}.wa .row{flex-wrap:wrap;gap:8px;justify-content:flex-start}.wa .msg{font-size:12px;min-height:16px;margin-top:4px}.wa .msg.bad{color:#fb7185}.wa .msg.ok{color:#34d399}';
  document.head.appendChild(css);
  const box = document.createElement('div'); box.className = 'wa';
  box.innerHTML = '<h4>WhatsApp contacts</h4><p class="hint">Say “message Mom on WhatsApp saying I\'ll be late”. Names and numbers stay on this device; Tim-Tim opens the chat with your text ready, only after you confirm. It cannot read chats or post status.</p>' +
    '<ul class="list" id="wa-list"></ul><div class="add"><input type="text" id="wa-name" placeholder="Name"><input type="text" id="wa-num" placeholder="+91 98765 43210"><button class="ghost" id="wa-add">Add</button></div>' +
    '<div class="row"><label class="ghost" style="cursor:pointer">Import contacts (.vcf or .csv)<input type="file" id="wa-file" accept=".vcf,.csv,.txt,text/vcard,text/csv" hidden></label></div>' +
    '<label class="row">Default country code<input type="text" id="wa-cc" style="width:90px" placeholder="91"></label>' +
    '<label class="row" id="wa-auto-row">Desktop app: press Send for me<div class="seg" id="wa-auto"><button data-v="1">On</button><button data-v="0">Off</button></div></label><p class="msg" id="wa-msg"></p>';
  const dev = [...panel.querySelectorAll('h4')].find(h => /developer|your data/i.test(h.textContent));
  panel.insertBefore(box, dev || null);
  const $ = s => box.querySelector(s), say = (t, c) => { const m = $('#wa-msg'); m.textContent = t; m.className = 'msg ' + (c || ''); };
  function render() {
    const ul = $('#wa-list'); ul.innerHTML = '';
    if (!contacts.length) { const li = document.createElement('li'); li.innerHTML = '<span><small>No contacts yet. Add one below or import a file.</small></span>'; ul.appendChild(li); return; }
    contacts.slice().sort((a, b) => a.name.localeCompare(b.name)).forEach(c => {
      const li = document.createElement('li'), sp = document.createElement('span'), b = document.createElement('button');
      sp.textContent = c.name; const sm = document.createElement('small'); sm.textContent = plus(c.number); sp.appendChild(sm);
      b.textContent = '✕'; b.title = 'Remove'; b.onclick = () => { contacts = contacts.filter(x => x !== c); save(); render(); }; li.append(sp, b); ul.appendChild(li);
    });
  }
  function add(name, raw) {
    name = String(name || '').trim().slice(0, 80); const number = fullNumber(raw);
    if (!name || !number) return false;
    if (contacts.some(c => norm(c.name) === norm(name) && c.number === number)) return true;
    contacts.push({ name, number }); return true;
  }
  $('#wa-add').onclick = () => { if (add($('#wa-name').value, $('#wa-num').value)) { save(); render(); $('#wa-name').value = $('#wa-num').value = ''; say('Added.', 'ok'); } else say('Enter a name and a full phone number (with country code, or set the default country code below).', 'bad'); };
  $('#wa-cc').value = defaultCC(); $('#wa-cc').addEventListener('change', e => { store(KCC, e.target.value.replace(/\D/g, '')); });
  const seg = $('#wa-auto'), mark = () => seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === (autoSend() ? '1' : '0')));
  seg.addEventListener('click', e => { const b = e.target.closest('button'); if (b) { store(KAUTO, b.dataset.v); mark(); } }); mark();
  if (!inv()) $('#wa-auto-row').hidden = true;                      // only the desktop app can press Send

  // vCard (.vcf) and simple CSV import
  function parseVcf(t) {
    const out = []; t = t.replace(/\r?\n[ \t]/g, '');               // unfold wrapped lines
    t.split(/BEGIN:VCARD/i).slice(1).forEach(card => {
      const fn = /^FN[^:]*:(.+)$/im.exec(card); let name = fn ? fn[1].trim() : '';
      if (!name) { const n = /^N[^:]*:(.+)$/im.exec(card); if (n) { const p = n[1].split(';'); name = ((p[1] || '') + ' ' + (p[0] || '')).trim(); } }
      [...card.matchAll(/^(?:item\d+\.)?TEL[^:]*:(.+)$/gim)].forEach(m => out.push([name, m[1].trim()]));
    }); return out;
  }
  function parseCsv(t) {
    return t.split(/\r?\n/).map(l => l.split(/[,;\t]/).map(x => x.replace(/^"|"$/g, '').trim())).filter(r => r.length >= 2 && r[0] && /\d/.test(r[1] || ''));
  }
  $('#wa-file').addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return; const text = await f.text(); const rows = /BEGIN:VCARD/i.test(text) ? parseVcf(text) : parseCsv(text); let n = 0;
    rows.forEach(([name, num]) => { if (add(name, num)) n++; }); save(); render(); e.target.value = '';
    say(n ? `Imported ${n} number${n === 1 ? '' : 's'}. People whose numbers can't be right were skipped.` : 'No usable contacts found in that file.', n ? 'ok' : 'bad');
  });
  render();
})();
