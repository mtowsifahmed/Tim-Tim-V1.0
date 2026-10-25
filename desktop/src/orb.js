/* Tim-Tim particle orb: a human-shaped cloud of particles (male or female) that reacts to
   idle / listening / thinking / speaking. Plain canvas 2D, classic script (no bundler needed). */
(function () {
  const W = 300, H = 600;            // figure design space
  const BUCKETS = 10;

  function drawSilhouette(ctx, figure) {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = ctx.strokeStyle = '#fff';
    ctx.lineCap = ctx.lineJoin = 'round';
    const limb = (w, pts) => { ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(...pts[0]); ctx.quadraticCurveTo(...pts[1], ...pts[2]); ctx.stroke(); };
    ctx.beginPath(); ctx.ellipse(150, 62, 33, 40, 0, 0, Math.PI * 2); ctx.fill();   // head
    ctx.fillRect(138, 96, 24, 32);                                                  // neck
    if (figure === 'female') {
      ctx.beginPath();                                                              // flowing hair
      ctx.moveTo(110, 70); ctx.quadraticCurveTo(88, 170, 104, 262); ctx.lineTo(128, 170);
      ctx.lineTo(150, 110); ctx.lineTo(172, 170); ctx.lineTo(196, 262);
      ctx.quadraticCurveTo(212, 170, 190, 70); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.ellipse(150, 64, 42, 46, 0, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath();                                                              // torso: narrow shoulders, waist, hips
      ctx.moveTo(106, 144); ctx.quadraticCurveTo(150, 128, 194, 144);
      ctx.lineTo(180, 246); ctx.quadraticCurveTo(178, 292, 210, 342);
      ctx.lineTo(90, 342); ctx.quadraticCurveTo(122, 292, 120, 246); ctx.closePath(); ctx.fill();
      limb(17, [[104, 154], [80, 250], [70, 342]]); limb(17, [[196, 154], [220, 250], [230, 342]]);
      limb(34, [[127, 336], [129, 452], [131, 574]]); limb(34, [[173, 336], [171, 452], [169, 574]]);
    } else {
      ctx.beginPath();                                                              // torso: broad shoulders, straight waist
      ctx.moveTo(88, 142); ctx.quadraticCurveTo(150, 116, 212, 142);
      ctx.lineTo(198, 302); ctx.quadraticCurveTo(150, 314, 102, 302); ctx.closePath(); ctx.fill();
      limb(26, [[88, 152], [64, 262], [56, 366]]); limb(26, [[212, 152], [236, 262], [244, 366]]);
      limb(44, [[128, 300], [122, 440], [120, 574]]); limb(44, [[172, 300], [178, 440], [180, 574]]);
    }
  }

  function sampleTargets(figure) {
    const off = document.createElement('canvas'); off.width = W; off.height = H;
    const c = off.getContext('2d', { willReadFrequently: true });
    drawSilhouette(c, figure);
    const data = c.getImageData(0, 0, W, H).data, pts = [];
    for (let y = 0; y < H; y += 2) for (let x = 0; x < W; x += 2) if (data[(y * W + x) * 4 + 3] > 128) pts.push([x, y]);
    return pts;
  }

  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const lerp = (a, b, t) => a + (b - a) * t;
  const STATE_COLORS = {            // matches the concept art: idle blue, listening green, thinking purple, speaking red
    idle: ['#2f6bff', '#22d3ee'], listening: ['#10b981', '#67e8f9'],
    thinking: ['#8b5cf6', '#d946ef'], speaking: ['#ef4444', '#fb923c'],
  };

  class Orb {
    constructor(canvas, opts = {}) {
      this.cv = canvas; this.ctx = canvas.getContext('2d');
      this.count = opts.count || 3200; this.halo = opts.halo || 260;
      this.figure = opts.figure || 'sphere';
      this.custom = [hex(opts.color1 || '#7c5cff'), hex(opts.color2 || '#22d3ee')];
      this.mode = opts.colorMode || 'accent'; this.accent = [hex('#ef4444'), hex('#ff7a59')];
      this.cur = [hex('#2f6bff'), hex('#22d3ee')];
      this.state = 'idle'; this.level = 0; this.t = 0; this.mouse = null; this.R = 105;
      this.ps = []; this.hs = [];
      for (let i = 0; i < this.count; i++) {      // Fibonacci sphere unit vectors, used by sphere mode
        const y = 1 - 2 * (i + .5) / this.count, r = Math.sqrt(1 - y * y), a = i * 2.399963;
        this.ps.push({ x: 150, y: 150, vx: 0, vy: 0, tx: 150, ty: 150, z: 0, ux: Math.cos(a) * r, uy: y, uz: Math.sin(a) * r,
          rf: Math.random() < 0.82 ? 0.985 + Math.random() * 0.03 : 0.25 + Math.random() * 0.7, s: 0.9 + Math.random() * 1.3, b: (Math.random() * BUCKETS) | 0, ph: Math.random() * 6.28 });
      }
      this.nodes = this.ps.filter((_, i) => i % 22 === 0).slice(0, 150);      // network nodes + nearest-neighbour links
      this.links = [];
      this.nodes.forEach((a, i) => {
        const d = this.nodes.map((b, j) => [j, (a.ux - b.ux) ** 2 + (a.uy - b.uy) ** 2 + (a.uz - b.uz) ** 2]).filter(q => q[0] !== i).sort((p, q) => p[1] - q[1]).slice(0, 2);
        d.forEach(q => { if (!this.links.some(l => (l[0] === i && l[1] === q[0]) || (l[1] === i && l[0] === q[0]))) this.links.push([i, q[0]]); });
      });
      for (let i = 0; i < this.halo; i++) this.hs.push({ a: Math.random() * 6.28, ring: i % 3, rr: 0.97 + Math.random() * 0.06, sp: 0.2 + Math.random() * 0.4, s: 0.9 + Math.random() * 1.3, b: (Math.random() * BUCKETS) | 0 });
      this.setFigure(this.figure);
      new ResizeObserver(() => this._resize()).observe(canvas.parentElement);
      canvas.addEventListener('pointermove', e => { const r = canvas.getBoundingClientRect(); this.mouse = [(e.clientX - r.left - this.ox) / this.sc, (e.clientY - r.top - this.oy) / this.sc]; });
      canvas.addEventListener('pointerleave', () => this.mouse = null);
      this._last = performance.now(); this._raf = requestAnimationFrame(t => this._frame(t));
    }
    get sphere() { return this.figure === 'sphere'; }
    setFigure(f) {
      this.figure = f;
      if (f === 'sphere') { this.dw = 300; this.dh = 300; this.cx = 150; this.cy = 150; }
      else {
        this.dw = W; this.dh = H; this.cx = 150; this.cy = 300;
        const pts = sampleTargets(f);
        for (const p of this.ps) {
          const q = pts[(Math.random() * pts.length) | 0]; p.tx = q[0] + (Math.random() - .5) * 2; p.ty = q[1] + (Math.random() - .5) * 2;
          p.hb = Math.max(0, Math.min(BUCKETS - 1, Math.round(q[1] / H * (BUCKETS - 1) + (Math.random() - .5) * 4)));
        }
      }
      for (const p of this.ps) p.b = this.sphere ? Math.max(0, Math.min(BUCKETS - 1, Math.round((p.uy + 1) / 2 * (BUCKETS - 1) + (Math.random() - .5) * 3))) : p.hb;
      this.ps.sort((a, b) => a.b - b.b);
      if (this.cv.parentElement) this._resize();
    }
    setColors(a, b) { this.custom = [hex(a), hex(b)]; }
    setColorMode(m) { this.mode = m; }
    setAccent(a, b) { this.accent = [hex(a), hex(b)]; }
    setState(s) { this.state = s; }
    setLight(v) { this.light = !!v; }
    setLevel(v) { this.level = Math.max(0, Math.min(1, v)); }
    destroy() { cancelAnimationFrame(this._raf); }
    _target() { return this.mode === 'state' ? STATE_COLORS[this.state].map(hex) : this.mode === 'accent' ? this.accent : this.custom; }
    _resize() {
      const r = this.cv.parentElement.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      if (r.width < 10 || r.height < 10) return;
      this.cv.width = r.width * dpr; this.cv.height = r.height * dpr;
      this.cv.style.width = r.width + 'px'; this.cv.style.height = r.height + 'px';
      this.dpr = dpr; this.sc = Math.min(r.width / (this.dw + 90), r.height / (this.dh + 50));
      this.ox = (r.width - this.dw * this.sc) / 2; this.oy = (r.height - this.dh * this.sc) / 2;
    }
    _frame(now) {
      const dt = Math.min(0.05, (now - this._last) / 1000); this._last = now; this.t += dt;
      const tg = this._target(), k = Math.min(1, dt * 4);                 // smooth color transitions between states
      for (let i = 0; i < 2; i++) for (let j = 0; j < 3; j++) this.cur[i][j] = lerp(this.cur[i][j], tg[i][j], k);
      this.pal = Array.from({ length: BUCKETS }, (_, i) => { const t = i / (BUCKETS - 1); return `rgb(${[0, 1, 2].map(j => Math.round(lerp(this.cur[0][j], this.cur[1][j], t))).join(',')})`; });
      if (this.sc) { this._step(dt); this._draw(); }
      this._raf = requestAnimationFrame(t => this._frame(t));
    }
    _rot(p, yaw, tilt) {
      const c = Math.cos(yaw), s = Math.sin(yaw), x = p.ux * c + p.uz * s, z = -p.ux * s + p.uz * c;
      const ct = Math.cos(tilt), st = Math.sin(tilt); return [x, p.uy * ct - z * st, p.uy * st + z * ct];
    }
    _step(dt) {
      const t = this.t, st = this.state, lv = this.level, cx = this.cx, cy = this.cy;
      if (this.sphere) {
        const spin = st === 'thinking' ? 1.3 : st === 'listening' ? 0.18 : st === 'speaking' ? 0.5 : 0.22;
        this.yaw = (this.yaw || 0) + spin * dt; const tilt = 0.38;
        let scale = 1 + Math.sin(t * 1.4) * 0.018;
        if (st === 'speaking') scale = 1 + lv * 0.13 + Math.sin(t * 11) * 0.012 * lv;
        for (const p of this.ps) {
          const [x, y, z] = this._rot(p, this.yaw, tilt); let rr = this.R * p.rf * scale;
          if (st === 'listening') rr *= 1 + Math.sin(p.uy * 6 - t * 4.5) * 0.045;
          if (st === 'thinking') rr *= 1 + Math.sin(p.ph + t * 5) * 0.03;
          const tx = cx + x * rr, ty = cy + y * rr; p.z = z;
          p.vx += (tx - p.x) * 0.16; p.vy += (ty - p.y) * 0.16;
          if (this.mouse) { const mx = p.x - this.mouse[0], my = p.y - this.mouse[1], md = Math.hypot(mx, my); if (md < 45) { const f = (45 - md) / 45 * 3; p.vx += mx / (md + 1) * f; p.vy += my / (md + 1) * f; } }
          p.vx *= 0.72; p.vy *= 0.72; p.x += p.vx; p.y += p.vy;
        }
        for (const h of this.hs) h.a += h.sp * dt * (st === 'thinking' ? 3 : 1) * 1.4;
        return;
      }
      const k = 0.07, damp = Math.pow(0.0009, dt);
      for (const p of this.ps) {
        let tx = p.tx, ty = p.ty; const dx = tx - cx, dy = ty - cy, d = Math.hypot(dx, dy) + 1; p.z = 0;
        if (st === 'idle') { ty += Math.sin(t * 1.3) * 1.6 * (dy / 300); tx += Math.sin(t * 0.7 + p.ph) * 0.8; ty += Math.cos(t * 0.6 + p.ph) * 0.8; }
        else if (st === 'listening') { const w = Math.sin(d * 0.045 - t * 4.2) * 5; tx += dx / d * w; ty += dy / d * w; }
        else if (st === 'thinking') { const a = t * 1.8 + p.ph * 0.3, r = 7 + Math.sin(t * 2 + p.ph) * 3; tx += Math.cos(a) * r; ty += Math.sin(a) * r; }
        else if (st === 'speaking') { const s = 1 + lv * 0.07 + Math.sin(t * 9 + p.ph) * 0.06 * lv; tx = cx + dx * s + (Math.random() - .5) * lv * 5; ty = cy + dy * s + (Math.random() - .5) * lv * 5; }
        p.vx += (tx - p.x) * k; p.vy += (ty - p.y) * k;
        if (this.mouse) { const mx = p.x - this.mouse[0], my = p.y - this.mouse[1], md = Math.hypot(mx, my); if (md < 55) { const f = (55 - md) / 55 * 4; p.vx += mx / (md + 1) * f; p.vy += my / (md + 1) * f; } }
        p.vx *= damp; p.vy *= damp; p.x += p.vx; p.y += p.vy;
      }
      const spin = st === 'thinking' ? 1.6 : st === 'speaking' ? 0.6 + lv : 0.3;
      for (const h of this.hs) h.a += h.sp * spin * dt * 2;
    }
    _draw() {
      const c = this.ctx, k = this.sc * this.dpr, cx = this.cx, cy = this.cy, sph = this.sphere;
      c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.cv.width, this.cv.height);
      c.setTransform(k, 0, 0, k, this.ox * this.dpr, this.oy * this.dpr);
      const [r, g, b] = this.cur[0].map(Math.round), lv = this.level, st = this.state;
      const ga = 0.14 + (st === 'speaking' ? lv * 0.22 : st === 'listening' ? 0.07 : 0);
      const rad = sph ? 190 : 260, gy = sph ? cy : 250, gr = c.createRadialGradient(cx, gy, 8, cx, gy, rad);
      gr.addColorStop(0, `rgba(${r},${g},${b},${ga})`); gr.addColorStop(1, `rgba(${r},${g},${b},0)`);
      c.fillStyle = gr; c.fillRect(-150, -100, this.dw + 300, this.dh + 200);
      c.globalCompositeOperation = this.light ? 'source-over' : 'lighter';
      if (sph) {                                                                  // glowing core
        const core = c.createRadialGradient(cx, cy, 0, cx, cy, 70 + lv * 25), [r2, g2, b2] = this.cur[1].map(Math.round);
        core.addColorStop(0, 'rgba(255,255,255,.95)'); core.addColorStop(.25, `rgba(${r2},${g2},${b2},.55)`); core.addColorStop(1, `rgba(${r},${g},${b},0)`);
        c.fillStyle = core; c.fillRect(cx - 120, cy - 120, 240, 240);
        c.globalAlpha = 0.5; c.strokeStyle = this.pal[BUCKETS >> 1]; c.lineWidth = 0.7; c.beginPath();      // neural links
        const pr = this.nodes.map(n => this._rot(n, this.yaw || 0, 0.38));
        for (const [i, j] of this.links) { const a = pr[i], d = pr[j]; if (a[2] < -0.3 && d[2] < -0.3) continue;
          c.moveTo(cx + a[0] * this.R * 1.02, cy + a[1] * this.R * 1.02); c.lineTo(cx + d[0] * this.R * 1.02, cy + d[1] * this.R * 1.02); }
        c.stroke(); c.globalAlpha = 0.95; c.fillStyle = this.pal[BUCKETS - 2];
        for (const a of pr) if (a[2] > -0.2) { c.beginPath(); c.arc(cx + a[0] * this.R * 1.02, cy + a[1] * this.R * 1.02, 1.5 + (a[2] + 1) * 0.7, 0, 7); c.fill(); }
      }
      c.globalAlpha = 0.4; let bi = -1;                                            // halo / orbit rings
      for (const h of this.hs) {
        if (h.b !== bi) { bi = h.b; c.fillStyle = this.pal[bi]; }
        let x, y;
        if (sph) { const tl = [0.35, -0.6, 1.2][h.ring], rx = 150 * h.rr, ry = [48, 62, 40][h.ring] * h.rr, ex = Math.cos(h.a) * rx, ey = Math.sin(h.a) * ry;
          x = cx + ex * Math.cos(tl) - ey * Math.sin(tl); y = cy + ex * Math.sin(tl) + ey * Math.cos(tl); }
        else { x = 150 + Math.cos(h.a) * 170 * h.rr; y = 300 + Math.sin(h.a) * 330 * h.rr; }
        c.fillRect(x, y, h.s, h.s);
      }
      c.globalAlpha = 0.92; bi = -1;
      for (const p of this.ps) {
        if (p.b !== bi) { bi = p.b; c.fillStyle = this.pal[bi]; }
        const sz = sph ? p.s * (0.5 + 0.7 * (p.z + 1) / 2) : p.s; c.fillRect(p.x, p.y, sz, sz);
      }
      c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
    }
  }
  window.TimOrb = Orb; window.TIM_STATE_COLORS = STATE_COLORS;
})();
