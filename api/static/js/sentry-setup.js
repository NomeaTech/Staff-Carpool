// Error reporting and bug reports with Sentry (carpool/sentry.py). The
// library is static/js/vendor/sentry-*.js, and its settings come from the
// page (templates/_sentry.html).
//
// - Errors in the page's scripts are sent to Sentry.
// - Session replay keeps a recording of the last moments in memory and only
//   sends it with an error or a bug report. All text, inputs and images in
//   it are hidden.
// - Links and buttons with data-bug-report (the More page) open Sentry's
//   feedback form, in the page's language. Its floating button is not
//   shown: on phones it would cover the dock.
(function () {
    const config = document.getElementById("sentry-config");
    if (!window.Sentry || !config) {
        return;
    }
    const settings = JSON.parse(config.textContent);
    const feedback = Sentry.feedbackIntegration({
        ...settings.feedback,
        autoInject: false,
        // The report is linked to the user's ID, which the team can look up
        showName: false,
        showEmail: false,
        showBranding: false,
        colorScheme: localStorage["theme"] == "dark" ? "dark" : "light",
    });
    Sentry.init({
        dsn: settings.dsn,
        environment: settings.environment,
        release: settings.release,
        sendDefaultPii: false,
        integrations: [Sentry.replayIntegration(), feedback],
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 1,
    });
    if (settings.user_id) {
        Sentry.setUser({ id: settings.user_id });
    }

    // The form lives in an element of its own at the end of <body>. Turbo
    // replaces <body> when the page changes, so it is moved to the new one.
    document.addEventListener("turbo:before-render", event => {
        const host = document.getElementById("sentry-feedback");
        if (host) {
            event.detail.newBody.appendChild(host);
        }
    });

    let opening = false;
    document.addEventListener("click", async event => {
        if (!event.target.closest("[data-bug-report]")) {
            return;
        }
        event.preventDefault();
        if (opening) {
            return;
        }
        opening = true;
        try {
            // The theme may have been changed since the page was loaded
            feedback.setTheme(localStorage["theme"] == "dark" ? "dark" : "light");
            // A new form each time, so that it starts empty
            const form = await feedback.createForm({
                onFormClose: () => form.removeFromDom(),
                onFormSubmitted: () => form.removeFromDom(),
            });
            form.appendToDom();
            form.open();
        } finally {
            opening = false;
        }
    });
})();
