/**
 * Institutional Crypto Intelligence - State Worker (SW)
 * Manages offline dashboard caching, fresh HTML/JSON state fetching,
 * and background sync readiness.
 */
const CACHE_NAME = 'crypto-intel-v4.6';
const ASSETS = ['BTC', 'ETH', 'SOL', 'XRP', 'ONDO', 'SUI', 'SEI', 'HBAR', 'HYPE'];
const STATIC_SHELL = ['./', './index.html'];

self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing State Worker for:', ASSETS.join(', '));
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_SHELL)).catch(() => {})
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activated and managing dashboard cache:', CACHE_NAME);
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((oldKey) => caches.delete(oldKey))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);
    const isDynamicStateOrHtml =
        url.pathname.endsWith('.json') ||
        url.pathname.endsWith('.html') ||
        url.pathname.endsWith('/');

    if (isDynamicStateOrHtml) {
        // Network-first for HTML and ./state/*.json so deployments and feed updates are not stuck on stale cache
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.ok) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    }
                    return networkResponse;
                })
                .catch(() => caches.match(event.request))
        );
        return;
    }

    // Cache-first with network fallback for other static assets
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            return (
                cachedResponse ||
                fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.ok) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    }
                    return networkResponse;
                })
            );
        })
    );
});
