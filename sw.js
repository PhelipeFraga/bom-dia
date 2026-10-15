// Deixa o app abrir sem internet:
// - páginas do próprio app: busca na rede e guarda a última versão;
// - dados do robô (GitHub): rede primeiro, cópia guardada se estiver offline;
// - ícones, letras e biblioteca do mapa (CDNs): guardados na primeira vez e reaproveitados.
const CACHE = "bom-dia-v18";
const SHELL = ["./", "index.html", "arte.js", "manifest.json", "icon.svg"];
const FIXOS = /cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|fonts\.googleapis\.com|fonts\.gstatic\.com/;
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  // dados do robô vêm com "?t=hora" para furar o cache do GitHub; guarda sempre na mesma chave, sem o "?t="
  const chave = url.host === "raw.githubusercontent.com" ? url.origin + url.pathname : e.request;
  const guarda = r => { if (r && (r.ok || r.type === "opaque")) { const c = r.clone(); caches.open(CACHE).then(x => x.put(chave, c)); } return r; };
  if (FIXOS.test(url.host)) {
    e.respondWith(caches.match(e.request).then(c => c || fetch(e.request).then(guarda)));
  } else if (url.origin === location.origin || url.host === "raw.githubusercontent.com") {
    e.respondWith(fetch(e.request).then(guarda).catch(() => caches.match(chave, { ignoreSearch: true })));
  }
});
