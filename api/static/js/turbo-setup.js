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
    // Show the loading bar soon, so a slow page still answers the tap at once
    Turbo.config.drive.progressBarDelay = 100;

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
