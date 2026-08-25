from pathlib import Path
import pytest
import yaml
from django.core.management import call_command

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
