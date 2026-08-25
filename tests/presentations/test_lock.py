import json
import pytest
from django.test import Client
from presentations import registry
from presentations.models import Session
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def played(tmp_path, settings, staff_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    staff_client.post('/presentations/ex/present/interaction/q1/open/')
    for tag, ch in [('theory', 'A'), ('theory', 'B'), ('data', 'B')]:
        c = Client()
        c.post(f'/p/{s.join_code}/join/', {'expertise_tag': tag})
        c.post(f'/p/{s.join_code}/respond/q1/', data=json.dumps({'choice': ch}), content_type='application/json')
    yield s
    registry.clear_cache()


def test_archive_aggregate_needs_locked_session(played, anon_client):
    assert anon_client.get('/presentations/ex/aggregate/q1/').status_code == 404


def test_archive_after_lock(played, anon_client, staff_client):
    staff_client.post('/presentations/ex/present/lock/')
    r = anon_client.get('/presentations/ex/aggregate/q1/')
    assert r.status_code == 200 and r.json()['counts'] == {'A': 1, 'B': 2} and r.json()['state'] == 'revealed'
    page = anon_client.get('/presentations/ex/').content.decode()
    data = json.loads(page.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['session']['locked'] is True and data['interactions']['q1']['state'] == 'revealed'
    assert 'LOCKED' in page


def test_never_opened_interaction_stays_hidden(tmp_path, settings, staff_client, anon_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    staff_client.post('/presentations/ex/present/lock/')
    assert anon_client.get('/presentations/ex/aggregate/q1/').status_code == 403
    registry.clear_cache()
