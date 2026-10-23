# Staff-Carpool
Version: 0.30.0

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
```
dj
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
