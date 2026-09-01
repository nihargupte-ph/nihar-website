import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.rasters import RASTER_DIR, extract_rasters
from presentations.sanitize import sanitize_svg
from presentations.theme import derive_theme

_VIDEO = {'.mp4', '.webm'}
_PAGE_RE = re.compile(r'^Pages:\s+(\d+)', re.M)


def pdf_to_svgs(pdf, out_dir):
    """Split a PDF into one SVG per page with poppler; returns paths named NN-page-NN.svg."""
    missing = [t for t in ('pdftocairo', 'pdfinfo') if not shutil.which(t)]
    if missing:
        raise CommandError(f"{'/'.join(missing)} (poppler-utils) is required to import PDF exports; install it or export SVGs")
    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True)
    m = _PAGE_RE.search(info.stdout)
    if info.returncode != 0 or not m:
        raise CommandError(f'pdfinfo could not read {pdf}: {info.stderr.strip()}')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for i in range(1, int(m.group(1)) + 1):
        out = out_dir / f'{i:02d}-page-{i:02d}.svg'
        r = subprocess.run(['pdftocairo', '-svg', '-f', str(i), '-l', str(i), str(pdf), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise CommandError(f'pdftocairo failed on page {i} of {pdf}: {r.stderr.strip()}')
        pages.append(out)
    return pages


def collect_sources(src, tmp_dir):
    """`src` is an export folder or a single PDF. Returns files in talk order; PDFs expand to their pages."""
    src = Path(src)
    files = [src] if src.is_file() else sorted(src.iterdir(), key=lambda p: p.name.lower())
    out = []
    for f in files:
        ext = f.suffix.lower()
        if ext == '.pdf':
            out.extend(pdf_to_svgs(f, Path(tmp_dir) / f.stem))
        elif ext in {'.svg'} | _VIDEO:
            out.append(f)
    return out


def slug_from_filename(name):
    stem = Path(name).stem
    stem = re.sub(r'^\d+[\s_-]*', '', stem)          # drop leading number
    s = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')
    return s or 'slide'


def import_sources(src, dest, tmp_dir, start=1):
    """Copy/convert exports into dest/slides as NN-<id>.<ext>; returns (slide entries, written svg paths)."""
    slides, used, svgs = [], set(), []
    for n, f in enumerate(collect_sources(src, tmp_dir), start):
        ext = f.suffix.lower()
        sid = slug_from_filename(f.name)
        base = sid
        k = 2
        while sid in used:
            sid = f'{base}-{k}'
            k += 1
        used.add(sid)
        out = dest / 'slides' / f'{n:02d}-{sid}{ext}'
        if ext == '.svg':
            # rasters out to files first: a whole deck of base64 payloads inlined into one page
            # is what made the corfu archive 20 MB of HTML (see presentations/rasters.py)
            text, _ = extract_rasters(sanitize_svg(f.read_text(encoding='utf-8')),
                                      dest / 'slides' / RASTER_DIR)
            out.write_text(text, encoding='utf-8')
            svgs.append(out)
            slides.append({'id': sid, 'svg': f'slides/{out.name}'})
        else:
            shutil.copy2(f, out)
            entry = {'id': sid, 'video': f'slides/{out.name}'}
            poster = out.with_suffix('.jpg')
            if shutil.which('ffmpeg'):
                r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out), '-frames:v', '1', str(poster)])
                if r.returncode == 0 and poster.exists():
                    entry['poster'] = f'slides/{poster.name}'
            slides.append(entry)
    return slides, svgs


class Command(BaseCommand):
    help = 'Scaffold presentations/decks/<slug>/ (optionally from a PDF, or a folder of SVG/PDF/MP4 exports)'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('--title', required=True)
        parser.add_argument('--from', dest='src', default=None)
        parser.add_argument('--date', default='2026-01-01')

    def handle(self, slug, title, src, date, **opts):
        with tempfile.TemporaryDirectory(prefix='newdeck-') as tmp:
            self._handle(slug, title, src, date, tmp)

    def _handle(self, slug, title, src, date, tmp):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug):
            raise CommandError('slug must be lowercase letters, digits and dashes')
        root = registry.decks_dir()
        dest = root / slug
        if dest.exists():
            self.stderr.write(f'{dest} already exists')
            sys.exit(1)
        template = root / '_template'
        if not template.is_dir():
            raise CommandError('presentations/decks/_template is missing')
        shutil.copytree(template, dest)
        (dest / 'slides').mkdir(exist_ok=True)
        (dest / 'static').mkdir(exist_ok=True)

        slides, svgs = import_sources(src, dest, tmp) if src else ([], [])
        theme = derive_theme(svgs) if svgs else None

        deck = {
            'title': title, 'date': date, 'venue': '', 'subtitle': '', 'transition': 'none',
            'expertise': ['theory', 'data analysis', 'instrumentation', 'not a physicist'],
        }
        if theme:
            deck['theme'] = theme
        deck['interactions'] = []
        deck['slides'] = slides
        header = (dest / 'deck.yaml').read_text() if (dest / 'deck.yaml').exists() else ''
        comments = '\n'.join(l for l in header.splitlines() if l.startswith('#'))
        body = yaml.safe_dump(deck, sort_keys=False, allow_unicode=True)
        (dest / 'deck.yaml').write_text(comments + '\n' + body + _EXAMPLES, encoding='utf-8')
        registry.clear_cache()
        self.stdout.write(f'created {dest} with {len(slides)} slides; edit deck.yaml, then `manage.py checkdecks`')


_EXAMPLES = '''
# --- examples (uncomment and adapt) ---
#footer:                   # bottom bar on every slide: name · affiliation · page number
#  name: Nihar Gupte
#  affiliation: MPI Grav. Phys & UMD
#  bg: '#e8e6e1'           # optional colours (hex)
#  fg: '#444444'
#interactions:
#  - id: q-example
#    type: choice          # choice | numeric | distribution | text
#    prompt: Which one?
#    options: [A, B, C]
#    answer: B
#slides:
#  - id: orbits
#    svg: slides/02-orbits.svg
#    hotspots:
#      - rect: [0.1, 0.1, 0.3, 0.2]
#        title: A thing
#        body: "Markdown **body**"
#        links: [{label: "arXiv", url: "https://arxiv.org/abs/..."}]
#    ask: [q-example]
#    show: [{id: q-example, rect: [0.5, 0.6, 0.45, 0.35]}]
#  - id: orbits-2
#    svg: slides/03-orbits-2.svg
#    continues: true       # reveal step: counts as the same slide number as the one before
#  - id: page
#    html: 03-page.html
#    underlay: slides/03-frame.svg
'''
