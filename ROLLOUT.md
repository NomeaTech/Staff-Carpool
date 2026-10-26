# Before full rollout

Everything that needs doing before LUT Kyyti moves from the pilot to a full
rollout. Tick items off as they are done, and add new ones as they come up.

## Legal and privacy

- [ ] **Privacy policy** (`api/static/documents/lut_kyyti_privacy_policy.pdf`): describe the ratings and reports. Include what is stored (scores, tags, no-shows, comments for the team, reports), who sees what (members see only averages, top tags and repeated no-shows; the team sees everything), how disputes are reviewed, and how long the data is kept.
- [ ] **Privacy policy:** mention Sentry (error reports and bug reports, with the user's ID, the browser and a replay with all text and images hidden; passed on by the app's server and stored in Sentry's EU region), if `SENTRY_DSN` is set in production.
- [ ] **Terms of use** (`api/static/documents/lut_kyyti_terms_of_use.pdf`): add rules for ratings and reports, such as honest ratings, no misuse of reports, and that no-shows are shown to other members.
- [ ] **Decide how long ratings and reports are kept.** Today they are deleted only when an account is deleted. Old no-shows are hidden after a year but stay in the database.
- [ ] **Pilot wording:** the landing page (`api/landing/templates/index.html`) and the FAQ (`api/landing/templates/faq.html`) say "During the pilot phase…", including who can sign up. Update this for the rollout, and for students if they will be included.

## Translations

- [ ] Add Finnish for "Enter a return time on at least one day, or choose one-way." (`api/home/templates/add_ride.html`). ("My rides" and "Find a ride" in `api/carpool/errors.py` are translated: Django uses every app's catalog, and `home`'s has them.)
- [ ] Have a native Finnish speaker review the translations for ratings, reports, their emails and notifications, and the FAQ section "Ratings and reports". They were added without a review.
- [ ] Before release, run `makemessages` to check that every string has a Finnish entry. Run on 2026-10-27, it found no Finnish in any catalog for: "Required" (`_rate_form.html`), "Didn't show up for a ride in the past year" (`_rating.html`), "If a co-rider says you didn't show up, it is shown too." and "This is what other members see with your name…" (`ratings.html`), "Ratings are anonymous…" (`ride_detail.html`), "Rate your passenger on %(route)s" (`home.html`), and "Too many wrong passwords. Wait %(minutes)s minutes and try again, or reset your password." (`accounts/forms.py`). makemessages puts guesses marked fuzzy in the catalogs: check them by hand, or add the entries by hand instead.

## Configuration and hosting

- [ ] **Hosting with Coolify** ([DEPLOYMENT.md](DEPLOYMENT.md)):
  - [x] Choose the server (`violetta`, Hetzner) and set up the DNS records (Cloudflare).
  - [x] Run `scripts/server-setup` on it; Coolify's dashboard at https://deploy.kyyti.net, with `lock-dashboard`.
  - [x] Coolify: two-factor login and a new password.
  - [x] Coolify's notifications: by email through Resend to fentorb24@gmail.com (failed deploys, backups and tasks, server problems).
  - [x] Deploy on push: `.github/workflows/deploy.yml` with the `COOLIFY_TOKEN` secret.
  - [x] Set up staging and production, each with its PostGIS database, Redis and the app, with their environment variables, uploads folder, health check, scheduled tasks and daily database backups.
  - [ ] Try a deploy and a rollback on staging, and check that the site stays up during them.
  - [x] Move the data from the old server (`bfentorddns.zapto.org`), keeping its `SECRET_KEY` and VAPID keys.
  - [x] Staging has the pilot's data (members, rides, photos) from the old server; production's database is clean.
  - [ ] Production has no accounts yet: create the team's admin account there (`ssh violetta`, then `kyyti production createsuperuser`; DEPLOYMENT.md, "Running a command in the app").
  - [x] `.github/workflows/deploy.yml` deploys with Coolify instead of to the old server.
  - [x] Shut the old server down, delete `/root/migration` on violetta, and the old deploy secrets in GitHub.
  - [ ] Change the internal passwords of the four databases (both PostGIS and both Redis): they were shown in a setup log. In Coolify, each database's settings, then put the new internal URL in the app's `DATABASE_URL` / `REDIS_URL` and redeploy.
- [x] Set up the jobs listed in [CRONJOBS.md](CRONJOBS.md) as Coolify scheduled tasks, in both environments.
- [x] Add `test.kyyti.net` (staging's address) to the Turnstile widget's hostnames in Cloudflare and to the Google Maps key's allowed websites.
- [ ] **Sentry** (error reporting and the "Report a bug" form, see the Sentry section of `README.md`):
  - [x] Create a Sentry account in the **EU data region** (it cannot be changed later), and a Django project in it.
  - [x] Put the project's DSN (Settings › Projects › *project* › Client Keys) in the app's environment variables in Coolify as `SENTRY_DSN`, on staging with `SENTRY_ENVIRONMENT = 'testing'` and in production with `'production'`. Redeploy the app.
  - [ ] Turn on "Prevent Storing of IP Addresses" in the project's Settings › Security & Privacy.
  - [x] "Report a bug" did not open with ad blockers (uBlock Origin, Brave). Sentry's scripts are now served under names of their own, everything goes through the app (`/app/support/relay/`), and where the scripts are blocked anyway the app's own form is used (README.md, "Sentry").
  - [ ] Send a test report from the More page in LibreWolf (uBlock Origin) and Brave, and in a browser without a blocker, and check that each arrives in Sentry (User Feedback), the first two with a replay if Sentry's form opened. One test report from the server's form ("please ignore") is already there.
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

## Long term

Not needed for the rollout, but should be done.

- [ ] **Backups off the server:** S3 storage in Coolify (an EU provider, e.g. Hetzner Object Storage) for the database backups: Storages (S3) › Add, then each database's Backups › S3. The uploaded files' daily copies (`/var/backups/kyyti`) are only on the server; copy them there too (e.g. rclone to the same storage).
