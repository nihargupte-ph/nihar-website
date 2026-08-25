import re
import json
import pytest
from presentations import registry
from .test_schema import make_deck

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


GLYPHS = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
<defs><symbol id="glyph0-1"><path d="M {d} 0 L 1 1"/></symbol><clipPath id="clip1"><rect width="5" height="5"/></clipPath>
<mask id="mask0"><rect width="1" height="1"/></mask></defs>
<g clip-path="url(#clip1)" style="mask:url(#mask0)"><use xlink:href="#glyph0-1" x="1"/><use href="#glyph0-1" x="2"/></g>
</svg>'''


def test_inline_svg_namespaces_ids_and_references(deck):
    # pdftocairo (and Canva) reuse the same ids on every page; inlined into one document they'd collide
    from presentations.render import inline_svg
    (deck / 'slides' / 'g.svg').write_text(GLYPHS.format(d=3))
    out = inline_svg(deck / 'slides' / 'g.svg', ns='intro')
    assert 'id="intro--glyph0-1"' in out and 'id="intro--clip1"' in out and 'id="intro--mask0"' in out
    assert 'xlink:href="#intro--glyph0-1"' in out and 'href="#intro--glyph0-1" x="2"' in out
    assert 'clip-path="url(#intro--clip1)"' in out and 'mask:url(#intro--mask0)' in out
    import re
    assert not re.search(r'(id="|#)(glyph0-1|clip1|mask0)\b', out)


def test_page_inlines_same_ids_on_two_slides_without_collision(deck, anon_client, db):
    (deck / 'slides' / '01.svg').write_text(GLYPHS.format(d=3))
    (deck / 'slides' / '02.svg').write_text(GLYPHS.format(d=7))
    html = anon_client.get('/presentations/ex/').content.decode()
    import re
    ids = re.findall(r'id="([^"]*glyph0-1)"', html)
    assert len(ids) == 2 and len(set(ids)) == 2, ids
    for i in ids:
        assert html.count(f'href="#{i}"') == 2


def test_footer_bar_on_every_slide_except_opted_out(deck, anon_client, db):
    y = (deck / 'deck.yaml').read_text().replace('interactions:', 'footer: {name: Nihar Gupte, affiliation: MPI & UMD, bg: "#abcdef"}\ninteractions:')
    y = y.replace('    html: page.html', '    html: page.html\n    footer: false')
    (deck / 'deck.yaml').write_text(y)
    registry.clear_cache()
    html = anon_client.get('/presentations/ex/').content.decode()
    assert html.count('class="slide-footer"') == 3
    assert 'Nihar Gupte' in html and 'MPI &amp; UMD' in html
    assert '1 / 4' in html and '2 / 4' in html and '4 / 4' in html and '3 / 4' not in html
    assert 'background:#abcdef;color:#444444' in html


def test_no_footer_bar_without_footer_config(deck, anon_client, db):
    html = anon_client.get('/presentations/ex/').content.decode()
    assert 'slide-footer' not in html


def test_counters_use_logical_numbers_for_reveal_steps(deck, anon_client, db):
    y = (deck / 'deck.yaml').read_text().replace('interactions:', 'footer: {name: N, affiliation: A}\ninteractions:')
    y = y.replace('    svg: slides/02.svg', '    svg: slides/02.svg\n    continues: true')
    (deck / 'deck.yaml').write_text(y)
    registry.clear_cache()
    html = anon_client.get('/presentations/ex/').content.decode()
    footers = re.findall(r'<span>(\d+ / \d+)</span></div>', html)
    assert footers == ['1 / 3', '1 / 3', '2 / 3', '3 / 3']
    assert '<span id="slide-num">1</span> / 3' in html
    data = json.loads(html.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert [s['number'] for s in data['slides']] == [1, 1, 2, 3] and data['page_count'] == 3
