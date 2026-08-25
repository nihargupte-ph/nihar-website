from pathlib import Path
from django.core.management import call_command
from presentations.schema import load_deck
from presentations import interactions

ROOT = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'example'


def test_example_deck_is_valid():
    deck = load_deck(ROOT, interaction_validator=interactions.validate)
    assert {s.kind for s in deck.slides} == {'svg', 'html', 'video'}
    assert {i.type for i in deck.interactions} == {'choice', 'numeric', 'distribution', 'text'}
    assert deck.warnings == []
    asked = {a for s in deck.slides for a in s.ask}
    shown = {r.id for s in deck.slides for r in s.show}
    assert 'q-orbits' in asked and 'q-orbits' in shown
    assert any(r.id == 'q-orbits' for s in deck.slides if s.id == 'orbits-results' for r in s.show)


def test_checkdecks_passes_on_repo(capsys):
    call_command('checkdecks')
    assert 'example: ok' in capsys.readouterr().out
