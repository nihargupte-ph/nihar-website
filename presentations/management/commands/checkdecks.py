import sys

from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.schema import DeckError, load_deck
from presentations import interactions


class Command(BaseCommand):
    help = 'Validate every presentations/decks/*/deck.yaml'

    def handle(self, *args, **options):
        root = registry.decks_dir()
        if not root.is_dir():
            raise CommandError('decks dir missing')
        bad = 0
        for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')):
            if not registry.valid_slug(d.name):
                bad += 1
                self.stderr.write(f'{d.name}: ERROR folder name must match [a-z0-9][a-z0-9-]*')
                continue
            try:
                deck = load_deck(d, interaction_validator=interactions.validate)
            except DeckError as e:
                bad += 1
                self.stderr.write(f'{d.name}: ERROR {e.message}')
                continue
            self.stdout.write(f'{d.name}: ok ({len(deck.slides)} slides, {len(deck.interactions)} interactions)')
            for w in deck.warnings:
                self.stdout.write(f'  warning: {w}')
        if bad:
            sys.exit(1)
