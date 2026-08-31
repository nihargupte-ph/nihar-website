"""The corfu deck's live eccentricity-prior poll slide."""
from pathlib import Path

from presentations import interactions
from presentations.schema import load_deck

DECK = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu'


def deck():
    return load_deck(DECK, interaction_validator=interactions.validate)


def test_poll_slide_follows_significance_slide():
    d = deck()
    assert d.warnings == []
    ids = [s.id for s in d.slides]
    # the poll comes straight after the "what is significance" slide
    assert ids[ids.index("bayes") + 1] == "ecc-prior"
    s = d.slide('ecc-prior')
    assert s.kind == 'html' and s.ask == ['ecc-prior'] and [r.id for r in s.show] == ['ecc-prior']


def test_poll_interaction_is_a_log10_prior():
    i = deck().interaction('ecc-prior')
    assert i.type == 'prior'
    assert i.config['axis']['min'] == -11 and i.config['axis']['max'] == 0
    assert i.config['axis']['bins'] >= 40
    assert i.config['log_uniform_min'] == -4


def test_poll_slide_markup_hosts_the_widget_and_assets():
    html = (DECK / '12-prior-poll.html').read_text()
    assert 'data-interaction="ecc-prior"' in html
    assert 'tell us who you are' not in html and 'Scan, draw' not in html
    assert 'prior-poll/poll.js' in html and 'prior-poll/poll.css' in html
    assert (DECK / 'static' / 'prior-poll' / 'poll.js').exists()
    assert (DECK / 'static' / 'prior-poll' / 'poll.css').exists()


def test_presenter_bar_has_no_qr_button_and_one_poll_button():
    ROOT = DECK.parents[2]
    present = (ROOT / 'presentations' / 'templates' / 'presentations' / 'present.html').read_text()
    assert 'id="qr-toggle"' not in present
    assert 'id="qr-box"' in present            # the poll slide clones it onto the slide
    js = (ROOT / 'presentations' / 'static' / 'presentations' / 'js' / 'present.js').read_text()
    assert 'POLL_SECONDS = 90' in js
    assert "'hidden', 'open', 'closed', 'revealed'" not in js


def test_prior_widget_hides_the_join_tag_slicer():
    js = (DECK.parents[2] / 'presentations' / 'static' / 'presentations' / 'js' / 'interactions' / 'prior.js').read_text()
    assert 'slicer: false' in js
    assert 'confidence' not in js
