/* Launch features: your logo, legal links, "Your data" tools (download / copy / delete), app install button, version,
   and the offline-capable service worker. Everything here is optional UI around the main app. */
(function () {
  const TT = window.TT || {}, cfg = window.TIMTIM_CONFIG || {}, VERSION = cfg.APP_VERSION || '1.0.0', BRAND = cfg.CREATED_BY || 'Zaftan Studios';
  const inTauri = !!(window.__TAURI__ && window.__TAURI__.core);
  const css = document.createElement('style');
  css.textContent = '.logo{background:#07070a url(icons/logo-mark.png) center/cover !important;box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--accent) 40%,transparent),0 12px 30px -18px var(--accent) !important}.logo b{display:none}' +
    '.as-logo{background:#07070a url(icons/logo-mark.png) center/cover !important;color:transparent !important;box-shadow:0 8px 22px -14px var(--accent),inset 0 0 0 1px color-mix(in srgb,var(--accent) 30%,transparent) !important}' +
    '.gate-logo{display:block;width:min(230px,64%);margin:0 auto 10px;border-radius:24px;box-shadow:0 24px 60px -34px var(--accent)}' +
    '.legal{font-size:12px;color:var(--muted);margin:14px 0 0 !important}.legal a,.about a{color:var(--accent);text-decoration:none;cursor:pointer}.legal a:hover,.about a:hover{text-decoration:underline}' +
    '.yd .row{flex-wrap:wrap;gap:8px;justify-content:flex-start}.yd .confirm{display:none;padding:12px;border-radius:12px;background:var(--input);border:1px solid #f43f5e66;margin-top:6px}.yd .confirm.on{display:block}' +
    '.yd .confirm input{width:100%;margin:8px 0}.yd .msg{font-size:12px;margin-top:6px;min-height:16px}.yd .msg.bad{color:#fb7185}.yd .msg.ok{color:#34d399}.about{font-size:12px;color:var(--muted);line-height:1.7}';
  document.head.appendChild(css);

  // ───────── your logo on the sign-in screen ─────────
  const big = document.querySelector('.gate-card .logo.big');
  if (big) { const img = new Image(); img.src = 'icons/logo-full.png'; img.alt = 'Tim-Tim'; img.className = 'gate-logo'; big.replaceWith(img); }
  const legalOpen = page => { try { if (inTauri && cfg.WEB_URL) { window.__TAURI__.core.invoke('open_url', { url: cfg.WEB_URL.replace(/\/$/, '') + '/' + page }); return; } } catch (_) {} window.open(page, '_blank', 'noopener'); };
  const links = () => '<a data-legal="terms.html">Terms</a> and <a data-legal="privacy.html">Privacy Policy</a>';
  const card = document.querySelector('.gate-card');
  if (card) { const p = document.createElement('p'); p.className = 'legal'; p.innerHTML = 'By continuing you agree to the ' + links() + '.'; card.appendChild(p); }
  document.addEventListener('click', e => { const a = e.target.closest('[data-legal]'); if (a) { e.preventDefault(); legalOpen(a.dataset.legal); } });

  // ───────── Settings: your data, install, about ─────────
  const panel = document.querySelector('#drawer .drawer-panel'); if (!panel) return;
  const dev = [...panel.querySelectorAll('h4')].find(h => /developer/i.test(h.textContent));
  const box = document.createElement('div'); box.className = 'yd';
  box.innerHTML = '<h4>Your data</h4><div class="row"><button class="ghost" id="yd-dl">Download my data</button><button class="ghost" id="yd-copy">Copy my data</button><button class="ghost danger" id="yd-del">Delete my account</button></div>' +
    '<div class="confirm" id="yd-confirm"><b>This permanently deletes your account, memory, settings and saved keys.</b><p class="hint">It cannot be undone. Type DELETE to confirm.</p><input type="text" id="yd-word" placeholder="DELETE" autocomplete="off"><button class="ghost danger" id="yd-go">Permanently delete</button></div>' +
    '<p class="msg" id="yd-msg"></p>' +
    '<div id="yd-install" hidden><h4>Install</h4><button class="ghost" id="yd-install-btn">Install Tim-Tim as an app</button></div><p class="hint" id="yd-ios" hidden>On iPhone: tap the Share button, then “Add to Home Screen”.</p>' +
    '<h4>About</h4><p class="about">Tim-Tim v' + VERSION + ' · made by ' + BRAND + '<br>' + links() + '</p>';
  (dev || { parentNode: panel, appendChild: 0 }).parentNode.insertBefore(box, dev || null);
  const $ = s => box.querySelector(s), say = (t, c) => { const m = $('#yd-msg'); m.textContent = t; m.className = 'msg ' + (c || ''); };
  const fetchData = async () => { if (!TT.net || !TimAuth.getToken()) throw new Error('Sign in first.'); return JSON.stringify(await TT.net.api('/account/export'), null, 2); };
  $('#yd-dl').onclick = async () => { try { const json = await fetchData(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' })); a.download = 'tim-tim-my-data.json'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); say('Downloaded. If nothing was saved on this device, use “Copy my data”.', 'ok'); } catch (e) { say(e.message, 'bad'); } };
  $('#yd-copy').onclick = async () => { try { await navigator.clipboard.writeText(await fetchData()); say('Copied to the clipboard. Paste it into a text file to keep it.', 'ok'); } catch (e) { say(e.message || 'Could not copy.', 'bad'); } };
  $('#yd-del').onclick = () => { if (!TimAuth.getToken()) { say('Sign in first.', 'bad'); return; } $('#yd-confirm').classList.toggle('on'); };
  $('#yd-go').onclick = async () => {
    if ($('#yd-word').value.trim() !== 'DELETE') { say('Type DELETE (capital letters) to confirm.', 'bad'); return; }
    try { await TT.net.api('/account/delete', { method: 'POST', body: { confirm: 'DELETE' } }); say('Your account was deleted. Goodbye!', 'ok');
      try { Object.keys(localStorage).filter(k => k.startsWith('timtim.')).forEach(k => localStorage.removeItem(k)); } catch (_) {}
      await TimAuth.signOut(); setTimeout(() => location.reload(), 1200); }
    catch (e) { say(e.message, 'bad'); }
  };

  // install button (Chrome/Edge/Android) or the iPhone hint
  let deferred = null;
  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; $('#yd-install').hidden = false; });
  $('#yd-install-btn').onclick = async () => { if (!deferred) return; deferred.prompt(); try { await deferred.userChoice; } catch (_) {} deferred = null; $('#yd-install').hidden = true; };
  window.addEventListener('appinstalled', () => { $('#yd-install').hidden = true; });
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone && !inTauri) $('#yd-ios').hidden = false;

  // offline-capable shell (web only)
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol) && !inTauri) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
