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
from pyseobnr.generate_waveform import GenerateWaveform

logger = logging.getLogger(__name__)

G_OVER_C3 = 4.925491025543576e-6  # seconds per solar mass


def analyzing_eccentric_bbh(request):
    return render(request, 'blog/analyzing_eccentric_bbh.html')


def _load_asd():
    """Load fiducial ASD for H1 and L1 from static data."""
    path = os.path.join(settings.STATICFILES_DIRS[0], 'data', 'asd_fiducial.hdf5')
    with h5py.File(path, 'r') as f:
        h1_asd = f['asds/H1'][0]
        l1_asd = f['asds/L1'][0]
    return h1_asd, l1_asd


def _downsample(arr, max_points=3000):
    """Downsample array to max_points by uniform striding."""
    if len(arr) <= max_points:
        return arr
    stride = max(1, len(arr) // max_points)
    return arr[::stride]


def _whiten_signal_and_generate_noise(hp_td, dt, asd, delta_f_asd=0.0625):
    """
    Whiten a TD signal using the ASD and generate a noise realization.

    Returns time array, whitened noise+signal, and whitened signal alone.
    """
    n = len(hp_td)

    # FFT the signal
    hp_fd = np.fft.rfft(hp_td) * dt
    freqs_signal = np.fft.rfftfreq(n, d=dt)

    # ASD frequency grid
    freqs_asd = np.arange(len(asd)) * delta_f_asd

    # Interpolate ASD to signal frequency grid
    asd_interp = np.interp(freqs_signal, freqs_asd, asd)
    # Avoid division by zero at DC
    asd_interp[asd_interp < 1e-30] = 1e-30

    # Whiten signal in FD
    delta_f_signal = freqs_signal[1] - freqs_signal[0] if len(freqs_signal) > 1 else 1.0
    signal_whitened_fd = np.sqrt(4 * delta_f_signal) * hp_fd / asd_interp

    # Generate Gaussian noise (unit variance whitened noise)
    noise_fd = (np.random.randn(len(freqs_signal)) + 1j * np.random.randn(len(freqs_signal)))

    # Combined whitened strain
    combined_fd = signal_whitened_fd + noise_fd

    # IFFT back
    signal_td = np.fft.irfft(signal_whitened_fd, n=n)
    combined_td = np.fft.irfft(combined_fd, n=n)

    t = np.arange(n) * dt
    return t, np.real(combined_td), np.real(signal_td)


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

        # Ensure m1 >= m2
        if m2 > m1:
            m1, m2 = m2, m1
            s1, s2 = s2, s1

        # Generate waveform with pyseobnr
        params = {
            'mass1': m1,
            'mass2': m2,
            'spin1z': s1,
            'spin2z': s2,
            'eccentricity': eccentricity,
            'rel_anomaly': mean_anomaly_deg * pi / 180.0,
            'distance': 2000.0,
            'inclination': 0.4,
            'deltaT': 1.0 / 2048.0,
            'f22_start': 20.0,
            'f_max': 1024.0,
            'approximant': 'SEOBNRv5EHM',
        }

        wf = GenerateWaveform(params)
        hp_lal, hc_lal = wf.generate_td_polarizations()

        # Extract polarizations
        hp_data = hp_lal.data.data
        hc_data = hc_lal.data.data
        epoch = float(hp_lal.epoch)
        dt = hp_lal.deltaT
        t_wf = epoch + np.arange(len(hp_data)) * dt

        # Extract dynamics and convert to two-body
        dyn = wf.model.dynamics
        m1_frac = wf.model.m_1  # fractional mass m1/M
        m2_frac = wf.model.m_2  # fractional mass m2/M
        M_total = wf.model.M    # total mass in solar masses

        # Convert dynamics time from geometric units (M) to physical seconds
        t_dyn = dyn[:, 0] * M_total * G_OVER_C3
        # Align dynamics end to waveform peak (merger)
        # Dynamics stop at merger; waveform continues into ringdown
        peak_idx = int(np.argmax(np.abs(hp_data)))
        t_peak = epoch + peak_idx * dt
        t_dyn = t_dyn - t_dyn[-1] + t_peak

        r = dyn[:, 1]    # separation in units of M
        phi = dyn[:, 2]   # orbital phase

        # Two-body positions relative to center of mass
        # Body 1 orbits at r1 = (m2/M)*r from COM
        # Body 2 orbits at r2 = (m1/M)*r from COM, opposite side
        x1 = m2_frac * r * np.cos(phi)
        y1 = m2_frac * r * np.sin(phi)
        x2 = -m1_frac * r * np.cos(phi)
        y2 = -m1_frac * r * np.sin(phi)

        # Generate whitened strain for H1 and L1
        h1_asd, l1_asd = _load_asd()

        t_strain_h1, h1_combined, h1_signal = _whiten_signal_and_generate_noise(
            hp_data, dt, h1_asd
        )
        t_strain_l1, l1_combined, l1_signal = _whiten_signal_and_generate_noise(
            hp_data, dt, l1_asd
        )
        # Shift strain time to match waveform epoch
        t_strain_h1 = t_strain_h1 + epoch
        t_strain_l1 = t_strain_l1 + epoch

        # Downsample for JSON transport
        response = {
            'status': 'ok',
            'trajectory': {
                't': _downsample(t_dyn).tolist(),
                'x1': _downsample(x1).tolist(),
                'y1': _downsample(y1).tolist(),
                'x2': _downsample(x2).tolist(),
                'y2': _downsample(y2).tolist(),
            },
            'polarizations': {
                't': _downsample(t_wf).tolist(),
                'hp': _downsample(hp_data).tolist(),
                'hc': _downsample(hc_data).tolist(),
            },
            'strain': {
                'H1': {
                    't': _downsample(t_strain_h1).tolist(),
                    'noise_plus_signal': _downsample(h1_combined).tolist(),
                    'signal': _downsample(h1_signal).tolist(),
                },
                'L1': {
                    't': _downsample(t_strain_l1).tolist(),
                    'noise_plus_signal': _downsample(l1_combined).tolist(),
                    'signal': _downsample(l1_signal).tolist(),
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


def _peters_a(c0, e):
    """Peters (1964) semi-major axis from eccentricity."""
    return c0 * e ** (12.0 / 19.0) * (1 + 121.0 / 304.0 * e ** 2) ** (870.0 / 2299.0) / (1 - e ** 2)


def _solve_e_from_a(c0, a_target):
    """Numerically invert Peters' relation using bisection (robust for high e)."""
    lo, hi = 1e-8, 1 - 1e-12
    for _ in range(200):
        mid = (lo + hi) / 2
        a_mid = _peters_a(c0, mid)
        if a_mid < a_target:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < 1e-12:
            break
    return (lo + hi) / 2


def _capture_eccentricity_distribution(sigma_1d_kms, Mtot_solar=45.0, mu_solar=11.25,
                                       Niter=200, Nrp=500, f_orb_ref=10.0):
    """
    Monte Carlo forward model p(e | sigma) for single-single GW captures.
    Ported from ecc_dist_cole_checkpoint.ipynb.

    sigma_1d_kms: 1D velocity dispersion in km/s
    Mtot_solar: total mass in solar masses
    mu_solar: reduced mass in solar masses
    Returns array of eccentricities at f_orb_ref Hz.
    """
    import math

    GMsun = 1.3271244e26   # cm^3/s^2
    cspeed = 2.998e10      # cm/s

    sigma_1d = sigma_1d_kms * 1e5  # km/s -> cm/s
    sigma_3d = math.sqrt(3.0) * sigma_1d
    sigma_rel = math.sqrt(2.0) * sigma_3d

    atarg = (GMsun * Mtot_solar / (4.0 * math.pi ** 2 * f_orb_ref)) ** (1.0 / 3.0)

    rng = np.random.default_rng()
    e_samples_list = []
    n_accepted = 0

    while n_accepted < Niter:
        batch_size = max(2 * (Niter - n_accepted), 100)
        x_batch = np.abs(rng.standard_normal(batch_size))
        y_batch = rng.random(batch_size)
        accept_mask = y_batch < np.power(x_batch, 3.0 / 7.0)
        x_accepted = x_batch[accept_mask]
        if len(x_accepted) == 0:
            continue

        n_needed = Niter - n_accepted
        x_use = x_accepted[:n_needed]
        n_accepted += len(x_use)

        vinf = x_use * sigma_rel

        coeff = (85.0 * math.pi / (6.0 * math.sqrt(2.0))) ** (2.0 / 7.0)
        coeff *= GMsun * (mu_solar * Mtot_solar ** 2.5) ** (2.0 / 7.0)
        coeff /= cspeed ** (10.0 / 7.0)
        rpmax = coeff / np.power(vinf, 4.0 / 7.0)

        j_idx = np.arange(Nrp) + 0.5
        drp = rpmax / Nrp
        rp = np.outer(drp, j_idx)
        C = 1.76 * rp

        # Vectorized bisection for eccentricity
        emin_arr = np.zeros_like(rp)
        emax_arr = np.ones_like(rp)

        for _ in range(60):
            emid = 0.5 * (emin_arr + emax_arr)
            emid_safe = np.maximum(emid, 1e-15)
            a_val = C / (
                np.power(emid_safe, -12.0 / 19.0)
                * (1.0 - emid * emid)
                * np.power(1.0 + 121.0 * emid * emid / 304.0, -870.0 / 2299.0)
            )
            too_high = a_val > atarg
            emax_arr = np.where(too_high, emid, emax_arr)
            emin_arr = np.where(~too_high, emid, emin_arr)

        e_final = 0.5 * (emin_arr + emax_arr)
        valid_mask = (e_final > 0) & (e_final < 1)
        e_samples_list.append(e_final[valid_mask].ravel())

    if e_samples_list:
        e_arr = np.concatenate(e_samples_list)
    else:
        e_arr = np.array([])

    # Filter to reasonable range
    e_arr = e_arr[(e_arr > 1e-12) & (e_arr < 10 ** (-0.1))]
    return e_arr


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
            eccs = _capture_eccentricity_distribution(
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
