# Before full rollout

Everything that needs doing before LUT Kyyti moves from the pilot to a full
rollout. Tick items off as they are done, and add new ones as they come up.

## Legal and privacy

- [ ] **Privacy policy** (`api/static/documents/lut_kyyti_privacy_policy.pdf`): describe the ratings and reports. Include what is stored (scores, tags, no-shows, comments for the team, reports), who sees what (members see only averages, top tags and repeated no-shows; the team sees everything), how disputes are reviewed, and how long the data is kept.
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

- [ ] Finalise hosting, and set the production `.env` (see `README.md`), including `SITE_URL`.
- [ ] Set up the cron jobs listed in [CRONJOBS.md](CRONJOBS.md).
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
