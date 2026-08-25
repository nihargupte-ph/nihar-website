"""Serves decks/<slug>/static/** at static/decks/<slug>/** and decks/<slug>/slides/** at static/decks/<slug>/slides/**."""
import os

from django.contrib.staticfiles.finders import BaseFinder
from django.core.files.storage import FileSystemStorage

from .registry import decks_dir

_SUBDIRS = {'static': '', 'slides': 'slides'}


class DeckStaticFinder(BaseFinder):
    def _roots(self):
        root = decks_dir()
        if not root.is_dir():
            return
        for d in sorted(root.iterdir()):
            if d.is_dir() and not d.name.startswith('_'):
                for sub, prefix in _SUBDIRS.items():
                    if (d / sub).is_dir():
                        yield d.name, prefix, d / sub

    def check(self, **kwargs):
        return []

    def find(self, path, all=False, **kwargs):
        matches = []
        if path.startswith('decks/'):
            rest = path[len('decks/'):]
            slug, _, rel = rest.partition('/')
            for s, prefix, base in self._roots():
                if s != slug:
                    continue
                if prefix and rel.startswith(prefix + '/'):
                    candidate = base / rel[len(prefix) + 1:]
                elif not prefix and not rel.startswith('slides/'):
                    candidate = base / rel
                else:
                    continue
                if candidate.is_file():
                    matches.append(str(candidate))
        if all:
            return matches
        return matches[0] if matches else None

    def list(self, ignore_patterns):
        for slug, prefix, base in self._roots():
            storage = FileSystemStorage(location=str(base))
            storage.prefix = f'decks/{slug}' + (f'/{prefix}' if prefix else '')
            for dirpath, _dirs, files in os.walk(base):
                for f in files:
                    rel = os.path.relpath(os.path.join(dirpath, f), base)
                    yield rel, storage
