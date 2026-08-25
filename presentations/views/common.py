import json

from django.http import HttpResponseServerError, JsonResponse
from django.template.loader import render_to_string

from .. import registry
from .. import interactions as interaction_types
from ..models import Participant, Response
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


def live_state(session):
    return {
        'v': session.version, 'slide': session.current_slide_id, 'locked': session.is_locked,
        'interactions': session.interaction_states, 'video': session.video_state,
        'participants': session.participants.count(),
    }


def json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


def bad(msg, status=400):
    return JsonResponse({'error': msg}, status=status)


def client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return (xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')) or ''


def participant_from(request, session):
    token = request.COOKIES.get(f'pres_{session.join_code}')
    if not token:
        return None
    return Participant.objects.filter(session=session, token=token).first()


def aggregate_payload(deck, session, iid, tag, is_staff):
    idef = deck.interaction(iid)
    if idef is None:
        return None, 404
    state = session.state_for(iid)
    if state in ('hidden', 'open') and not is_staff:
        return {'error': 'not revealed'}, 403
    qs = Response.objects.filter(session=session, interaction_id=iid).select_related('participant')
    tag = tag or 'all'
    if tag.startswith('not:'):
        qs = qs.exclude(participant__expertise_tag=tag[4:])
    elif tag != 'all':
        qs = qs.filter(participant__expertise_tag=tag)
    payloads = [r.payload for r in qs]
    if tag != 'all' and len(payloads) < 3:
        return {'n': len(payloads), 'too_small': True, 'tag': tag}, 200
    agg = interaction_types.get(idef.type).aggregate(payloads, idef.config)
    agg['tag'] = tag
    agg['state'] = state
    return agg, 200
