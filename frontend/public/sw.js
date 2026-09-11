const CACHE_NAME = 'synaptix-shell-v4'
const APP_SHELL = ['/', '/index.html', '/manifest.webmanifest', '/favicon.png', '/synaptix-logo.png']

self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return
  const requestUrl = new URL(event.request.url)
  if (requestUrl.origin !== self.location.origin) return
  if (requestUrl.pathname.startsWith('/api')) return

  // Network-first strategy: always fetch the latest files from the server/Vite when online.
  // Only fall back to cache when offline or network drops.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200) {
          const copy = response.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy))
        }
        return response
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/index.html')))
  )
})
