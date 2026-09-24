/* Aira PWA service worker — shell cache only.
   Network-first for pages/APIs so visit/chat data stays fresh.
   Keep the cache list small; never cache authenticated JSON responses. */
const CACHE = "aira-shell-v13";
const SHELL = [
  "/",
  "/static/css/aira.css",
  "/static/css/shell.css",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/shell.js",
  "/static/js/select.js",
  "/static/img/aira-wordmark.png",
  "/static/img/icons/aira-heart.png",
  "/static/img/icons/icon-192.png",
  "/static/img/icons/icon-512.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Never intercept API / mutating visit endpoints — always network.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/admin/") ||
    url.pathname.includes("/transcribe") ||
    url.pathname.includes("/summarize") ||
    url.pathname.includes("/start")
  ) {
    return;
  }

  const isStatic = url.pathname.startsWith("/static/");
  if (isStatic) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetched = fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        }).catch(() => cached);
        return cached || fetched;
      })
    );
    return;
  }

  // HTML navigations: network first, fall back to cached shell/home.
  if (req.mode === "navigate" || (req.headers.get("accept") || "").includes("text/html")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match("/")))
    );
  }
});
