/* The always-on-top floating orb. It mirrors the main window's state; click it to bring Tim-Tim forward, drag to move it. */
(function () {
  const T = window.__TAURI__; if (!T) return;
  const orb = new TimOrb(document.getElementById('orb'), { figure: 'sphere', colorMode: 'accent' });
  T.event.listen('tt-state', e => { const p = e.payload || {}; orb.setState(p.state || 'idle'); orb.setLevel(p.level || 0); if (p.accent) orb.setAccent(p.accent[0], p.accent[1]); });
  let down = null, dragging = false;
  const w = document.getElementById('wrap');
  w.addEventListener('pointerdown', e => { down = [e.screenX, e.screenY]; dragging = false; });
  w.addEventListener('pointermove', async e => { if (down && !dragging && Math.hypot(e.screenX - down[0], e.screenY - down[1]) > 4) { dragging = true; try { await T.webviewWindow.getCurrentWebviewWindow().startDragging(); } catch (_) {} } });
  w.addEventListener('pointerup', () => { if (down && !dragging) T.event.emit('orb-click', {}); down = null; });
})();
