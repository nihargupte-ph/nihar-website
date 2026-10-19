"""Precompute the single-single-capture forward model for the `16-forward.html` slide.

Run from the deck folder (needs numpy, scipy, poppler's `pdftocairo` and pyseobnr):

    micromamba run -n django-nihar-website python tools/forwardmodel.py

and it writes `static/forward/forward.json`. The browser only replays what is in there --
no physics runs client-side.

THE CHAIN (Gupte+ 2026, arXiv:2603.29019, Secs. 5-7)
-----------------------------------------------------
1. host     NSC with probability beta, else GC.
2. sigma    log10 sigma ~ N(mu, std), fitted (mean / std of log10 sigma, as in the paper's
            notebook) to 112 Milky Way GCs (Baumgardt & Hilker 2018, Gaia + ground RVs) or 108
            NSCs (Baldassare+ 2022, HST). The raw catalogues are copied below.
3. binary   m1, m2 from Power Law + Peak at the GWTC-3 median hyperparameters (an illustration;
            the paper itself fits the GWTC-4 broken-power-law-two-peaks model). Then the capture
            model, ported line for line from `p_e_given_sigma_Mtot_mu` in the paper's
            `ecc_dist_cole_final_plot.ipynb` (the one that drew Fig. 3; the copy in
            `ecc_dist_cole_checkpoint.ipynb` has `forbref` unsquared in Kepler's law): v_inf = sqrt(6) sigma x with p(x) ~ x^(3/7) |N(0,1)|,
            r_p ~ U[0, r_p,max(v_inf)], and Peters' a(e) inverted at an orbital frequency of 10 Hz.
4. p_det    the anomaly-averaged p_det(e) of the paper's Fig. 4, read off the *vector* figure
            (tools/paper/selection_function.pdf). It is for one reference system (chirp mass 35,
            q = 1, d_L = 2 Gpc, HLV) and stops at e = 0.57; larger e hold the last value. So the
            slide shows only the *eccentricity* part of the selection effect.
            The slide draws the curve with its fiducial binary as a caption; a drawn binary is only
            marked by its e, never given that curve's p_det.

CHECK: `check_fig3()` recomputes the paper's Fig. 3 (m1 = 30, m2 = 10, sigma = 5..300 km/s) and
compares peak positions with the curves extracted from tools/paper/ecc_distribution.pdf.
"""
import json
import math
import os
import re
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DECK = os.path.dirname(HERE)
OUT = os.path.join(DECK, 'static', 'forward', 'forward.json')

# --- constants, as in the paper's notebook (cgs) ------------------------------------
GMsun = 1.3271244e26
cspeed = 2.99792458e10
forbref = 10.0                # reference *orbital* frequency [Hz]

# --- step 2 data: 1D central velocity dispersions [km/s] ----------------------------
# Baumgardt & Hilker (2018) Table 2, 112 Milky Way GCs
GC_SIGMA_1D_KMS = [
    12.2, 3.3, 8.8, 5.6, 6.1, 10.2, 6.5, 1.6, 7.1, 1.3, 14.4, 1.8,
    1.4, 4.5, 1, 3.1, 4.9, 2.5, 3.7, 4.8, 5.9, 1.6, 17.6, 8.1,
    9.3, 1.6, 5.3, 8.9, 3.1, 11.9, 0.6, 3.9, 7.7, 6.5, 8.3, 0.8,
    9.5, 4.6, 2.7, 2.2, 9.2, 2.4, 4.3, 1.6, 9.2, 7.1, 4.5, 6.2,
    4.5, 15.2, 11, 8.9, 7.5, 5.7, 9, 8, 4.5, 7.8, 6.2, 4.4,
    3, 5.5, 3.9, 23.2, 7.8, 2.9, 18.2, 11.1, 5.2, 19, 15.8, 18.8,
    8.7, 3.4, 8.2, 2.8, 6.4, 5.9, 6.4, 8.7, 8.5, 3.5, 3.3, 7.5,
    4.2, 6.1, 12.6, 6.9, 8.4, 7.1, 5, 16.2, 5.3, 3.2, 8.3, 7.2,
    6.1, 0.8, 2, 4.8, 1.4, 3.7, 3.3, 11.8, 4.7, 4.4, 12.9, 10.6,
    5.5, 1, 1.2, 1.4,
]
# Baldassare et al. (2022) Table 1, 108 NSCs (1D dispersions from Stone et al. 2017)
NSC_SIGMA_1D_KMS = [
    93.39, 23.99, 29.47, 30.88, 100.86, 67.15, 22.01, 10.43, 82.51, 32.07, 41.97, 60.35,
    79.84, 21.04, 25.49, 56.43, 84.03, 238.72, 124.05, 50.19, 107.57, 30.83, 61.89, 46.21,
    72.63, 395.65, 186.72, 122.32, 61.95, 70.23, 35.37, 85.74, 46.51, 101.82, 70.73, 90.77,
    183.49, 28.98, 23.96, 27.47, 89.98, 76.3, 52.59, 41.47, 87.39, 97.96, 41.09, 155.48,
    11.39, 23.61, 10.47, 99.99, 263.07, 90.98, 51.72, 32.17, 20.99, 42.75, 67.15, 24.54,
    66.11, 68.78, 74.14, 18.88, 66.56, 13.23, 45.81, 61.78, 130.63, 24.66, 65.3, 33.76,
    28.3, 17.17, 63.38, 55.99, 234.18, 82.73, 38.9, 130.07, 15.38, 20.32, 17.42, 84.08,
    214.33, 111.53, 57.43, 15.56, 34.77, 51, 122.3, 6.85, 33.94, 56.68, 28.17, 102.52,
    56.26, 30.72, 11.08, 33.89, 16.01, 36.58, 37.5, 34.38, 24.13, 198.11, 61.89, 25.76,
]

# --- step 3: Power Law + Peak, GWTC-3 (Abbott+ 2023, PRX 13 011048) median hyperparameters ---
PLP = {'alpha': 3.40, 'beta_q': 1.08, 'mmin': 5.08, 'mmax': 86.85,
       'lam_peak': 0.039, 'mpp': 33.73, 'sigpp': 3.56, 'delta_m': 4.83}

LOGE = {'min': -4.0, 'max': 0.0, 'bins': 48}          # the slide's log10 e axis
SIGMA_GRID_KMS = np.geomspace(0.5, 500, 31)            # p(log e | sigma) curves, nearest is shown
N_POOL = 2500                                          # replayable draws per host
N_CURVE = 6000                                         # binaries per sigma-grid curve
SEED = 20261020


# --- the capture model ----------------------------------------------------------------

def draw_x(rng, n):
    """|N(0,1)| reweighted by x^(3/7) (accept-reject), as in the notebook."""
    out = np.empty(0)
    while out.size < n:
        x = np.abs(rng.standard_normal(2 * (n - out.size) + 100))
        y = rng.random(x.size)
        out = np.r_[out, x[y < np.power(x, 3.0 / 7.0)]]
    return out[:n]


def capture_e(rng, sigma_kms, m1, m2):
    """One e_10Hz per binary (arrays broadcast). Port of the notebook's p_e_given_sigma_Mtot_mu:
    there every r_p on a uniform grid in [0, r_p,max] is kept, here one uniform r_p per draw."""
    sigma_kms, m1, m2 = np.broadcast_arrays(np.asarray(sigma_kms, float), m1, m2)
    n = sigma_kms.size
    Mtot = (m1 + m2).ravel()
    mu = (m1 * m2).ravel() / Mtot
    sigma_rel = math.sqrt(2.0) * math.sqrt(3.0) * sigma_kms.ravel() * 1e5
    atarg = (GMsun * Mtot / (4.0 * math.pi ** 2 * forbref ** 2)) ** (1.0 / 3.0)   # Kepler at f_orb
    vinf = draw_x(rng, n) * sigma_rel
    coeff = (85.0 * math.pi / (6.0 * math.sqrt(2.0))) ** (2.0 / 7.0)
    coeff = coeff * GMsun * (mu * Mtot ** 2.5) ** (2.0 / 7.0) / cspeed ** (10.0 / 7.0)
    rpmax = coeff / np.power(vinf, 4.0 / 7.0)
    rp = rng.random(n) * rpmax
    C = 1.76 * rp
    lo, hi = np.zeros(n), np.ones(n)
    for _ in range(60):
        e = 0.5 * (lo + hi)
        es = np.maximum(e, 1e-300)
        a = C / (np.power(es, -12.0 / 19.0) * (1.0 - e * e) * np.power(1.0 + 121.0 * e * e / 304.0, -870.0 / 2299.0))
        high = a > atarg
        hi = np.where(high, e, hi)
        lo = np.where(high, lo, e)
    e = (0.5 * (lo + hi)).reshape(sigma_kms.shape)
    rp_M = (rp / (GMsun * Mtot / cspeed ** 2)).reshape(sigma_kms.shape)          # r_p in units of GM/c^2
    return e, (vinf / 1e5).reshape(sigma_kms.shape), rp_M


# --- the mass model ---------------------------------------------------------------------

def smoothing(m, mmin, delta):
    out = np.zeros_like(m)
    out[m >= mmin + delta] = 1.0
    mid = (m > mmin) & (m < mmin + delta)
    mp = m[mid] - mmin
    with np.errstate(over="ignore"):              # exp overflows to inf -> S = 0, as intended
        out[mid] = 1.0 / (np.exp(delta / mp + delta / (mp - delta)) + 1.0)
    return out


def plp_m1(m):
    p = PLP
    pl = np.where((m >= p['mmin']) & (m <= p['mmax']), m ** -p['alpha'], 0.0)
    pl /= np.trapezoid(pl, m)
    g = np.exp(-0.5 * ((m - p['mpp']) / p['sigpp']) ** 2)
    g /= np.trapezoid(g, m)
    out = ((1 - p['lam_peak']) * pl + p['lam_peak'] * g) * smoothing(m, p['mmin'], p['delta_m'])
    return out / np.trapezoid(out, m)


def draw_masses(rng, n):
    grid = np.linspace(2.0, 100.0, 4000)
    pdf = plp_m1(grid)
    cdf = np.cumsum(pdf)
    cdf /= cdf[-1]
    m1 = np.interp(rng.random(n), cdf, grid)
    m2 = np.empty(n)
    for i, a in enumerate(m1):           # p(q | m1) ~ q^beta S(q m1), q in (mmin/m1 .. 1)
        q = np.linspace(2.0 / a, 1.0, 400)
        w = q ** PLP['beta_q'] * smoothing(q * a, PLP['mmin'], PLP['delta_m'])
        c = np.cumsum(w)
        m2[i] = a * np.interp(rng.random() * c[-1], c, q)
    return m1, m2


# --- figures read off the paper's vector PDFs -------------------------------------------

def _svg(pdf):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'f.svg')
        subprocess.run(['pdftocairo', '-svg', pdf, out], check=True)
        return open(out).read()


def _pts(d):
    return np.array([[float(a), float(b)] for a, b in re.findall(r'([-\d.]+) ([-\d.]+)', d)])


def fig4_pdet():
    """Bottom panel of Fig. 4. Ticks (pre-transform coordinates): x 71.28 -> e = 0, 45.95 per 0.1;
    y 47.85 -> 0.35, 36.10 per 0.05."""
    s = _svg(os.path.join(HERE, 'paper', 'selection_function.pdf'))
    curves = {}
    for name, col in (('fixed', '29.803467%,44.7052%,69.018555%'), ('averaged', '86.665344%,51.763916%,32.156372%')):
        ds = [d for d in re.findall(r'stroke:rgb\(%s\);[^"]*" d="([^"]*)" transform' % re.escape(col), s)]
        d = [d for d in ds if _pts(d)[:, 1].max() < 156][0]          # the panel spanning y 39.6..156
        p = _pts(d)
        e = (p[:, 0] - 71.28) / 459.5
        pdet = 0.35 + (p[:, 1] - 47.85) / (36.10 / 0.05)
        o = np.argsort(e)
        curves[name] = {'e': np.round(e[o], 4).tolist(), 'pdet': np.round(pdet[o], 4).tolist()}
    return curves


def fig3_curves():
    """Fig. 3 step outlines: x spans the axes 71.20..555.76 = log10 e -4..0, y from the baseline."""
    s = _svg(os.path.join(HERE, 'paper', 'ecc_distribution.pdf'))
    cols = ['29.803467%,44.7052%,69.018555%', '33.332825%,65.881348%,40.783691%',
            '86.665344%,51.763916%,32.156372%', '88.626099%,29.019165%,19.999695%',
            '41.567993%,31.764221%,63.920593%']
    out = {}
    for sig, col in zip([5, 10, 30, 100, 300], cols):
        ds = re.findall(r'stroke:rgb\(%s\);[^"]*" d="([^"]*)" transform' % re.escape(col), s)
        p = _pts([d for d in ds if d.startswith('M -1.0')][0])
        x = -4 + (p[:, 0] - 71.198645) / (555.761769 - 71.198645) * 4
        out[sig] = (x, p[:, 1] - 76.485526)
    return out


def check_fig3(rng):
    ref = fig3_curves()
    rows = []
    for sig, (x, y) in ref.items():
        flat = np.abs(np.diff(y)) < 1e-6                     # horizontal segments = bin tops
        mids = 0.5 * (x[:-1] + x[1:])[flat]
        peak_paper = float(mids[np.argmax(y[:-1][flat])])
        e = capture_e(rng, np.full(40000, sig), 30.0, 10.0)[0]
        h, b = np.histogram(np.log10(e), bins=100, range=(-11, -0.1))
        peak_mine = float(0.5 * (b[1:] + b[:-1])[np.argmax(h)])
        rows.append({'sigma': sig, 'peak_paper': round(peak_paper, 2), 'peak_here': round(peak_mine, 2)})
        print(f'  Fig. 3 check  sigma={sig:3d} km/s  peak log10 e: paper {peak_paper:+.2f}  here {peak_mine:+.2f}')
    return rows


# --- step 4 visual: an eccentric signal against its quasi-circular template --------------

def waveforms():
    from pyseobnr.generate_waveform import GenerateWaveform
    m = 35.0 * 2 ** 0.2                     # chirp mass 35, q = 1: the Fig. 4 reference system
    out = {}
    for name, e in (('circular', 0.0), ('eccentric', 0.3)):
        p = dict(mass1=m, mass2=m, spin1z=0.0, spin2z=0.0, eccentricity=e, rel_anomaly=0.0,
                 f22_start=10.0, deltaT=1 / 4096.0, f_max=2048.0, distance=2000.0, inclination=0.0,
                 approximant='SEOBNRv5EHM')
        hp, _ = GenerateWaveform(p).generate_td_polarizations()
        h = np.asarray(hp.data.data)
        t = np.arange(h.size) * hp.deltaT + float(hp.epoch)      # t = 0 at merger
        keep = (t > -1.2) & (t < 0.05)
        t, h = t[keep], h[keep]
        idx = np.linspace(0, t.size - 1, 1400).astype(int)
        out[name] = {'t': np.round(t[idx], 5).tolist(), 'h': np.round(h[idx] / 5e-22, 4).tolist()}
    out['e'] = 0.3
    out['system'] = 'SEOBNRv5EHM, m1 = m2 = 40.2, e = 0 vs 0.3 at f22 = 10 Hz, plus polarisation'
    return out


# --- step 4 animation: scan a small quasi-circular bank against the same eccentric signal ---
# A cartoon of a search, not pycbc: 6 x 4 SEOBNRv5EHM templates at e = 0 on a (chirp mass, q) grid,
# each matched against the e = 0.3 signal above (plus polarisation, face-on, 2 Gpc) with the aLIGO
# design PSD from 10 Hz, maximised over time and phase. SNR = match x the signal's optimal SNR.
BANK_MC = [31.0, 33.0, 35.0, 37.0, 39.0, 41.0]
BANK_Q = [1.0, 0.8, 0.6, 0.45]


def template_bank():
    import lal
    import lalsimulation as ls
    from pyseobnr.generate_waveform import GenerateWaveform
    dt, n = 1 / 4096.0, 2 ** 16

    def gen(m1, m2, e):
        p = dict(mass1=m1, mass2=m2, spin1z=0.0, spin2z=0.0, eccentricity=e, rel_anomaly=0.0,
                 f22_start=10.0, deltaT=dt, f_max=2048.0, distance=2000.0, inclination=0.0,
                 approximant='SEOBNRv5EHM')
        hp, _ = GenerateWaveform(p).generate_td_polarizations()
        x = np.zeros(n)
        x[:hp.data.length] = hp.data.data
        return x, float(hp.epoch)

    f = np.fft.rfftfreq(n, dt)
    psd = lal.CreateREAL8FrequencySeries('psd', 0, 0, f[1], lal.DimensionlessUnit, f.size)
    ls.SimNoisePSDaLIGODesignSensitivityP1200087(psd, 10.0)
    S = np.array(psd.data.data)
    S[(f < 10) | (S <= 0)] = np.inf
    norm = lambda a: math.sqrt(4 * f[1] * np.sum(np.abs(a) ** 2 / S))

    s, epoch = gen(35.0 * 2 ** 0.2, 35.0 * 2 ** 0.2, 0.3)
    sf = np.fft.rfft(s) * dt
    rho_opt = norm(sf)
    t = np.arange(n) * dt + epoch
    keep = np.flatnonzero((t > -1.2) & (t < 0.05))
    idx = keep[np.linspace(0, keep.size - 1, 1400).astype(int)]      # the same samples card 4 plots

    rows = []
    for mc in BANK_MC:
        for q in BANK_Q:
            M = mc / (q / (1 + q) ** 2) ** 0.6
            h, _ = gen(M / (1 + q), M * q / (1 + q), 0.0)
            hf = np.fft.rfft(h) * dt
            # complex overlap against lag: |z| is the phase-maximised overlap, its peak the time shift
            prod = np.zeros(n, complex)
            prod[:f.size] = sf * np.conj(hf) / S
            z = 4 * f[1] * np.fft.ifft(prod) * n
            k = int(np.argmax(np.abs(z)))
            match = abs(z[k]) / (rho_opt * norm(hf))
            # the template shifted and rotated onto the signal, for the overlay
            spec = np.zeros(n, complex)
            spec[:f.size] = 2 * hf * np.exp(1j * np.angle(z[k]))
            al = np.roll(np.real(np.fft.ifft(spec)) / dt, k)
            check = 4 * f[1] * np.real(np.sum(sf * np.conj(np.fft.rfft(al) * dt) / S)) / (rho_opt * norm(hf))
            assert abs(check - match) < 0.02, (mc, q, check, match)
            rows.append({'mc': mc, 'q': q, 'match': round(float(match), 4),
                         'snr': round(float(match * rho_opt), 2),
                         'h': np.round(al[idx] / 5e-22, 2).tolist()})
    best = max(rows, key=lambda r: r['snr'])
    print(f'  bank: optimal SNR {rho_opt:.2f}; best template Mc = {best["mc"]}, q = {best["q"]}, '
          f'match {best["match"]:.3f}, SNR {best["snr"]:.2f}')
    return {'mc': BANK_MC, 'q': BANK_Q, 'rho_opt': round(rho_opt, 2), 'templates': rows,
            'system': 'SEOBNRv5EHM at e = 0 vs the e = 0.3 signal; aLIGO design PSD (P1200087) from 10 Hz, '
                      'one detector, maximised over time and phase'}


# --- assemble ------------------------------------------------------------------------------

def build():
    rng = np.random.default_rng(SEED)
    hosts = {}
    for host, data in (('gc', GC_SIGMA_1D_KMS), ('nsc', NSC_SIGMA_1D_KMS)):
        l = np.log10(np.asarray(data))
        hosts[host] = {'mu': float(l.mean()), 'std': float(l.std()), 'n': len(data),
                       'data_kms': data}
    pdet = fig4_pdet()
    ea, pa = np.array(pdet['averaged']['e']), np.array(pdet['averaged']['pdet'])
    pdet_of = lambda e: np.interp(e, ea, pa)            # holds the end values outside [0, 0.57]

    edges = np.linspace(LOGE['min'], LOGE['max'], LOGE['bins'] + 1)
    pool = {}
    for host in ('gc', 'nsc'):
        h = hosts[host]
        sig = 10 ** rng.normal(h['mu'], h['std'], N_POOL)
        m1, m2 = draw_masses(rng, N_POOL)
        e, vinf, rp_M = capture_e(rng, sig, m1, m2)
        pd = pdet_of(e)
        pool[host] = [[round(float(a), 2), round(float(b), 1), round(float(c), 1), min(float(f'{d:.4g}'), 0.9999),
                       round(float(v), 1), round(float(p), 3), float(f'{r:.3g}')]
                      for a, b, c, d, v, p, r in zip(sig, m1, m2, e, vinf, pd, rp_M)]

    curves = []
    for s in SIGMA_GRID_KMS:
        m1, m2 = draw_masses(rng, N_CURVE)
        e = capture_e(rng, np.full(N_CURVE, s), m1, m2)[0]
        c = np.histogram(np.log10(np.clip(e, 1e-30, None)), bins=edges)[0] / N_CURVE / np.diff(edges)
        curves.append({'sigma': round(float(s), 3), 'p': np.round(c, 4).tolist()})

    mgrid = np.linspace(2, 100, 197)
    return {
        'note': 'Built by tools/forwardmodel.py; see its docstring for every assumption.',
        'loge': {**LOGE, 'edges': np.round(edges, 4).tolist()},
        'hosts': hosts,
        'pool_fields': ['sigma_kms', 'm1', 'm2', 'e10Hz', 'vinf_kms', 'pdet', 'rp_GM_c2'],
        'pool': pool,
        'curves': curves,
        'mass': {'m': mgrid.tolist(), 'p': np.round(plp_m1(mgrid), 5).tolist(), 'model': 'Power Law + Peak, GWTC-3 medians', **PLP},
        'pdet': pdet,
        'pdet_system': 'chirp mass 35 Msun, q = 1, d_L = 2 Gpc, chi_eff = 0, HLV (Gupte+ 2026 Fig. 4)',
        'fig3_check': check_fig3(rng),
        'waveforms': waveforms(),
        'bank': template_bank(),
    }


if __name__ == '__main__':
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    for host in ('gc', 'nsc'):
        h = data['hosts'][host]
        print(f'  {host}: log10 sigma = {h["mu"]:.3f} +- {h["std"]:.3f}  (sigma ~ {10**h["mu"]:.1f} km/s, N = {h["n"]})')
    print(f'wrote {OUT} ({os.path.getsize(OUT) / 1e3:.0f} kB)')
