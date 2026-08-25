import json
import pytest
from presentations import registry
from presentations.models import Session
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield make_deck(tmp_path)
    registry.clear_cache()


def test_present_requires_staff(deck, anon_client):
    r = anon_client.get('/presentations/ex/present/')
    assert r.status_code == 302 and '/admin/login/' in r['Location']


def test_present_creates_and_resumes_session(deck, staff_client):
    r = staff_client.get('/presentations/ex/present/')
    assert r.status_code == 200
    s = Session.open_for('ex')
    assert s is not None and s.current_slide_id == 'title'
    assert f'/p/{s.join_code}/' in r.content.decode()
    assert '<svg' in r.content.decode().split('id="qr-box"')[1][:2000]
    staff_client.get('/presentations/ex/present/')
    assert Session.objects.filter(deck_slug='ex').count() == 1


def _post(client, url, body=None):
    return client.post(url, data=json.dumps(body or {}), content_type='application/json')


def test_presenter_actions(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    assert _post(staff_client, '/presentations/ex/present/goto/', {'slide': 'results'}).status_code == 200
    assert _post(staff_client, '/presentations/ex/present/goto/', {'slide': 'nope'}).status_code == 400
    assert _post(staff_client, '/presentations/ex/present/interaction/q1/open/').status_code == 200
    assert _post(staff_client, '/presentations/ex/present/interaction/q1/bogus/').status_code == 400
    assert _post(staff_client, '/presentations/ex/present/interaction/zz/open/').status_code == 400
    assert _post(staff_client, '/presentations/ex/present/video/', {'playing': True, 't': 3.5}).status_code == 200
    s.refresh_from_db()
    assert s.current_slide_id == 'results' and s.interaction_states == {'q1': 'open'}
    assert s.video_state['playing'] is True and s.video_state['t'] == 3.5
    st = staff_client.get('/presentations/ex/present/state/').json()
    assert st['slide'] == 'results' and st['interactions'] == {'q1': 'open'} and st['participants'] == 0
    assert st['v'] == s.version


def test_presenter_actions_reject_anon(deck, anon_client, staff_client):
    staff_client.get('/presentations/ex/present/')
    r = _post(anon_client, '/presentations/ex/present/goto/', {'slide': 'results'})
    assert r.status_code in (302, 403)


def test_lock_and_unlock(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    _post(staff_client, '/presentations/ex/present/interaction/q1/open/')
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    s = Session.objects.get(deck_slug='ex')
    assert s.is_locked and s.interaction_states == {'q1': 'revealed'}
    assert Session.open_for('ex') is None and Session.archived_for('ex') == s
    assert _post(staff_client, '/presentations/ex/present/unlock/').status_code == 200
    assert Session.open_for('ex') == s


def test_livecache_ttl(deck, staff_client, monkeypatch):
    from presentations import livecache
    calls = []
    def builder():
        calls.append(1)
        return {'v': len(calls)}
    t = [1000.0]
    monkeypatch.setattr(livecache.time, 'monotonic', lambda: t[0])
    assert livecache.get_state('ABC', builder) == {'v': 1}
    assert livecache.get_state('ABC', builder) == {'v': 1}
    t[0] += 1.1
    assert livecache.get_state('ABC', builder) == {'v': 2}
    livecache.invalidate('ABC')
    assert livecache.get_state('ABC', builder) == {'v': 3}
