from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .. import interactions as interaction_types
from .. import livecache
from ..models import Participant, Response, Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from ..textutil import hash_ip
from .common import (DeckErrorResponse, aggregate_payload, bad, client_ip, deck_error_response,
                     deck_or_404, json_body, live_state, participant_from)

COOKIE_AGE = 365 * 24 * 3600


def _session(code):
    s = Session.objects.filter(join_code=code.upper()).first()
    if s is None:
        raise Http404('unknown join code')
    return s


def phone(request, code):
    session = _session(code)
    if session.is_locked:
        return redirect(reverse('presentations:archive', args=[session.deck_slug]))
    try:
        deck = deck_or_404(session.deck_slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    participant = participant_from(request, session)
    if participant is None:
        return render(request, 'presentations/join.html', {'deck': deck, 'session': session,
                                                          'theme_css': theme_css(deck.theme)})
    base = f'/p/{session.join_code}/'
    urls = {'state': base + 'state/', 'respond': base + 'respond/', 'aggregate': base + 'aggregate/',
            'comment': reverse('presentations:comment', args=[deck.slug])}
    data = deck_json(deck, session, 'phone', urls)
    data['participant'] = {'name': participant.display_name, 'tag': participant.expertise_tag}
    return render(request, 'presentations/phone.html', {
        'deck': deck, 'session': session, 'slides': rendered_slides(deck, request),
        'theme_css': theme_css(deck.theme), 'deck_data': deck_json_script(data), 'participant': participant,
    })


@require_POST
def join(request, code):
    session = _session(code)
    if session.is_locked:
        return bad('session is locked', 409)
    try:
        deck = deck_or_404(session.deck_slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    tag = request.POST.get('expertise_tag', '')
    if tag not in deck.expertise:
        return bad('pick one of the listed expertise tags')
    name = request.POST.get('display_name', '').strip()[:60]
    p = Participant.objects.create(session=session, expertise_tag=tag, display_name=name,
                                   ip_hash=hash_ip(client_ip(request)))
    livecache.invalidate(session.join_code)
    resp = redirect(reverse('presentations:phone', args=[session.join_code]))
    resp.set_cookie(f'pres_{session.join_code}', p.token, max_age=COOKIE_AGE, samesite='Lax',
                    secure=request.is_secure(), httponly=True)
    return resp


@require_GET
def state(request, code):
    session = _session(code)
    payload = livecache.get_state(session.join_code, lambda: live_state(Session.objects.get(pk=session.pk)))
    resp = JsonResponse(payload)
    resp['Cache-Control'] = 'no-store'
    return resp


@require_POST
def respond(request, code, iid):
    session = _session(code)
    try:
        deck = deck_or_404(session.deck_slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    participant = participant_from(request, session)
    if participant is None:
        return bad('join first', 401)
    idef = deck.interaction(iid)
    if idef is None:
        return bad('unknown interaction', 404)
    if session.state_for(iid) != 'open':
        return bad('interaction is not open', 409)
    try:
        payload = interaction_types.get(idef.type).clean_payload(json_body(request), idef.config)
    except ValueError as e:
        return bad(str(e))
    Response.objects.update_or_create(participant=participant, interaction_id=iid,
                                      defaults={'session': session, 'payload': payload})
    return JsonResponse({'ok': True})


@require_GET
def aggregate(request, code, iid):
    session = _session(code)
    try:
        deck = deck_or_404(session.deck_slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    payload, status = aggregate_payload(deck, session, iid, request.GET.get('tag'), request.user.is_staff)
    if payload is None:
        return bad('unknown interaction', 404)
    resp = JsonResponse(payload, status=status)
    resp['Cache-Control'] = 'no-store'
    return resp
