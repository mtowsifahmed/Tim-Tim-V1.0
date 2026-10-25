/* Shows where a live-web answer came from: small clickable chips under the assistant's reply. */
(function () {
  const TT = window.TT; if (!TT) return;
  const css = document.createElement('style');
  css.textContent = '.sources{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.sources a{display:inline-flex;gap:6px;align-items:center;max-width:100%;padding:4px 10px;border-radius:99px;font-size:11px;color:var(--muted);text-decoration:none;background:var(--input);border:1px solid var(--card-b);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sources a:hover{color:var(--text);border-color:var(--accent)}.sources b{color:var(--accent);font-weight:600}.sources .lbl{font-size:10.5px;color:var(--muted);align-self:center;margin-right:2px}';
  document.head.appendChild(css);
  function openLink(url) {
    try { if (window.__TAURI__ && window.__TAURI__.core) { window.__TAURI__.core.invoke('open_url', { url }); return; } } catch (_) {}
    window.open(url, '_blank', 'noopener');
  }
  TT.on('sources', m => {
    const all = document.querySelectorAll('#log .m.a .bub'), bub = all[all.length - 1];
    if (!bub || !Array.isArray(m.items) || !m.items.length) return;
    const holder = bub.parentElement; let box = holder.querySelector('.sources'); if (box) box.remove();
    box = document.createElement('div'); box.className = 'sources'; box.innerHTML = '<span class="lbl">Sources</span>';
    m.items.forEach((s, i) => {
      if (!/^https?:\/\//.test(s.url)) return;
      const a = document.createElement('a'); a.href = '#'; a.title = s.title; a.innerHTML = '<b>' + (i + 1) + '</b>';
      a.appendChild(document.createTextNode(' ' + (s.source || 'link') + (s.age ? ' · ' + s.age : '')));
      a.addEventListener('click', e => { e.preventDefault(); openLink(s.url); }); box.appendChild(a);
    });
    holder.appendChild(box); const log = document.getElementById('log'); if (log) log.scrollTop = log.scrollHeight;
  });
})();
