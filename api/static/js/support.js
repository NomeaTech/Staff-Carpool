// Error reporting and bug reports with Sentry (carpool/sentry.py). The
// library is static/js/vendor/kyyti-support-*.js, and its settings come from
// the page (templates/_sentry.html). Neither is named after Sentry, and
// everything goes to Sentry through the app (tunnel), as ad blockers block
// Sentry's scripts and addresses.
//
// - Errors in the page's scripts are sent to Sentry.
// - Session replay keeps a recording of the last moments in memory and only
//   sends it with an error or a bug report. All text, inputs and images in
//   it are hidden.
// - Links with data-bug-report (the More page) open Sentry's feedback form,
//   in the page's language. Its floating button is not shown: on phones it
//   would cover the dock. Where this script or the library does not load
//   (blocked), or the form cannot be opened, the link leads to the app's own
//   form instead (home/views.py report_bug).
(function () {
    const config = document.getElementById("support-config");
    if (!window.Sentry || !config) {
        return;
    }
    const settings = JSON.parse(config.textContent);
    const feedback = Sentry.feedbackIntegration({
        ...settings.feedback,
        autoInject: false,
        // The form's element; the default (sentry-feedback) may be hidden by ad blockers
        id: "kyyti-support",
        // The report is linked to the user's ID, which the team can look up
        showName: false,
        showEmail: false,
        showBranding: false,
        colorScheme: localStorage["theme"] == "dark" ? "dark" : "light",
    });
    Sentry.init({
        dsn: settings.dsn,
        tunnel: settings.tunnel,
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
        const host = document.getElementById("kyyti-support");
        if (host) {
            event.detail.newBody.appendChild(host);
        }
    });

    let opening = false;
    document.addEventListener("click", async event => {
        const link = event.target.closest("[data-bug-report]");
        if (!link) {
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
        } catch (error) {
            // The app's own form, as without this script
            window.Turbo ? Turbo.visit(link.href) : location.assign(link.href);
        } finally {
            opening = false;
        }
    });
})();
