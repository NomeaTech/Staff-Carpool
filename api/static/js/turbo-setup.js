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

    // The mobile dock: the tapped tab shows as chosen at once while its page
    // loads, as in apps. It is marked on <html> (data-dock-pending, see
    // styles.css) rather than on the dock: Turbo's copies of pages for going
    // back are of <head> and <body>, so the mark never ends up in one, and
    // nothing has to be undone before Turbo makes a copy.
    const root = document.documentElement;
    document.addEventListener("click", (event) => {
        const item = event.target.closest && event.target.closest(".dock > a[href]");
        if (!item || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }
        root.dataset.dockPending = [...item.parentElement.children].indexOf(item) + 1;
    }, true);
    // The new page shows its own tab (also when it is a copy shown first)
    function clearDockPending() {
        delete root.dataset.dockPending;
    }
    for (const type of ["turbo:render", "turbo:load", "turbo:fetch-request-error"]) {
        document.addEventListener(type, clearDockPending);
    }
    window.addEventListener("pageshow", clearDockPending);

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
