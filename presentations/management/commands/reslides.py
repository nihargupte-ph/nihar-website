"""Re-import the SVG layer of an existing deck from a fresh PDF/export, keeping everything authored by hand."""
import re
import shutil
import tempfile
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.models import Session
from presentations.rasters import RASTER_DIR, prune_rasters

from .newdeck import import_sources

_TOP_KEY = re.compile(r'^[A-Za-z_][\w-]*\s*:')


def split_slides_block(text):
    """→ (before, entries, after). `entries` are the verbatim text chunks of each top-level `- id:` item under
    `slides:`; comments inside chunks stay with them; trailing column-0 comments go to `after`."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if re.match(r'^slides\s*:\s*(#.*)?$', l)), None)
    if start is None:
        raise CommandError('deck.yaml has no top-level `slides:` block')
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _TOP_KEY.match(lines[i]):
            end = i
            break
    block = lines[start + 1:end]
    first = next((l for l in block if re.match(r'^\s*-\s+id\s*:', l)), None)
    if first is None:
        raise CommandError('slides: block has no `- id:` entries')
    indent = first[:len(first) - len(first.lstrip())]
    item = re.compile(r'^' + re.escape(indent) + r'-\s+id\s*:')
    entries, cur = [], []
    for l in block:
        if item.match(l):
            if cur:
                entries.append(''.join(cur))
            cur = [l]
        else:
            cur.append(l)
    if cur:
        entries.append(''.join(cur))
    # peel trailing column-0 comment/blank lines off the last entry
    tail = []
    last = entries[-1].splitlines(keepends=True)
    while last and (last[-1].startswith('#') or not last[-1].strip()):
        tail.insert(0, last.pop())
    entries[-1] = ''.join(last)
    return ''.join(lines[:start + 1]), entries, ''.join(tail) + ''.join(lines[end:]), indent


def dump_entries(entries, indent):
    text = yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, default_flow_style=None)
    return ''.join(indent + l for l in text.splitlines(keepends=True))


class Command(BaseCommand):
    help = ('Replace all svg slides of presentations/decks/<slug>/ with a fresh import (PDF or export folder); '
            'html and video slides are kept verbatim and moved to the end of slides: for you to reorder.')

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('--from', dest='src', required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true', help='proceed even if the deck has had a session')

    def handle(self, slug, src, dry_run, force, **opts):
        dest = registry.decks_dir() / slug
        yaml_path = dest / 'deck.yaml'
        if not yaml_path.is_file():
            raise CommandError(f'{yaml_path} not found')
        if not force and Session.objects.filter(deck_slug=slug).exists():
            raise CommandError(f"deck '{slug}' has had a session; slide ids are persistence keys "
                               f"(comments, current slide). Re-run with --force if you accept that.")
        original = yaml_path.read_text(encoding='utf-8')
        before, chunks, after, indent = split_slides_block(original)

        old_svg, kept = {}, []
        for chunk in chunks:
            entry = yaml.safe_load(chunk)[0]
            if 'svg' in entry:
                old_svg[entry['id']] = entry
            else:
                kept.append(chunk)
        old_svg_files = [dest / e['svg'] for e in old_svg.values()]

        with tempfile.TemporaryDirectory(prefix='reslides-') as tmp:
            stage = Path(tmp) / 'stage'
            (stage / 'slides').mkdir(parents=True)
            new_entries, _ = import_sources(src, stage, tmp)
            carried, dropped = [], []
            for e in new_entries:
                old = old_svg.pop(e['id'], None)
                if old:
                    extras = {k: v for k, v in old.items() if k not in ('id', 'svg')}
                    if extras:
                        e.update(extras)
                        carried.append(e['id'])
            dropped = [i for i, e in old_svg.items() if any(k not in ('id', 'svg') for k in e)]
            unmatched = list(old_svg)

            new_files = sorted(p.name for p in (stage / 'slides').iterdir() if p.is_file())
            self.stdout.write(f"import: {len(new_entries)} slides from {src}: {', '.join(e['id'] for e in new_entries)}")
            self.stdout.write(f"kept at end: {len(kept)} html/video entries")
            self.stdout.write(f"carried hotspots/ask/show/footer for: {', '.join(carried) or '-'}")
            self.stdout.write(f"old svg slides with no match in new import: {', '.join(unmatched) or '-'}"
                              + (f" (dropped authored config for: {', '.join(dropped)}; it is in deck.yaml.bak)" if dropped else ''))
            if dry_run:
                self.stdout.write('dry run: nothing written')
                return

            shutil.copy2(yaml_path, yaml_path.with_suffix('.yaml.bak'))
            for f in old_svg_files:
                if f.is_file():
                    f.unlink()
            for name in new_files:
                shutil.copy2(stage / 'slides' / name, dest / 'slides' / name)
            staged_img = stage / 'slides' / RASTER_DIR
            if staged_img.is_dir():
                (dest / 'slides' / RASTER_DIR).mkdir(exist_ok=True)
                for p in staged_img.iterdir():
                    shutil.copy2(p, dest / 'slides' / RASTER_DIR / p.name)
        # extracted rasters are content-hashed, so the ones the new export doesn't use are dead
        prune_rasters(dest / 'slides')

        body = dump_entries(new_entries, indent) + ''.join(kept)
        yaml_path.write_text(before + body + after, encoding='utf-8')
        registry.clear_cache()
        self.stdout.write(f'rewrote {yaml_path} (backup: deck.yaml.bak); reorder slides: then `manage.py checkdecks`')
