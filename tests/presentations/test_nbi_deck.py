"""The Niels Bohr Institute deck: corfu's interactive slides carried onto a new Canva export.

The maths of the expert-prior Bayes factor is covered by test_corfu_expertbf.py; this only checks
what differs here -- which slides carry the blank, that the copied assets point at this deck, and
the GW200129 video placed after the spectrogram.
"""
import importlib.util
import json
from pathlib import Path

import pytest

DECK = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'nbi'

# event -> the NBI pages whose text reads "__ (uniform, log-uni, expert prior)"
BF_SLIDES = {'GW200208_22': ['page-51'], 'GW200105': ['page-11'],
             'GW190701': ['page-13'], 'GW200129': ['page-19', 'page-21', 'page-22']}


@pytest.fixture(scope='module')
def data():
    spec = importlib.util.spec_from_file_location('nbi_expertbf', DECK / 'tools' / 'expertbf.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build()


def _deck():
    from presentations import interactions
    from presentations.schema import load_deck
    return load_deck(DECK, interaction_validator=interactions.validate)


def test_static_json_is_up_to_date(data):
    on_disk = json.loads((DECK / 'static' / 'expertbf' / 'expertbf.json').read_text())
    assert on_disk == json.loads(json.dumps(data))
    assert {r['id']: r['slides'] for r in data['events']} == BF_SLIDES


def test_expert_bf_slides_are_html_over_their_original_svg():
    d = _deck()
    assert d.warnings == []
    for sids in BF_SLIDES.values():
        for sid in sids:
            s = d.slide(sid)
            assert (s.kind, s.path, s.underlay) == ('html', '14-expert-bf.html', f'slides/{sid[-2:]}-{sid}.svg')


def test_interactive_slides_and_video_are_in_place():
    ids = [s.id for s in _deck().slides]
    eob = [f'eob-{i}' for i in range(1, 7)]           # the EOB flowchart, one box per click
    dingo = ['page-03', 'page-04', 'page-05']
    assert ids[:18] == ['page-01', 'page-02', 'massplot', 'channels', 'page-06', 'page-07', 'page-08', *eob, *dingo, 'bayes', 'ecc-prior']
    assert ids[ids.index('page-25') + 1] == 'gw200129-chirp'      # right after the spectrogram
    assert 'riskgrid' not in ids                                  # dropped for this talk
    assert ids[ids.index('page-45') + 1] == 'timeline'
    assert (DECK / 'slides' / '22b-gw200129-chirp.mp4').exists()


def test_no_copied_file_still_points_at_corfu():
    for p in DECK.rglob('*'):
        if p.suffix in {'.html', '.js', '.css'}:
            assert 'corfu' not in p.read_text(), p


@pytest.mark.django_db
def test_archive_without_a_session_renders_six_dashes(anon_client):
    r = anon_client.get('/presentations/nbi/')
    assert r.status_code == 200
    assert r.content.decode().count('class="xbf xbf--none"') == 6


def test_eob_steps_are_one_logical_slide_and_reveal_in_order():
    d = _deck()
    steps = [d.slide(f'eob-{i}') for i in range(1, 7)]
    assert [s.continues for s in steps] == [False] + [True] * 5
    assert {s.path for s in steps} == {'15-eob.html'}
    html = (DECK / '15-eob.html').read_text()
    assert sorted(set(html.split('data-n="')[i][0] for i in range(1, html.count('data-n="') + 1))) == list('123456')
    assert 'eob-head-{{ slide.id }}' in html     # a shared marker id would point into a hidden step
    assert 'Effective one body' not in html


@pytest.mark.django_db
def test_archive_renders_each_eob_step_with_its_own_step_number(anon_client):
    body = anon_client.get('/presentations/nbi/').content.decode()
    for i in range(1, 7):
        assert f'<div class="eob" data-step="{i}">' in body


# --- the forward-model pipeline (16-forward.html, replaces pages 41 + 42) -----------------------

def _forward():
    return json.loads((DECK / 'static' / 'forward' / 'forward.json').read_text())


def test_forward_steps_replace_pages_41_and_42():
    d = _deck()
    ids = [s.id for s in d.slides]
    assert 'page-41' not in ids and 'page-42' not in ids
    steps = [d.slide(f'fwd-{i}') for i in range(1, 10)]    # 5 cards + 3 more capture equations + their plots
    assert [s.continues for s in steps] == [False] + [True] * 8
    assert ids[ids.index('page-40') + 1] == 'fwd-1' and ids[ids.index('fwd-9') + 1] == 'page-43'
    assert ids[ids.index('catalog') + 1] == 'page-33'               # the live blog-catalog embed, before "priors all wrong"


def test_forward_json_carries_both_catalogues_and_pools():
    f = _forward()
    assert f['hosts']['gc']['n'] == 112 and f['hosts']['nsc']['n'] == 108
    assert f['hosts']['gc']['mu'] < 1.0 < f['hosts']['nsc']['mu']          # ~5 vs ~50 km/s
    for h in ('gc', 'nsc'):
        assert len(f['pool'][h]) >= 1000
        assert all(0 < row[3] < 1 and 0 < row[5] < 1 and row[6] > 0 for row in f['pool'][h])   # e, p_det, r_p
    assert f['pool_fields'] == ['sigma_kms', 'm1', 'm2', 'e10Hz', 'vinf_kms', 'pdet', 'rp_GM_c2']


def test_forward_model_reproduces_paper_fig3_peaks():
    for row in _forward()['fig3_check']:
        assert abs(row['peak_here'] - row['peak_paper']) < 0.3, row


def test_forward_pdet_is_the_extracted_fig4_curve():
    p = _forward()['pdet']['averaged']
    assert 0.0 <= p['e'][0] < 0.01 and 0.55 < p['e'][-1] < 0.6
    assert abs(p['pdet'][0] - 0.475) < 0.01 and min(p['pdet']) > 0.38


@pytest.mark.django_db
def test_archive_renders_each_forward_step(anon_client):
    body = anon_client.get('/presentations/nbi/').content.decode()
    for i in range(1, 10):
        assert f'<div class="fwd" data-step="{i}"' in body


def test_catalog_slide_embeds_the_blog_page_same_origin(client):
    html = (DECK / '18-catalog.html').read_text()
    assert 'data-src="/blog/catalog-of-eccentric-binary-black-holes/"' in html   # relative: same origin
    r = client.get('/blog/catalog-of-eccentric-binary-black-holes/')
    assert r.status_code == 200 and r['X-Frame-Options'] == 'SAMEORIGIN'


# --- the live eccentricity-prior poll on the real NBI deck --------------------------------------

@pytest.mark.django_db
def test_nbi_prior_poll_round_trip_feeds_the_expert_bayes_factor(staff_client):
    from django.test import Client
    from presentations.models import Session
    xbf = json.loads((DECK / 'static' / 'expertbf' / 'expertbf.json').read_text())
    bins = xbf['axis']['bins']
    staff_client.get('/presentations/nbi/present/')                       # opens a session
    code = Session.open_for('nbi').join_code
    assert staff_client.post('/presentations/nbi/present/interaction/ecc-prior/open/').status_code in (200, 204, 302)

    phone = Client()
    phone.post(f'/p/{code}/join/', {'expertise_tag': 'theory', 'display_name': 'Ada'})
    w = [0.0] * bins
    w[bins - 5] = 1.0                                                       # all mass near e ~ 0.3
    r = phone.post(f'/p/{code}/respond/ecc-prior/', data=json.dumps({'weights': w, 'name': 'Ada',
                   'expertise': ['astrophysics']}), content_type='application/json')
    assert r.status_code == 200, r.content

    agg = staff_client.get(f'/p/{code}/aggregate/ecc-prior/').json()
    assert agg['n'] == 1 and len(agg['mean']) == bins                       # same grid expertbf.js reweights on
    assert phone.get(f'/p/{code}/aggregate/ecc-prior/').status_code == 403   # hidden from phones until revealed
    for state in ('closed', 'revealed'):
        assert staff_client.post(f'/presentations/nbi/present/interaction/ecc-prior/{state}/').status_code in (200, 204, 302)
    agg = phone.get(f'/p/{code}/aggregate/ecc-prior/')
    assert agg.status_code == 200 and agg.json()['state'] == 'revealed'


def test_degeneracy_aside_is_two_steps_figure_then_player():
    d = _deck()
    ids = [s.id for s in d.slides]
    assert ids[ids.index('page-12') + 1] == 'page-12b'
    a, b = d.slide('page-12'), d.slide('page-12b')
    assert (a.continues, b.continues) == (False, True) and a.underlay == b.underlay
    html = (DECK / '17-nametune.html').read_text()
    assert "data-player=\"{% if slide.id == 'page-12' %}0{% else %}1{% endif %}\"" in html


def test_gw200129_glitch_table_rows_reweight_back_to_the_published_numbers(data):
    """Each mitigation row, given the uniform or log-uniform prior on the poll grid, returns its own row of Table 5."""
    spec = importlib.util.spec_from_file_location('nbi_expertbf_t', DECK / 'tools' / 'expertbf.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tb,) = data['tables']
    assert tb['slides'] == ['page-22'] and [r['label'] for r in tb['rows']] == ['gwsubtract', 'BayesWave A', 'BayesWave B', 'BayesWave C']
    edges = data['edges']
    for r in tb['rows']:
        assert r['ratio'] < r['ratio_bound'] and r['k_spread_dex'] <= 0.03
        assert abs(r['e_star'] - r['posterior']['e']) < 0.05          # lands on the published e_10Hz, unfitted
        for kind in ('uniform', 'log_uniform'):
            got = mod.bayes_factor(mod.reference_masses(kind, edges), r['lambda'], r['k'])
            assert abs(got / r['quoted'][kind] - 1) <= r['grid_tolerance']


def test_expert_blank_is_prior_odds_times_the_uniform_bayes_factor(data):
    """Delta-at-zero vs uniform-prior models: the json carries the threshold and every event its uniform B."""
    assert data['odds']['threshold'] == 0.05 and abs(data['odds']['threshold_log10'] + 1.30103) < 1e-5
    assert {e['id']: round(e['quoted']['uniform']) for e in data['events']} == {
        'GW200208_22': 17, 'GW200105': 17, 'GW190701': 407, 'GW200129': 10000}
    js = (DECK / 'static' / 'expertbf' / 'expertbf.js').read_text()
    assert 'po.odds * ev.quoted.uniform' in js and 'po.odds * c.row.quoted.uniform' in js


def test_nametune_third_clip_is_the_liechtenstein_anthem_heard_as_god_save_the_king():
    nt = json.loads((DECK / 'static' / 'nametune' / 'nametune.json').read_text())
    assert [c['id'] for c in nt['clips']] == ['another_room', 'short_decisive', 'anthem']
    a = nt['clips'][2]
    assert a['believed'] == 'God Save the King' and a['answer'].replace('\u00a0', ' ') == 'British national anthem, or is it?'
    assert (DECK / 'static' / 'nametune' / a['src']).exists()
    lb = a['log10B']
    assert lb[-1] > 10 and abs(a['duration'] - 10) < 0.5        # climbs off the 0-10 plot for the wrong song
    assert all(b >= a_ - 0.3 for a_, b in zip(lb, lb[1:]))      # and never turns back
    assert "id: 'anthem'" in (DECK / 'static' / 'nametune' / 'nametune.js').read_text()


def test_massplot_is_a_full_bleed_lazy_embed_after_the_table_of_contents():
    d = _deck()
    s = d.slide('massplot')
    assert (s.kind, s.path) == ('html', '19-massplot.html') and s.footer is False
    html = (DECK / '19-massplot.html').read_text()
    assert 'data-src="https://ligo.northwestern.edu/media/mass-plot/index.html"' in html and ' src="https://ligo' not in html
