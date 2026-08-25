import json
import pytest
from presentations import registry
from .test_schema import make_deck, GOOD

SVG = '<?xml version="1.0"?><!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="10" height="10"/></svg>'
PAGE = '{% extends "presentations/slide_base.html" %}{% block slide %}<h1 data-hotspot="H" data-body="b">Page {{ theme.bg }}</h1><div data-interaction="q1"></div>{% endblock %}'


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    d = make_deck(tmp_path)
    (d / 'slides' / '01.svg').write_text(SVG)
    (d / 'page.html').write_text(PAGE)
    yield d
    registry.clear_cache()


def test_inline_svg_normalises(deck):
    from presentations.render import inline_svg
    out = inline_svg(deck / 'slides' / '01.svg')
    assert not out.startswith('<?xml') and 'DOCTYPE' not in out
    assert 'viewBox="0 0 1920 1080"' in out
    assert 'width="100%"' in out and 'preserveAspectRatio="xMidYMid meet"' in out


def test_archive_renders_all_kinds(deck, anon_client, db):
    r = anon_client.get('/presentations/ex/')
    assert r.status_code == 200
    html = r.content.decode()
    assert html.count('data-slide-id=') == 4
    assert '<rect width="10" height="10"' in html                     # svg inlined
    assert 'Page #111111' in html                                     # html slide rendered with theme
    assert '<video' in html and '/static/decks/ex/slides/03.mp4' in html
    assert 'poster="/static/decks/ex/slides/03.jpg"' in html
    data = json.loads(html.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['mode'] == 'archive' and data['session'] is None
    assert data['slides'][0]['hotspots'][0]['body_html'] == '<p><strong>bold</strong></p>'
    assert data['interactions']['q1']['state'] == 'hidden'
    assert '--bg:#111111' in html.replace(' ', '')


def test_archive_404_for_unknown(anon_client, db, settings, tmp_path):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    assert anon_client.get('/presentations/zzz/').status_code == 404


def test_archive_shows_readable_500_for_broken_deck(deck, anon_client, db):
    (deck / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    r = anon_client.get('/presentations/ex/')
    assert r.status_code == 500 and b'expertise' in r.content
