#!/usr/bin/env python3
"""Rewrite the venue/date line of the title slide (slides/01-page-01.svg).

The Canva text is outlines, so the line is recomposed from glyphs already in the NBI title page
(same font and size). A letter that appears on neither of its two small-text lines cannot be used,
and the script says so.  Usage: python tools/titleline.py "Seminar    Princeton University   November 2026"
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SRC = HERE.parent / 'nbi' / 'slides' / '01-page-01.svg'
DST = HERE / 'slides' / '01-page-01.svg'
AFFIL = 'Max Planck Institute for Gravitational Physics and University of Maryland'
OLD = 'Seminar{}Niels Bohr Institute{}October 2026'
USE = r'<g style="[^"]*">\s*<use xlink:href="#(glyph2-\d+)" x="([\d.]+)" y="([\d.]+)" />\s*</g>\s*'


def main(text):
    svg = SRC.read_text()
    lines = {}
    for m in re.finditer(USE, svg):
        lines.setdefault(m[3], []).append(m)
    (y1, l1), (y2, l2) = sorted(lines.items(), key=lambda kv: float(kv[0]))
    known = [(AFFIL, l1)]
    # the old line's runs of spaces between its three parts are not recorded anywhere: find them
    fits = [OLD.format(' ' * a, ' ' * b) for a in range(1, 12) for b in range(1, 12)
            if len(OLD.format(' ' * a, ' ' * b)) == len(l2)]
    glyph, advance = {}, {}
    for chars, line in [known[0]]:
        for c, m in zip(chars, line):
            glyph[c] = m[1]
    fits = [f for f in fits if all(glyph.get(c, m[1]) == m[1] for c, m in zip(f, l2))]
    if not fits:
        raise SystemExit('could not read the old line')
    known.append((fits[0], l2))
    for chars, line in known:
        for i, (c, m) in enumerate(zip(chars, line)):
            glyph[c] = m[1]
            if i + 1 < len(line):
                advance.setdefault(c, float(line[i + 1][2]) - float(m[2]))
    # a line's last glyph has no successor to measure against; '6' ends the old line
    advance.setdefault('6', advance['0'])
    missing = sorted(set(text) - set(glyph))
    if missing:
        raise SystemExit(f'no outlines for {missing}: reword, or re-export the page from Canva')
    fill = re.search(r'<g style="([^"]*)">', l2[0][0])[1]
    x0, x1 = float(l2[0][2]), float(l2[-1][2])
    centre = (x0 + x1 + advance[known[1][0][-1]]) / 2
    width = sum(advance[c] for c in text)
    x, out = centre - width / 2, []
    for c in text:
        out.append(f'<g style="{fill}">\n  <use xlink:href="#{glyph[c]}" x="{x:.6f}" y="{y2}" />\n</g>\n')
        x += advance[c]
    start, end = l2[0].start(), l2[-1].end()
    DST.write_text(svg[:start] + ''.join(out) + svg[end:])
    print(f'wrote {DST.name}: {text!r} ({width:.1f}pt wide, centred on {centre:.1f})')


if __name__ == '__main__':
    main(sys.argv[1])
