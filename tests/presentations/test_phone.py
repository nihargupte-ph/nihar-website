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


# --- the comments panel on a phone -------------------------------------------------------------
# `.comments-panel` is `width:min(380px,100vw)`, so on every iPhone it covers the whole screen —
# including the fixed `#comment-toggle` at left:12px, which is what opened it. Measured in an
# emulated iPhone 13 / SE / 12 Pro: zero pixels of the toggle are hittable once the panel is open,
# and `stage.swipe()` deliberately ignores `.comments-panel`. Without a control inside the panel an
# attendee who opens it is stuck there and has to reload the page.

def _read(*parts):
    from pathlib import Path
    return (Path(__file__).resolve().parents[2] / 'presentations').joinpath(*parts).read_text()


def test_comments_panel_carries_its_own_close_control():
    tpl = _read('templates', 'presentations', '_comments.html')
    assert 'id="comment-close"' in tpl, 'the panel covers the toggle on a phone — it needs its own ✕'
    js = _read('static', 'presentations', 'js', 'comments.js')
    assert '#comment-close' in js, 'the ✕ must actually be wired to close the panel'


def test_comments_panel_stays_above_the_phone_keyboard():
    """iOS shrinks the visual viewport, not the layout viewport, so a `bottom:0` fixed panel keeps
    its form behind the keyboard. comments.js has to track visualViewport and inset the panel."""
    js = _read('static', 'presentations', 'js', 'comments.js')
    assert 'visualViewport' in js


def test_comment_form_does_not_scroll_away_behind_a_backlog_of_questions():
    """With a room's worth of questions the composer must stay put — an attendee should never have
    to scroll a list to find the box. The panel is a column: fixed head, scrolling list, fixed form."""
    css = _read('static', 'presentations', 'css', 'deck.css')
    import re
    panel = re.search(r'\.comments-panel\{[^}]*\}', css).group(0)
    assert 'display:flex' in panel and 'flex-direction:column' in panel and 'overflow:hidden' in panel
    assert re.search(r'#comment-list\{[^}]*flex:1[^}]*overflow:auto', css)
