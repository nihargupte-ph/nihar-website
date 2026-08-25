import pytest
from django.http import Http404

from presentations import registry
from presentations.schema import DeckError
from .test_schema import make_deck, GOOD


@pytest.fixture
def decks(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield tmp_path
    registry.clear_cache()


def test_all_decks_sorted_and_skips_underscore(decks):
    make_deck(decks).rename(decks / 'older')
    (decks / 'older' / 'deck.yaml').write_text(GOOD.replace('2026-09-12', '2025-01-01'))
    make_deck(decks)  # 'ex', 2026-09-12
    (decks / '_template').mkdir()
    (decks / '_template' / 'deck.yaml').write_text('title: x')
    assert [d.slug for d in registry.all_decks()] == ['ex', 'older']


def test_get_deck_404_and_error(decks):
    with pytest.raises(Http404):
        registry.get_deck('nope')
    make_deck(decks)
    (decks / 'ex' / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    with pytest.raises(DeckError):
        registry.get_deck('ex')


def test_all_decks_isolates_broken_deck(decks):
    make_deck(decks)
    (decks / 'bad').mkdir()
    (decks / 'bad' / 'deck.yaml').write_text('title: broken\n')
    slugs = [d.slug for d in registry.all_decks()]
    assert slugs == ['ex']


def test_checkdecks_command(decks, capsys):
    from django.core.management import call_command
    make_deck(decks)
    call_command('checkdecks')
    out = capsys.readouterr().out
    assert 'ex: ok' in out
    (decks / 'bad').mkdir()
    (decks / 'bad' / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    with pytest.raises(SystemExit):
        call_command('checkdecks')


def test_bad_folder_name_is_skipped_not_a_500(decks, anon_client, db):
    """A folder name that isn't a valid slug can't be a deck URL, so it must never reach reverse()."""
    make_deck(decks).rename(decks / 'bad name')
    make_deck(decks)   # 'ex'
    registry.clear_cache()
    assert [d.slug for d in registry.all_decks()] == ['ex']
    with pytest.raises(Http404):
        registry.get_deck('bad name')
    r = anon_client.get('/presentations/')
    assert r.status_code == 200 and b'bad name' not in r.content

    from presentations.finders import DeckStaticFinder
    assert DeckStaticFinder().find('decks/bad name/slides/01.svg') is None

    from django.core.management import call_command
    with pytest.raises(SystemExit):
        call_command('checkdecks')


def test_index_page_lists_decks(decks, anon_client, db):
    make_deck(decks)
    r = anon_client.get('/presentations/')
    assert r.status_code == 200
    assert b'Example' in r.content and b'/presentations/ex/' in r.content


def test_static_finder_maps_deck_static_and_slides(decks):
    from presentations.finders import DeckStaticFinder
    d = make_deck(decks)
    (d / 'static').mkdir()
    (d / 'static' / 'app.js').write_text('1')
    f = DeckStaticFinder()
    assert f.find('decks/ex/app.js') == str(d / 'static' / 'app.js')
    assert f.find('decks/ex/slides/01.svg') == str(d / 'slides' / '01.svg')
    assert f.find('decks/ex/deck.yaml') is None
    listed = {p for p, _ in f.list([])}
    assert 'app.js' in listed and '01.svg' in listed   # slides root yields paths relative to slides/, storage.prefix adds 'decks/ex/slides'
    assert f.find('decks/ex/app.js', all=True) == [str(d / 'static' / 'app.js')]


def test_static_finder_rejects_path_traversal(decks):
    from presentations.finders import DeckStaticFinder
    d = make_deck(decks)
    (d / 'static').mkdir()
    (d / 'static' / 'app.js').write_text('1')
    f = DeckStaticFinder()
    assert f.find('decks/ex/../../deck.yaml') is None
    assert f.find('decks/ex/slides/../../../../nihar_website/settings.py') is None
    assert f.find('decks/ex/../ex/app.js') is None
