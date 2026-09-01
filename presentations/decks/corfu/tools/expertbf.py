"""Reweight the published eccentricity Bayes factors onto the audience's own prior.

Run `python tools/expertbf.py` from the deck folder to regenerate
`static/expertbf/expertbf.json`; the browser only does the final dot product.

WHAT THE SLIDES QUOTE
---------------------
Four event slides carry a line like

    Bayes factor ~ 17, 3, __ (uniform, log-uni, expert prior)

Three of those pairs are the SEOBNRv4PHM / NRSur7dq4 columns of Table 5 of
Gupte+ 2024 (arXiv:2404.14286): log10 B for an eccentric aligned-spin model
(EAS) against a quasi-circular *precessing* model (QCP), with e_10Hz either
uniform on [0, 0.5] or log-uniform on [1e-4, 0.5].  The same table also gives
the *nested* comparison, EAS against quasi-circular aligned-spin (QCAS), and
the e_10Hz posterior.  That extra column is what makes this exercise possible.

THE MODEL
---------
Write x = log10 e and let L(x) be the eccentric model's likelihood marginalised
over every other parameter.  For any prior pi(x),

    B_{EAS/QCAS}(pi) = int pi(x) Lambda(x) dx,        Lambda(x) = L(x) / Z_QCAS
    B_{EAS/QCP}(pi)  = k * int pi(x) Lambda(x) dx,    k = Z_QCAS / Z_QCP

k has nothing to do with eccentricity, so it must be the same for both priors:
k = B_QCP/B_QCAS is measured twice and the two values agree to <= 0.03 dex for
all three events (`k_spread_dex`), which is the first consistency check.

Because EAS -> QCAS as e -> 0, Lambda(-inf) = 1 exactly.  We take

    Lambda(x) = 1 + A * N(x; mu, sigma)

- sigma comes from the published 90% HDI on e_10Hz (a log-space Gaussian), so
  it is not a free knob.  The answer is very insensitive to it (see
  `sigma_sensitivity` in the json).
- A and mu are then fixed *exactly* by the two quoted QCAS Bayes factors.

FEASIBILITY, AND WHY GW200105 IS LEFT BLANK
-------------------------------------------
For any Lambda >= 0 supported on [0, e_max],

    B_uniform / B_loguniform <= sup pi_U/pi_LU = ln(e_max / e_min)

(= 8.517 for [0, 0.5] / [1e-4, 0.5]).  The three Gupte+ 2024 events sit at 66%,
92% and 69% of that ceiling.  GW200105's quoted 17 / 1.3 is a ratio of 13.1
against a ceiling of ln(0.2/1e-4) = 7.60, so *no* non-negative likelihood
reproduces both numbers -- unsurprising, since the two numbers come from
different papers at different reference frequencies.  It is reported as not
computable rather than fitted.

LIMITS OF THE APPROXIMATION
---------------------------
- Below e = 1e-4 nothing anchors Lambda; we assume it equals its e -> 0 value
  (the data cannot resolve e = 1e-6 from e = 0).  This is the assumption that
  makes the answer finite at all: without it B_expert is unbounded above,
  because the audience puts most of its mass where the published analyses
  carry no information.
- Above e = 0.5 the published runs never sampled, and the model relaxes back to
  the plateau.  It should really fall, so B_expert is an over-estimate for any
  audience curve with mass at e > 0.5; `mass_above_ceiling` flags it.
- The fitted bump is narrower than one 0.125-dex poll bin, so on the poll grid
  the answer is driven by the audience's mass in the single bin containing
  e ~ 0.33-0.47.  `grid_tolerance` records the resulting discretisation error.
"""
import json
import math
import os

LN10 = math.log(10.0)
Z90 = 1.6448536269514722          # normal quantile for a 90% central interval

# The poll's axis (deck.yaml, interaction `ecc-prior`).
AXIS = {'min': -11.0, 'max': 0.0, 'bins': 88}

# The eccentricity priors used by Gupte+ 2024 (arXiv:2404.14286), Table 5 caption:
# "uniform between [0.0, 0.5] or log-uniform between [1e-4, 0.5]" on e_10Hz.
E_MAX = 0.5
E_MIN_LOG = 1e-4
X_CEIL = math.log10(E_MAX)
X_REF = math.log10(E_MIN_LOG)

SOURCE = 'Gupte+ 2024, arXiv:2404.14286 Table 5 (e_10Hz; uniform [0, 0.5] / log-uniform [1e-4, 0.5])'

EVENTS = [
    {
        'id': 'GW200208_22',
        'label': 'GW200208_22',
        'slides': ['page-06', 'page-07', 'page-08', 'page-09'],
        # x/y are fractions of the 1920x1080 stage: the "__" word box on the slide,
        # read off the Canva PDF with `pdftotext -bbox` (page size 1440x810 pt).
        'blank': {'x': 295.037916 / 1440, 'y': 120.371327 / 810,
                  'w': (313.409608 - 295.037916) / 1440, 'h': (144.698429 - 120.371327) / 810},
        'row': 'Unmitigated Strain',
        'qcp_model': 'SEOBNRv4PHM',
        # log10 B, EAS vs quasi-circular precessing -- the pair printed on the slide
        'log10_b_qcp': {'uniform': 1.23, 'log_uniform': 0.48},
        # log10 B, EAS vs quasi-circular aligned-spin (nested; anchors Lambda(-inf) = 1)
        'log10_b_qcas': {'uniform': 1.77, 'log_uniform': 1.05},
        'posterior': {'e': 0.40, 'lo': 0.25, 'hi': 0.48},     # e_10Hz mean and 90% HDI
        'source': SOURCE,
    },
    {
        'id': 'GW200105',
        'label': 'GW200105',
        'slides': ['page-14'],
        'blank': {'x': 309.622610 / 1440, 'y': 186.647178 / 810,
                  'w': (327.994324 - 309.622610) / 1440, 'h': (210.974280 - 186.647178) / 810},
        'fittable': False,
        'quoted': {'uniform': 17.0, 'log_uniform': 1.3},
        'reason': ('the two quoted numbers come from different analyses (uniform: Morras+ 2025 / '
                   'Kacanja+ 2025 / Planas+ 2025; log-uniform: Clarke+ 2026, e in [1e-4, 0.2] at '
                   '20 Hz). Their ratio, 13.1, exceeds ln(0.2/1e-4) = 7.60, the largest ratio any '
                   'non-negative likelihood can produce between those two priors, so no single '
                   'likelihood reproduces both and the reweighting is not defined.'),
        'source': 'Clarke+ 2026 (arXiv:2605.18742) Table 1; Morras+ 2025 (arXiv:2503.15393)',
    },
    {
        'id': 'GW190701',
        'label': 'GW190701',
        'slides': ['page-16', 'page-17'],
        'blank': {'x': 1177.078263 / 1440, 'y': 472.268537 / 810,
                  'w': (1198.751336 - 1177.078263) / 1440, 'h': (500.964111 - 472.268537) / 810},
        'row': 'BayesWave',
        'qcp_model': 'SEOBNRv4PHM',
        'log10_b_qcp': {'uniform': 2.61, 'log_uniform': 1.71},
        'log10_b_qcas': {'uniform': 3.00, 'log_uniform': 2.11},
        'posterior': {'e': 0.46, 'lo': 0.42, 'hi': 0.50},
        'source': SOURCE,
    },
    {
        'id': 'GW200129',
        'label': 'GW200129',
        'slides': ['page-23'],
        'blank': {'x': 1030.965505 / 1440, 'y': 104.496488 / 810,
                  'w': (1071.305602 - 1030.965505) / 1440, 'h': (140.108064 - 104.496488) / 810},
        'row': 'gwsubtract',
        'qcp_model': 'NRSur7dq4',
        'log10_b_qcp': {'uniform': 4.00, 'log_uniform': 3.23},
        'log10_b_qcas': {'uniform': 4.75, 'log_uniform': 3.98},
        'posterior': {'e': 0.34, 'lo': 0.28, 'hi': 0.45},
        'source': SOURCE,
    },
]


# --- priors (densities in x = log10 e) ---------------------------------------------

def uniform_pdf(x):
    """Uniform in e on [0, E_MAX], expressed as a density in log10 e."""
    return LN10 * (10.0 ** x) / E_MAX if x <= X_CEIL else 0.0


def log_uniform_pdf(x):
    """Log-uniform in e on [E_MIN_LOG, E_MAX]: flat in log10 e."""
    return 1.0 / (X_CEIL - X_REF) if X_REF <= x <= X_CEIL else 0.0


def ratio_bound(e_max, e_min):
    """Largest possible B_uniform / B_loguniform for any Lambda >= 0 on [0, e_max]:
    sup_x pi_U(x)/pi_LU(x) is reached at the shared upper edge and equals ln(e_max/e_min)."""
    return math.log(e_max / e_min)


RATIO_BOUND = ratio_bound(E_MAX, E_MIN_LOG)


# --- Lambda ------------------------------------------------------------------------

def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm(x, mu, sigma):
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2.0 * math.pi))


def lam(x, fit):
    """Lambda(x) = L(x)/Z_QCAS = 1 + A N(x; mu, sigma)."""
    return 1.0 + fit['A'] * _norm(x, fit['mu'], fit['sigma'])


def _bump_uniform(mu, sigma):
    """int_{-inf}^{X_CEIL} pi_U(x) N(x; mu, sigma) dx, in closed form.
    pi_U ∝ 10^x, so the Gaussian integral is a shifted normal CDF."""
    s = sigma * sigma * LN10
    return (LN10 / E_MAX) * (10.0 ** mu) * math.exp(0.5 * s * LN10) * _phi((X_CEIL - mu - s) / sigma)


def _bump_log_uniform(mu, sigma):
    """int pi_LU(x) N(x; mu, sigma) dx, in closed form (pi_LU is flat on [X_REF, X_CEIL])."""
    return (_phi((X_CEIL - mu) / sigma) - _phi((X_REF - mu) / sigma)) / (X_CEIL - X_REF)


uniform_pdf.bump = _bump_uniform
log_uniform_pdf.bump = _bump_log_uniform


def _bump_integral(pdf, mu, sigma, a, b, n=40000):
    """int_a^b pdf(x) N(x; mu, sigma) dx -- closed form for the two reference priors,
    midpoint rule otherwise."""
    exact = getattr(pdf, 'bump', None)
    if exact is not None and a <= AXIS['min'] and b >= X_CEIL:
        return exact(mu, sigma)
    h = (b - a) / n
    return h * sum(pdf(a + h * (i + 0.5)) * _norm(a + h * (i + 0.5), mu, sigma) for i in range(n))


def _mass(pdf, a, b, n=40000):
    if pdf is uniform_pdf and a <= AXIS['min'] and b >= X_CEIL:
        return 1.0 - (10.0 ** a) / E_MAX
    if pdf is log_uniform_pdf and a <= X_REF and b >= X_CEIL:
        return 1.0
    h = (b - a) / n
    return h * sum(pdf(a + h * (i + 0.5)) for i in range(n))


def integrate(pdf, fit, a=None, b=None):
    """int pdf(x) Lambda(x) dx over the prior's support."""
    a = AXIS['min'] if a is None else a
    b = X_CEIL if b is None else b
    return _mass(pdf, a, b) + fit['A'] * _bump_integral(pdf, fit['mu'], fit['sigma'], a, b)


def bayes_factor_continuum(pdf, fit):
    """B_{EAS/QCP} for a continuous prior -- the quantity the slides quote."""
    return fit['k'] * integrate(pdf, fit)


def _solve_mu(ratio, sigma):
    """Find mu <= X_CEIL with I_U(mu, sigma) / I_LU(mu, sigma) = ratio."""
    def f(mu):
        d = _bump_log_uniform(mu, sigma)
        if d <= 1e-300:
            return -ratio
        return _bump_uniform(mu, sigma) / d - ratio
    lo, hi = X_REF, X_CEIL
    if f(hi) < 0 or f(lo) > 0:
        raise ValueError(f'no mu <= log10({E_MAX}) reproduces both Bayes factors at sigma={sigma:.4g} '
                         f'(ratio {ratio:.3f}, ceiling {RATIO_BOUND:.3f})')
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def fit(event, sigma=None):
    """Fit Lambda(x) = 1 + A N(x; mu, sigma) to an event's two quoted Bayes factors.

    Returns k (the prior-independent QCAS->QCP offset), A, mu, sigma, plus the
    diagnostics the json and the tests use.
    """
    if not event.get('fittable', True):
        raise ValueError(f"{event['id']} is not fittable: {event['reason']}")

    qcp, qcas = event['log10_b_qcp'], event['log10_b_qcas']
    k_u = 10.0 ** (qcp['uniform'] - qcas['uniform'])
    k_l = 10.0 ** (qcp['log_uniform'] - qcas['log_uniform'])
    k_spread = abs(math.log10(k_u) - math.log10(k_l))
    k = 10.0 ** (0.5 * (math.log10(k_u) + math.log10(k_l)))

    b_u = 10.0 ** qcas['uniform']
    b_l = 10.0 ** qcas['log_uniform']
    ratio = (b_u - 1.0) / (b_l - 1.0)

    p = event['posterior']
    if sigma is None:
        # log-space Gaussian matched to the published 90% HDI on e_10Hz
        sigma = (math.log10(p['hi']) - math.log10(p['lo'])) / (2.0 * Z90)

    mu = _solve_mu(ratio, sigma)
    i_l = _bump_integral(log_uniform_pdf, mu, sigma, X_REF, X_CEIL)
    A = (b_l - 1.0) / i_l

    out = {
        'id': event['id'], 'k': k, 'k_spread_dex': k_spread, 'A': A, 'mu': mu, 'sigma': sigma,
        'ratio': ratio, 'ratio_bound': RATIO_BOUND, 'ratio_fraction': ratio / RATIO_BOUND,
        # the delta-function limit: pi_U(e)/pi_LU(e) = ratio has the closed-form solution
        'e_star': 10.0 ** mu,
        'e_star_delta': E_MAX * ratio / RATIO_BOUND,
        'b_qcas': {'uniform': b_u, 'log_uniform': b_l},
    }
    return out


# --- the poll grid -----------------------------------------------------------------

def axis_edges(axis=None):
    a = axis or AXIS
    n = a['bins']
    return [a['min'] + (a['max'] - a['min']) * i / n for i in range(n + 1)]


def lambda_bins(fit_, edges):
    """Bin-averaged Lambda: (1/dx) int_bin Lambda dx, exact for the Gaussian."""
    mu, sigma, A = fit_['mu'], fit_['sigma'], fit_['A']
    out = []
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        mass = _phi((b - mu) / sigma) - _phi((a - mu) / sigma)
        out.append(1.0 + A * mass / (b - a))
    return out


def reference_masses(kind, edges):
    """Bin masses of the *papers'* uniform / log-uniform prior on the poll grid."""
    if kind == 'uniform':
        e = [10.0 ** x for x in edges]
        return [max(0.0, min(e[i + 1], E_MAX) - min(e[i], E_MAX)) / E_MAX for i in range(len(edges) - 1)]
    if kind == 'log_uniform':
        span = X_CEIL - X_REF
        return [max(0.0, min(edges[i + 1], X_CEIL) - max(edges[i], X_REF)) / span
                for i in range(len(edges) - 1)]
    raise ValueError(kind)


def bayes_factor(weights, lambda_bins_, k):
    """B_{EAS/QCP} for a discrete prior given as bin masses.  None if there is nothing
    to integrate (no responses yet, or a degenerate curve) rather than a NaN."""
    if not weights or len(weights) != len(lambda_bins_):
        return None
    total = sum(weights)
    if not total > 0:
        return None
    return k * sum(w * l for w, l in zip(weights, lambda_bins_)) / total


# --- the generated payload ---------------------------------------------------------

def _sigma_sensitivity(event, edges, probe):
    """How much B_expert moves across the admissible widths, for a fixed probe prior."""
    base = fit(event)
    vals = []
    for scale in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        try:
            f = fit(event, sigma=base['sigma'] * scale)
        except ValueError:
            continue
        b = bayes_factor(probe, lambda_bins(f, edges), f['k'])
        vals.append({'sigma': f['sigma'], 'mu': f['mu'], 'B': b})
    return vals


def _probe(edges):
    """A stand-in 'expert' curve for the sensitivity numbers: log-normal in log10 e,
    centred at e = 1e-3 with a 1.5-dex width.  Only used for diagnostics."""
    w = []
    for i in range(len(edges) - 1):
        c = 0.5 * (edges[i] + edges[i + 1])
        w.append(math.exp(-0.5 * ((c + 3.0) / 1.5) ** 2))
    s = sum(w)
    return [x / s for x in w]


def build():
    edges = axis_edges()
    probe = _probe(edges)
    events = []
    for ev in EVENTS:
        row = {
            'id': ev['id'], 'label': ev['label'], 'slides': list(ev['slides']),
            'blank': {k: round(v, 6) for k, v in ev['blank'].items()},
            'source': ev['source'], 'fittable': ev.get('fittable', True),
        }
        if not row['fittable']:
            row.update({'lambda': None, 'k': None, 'mu': None, 'sigma': None,
                        'quoted': ev['quoted'], 'reason': ev['reason'],
                        'ratio': ev['quoted']['uniform'] / ev['quoted']['log_uniform'],
                        'ratio_bound': ratio_bound(0.2, 1e-4)})
            events.append(row)
            continue

        f = fit(ev)
        lb = lambda_bins(f, edges)
        quoted = {k: 10.0 ** v for k, v in ev['log10_b_qcp'].items()}
        # discretisation error of the round trip on the 0.125-dex grid
        err = max(abs(bayes_factor(reference_masses(k, edges), lb, f['k']) / quoted[k] - 1.0)
                  for k in ('uniform', 'log_uniform'))
        row.update({
            'quoted': quoted,
            'quoted_log10': dict(ev['log10_b_qcp']),
            'qcp_model': ev['qcp_model'], 'row': ev['row'],
            'posterior': ev['posterior'],
            'k': f['k'], 'k_spread_dex': f['k_spread_dex'],
            'A': f['A'], 'mu': f['mu'], 'sigma': f['sigma'],
            'e_star': f['e_star'], 'e_star_delta': f['e_star_delta'],
            'ratio': f['ratio'], 'ratio_bound': f['ratio_bound'],
            'ratio_fraction': f['ratio_fraction'],
            'lambda': lb,
            'grid_tolerance': max(0.01, math.ceil(err * 200) / 200),
            'grid_error': err,
            'sigma_sensitivity': _sigma_sensitivity(ev, edges, probe),
        })
        events.append(row)

    return {
        'note': ('Lambda(log10 e) = 1 + A N(mu, sigma) fitted to the uniform- and log-uniform-prior '
                 'Bayes factors of each event; B_expert = k * sum(w_i Lambda_i) over the audience '
                 'mixture. See tools/expertbf.py for the assumptions.'),
        'axis': dict(AXIS),
        'edges': edges,
        'prior': {'e_max': E_MAX, 'e_min_log': E_MIN_LOG, 'ratio_bound': RATIO_BOUND},
        'events': events,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, '..', 'static', 'expertbf', 'expertbf.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = build()
    with open(out, 'w') as fh:
        json.dump(data, fh, indent=1)
        fh.write('\n')
    for r in data['events']:
        if r['fittable']:
            print(f"{r['id']:12s} B_U={r['quoted']['uniform']:10.1f} B_LU={r['quoted']['log_uniform']:9.1f}  "
                  f"k={r['k']:.4f} (spread {r['k_spread_dex']:.3f} dex)  e*={r['e_star']:.3f} "
                  f"(published {r['posterior']['e']} [{r['posterior']['lo']}, {r['posterior']['hi']}])  "
                  f"ratio {r['ratio']:.2f}/{r['ratio_bound']:.2f}  grid err {r['grid_error']*100:.1f}%")
        else:
            print(f"{r['id']:12s} not computable: {r['reason'][:70]}...")
    print('wrote', os.path.normpath(out))


if __name__ == '__main__':
    main()
