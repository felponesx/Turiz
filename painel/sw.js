/* Guarda só o próprio app (casca) para abrir rápido e offline; os status vêm sempre da rede. */
const V = "turiz-bots-v1";
const CASCA = ["./", "index.html", "estilo.css", "app.js", "bots.js", "manifest.webmanifest", "icone.svg", "icone-192.png"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(V).then((c) => c.addAll(CASCA)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;           // GitHub e demais: direto na rede
  e.respondWith(caches.open(V).then(async (c) => {
    const guardado = await c.match(e.request);
    const rede = fetch(e.request).then((r) => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => guardado);
    return guardado || rede;                                                          // abre já com o que tem e atualiza por baixo
  }));
});
