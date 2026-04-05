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

        # Estimate SNR-like scaling: lower distance = higher SNR = tighter posteriors
        # At d=2000 Mpc with these masses, SNR is low (~5-15)
        # Use a rough SNR proxy based on total mass and distance
        total_mass = m1 + m2
        snr_proxy = total_mass / 40.0 * 10.0  # rough SNR ~5-15

        # Width of Gaussian posteriors: sigma ~ param_scale / SNR
        # Add random offset so the peak isn't always exactly at injection
        rng = np.random.default_rng()

        params_info = [
            {'name': 'm1', 'injected': m1, 'scale': 5.0, 'min': 5, 'max': 100, 'label': 'Mass 1 (M\u2609)'},
            {'name': 'm2', 'injected': m2, 'scale': 5.0, 'min': 5, 'max': 100, 'label': 'Mass 2 (M\u2609)'},
            {'name': 's1z', 'injected': s1, 'scale': 0.15, 'min': 0, 'max': 1.0, 'label': 'Spin 1'},
            {'name': 's2z', 'injected': s2, 'scale': 0.15, 'min': 0, 'max': 1.0, 'label': 'Spin 2'},
            {'name': 'ecc', 'injected': ecc, 'scale': 0.1, 'min': 0, 'max': 1.0, 'label': 'Eccentricity'},
            {'name': 'anomaly', 'injected': anomaly, 'scale': 40.0, 'min': 0, 'max': 360, 'label': 'Mean Anomaly (\u00b0)'},
        ]

        posteriors = {}
        for p in params_info:
            sigma = p['scale'] / max(snr_proxy, 1.0)
            # Random offset: shift the peak by up to 0.5 sigma
            offset = rng.normal(0, 0.5 * sigma)
            center = p['injected'] + offset

            samples = rng.normal(center, sigma, size=n_samples)
            # Clip to physical bounds
            samples = np.clip(samples, p['min'], p['max'])

            posteriors[p['name']] = {
                'samples': samples.tolist(),
                'injected': p['injected'],
                'label': p['label'],
            }

        return JsonResponse({'status': 'ok', 'posteriors': posteriors})

    except Exception as e:
        logger.exception("Analysis failed")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
