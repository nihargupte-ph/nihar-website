import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.sanitize import sanitize_svg
from presentations.theme import derive_theme

_VIDEO = {'.mp4', '.webm'}


def slug_from_filename(name):
    stem = Path(name).stem
    stem = re.sub(r'^\d+[\s_-]*', '', stem)          # drop leading number
    s = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')
    return s or 'slide'


class Command(BaseCommand):
    help = 'Scaffold presentations/decks/<slug>/ (optionally from a folder of SVG/MP4 exports)'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('--title', required=True)
        parser.add_argument('--from', dest='src', default=None)
        parser.add_argument('--date', default='2026-01-01')

    def handle(self, slug, title, src, date, **opts):
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

        slides, used, svgs = [], set(), []
        if src:
            files = sorted(Path(src).iterdir(), key=lambda p: p.name.lower())
            n = 0
            for f in files:
                ext = f.suffix.lower()
                if ext not in {'.svg'} | _VIDEO:
                    continue
                n += 1
                sid = slug_from_filename(f.name)
                base = sid
                k = 2
                while sid in used:
                    sid = f'{base}-{k}'
                    k += 1
                used.add(sid)
                out = dest / 'slides' / f'{n:02d}-{sid}{ext}'
                if ext == '.svg':
                    out.write_text(sanitize_svg(f.read_text(encoding='utf-8')), encoding='utf-8')
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
        theme = derive_theme(svgs) if svgs else None

        deck = {
            'title': title, 'date': date, 'subtitle': '', 'transition': 'fade',
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
#  - id: page
#    html: 03-page.html
#    underlay: slides/03-frame.svg
'''
