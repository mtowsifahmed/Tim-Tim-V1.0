/* Tim-Tim service worker: lets the app install and open instantly, and keeps working as a shell when offline.
   Network-first for our own files (so an update reaches everyone on their next open); never touches API or other sites. */
const V = 'timtim-v1';
const CORE = ['./', 'index.html', 'styles.css', 'config.js', 'auth.js', 'globe-data.js', 'lib/qrcode.js', 'net.js', 'voice.js', 'orb.js', 'globe.js', 'map.js', 'studio.js',
  'actions.js', 'panels.js', 'app.js', 'extras.js', 'sources.js', 'websettings.js', 'mobile.js', 'release.js', 'whatsapp.js', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/logo-full.png', 'icons/logo-mark.png', 'privacy.html', 'terms.html'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => Promise.all(CORE.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== self.location.origin) return;
  e.respondWith(fetch(r).then(res => { if (res.ok) { const copy = res.clone(); caches.open(V).then(c => c.put(r, copy)); } return res; })
    .catch(() => caches.match(r).then(m => m || caches.match('index.html'))));
});
