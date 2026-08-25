import json
import re
from pathlib import Path

from django.template import engines
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .textutil import render_markdown

_XML_DECL = re.compile(r'<\?xml[^>]*\?>', re.S)
_DOCTYPE = re.compile(r'<!DOCTYPE[^>]*>', re.S | re.I)
_ROOT = re.compile(r'<svg\b([^>]*)>', re.S)
_ATTR = re.compile(r'\s(width|height|preserveAspectRatio)\s*=\s*"[^"]*"')
_NUM = re.compile(r'[\d.]+')


def inline_svg(path):
    text = Path(path).read_text(encoding='utf-8')
    text = _DOCTYPE.sub('', _XML_DECL.sub('', text)).strip()
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


def render_html_slide(deck, slide, request):
    src = (deck.dir / slide.path).read_text(encoding='utf-8')
    tpl = engines['django'].from_string(src)
    return tpl.render({
        'deck': deck, 'slide': slide, 'theme': deck.theme,
        'deck_static': static(f'decks/{deck.slug}/'),
    }, request)


def rendered_slides(deck, request):
    out = []
    for n, s in enumerate(deck.slides):
        row = {'slide': s, 'index': n, 'markup': '', 'video_url': '', 'poster_url': '', 'underlay': ''}
        if s.kind == 'svg':
            row['markup'] = inline_svg(deck.dir / s.path)
        elif s.kind == 'html':
            row['markup'] = mark_safe(render_html_slide(deck, s, request))
            if s.underlay:
                row['underlay'] = inline_svg(deck.dir / s.underlay)
        else:
            row['video_url'] = slide_static_url(deck, s.path)
            row['poster_url'] = slide_static_url(deck, s.poster) if s.poster else ''
        out.append(row)
    return out


def theme_css(theme):
    parts = [f"--bg:{theme['bg']}", f"--fg:{theme['fg']}"]
    for i, a in enumerate(theme['accents'], 1):
        parts.append(f'--accent-{i}:{a}')
    parts.append(f"--accent:{theme['accents'][0]}")
    parts.append(f"--font-display:'{theme['font_display']}',sans-serif")
    parts.append(f"--font-body:'{theme['font_body']}',sans-serif")
    return ';'.join(parts)


def deck_json(deck, session, mode, urls):
    states = session.interaction_states if session else {}
    return {
        'slug': deck.slug, 'title': deck.title, 'mode': mode, 'transition': deck.transition,
        'theme': deck.theme, 'expertise': deck.expertise,
        'slides': [{
            'id': s.id, 'kind': s.kind, 'index': n,
            'hotspots': [{'rect': h.rect, 'title': h.title, 'body_html': render_markdown(h.body), 'links': h.links}
                         for h in s.hotspots],
            'ask': s.ask, 'show': [{'id': r.id, 'rect': r.rect} for r in s.show],
        } for n, s in enumerate(deck.slides)],
        'interactions': {i.id: {'type': i.type, 'config': i.config, 'state': states.get(i.id, 'hidden')}
                         for i in deck.interactions},
        'session': ({'code': session.join_code, 'locked': session.is_locked, 'current': session.current_slide_id,
                     'version': session.version} if session else None),
        'urls': urls,
    }


def deck_json_script(data):
    return mark_safe(json.dumps(data).replace('</', '<\\/'))
