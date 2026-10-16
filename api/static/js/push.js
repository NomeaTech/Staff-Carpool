// PWA push notifications on this device (notifications/push.py).
//
// The profile page's "Push notifications on this device" switch subscribes
// the browser with the server's VAPID public key, and saves the subscription
// on the server (notifications.views.push_subscribe). On iPhone and iPad,
// Safari only allows it in the app added to the Home Screen.
//
// On every page, the subscription is sent again once per visit while push
// is on, as browsers can renew subscriptions by themselves.
(function () {
    const config = document.getElementById("push-config");
    if (!config) {
        return;
    }
    const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const installed = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

    // The VAPID public key (base64url) as the bytes PushManager wants
    function applicationServerKey() {
        const base64 = config.dataset.publicKey.replace(/-/g, "+").replace(/_/g, "/");
        const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
        return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
    }

    function sameKey(subscription) {
        const key = subscription.options && subscription.options.applicationServerKey;
        if (!key) {
            return true;
        }
        const a = new Uint8Array(key), b = applicationServerKey();
        return a.length === b.length && a.every((byte, i) => byte === b[i]);
    }

    // The service worker's registration. It never arrives if the service
    // worker could not be registered, so this gives up after a while.
    function serviceWorker() {
        return Promise.race([
            navigator.serviceWorker.ready,
            new Promise((_, reject) => setTimeout(() => reject(new Error("No service worker")), 10000)),
        ]);
    }

    function post(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": config.dataset.csrf },
            body: JSON.stringify(body),
        });
    }

    async function currentSubscription() {
        const registration = await serviceWorker();
        return registration.pushManager.getSubscription();
    }

    async function enable() {
        // Asked from a click, as Safari requires
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            return false;
        }
        const registration = await serviceWorker();
        let subscription = await registration.pushManager.getSubscription();
        // Made with keys the server no longer uses
        if (subscription && !sameKey(subscription)) {
            await subscription.unsubscribe();
            subscription = null;
        }
        subscription = subscription || await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey(),
        });
        const response = await post(config.dataset.subscribeUrl, subscription.toJSON());
        return response.ok;
    }

    async function disable() {
        const subscription = await currentSubscription();
        if (subscription) {
            await post(config.dataset.unsubscribeUrl, { endpoint: subscription.endpoint });
            await subscription.unsubscribe();
        }
    }

    // Keeps the server's copy of this device's subscription up to date
    async function sync() {
        if (!supported || Notification.permission !== "granted") {
            return;
        }
        try {
            if (sessionStorage.getItem("kyyti-push-synced")) {
                return;
            }
        } catch {
            // Storage blocked: sync every page then
        }
        const subscription = await currentSubscription();
        if (subscription && sameKey(subscription)) {
            const response = await post(config.dataset.subscribeUrl, subscription.toJSON());
            if (response.ok) {
                try {
                    sessionStorage.setItem("kyyti-push-synced", "1");
                } catch {}
            }
        }
    }

    // The switch on the profile page
    const panel = document.getElementById("push-settings");
    if (panel) {
        const status = panel.querySelector("[data-push-status]");
        const button = panel.querySelector("[data-push-toggle]");

        async function render() {
            try {
                await renderState();
            } catch {
                button.hidden = true;
                status.textContent = panel.dataset.error;
            }
        }

        async function renderState() {
            button.hidden = true;
            if (iOS && !installed) {
                status.textContent = panel.dataset.ios;
                return;
            }
            if (!supported) {
                status.textContent = panel.dataset.unsupported;
                return;
            }
            if (Notification.permission === "denied") {
                status.textContent = panel.dataset.denied;
                return;
            }
            const on = Notification.permission === "granted" && Boolean(await currentSubscription());
            status.textContent = on ? panel.dataset.on : panel.dataset.off;
            button.textContent = on ? panel.dataset.turnOff : panel.dataset.turnOn;
            button.classList.toggle("btn-primary", !on);
            button.classList.toggle("btn-outline", on);
            button.dataset.on = on ? "1" : "";
            button.hidden = false;
        }

        button.addEventListener("click", async () => {
            button.disabled = true;
            try {
                if (button.dataset.on) {
                    await disable();
                } else if (!await enable() && Notification.permission !== "denied") {
                    status.textContent = panel.dataset.error;
                    return;
                }
                await render();
            } catch {
                status.textContent = panel.dataset.error;
            } finally {
                button.disabled = false;
            }
        });

        render();
    }

    sync().catch(() => {});
    window.kyytiPush = { enable, disable };
})();
