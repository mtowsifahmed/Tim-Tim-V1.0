/* Phone layout: on narrow screens the dashboard becomes a one-screen app with a bottom bar (Chat, Core, Team, World). */
(function () {
  const css = document.createElement('style');
  css.textContent = `
  #mic{touch-action:none;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
  .mnav{display:none}
  @media (max-width:820px){
    html,body{height:100%;overscroll-behavior:none}
    .shell{height:100dvh;padding:6px 6px 64px;gap:6px}
    .bar{padding:6px 8px;gap:6px}.brand strong,.tag,#wifi,#theme-t{display:none}.logo{width:30px;height:30px}
    #conn-t{max-width:34vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chip-btn{padding:6px 9px;font-size:12px}
    .cols{display:block;flex:1;min-height:0;position:relative}
    .col{position:absolute;inset:0;height:100%;overflow:auto}
    body[data-m] .col{display:none !important}
    body[data-m="chat"] .col.right,body[data-m="world"] .col.left{display:flex !important}
    body[data-m="core"] .col.mid,body[data-m="team"] .col.mid{display:flex !important;flex-direction:column}
    body[data-m="core"] .col.mid .studio,body[data-m="team"] .col.mid .core{display:none}
    body[data-m="core"] .core,body[data-m="team"] .studio{flex:1;min-height:0}
    .col.left .heads-card{min-height:220px}
    .sat{width:auto;padding:7px 9px;gap:7px}.sat i,.sat em{display:none}.sat b{font-size:10.5px;letter-spacing:.8px}.sat .ico{width:28px;height:28px}
    .s-mem{left:2%;top:13%}.s-skill{left:2%;top:74%}.s-pers{right:2%;top:13%}.s-set{right:2%;top:74%}
    .links{display:none}
    .core-foot{bottom:10px}.core-foot canvas{width:50px}
    .think-pill{top:8px;padding:5px 12px;font-size:10.5px}
    .composer{margin:8px 8px 10px}.mic{width:46px;height:46px}.mic svg{width:20px;height:20px}
    .as-pane{padding:10px}
    .menu{max-width:92vw}.drawer-panel{width:100%}
    .mnav{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:45;height:58px;padding-bottom:env(safe-area-inset-bottom);background:var(--panel);border-top:1px solid var(--card-b)}
    .mnav button{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;font-size:11px;color:var(--muted)}
    .mnav button svg{width:21px;height:21px}.mnav button.on{color:var(--accent)}
  }`;
  document.head.appendChild(css);
  const nav = document.createElement('nav'); nav.className = 'mnav';
  const item = (m, label, icon) => `<button data-m="${m}"><svg><use href="#i-${icon}"/></svg>${label}</button>`;
  nav.innerHTML = item('chat', 'Chat', 'send') + item('core', 'Core', 'skills') + item('team', 'Team', 'team') + item('world', 'World', 'radar');
  document.body.appendChild(nav);
  const set = m => { document.body.dataset.m = m; nav.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === m)); window.dispatchEvent(new Event('resize')); };
  nav.addEventListener('click', e => { const b = e.target.closest('button'); if (b) set(b.dataset.m); });
  set('chat');
  const mic = document.getElementById('mic'); if (mic) mic.addEventListener('contextmenu', e => e.preventDefault());
})();
