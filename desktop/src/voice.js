/* Voice layer: microphone capture (16 kHz PCM) with push-to-talk / hands-free / wake-phrase activation,
   sentence-by-sentence audio playback with barge-in, a "thinking" filler, and a live output level. */
(function () {
  const TT = window.TT, V = TT.voice = { mode: 'ptt', wake: 'hey tim', speakReplies: true, micOn: false, recording: false, playing: false, micError: '', deviceId: '', devices: [] };
  let ctx, stream, src, proc, mute, analyser, outGain, floor = 0.004, loud = 0, quiet = 0, ring = [], recStart = 0, gotResponse = true, fillerT = null, vadHold = 0;
  let pttHeld = false, pttGen = 0; const MIN_TAP_MS = 350;
  let nextTime = 0, sources = new Set(), decoded = new Map(), nextSeq = 1, pendingDecode = 0, turnDone = true, meter = 0;

  async function audio() { if (!ctx) { ctx = new (window.AudioContext || window.webkitAudioContext)(); outGain = ctx.createGain(); analyser = ctx.createAnalyser(); analyser.fftSize = 512; outGain.connect(analyser); analyser.connect(ctx.destination); } if (ctx.state !== 'running') await ctx.resume(); return ctx; }

  // ───────── microphone ─────────
  V.startMic = async () => {
    if (V.micOn) return true;
    try {
      await audio();
      const audio_constraints = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 };
      // Lock onto the microphone the user picked; if that device vanished, fall back to the default one.
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: V.deviceId ? { ...audio_constraints, deviceId: { exact: V.deviceId } } : audio_constraints }); }
      catch (e) { if (!V.deviceId || e.name !== 'OverconstrainedError') throw e; stream = await navigator.mediaDevices.getUserMedia({ audio: audio_constraints }); }
    } catch (e) { V.micError = e.name === 'NotAllowedError' ? 'Microphone permission was denied.' : 'No microphone available.'; TT.emit('mic', { error: V.micError }); return false; }
    src = ctx.createMediaStreamSource(stream); proc = ctx.createScriptProcessor(4096, 1, 1); mute = ctx.createGain(); mute.gain.value = 0;
    proc.onaudioprocess = onFrame; src.connect(proc); proc.connect(mute); mute.connect(ctx.destination); V.micOn = true; V.micError = ''; TT.emit('mic', { on: true });
    listDevices(); return true;
  };

  // Names are only readable after the user has granted microphone access once.
  V.listDevices = listDevices;
  async function listDevices() {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      V.devices = all.filter(d => d.kind === 'audioinput').map(d => ({ id: d.deviceId, label: d.label || 'Microphone ' + (d.deviceId.slice(0, 4) || '?') }));
      TT.emit('micdevices', V.devices);
    } catch (_) {}
  }
  V.setDevice = id => {
    V.deviceId = id || '';
    if (V.micOn) { const was = V.recording; V.stopMic(); if (was) TT.emit('toast', 'Microphone changed.'); }
  };
  V.stopMic = () => { if (!V.micOn) return; try { proc.disconnect(); src.disconnect(); stream.getTracks().forEach(t => t.stop()); } catch (_) {} V.micOn = false; if (V.recording) cancelUtterance(); pttHeld = false; pttGen++; TT.emit('mic', { on: false }); };

  function pcm16k(f) {
    const ratio = ctx.sampleRate / 16000, n = Math.floor(f.length / ratio), out = new Int16Array(n);
    for (let i = 0; i < n; i++) { const a = Math.floor(i * ratio), b = Math.min(f.length, Math.floor((i + 1) * ratio)); let s = 0; for (let j = a; j < b; j++) s += f[j]; const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a))); out[i] = v < 0 ? v * 0x8000 : v * 0x7fff; }
    return out;
  }
  function onFrame(e) {
    const f = e.inputBuffer.getChannelData(0); let sum = 0; for (let i = 0; i < f.length; i++) sum += f[i] * f[i];
    const rms = Math.sqrt(sum / f.length); meter = rms; const chunk = pcm16k(f);
    if (V.recording) { TT.net.sendBinary(chunk.buffer); if (V.mode !== 'ptt') { if (rms < Math.max(0.012, floor * 2.5)) { quiet++; if (quiet * f.length / ctx.sampleRate > 0.95) endUtterance(); } else quiet = 0; } if (Date.now() - recStart > 58000) endUtterance(); return; }
    ring.push(chunk); if (ring.length > 5) ring.shift();
    if (V.mode === 'ptt' || TT.paused) return;
    floor = floor * 0.97 + rms * 0.03 * (loud ? 0 : 1);
    const thr = V.playing ? Math.max(0.06, floor * 6) : Math.max(0.018, floor * 3.2);          // harder to trigger while Tim-Tim is talking (echo)
    if (rms > thr) { loud++; if (loud >= (V.playing ? 3 : 2)) { loud = 0; beginUtterance(true); } } else loud = 0;
  }

  function beginUtterance(withPre) {
    if (V.recording || TT.paused) return;
    if (V.playing || !turnDone) V.interrupt();                                                    // barge-in
    V.recording = true; quiet = 0; recStart = Date.now(); TT.net.send({ type: 'audio_start' });
    if (withPre) ring.forEach(c => TT.net.sendBinary(c.buffer)); ring = []; TT.emit('rec', { on: true });
  }
  function endUtterance() {
    if (!V.recording) return; V.recording = false;
    TT.net.send({ type: 'audio_end', ...(V.mode === 'wake' ? { wake: V.wake } : {}) });
    gotResponse = false; turnDone = false; TT.emit('rec', { on: false }); clearTimeout(fillerT); fillerT = setTimeout(() => { if (!gotResponse) V.filler(); }, 1000);
  }
  // Throw the clip away instead of sending it: silence is what makes the speech model invent "thank you".
  function cancelUtterance() {
    if (!V.recording) return; V.recording = false;
    TT.net.send({ type: 'audio_cancel' }); ring = []; quiet = 0; TT.emit('rec', { on: false });
  }
  V.pttStart = async () => {
    if (TT.paused) return false;
    pttHeld = true; const gen = ++pttGen;
    if (!(await V.startMic())) return false;
    // The key may have been released while the microphone was still opening: never start a clip nobody is holding.
    if (gen !== pttGen || !pttHeld) return false;
    if (V.recording) return true;
    beginUtterance(false); return true;
  };
  V.pttStop = () => {
    pttHeld = false; pttGen++;
    if (!V.recording) return;                                   // released before the mic opened: nothing was sent
    if (Date.now() - recStart < MIN_TAP_MS) { cancelUtterance(); TT.emit('toast', 'Hold Space while you speak.'); return; }
    endUtterance();
  };
  V.setMode = async m => { V.mode = m; pttHeld = false; pttGen++; if (m === 'ptt') { if (V.recording) cancelUtterance(); } else await V.startMic(); TT.emit('voicemode', m); };
  V.noteResponse = () => { gotResponse = true; clearTimeout(fillerT); };
  V.turnStarted = () => { turnDone = false; gotResponse = false; };
  V.turnFinished = () => { turnDone = true; checkEnd(); };

  // ───────── playback ─────────
  V.onAudio = async ({ meta, bytes }) => {
    V.noteResponse(); if (!V.speakReplies) return; await audio(); pendingDecode++; V.playing = true;
    try { decoded.set(meta.seq, await ctx.decodeAudioData(bytes.slice(0))); } catch (_) { decoded.set(meta.seq, null); }
    pendingDecode--; drain();
  };
  function drain() {
    while (decoded.has(nextSeq)) {
      const buf = decoded.get(nextSeq); decoded.delete(nextSeq); nextSeq++; if (!buf) continue;
      const s = ctx.createBufferSource(); s.buffer = buf; s.connect(outGain); const t = Math.max(ctx.currentTime + 0.04, nextTime); s.start(t); nextTime = t + buf.duration;
      sources.add(s); s.onended = () => { sources.delete(s); checkEnd(); };
    }
  }
  function checkEnd() { if (sources.size === 0 && pendingDecode === 0 && decoded.size === 0 && turnDone && V.playing) { V.playing = false; nextSeq = 1; nextTime = 0; TT.emit('speech_end'); } }
  V.interrupt = () => {
    sources.forEach(s => { try { s.onended = null; s.stop(); } catch (_) {} }); sources.clear(); decoded.clear(); nextSeq = 1; nextTime = 0; pendingDecode = 0;
    const was = V.playing || !turnDone; V.playing = false; turnDone = true; clearTimeout(fillerT); if (was) TT.net.send({ type: 'interrupt' }); TT.emit('speech_end');
  };
  V.resetPlayback = () => { nextSeq = 1; decoded.clear(); };
  V.level = () => { if (!analyser || !V.playing) return 0; const d = new Uint8Array(analyser.fftSize); analyser.getByteTimeDomainData(d); let s = 0; for (const x of d) { const v = (x - 128) / 128; s += v * v; } return Math.min(1, Math.sqrt(s / d.length) * 3.2); };
  V.micLevel = () => Math.min(1, meter * 9);

  // soft "mm" while thinking, generated locally (costs no provider quota)
  V.filler = async () => { if (!V.speakReplies) return; await audio(); const o = ctx.createOscillator(), lp = ctx.createBiquadFilter(), g = ctx.createGain(), t = ctx.currentTime;
    o.type = 'sine'; o.frequency.setValueAtTime(165, t); o.frequency.linearRampToValueAtTime(190, t + 0.35); lp.type = 'lowpass'; lp.frequency.value = 700;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.07, t + 0.12); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45); o.connect(lp); lp.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + 0.5); };
  V.unlock = () => audio();
})();
