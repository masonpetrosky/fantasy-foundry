/* Fantasy Foundry – offline-fallback service worker */

const CACHE_NAME = "ff-shell-v1";
const SHELL_ASSETS = ["/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only handle GET navigation and same-origin requests
  if (request.method !== "GET") return;

  // API requests: network-only (don't cache API responses)
  if (new URL(request.url).pathname.startsWith("/api/")) return;

  // Static assets (JS, CSS, images): cache-first
  if (
    request.destination === "script" ||
    request.destination === "style" ||
    request.destination === "image" ||
    request.destination === "font"
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      }),
    );
    return;
  }

  // Navigation requests: network-first with 3s timeout fallback to cached shell
  if (request.mode === "navigate") {
    event.respondWith(
      Promise.race([
        fetch(request),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("nav timeout")), 3000),
        ),
      ]).catch(() => caches.match("/")),
    );
    return;
  }
});
