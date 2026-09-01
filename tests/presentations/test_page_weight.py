"""Canva exports embed every raster as a base64 data URI inside the slide SVG, and `render.py`
inlines every slide of the deck into one document — so the corfu archive page was 20.4 MB of HTML,
14.1 MB of it base64. iOS Safari jettisons the web content process under that weight; focusing the
comment textarea (keyboard + full relayout) was the push that killed the tab.

The rasters therefore have to live in files next to the slide, fetched separately and evictable.
"""
import re
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from django.templatetags.static import static

from presentations import registry
from presentations.rasters import extract_rasters
from presentations.render import inline_svg
from presentations.sanitize import sanitize_svg

CORFU = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu'

# a 1x1 png and a 1x1 gif, as Canva would embed them
PNG_B64 = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5E'
           'rkJggg==')
PNG2_B64 = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5'
            'ErkJggg==')
JPG_B64 = ('/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIx'
           'wcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAA'
           'AAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==')


@pytest.fixture
def deckdir(tmp_path, settings):
    """The reference 4-slide deck (svg, svg, html, video) with real SVG bodies."""
    from .test_schema import make_deck
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    d = make_deck(tmp_path)
    for n in ('01', '02'):
        (d / 'slides' / f'{n}.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">'
            f'<g id="g{n}"><rect width="10" height="10"/></g></svg>')
    (d / 'page.html').write_text('{% extends "presentations/slide_base.html" %}'
                                 '{% block slide %}<h1>Page</h1>{% endblock %}')
    yield d
    registry.clear_cache()


def svg_with(*b64_and_mime):
    imgs = ''.join(f'<image width="4" height="4" xlink:href="data:{m};base64,{b}"/>'
                   for b, m in b64_and_mime)
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 1920 1080">{imgs}<rect width="9" height="9"/></svg>')


# --- the extractor -------------------------------------------------------------------------

def test_extract_rasters_writes_content_hashed_files(tmp_path):
    text, written = extract_rasters(svg_with((PNG_B64, 'image/png'), (JPG_B64, 'image/jpeg')),
                                    tmp_path / 'img')
    assert 'base64' not in text and 'data:image' not in text
    assert len(written) == 2
    assert {p.suffix for p in written} == {'.png', '.jpg'}
    for p in written:
        assert re.fullmatch(r'[0-9a-f]{40}\.(png|jpg)', p.name), p.name
        assert p.is_file() and p.stat().st_size > 0
        assert f'xlink:href="img/{p.name}"' in text
    assert '<rect width="9" height="9"/>' in text          # nothing else touched


def test_extract_rasters_deduplicates_by_content(tmp_path):
    """Several slides reuse the same figure; 96 embeds in corfu are only 60 distinct images."""
    text, written = extract_rasters(svg_with((PNG_B64, 'image/png'), (PNG_B64, 'image/png'),
                                             (PNG2_B64, 'image/png')), tmp_path / 'img')
    assert len(written) == 2                                # one file per distinct payload
    assert len(set(re.findall(r'href="(img/[^"]+)"', text))) == 2
    assert len(re.findall(r'href="img/', text)) == 3        # all three <image>s still have an href


def test_extract_rasters_is_a_no_op_without_rasters(tmp_path):
    src = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    text, written = extract_rasters(src, tmp_path / 'img')
    assert text == src and written == []
    assert not (tmp_path / 'img').exists()


def test_extract_rasters_does_not_re_encode(tmp_path):
    """Straight extraction: the bytes on disk are the bytes that were in the data URI."""
    import base64
    _, written = extract_rasters(svg_with((PNG_B64, 'image/png')), tmp_path / 'img')
    assert written[0].read_bytes() == base64.b64decode(PNG_B64)


# --- the sanitiser has to let the extracted href through ------------------------------------

def test_sanitizer_keeps_extracted_raster_hrefs_and_still_drops_the_web(tmp_path):
    dirty = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
             '<image xlink:href="img/' + 'a' * 40 + '.png"/>'
             '<image xlink:href="../../../etc/passwd"/>'
             '<image xlink:href="https://evil.example/x.png"/>'
             '<image xlink:href="img/../../secret.png"/></svg>')
    out = sanitize_svg(dirty)
    assert f'img/{"a" * 40}.png' in out
    assert 'evil.example' not in out and 'passwd' not in out and 'secret.png' not in out


# --- inlining has to make the href resolve against the page -------------------------------

def test_inline_svg_rewrites_raster_hrefs_to_absolute_static_urls(tmp_path):
    """`inline_svg` drops the SVG into the *page*, so a relative `img/x.png` would resolve against
    /presentations/corfu/ (or /p/<code>/), not against the SVG. It must come out absolute."""
    (tmp_path / 'slides').mkdir()
    p = tmp_path / 'slides' / '01.svg'
    p.write_text(svg_with((PNG_B64, 'image/png')))
    extracted, _ = extract_rasters(p.read_text(), tmp_path / 'slides' / 'img')
    p.write_text(extracted)
    name = re.search(r'href="img/([^"]+)"', extracted).group(1)

    out = inline_svg(p, ns='s1', asset_base='/static/decks/ex/slides/')
    assert f'xlink:href="/static/decks/ex/slides/img/{name}"' in out
    assert 'href="img/' not in out


# --- the corfu deck itself ------------------------------------------------------------------

@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_corfu_slides_carry_no_embedded_rasters():
    fat = [p.name for p in sorted(CORFU.glob('slides/*.svg')) if 'base64' in p.read_text()]
    assert fat == [], f'{len(fat)} corfu slides still embed base64 rasters: {fat[:5]}'


@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_corfu_extracted_rasters_are_on_disk_and_referenced():
    refs = set()
    for p in sorted(CORFU.glob('slides/*.svg')):
        refs |= set(re.findall(r'(?:xlink:)?href="img/([^"]+)"', p.read_text()))
    assert refs, 'corfu slides reference no extracted rasters at all'
    missing = [r for r in refs if not (CORFU / 'slides' / 'img' / r).is_file()]
    assert missing == [], f'referenced but not on disk: {missing}'


@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_corfu_archive_page_fits_in_a_phone(anon_client, db):
    registry.clear_cache()
    r = anon_client.get('/presentations/corfu/')
    assert r.status_code == 200
    mb = len(r.content) / 1e6
    assert b'data:image' not in r.content, 'a slide still ships a base64 raster in the HTML'
    assert mb < 3.0, f'the archive page is {mb:.1f} MB of HTML — iOS Safari will jettison the tab'


@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_corfu_present_page_fits_in_a_phone(staff_client, db):
    registry.clear_cache()
    r = staff_client.get('/presentations/corfu/present/')
    assert r.status_code == 200
    mb = len(r.content) / 1e6
    assert b'data:image' not in r.content
    assert mb < 3.0, f'the present page is {mb:.1f} MB of HTML'


# --- only a window of slides is in the DOM at once ------------------------------------------

@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_archive_ships_only_a_window_of_slide_markup(anon_client, db):
    """52 svg slides of outlined text is 6 MB of markup even with the rasters gone. Only a few
    are inlined; the rest name a URL the browser fetches when the slide is reached.

    Counting `class="slide-svg"` is not the measure: an html slide's `underlay:` carries that class
    too and is always inlined, so the corfu deck's nine underlays (the table of contents and the
    eight expert-BF event slides) show up here without being eager *slides*. Count the svg slides
    that were deferred, and hold the page to a size a phone can carry."""
    registry.clear_cache()
    html = anon_client.get('/presentations/corfu/').content.decode()
    deferred = html.count('data-svg-src=')
    svg_slides = sum(1 for s in registry.get_deck('corfu').slides if s.kind == 'svg')
    assert deferred >= svg_slides - 4, f'only {deferred} of {svg_slides} svg slides deferred'
    assert len(html) / 1e6 < 3.0, f'the archive page is {len(html) / 1e6:.1f} MB of HTML'
    assert re.search(r'data-svg-src="/presentations/corfu/slide/page-40/"', html)


def test_slide_markup_endpoint_matches_what_the_page_would_have_inlined(deckdir, anon_client, db):
    from presentations.render import inline_svg
    r = anon_client.get('/presentations/ex/slide/results/')
    assert r.status_code == 200 and r['Content-Type'].startswith('text/html')
    body = r.content.decode()
    assert body == str(inline_svg(deckdir / 'slides' / '02.svg', ns='results',
                                  asset_base='/static/decks/ex/slides/'))
    assert 'class="slide-svg"' in body and 'results--' in body   # ids namespaced per slide


def test_slide_markup_endpoint_rejects_unknown_and_non_svg_slides(deckdir, anon_client, db):
    assert anon_client.get('/presentations/ex/slide/nope/').status_code == 404
    assert anon_client.get('/presentations/ex/slide/page/').status_code == 404   # html slide
    assert anon_client.get('/presentations/nosuchdeck/slide/x/').status_code == 404


def test_deck_json_carries_the_slide_url(deckdir, anon_client, db):
    import json
    html = anon_client.get('/presentations/ex/').content.decode()
    data = json.loads(html.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['urls']['slide'] == '/presentations/ex/slide/'


# --- the import pipeline does it for new decks ----------------------------------------------

def test_newdeck_extracts_rasters(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    (tmp_path / 'decks' / '_template' / 'slides').mkdir(parents=True)
    (tmp_path / 'decks' / '_template' / 'static').mkdir()
    (tmp_path / 'decks' / '_template' / 'deck.yaml').write_text('title: x\n')
    src = tmp_path / 'export'
    src.mkdir()
    (src / '01-a.svg').write_text(svg_with((PNG_B64, 'image/png')))
    (src / '02-b.svg').write_text(svg_with((PNG_B64, 'image/png'), (PNG2_B64, 'image/png')))
    call_command('newdeck', 'raster-talk', '--title', 'T', '--from', str(src))
    slides = tmp_path / 'decks' / 'raster-talk' / 'slides'
    assert all('base64' not in p.read_text() for p in slides.glob('*.svg'))
    # shared image written once, both slides point at it
    assert len(list((slides / 'img').glob('*.png'))) == 2
    registry.clear_cache()


def test_extractrasters_command_fixes_a_deck_in_place(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    d = tmp_path / 'decks' / 'old'
    (d / 'slides').mkdir(parents=True)
    (d / 'deck.yaml').write_text('title: x\n')
    (d / 'slides' / '01-a.svg').write_text(svg_with((PNG_B64, 'image/png')))
    before = (d / 'slides' / '01-a.svg').read_text()

    call_command('extractrasters', 'old', '--dry-run')
    assert (d / 'slides' / '01-a.svg').read_text() == before, 'dry run wrote something'
    assert not (d / 'slides' / 'img').exists()

    call_command('extractrasters', 'old')
    assert 'base64' not in (d / 'slides' / '01-a.svg').read_text()
    assert len(list((d / 'slides' / 'img').glob('*.png'))) == 1
    registry.clear_cache()


# --- served in DEBUG and after collectstatic ------------------------------------------------

@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_extracted_rasters_are_findable_and_typed():
    """DEBUG's static view and collectstatic both go through the finders; the test runner forces
    DEBUG off, so this checks the finder rather than the /static/ URL (the live-server check is in
    the branch's verification notes)."""
    import mimetypes

    from django.contrib.staticfiles import finders
    names = sorted(p.name for p in (CORFU / 'slides' / 'img').glob('*')) \
        if (CORFU / 'slides' / 'img').is_dir() else []
    assert names, 'no extracted rasters to serve'
    for name in names[:5]:
        found = finders.find(f'decks/corfu/slides/img/{name}')
        assert found, f'{name} is referenced by a slide but no finder serves it'
        assert Path(found) == CORFU / 'slides' / 'img' / name
        assert mimetypes.guess_type(name)[0] in ('image/png', 'image/jpeg')


@pytest.mark.skipif(not CORFU.is_dir(), reason='corfu deck not present')
def test_extracted_rasters_survive_collectstatic(tmp_path, settings):
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = {**settings.STORAGES,
                         'staticfiles': {'BACKEND': 'nihar_website.storage.ForgivingManifestStaticFilesStorage'}}
    call_command('collectstatic', '--noinput', '--clear', verbosity=0)
    src = sorted((CORFU / 'slides' / 'img').glob('*'))
    assert src, 'no extracted rasters'
    for p in src[:5]:
        out = tmp_path / 'decks' / 'corfu' / 'slides' / 'img' / p.name
        assert out.is_file(), f'{p.name} was not collected'
        assert out.read_bytes() == p.read_bytes()
    assert static('decks/corfu/slides/img/') .endswith('/static/decks/corfu/slides/img/')
