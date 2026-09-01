"""nginx serves /static/ as `Cache-Control: public, immutable` for 30 days (90 for svg), behind
Cloudflare. With unhashed filenames that pins every visitor — and the edge — to whatever version
they first loaded: a fixed comments.js was still being served to a phone a day after it shipped
(`cf-cache-status: HIT`, `age: 4980`), and `immutable` means the browser will not even revalidate.
So a static file's URL has to change when its contents do."""
import re

import pytest
from django.core.management import call_command
from django.templatetags.static import static


PROD_STORAGE = 'nihar_website.storage.ForgivingManifestStaticFilesStorage'


@pytest.fixture
def collected(tmp_path, settings):
    """Collect the way production does. The dev .env sets DEBUG=True, so settings picks the plain
    storage there; this pins down what the deploy actually gets."""
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = {**settings.STORAGES, 'staticfiles': {'BACKEND': PROD_STORAGE}}
    call_command('collectstatic', '--noinput', '--clear', verbosity=0)
    return tmp_path


def test_settings_use_the_hashing_storage_off_debug():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / 'nihar_website' / 'settings.py').read_text()
    assert PROD_STORAGE in src and 'if DEBUG' in src


def test_engine_assets_get_a_content_hashed_name(collected):
    for rel in ('presentations/js/comments.js', 'presentations/js/phone.js',
                'presentations/css/deck.css'):
        stem, _, ext = rel.rpartition('.')
        hashed = list(collected.glob(f'{stem}.*.{ext}'))
        assert hashed, f'{rel} was collected without a content hash — a fix can never reach a phone'
        assert re.fullmatch(r'[0-9a-f]{12}', hashed[0].name.split('.')[-2])


def test_static_tag_points_at_the_hashed_copy(collected):
    assert re.search(r'/comments\.[0-9a-f]{12}\.js$', static('presentations/js/comments.js'))


def test_deck_slides_keep_working_off_the_unhashed_prefix(collected):
    """render.py hands slides a `deck_static` *directory* prefix and the deck templates concatenate
    onto it, so those URLs stay unhashed. The prefix must resolve rather than raise, and the plain
    copy must still be on disk for nginx to serve. (Deck assets therefore still ride nginx's 30-day
    immutable expiry — see the note in nihar_website/storage.py.)"""
    assert static('decks/corfu/').endswith('/static/decks/corfu/')
    assert (collected / 'decks' / 'corfu' / 'toc' / 'toc.js').is_file()
