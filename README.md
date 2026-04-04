# Nihar Website

Personal website built with Django 5.0.7.

## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# Visit http://127.0.0.1:8000
```

## How Django Works (Quick Refresher)

A request flows through Django like this:

```
Browser request
  -> nihar_website/urls.py      (root URL router - sends to the right app)
  -> homepage/urls.py            (app URL router - picks the right view)
  -> homepage/views.py           (view function - prepares data)
  -> homepage/templates/...html  (template - renders HTML with that data)
  -> static/                     (CSS, JS, images referenced by templates)
```

**To add a new page:** add a URL pattern in `homepage/urls.py`, write a view function in `homepage/views.py`, create a template in `homepage/templates/homepage/`.

**To add a new model:** define it in `homepage/models.py`, then run `python manage.py makemigrations && python manage.py migrate`.

## Project Structure

```
nihar-website/
├── manage.py                  # Django CLI entry point (runserver, migrate, etc.)
├── requirements.txt           # Python dependencies
├── db.sqlite3                 # SQLite database (local dev)
│
├── nihar_website/             # PROJECT CONFIG (settings, root URL routing)
│   ├── settings.py            #   All Django settings (DB, apps, static files, etc.)
│   ├── urls.py                #   Root URL config - delegates to homepage/urls.py
│   ├── wsgi.py                #   Production server entry point
│   └── asgi.py                #   Async server entry point
│
├── homepage/                  # MAIN APP (where most code lives)
│   ├── urls.py                #   URL routes for this app
│   ├── views.py               #   View functions (handle requests, return responses)
│   ├── models.py              #   Database models (Poster)
│   ├── admin.py               #   Django admin configuration
│   ├── templates/homepage/    #   HTML templates for this app
│   │   ├── base.html          #     Base layout
│   │   ├── publications.html  #     Homepage / publications listing
│   │   ├── poster_detail.html #     Individual poster page
│   │   └── mindmap_viewer.html#     Interactive SVG mindmap viewer
│   └── migrations/            #   Auto-generated DB migration files
│
├── static/                    # STATIC ASSETS (served directly to browser)
│   ├── images/                #   Poster images, PDFs, profile pics, logos
│   ├── mindmaps/              #   SVG mindmap files (physics.svg, cs-stat.svg)
│   └── assets/                #   CSS, JS, fonts
│
├── staticfiles/               # Collected static files (output of collectstatic)
├── templates/                 #   Project-level templates (navbar.html)
└── pages/                     #   Unused/placeholder app
```

## Current Routes

| URL | View | Template |
|-----|------|----------|
| `/` | `publications` | `publications.html` |
| `/projects/` | `projects` | `projects.html` |
| `/posters/<slug>/` | `poster_detail` | `poster_detail.html` |
| `/mindmap/<slug>/` | `mindmap_viewer` | `mindmap_viewer.html` |
| `/admin/` | Django admin | built-in |

## Common Commands

```bash
python manage.py runserver          # Start dev server
python manage.py makemigrations     # Generate migrations after model changes
python manage.py migrate            # Apply migrations to DB
python manage.py createsuperuser    # Create admin login
python manage.py collectstatic      # Copy static files to staticfiles/
```
