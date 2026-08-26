import json
import re
from pathlib import Path

from presentations import interactions
from presentations.schema import load_deck

DECK = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu'
TL = DECK / 'static' / 'timeline'
LANES = {'real-data', 'simulated', 'likelihood'}


def load():
    return json.loads((TL / 'timeline.json').read_text())


def test_lanes():
    assert [l['id'] for l in load()['lanes']] == ['real-data', 'simulated', 'likelihood']
    assert all(l['title'] for l in load()['lanes'])


def test_entries_are_well_formed():
    entries = load()['entries']
    assert entries, 'no entries'
    ids, arxivs = set(), set()
    for e in entries:
        assert set(e) >= {'id', 'lane', 'first_author', 'authors', 'title', 'arxiv', 'v1_date', 'figure', 'caption'}, e['id']
        assert e['lane'] in LANES, e['id']
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', e['v1_date']), e['id']
        if e['arxiv'] is None:
            assert e.get('url', '').startswith('https://'), f"{e['id']}: non-arXiv entries need a url"
        else:
            assert re.fullmatch(r'\d{4}\.\d{4,5}|[a-z\-]+/\d{7}', e['arxiv']), e['id']
            assert e['arxiv'] not in arxivs, e['id']
            arxivs.add(e['arxiv'])
        assert e['id'] not in ids, e['id']
        ids.add(e['id'])
        if e['figure'] is not None:
            assert (TL / e['figure']).is_file(), e['id']


def test_real_data_lane_has_citations():
    assert sum(e['lane'] == 'real-data' for e in load()['entries']) >= 5


def test_deck_has_timeline_slide():
    deck = load_deck(DECK, interaction_validator=interactions.validate)
    assert deck.warnings == []
    [s] = [s for s in deck.slides if s.id == 'timeline']
    assert s.kind == 'html' and s.path == '04-timeline.html'
    html = (DECK / '04-timeline.html').read_text()
    assert 'data-anchor="missing-citation"' in html
    assert 'timeline/timeline.json' in html
