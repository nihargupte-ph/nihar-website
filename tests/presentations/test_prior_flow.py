"""End-to-end: phone submits a prior curve, presenter reads every curve back with metadata."""
import json
import pytest
from django.test import Client
from presentations import registry
from presentations.models import Session
from .test_schema import make_deck

pytestmark = pytest.mark.django_db

DECK = """
title: Example
date: 2026-09-12
expertise: [theory, data]
theme: {bg: "#111111", fg: "#eeeeee", accents: ["#37b49f"]}
interactions:
  - id: ep
    type: prior
    prompt: Draw your prior
    axis: {min: -4, max: 0, bins: 4, label: log10 e}
slides:
  - id: title
    svg: slides/01.svg
  - id: poll
    html: poll.html
    ask: [ep]
    show: [{id: ep}]
"""


@pytest.fixture
def live(tmp_path, settings, staff_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path, text=DECK, files=('slides/01.svg', 'poll.html'))
    staff_client.get('/presentations/ex/present/')
    yield Session.open_for('ex')
    registry.clear_cache()


def phone_client(code, name):
    c = Client()
    c.post(f'/p/{code}/join/', {'expertise_tag': 'theory', 'display_name': name})
    return c


def respond(client, code, payload):
    return client.post(f'/p/{code}/respond/ep/', data=json.dumps(payload), content_type='application/json')


def test_prior_round_trip(live, staff_client):
    code = live.join_code
    staff_client.post('/presentations/ex/present/interaction/ep/open/')
    a, b = phone_client(code, 'A'), phone_client(code, 'B')
    assert respond(a, code, {'weights': [1, 0, 0, 0], 'name': 'Ada', 'institute': 'AEI',
                             'expertise': ['astrophysics']}).status_code == 200
    assert respond(b, code, {'weights': [0, 0, 0, 1], 'expertise': ['astrology']}).status_code == 400
    assert respond(b, code, {'weights': [0, 0, 0, 1], 'name': 'Bo', 'expertise': ['instrumentation', 'other'],
                             'other': 'ML'}).status_code == 200
    # resubmit replaces
    assert respond(a, code, {'weights': [0, 1, 0, 0], 'name': 'Ada', 'institute': 'AEI',
                             'expertise': ['astrophysics']}).status_code == 200
    agg = staff_client.get(f'/p/{code}/aggregate/ep/').json()
    assert agg['n'] == 2 and agg['state'] == 'open'
    by_name = {c['name']: c for c in agg['curves']}
    assert by_name['Ada']['weights'] == [0, 1, 0, 0]
    assert by_name['Bo']['expertise'] == ['instrumentation', 'other'] and by_name['Bo']['other'] == 'ML'
    assert agg['mean'] == [0, 0.5, 0, 0.5]
    assert set(agg['comparisons']) == {'log_uniform', 'uniform'}
    assert a.get(f'/p/{code}/aggregate/ep/').status_code == 403     # phones wait for reveal


def test_phone_preview_page_is_staff_only_and_frames_the_join_url(live, staff_client, anon_client):
    r = staff_client.get('/presentations/ex/present/phone-preview/')
    assert r.status_code == 200
    assert f'src="/p/{live.join_code}/"'.encode() in r.content
    assert anon_client.get('/presentations/ex/present/phone-preview/').status_code == 302


def test_phone_pages_allow_same_origin_framing(live, anon_client):
    code = live.join_code
    assert anon_client.get(f'/p/{code}/')['X-Frame-Options'] == 'SAMEORIGIN'          # join form
    phone_client(code, 'A')
    c = Client(); c.post(f'/p/{code}/join/', {'expertise_tag': 'theory', 'display_name': 'B'})
    assert c.get(f'/p/{code}/')['X-Frame-Options'] == 'SAMEORIGIN'                     # deck mirror
