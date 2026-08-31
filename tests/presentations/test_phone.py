import json
import pytest
from presentations import registry
from presentations.models import Session, Participant, Response
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def live(tmp_path, settings, staff_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    yield Session.open_for('ex')
    registry.clear_cache()


def join(client, code, tag='theory', name='Ana'):
    return client.post(f'/p/{code}/join/', {'expertise_tag': tag, 'display_name': name})


def test_join_flow(live, anon_client):
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 200 and b'expertise_tag' in r.content and b'theory' in r.content
    assert join(anon_client, live.join_code, tag='nope').status_code == 400
    r = join(anon_client, live.join_code)
    assert r.status_code == 302 and f'pres_{live.join_code}' in r.cookies
    p = Participant.objects.get(session=live)
    assert p.expertise_tag == 'theory' and p.display_name == 'Ana' and p.ip_hash
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 200 and b'id="deck-data"' in r.content and b'expertise_tag' not in r.content
    assert anon_client.get('/p/ZZZZZZ/').status_code == 404


def test_state_endpoint(live, anon_client):
    r = anon_client.get(f'/p/{live.join_code}/state/')
    assert r.status_code == 200 and r['Cache-Control'] == 'no-store'
    assert r.json()['slide'] == 'title' and r.json()['participants'] == 0


def _respond(client, code, iid, payload):
    return client.post(f'/p/{code}/respond/{iid}/', data=json.dumps(payload), content_type='application/json')


def test_respond_state_machine(live, anon_client, staff_client):
    code = live.join_code
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 401
    join(anon_client, code)
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 409      # hidden
    staff_client.post(f'/presentations/ex/present/interaction/q1/open/')
    assert _respond(anon_client, code, 'q1', {'choice': 'Z'}).status_code == 400
    assert _respond(anon_client, code, 'zz', {'choice': 'A'}).status_code == 404
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 200
    assert _respond(anon_client, code, 'q1', {'choice': 'B'}).status_code == 200      # upsert
    assert Response.objects.filter(session=live, interaction_id='q1').count() == 1
    assert Response.objects.get(session=live).payload == {'choice': 'B'}
    staff_client.post(f'/presentations/ex/present/interaction/q1/closed/')
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 409


def test_aggregate_visibility_and_slicing(live, staff_client):
    from django.test import Client
    code = live.join_code
    staff_client.post(f'/presentations/ex/present/interaction/q1/open/')
    clients = []
    for i, (tag, choice) in enumerate([('theory', 'A'), ('theory', 'A'), ('theory', 'B'), ('data', 'B')]):
        c = Client()
        join(c, code, tag=tag, name=f'p{i}')
        _respond(c, code, 'q1', {'choice': choice})
        clients.append(c)
    # phones can't see aggregate while open; staff can
    assert clients[0].get(f'/p/{code}/aggregate/q1/').status_code == 403
    r = staff_client.get(f'/p/{code}/aggregate/q1/')
    assert r.status_code == 200 and r.json()['counts'] == {'A': 2, 'B': 2}
    staff_client.post(f'/presentations/ex/present/interaction/q1/revealed/')
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=theory')
    assert r.json()['n'] == 3 and r.json()['counts'] == {'A': 2, 'B': 1}
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=data')
    assert r.json() == {'n': 1, 'too_small': True, 'tag': 'data'}
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=not:data')
    assert r.json()['n'] == 3
    assert clients[0].get(f'/p/{code}/aggregate/zz/').status_code == 404


def test_locked_session_phone_redirects_to_archive(live, anon_client, staff_client):
    staff_client.post('/presentations/ex/present/lock/')
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 302 and r['Location'] == '/presentations/ex/'
