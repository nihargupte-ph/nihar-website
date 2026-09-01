import json
import pytest
from presentations import registry
from presentations.models import Comment
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield make_deck(tmp_path)
    registry.clear_cache()


def post(client, body):
    return client.post('/presentations/ex/comment/', data=json.dumps(body), content_type='application/json')


def test_create_and_list(deck, anon_client):
    r = post(anon_client, {'slide': 'title', 'anchor': {'rect': [0.1, 0.1, 0.2, 0.2]}, 'body': 'why **this**?', 'author_name': 'Ana', 'website': ''})
    assert r.status_code == 201
    j = r.json()
    assert j['html'] == '<p>why <strong>this</strong>?</p>' and j['author'] == 'Ana' and j['num'] == 1
    r = anon_client.get('/presentations/ex/comments/')
    assert r.json()['comments'][0]['anchor'] == {'rect': [0.1, 0.1, 0.2, 0.2]}
    assert Comment.objects.get().ip_hash


def test_validation(deck, anon_client):
    assert post(anon_client, {'slide': 'zzz', 'body': 'x'}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': '   '}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': 'x' * 1001}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': 'x', 'anchor': {'rect': [2, 0, 0, 0]}}).status_code == 400
    assert post(anon_client, {'slide': 'page', 'body': 'x', 'anchor': {'rect': [0, 0, .1, .1]}}).status_code == 400  # html slide → anchor names only
    assert post(anon_client, {'slide': 'page', 'body': 'x', 'anchor': {'anchor': 'fig-2'}}).status_code == 201
    assert post(anon_client, {'slide': 'title', 'body': 'x', 'anchor': None}).status_code == 201


def test_honeypot_silently_drops(deck, anon_client):
    r = post(anon_client, {'slide': 'title', 'body': 'buy stuff', 'website': 'http://spam'})
    assert r.status_code == 201 and Comment.objects.count() == 0


def test_rate_limit(deck, anon_client):
    for i in range(5):
        assert post(anon_client, {'slide': 'title', 'body': f'c{i}'}).status_code == 201
    assert post(anon_client, {'slide': 'title', 'body': 'c6'}).status_code == 429


def test_hidden_not_listed(deck, anon_client):
    post(anon_client, {'slide': 'title', 'body': 'ok'})
    Comment.objects.update(is_hidden=True)
    assert anon_client.get('/presentations/ex/comments/').json()['comments'] == []


def test_participant_signs_comment(deck, anon_client, staff_client):
    from presentations.models import Session
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    anon_client.post(f'/p/{s.join_code}/join/', {'expertise_tag': 'theory', 'display_name': 'Bo'})
    r = post(anon_client, {'slide': 'title', 'body': 'hi'})
    assert r.json()['author'] == 'Bo' and Comment.objects.get().participant is not None


def test_rate_limit_counts_people_not_the_lecture_hall(deck, anon_client, staff_client):
    """A conference room NATs to one public IP. Five questions from one keen attendee must not
    silence everyone else for the rest of the minute."""
    from django.test import Client
    from presentations.models import Session
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    keen, quiet = anon_client, Client()
    for c, name in ((keen, 'Ana'), (quiet, 'Bo')):
        c.post(f'/p/{s.join_code}/join/', {'expertise_tag': 'theory', 'display_name': name})
    for i in range(5):
        assert post(keen, {'slide': 'title', 'body': f'ana {i}'}).status_code == 201
    assert post(keen, {'slide': 'title', 'body': 'ana 6'}).status_code == 429       # still capped
    assert post(quiet, {'slide': 'title', 'body': 'bo 1'}).status_code == 201       # but Bo is not
