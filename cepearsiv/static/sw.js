var CACHE = "ceparsiv-v1";
var STATIC = [
  "/static/css/app.css",
  "/static/app.js",
  "/static/preview.js",
  "/static/htmx.min.js",
  "/static/fonts/IBMPlexMono-Regular.woff2",
  "/static/fonts/IBMPlexMono-SemiBold.woff2",
  "/static/favicon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(STATIC);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;

  if (STATIC.indexOf(url.pathname) !== -1) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        if (cached) return cached;
        return fetch(event.request).then(function (response) {
          if (response.ok) {
            var copy = response.clone();
            caches.open(CACHE).then(function (cache) { cache.put(event.request, copy); });
          }
          return response;
        });
      })
    );
    return;
  }

  if (url.pathname === "/") {
    event.respondWith(
      fetch(event.request).catch(function () {
        return caches.match("/");
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request).then(function (response) {
      if (response.ok && response.type === "basic") {
        var copy = response.clone();
        caches.open(CACHE).then(function (cache) { cache.put(event.request, copy); });
      }
      return response;
    }).catch(function () {
      return caches.match(event.request);
    })
  );
});
