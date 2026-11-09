/**
 * Institutional Crypto Intelligence - State Worker (SW)
 * Manages WebSocket feeds, background sync, and offline dashboard state.
 */
const CACHE_NAME = 'crypto-intel-v4.5';
const ASSETS = ['BTC', 'ETH', 'SOL', 'XRP', 'ONDO', 'SUI', 'SEI'];

self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing State Worker...');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activated and managing dashboard cache.');
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
