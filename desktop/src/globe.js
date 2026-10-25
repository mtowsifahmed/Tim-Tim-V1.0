/* Live rotating dotted globe (orthographic, canvas 2D) with pulsing event markers.
   Land comes from globe-data.js (Natural Earth, public domain). Drag to spin. */
(function () {
  const L = window.TIMTIM_LAND;
  const land = [];
  if (L) {
    const bin = atob(L.bits);
    for (let r = 0; r < L.rows; r++) for (let c = 0; c < L.cols; c++) {
      const i = r * L.cols + c;
      if (bin.charCodeAt(i >> 3) & (1 << (i & 7))) {
        for (let k = 0; k < 2; k++) {          // two jittered points per land cell hides the grid
          const lon = (-180 + (c + Math.random()) * L.step) * Math.PI / 180, lat = (90 - (r + Math.random()) * L.step) * Math.PI / 180;
          land.push([Math.cos(lat) * Math.sin(lon), Math.sin(lat), Math.cos(lat) * Math.cos(lon)]);
        }
      }
    }
  }
  const ll = (lat, lon) => { lat *= Math.PI / 180; lon *= Math.PI / 180; return [Math.cos(lat) * Math.sin(lon), Math.sin(lat), Math.cos(lat) * Math.cos(lon)]; };

  class Globe {
    constructor(canvas, opts = {}) {
      this.cv = canvas; this.ctx = canvas.getContext('2d'); this.rot = opts.lon0 || -0.9; this.tilt = 0.35;
      this.color = opts.color || '#3b82f6'; this.accent = opts.accent || '#ef4444'; this.markers = []; this.t = 0;
      this.drag = null; this.speed = opts.speed == null ? 0.12 : opts.speed;
      canvas.addEventListener('pointerdown', e => { this.drag = e.clientX; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener('pointermove', e => { if (this.drag != null) { this.rot += (e.clientX - this.drag) * 0.008; this.drag = e.clientX; } });
      canvas.addEventListener('pointerup', () => this.drag = null);
      new ResizeObserver(() => this._resize()).observe(canvas.parentElement); this._resize();
      this._last = performance.now(); requestAnimationFrame(t => this._frame(t));
    }
    setColors(c, a) { this.color = c; this.accent = a; }
    setMarkers(list) { this.markers = list.filter(m => isFinite(m.lat) && isFinite(m.lon)).map(m => ({ ...m, v: ll(m.lat, m.lon), ph: Math.random() * 6 })); }
    _resize() {
      const r = this.cv.parentElement.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 1.5);
      if (r.width < 10) return; this.w = r.width; this.h = r.height; this.d = d;
      this.cv.width = r.width * d; this.cv.height = r.height * d; this.cv.style.width = r.width + 'px'; this.cv.style.height = r.height + 'px';
    }
    _frame(now) {
      const dt = Math.min(0.05, (now - this._last) / 1000); this._last = now; this.t += dt;
      if (this.drag == null) this.rot += this.speed * dt;
      if (this.w) this._draw(); requestAnimationFrame(t => this._frame(t));
    }
    _proj(v) {
      const c = Math.cos(this.rot), s = Math.sin(this.rot), x = v[0] * c - v[2] * s, z = v[0] * s + v[2] * c;
      const ct = Math.cos(this.tilt), st = Math.sin(this.tilt); return [x, v[1] * ct - z * st, v[1] * st + z * ct];
    }
    _draw() {
      const c = this.ctx, d = this.d, R = Math.min(this.w, this.h) * 0.42, cx = this.w / 2, cy = this.h / 2;
      c.setTransform(d, 0, 0, d, 0, 0); c.clearRect(0, 0, this.w, this.h);
      const g = c.createRadialGradient(cx, cy, R * 0.6, cx, cy, R * 1.3); g.addColorStop(0, this.color + '33'); g.addColorStop(1, this.color + '00');
      c.fillStyle = g; c.fillRect(0, 0, this.w, this.h);                                       // atmosphere
      c.fillStyle = this.color + '14'; c.beginPath(); c.arc(cx, cy, R, 0, 7); c.fill();         // ocean disc
      c.strokeStyle = this.color + '55'; c.lineWidth = 1; c.beginPath(); c.arc(cx, cy, R, 0, 7); c.stroke();
      c.fillStyle = this.color;
      for (const v of land) { const p = this._proj(v); if (p[2] <= 0) continue; c.globalAlpha = 0.25 + 0.75 * p[2]; c.fillRect(cx + p[0] * R, cy - p[1] * R, 1.6, 1.6); }
      c.globalAlpha = 1;
      for (const m of this.markers) {                                                           // pulsing live markers
        const p = this._proj(m.v); if (p[2] <= 0.05) continue; const x = cx + p[0] * R, y = cy - p[1] * R, ph = (this.t * 1.2 + m.ph) % 1;
        const col = m.color || this.accent, sz = (m.size || 1);
        c.strokeStyle = col; c.globalAlpha = (1 - ph) * 0.8 * p[2]; c.lineWidth = 1.2; c.beginPath(); c.arc(x, y, (3 + ph * 11) * sz, 0, 7); c.stroke();
        c.globalAlpha = p[2]; c.fillStyle = col; c.beginPath(); c.arc(x, y, 2.4 * sz, 0, 7); c.fill();
      }
      c.globalAlpha = 1;
    }
  }
  window.TimGlobe = Globe;
})();
