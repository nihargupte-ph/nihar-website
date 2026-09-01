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


def test_broken_deck_yaml_gives_500_on_presenter_actions(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    (deck / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    r1 = _post(staff_client, '/presentations/ex/present/video/', {'playing': True, 't': 1})
    assert r1.status_code == 500 and b'expertise' in r1.content
    r2 = _post(staff_client, '/presentations/ex/present/goto/', {'slide': 'results'})
    assert r2.status_code == 500 and b'expertise' in r2.content


def test_unlock_conflicts_with_another_open_session(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    s1 = Session.open_for('ex')
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    # Baseline: unlocking the sole archived session with nothing else open still works.
    assert _post(staff_client, '/presentations/ex/present/unlock/').status_code == 200
    s1.refresh_from_db()
    assert not s1.is_locked
    # Re-lock it, then open a fresh session for the same deck (the old one archived).
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    assert _post(staff_client, '/presentations/ex/present/new/').status_code == 200
    s2 = Session.open_for('ex')
    assert s2 is not None and s2.pk != s1.pk
    r = _post(staff_client, '/presentations/ex/present/unlock/')
    assert r.status_code == 409
    s1.refresh_from_db()
    assert s1.is_locked
    assert Session.open_for('ex') == s2


def test_present_page_after_lock_offers_new_session(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    r = staff_client.get('/presentations/ex/present/')
    assert r.status_code == 200
    body = r.content.decode()
    assert 'Unlock' in body
    assert 'id="new-session-btn"' in body
    tag = body.split('id="new-session-btn"')[1].split('>')[0]
    assert 'hidden' not in tag
    assert Session.objects.filter(deck_slug='ex').count() == 1


def test_new_session_while_locked(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    r = _post(staff_client, '/presentations/ex/present/new/')
    assert r.status_code == 200
    assert Session.objects.filter(deck_slug='ex').count() == 2
    new = Session.open_for('ex')
    assert new is not None and not new.is_locked
    assert r.json()['code'] == new.join_code


def test_new_session_conflicts_with_open_session(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    r = _post(staff_client, '/presentations/ex/present/new/')
    assert r.status_code == 409
    assert Session.objects.filter(deck_slug='ex').count() == 1


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


def test_fullscreen_letterbox_uses_the_deck_background_not_black():
    """In fullscreen the 16:9 slide is letterboxed; the strip must read as margin, not black bars."""
    from pathlib import Path
    css = (Path(__file__).resolve().parents[2] / 'presentations' / 'static' / 'presentations' / 'css' / 'deck.css').read_text()
    import re
    block = re.search(r'@media \(display-mode: fullscreen\)\{[\s\S]*?\n\}', css).group(0)
    assert 'background:var(--bg)' in block and '#000' not in block


def test_fullscreen_actually_reclaims_the_chrome_bar():
    """The 40px chrome bar is hidden in fullscreen, so the stage must be sized against the full
    viewport height. It was not: `.stage__inner{width:min(100%,calc((100vh - 40px)*16/9))}` sits
    *after* the @media block in the file and a media query adds no specificity, so the later rule
    won and the slide stayed 40px short — measured 1849x1040 inside a 1920x1080 fullscreen window,
    centred, i.e. white margin on all four sides of a screen the slide should have filled exactly.

    Carry the bar's height in a custom property instead, so one declaration serves both states and
    source order cannot decide it."""
    from pathlib import Path
    import re
    css = (Path(__file__).resolve().parents[2] / 'presentations' / 'static' / 'presentations'
           / 'css' / 'deck.css').read_text()
    inner = re.search(r'\n\.stage__inner\{[^}]*\}', css).group(0)
    assert '40px' not in inner, 'the stage still hard-codes the chrome height'
    assert 'var(--chrome-h)' in inner
    block = re.search(r'@media \(display-mode: fullscreen\)\{[\s\S]*?\n\}', css).group(0)
    assert re.search(r'--chrome-h:\s*0', block), 'fullscreen must zero the chrome height'


def test_the_presenter_bars_only_wake_when_the_pointer_reaches_their_edge():
    """Any mouse movement anywhere used to pop the bottom bar (and the top chrome) open, which is
    distracting while you are pointing at a slide. Each bar should reveal only when the pointer is
    actually near its own edge of the screen."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / 'presentations' / 'static' / 'presentations'
          / 'js' / 'present.js').read_text()
    assert 'clientY' in js, 'the wake handler has to look at where the pointer is'
    assert 'EDGE' in js


def test_the_slide_footer_stays_at_the_bottom_of_a_short_html_slide():
    """On an html slide the footer is a sibling *after* `.slide-page`, sticky to the bottom of the
    scrollport. Sticky only pulls an element down when the content is tall enough to scroll, so a
    slide whose page collapses — an underlay-only slide such as the expert-BF ones, whose deck CSS
    sets `min-height:0` — left the name/affiliation bar sitting at the *top* of the slide. Lay the
    slide out as a column so the page always takes the space above the footer."""
    from pathlib import Path
    import re
    css = (Path(__file__).resolve().parents[2] / 'presentations' / 'static' / 'presentations'
           / 'css' / 'deck.css').read_text()
    html = re.search(r'\n\.slide--html\{[^}]*\}', css).group(0)
    assert 'flex-direction:column' in html
    assert re.search(r'\.slide--html>\.slide-page\{[^}]*flex:1', css), 'the page must fill above the footer'
