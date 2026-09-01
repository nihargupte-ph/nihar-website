import json
import posixpath
import re
from pathlib import Path

from django.template import engines
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .rasters import RASTER_ATTR
from .textutil import render_markdown

_XML_DECL = re.compile(r'<\?xml[^>]*\?>', re.S)
_DOCTYPE = re.compile(r'<!DOCTYPE[^>]*>', re.S | re.I)
_ROOT = re.compile(r'<svg\b([^>]*)>', re.S)
_ATTR = re.compile(r'\s(width|height|preserveAspectRatio)\s*=\s*"[^"]*"')
_NUM = re.compile(r'[\d.]+')
_ID = re.compile(r'\sid="([^"]+)"')
_REF = re.compile(r"(href=\"#|url\(#|url\('#|url\(\"#)([^\"'\)\s]+)")


def namespace_ids(text, ns):
    """Prefix every id (and #id reference) with `ns--`. Exports reuse ids like glyph0-1 on every page,
    and all slides of a deck are inlined into one document, so unprefixed ids would resolve to the first slide's."""
    ids = set(_ID.findall(text))
    if not ids:
        return text
    text = _ID.sub(lambda m: f' id="{ns}--{m.group(1)}"', text)
    return _REF.sub(lambda m: f'{m.group(1)}{ns}--{m.group(2)}' if m.group(2) in ids else m.group(0), text)


def inline_svg(path, ns=None, asset_base=None):
    """`asset_base` is the /static/ URL of the directory the SVG lives in. Extracted rasters are
    referenced relatively (`img/<sha1>.png`) so the SVG works when fetched on its own, but this
    markup is inlined into the *page* — where a relative href would resolve against
    /presentations/<slug>/ — so those hrefs are made absolute here."""
    text = Path(path).read_text(encoding='utf-8')
    text = _DOCTYPE.sub('', _XML_DECL.sub('', text)).strip()
    if asset_base:
        text = RASTER_ATTR.sub(lambda m: f'{m.group(1)}="{asset_base}{m.group(2)}"', text)
    if ns:
        text = namespace_ids(text, ns)
    m = _ROOT.search(text)
    if not m:
        return mark_safe('')
    attrs = m.group(1)
    if 'viewBox' not in attrs:
        w = re.search(r'\swidth="([^"]+)"', attrs)
        h = re.search(r'\sheight="([^"]+)"', attrs)
        wv = _NUM.search(w.group(1)).group(0) if w and _NUM.search(w.group(1)) else '1920'
        hv = _NUM.search(h.group(1)).group(0) if h and _NUM.search(h.group(1)) else '1080'
        attrs += f' viewBox="0 0 {wv} {hv}"'
    attrs = _ATTR.sub('', attrs)
    attrs += ' width="100%" height="100%" preserveAspectRatio="xMidYMid meet" class="slide-svg"'
    text = text[:m.start()] + f'<svg{attrs}>' + text[m.end():]
    return mark_safe(text)


def slide_static_url(deck, rel):
    return static(f'decks/{deck.slug}/{rel}')


def asset_base(deck, rel):
    """/static/ URL of the directory `rel` (a deck-relative file) sits in."""
    parent = posixpath.dirname(str(rel).replace('\\', '/'))
    return static(f'decks/{deck.slug}/' + (f'{parent}/' if parent else ''))


def render_html_slide(deck, slide, request):
    src = (deck.dir / slide.path).read_text(encoding='utf-8')
    tpl = engines['django'].from_string(src)
    return tpl.render({
        'deck': deck, 'slide': slide, 'theme': deck.theme,
        'deck_static': static(f'decks/{deck.slug}/'),
    }, request)


# How many svg slides either side of the first one ship their markup in the page. A deck of
# outlined-text exports is ~120 KB of markup per slide, and all 56 corfu slides at once was 6 MB
# even after the rasters came out — enough to get the tab jettisoned on an iPhone. The rest name
# `slide_url` and `stage.js` fetches (and drops again) them as the deck is walked.
EAGER_SLIDES = 2


def slide_markup_url(deck, slide):
    return f'/presentations/{deck.slug}/slide/{slide.id}/'


def rendered_slides(deck, request):
    out = []
    for n, s in enumerate(deck.slides):
        row = {'slide': s, 'index': n, 'markup': '', 'video_url': '', 'poster_url': '', 'underlay': '',
               'svg_url': '', 'footer': bool(deck.footer and s.footer)}
        if s.kind == 'svg':
            if n <= EAGER_SLIDES:
                row['markup'] = inline_svg(deck.dir / s.path, ns=s.id, asset_base=asset_base(deck, s.path))
            else:
                row['svg_url'] = slide_markup_url(deck, s)
        elif s.kind == 'html':
            row['markup'] = mark_safe(render_html_slide(deck, s, request))
            if s.underlay:
                row['underlay'] = inline_svg(deck.dir / s.underlay, ns=f'{s.id}-u',
                                             asset_base=asset_base(deck, s.underlay))
        else:
            row['video_url'] = slide_static_url(deck, s.path)
            row['poster_url'] = slide_static_url(deck, s.poster) if s.poster else ''
        out.append(row)
    return out


def _is_light(hex_colour):
    h = hex_colour.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5


# Surface tokens the chrome uses so panels/borders/buttons read on both dark and light decks.
_DARK_SURFACES = {'--line': 'rgba(255,255,255,.15)', '--line-soft': 'rgba(255,255,255,.08)', '--surface': 'rgba(255,255,255,.12)',
                  '--panel': 'rgba(10,10,10,.85)', '--panel-solid': '#151515', '--field': 'rgba(0,0,0,.4)', '--on-accent': '#000',
                  '--shadow': '0 10px 40px rgba(0,0,0,.5)', '--scrim': 'rgba(0,0,0,.45)'}
_LIGHT_SURFACES = {'--line': 'rgba(0,0,0,.14)', '--line-soft': 'rgba(0,0,0,.07)', '--surface': 'rgba(0,0,0,.07)',
                   '--panel': 'rgba(255,255,255,.92)', '--panel-solid': '#ffffff', '--field': 'rgba(0,0,0,.04)', '--on-accent': '#fff',
                   '--shadow': '0 10px 40px rgba(0,0,0,.18)', '--scrim': 'rgba(255,255,255,.75)'}


def theme_css(theme):
    parts = [f"--bg:{theme['bg']}", f"--fg:{theme['fg']}"]
    for i, a in enumerate(theme['accents'], 1):
        parts.append(f'--accent-{i}:{a}')
    parts.append(f"--accent:{theme['accents'][0]}")
    parts.append(f"--font-display:'{theme['font_display']}',serif")
    parts.append(f"--font-body:'{theme['font_body']}',sans-serif")
    surfaces = _LIGHT_SURFACES if _is_light(theme['bg']) else _DARK_SURFACES
    parts.extend(f'{k}:{v}' for k, v in surfaces.items())
    return ';'.join(parts)


def deck_json(deck, session, mode, urls):
    states = session.interaction_states if session else {}
    return {
        'slug': deck.slug, 'title': deck.title, 'mode': mode, 'transition': deck.transition,
        'theme': deck.theme, 'expertise': deck.expertise, 'page_count': deck.page_count,
        'slides': [{
            'id': s.id, 'kind': s.kind, 'index': n, 'number': s.number,
            'hotspots': [{'rect': h.rect, 'title': h.title, 'body_html': render_markdown(h.body), 'links': h.links}
                         for h in s.hotspots],
            'ask': s.ask, 'show': [{'id': r.id, 'rect': r.rect} for r in s.show],
        } for n, s in enumerate(deck.slides)],
        'interactions': {i.id: {'type': i.type, 'config': i.config, 'state': states.get(i.id, 'hidden')}
                         for i in deck.interactions},
        'session': ({'code': session.join_code, 'locked': session.is_locked, 'current': session.current_slide_id,
                     'version': session.version} if session else None),
        'urls': {'slide': f'/presentations/{deck.slug}/slide/', **urls},
    }


def deck_json_script(data):
    return mark_safe(json.dumps(data).replace('</', '<\\/'))
