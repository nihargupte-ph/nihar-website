# Nihar Website Project

A Django-based personal website project using Django 5.0.7.

## Project Structure

```
nihar-website/
├── manage.py              # Django management script
├── db.sqlite3            # SQLite database
├── nihar_website/        # Main Django project settings
│   ├── settings.py       # Django configuration
│   ├── urls.py          # URL routing
│   ├── wsgi.py          # WSGI application entry point
│   └── asgi.py          # ASGI application entry point
├── homepage/            # Main Django app
├── pages/               # Pages app
├── templates/           # HTML templates
├── static/              # Static assets (CSS, JS, images)
└── staticfiles/         # Compiled static files
```

## Tech Stack

- **Framework**: Django 5.0.7
- **Database**: SQLite3 (development)
- **Python Version**: 3.x
- **Template Engine**: Django Templates

## Key Configuration

- **DEBUG**: Currently enabled (development mode)
- **INSTALLED_APPS**: Django built-ins + `homepage` app
- **Database**: SQLite at `db.sqlite3`
- **Static files**: Served from `static/` directory

## Common Commands

```bash
python manage.py runserver        # Start development server
python manage.py makemigrations   # Create database migrations
python manage.py migrate          # Apply database migrations
python manage.py createsuperuser  # Create admin user
python manage.py collectstatic    # Collect static files
```

## Important Notes for Development

1. **Security**: The SECRET_KEY and DEBUG settings are not production-ready. Update these before deploying.
2. **ALLOWED_HOSTS**: Currently empty - add your domain when deploying.
3. **Database**: Using SQLite locally. Consider PostgreSQL for production.
4. **Static Files**: Configure `STATIC_URL` and `STATIC_ROOT` properly for production.

## Django Apps

- **homepage**: Main homepage app

## Related Documentation

- [Django 5.0 Docs](https://docs.djangoproject.com/en/5.0/)
- [Django Settings Reference](httI saved it to @static/mindmaps/physics.svg, can you implement the
  feature?ps://docs.djangoproject.com/en/5.0/ref/settings/)
