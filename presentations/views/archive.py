from django.shortcuts import render
from django.urls import reverse

from .. import registry
from ..models import Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from .common import DeckErrorResponse, deck_error_response, deck_or_404


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
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = Session.archived_for(slug)
    live = Session.open_for(slug)
    urls = {
        'aggregate': f'/presentations/{slug}/aggregate/',
        'comment': reverse('presentations:comment', args=[slug]),
        'state': None,
    }
    data = deck_json(deck, session, 'archive', urls)
    return render(request, 'presentations/archive.html', {
        'deck': deck, 'slides': rendered_slides(deck, request), 'theme_css': theme_css(deck.theme),
        'deck_data': deck_json_script(data), 'live': live, 'session': session,
    })
