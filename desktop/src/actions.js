/* Desktop automation on the user's computer. The backend only PROPOSES actions. Here we enforce:
   per-skill permission (ask / always / never), a visible confirmation, execution via the Tauri backend, and an action log with undo. */
(function () {
  const TT = window.TT;
  const SKILLS = {
    open_app: { risk: 'low', title: 'Open an app', undo: 'close_app' }, close_app: { risk: 'medium', title: 'Close an app' }, open_url: { risk: 'low', title: 'Open a web page' },
    read_file: { risk: 'medium', title: 'Read a file' }, write_file: { risk: 'high', title: 'Write a file', undo: 'restore' }, run_shell: { risk: 'high', title: 'Run a command' },
    type_text: { risk: 'high', title: 'Type text into the focused window', input: true }, press_key: { risk: 'high', title: 'Press a key or shortcut', input: true }, click: { risk: 'high', title: 'Click on the screen', input: true },
    search_web: { risk: 'low', title: 'Search the web' }, open_path: { risk: 'low', title: 'Open a file or folder' }, list_dir: { risk: 'medium', title: 'List a folder' },
    create_folder: { risk: 'medium', title: 'Create a folder' }, copy_file: { risk: 'high', title: 'Copy a file' }, move_file: { risk: 'high', title: 'Move or rename a file', undo: 'move' },
    delete_file: { risk: 'high', title: 'Move to the Recycle Bin' }, clipboard_read: { risk: 'medium', title: 'Read the clipboard' }, clipboard_write: { risk: 'medium', title: 'Copy text to the clipboard' },
    media_key: { risk: 'low', title: 'Press a media key' }, system_info: { risk: 'low', title: 'Check system info' }, lock_screen: { risk: 'medium', title: 'Lock the computer' },
    set_reminder: { risk: 'low', title: 'Set a reminder', local: true },
    whatsapp_open: { risk: 'low', title: 'Open WhatsApp', local: true }, whatsapp_message: { risk: 'high', title: 'Send a WhatsApp message', local: true },
  };
  // skills that map 1:1 onto a desktop command (name -> picks its arguments)
  const DIRECT = { list_dir: a => ({ path: a.path }), create_folder: a => ({ path: a.path }), open_path: a => ({ path: a.path }), copy_file: a => ({ from: a.from, to: a.to }), move_file: a => ({ from: a.from, to: a.to }),
    delete_file: a => ({ path: a.path }), clipboard_read: () => ({}), clipboard_write: a => ({ text: a.text }), media_key: a => ({ key: a.key, times: a.times || 1 }), system_info: () => ({}), lock_screen: () => ({}) };
  const KEY = 'timtim.skillperms';
  let perms = {}; try { perms = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (_) {}
  const inv = () => window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke;
  const A = TT.actions = { SKILLS, tasks: [], inTauri: () => !!inv() };
  // Reminders are local (nothing on the computer is touched), so they never hold a reply hostage behind a modal.
  A.perm = s => perms[s] || (SKILLS[s] && SKILLS[s].local ? 'always' : 'ask');
  A.setPerm = (s, v) => { perms[s] = v; try { localStorage.setItem(KEY, JSON.stringify(perms)); } catch (_) {} TT.emit('perms'); };

  const $ = s => document.querySelector(s);
  function ask(m) {
    return new Promise(res => {
      const meta = SKILLS[m.skill], argsTxt = Object.entries(m.args).map(([k, v]) => `${k}: ${k === 'content' ? v.slice(0, 300) + (v.length > 300 ? `… (${v.length} characters)` : '') : v}`).join('\n') + (TT.whatsapp && TT.whatsapp.describe ? TT.whatsapp.describe(m) : '');
      $('#cf-title').textContent = meta.title + '?'; $('#cf-desc').textContent = `${(TT.agentName && TT.agentName(m.agent)) || 'Tim-Tim'} wants to do this on your computer (risk: ${meta.risk}).`;
      $('#cf-args').textContent = argsTxt; $('#cf-always-row').hidden = meta.risk === 'high'; $('#cf-always').checked = false; $('#confirm').hidden = false;
      const done = ok => { $('#confirm').hidden = true; if (ok && $('#cf-always').checked) A.setPerm(m.skill, 'always'); $('#cf-allow').onclick = $('#cf-deny').onclick = null; res(ok); };
      $('#cf-allow').onclick = () => done(true); $('#cf-deny').onclick = () => done(false);
    });
  }
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const win = () => { try { return window.__TAURI__.webviewWindow.getCurrentWebviewWindow(); } catch (_) { return null; } };
  // ───────── reminders run inside the app (no computer access needed) ─────────
  const RKEY = 'timtim.reminders'; let reminders = []; try { reminders = JSON.parse(localStorage.getItem(RKEY) || '[]'); } catch (_) {}
  const saveR = () => { try { localStorage.setItem(RKEY, JSON.stringify(reminders)); } catch (_) {} };
  function fire(r) {
    const text = 'Reminder: ' + r.message;
    if (TT.toast) TT.toast(text); if (TT.speakLocal) TT.speakLocal(text);
    try { if (window.Notification && Notification.permission === 'granted') new Notification('Tim-Tim', { body: r.message }); } catch (_) {}
    const t = A.tasks.find(x => x.id === r.id); if (t) { t.status = 'done'; t.output = 'Reminded you.'; TT.emit('task', t); }
    reminders = reminders.filter(x => x.id !== r.id); saveR();
  }
  function schedule(r) { setTimeout(() => fire(r), Math.max(0, r.due - Date.now())); }
  A.reminders = () => reminders.slice();
  function addReminder(id, minutes, message) {
    const r = { id, message, due: Date.now() + minutes * 60000 }; reminders.push(r); saveR(); schedule(r);
    try { if (window.Notification && Notification.permission === 'default') Notification.requestPermission(); } catch (_) {}
    return `I'll remind you in ${minutes} minute${minutes === 1 ? '' : 's'}: ${message}`;
  }
  reminders.forEach(r => { if (!A.tasks.find(x => x.id === r.id)) A.tasks.push({ id: r.id, skill: 'set_reminder', args: { minutes: Math.max(1, Math.round((r.due - Date.now()) / 60000)), message: r.message }, agent: 'planner', status: 'done', output: 'Reminder pending', at: Date.now() }); schedule(r); });

  async function exec(skill, args, taskId) {
    if (skill === 'whatsapp_open' || skill === 'whatsapp_message') return TT.whatsapp ? TT.whatsapp.run(skill, args) : { ok: false, error: 'The WhatsApp helper did not load.' };
    if (skill === 'set_reminder') return { ok: true, output: addReminder(taskId, args.minutes, args.message), scheduled: true };
    if (skill === 'search_web') { const url = 'https://duckduckgo.com/?q=' + encodeURIComponent(args.query); return exec('open_url', { url }); }
    const call = inv();
    if (call && SKILLS[skill] && SKILLS[skill].input) {          // keyboard/mouse skills act on the OTHER window: step aside first, then come back
      const w = win();
      try { if (w) { await w.minimize(); await sleep(900); } else { await sleep(3500); } } catch (_) { await sleep(3500); }
      let r;
      try { r = { ok: true, output: await call(skill, skill === 'type_text' ? { text: args.text } : skill === 'press_key' ? { key: args.key } : { x: args.x, y: args.y }) }; } catch (e) { r = { ok: false, error: String(e) }; }
      try { if (w) { await sleep(500); await w.unminimize(); await w.setFocus(); } } catch (_) {}
      return r;
    }
    if (call && DIRECT[skill]) {
      try { const out = await call(skill, DIRECT[skill](args)); return { ok: true, output: out }; } catch (e) { return { ok: false, error: String(e) }; }
    }
    if (!call) {                                              // browser preview: only opening a page is possible
      if (skill === 'open_url') { window.open(args.url, '_blank', 'noopener'); return { ok: true, output: 'Opened in the browser.' }; }
      return { ok: false, error: 'Computer actions need the Tim-Tim desktop app (not the browser preview).' };
    }
    try {
      if (skill === 'open_app') return { ok: true, output: await call('open_app', { name: args.app }) };
      if (skill === 'close_app') return { ok: true, output: await call('close_app', { name: args.app }) };
      if (skill === 'open_url') return { ok: true, output: await call('open_url', { url: args.url }) };
      if (skill === 'run_shell') return { ok: true, output: await call('run_shell', { command: args.command }) };
      if (skill === 'read_file') return { ok: true, output: await call('read_file', { path: args.path }) };
      if (skill === 'write_file') { let backup = null; try { backup = await call('read_file', { path: args.path }); } catch (_) {} return { ok: true, output: await call('write_file', { path: args.path, content: args.content }), backup }; }
    } catch (e) { return { ok: false, error: String(e) }; }
    return { ok: false, error: 'unknown skill' };
  }

  A.handle = async m => {
    const meta = SKILLS[m.skill]; if (!meta) { TT.net.send({ type: 'action_result', id: m.id, error: 'unknown skill' }); return; }
    const task = { id: m.id, skill: m.skill, args: m.args, agent: m.agent, status: 'asking', at: Date.now() }; A.tasks.unshift(task); TT.emit('task', task);
    const p = A.perm(m.skill); let ok;
    if (p === 'never') ok = false; else if (p === 'always' && meta.risk !== 'high') ok = true; else ok = await ask(m);
    if (!ok) { task.status = 'denied'; TT.emit('task', task); TT.net.send({ type: 'action_result', id: m.id, denied: true }); return; }
    task.status = 'running'; TT.emit('task', task);
    const r = await exec(m.skill, m.args, m.id);
    task.status = r.ok ? 'done' : 'failed'; task.output = r.ok ? r.output : r.error; if (r.ok && m.skill === 'write_file') task.backup = r.backup === undefined ? null : r.backup; TT.emit('task', task);
    TT.net.send({ type: 'action_result', id: m.id, ...(r.ok ? { ok: true, output: String(r.output || '').slice(0, 4000) } : { error: String(r.error).slice(0, 500) }) });
  };

  A.undo = async task => {
    const call = inv(); if (!call) return false;
    try {
      if (task.skill === 'open_app') await call('close_app', { name: task.args.app });
      else if (task.skill === 'write_file') await call('restore_file', { path: task.args.path, backup: task.backup });
      else if (task.skill === 'move_file') await call('move_file', { from: task.args.to, to: task.args.from });
      else return false;
      task.status = 'undone'; TT.emit('task', task); return true;
    } catch (e) { task.output = String(e); TT.emit('task', task); return false; }
  };
  A.canUndo = t => t.status === 'done' && inv() && (t.skill === 'open_app' || t.skill === 'write_file' || t.skill === 'move_file');
  TT.on('action_request', A.handle);
})();
