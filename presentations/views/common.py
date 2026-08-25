from django.http import HttpResponseNotFound, HttpResponseServerError
from django.template.loader import render_to_string

from .. import registry
from ..schema import DeckError


class DeckErrorResponse(Exception):
    """Wraps a DeckError so views can return a readable 500."""
    def __init__(self, err):
        self.err = err


def deck_or_404(slug):
    try:
        return registry.get_deck(slug)
    except DeckError as e:
        raise DeckErrorResponse(e)


def deck_error_response(request, exc):
    html = render_to_string('presentations/deck_error.html', {'error': exc.err}, request=request)
    return HttpResponseServerError(html)


def placeholder(request, *args, **kwargs):
    return HttpResponseNotFound()
