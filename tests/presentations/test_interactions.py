import pytest
from presentations import interactions as I


def test_registry_has_four_types():
    assert set(I.all_types()) == {'choice', 'numeric', 'distribution', 'text'}
    with pytest.raises(ValueError):
        I.get('nope')


# --- choice ---
CHOICE = {'prompt': 'Which?', 'options': ['A', 'B', 'C'], 'answer': 'B'}


def test_choice_config_validation():
    I.validate('choice', CHOICE)
    with pytest.raises(ValueError):
        I.validate('choice', {'prompt': 'x', 'options': ['A']})          # < 2 options
    with pytest.raises(ValueError):
        I.validate('choice', {'prompt': 'x', 'options': ['A', 'B'], 'answer': 'Z'})


def test_choice_payload_and_aggregate():
    c = I.get('choice')
    assert c.clean_payload({'choice': 'A'}, CHOICE) == {'choice': 'A'}
    with pytest.raises(ValueError):
        c.clean_payload({'choice': 'Z'}, CHOICE)
    agg = c.aggregate([{'choice': 'A'}, {'choice': 'B'}, {'choice': 'B'}], CHOICE)
    assert agg == {'n': 3, 'counts': {'A': 1, 'B': 2, 'C': 0}}
    assert c.aggregate([], CHOICE) == {'n': 0, 'counts': {'A': 0, 'B': 0, 'C': 0}}


# --- numeric ---
NUM = {'prompt': 'rate', 'log': True, 'truth': 23.9}


def test_numeric_payload_and_aggregate():
    n = I.get('numeric')
    assert n.clean_payload({'value': '12.5'}, NUM) == {'value': 12.5}
    assert n.clean_payload({'value': 3, 'err': 1}, NUM) == {'value': 3.0, 'err': 1.0}
    with pytest.raises(ValueError):
        n.clean_payload({'value': -1}, NUM)      # log scale requires > 0
    with pytest.raises(ValueError):
        n.clean_payload({'value': 'abc'}, NUM)
    agg = n.aggregate([{'value': 1}, {'value': 10}, {'value': 100}], NUM)
    assert agg['n'] == 3 and agg['values'] == [1.0, 10.0, 100.0]
    assert agg['median'] == 10.0 and agg['q16'] <= 10.0 <= agg['q84']
    assert n.aggregate([], NUM) == {'n': 0, 'values': [], 'errs': [], 'median': None, 'q16': None, 'q84': None}


def test_numeric_min_max():
    n = I.get('numeric')
    cfg = {'prompt': 'p', 'min': 0, 'max': 10}
    with pytest.raises(ValueError):
        n.clean_payload({'value': 11}, cfg)


# --- distribution ---
DIST = {'prompt': 'prior', 'axis': {'min': 0, 'max': 1, 'bins': 4, 'label': 'e'}}


def test_distribution_payload_normalises():
    d = I.get('distribution')
    out = d.clean_payload({'weights': [1, 1, 2, 0]}, DIST)
    assert out['weights'] == [0.25, 0.25, 0.5, 0.0]
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [1, 1]}, DIST)            # wrong length
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [0, 0, 0, 0]}, DIST)      # all zero
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [1, -1, 1, 1]}, DIST)     # negative


def test_distribution_aggregate():
    d = I.get('distribution')
    agg = d.aggregate([{'weights': [1, 0, 0, 0]}, {'weights': [0, 0, 0, 1]}], DIST)
    assert agg['n'] == 2
    assert agg['mean'] == [0.5, 0.0, 0.0, 0.5]
    assert agg['curves'] == [[1, 0, 0, 0], [0, 0, 0, 1]]
    assert agg['edges'] == [0.0, 0.25, 0.5, 0.75, 1.0]


# --- text ---
TXT = {'prompt': 'one word', 'max_len': 12}


def test_text_payload_and_aggregate():
    t = I.get('text')
    assert t.clean_payload({'text': '  Chaotic!  '}, TXT) == {'text': 'Chaotic!'}
    with pytest.raises(ValueError):
        t.clean_payload({'text': 'way too long for this'}, TXT)
    with pytest.raises(ValueError):
        t.clean_payload({'text': ''}, TXT)
    agg = t.aggregate([{'text': 'chaotic orbits'}, {'text': 'Chaotic'}, {'text': 'the messy'}], TXT)
    assert agg['n'] == 3
    assert agg['counts'] == {'chaotic': 2, 'orbits': 1, 'messy': 1}   # stopword 'the' dropped


def test_text_profanity_rejected():
    t = I.get('text')
    with pytest.raises(ValueError):
        t.clean_payload({'text': 'fuck'}, TXT)


# --- textutil ---
def test_render_markdown_allowlist():
    from presentations.textutil import render_markdown
    html = render_markdown('**b** <script>x</script> [l](https://x.y)')
    assert '<strong>b</strong>' in html and '<script>' not in html
    assert 'rel="nofollow noopener"' in html and 'target="_blank"' in html


def test_hash_ip_is_stable_and_opaque():
    from presentations.textutil import hash_ip
    assert hash_ip('1.2.3.4') == hash_ip('1.2.3.4') and len(hash_ip('1.2.3.4')) == 64
    assert '1.2.3.4' not in hash_ip('1.2.3.4')
