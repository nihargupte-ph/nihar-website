"""Rewrite an already-imported deck's slide SVGs so their bitmaps live in files, not data URIs.

`newdeck`/`reslides` do this at import time; this is the retrofit for decks imported before that,
and it is idempotent — run it again after hand-editing a slide in Canva and re-exporting one page.
Slide ids and deck.yaml are untouched (the SVG file name does not change), so it is safe on a deck
that has had live sessions.
"""
from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.rasters import RASTER_DIR, extract_rasters, preview_extraction, prune_rasters


class Command(BaseCommand):
    help = 'Extract base64 rasters out of a deck\'s slide SVGs into slides/img/<sha1>.<ext>'

    def add_arguments(self, parser):
        parser.add_argument('slugs', nargs='*', help='deck slugs (default: every deck)')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--prune', action='store_true',
                            help='also delete extracted images no slide references any more')

    def handle(self, slugs, dry_run, prune, **opts):
        root = registry.decks_dir()
        if slugs:
            for s in slugs:
                if not (root / s / 'deck.yaml').is_file():
                    raise CommandError(f'{root / s / "deck.yaml"} not found')
            targets = [root / s for s in slugs]
        else:
            targets = [d for d in sorted(root.iterdir()) if (d / 'deck.yaml').is_file()]

        for deck in targets:
            slides = deck / 'slides'
            if not slides.is_dir():
                continue
            saved = files = touched = 0
            names = set()
            for svg in sorted(slides.glob('*.svg')):
                src = svg.read_text(encoding='utf-8')
                text, written = ((preview_extraction(src), []) if dry_run
                                 else extract_rasters(src, slides / RASTER_DIR))
                if text == src:
                    continue
                touched += 1
                saved += len(src) - len(text)
                names |= {p.name for p in written}
                if not dry_run:
                    svg.write_text(text, encoding='utf-8')
            files = len(names)
            gone = prune_rasters(slides) if prune and not dry_run else []
            note = f' (pruned {len(gone)})' if gone else ''
            verb = 'would shrink' if dry_run else 'shrank'
            self.stdout.write(f'{deck.name}: {verb} {touched} slides by {saved / 1e6:.1f} MB '
                              f'into {files} image files{note}')
        if dry_run:
            self.stdout.write('dry run: nothing written')
        else:
            registry.clear_cache()
