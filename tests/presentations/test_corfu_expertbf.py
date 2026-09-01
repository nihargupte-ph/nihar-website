"""Per-event 'expert prior' Bayes factors for the corfu deck.

The slides quote two Bayes factors per event (uniform and log-uniform prior on
e_10Hz).  `tools/expertbf.py` turns that pair into a likelihood-ratio curve
Lambda(log10 e) that can be integrated against the audience's poll mixture.
These tests pin the maths, the round trip through the quoted numbers, and the
generated static JSON.
"""
import importlib.util
import json
import math
from pathlib import Path

import pytest

DECK = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu'
TOOLS = DECK / 'tools'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def m():
    return load('expertbf')


@pytest.fixture(scope='module')
def data(m):
    return m.build()


# --- the analytic feasibility bound -------------------------------------------------

def test_ratio_bound_is_ln_of_the_prior_range(m):
    # B_uniform / B_loguniform <= sup pi_U/pi_LU = ln(e_max/e_min) for any Lambda >= 0
    assert m.ratio_bound(0.5, 1e-4) == pytest.approx(math.log(5000.0))
    assert m.ratio_bound(0.5, 1e-4) == pytest.approx(8.5172, abs=1e-3)


def test_every_fitted_event_respects_the_bound(m):
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        assert f['ratio'] < f['ratio_bound'], ev['id']


def test_gw200105_pair_violates_the_bound_and_is_not_fitted(m):
    ev = next(e for e in m.EVENTS if e['id'] == 'GW200105')
    assert ev['fittable'] is False
    bu, blu = ev['quoted']['uniform'], ev['quoted']['log_uniform']
    # 17 / 1.3 = 13.1 exceeds ln(0.2/1e-4) = 7.60: no non-negative likelihood reproduces both
    assert bu / blu > m.ratio_bound(0.2, 1e-4)
    with pytest.raises(ValueError):
        m.fit(ev)


# --- the fit ------------------------------------------------------------------------

def test_k_the_precessing_offset_is_prior_independent(m):
    """k = Z_QCAS/Z_QCP carries no eccentricity, so B_QCP/B_QCAS must agree between
    the uniform and the log-uniform row.  It does, to within the papers' 0.04 dex."""
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        assert f['k_spread_dex'] < 0.08, (ev['id'], f['k_spread_dex'])


def test_fit_reproduces_the_nested_bayes_factors_exactly(m):
    """Lambda is anchored on the nested EAS/QCAS pair, so pushing the uniform prior back
    through it must return the quoted uniform B, and the log-uniform prior the quoted
    log-uniform B, to quadrature precision."""
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        assert m.integrate(m.uniform_pdf, f) == pytest.approx(10.0 ** ev['log10_b_qcas']['uniform'], rel=1e-5)
        assert m.integrate(m.log_uniform_pdf, f) == pytest.approx(10.0 ** ev['log10_b_qcas']['log_uniform'], rel=1e-5)


def test_fit_reproduces_the_quoted_precessing_bayes_factors(m):
    """The pair actually printed on the slides is EAS/QCP = k * EAS/QCAS.  k is a single
    constant fitted as the geometric mean of the two rows, so the round trip is exact up
    to half the (tiny) inconsistency between them."""
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        tol = 10.0 ** (0.5 * f['k_spread_dex']) - 1.0 + 1e-4
        for kind in ('uniform', 'log_uniform'):
            pdf = m.uniform_pdf if kind == 'uniform' else m.log_uniform_pdf
            got = m.bayes_factor_continuum(pdf, f)
            assert got == pytest.approx(10.0 ** ev['log10_b_qcp'][kind], rel=tol), (ev['id'], kind)
        assert tol < 0.04, ev['id']


def test_effective_eccentricity_lands_inside_the_published_posterior(m):
    """Independent check: the two Bayes factors alone imply an eccentricity, and it
    agrees with the e_10Hz posterior the same table reports."""
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        lo, hi = ev['posterior']['lo'], ev['posterior']['hi']
        assert lo <= f['e_star'] <= hi, (ev['id'], f['e_star'], lo, hi)


def test_lambda_is_non_negative_and_flat_at_low_eccentricity(m):
    for ev in m.EVENTS:
        if not ev.get('fittable', True):
            continue
        f = m.fit(ev)
        assert m.lam(-11.0, f) == pytest.approx(1.0, abs=1e-9)
        assert m.lam(-8.0, f) == pytest.approx(1.0, abs=1e-9)
        assert all(m.lam(x / 10.0, f) >= 0 for x in range(-110, 1))


# --- the poll grid ------------------------------------------------------------------

def test_grid_round_trip_recovers_the_quoted_numbers(m, data):
    """Same round trip, but through the discrete 88-bin poll axis the browser uses."""
    edges = data['edges']
    for row in data['events']:
        if not row['fittable']:
            continue
        for kind in ('uniform', 'log_uniform'):
            w = m.reference_masses(kind, edges)
            got = m.bayes_factor(w, row['lambda'], row['k'])
            assert got == pytest.approx(row['quoted'][kind], rel=row['grid_tolerance']), (row['id'], kind)
        # the loss is the piecewise-constant approximation of the *reference* priors on a
        # 0.125-dex grid (worst for GW190701, whose bump sits in the bin straddling e = 0.5)
        assert row['grid_error'] < 0.40, (row['id'], row['grid_error'])


def test_a_prior_that_lives_at_tiny_eccentricity_gives_no_evidence(m, data):
    """The pedagogical case: an audience that believes e ~ 1e-6 gets Lambda's plateau,
    i.e. the Bayes factor collapses to k (<1) -- no support for eccentricity."""
    edges = data['edges']
    n = len(edges) - 1
    w = [0.0] * n
    for i in range(n):
        if -6.5 <= 0.5 * (edges[i] + edges[i + 1]) <= -5.5:
            w[i] = 1.0
    w = [x / sum(w) for x in w]
    for row in data['events']:
        if not row['fittable']:
            continue
        got = m.bayes_factor(w, row['lambda'], row['k'])
        assert got == pytest.approx(row['k'], rel=1e-9)
        assert got < 1.0


def test_a_prior_sitting_on_the_effective_eccentricity_recovers_a_large_factor(m, data):
    edges = data['edges']
    n = len(edges) - 1
    for row in data['events']:
        if not row['fittable']:
            continue
        w = [0.0] * n
        j = min(range(n), key=lambda i: abs(0.5 * (edges[i] + edges[i + 1]) - row['mu']))
        w[j] = 1.0
        assert m.bayes_factor(w, row['lambda'], row['k']) > row['quoted']['uniform']


def test_bayes_factor_handles_degenerate_input(m, data):
    row = next(r for r in data['events'] if r['fittable'])
    assert m.bayes_factor([], row['lambda'], row['k']) is None
    assert m.bayes_factor([0.0] * len(row['lambda']), row['lambda'], row['k']) is None


# --- the shipped json ---------------------------------------------------------------

def test_static_json_is_up_to_date(m, data):
    on_disk = json.loads((DECK / 'static' / 'expertbf' / 'expertbf.json').read_text())
    assert on_disk == json.loads(json.dumps(data))


def test_json_shape(data):
    assert data['axis'] == {'min': -11.0, 'max': 0.0, 'bins': 88}
    assert len(data['edges']) == 89
    by_id = {r['id']: r for r in data['events']}
    assert set(by_id) == {'GW200208_22', 'GW200105', 'GW190701', 'GW200129'}
    slides = [s for r in data['events'] for s in r['slides']]
    assert sorted(slides) == ['page-06', 'page-07', 'page-08', 'page-09',
                              'page-14', 'page-16', 'page-17', 'page-23']
    for r in data['events']:
        assert r['blank'] and 0 < r['blank']['x'] < 1 and 0 < r['blank']['y'] < 1
        if r['fittable']:
            assert len(r['lambda']) == 88
        else:
            assert r['lambda'] is None and r['reason']


# --- the deck wiring ----------------------------------------------------------------

def _deck():
    from presentations import interactions
    from presentations.schema import load_deck
    return load_deck(DECK, interaction_validator=interactions.validate)


def test_affected_slides_are_html_over_their_original_svg(data):
    d = _deck()
    assert d.warnings == []
    want = {s: f'slides/{s[-2:]}-{s}.svg' for r in data['events'] for s in r['slides']}
    for sid, svg in want.items():
        s = d.slide(sid)
        assert s.kind == 'html', sid
        assert s.path == '14-expert-bf.html', sid
        assert s.underlay == svg, sid          # the Canva page is kept as the backdrop
    # ids are persistence keys: the deck still has exactly the same slide ids in order
    ids = [s.id for s in d.slides]
    assert ids[:12] == ['page-01', 'page-02', 'channels', 'page-03', 'page-04', 'page-05',
                        'bayes', 'ecc-prior', 'page-06', 'page-07', 'page-08', 'page-09']


def test_slide_template_and_assets_exist():
    html = (DECK / '14-expert-bf.html').read_text()
    assert 'data-slide="{{ slide.id }}"' in html
    assert 'expertbf/expertbf.js' in html and 'expertbf/expertbf.css' in html
    assert (DECK / 'static' / 'expertbf' / 'expertbf.js').exists()
    assert (DECK / 'static' / 'expertbf' / 'expertbf.css').exists()


def test_script_selects_its_own_roots_and_survives_being_loaded_eight_times():
    js = (DECK / 'static' / 'expertbf' / 'expertbf.js').read_text()
    assert ".xbf:not([data-done])" in js       # the archive page holds every slide at once
    assert 'NS.mounted' in js                  # eight slides each emit the same <script src>


@pytest.mark.django_db
def test_present_view_renders_one_overlay_per_affected_slide(staff_client, data):
    r = staff_client.get('/presentations/corfu/present/')
    assert r.status_code == 200
    body = r.content.decode()
    for row in data['events']:
        for sid in row['slides']:
            assert f'<div class="xbf xbf--none" data-slide="{sid}"' in body, sid
    assert body.count('class="xbf xbf--none"') == 8


@pytest.mark.django_db
def test_archive_without_a_session_still_renders_the_dash(anon_client):
    r = anon_client.get('/presentations/corfu/')
    assert r.status_code == 200
    body = r.content.decode()
    assert body.count('class="xbf xbf--none"') == 8
    assert '&mdash;' in body or '—' in body


# --- python / js parity -------------------------------------------------------------

NODE = Path.home() / '.nvm' / 'versions' / 'node' / 'v22.22.2' / 'bin' / 'node'


@pytest.mark.skipif(not NODE.exists(), reason='node >= 14 not installed at the documented path')
def test_browser_and_python_agree_on_the_dot_product(m, data):
    import subprocess
    edges = data['edges']
    probe = m._probe(edges)
    script = Path(__file__).parent / 'js' / 'expertbf.test.mjs'
    out = subprocess.run([str(NODE), str(script)], input=json.dumps(probe),
                         capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    for row in data['events']:
        if not row['fittable']:
            assert got[row['id']] is None
            continue
        want = m.bayes_factor(probe, row['lambda'], row['k'])
        assert got[row['id']] == pytest.approx(want, rel=1e-12), row['id']
