import io

import qrcode
import qrcode.image.svg
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from .. import livecache
from ..models import INTERACTION_STATES, Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from .common import DeckErrorResponse, bad, deck_error_response, deck_or_404, json_body, live_state


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return mark_safe(buf.getvalue().decode())


def _session(deck):
    s = Session.open_for(deck.slug)
    if s is not None:
        if not s.current_slide_id:
            s.set_slide(deck.slides[0].id)
        return s
    archived = Session.archived_for(deck.slug)
    if archived is not None:
        return archived
    try:
        with transaction.atomic():
            s = Session.objects.create(deck_slug=deck.slug, current_slide_id=deck.slides[0].id)
    except IntegrityError:
        # Lost the race to create the open session — another request beat us to it.
        s = Session.open_for(deck.slug)
    return s


def _touch(session):
    livecache.invalidate(session.join_code)


@staff_member_required
def present(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = _session(deck)
    join_url = request.build_absolute_uri(f'/p/{session.join_code}/')
    base = f'/presentations/{slug}/present/'
    urls = {
        'state': base + 'state/', 'goto': base + 'goto/', 'interaction': base + 'interaction/',
        'video': base + 'video/', 'lock': base + 'lock/', 'unlock': base + 'unlock/', 'new': base + 'new/',
        'aggregate': (f'/presentations/{slug}/aggregate/' if session.is_locked
                      else f'/p/{session.join_code}/aggregate/'),
        'comment': reverse('presentations:comment', args=[slug]),
        'comments': f'/presentations/{slug}/comments/',
    }
    data = deck_json(deck, session, 'present', urls)
    return render(request, 'presentations/present.html', {
        'deck': deck, 'session': session, 'slides': rendered_slides(deck, request),
        'theme_css': theme_css(deck.theme), 'deck_data': deck_json_script(data),
        'join_url': join_url, 'qr': qr_svg(join_url),
    })


@staff_member_required
@require_POST
def new_session(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    if Session.open_for(slug) is not None:
        return bad('a session is already open', 409)
    try:
        with transaction.atomic():
            s = Session.objects.create(deck_slug=slug, current_slide_id=deck.slides[0].id)
    except IntegrityError:
        return bad('a session is already open', 409)
    _touch(s)
    return JsonResponse({'ok': True, 'code': s.join_code})


def _open_session_or_400(slug):
    s = Session.open_for(slug)
    return s


@staff_member_required
@require_POST
def goto(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    sid = json_body(request).get('slide')
    if deck.slide(sid) is None:
        return bad('unknown slide')
    s.set_slide(sid)
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def interaction(request, slug, iid, state):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    if deck.interaction(iid) is None:
        return bad('unknown interaction')
    if state not in INTERACTION_STATES:
        return bad('invalid state')
    s.set_interaction_state(iid, state)
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def video(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    body = json_body(request)
    try:
        s.set_video_state(body.get('playing', False), body.get('t', 0))
    except (TypeError, ValueError):
        return bad('bad video state')
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def lock(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = Session.open_for(slug)
    if s is None:
        return bad('no open session')
    s.lock()
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def unlock(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = Session.archived_for(slug)
    if s is None:
        return bad('nothing to unlock')
    if Session.open_for(slug) is not None:
        return bad('another session is open', 409)
    try:
        s.unlock()
    except IntegrityError:
        return bad('another session is open', 409)
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_GET
def state(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    s = Session.open_for(slug) or Session.archived_for(slug)
    if s is None:
        return bad('no session', 404)
    return JsonResponse(live_state(s))
