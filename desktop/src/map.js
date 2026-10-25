/* Flat live world map: dotted land (Natural Earth mask), pulsing event markers, wheel/drag/button zoom. */
(function () {
  const L = window.TIMTIM_LAND, land = [];
  if (L) { const bin = atob(L.bits);
    for (let r = 0; r < L.rows; r++) for (let c = 0; c < L.cols; c++) { const i = r * L.cols + c;
      if (bin.charCodeAt(i >> 3) & (1 << (i & 7))) for (let k = 0; k < 1; k++) land.push([-180 + (c + Math.random()) * L.step, 90 - (r + Math.random()) * L.step]); } }
  class WorldMap {
    constructor(canvas, opts = {}) {
      this.cv = canvas; this.ctx = canvas.getContext('2d'); this.color = opts.color || '#2dd4bf'; this.markers = []; this.t = 0;
      this.zoom = 1; this.cx = 10; this.cy = 18; this.drag = null; this.sel = null;
      canvas.addEventListener('wheel', e => { e.preventDefault(); this.zoomBy(e.deltaY < 0 ? 1.2 : 1 / 1.2); }, { passive: false });
      canvas.addEventListener('pointerdown', e => { this.drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener('pointermove', e => { if (this.drag) { const s = this._scale(); this.cx -= (e.clientX - this.drag[0]) / s; this.cy += (e.clientY - this.drag[1]) / s; this.drag = [e.clientX, e.clientY]; this._clamp(); } });
      canvas.addEventListener('pointerup', () => this.drag = null);
      new ResizeObserver(() => this._resize()).observe(canvas.parentElement); this._resize();
      this._last = performance.now(); requestAnimationFrame(t => this._frame(t));
    }
    setColor(c) { this.color = c; }
    setMarkers(list) { this.markers = list.filter(m => isFinite(m.lat) && isFinite(m.lon)).map(m => ({ ...m, ph: Math.random() })); }
    zoomBy(f) { this.zoom = Math.max(1, Math.min(8, this.zoom * f)); this._clamp(); }
    reset() { this.zoom = 1; this.cx = 10; this.cy = 18; }
    _scale() { return (this.w / 360) * this.zoom; }
    _clamp() { const s = this._scale(), hw = this.w / 2 / s, hh = this.h / 2 / s; this.cx = Math.max(-180 + hw, Math.min(180 - hw, this.cx)); this.cy = Math.max(-85 + hh, Math.min(85 - hh, this.cy)); if (hw >= 180) this.cx = 0; }
    _resize() { const r = this.cv.parentElement.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 1.5); if (r.width < 10) return;
      this.w = r.width; this.h = r.height; this.d = d; this.cv.width = r.width * d; this.cv.height = r.height * d; this.cv.style.width = r.width + 'px'; this.cv.style.height = r.height + 'px'; this._clamp(); }
    _frame(now) { this.t += Math.min(0.05, (now - this._last) / 1000); this._last = now; if (this.w) this._draw(); requestAnimationFrame(t => this._frame(t)); }
    _xy(lon, lat) { const s = this._scale(); return [this.w / 2 + (lon - this.cx) * s, this.h / 2 - (lat - this.cy) * s]; }
    _draw() {
      const c = this.ctx, d = this.d, s = this._scale(); c.setTransform(d, 0, 0, d, 0, 0); c.clearRect(0, 0, this.w, this.h);
      c.strokeStyle = this.color + '1f'; c.lineWidth = 1; c.beginPath();                       // graticule
      for (let lon = -180; lon <= 180; lon += 30) { const x = this._xy(lon, 0)[0]; c.moveTo(x, 0); c.lineTo(x, this.h); }
      for (let lat = -60; lat <= 80; lat += 30) { const y = this._xy(0, lat)[1]; c.moveTo(0, y); c.lineTo(this.w, y); } c.stroke();
      c.fillStyle = this.color; const sz = Math.max(1, s * 0.62);
      for (const p of land) { const [x, y] = this._xy(p[0], p[1]); if (x < -3 || y < -3 || x > this.w + 3 || y > this.h + 3) continue; c.globalAlpha = 0.42; c.fillRect(x, y, sz, sz); }
      const sweep = (this.t * 0.18) % 1, sx = this.w * sweep;                                  // radar sweep
      const g = c.createLinearGradient(sx - 60, 0, sx, 0); g.addColorStop(0, this.color + '00'); g.addColorStop(1, this.color + '33'); c.globalAlpha = 1; c.fillStyle = g; c.fillRect(sx - 60, 0, 60, this.h);
      for (const m of this.markers) { const [x, y] = this._xy(m.lon, m.lat); if (x < 0 || y < 0 || x > this.w || y > this.h) continue;
        const ph = (this.t * 0.9 + m.ph) % 1, col = m.color || '#ef4444', sc = (m.size || 1) * (0.8 + this.zoom * 0.12);
        c.strokeStyle = col; c.globalAlpha = (1 - ph) * 0.85; c.lineWidth = 1.3; c.beginPath(); c.arc(x, y, (3 + ph * 13) * sc, 0, 7); c.stroke();
        c.globalAlpha = 1; c.fillStyle = col; c.shadowColor = col; c.shadowBlur = 8; c.beginPath(); c.arc(x, y, 2.6 * sc, 0, 7); c.fill(); c.shadowBlur = 0; }
      c.globalAlpha = 1;
    }
  }
  window.TimMap = WorldMap;
})();
