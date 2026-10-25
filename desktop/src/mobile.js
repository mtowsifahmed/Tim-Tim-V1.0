/* Phone layout: the rail becomes a bottom bar (Chat, Core, Team, World), the section views fill the
   screen one at a time, and the chat box docks above the bar so it is available on every tab. */
(function () {
  const css = document.createElement('style');
  css.textContent = `
  #mic{touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
  .mnav{display:none}
  @media (max-width:820px){
    html,body{height:100%;overscroll-behavior:none}
    .shell{height:100dvh}
    .rail{display:none}
    .bar{height:54px;padding:0 12px;gap:8px}
    .wordmark{font-size:13px;letter-spacing:.18em}.crumb{gap:9px}.crumb b{font-size:10px;letter-spacing:.16em}
    #conn-t{max-width:30vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .chip-btn{height:28px;padding:0 9px;font-size:10.5px}
    .work{display:block;padding:8px 8px 122px;min-height:0;overflow:hidden}
    .views,.dock{height:100%;min-height:0;display:none}
    body[data-m="chat"] .dock{display:flex}
    body[data-m="core"] .views,body[data-m="team"] .views,body[data-m="world"] .views{display:flex}
    .view{overflow:auto;gap:10px;padding-right:0}
    .card{border-radius:14px}
    .core-strip{grid-template-columns:1fr 1fr;gap:7px;padding:0 10px 8px}
    .sat{padding:10px 11px;gap:5px}.sat i{display:none}.sat b{font-size:10px}.sat em{display:none}.sat .ico{width:24px;height:24px}
    .orb-stage{min-height:150px}
    .core-foot{padding:2px 10px 12px;gap:10px}.core-foot canvas{width:52px;height:22px}.pause{padding:0 11px;font-size:9px}
    .think-pill{top:10px;padding:5px 12px;font-size:9.5px;letter-spacing:.18em}
    .card-h{padding:12px 13px 0}
    .studio .tabs{margin-left:0;width:100%;margin-top:8px}.studio .tabs button{flex:1;text-align:center}
    .card-h:has(.tabs){flex-wrap:wrap}
    .stats{gap:6px;padding:0 10px}.stats b{font-size:15px}.stats>div{padding:8px 9px}.stats span{font-size:8px}
    .wm .pills{margin-left:0;order:3;width:100%;margin-top:6px}
    .world-row{grid-template-columns:1fr}
    .as-pane{padding:10px 12px}
    .composer{margin:8px 8px 10px}.mic{width:40px;height:40px}.composer .send{width:36px;height:36px}
    /* docked composer, always available above the tab bar */
    .composer.docked{position:fixed;left:0;right:0;bottom:calc(58px + env(safe-area-inset-bottom));z-index:44;margin:0;padding:8px 10px;
      border-radius:0;border-left:0;border-right:0;border-bottom:0;background:var(--panel);box-shadow:0 -10px 30px -18px var(--shade)}
    .menu{max-width:92vw;min-width:0}.drawer-panel{width:100%}
    .sheet{padding:10px}.sheet-card{max-height:92vh}
    .wm-grid{grid-template-columns:1fr}.globe-wrap{min-height:240px}
    .mnav{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:45;height:58px;padding-bottom:env(safe-area-inset-bottom);
      background:color-mix(in srgb,var(--panel) 96%,transparent);border-top:1px solid var(--line);backdrop-filter:blur(18px)}
    .mnav button{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font-size:10px;letter-spacing:.08em;
      text-transform:uppercase;color:var(--muted);transition:color .2s var(--ease)}
    .mnav button svg{width:20px;height:20px;stroke-width:1.6}
    .mnav button.on{color:var(--accent)}
    .mnav button.on svg{filter:drop-shadow(0 0 8px color-mix(in srgb,var(--accent) 60%,transparent))}
  }`;
  document.head.appendChild(css);
  const nav = document.createElement('nav'); nav.className = 'mnav';
  const item = (m, label, icon) => `<button data-m="${m}"><svg><use href="#i-${icon}"/></svg>${label}</button>`;
  nav.innerHTML = item('chat', 'Chat', 'send') + item('core', 'Core', 'core') + item('team', 'Team', 'team') + item('world', 'World', 'radar');
  document.body.appendChild(nav);
  const TT = window.TT || {};
  const set = m => {
    document.body.dataset.m = m;
    nav.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === m));
    if (m !== 'chat' && TT.focusView) TT.focusView(m);      // the same section the rail selects on desktop
    window.dispatchEvent(new Event('resize'));
  };
  nav.addEventListener('click', e => { const b = e.target.closest('button'); if (b) set(b.dataset.m); });
  // ───── keep the chat box on every tab ─────
  // It lives inside the assistant dock, which the tab bar hides, so on a phone it is moved next to the
  // tab bar as a fixed bar instead of disappearing with the dock.
  const composer = document.getElementById('composer');
  const card = composer && composer.parentElement, after = composer && composer.nextSibling;
  const narrow = () => matchMedia('(max-width:820px)').matches;
  function dock() {
    if (!composer) return;
    if (narrow()) {
      if (composer.parentElement !== document.body) document.body.appendChild(composer);
      composer.classList.add('docked');
    } else {
      if (composer.parentElement !== card) card.insertBefore(composer, after);
      composer.classList.remove('docked');
    }
  }
  dock();
  addEventListener('resize', dock);
  if (window.matchMedia) { try { matchMedia('(max-width:820px)').addEventListener('change', dock); } catch (_) {} }
  // Sending from another tab jumps to Chat, so the reply is visible instead of landing in a hidden pane.
  if (composer) composer.addEventListener('submit', () => { if (!narrow() || document.body.dataset.m === 'chat') return; set('chat'); });
  set('chat');
  const mic = document.getElementById('mic'); if (mic) mic.addEventListener('contextmenu', e => e.preventDefault());
})();
