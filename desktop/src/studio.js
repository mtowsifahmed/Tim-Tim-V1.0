/* Animated isometric "Agent Studio": one desk per sub-agent, a central hub, and live data lines.
   setStatus(id, 'idle' | 'working' | 'done', label) drives the animation (styles in styles.css). */
(function () {
  const POS = [[150, 172], [300, 104], [450, 172], [300, 236]];
  const CHIP = [-66, -66, -66, 62];     // y offset of the label chip (bottom desk puts it below)
  function station(a, x, y, chipY) {
    return `<g class="st st-idle" id="${a.dom}-st-${a.id}" style="--c:${a.color}" transform="translate(${x},${y})">
      <ellipse class="shadow" cx="0" cy="30" rx="58" ry="14"/>
      <polygon class="desk-l" points="-46,0 0,23 0,37 -46,14"/><polygon class="desk-r" points="46,0 0,23 0,37 46,14"/>
      <polygon class="desk-t" points="0,-23 46,0 0,23 -46,0"/>
      <g class="fig"><circle class="head" cx="-24" cy="-37" r="6.5"/><rect class="body" x="-31" y="-30" width="14" height="19" rx="6"/></g>
      <g class="mon"><rect class="scr" x="-6" y="-42" width="34" height="22" rx="3"/><rect class="glow" x="-3" y="-39" width="28" height="16" rx="2"/>
        <path class="scan" d="M0 -33h22M0 -29h14M0 -25h18"/><rect class="stand" x="9" y="-20" width="4" height="7"/></g>
      <g class="ptcs"><circle class="ptc" cx="2" cy="-44" r="1.8" style="animation-delay:0s"/><circle class="ptc" cx="14" cy="-46" r="1.4" style="animation-delay:.7s"/><circle class="ptc" cx="24" cy="-44" r="1.8" style="animation-delay:1.4s"/></g>
      <g class="chip" transform="translate(0,${chipY})"><rect x="-52" y="-15" width="104" height="31" rx="9"/><circle class="chip-dot" cx="-40" cy="0" r="4.5"/>
        <text class="t1" x="-31" y="-2">${a.name}</text><text class="t2" x="-31" y="10" id="${a.dom}-lbl-${a.id}">Idle</text></g>
    </g>`;
  }
  window.TimStudio = function (container, agents, dom) {
    const list = agents.map(a => ({ ...a, dom }));
    const lines = list.map((a, i) => `<path class="flow" id="${dom}-fl-${a.id}" style="--c:${a.color}" d="M300 176 L${POS[i][0]} ${POS[i][1]}"/>`).join('');
    container.innerHTML = `<svg viewBox="40 22 520 312" preserveAspectRatio="xMidYMid meet" class="studio-svg">
      <defs><radialGradient id="${dom}-fg" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="var(--accent)" stop-opacity=".22"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></radialGradient></defs>
      <polygon class="floor" points="300,58 566,190 300,322 34,190"/>
      <polygon fill="url(#${dom}-fg)" points="300,58 566,190 300,322 34,190"/>
      <g class="grid">${[1, 2, 3, 4, 5].map(i => { const f = i / 6, ax = 300 - f * 266, ay = 58 + f * 132, bx = 300 + f * 266;
        return `<path d="M${ax} ${ay} l266 132"/><path d="M${bx} ${ay} l-266 132"/>`; }).join('')}</g>
      ${lines}
      <g class="hub"><circle class="hub-r" cx="300" cy="176" r="20"/><circle class="hub-c" cx="300" cy="176" r="7"/></g>
      ${list.map((a, i) => station(a, POS[i][0], POS[i][1], CHIP[i])).join('')}
    </svg>`;
    return {
      setStatus(id, st, label) {
        const g = container.querySelector(`#${dom}-st-${id}`); if (!g) return;
        g.setAttribute('class', 'st st-' + st);
        container.querySelector(`#${dom}-fl-${id}`).setAttribute('class', 'flow' + (st === 'working' ? ' on' : ''));
        container.querySelector(`#${dom}-lbl-${id}`).textContent = label || ({ idle: 'Idle', working: 'Working…', done: 'Done' })[st];
      },
    };
  };
})();

/* Visual Hub: the orchestrator, the four agents and the skills they may use, with live activity on the edges. */
(function () {
  const SKILLS = ['open_app', 'close_app', 'open_url', 'read_file', 'write_file', 'run_shell'];
  const USES = { research: ['open_url'], coding: ['open_app', 'run_shell', 'read_file', 'write_file'], creative: ['open_app', 'open_url', 'write_file'], planner: ['open_app', 'open_url'] };
  window.TimHub = function (container, agents) {
    const A = [[140, 70], [460, 70], [140, 230], [460, 230]], S = SKILLS.map((s, i) => [300 + (i - 2.5) * 96, i % 2 ? 282 : 18]);
    const edgesAS = agents.map((a, i) => (USES[a.id] || []).map(s => `<line class="edge" id="he-${a.id}-${s}" style="--c:${a.color}" x1="${A[i][0]}" y1="${A[i][1]}" x2="${S[SKILLS.indexOf(s)][0]}" y2="${S[SKILLS.indexOf(s)][1]}"/>`).join('')).join('');
    container.innerHTML = `<svg class="hub-svg studio-svg" viewBox="0 0 600 300" preserveAspectRatio="xMidYMid meet">
      ${edgesAS}
      ${agents.map((a, i) => `<line class="edge" id="hc-${a.id}" style="--c:${a.color}" x1="300" y1="150" x2="${A[i][0]}" y2="${A[i][1]}"/>`).join('')}
      <circle class="hub-r" cx="300" cy="150" r="30" style="transform-origin:300px 150px"/><circle class="node" style="--c:var(--accent)" cx="300" cy="150" r="22"/><text x="300" y="154" text-anchor="middle">Core</text>
      ${agents.map((a, i) => `<g id="hn-${a.id}"><circle class="node" style="--c:${a.color}" cx="${A[i][0]}" cy="${A[i][1]}" r="24"/><text x="${A[i][0]}" y="${A[i][1] + 4}" text-anchor="middle">${a.icon}</text><text x="${A[i][0]}" y="${A[i][1] + 42}" text-anchor="middle">${a.name}</text></g>`).join('')}
      ${SKILLS.map((s, i) => `<g><rect class="node" style="--c:var(--muted)" x="${S[i][0] - 38}" y="${S[i][1] - 10}" width="76" height="20" rx="10"/><text x="${S[i][0]}" y="${S[i][1] + 4}" text-anchor="middle" style="font-size:9.5px">${s}</text></g>`).join('')}
    </svg>`;
    return { setStatus(id, st) { const on = st === 'working'; const c = container.querySelector('#hc-' + id); if (c) c.setAttribute('class', 'edge' + (on ? ' on' : ''));
      (USES[id] || []).forEach(s => { const e = container.querySelector(`#he-${id}-${s}`); if (e) e.setAttribute('class', 'edge' + (on ? ' on' : '')); }); } };
  };
})();
