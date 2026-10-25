/* Backend connection: WebSocket (voice + chat + relay) and authenticated HTTP helper.
   Emits events through TT.on(type, fn). Binary frames (TTS audio) are paired with the preceding "audio" header. */
(function () {
  const TT = window.TT = window.TT || {};
  const handlers = {};
  TT.on = (t, f) => { (handlers[t] = handlers[t] || []).push(f); };
  TT.emit = (t, d) => { (handlers[t] || []).forEach(f => { try { f(d); } catch (e) { console.error(t, e); } }); };

  let ws = null, want = false, retry = 0, retryTimer = null, hb = null, pingAt = 0, pendingAudio = null;
  const net = TT.net = { url: '', device: 'desktop', latency: null };
  net.http = () => net.url.replace(/^ws/, 'http').replace(/\/ws$/, '');
  net.ready = () => !!ws && ws.readyState === 1 && net.authed;
  net.send = o => { if (net.ready()) { ws.send(JSON.stringify(o)); return true; } return false; };
  net.sendBinary = b => { if (net.ready()) ws.send(b); };

  net.api = async (path, opts = {}) => {
    const t = TimAuth.getToken();
    const r = await fetch(net.http() + path, { ...opts, headers: { 'Content-Type': 'application/json', ...(t ? { Authorization: 'Bearer ' + t } : {}), ...(opts.headers || {}) },
      body: opts.body !== undefined && typeof opts.body !== 'string' ? JSON.stringify(opts.body) : opts.body });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(typeof j.detail === 'string' ? j.detail : 'Request failed (' + r.status + ')'); e.status = r.status; throw e; }
    return j;
  };

  net.connect = () => {
    clearTimeout(retryTimer); want = true; net.authed = false;
    if (ws) { ws.onclose = null; ws.close(); }
    if (!TimAuth.getToken()) return;
    TT.emit('conn', { state: 'connecting' });
    const sock = ws = new WebSocket(net.url); sock.binaryType = 'arraybuffer';
    sock.onopen = () => { retry = 0; sock.send(JSON.stringify({ type: 'auth', token: TimAuth.getToken(), device: net.device, name: net.deviceName || net.device })); };
    sock.onclose = ev => {
      if (ws === sock) ws = null; net.authed = false; clearInterval(hb);
      if (ev.code === 4401) {                                              // token rejected: refresh once; sign out only if that truly fails
        TT.emit('conn', { state: 'connecting' });
        TimAuth.refreshNow().then(ok => { if (ok) { net.connect(); } else if (!TimAuth.getToken()) { TT.emit('conn', { state: 'expired' }); } else { retryTimer = setTimeout(net.connect, 15000); } });
        return;
      }
      TT.emit('conn', { state: 'down' });
      if (want) retryTimer = setTimeout(net.connect, Math.min(15000, 1000 * 2 ** retry++));
    };
    sock.onerror = () => TT.emit('conn', { state: 'error', first: retry === 0 });
    sock.onmessage = ev => {
      if (typeof ev.data !== 'string') { if (pendingAudio) { TT.emit('audio', { meta: pendingAudio, bytes: ev.data }); pendingAudio = null; } return; }
      const m = JSON.parse(ev.data);
      if (m.type === 'ready') { net.authed = true; hb = setInterval(() => { pingAt = performance.now(); net.send({ type: 'ping' }); }, 20000); pingAt = performance.now(); net.send({ type: 'ping' }); }
      if (m.type === 'pong') { net.latency = Math.round(performance.now() - pingAt); TT.emit('latency', net.latency); return; }
      if (m.type === 'audio') { pendingAudio = m; return; }
      TT.emit(m.type, m);
    };
  };
  net.disconnect = () => { want = false; clearTimeout(retryTimer); clearInterval(hb); if (ws) { ws.onclose = null; ws.close(); ws = null; } net.authed = false; };
})();
