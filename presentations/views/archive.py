from django.shortcuts import render

from .. import registry
from ..models import Session


def index(request):
    decks = registry.all_decks()
    rows = []
    for d in decks:
        live = Session.open_for(d.slug)
        archived = Session.archived_for(d.slug)
        status = 'live' if live and live.current_slide_id else ('archived' if archived else 'upcoming')
        rows.append({'deck': d, 'status': status})
    return render(request, 'presentations/index.html', {'rows': rows})


def archive(request, slug):
    # Temporary stub so presentations:archive resolves for the index template.
    # Task 5 replaces this with the real archive/live view.
    return render(request, 'presentations/index.html', {'rows': []})
