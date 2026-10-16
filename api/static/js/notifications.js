// Notifications: the bell's menu, the unread counts, and pop-ups for
// notifications as they arrive (notifications/views.py).
//
// While the app is open, it asks the server for new notifications every
// POLL_INTERVAL (and when the tab is shown again), and shows each one as a
// pop-up. On devices with push notifications on (static/js/push.js), the
// service worker shows them as system notifications and tells this page, so
// they are not shown again as pop-ups.
(function () {
    const root = document.querySelector("[data-notifications]");
    if (!root) {
        return;
    }
    const menu = root.querySelector("[data-notifications-menu]");
    const toasts = document.getElementById("notification-toasts");
    const POLL_INTERVAL = 30 * 1000;
    const TOAST_TIME = 8 * 1000;
    // Notifications newer than this have not been shown yet
    let since = root.dataset.since;
    // Notifications already shown (as pop-ups or push notifications)
    const shown = new Set();
    let menuStale = true;

    function setUnread(count) {
        for (const badge of document.querySelectorAll("[data-unread-badge]")) {
            badge.textContent = count > 9 ? "9+" : String(count);
            badge.classList.toggle("hidden", !count);
        }
        for (const dot of document.querySelectorAll("[data-unread-dot]")) {
            dot.classList.toggle("hidden", !count);
        }
    }

    async function loadMenu() {
        if (!menuStale) {
            return;
        }
        menuStale = false;
        try {
            const response = await fetch(root.dataset.menuUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (response.ok) {
                menu.innerHTML = await response.text();
            } else {
                menuStale = true;
            }
        } catch {
            menuStale = true;
        }
    }

    // The menu opens when the bell gets focus (daisyUI dropdown)
    root.addEventListener("focusin", loadMenu);
    root.addEventListener("mouseenter", loadMenu);

    // "Mark all as read" in the menu, without leaving the page
    menu.addEventListener("submit", async (event) => {
        const form = event.target;
        if (!form.matches("[data-mark-all-read]")) {
            return;
        }
        event.preventDefault();
        try {
            await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            setUnread(0);
            menuStale = true;
            await loadMenu();
        } catch {
            form.submit();
        }
    });

    // A pop-up for a notification (a payload from Notification.as_payload).
    // Its text is set as text, so names and messages cannot add markup.
    function show(notification) {
        if (shown.has(notification.id)) {
            return;
        }
        shown.add(notification.id);
        const link = document.createElement("a");
        link.href = notification.url;
        link.className = "alert bg-base-100 border border-base-300 shadow-lg items-start w-80 max-w-[calc(100vw-2rem)] whitespace-normal";
        link.setAttribute("role", "status");

        const text = document.createElement("div");
        const title = document.createElement("p");
        title.className = "font-bold text-sm";
        title.textContent = notification.title;
        const message = document.createElement("p");
        message.className = "text-sm text-base-content/80";
        message.textContent = notification.message;
        text.append(title, message);
        link.append(text);

        toasts.append(link);
        setTimeout(() => link.remove(), TOAST_TIME);
    }

    async function poll() {
        if (document.hidden) {
            return;
        }
        try {
            const response = await fetch(`${root.dataset.pollUrl}?since=${encodeURIComponent(since)}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            since = data.now;
            setUnread(data.unread);
            if (data.notifications.length) {
                menuStale = true;
                // Oldest first, so the newest ends up at the bottom
                for (const notification of data.notifications.reverse()) {
                    show(notification);
                }
            }
        } catch {
            // Offline, or logged out: try again later
        }
    }

    // A push notification arrived (static/js/serviceworker.js): the system
    // has shown it, so only update the bell
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.addEventListener("message", (event) => {
            if (event.data && event.data.type === "kyyti-notification") {
                shown.add(event.data.notification.id);
                menuStale = true;
                poll();
            }
        });
    }

    setInterval(poll, POLL_INTERVAL);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            poll();
        }
    });

    window.kyytiNotifications = { show, poll };
})();
