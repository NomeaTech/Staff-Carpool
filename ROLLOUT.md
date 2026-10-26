# Before full rollout

Everything that needs doing before LUT Kyyti moves from the pilot to a full
rollout. Tick items off as they are done, and add new ones as they come up.

## Legal and privacy

- [ ] **Privacy policy** (`api/static/documents/lut_kyyti_privacy_policy.pdf`): describe the ratings and reports. Include what is stored (scores, tags, no-shows, comments for the team, reports), who sees what (members see only averages, top tags and repeated no-shows; the team sees everything), how disputes are reviewed, and how long the data is kept.
- [ ] **Privacy policy:** mention Sentry (error reports and bug reports, with the user's ID and a replay with all text and images hidden; stored in Sentry's EU region), if `SENTRY_DSN` is set in production.
- [ ] **Terms of use** (`api/static/documents/lut_kyyti_terms_of_use.pdf`): add rules for ratings and reports, such as honest ratings, no misuse of reports, and that no-shows are shown to other members.
- [ ] **Decide how long ratings and reports are kept.** Today they are deleted only when an account is deleted. Old no-shows are hidden after a year but stay in the database.
- [ ] **Pilot wording:** the landing page (`api/landing/templates/index.html`) and the FAQ (`api/landing/templates/faq.html`) say "During the pilot phase…", including who can sign up. Update this for the rollout, and for students if they will be included.

## Translations

- [ ] Add Finnish for three strings missing from the `.po` files:
  - "My rides" and "Find a ride" in `api/carpool/errors.py` (go in `api/locale/fi/LC_MESSAGES/django.po`)
  - "Enter a return time on at least one day, or choose one-way." in `api/home/templates/add_ride.html`
- [ ] Have a native Finnish speaker review the translations for ratings, reports, their emails and notifications, and the FAQ section "Ratings and reports". They were added without a review.
- [ ] Before release, run `makemessages` to check that every string has a Finnish entry.

## Configuration and hosting

- [ ] **Hosting with Coolify** ([DEPLOYMENT.md](DEPLOYMENT.md)):
  - [ ] Choose the server (EU provider, 4 GB of memory or 8 GB with Metabase) and set up the DNS records.
  - [ ] Run `scripts/server-setup` on it, then set up Coolify: dashboard address, `lock-dashboard`, two-factor login, GitHub, notifications.
  - [ ] Set up staging and production, each with its PostGIS database, Redis and the app, with their environment variables (including `SITE_URL`), uploads folder and health check.
  - [ ] Try a deploy and a rollback on staging, and check that the site stays up during them.
  - [ ] Move the data from the current server (DEPLOYMENT.md, "Moving from the current server"), keeping its `SECRET_KEY` and VAPID keys.
  - [ ] Afterwards, remove `.github/workflows/deploy.yml`, which still deploys `testing` to the current server, and shut that server down.
  - [ ] The Docker image (`Dockerfile`) has not been built yet: the first deploy is its first build. Try it beforehand with `docker compose up --build` if you can.
- [ ] **Backups off the server:** S3 storage in Coolify for the database backups. The uploaded files' daily copies (`/var/backups/kyyti`) are only on the server; copy them elsewhere too (e.g. rclone to the same S3 storage).
- [ ] Set up the jobs listed in [CRONJOBS.md](CRONJOBS.md) as Coolify scheduled tasks, in both environments.
- [ ] Add `test.kyyti.net` (staging's address) to the Turnstile widget's hostnames in Cloudflare and to the Google Maps key's allowed websites.
- [ ] **Sentry** (error reporting and the "Report a bug" form, see the Sentry section of `README.md`):
  - [ ] Create a Sentry account in the **EU data region** (it cannot be changed later), and a Django project in it.
  - [ ] Put the project's DSN (Settings › Projects › *project* › Client Keys) in the app's environment variables in Coolify as `SENTRY_DSN`, on staging with `SENTRY_ENVIRONMENT = 'testing'` and in production with `'production'`. Redeploy the app.
  - [ ] Turn on "Prevent Storing of IP Addresses" in the project's Settings › Security & Privacy.
  - [ ] Send a test report from the More page ("Report a bug") and check that it arrives in Sentry with its replay.
  - [ ] Optional: connect GitHub or Slack (Settings › Integrations) so new issues are announced.
  - [ ] The free plan has one user. Move to the Team plan (about $26/month) if more people need to read the reports.
- [ ] `CONTACT_EMAIL` in `api/carpool/settings.py` is a personal address. Contact form messages and reports of members go to it. Change it to a team mailbox, and consider reading it from `.env`.

## Moderation

- [ ] Decide who handles reports and disputed ratings, and how quickly. Both are in the admin: Rides › Reports (filter by "handled at: empty") and Rides › Ratings (filter by "review: disputed, waiting for review").
- [ ] Make sure everyone handling them has an admin account with two-step verification set up (the admin requires it).
- [ ] Agree on what to do about members who are reported repeatedly or have many no-shows. The app only shows and warns; it never blocks anyone.

## Testing

- [ ] Try the rating, reporting and ratings-page flows in a real browser, on a phone too. The row of ten score buttons has not been checked by eye at phone width.
- [ ] Three tests fail when static files are collected with hashed names (`landing` legal documents, `notifications` Turbo and push icon). Check whether they also fail in the environment the tests are normally run in, and fix the tests or that setup.

## Code clean-up

- [x] Replace the date parsing marked "TEMPORARY" in `api/rides/models.py`. Dates and times are now shown in each language's formats (`api/carpool/formats/`).
- [ ] `python-dateutil` in `api/requirements.txt` was only used by that parsing. Remove it if nothing else needs it.
