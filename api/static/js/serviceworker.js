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
    '/static/images/icons/android-chrome-384x384.png',
    '/static/images/icons/splash-640x1136.png',
    '/static/images/icons/splash-750x1334.png',
    '/static/images/icons/splash-1334x750.png'
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

// Clear cache on activate
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => (cacheName.startsWith("django-pwa-")))
                    .filter(cacheName => (cacheName !== staticCacheName))
                    .map(cacheName => caches.delete(cacheName))
            );
        })
    );
});

// Serve from Cache
self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
            .catch(() => {
                return caches.match('/offline/');
            })
    )
});
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
