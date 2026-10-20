// Turbo Drive settings (the library is static/js/vendor/turbo-*.js).
//
// Links within /app/ (meta turbo-root) change the page without reloading
// it: the new page's body replaces the old one, and the CSS and scripts in
// <head> stay loaded. (No view transitions: they delayed the new page.)
//
// Things to know when writing page scripts:
// - Scripts in a page's <body> run each time the page is shown. Wrap them in
//   a function (no top-level const/let), and do not wait for window "load"
//   or "DOMContentLoaded": the page is already there when they run.
// - Scripts in <head> run once. To do something on every page, listen for
//   "turbo:load" (also sent for the first page).
// - Before leaving a page, Turbo keeps a copy to show when going back. Pages
//   whose widgets do not survive being copied (Google Maps inputs, the photo
//   cropper) opt out with <meta name="turbo-cache-control" content="no-cache">
//   in {% block head %}.
(function () {
    if (!window.Turbo) {
        return;
    }

    // Forms are posted as usual: Django shows forms with errors again with
    // a 200 response, which Turbo would not show
    Turbo.config.forms.mode = "off";

    // Turbo loads a link's page early when the mouse is over it (after
    // 100 ms, so that passing over links does not load them all). On touch
    // screens, do the same when a finger touches a link: the page then starts
    // loading before the finger is lifted. Moving the finger (scrolling)
    // cancels it, as the mouse leaving the link does.
    let touchedLink = null;
    document.addEventListener("touchstart", (event) => {
        touchedLink = event.target.closest && event.target.closest("a[href]");
        // Turbo listens for these on the document (capturing), so they work
        // like hovering the link
        touchedLink?.dispatchEvent(new MouseEvent("mouseenter"));
    }, { passive: true, capture: true });
    for (const type of ["touchmove", "touchcancel"]) {
        document.addEventListener(type, () => {
            touchedLink?.dispatchEvent(new MouseEvent("mouseleave"));
            touchedLink = null;
        }, { passive: true, capture: true });
    }

    // The mobile dock (#app-dock) stays on screen across page changes:
    // with data-turbo-permanent, Turbo keeps the same element rather than
    // the new page's (or a copy's, when going back). So:
    // - a tapped tab is pressed from the moment it is touched until its
    //   page is shown, and then fades back (.dock-pressed in styles.css);
    // - which tab is chosen comes from each page's <body data-dock-tab>,
    //   set by the server, never from a copy of an older dock.
    let pressedTab = null;
    let visiting = false;

    function dockTabs() {
        const dock = document.getElementById("app-dock");
        return dock ? [...dock.children] : [];
    }

    function choose(position) {
        dockTabs().forEach((tab, i) => {
            const chosen = i + 1 === position;
            tab.classList.toggle("dock-active", chosen);
            tab.classList.toggle("text-primary", chosen);
        });
    }

    function release() {
        pressedTab?.classList.remove("dock-pressed");
        pressedTab = null;
    }

    document.addEventListener("pointerdown", (event) => {
        const tab = event.target.closest && event.target.closest("#app-dock > a[href]");
        if (!tab || event.button !== 0) {
            return;
        }
        release();
        pressedTab = tab;
        tab.classList.add("dock-pressed");
    }, { passive: true, capture: true });
    // Scrolling or moving the finger off: not a tap
    document.addEventListener("pointercancel", release, true);
    document.addEventListener("pointerup", () => {
        // A press that does not become a page change (e.g. a long press)
        const tab = pressedTab;
        setTimeout(() => {
            if (tab && tab === pressedTab && !visiting) {
                release();
            }
        }, 500);
    }, true);

    document.addEventListener("click", (event) => {
        const tab = event.target.closest && event.target.closest("#app-dock > a[href]");
        if (!tab) {
            return;
        }
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            release();
            return;
        }
        visiting = true;
        if (tab !== pressedTab) {
            // e.g. chosen with the keyboard
            release();
            pressedTab = tab;
            tab.classList.add("dock-pressed");
        }
        choose(dockTabs().indexOf(tab) + 1);
    }, true);

    // Before a page (or a copy of one) is shown: its tab is chosen, and the
    // unread dot is the page's
    document.addEventListener("turbo:before-render", (event) => {
        const newBody = event.detail.newBody;
        choose(Number(newBody.dataset.dockTab));
        const dot = newBody.querySelector("#app-dock [data-unread-dot]");
        const liveDot = document.querySelector("#app-dock [data-unread-dot]");
        if (dot && liveDot) {
            liveDot.classList.toggle("hidden", dot.classList.contains("hidden"));
        }
    });
    // Once shown, the pressed tab fades back. Not before: Turbo moves the
    // dock into the new page, and a moved element starts without its
    // earlier look, so there would be nothing to fade from. Reading its
    // style first gives it that look in its new place.
    document.addEventListener("turbo:render", () => {
        if (pressedTab) {
            getComputedStyle(pressedTab.firstElementChild).transform;
            getComputedStyle(pressedTab).backgroundColor;
        }
        release();
        visiting = false;
    });
    // A page change that failed: back to the page's own tab
    document.addEventListener("turbo:fetch-request-error", () => {
        choose(Number(document.body.dataset.dockTab));
        release();
        visiting = false;
    });

    // Before keeping a copy of the page for going back: close what is open
    // and remove messages that should not show again
    document.addEventListener("turbo:before-cache", () => {
        const drawer = document.getElementById("my-drawer-5");
        if (drawer) {
            drawer.checked = false;
        }
        document.activeElement && document.activeElement.blur && document.activeElement.blur();
        document.getElementById("messages")?.remove();
        document.getElementById("notification-toasts")?.replaceChildren();
        for (const dialog of document.querySelectorAll("dialog[open]")) {
            dialog.close();
        }
    });
})();
