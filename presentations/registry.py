"""Discovers presentations/decks/*/deck.yaml. Cached per process; DEBUG re-reads on mtime change."""
import logging
import re
from pathlib import Path

from django.conf import settings
from django.http import Http404

from . import interactions
from .schema import DeckError, load_deck

log = logging.getLogger(__name__)
_cache = {}   # slug -> (mtime, Deck)

SLUG_RE = re.compile(r'[a-z0-9][a-z0-9-]*')   # same rule newdeck enforces; a folder that breaks it is not a deck


def valid_slug(name):
    return bool(SLUG_RE.fullmatch(name))


def decks_dir():
    return Path(settings.PRESENTATIONS_DECKS_DIR)


def clear_cache():
    _cache.clear()


def _load(slug):
    d = decks_dir() / slug
    yaml_path = d / 'deck.yaml'
    if not d.is_dir() or not yaml_path.is_file() or not valid_slug(slug):
        raise Http404(f"No presentation '{slug}'")
    mtime = yaml_path.stat().st_mtime
    hit = _cache.get(slug)
    if hit and (hit[0] == mtime or not settings.DEBUG):
        return hit[1]
    deck = load_deck(d, interaction_validator=interactions.validate)
    for w in deck.warnings:
        log.warning('deck %s: %s', slug, w)
    _cache[slug] = (mtime, deck)
    return deck


def get_deck(slug):
    return _load(slug)


def all_decks():
    out = []
    root = decks_dir()
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir() and valid_slug(p.name)):
        try:
            out.append(_load(d.name))
        except (DeckError, Http404) as e:
            log.error('skipping deck %s: %s', d.name, e)
    out.sort(key=lambda dk: dk.date, reverse=True)
    return out
