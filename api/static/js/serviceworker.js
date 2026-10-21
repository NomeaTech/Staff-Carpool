// Base Service Worker implementation.  To use your own Service Worker, set the PWA_SERVICE_WORKER_PATH variable in settings.py

var staticCacheName = "django-pwa-v" + new Date().getTime();
// Files that are available offline. Every file must exist: see the install
// handler below for what happens otherwise.
var filesToCache = [
    '/offline/',
    '/static/css/django-pwa-app.css',
    '/static/images/icons/favicon.ico',
    '/static/images/icons/favicon-16x16.png',
    '/static/images/icons/favicon-32x32.png',
    '/static/images/icons/apple-touch-icon.png',
    '/static/images/icons/android-chrome-192x192.png',
    '/static/images/icons/android-chrome-384x384.png'
];

// Cache on install. Each file is cached on its own: with cache.addAll() one
// missing file failed the whole install, so the service worker never ran.
self.addEventListener("install", event => {
    this.skipWaiting();
    event.waitUntil(
        caches.open(staticCacheName)
            .then(cache => Promise.allSettled(filesToCache.map(file => cache.add(file))))
            .then(results => {
                results
                    .filter(result => result.status === "rejected")
                    .forEach(result => console.warn("Service worker could not cache a file:", result.reason));
            })
    )
});

// Static files the app has loaded: CSS, scripts, fonts, images
var RUNTIME_CACHE = "kyyti-static-v1";

// Clear cache on activate, and start loading pages while the service worker
// starts up (navigation preload)
self.addEventListener('activate', event => {
    event.waitUntil(Promise.all([
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => (cacheName.startsWith("django-pwa-")))
                    .filter(cacheName => (cacheName !== staticCacheName))
                    .map(cacheName => caches.delete(cacheName))
            );
        }),
        self.registration.navigationPreload ? self.registration.navigationPreload.enable() : null,
        self.clients.claim(),
    ]));
});

// - Pages are always loaded from the network, so their data is up to date
//   (the offline page when there is no connection).
// - Static files are shown at once from the device and refreshed in the
//   background. The app's scripts have the release in their URLs (?v=,
//   see STATIC_VERSION in settings), so a new release loads them anew.
// - Anything else (fetches, form posts) goes to the network as it is.
self.addEventListener("fetch", event => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== "GET") {
        return;
    }
    if (request.mode === "navigate") {
        event.respondWith((async () => {
            try {
                return (await event.preloadResponse) || await fetch(request);
            } catch {
                return (await caches.match("/offline/")) || Response.error();
            }
        })());
        return;
    }
    if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
        event.respondWith(staleWhileRevalidate(event));
    }
});

async function staleWhileRevalidate(event) {
    const request = event.request;
    const cache = await caches.open(RUNTIME_CACHE);
    const cached = await caches.match(request);
    const refresh = fetch(request).then(async response => {
        if (response.ok && response.type === "basic") {
            await cache.put(request, response.clone());
            await forgetOtherVersions(cache, request.url);
        }
        return response;
    });
    if (cached) {
        // Refreshed after the response, without holding it up
        event.waitUntil(refresh.catch(() => {}));
        return cached;
    }
    return refresh;
}

// Removes the copies of the same file with another ?v= (an older release)
async function forgetOtherVersions(cache, url) {
    const kept = new URL(url);
    for (const request of await cache.keys()) {
        const other = new URL(request.url);
        if (other.pathname === kept.pathname && other.search !== kept.search) {
            await cache.delete(request);
        }
    }
}
// Push notifications (notifications/push.py). The payload is a notification
// (Notification.as_payload) with its icon. It is always shown, even while
// the app is open (Safari stops push notifications for sites that receive
// them without showing them); open windows are told too, so they update
// the bell and do not also show it as a pop-up (static/js/notifications.js).
self.addEventListener("push", event => {
    let notification;
    try {
        notification = event.data.json();
    } catch {
        notification = { title: "LUT Kyyti", message: event.data ? event.data.text() : "", url: "/app/notifications/" };
    }
    event.waitUntil((async () => {
        await self.registration.showNotification(notification.title, {
            body: notification.message,
            icon: notification.icon,
            badge: notification.badge,
            tag: notification.id,
            data: { url: notification.url },
        });
        const windows = await clients.matchAll({ type: "window", includeUncontrolled: true });
        for (const client of windows) {
            client.postMessage({ type: "kyyti-notification", notification });
        }
    })());
});

// Tapping a notification opens its page, in an open window of the app if
// there is one
self.addEventListener("notificationclick", event => {
    event.notification.close();
    const url = new URL(event.notification.data?.url || "/app/notifications/", self.location.origin).href;
    event.waitUntil((async () => {
        const windows = await clients.matchAll({ type: "window", includeUncontrolled: true });
        for (const client of windows) {
            if (new URL(client.url).origin === self.location.origin && "focus" in client) {
                await client.focus();
                return client.navigate ? client.navigate(url) : undefined;
            }
        }
        return clients.openWindow(url);
    })());
});
