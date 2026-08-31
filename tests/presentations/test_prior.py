"""The `prior` interaction: an audience-drawn eccentricity prior on a log10(e) grid."""
import pytest
from presentations import interactions as I
from presentations.interactions.prior import EXPERTISE

CFG = {'prompt': 'Draw your prior', 'axis': {'min': -4, 'max': 0, 'bins': 4, 'label': 'log10 e'}}
GOOD = {'weights': [1, 1, 2, 0], 'name': '  Ada ', 'institute': 'AEI', 'expertise': ['astrophysics', 'other'],
        'other': 'philosophy'}


def test_registry_includes_prior():
    assert 'prior' in I.all_types()


def test_expertise_tags_are_the_agreed_seven():
    assert EXPERTISE == ['data analysis', 'waveform model', 'theoretical modelling', 'numerical relativity',
                         'astrophysics', 'instrumentation', 'other']


def test_prior_config_validation():
    I.validate('prior', CFG)
    I.validate('prior', {**CFG, 'log_uniform_min': -2})
    with pytest.raises(ValueError):
        I.validate('prior', {'prompt': 'x', 'axis': {'min': 0, 'max': 0, 'bins': 4}})      # max must exceed min
    with pytest.raises(ValueError):
        I.validate('prior', {'prompt': 'x', 'axis': {'min': -4, 'max': 0, 'bins': 1}})     # too few bins
    with pytest.raises(ValueError):
        I.validate('prior', {'prompt': 'x'})                                               # axis required
    with pytest.raises(ValueError):
        I.validate('prior', {**CFG, 'log_uniform_min': 1})                                 # outside the axis


def test_prior_payload_normalises_weights_and_keeps_metadata():
    p = I.get('prior')
    out = p.clean_payload(GOOD, CFG)
    assert out == {'weights': [0.25, 0.25, 0.5, 0.0], 'name': 'Ada', 'institute': 'AEI',
                   'expertise': ['astrophysics', 'other'], 'other': 'philosophy'}


def test_prior_payload_optional_fields_default():
    p = I.get('prior')
    out = p.clean_payload({'weights': [1, 1, 1, 1]}, CFG)
    assert out['name'] == '' and out['institute'] == '' and out['expertise'] == [] and out['other'] == ''
    assert out['weights'] == [0.25, 0.25, 0.25, 0.25]


def test_prior_payload_rejects_bad_input():
    p = I.get('prior')
    with pytest.raises(ValueError):
        p.clean_payload({**GOOD, 'weights': [1, 1]}, CFG)                    # wrong length
    with pytest.raises(ValueError):
        p.clean_payload({**GOOD, 'weights': [0, 0, 0, 0]}, CFG)              # all zero
    with pytest.raises(ValueError):
        p.clean_payload({**GOOD, 'weights': [1, -1, 1, 1]}, CFG)             # negative
    with pytest.raises(ValueError):
        p.clean_payload({**GOOD, 'expertise': ['astrology']}, CFG)           # unknown tag
    with pytest.raises(ValueError):
        p.clean_payload({**GOOD, 'name': 'x' * 61}, CFG)                     # too long


def test_prior_aggregate_returns_curves_with_metadata_and_mean():
    p = I.get('prior')
    a = p.clean_payload({'weights': [1, 0, 0, 0], 'name': 'A', 'expertise': ['astrophysics']}, CFG)
    b = p.clean_payload({'weights': [0, 0, 0, 1], 'name': 'B', 'expertise': ['instrumentation']}, CFG)
    agg = p.aggregate([a, b], CFG)
    assert agg['n'] == 2
    assert agg['mean'] == [0.5, 0.0, 0.0, 0.5]
    assert agg['edges'] == [-4.0, -3.0, -2.0, -1.0, 0.0]
    assert agg['expertise'] == EXPERTISE
    assert [c['name'] for c in agg['curves']] == ['A', 'B']
    assert agg['curves'][0] == {'weights': [1.0, 0.0, 0.0, 0.0], 'name': 'A', 'institute': '',
                                'expertise': ['astrophysics'], 'other': ''}


def test_prior_aggregate_comparison_priors_on_log10_grid():
    agg = I.get('prior').aggregate([], CFG)
    cmp = agg['comparisons']
    # log-uniform on [10^min, 10^max] is flat in log10 e
    assert cmp['log_uniform'] == pytest.approx([0.25, 0.25, 0.25, 0.25])
    # uniform on e in [10^min, 10^max]: mass per bin is the width of the bin in e
    tot = 1 - 1e-4
    assert cmp['uniform'] == pytest.approx([(1e-3 - 1e-4) / tot, (1e-2 - 1e-3) / tot, (1e-1 - 1e-2) / tot, (1 - 1e-1) / tot])
    assert sum(cmp['uniform']) == pytest.approx(1.0)


def test_prior_log_uniform_lower_bound_is_independent_of_the_axis():
    cfg = {'prompt': 'p', 'axis': {'min': -8, 'max': 0, 'bins': 8}, 'log_uniform_min': -4}
    cmp = I.get('prior').aggregate([], cfg)['comparisons']
    assert cmp['log_uniform'] == pytest.approx([0, 0, 0, 0, .25, .25, .25, .25])
    # a bound between edges splits the bin by overlap
    cfg = {'prompt': 'p', 'axis': {'min': -4, 'max': 0, 'bins': 2}, 'log_uniform_min': -3}
    assert I.get('prior').aggregate([], cfg)['comparisons']['log_uniform'] == pytest.approx([1 / 3, 2 / 3])


def test_prior_aggregate_empty():
    agg = I.get('prior').aggregate([], CFG)
    assert agg['n'] == 0 and agg['curves'] == [] and agg['mean'] == [0.0] * 4
