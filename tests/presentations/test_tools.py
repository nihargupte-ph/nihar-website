import shutil
import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from presentations.sanitize import sanitize_svg
from presentations.theme import derive_theme

DIRTY = '''<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
<script>alert(1)</script><foreignObject><div>x</div></foreignObject>
<rect width="5" height="5" onclick="evil()" fill="#123456"/>
<a xlink:href="https://evil.example"><text>t</text></a>
<use xlink:href="#ok"/><image href="data:image/png;base64,AAAA"/>
</svg>'''


def test_sanitize_svg():
    out = sanitize_svg(DIRTY)
    assert '<script' not in out and 'foreignObject' not in out and 'onclick' not in out
    assert 'evil.example' not in out and 'href="#ok"' in out and 'data:image/png' in out
    assert 'fill="#123456"' in out and 'viewBox="0 0 10 10"' in out
    assert out.count('<svg') == 1


THEMED = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
<rect width="1920" height="1080" fill="#101820"/>
<rect x="0" y="0" width="600" height="400" fill="#37b49f"/>
<circle cx="900" cy="500" r="100" fill="#e9c46a"/>
<text fill="#f4f1ea" font-family="Montserrat" x="1" y="1">Hi</text>
<text fill="#f4f1ea" style="font-family: 'Inter', sans-serif" x="1" y="2">there</text>
<path d="M0 0" stroke="#e76f51" fill="none"/>
</svg>'''


def test_derive_theme(tmp_path):
    p = tmp_path / 'a.svg'; p.write_text(THEMED)
    t = derive_theme([p])
    assert t['bg'] == '#101820' and t['fg'] == '#f4f1ea'
    assert t['accents'][:2] == ['#37b49f', '#e9c46a'] and '#e76f51' in t['accents']
    assert t['font_display'] == 'Montserrat' and t['font_body'] == 'Inter'


def test_derive_theme_defaults_when_empty(tmp_path):
    p = tmp_path / 'e.svg'; p.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    t = derive_theme([p])
    assert set(t) == {'bg', 'fg', 'accents', 'font_display', 'font_body'} and t['accents']


def test_newdeck_from_dir(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    (tmp_path / 'decks' / '_template' / 'slides').mkdir(parents=True)
    (tmp_path / 'decks' / '_template' / 'static').mkdir()
    (tmp_path / 'decks' / '_template' / 'deck.yaml').write_text('title: x\n')
    src = tmp_path / 'export'; src.mkdir()
    (src / '02-Orbits.svg').write_text(DIRTY)
    (src / '01 Title.svg').write_text(THEMED)
    call_command('newdeck', 'my-talk', '--title', 'My Talk', '--from', str(src), '--date', '2026-10-01')
    d = tmp_path / 'decks' / 'my-talk'
    y = yaml.safe_load((d / 'deck.yaml').read_text())
    assert y['title'] == 'My Talk' and y['date'] == '2026-10-01'
    assert [s['id'] for s in y['slides']] == ['title', 'orbits']
    assert [s['svg'] for s in y['slides']] == ['slides/01-title.svg', 'slides/02-orbits.svg']
    assert y['theme']['bg'] == '#101820'
    assert '<script' not in (d / 'slides' / '02-orbits.svg').read_text()
    assert (d / 'static').is_dir()
    from presentations.schema import load_deck
    assert load_deck(d).title == 'My Talk'
    with pytest.raises(SystemExit):
        call_command('newdeck', 'my-talk', '--title', 'dup')


CASE_HREF = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
<a xlink:HREF="https://evil.example"><text>t</text></a>
<a HREF="javascript:alert(1)"><text>t2</text></a>
<use xlink:href="#ok"/><image href="data:image/png;base64,AAAA"/>
</svg>'''


def test_sanitize_svg_href_case_insensitive_and_javascript_scheme():
    out = sanitize_svg(CASE_HREF)
    assert 'evil.example' not in out
    assert 'javascript:' not in out
    assert 'href="#ok"' in out and 'data:image/png' in out


SMIL = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
<rect width="5" height="5" fill="#123456"><set attributeName="onclick" to="alert(1)"/></rect>
<a><animate attributeName="href" to="javascript:alert(1)"/></a>
<circle cx="1" cy="1" r="1" fill="#654321"/>
</svg>'''


def test_sanitize_svg_drops_smil_animation_tags():
    out = sanitize_svg(SMIL)
    assert '<set' not in out and '<animate' not in out
    assert 'onclick' not in out and 'javascript:' not in out
    assert 'fill="#123456"' in out and 'fill="#654321"' in out


def test_newdeck_missing_template_raises_command_error(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    (tmp_path / 'decks').mkdir(parents=True)
    with pytest.raises(CommandError):
        call_command('newdeck', 'x', '--title', 'X')


def _make_pdf(path, n_pages):
    """Hand-rolled n-page PDF (960x540 pt), each page a filled rectangle."""
    objs = [b'<< /Type /Catalog /Pages 2 0 R >>']
    kids = ' '.join(f'{3 + 2 * i} 0 R' for i in range(n_pages))
    objs.append(f'<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>'.encode())
    for i in range(n_pages):
        content = f'{0.1 * i:.1f} 0.2 0.8 rg 100 100 400 300 re f'.encode()
        objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 960 540] /Contents {4 + 2 * i} 0 R >>'.encode())
        objs.append(b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream')
    out, offsets = b'%PDF-1.4\n', []
    for num, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f'{num} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n'.encode() + b'0000000000 65535 f \n'
    out += b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    path.write_bytes(out)


def _template(tmp_path):
    (tmp_path / 'decks' / '_template' / 'slides').mkdir(parents=True)
    (tmp_path / 'decks' / '_template' / 'static').mkdir()
    (tmp_path / 'decks' / '_template' / 'deck.yaml').write_text('title: x\n')


needs_poppler = pytest.mark.skipif(not (shutil.which('pdftocairo') and shutil.which('pdfinfo')), reason='poppler not installed')


@needs_poppler
def test_newdeck_from_pdf_file_makes_one_svg_slide_per_page(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    _template(tmp_path)
    pdf = tmp_path / 'talk.pdf'
    _make_pdf(pdf, 3)
    call_command('newdeck', 'pdf-talk', '--title', 'PDF Talk', '--from', str(pdf))
    d = tmp_path / 'decks' / 'pdf-talk'
    y = yaml.safe_load((d / 'deck.yaml').read_text())
    assert [s['id'] for s in y['slides']] == ['page-01', 'page-02', 'page-03']
    assert [s['svg'] for s in y['slides']] == ['slides/01-page-01.svg', 'slides/02-page-02.svg', 'slides/03-page-03.svg']
    for s in y['slides']:
        svg = (d / s['svg']).read_text()
        assert svg.lstrip().startswith('<') and '<svg' in svg and '<path' in svg
    from presentations.schema import load_deck
    assert len(load_deck(d).slides) == 3


@needs_poppler
def test_newdeck_dir_expands_pdf_pages_in_place(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    _template(tmp_path)
    src = tmp_path / 'export'; src.mkdir()
    (src / '01-intro.svg').write_text(THEMED)
    _make_pdf(src / '02-body.pdf', 2)
    (src / '03-demo.mp4').write_bytes(b'not really a video')
    call_command('newdeck', 'mixed', '--title', 'Mixed', '--from', str(src))
    y = yaml.safe_load((tmp_path / 'decks' / 'mixed' / 'deck.yaml').read_text())
    assert [s['id'] for s in y['slides']] == ['intro', 'page-01', 'page-02', 'demo']
    assert y['slides'][2]['svg'] == 'slides/03-page-02.svg'
    assert y['slides'][3]['video'] == 'slides/04-demo.mp4'


def test_newdeck_pdf_without_poppler_is_a_clear_error(tmp_path, settings, monkeypatch):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    _template(tmp_path)
    pdf = tmp_path / 'talk.pdf'
    _make_pdf(pdf, 1)
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    with pytest.raises(CommandError, match='pdftocairo'):
        call_command('newdeck', 'nopoppler', '--title', 'X', '--from', str(pdf))


def test_newdeck_defaults_to_no_transition_and_documents_footer(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    _template(tmp_path)
    call_command('newdeck', 'plain', '--title', 'Plain')
    text = (tmp_path / 'decks' / 'plain' / 'deck.yaml').read_text()
    assert yaml.safe_load(text)['transition'] == 'none'
    assert '#footer:' in text and 'affiliation' in text


RESLIDES_YAML = '''# header comment
title: Talk
date: 2026-01-01
expertise: [a, b]
footer: {name: N, affiliation: A}
interactions:
  - id: q1
    type: choice
    prompt: p
    options: [A, B]
slides:
- id: page-01
  svg: slides/01-page-01.svg
  footer: false
  hotspots:
  - rect: [0.1, 0.1, 0.2, 0.2]
    title: Hot
  ask: [q1]
- id: page-02
  svg: slides/02-page-02.svg
  show:
  - id: q1
    rect: [0.1, 0.2, 0.8, 0.6]
- id: page        # my html
  html: page.html
  underlay: slides/frame.svg
- id: vid
  video: slides/04-vid.mp4
# --- examples ---
#slides: nope
'''
OLD_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>OLD</text></svg>'
NEW_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>NEW {}</text></svg>'
PAGE = '{% extends "presentations/slide_base.html" %}{% block slide %}hi{% endblock %}'


def _reslides_deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    d = tmp_path / 'decks' / 'rs'
    (d / 'slides').mkdir(parents=True)
    (d / 'deck.yaml').write_text(RESLIDES_YAML)
    (d / 'page.html').write_text(PAGE)
    for f in ('01-page-01.svg', '02-page-02.svg', 'frame.svg'):
        (d / 'slides' / f).write_text(OLD_SVG)
    (d / 'slides' / '04-vid.mp4').write_bytes(b'v')
    src = tmp_path / 'export'; src.mkdir()
    for i in (1, 2, 3):
        (src / f'{i:02d}-page-{i:02d}.svg').write_text(NEW_SVG.format(i))
    return d, src


def test_reslides_replaces_svgs_and_moves_html_video_to_end(tmp_path, settings, db, capsys):
    d, src = _reslides_deck(tmp_path, settings)
    call_command('reslides', 'rs', '--from', str(src))
    text = (d / 'deck.yaml').read_text()
    y = yaml.safe_load(text)
    assert [s['id'] for s in y['slides']] == ['page-01', 'page-02', 'page-03', 'page', 'vid']
    assert y['slides'][0]['footer'] is False and y['slides'][0]['hotspots'][0]['title'] == 'Hot' and y['slides'][0]['ask'] == ['q1']
    assert y['slides'][1]['show'] == [{'id': 'q1', 'rect': [0.1, 0.2, 0.8, 0.6]}]
    assert y['slides'][2] == {'id': 'page-03', 'svg': 'slides/03-page-03.svg'}
    assert y['slides'][3]['underlay'] == 'slides/frame.svg' and y['slides'][4]['video'] == 'slides/04-vid.mp4'
    assert '# my html' in text and '#slides: nope' in text and '# header comment' in text
    assert 'footer: {name: N, affiliation: A}' in text
    assert 'NEW 1' in (d / 'slides' / '01-page-01.svg').read_text()
    assert 'NEW 3' in (d / 'slides' / '03-page-03.svg').read_text()
    assert (d / 'slides' / 'frame.svg').read_text() == OLD_SVG
    assert (d / 'slides' / '04-vid.mp4').exists()
    assert (d / 'deck.yaml.bak').read_text() == RESLIDES_YAML
    from presentations.schema import load_deck
    assert [s.kind for s in load_deck(d).slides] == ['svg', 'svg', 'svg', 'html', 'video']
    out = capsys.readouterr().out
    assert 'carried' in out and 'page-01' in out


def test_reslides_drops_unmatched_old_svg_config_but_keeps_backup(tmp_path, settings, db, capsys):
    d, src = _reslides_deck(tmp_path, settings)
    (src / '02-page-02.svg').unlink()
    (src / '03-page-03.svg').unlink()
    call_command('reslides', 'rs', '--from', str(src))
    y = yaml.safe_load((d / 'deck.yaml').read_text())
    assert [s['id'] for s in y['slides']] == ['page-01', 'page', 'vid']
    assert not (d / 'slides' / '02-page-02.svg').exists()
    assert 'page-02' in (d / 'deck.yaml.bak').read_text()
    assert 'dropped' in capsys.readouterr().out


def test_reslides_dry_run_changes_nothing(tmp_path, settings, db, capsys):
    d, src = _reslides_deck(tmp_path, settings)
    call_command('reslides', 'rs', '--from', str(src), '--dry-run')
    assert (d / 'deck.yaml').read_text() == RESLIDES_YAML
    assert not (d / 'deck.yaml.bak').exists()
    assert (d / 'slides' / '01-page-01.svg').read_text() == OLD_SVG
    assert not (d / 'slides' / '03-page-03.svg').exists()
    assert 'page-03' in capsys.readouterr().out


def test_reslides_refuses_when_deck_has_a_session_unless_forced(tmp_path, settings, db):
    from presentations.models import Session
    d, src = _reslides_deck(tmp_path, settings)
    Session.objects.create(deck_slug='rs')
    with pytest.raises(CommandError, match='session'):
        call_command('reslides', 'rs', '--from', str(src))
    assert (d / 'deck.yaml').read_text() == RESLIDES_YAML
    call_command('reslides', 'rs', '--from', str(src), '--force')
    assert (d / 'slides' / '03-page-03.svg').exists()
