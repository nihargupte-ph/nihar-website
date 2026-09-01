from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .. import registry
from ..models import Session
from ..render import asset_base, deck_json, deck_json_script, inline_svg, rendered_slides, theme_css
from .common import DeckErrorResponse, aggregate_payload, bad, deck_error_response, deck_or_404


def index(request):
    decks = registry.all_decks()
    rows = []
    for d in decks:
        live = Session.open_for(d.slug)
        archived = Session.archived_for(d.slug)
        status = 'live' if live and live.current_slide_id else ('archived' if archived else 'upcoming')
        rows.append({'deck': d, 'status': status})
    return render(request, 'presentations/index.html', {'rows': rows})


@ensure_csrf_cookie
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
        'comments': f'/presentations/{slug}/comments/',
        'state': None,
    }
    data = deck_json(deck, session, 'archive', urls)
    return render(request, 'presentations/archive.html', {
        'deck': deck, 'slides': rendered_slides(deck, request), 'theme_css': theme_css(deck.theme),
        'deck_data': deck_json_script(data), 'live': live, 'session': session,
    })


@require_GET
def slide_markup(request, slug, sid):
    """One svg slide's inlined markup, for the slides the page did not ship (see render.EAGER_SLIDES).
    Same bytes `rendered_slides` would have put in the page — id-namespaced, raster hrefs absolute."""
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    slide = next((s for s in deck.slides if s.id == sid), None)
    if slide is None or slide.kind != 'svg':
        raise Http404('no such svg slide')
    html = inline_svg(deck.dir / slide.path, ns=slide.id, asset_base=asset_base(deck, slide.path))
    r = HttpResponse(html, content_type='text/html; charset=utf-8')
    r['Cache-Control'] = 'private, max-age=60'
    return r


@require_GET
def archive_aggregate(request, slug, iid):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = Session.archived_for(slug)
    if session is None:
        return bad('no archived session', 404)
    if session.state_for(iid) != 'revealed' and deck.interaction(iid) is not None:
        return bad('not revealed', 403)
    payload, status = aggregate_payload(deck, session, iid, request.GET.get('tag'), True)
    if payload is None:
        return bad('unknown interaction', 404)
    return JsonResponse(payload, status=status)
