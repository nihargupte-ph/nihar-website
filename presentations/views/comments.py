from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..models import Comment, Session
from ..textutil import hash_ip, render_markdown
from .common import (DeckErrorResponse, bad, client_ip, deck_error_response, deck_or_404,
                     json_body, participant_from)

RATE_LIMIT = 5                  # per person, per window
IP_RATE_LIMIT = 30              # per IP: a lecture hall NATs to one address, so this is a room, not a person
RATE_WINDOW = timedelta(minutes=1)


def _serialize(c, num):
    return {'id': c.id, 'slide': c.slide_id, 'anchor': c.anchor, 'author': c.author_name or 'anon',
            'html': render_markdown(c.body), 'created_at': c.created_at.isoformat(), 'num': num}


def _numbered(qs):
    """Number comments per slide in creation order so the overlay can label boxes ①②③."""
    counters, out = {}, []
    for c in qs:
        counters[c.slide_id] = counters.get(c.slide_id, 0) + 1
        out.append(_serialize(c, counters[c.slide_id]))
    return out


def _valid_anchor(slide, anchor):
    if anchor is None:
        return True
    if not isinstance(anchor, dict) or len(anchor) != 1:
        return False
    if 'rect' in anchor:
        r = anchor['rect']
        return (slide.uses_stage and isinstance(r, list) and len(r) == 4
                and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in r))
    if 'anchor' in anchor:
        return slide.kind == 'html' and isinstance(anchor['anchor'], str) and 0 < len(anchor['anchor']) <= 60
    return False


@require_GET
def list_comments(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    qs = Comment.visible.filter(deck_slug=slug).order_by('created_at')
    return JsonResponse({'comments': _numbered(qs)})


@require_POST
def create(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    body = json_body(request)
    if body.get('website'):
        return JsonResponse({'ok': True}, status=201)          # honeypot: pretend
    slide = deck.slide(body.get('slide'))
    if slide is None:
        return bad('unknown slide')
    text = (body.get('body') or '').strip()
    if not text:
        return bad('empty comment')
    if len(text) > 1000:
        return bad('comment too long (max 1000 characters)')
    anchor = body.get('anchor')
    if not _valid_anchor(slide, anchor):
        return bad('bad anchor')
    ip = hash_ip(client_ip(request))
    participant = None
    for s in (Session.open_for(slug), Session.archived_for(slug)):
        if s is not None:
            participant = participant_from(request, s)
            if participant:
                break
    since = timezone.now() - RATE_WINDOW
    recent = Comment.objects.filter(created_at__gte=since)
    # Count the person when we know who they are; everyone in the room shares one IP.
    if participant is not None:
        if recent.filter(participant=participant).count() >= RATE_LIMIT:
            return bad('too many comments, wait a minute', 429)
        if recent.filter(ip_hash=ip).count() >= IP_RATE_LIMIT:
            return bad('too many comments from this network, wait a minute', 429)
    elif recent.filter(ip_hash=ip).count() >= RATE_LIMIT:
        return bad('too many comments, wait a minute', 429)
    author = (body.get('author_name') or '').strip()[:60] or (participant.display_name if participant else '')
    c = Comment.objects.create(deck_slug=slug, slide_id=slide.id, anchor=anchor, author_name=author,
                               participant=participant, body=text, ip_hash=ip)
    num = Comment.visible.filter(deck_slug=slug, slide_id=slide.id, created_at__lte=c.created_at).count()
    return JsonResponse(_serialize(c, num), status=201)
