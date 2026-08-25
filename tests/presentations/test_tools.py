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
