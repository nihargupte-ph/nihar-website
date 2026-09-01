"""Pull base64 rasters out of exported slide SVGs into content-hashed files beside the slide.

Canva/poppler exports embed every bitmap as a `data:image/png;base64,…` href on an `<image>`.
`render.py` inlines every slide of a deck into one document, so those payloads all land in the
HTML at once — the corfu deck was 20.4 MB of markup, 14.1 MB of it base64, which iOS Safari will
not carry. Written out as files they are fetched (and evicted) one at a time by the browser, and
a content-hashed name is self-busting behind nginx's 30-day `immutable` expiry on /static/.

Bytes are copied straight out of the data URI — no re-encoding, so no quality change.
The href written into the SVG is *relative* (`img/<sha1>.<ext>`): correct when the SVG is fetched
on its own, and rewritten to an absolute /static/ URL by `render.inline_svg` when it is inlined
into a page. `RASTER_HREF` is the shape `sanitize.py` allows through.
"""
import base64
import binascii
import hashlib
import re

RASTER_DIR = 'img'
# what extract_rasters writes, and the only relative href sanitize_svg lets through
RASTER_HREF = re.compile(r'img/[0-9a-f]{40}\.[a-z0-9]{1,5}')
# the same shape, as it appears in an href attribute, for the rewrite at inline time
RASTER_ATTR = re.compile(r'((?:xlink:)?href)\s*=\s*"(img/[0-9a-f]{40}\.[a-z0-9]{1,5})"')

_DATA_URI = re.compile(r'((?:xlink:)?href)\s*=\s*"data:(image/[a-z0-9.+-]+);base64,([^"]*)"', re.I)
_EXT = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/gif': 'gif',
        'image/webp': 'webp', 'image/svg+xml': 'svg', 'image/avif': 'avif'}


def extract_rasters(text, img_dir):
    """Rewrite every embedded raster in `text` to a file in `img_dir`.

    Returns `(new_text, files)` where `files` is the distinct Paths the text now references
    (slides reuse figures, so this is shorter than the number of `<image>`s). `img_dir` is only
    created if there is something to put in it.
    """
    seen = {}

    def repl(m):
        attr, mime, payload = m.group(1), m.group(2).lower(), m.group(3)
        try:
            raw = base64.b64decode(re.sub(r'\s+', '', payload), validate=True)
        except (binascii.Error, ValueError):
            return m.group(0)                       # not decodable: leave it exactly as it was
        if not raw:
            return m.group(0)
        digest = hashlib.sha1(raw).hexdigest()
        name = f'{digest}.{_EXT.get(mime, "bin")}'
        if name not in seen:
            img_dir.mkdir(parents=True, exist_ok=True)
            out = img_dir / name
            if not out.is_file() or out.read_bytes() != raw:
                out.write_bytes(raw)
            seen[name] = out
        return f'{attr}="{RASTER_DIR}/{name}"'

    return _DATA_URI.sub(repl, text), list(seen.values())


def preview_extraction(text):
    """What extract_rasters would produce, writing nothing — for `--dry-run` size reporting."""
    return _DATA_URI.sub(lambda m: f'{m.group(1)}="{RASTER_DIR}/{"0" * 40}.png"', text)


def referenced_rasters(slides_dir):
    """Names under `slides/img/` that some SVG in `slides_dir` still points at."""
    names = set()
    for svg in slides_dir.glob('*.svg'):
        names |= {m.group(2).split('/', 1)[1]
                  for m in RASTER_ATTR.finditer(svg.read_text(encoding='utf-8'))}
    return names


def prune_rasters(slides_dir):
    """Drop extracted images no slide references any more (a re-export replaces every figure).
    Returns the deleted Paths."""
    img_dir = slides_dir / RASTER_DIR
    if not img_dir.is_dir():
        return []
    keep = referenced_rasters(slides_dir)
    gone = [p for p in sorted(img_dir.iterdir()) if p.is_file() and p.name not in keep]
    for p in gone:
        p.unlink()
    return gone
