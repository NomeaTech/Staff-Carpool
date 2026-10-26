# Staff-Carpool
Version: 1.0.0

## Installation instructions

### Create `.env` in `api/` (Replace with real values)
```
CSRF_COOKIE_DOMAIN = "domain"
SECRET_KEY = 'key'
DEBUG = 'boolean'
STATIC_ROOT = './directory/'
POSTGRES_PASSWORD = 'database password'
# Optional: Metabase's address, linked from the admin's user statistics (scripts/metabase)
METABASE_URL = 'https://stats.example.fi'
# Optional: after how many days the activity log's events are anonymised (default 730)
ACTIVITY_ANONYMISE_DAYS = '730'
# Optional: error reporting and the "Report a bug" form (see Sentry below)
SENTRY_DSN = 'https://...@o0.ingest.de.sentry.io/0'
SENTRY_ENVIRONMENT = 'testing'
# Optional: share of requests whose timings are recorded in Sentry, 0 to 1 (default 0)
SENTRY_TRACES_SAMPLE_RATE = '0'
# On the server (DEPLOYMENT.md); unset in development:
# the database's address, instead of the local one and POSTGRES_PASSWORD
DATABASE_URL = 'postgres://postgres:password@host:5432/campus_ride'
# Redis, shared by all of the app's processes, instead of a cache in each
REDIS_URL = 'redis://default:password@host:6379/0'
# The site's address, for links in emails; it is also allowed and trusted
SITE_URL = 'https://kyyti.net'
```

### Deployment
The server runs the app with Coolify, which deploys each push to `testing`
(staging) and `main` (production) without downtime. Setting up a server,
releasing and rolling back: see [DEPLOYMENT.md](DEPLOYMENT.md).

### Create development environment
```
python -m venv env

source env/bin/activate

pip install -r requirements.txt

cd api

python manage.py tailwind install

python manage.py tailwind dev
```

### Activity log
The app records what users do (`api/activity/`) for the admin's user statistics.
Events older than `ACTIVITY_ANONYMISE_DAYS` lose their user and ride; the app
does this itself once a day, so there is nothing to schedule.

### Sentry (errors and bug reports)
With `SENTRY_DSN` set, errors on the server and in the browser are sent to
[Sentry](https://sentry.io), and the More page gets a "Report a bug" form
(`api/carpool/sentry.py`). Only the user's ID is sent with them: no names,
emails, IP addresses or form contents. Bug reports and errors come with a
replay of the moments before them, with all text and images hidden.

1. Create a Sentry organisation in the EU region, and in it a Django project.
2. Copy its DSN (Settings › Projects › *project* › Client Keys) to `.env`.
3. In the project's Settings › Security & Privacy, turn on "Prevent Storing of
   IP Addresses".
