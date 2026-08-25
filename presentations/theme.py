"""Guess a palette + fonts from SVG exports. Heuristic; newdeck writes the result into deck.yaml for editing."""
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .schema import DEFAULT_THEME

_HEX = re.compile(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
_STYLE_FILL = re.compile(r'fill\s*:\s*([^;]+)')
_STYLE_FONT = re.compile(r"font-family\s*:\s*([^;]+)")


def _norm(c):
    m = _HEX.match((c or '').strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return '#' + h.lower()


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))))


def _lum(h):
    r, g, b = (v / 255 for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _num(v, default=0.0):
    m = re.match(r'[-\d.]+', str(v or ''))
    try:
        return float(m.group(0)) if m else default
    except ValueError:
        return default


def _area(el):
    t = el.tag.rsplit('}', 1)[-1]
    if t == 'rect':
        return _num(el.get('width')) * _num(el.get('height'))
    if t == 'circle':
        return math.pi * _num(el.get('r')) ** 2
    if t == 'ellipse':
        return math.pi * _num(el.get('rx')) * _num(el.get('ry'))
    return 1.0


def _fill_of(el):
    f = el.get('fill')
    if not f:
        m = _STYLE_FILL.search(el.get('style') or '')
        f = m.group(1) if m else None
    return _norm(f)


def _font_of(el):
    f = el.get('font-family')
    if not f:
        m = _STYLE_FONT.search(el.get('style') or '')
        f = m.group(1) if m else None
    if not f:
        return None
    return f.split(',')[0].strip().strip('\'"') or None


def derive_theme(svg_paths):
    area = Counter()
    text_fill = Counter()
    fonts = Counter()
    for p in svg_paths:
        try:
            root = ET.fromstring(Path(p).read_text(encoding='utf-8'))
        except ET.ParseError:
            continue
        for el in root.iter():
            tag = el.tag.rsplit('}', 1)[-1]
            c = _fill_of(el)
            if c and c != 'none':
                area[c] += _area(el)
                if tag in ('text', 'tspan'):
                    text_fill[c] += 1
            s = _norm(el.get('stroke'))
            if s:
                area[s] += 1.0
            f = _font_of(el)
            if f and tag in ('text', 'tspan'):
                fonts[f] += 1
    theme = dict(DEFAULT_THEME)
    if not area:
        return theme
    bg = area.most_common(1)[0][0]
    if text_fill:
        fg = text_fill.most_common(1)[0][0]
    else:
        cands = [c for c, _ in area.most_common(8) if c != bg]
        fg = max(cands, key=lambda c: abs(_lum(c) - _lum(bg))) if cands else DEFAULT_THEME['fg']
    accents = []
    for c, _ in area.most_common():
        if c in (bg, fg) or any(_dist(c, a) < 40 for a in accents) or _dist(c, bg) < 40 or _dist(c, fg) < 40:
            continue
        accents.append(c)
        if len(accents) == 3:
            break
    theme.update({'bg': bg, 'fg': fg, 'accents': accents or list(DEFAULT_THEME['accents'])})
    ranked = [f for f, _ in fonts.most_common()]
    if ranked:
        theme['font_display'] = ranked[0]
        theme['font_body'] = ranked[1] if len(ranked) > 1 else ranked[0]
    return theme
