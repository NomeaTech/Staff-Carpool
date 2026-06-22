# Staff-Carpool

## Installation instructions

### Create `.env` in `api/` (Replace with real values)
```
CSRF_COOKIE_DOMAIN = "domain"
SECRET_KEY = 'key'
DEBUG = 'boolean'
STATIC_ROOT = './directory/'
```

### Create development environment
```
python -m venv env

source env/bin/activate

pip install -r requirements.txt

cd api

python manage.py tailwind install

python manage.py tailwind dev
```