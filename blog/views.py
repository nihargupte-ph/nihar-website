import json
import logging
import os
from math import pi

import h5py
import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from blog.catalog_helpers import (
    CATALOG_POSTERIOR_COLUMNS,
    CATALOG_POSTERIOR_PRECISION,
    CATALOG_RUNS,
    GWTC_TO_HDF5_ALIASES,
    QC_BOUNDARY,
    TRAJECTORY_DECIMAL_COLS,
    TRAJECTORY_SIGFIG_COLS,
    round_sig,
)
from blog.simulate_helpers import (
    capture_eccentricity_distribution,
    downsample,
    load_asd,
    whiten_signal_and_generate_noise,
)
from blog.waveforms import generate_eccentric_bbh_waveform

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulate your own eccentric BBH
# ---------------------------------------------------------------------------

def analyzing_eccentric_bbh(request):
    return render(request, 'blog/simulate_your_own_eccentric_bbh.html')


@csrf_exempt
@require_POST
def simulate_bbh(request):
    try:
        data = json.loads(request.body)
        m1 = float(data['bh1_mass'])
        s1 = float(data['bh1_spin'])
        m2 = float(data['bh2_mass'])
        s2 = float(data['bh2_spin'])
        eccentricity = float(data['eccentricity'])
        mean_anomaly_deg = float(data['mean_anomaly'])

        result = generate_eccentric_bbh_waveform(
            m1=m1,
            m2=m2,
            spin1z=s1,
            spin2z=s2,
            eccentricity=eccentricity,
            rel_anomaly_rad=mean_anomaly_deg * pi / 180.0,
        )
        traj = result['trajectory']
        pol = result['polarizations']
        meta = result['meta']

        h1_asd, l1_asd = load_asd()
        t_strain_h1, h1_combined, h1_signal = whiten_signal_and_generate_noise(
            pol['hp'], meta['dt'], h1_asd
        )
        t_strain_l1, l1_combined, l1_signal = whiten_signal_and_generate_noise(
            pol['hp'], meta['dt'], l1_asd
        )
        t_strain_h1 = t_strain_h1 + meta['epoch']
        t_strain_l1 = t_strain_l1 + meta['epoch']

        response = {
            'status': 'ok',
            'trajectory': {
                't': downsample(traj['t']).tolist(),
                'x1': downsample(traj['x1']).tolist(),
                'y1': downsample(traj['y1']).tolist(),
                'x2': downsample(traj['x2']).tolist(),
                'y2': downsample(traj['y2']).tolist(),
            },
            'polarizations': {
                't': downsample(pol['t']).tolist(),
                'hp': downsample(pol['hp']).tolist(),
                'hc': downsample(pol['hc']).tolist(),
            },
            'strain': {
                'H1': {
                    't': downsample(t_strain_h1).tolist(),
                    'noise_plus_signal': downsample(h1_combined).tolist(),
                    'signal': downsample(h1_signal).tolist(),
                },
                'L1': {
                    't': downsample(t_strain_l1).tolist(),
                    'noise_plus_signal': downsample(l1_combined).tolist(),
                    'signal': downsample(l1_signal).tolist(),
                },
            },
        }

        return JsonResponse(response)

    except Exception as e:
        logger.exception("Simulation failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def analyze_bbh(request):
    """
    Generate mock posterior samples as Gaussians around injected parameters.
    Width scales inversely with SNR (louder signal = tighter posterior).
    """
    try:
        data = json.loads(request.body)
        m1 = float(data['bh1_mass'])
        m2 = float(data['bh2_mass'])
        s1 = float(data['bh1_spin'])
        s2 = float(data['bh2_spin'])
        ecc = float(data['eccentricity'])
        anomaly = float(data['mean_anomaly'])

        n_samples = 5000

        # Ensure m1 >= m2
        if m2 > m1:
            m1, m2 = m2, m1
            s1, s2 = s2, s1

        # Compute well-measured PE quantities
        # Chirp mass: Mc = (m1*m2)^(3/5) / (m1+m2)^(1/5)
        total_mass = m1 + m2
        eta = m1 * m2 / total_mass ** 2
        mc_inj = total_mass * eta ** 0.6
        # Effective spin: chi_eff = (m1*s1 + m2*s2) / (m1+m2)
        chi_eff_inj = (m1 * s1 + m2 * s2) / total_mass
        q_inj = m1 / m2  # mass ratio q >= 1

        # SNR proxy for width scaling
        snr_proxy = total_mass / 40.0 * 10.0

        rng = np.random.default_rng()

        # Sample Gaussians in the well-measured space: (Mc, chi_eff, ecc, anomaly)
        sigma_mc = 1.5 / max(snr_proxy, 1.0)
        sigma_chi = 0.08 / max(snr_proxy, 1.0)
        sigma_ecc = 0.1 / max(snr_proxy, 1.0)
        sigma_anom = 40.0 / max(snr_proxy, 1.0)

        # Small random offsets so peak isn't always at injection
        mc_samples = rng.normal(mc_inj + rng.normal(0, 0.3 * sigma_mc), sigma_mc, n_samples)
        chi_eff_samples = rng.normal(chi_eff_inj + rng.normal(0, 0.3 * sigma_chi), sigma_chi, n_samples)
        mc_samples = np.clip(mc_samples, 1.0, 200.0)
        chi_eff_samples = np.clip(chi_eff_samples, -1.0, 1.0)

        # Mass ratio: broader posterior, weakly correlated with Mc
        sigma_q = 0.8 / max(snr_proxy, 1.0)
        q_samples = rng.normal(q_inj + rng.normal(0, 0.3 * sigma_q), sigma_q, n_samples)
        q_samples = np.clip(q_samples, 1.0, 10.0)

        # Derive component masses from (Mc, q):
        # Mc = M_total * eta^(3/5), eta = q/(1+q)^2
        # M_total = Mc / eta^(3/5), m1 = M_total * q/(1+q), m2 = M_total / (1+q)
        eta_samples = q_samples / (1 + q_samples) ** 2
        mtot_samples = mc_samples / eta_samples ** 0.6
        m1_samples = mtot_samples * q_samples / (1 + q_samples)
        m2_samples = mtot_samples / (1 + q_samples)
        m1_samples = np.clip(m1_samples, 1.0, 200.0)
        m2_samples = np.clip(m2_samples, 1.0, 200.0)

        # Derive component spins from (chi_eff, q):
        # chi_eff = (m1*s1 + m2*s2)/(m1+m2) = (q*s1 + s2)/(1+q)
        # Assign: s1 ~ chi_eff + noise, s2 ~ chi_eff + noise, adjusted to match chi_eff
        # This gives broad individual spin posteriors (poorly constrained) but correlated
        spin_noise = rng.normal(0, 0.15, n_samples)
        s1_samples = chi_eff_samples + spin_noise
        s2_samples = chi_eff_samples * (1 + q_samples) / q_samples - s1_samples * 1.0 / q_samples
        # Add extra noise to s2 (it's even less constrained)
        s2_samples += rng.normal(0, 0.1, n_samples)
        s1_samples = np.clip(s1_samples, 0, 1.0)
        s2_samples = np.clip(s2_samples, 0, 1.0)

        # Eccentricity and anomaly: direct Gaussians (independent)
        ecc_samples = rng.normal(ecc + rng.normal(0, 0.3 * sigma_ecc), sigma_ecc, n_samples)
        anom_samples = rng.normal(anomaly + rng.normal(0, 0.3 * sigma_anom), sigma_anom, n_samples)
        ecc_samples = np.clip(ecc_samples, 0, 1.0)
        anom_samples = np.clip(anom_samples, 0, 360)

        posteriors = {
            'm1': {'samples': m1_samples.tolist(), 'injected': m1, 'label': 'Mass 1 (M\u2609)'},
            'm2': {'samples': m2_samples.tolist(), 'injected': m2, 'label': 'Mass 2 (M\u2609)'},
            's1z': {'samples': s1_samples.tolist(), 'injected': s1, 'label': 'Spin 1'},
            's2z': {'samples': s2_samples.tolist(), 'injected': s2, 'label': 'Spin 2'},
            'ecc': {'samples': ecc_samples.tolist(), 'injected': ecc, 'label': 'Eccentricity'},
            'anomaly': {'samples': anom_samples.tolist(), 'injected': anomaly, 'label': 'Mean Anomaly (\u00b0)'},
        }

        return JsonResponse({'status': 'ok', 'posteriors': posteriors})

    except Exception as e:
        logger.exception("Analysis failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def eccentricity_distribution(request):
    """Generate eccentricity distribution samples for a given formation channel."""
    try:
        data = json.loads(request.body)
        channel = data.get('channel', 'gc')
        sigma = float(data.get('sigma', 10.0))
        m1 = float(data.get('m1', 25.0))
        m2 = float(data.get('m2', 20.0))

        Mtot = m1 + m2
        mu = m1 * m2 / Mtot

        if channel == 'isolated':
            log_samples = np.random.normal(-11, 0.5, size=5000).tolist()
        else:
            eccs = capture_eccentricity_distribution(
                sigma, Mtot_solar=Mtot, mu_solar=mu, Niter=100, Nrp=500
            )
            eccs = eccs[eccs > 1e-15]
            log_samples = np.log10(eccs).tolist()

        return JsonResponse({
            'status': 'ok',
            'samples': log_samples,
            'sigma': sigma,
            'channel': channel,
        })

    except Exception as e:
        logger.exception("Eccentricity distribution failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Catalog of eccentric BBH
# ---------------------------------------------------------------------------

def catalog_eccentric_bbh(request):
    return render(request, 'blog/catalog_eccentric_bbh.html')


def catalog_posteriors(request):
    """Return the eccentric BBH posteriors for every observing run as JSON.

    The output shape is::

        {
          status: 'ok',
          runs: {
            'O1':  { '<event>': {
                '<col>': [...], ...,
                'll_max_qc': float | None,
                'll_max_ecc': float | None,
                'trajectories': {
                    'qc':  { 't': [...], ..., 'ml': {...} } | absent,
                    'ecc': { 't': [...], ..., 'ml': {...} } | absent,
                },
            } },
            'O2':  { ... }, 'O3': { ... }, 'O4a': { ... },
          }
        }

    Each event ships its full posterior cloud (column -> list of samples)
    plus up to two precomputed pyseobnr trajectories: one MAP from
    ``e < QC_BOUNDARY`` and one from ``e >= QC_BOUNDARY``. The two
    ``ll_max_*`` scalars are the maximum log-likelihood within each bin
    so the JS can compute the bin-wise log-posterior under any of the
    catalog page's prior options without recomputing it from the full
    log_likelihood column.
    """
    posteriors_path = os.path.join(
        settings.STATICFILES_DIRS[0], 'data', 'posteriors_ecc.h5'
    )
    trajectories_path = os.path.join(
        settings.STATICFILES_DIRS[0], 'data', 'trajectories_ecc.h5'
    )

    runs: dict[str, dict] = {run: {} for run in CATALOG_RUNS}
    # event_name -> event dict, for fast trajectory attach below.
    event_index: dict[str, dict] = {}

    with h5py.File(posteriors_path, 'r') as f:
        for run in CATALOG_RUNS:
            if run not in f:
                continue
            run_grp = f[run]
            for event_name in run_grp.keys():
                grp = run_grp[event_name]

                event: dict = {}
                for col in CATALOG_POSTERIOR_COLUMNS:
                    if col not in grp:
                        continue
                    # Cast to float64 before rounding so the JSON encoder
                    # writes the short repr (38.16, not 38.15999984741211).
                    arr = grp[col][...].astype(np.float64)
                    decimals = CATALOG_POSTERIOR_PRECISION.get(col)
                    if decimals is not None:
                        arr = np.round(arr, decimals)
                    event[col] = arr.tolist()

                # Per-bin max log-likelihood — needed by the JS to score
                # the qc vs ecc trajectories under each prior option.
                ecc_arr = grp['eccentricity'][...]
                ll_arr = grp['log_likelihood'][...]
                qc_mask = ecc_arr < QC_BOUNDARY
                event['ll_max_qc'] = (
                    float(ll_arr[qc_mask].max()) if qc_mask.any() else None
                )
                event['ll_max_ecc'] = (
                    float(ll_arr[~qc_mask].max()) if (~qc_mask).any() else None
                )

                # Per-event original prior P(qc). The eccentricity prior
                # was uniform on [0, e_max] where e_max varies by event
                # (0.5 for most O3 events, up to ~0.8 for some O4a).
                # Using max(ecc samples) as a proxy for e_max.
                e_max = float(ecc_arr.max())
                e_max = max(e_max, QC_BOUNDARY + 0.01)  # safety floor
                event['p_orig_qc'] = round(QC_BOUNDARY / e_max, 4)

                event['trajectories'] = {}

                runs[run][event_name] = event
                event_index[event_name] = event

    if os.path.exists(trajectories_path):
        with h5py.File(trajectories_path, 'r') as f:
            for event_name in f.keys():
                event = event_index.get(event_name)
                if event is None:
                    continue
                ev_grp = f[event_name]
                for bin_name in ('qc', 'ecc'):
                    if bin_name not in ev_grp:
                        continue
                    bin_grp = ev_grp[bin_name]
                    traj: dict = {}
                    for col, decimals in TRAJECTORY_DECIMAL_COLS.items():
                        if col in bin_grp:
                            arr = bin_grp[col][...].astype(np.float64)
                            traj[col] = np.round(arr, decimals).tolist()
                    for col in TRAJECTORY_SIGFIG_COLS:
                        if col in bin_grp:
                            arr = bin_grp[col][...].astype(np.float64)
                            traj[col] = round_sig(arr, 4)
                    traj['ml'] = {
                        k: (v.item() if hasattr(v, 'item') else v)
                        for k, v in bin_grp.attrs.items()
                    }
                    event['trajectories'][bin_name] = traj
    else:
        logger.warning(
            "trajectories_ecc.h5 not found at %s; "
            "run scripts/generate_o4a_trajectories.py to populate it.",
            trajectories_path,
        )

    # Merge in the full GWTC BBH event list so events without
    # eccentricity data still appear as placeholder cards.
    gwtc_path = os.path.join(
        settings.STATICFILES_DIRS[0], 'data', 'gwtc_bbh_events.json'
    )
    if os.path.exists(gwtc_path):
        with open(gwtc_path, 'r') as fp:
            gwtc_events = json.load(fp)
        for run in CATALOG_RUNS:
            for gwtc_name in gwtc_events.get(run, []):
                if gwtc_name in runs[run]:
                    continue
                hdf5_name = GWTC_TO_HDF5_ALIASES.get(gwtc_name)
                if hdf5_name and hdf5_name in runs[run]:
                    runs[run][gwtc_name] = runs[run].pop(hdf5_name)
                    continue
                runs[run][gwtc_name] = {'_noData': True}

    return JsonResponse({'status': 'ok', 'runs': runs})
