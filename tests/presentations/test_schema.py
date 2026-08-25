from pathlib import Path
import textwrap
import pytest
import yaml

from presentations.schema import load_deck, DeckError

GOOD = """
title: Example
date: 2026-09-12
expertise: [theory, data]
theme: {bg: "#111111", fg: "#eeeeee", accents: ["#37b49f"]}
interactions:
  - id: q1
    type: choice
    prompt: Which?
    options: [A, B]
slides:
  - id: title
    svg: slides/01.svg
    hotspots:
      - rect: [0.1, 0.1, 0.2, 0.2]
        title: Hot
        body: "**bold**"
        links: [{label: L, url: "https://x.y"}]
    ask: [q1]
  - id: results
    svg: slides/02.svg
    show:
      - {id: q1, rect: [0.1, 0.2, 0.8, 0.6]}
  - id: page
    html: page.html
    show: [{id: q1}]
  - id: vid
    video: slides/03.mp4
    poster: slides/03.jpg
"""


def make_deck(tmp_path, text=GOOD, files=('slides/01.svg', 'slides/02.svg', 'page.html', 'slides/03.mp4', 'slides/03.jpg')):
    d = tmp_path / 'ex'
    for f in files:
        p = d / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('x')
    (d / 'deck.yaml').write_text(textwrap.dedent(text))
    return d


def test_good_deck_loads(tmp_path):
    deck = load_deck(make_deck(tmp_path))
    assert deck.slug == 'ex' and deck.title == 'Example'
    assert [s.kind for s in deck.slides] == ['svg', 'svg', 'html', 'video']
    assert deck.slides[0].hotspots[0].title == 'Hot'
    assert deck.slides[0].ask == ['q1']
    assert deck.slides[1].show[0].rect == [0.1, 0.2, 0.8, 0.6]
    assert deck.slides[2].show[0].rect is None
    assert deck.slides[3].poster == 'slides/03.jpg'
    assert deck.interaction('q1').config == {'prompt': 'Which?', 'options': ['A', 'B']}
    assert deck.slide_index('page') == 2
    assert [i.id for i in deck.interactions_for_slide(deck.slides[1])] == ['q1']
    assert deck.transition == 'fade'


def _expect_error(tmp_path, text, needle, **kw):
    with pytest.raises(DeckError) as ei:
        load_deck(make_deck(tmp_path, text, **kw))
    assert needle in str(ei.value)


def test_duplicate_slide_id(tmp_path):
    _expect_error(tmp_path, GOOD.replace('id: results', 'id: title'), 'duplicate slide id')


def test_duplicate_interaction_id(tmp_path):
    bad = GOOD.replace('slides:', "  - id: q1\n    type: choice\n    prompt: p\n    options: [A]\nslides:")
    _expect_error(tmp_path, bad, 'duplicate interaction id')


def test_missing_file(tmp_path):
    _expect_error(tmp_path, GOOD, 'slides/02.svg', files=('slides/01.svg', 'page.html', 'slides/03.mp4', 'slides/03.jpg'))


def test_unresolved_ask(tmp_path):
    _expect_error(tmp_path, GOOD.replace('ask: [q1]', 'ask: [zzz]'), "unknown interaction 'zzz'")


def test_html_show_with_rect_rejected(tmp_path):
    _expect_error(tmp_path, GOOD.replace('show: [{id: q1}]', 'show: [{id: q1, rect: [0,0,1,1]}]'), 'must not give rect')


def test_svg_show_without_rect_rejected(tmp_path):
    _expect_error(tmp_path, GOOD.replace('- {id: q1, rect: [0.1, 0.2, 0.8, 0.6]}', '- {id: q1}'), 'must give rect')


def test_bad_rect(tmp_path):
    _expect_error(tmp_path, GOOD.replace('[0.1, 0.1, 0.2, 0.2]', '[0.1, 0.1, 1.2]'), 'rect')


def test_expertise_bounds(tmp_path):
    _expect_error(tmp_path, GOOD.replace('[theory, data]', '[theory]'), 'expertise')


def test_unknown_slide_kind(tmp_path):
    _expect_error(tmp_path, GOOD.replace('html: page.html', 'pdf: page.html'), 'svg, html or video')


def test_validator_hook_called(tmp_path):
    def v(type_name, config):
        raise ValueError('nope ' + type_name)
    with pytest.raises(DeckError) as ei:
        load_deck(make_deck(tmp_path), interaction_validator=v)
    assert 'nope choice' in str(ei.value)


def test_unasked_interaction_is_warning_not_error(tmp_path):
    text = GOOD.replace('ask: [q1]', '')
    deck = load_deck(make_deck(tmp_path, text))
    assert deck.warnings == ["interaction 'q1' is never asked on any slide"]
