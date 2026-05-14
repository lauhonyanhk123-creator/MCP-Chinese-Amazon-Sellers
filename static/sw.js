const CACHE_NAME = 'cross-border-seller-v1';
const STATIC_CACHE = 'static-assets-v1';
const API_CACHE = 'api-cache-v1';
const OFFLINE_URL = '/offline';

const STATIC_ASSETS = [
  '/',
  '/offline',
  '/static/css/sparkline.css',
  '/static/js/sparkline.js',
  '/static/js/analytics.js',
  '/static/js/charts-init.js'
];

const API_CACHE_DURATION = 5 * 60 * 1000;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
  } else if (request.mode === 'navigate') {
    event.respondWith(handleNavigationRequest(request));
  } else {
    event.respondWith(handleStaticRequest(request));
  }
});

async function handleApiRequest(request) {
  const cache = await caches.open(API_CACHE);

  if (request.method === 'GET') {
    try {
      const networkResponse = await fetch(request);

      if (networkResponse.ok) {
        const responseClone = networkResponse.clone();
        const cacheEntry = {
          data: responseClone.clone(),
          timestamp: Date.now()
        };
        await cache.put(request, new Response(await networkResponse.clone().text(), {
          headers: networkResponse.headers
        }));
      }

      return networkResponse;
    } catch (error) {
      const cachedResponse = await cache.match(request);
      if (cachedResponse) {
        return cachedResponse;
      }
      return new Response(JSON.stringify({ error: 'Offline', cached: false }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }

  try {
    return await fetch(request);
  } catch (error) {
    return new Response(JSON.stringify({ error: 'Offline', success: false }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function handleNavigationRequest(request) {
  try {
    const networkResponse = await fetch(request);
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    try {
      const offlinePage = await caches.match(OFFLINE_URL);
      if (offlinePage) {
        return offlinePage;
      }
    } catch (e) {
    }

    return caches.match('/offline') || new Response('Offline', { status: 503 });
  }
}

async function handleStaticRequest(request) {
  const cachedResponse = await caches.match(request);

  if (cachedResponse) {
    fetch(request)
      .then((networkResponse) => {
        if (networkResponse.ok) {
          caches.open(STATIC_CACHE)
            .then((cache) => cache.put(request, networkResponse));
        }
      })
      .catch(() => {});

    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    if (request.destination === 'image') {
      return new Response('', { status: 404 });
    }
    throw error;
  }
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'GET_CACHED_DATA') {
    getCachedData().then((data) => {
      event.ports[0].postMessage(data);
    });
  }
});

async function getCachedData() {
  const cache = await caches.open(API_CACHE);
  const requests = await cache.keys();
  const cachedData = [];

  for (const request of requests) {
    if (request.url.includes('/api/')) {
      try {
        const response = await cache.match(request);
        if (response) {
          const data = await response.text();
          cachedData.push({
            url: request.url,
            data: data,
            timestamp: Date.now()
          });
        }
      } catch (e) {
      }
    }
  }

  return cachedData;
}
