"""Shared eccentric BBH waveform generation utilities.

Wraps ``pyseobnr.GenerateWaveform`` (``SEOBNRv5EHM``) so both the
``analyzing-eccentric-binary-black-holes`` and
``catalog-of-eccentric-binary-black-holes`` blogposts can produce
EOB-quality dynamics and polarizations from the same code path.
"""
from __future__ import annotations

import numpy as np
from pyseobnr.generate_waveform import GenerateWaveform

# G / c^3 in seconds per solar mass — converts EOB geometric time to physical s.
G_OVER_C3 = 4.925491025543576e-6


def generate_eccentric_bbh_waveform(
    m1,
    m2,
    spin1z,
    spin2z,
    eccentricity,
    rel_anomaly_rad,
    distance=2000.0,
    inclination=0.4,
    deltaT=1.0 / 2048.0,
    f22_start=20.0,
    f_max=1024.0,
    lmax_nyquist=None,
    f22_display=None,
):
    """Run SEOBNRv5EHM and return aligned trajectory + polarizations.

    Returns a dict with three keys:

    * ``trajectory``: ``{'t', 'x1', 'y1', 'x2', 'y2', 'r', 'phi'}`` — the
      two-body positions in COM frame, in EOB units (separation in M),
      with time aligned to the polarization peak.
    * ``polarizations``: ``{'t', 'hp', 'hc'}``.
    * ``meta``: scalar parameters useful to downstream consumers
      (``M_total``, mass fractions, ``epoch``, ``dt``, etc.).

    If ``f22_display`` is set, the returned arrays are trimmed to start
    from where the (2,2) GW frequency permanently exceeds that value.
    This lets integration begin at a low ``f22_start`` (giving pyseobnr
    more room) while only shipping the detector-sensitive band.

    The ``m2 > m1`` case is handled by swapping inputs so the convention
    ``m1 >= m2`` is preserved before the call to pyseobnr.
    """
    if m2 > m1:
        m1, m2 = m2, m1
        spin1z, spin2z = spin2z, spin1z

    params = {
        'mass1': m1,
        'mass2': m2,
        'spin1z': spin1z,
        'spin2z': spin2z,
        'eccentricity': eccentricity,
        'rel_anomaly': rel_anomaly_rad,
        'distance': distance,
        'inclination': inclination,
        'deltaT': deltaT,
        'f22_start': f22_start,
        'f_max': f_max,
        'approximant': 'SEOBNRv5EHM',
    }
    if lmax_nyquist is not None:
        params['lmax_nyquist'] = lmax_nyquist

    wf = GenerateWaveform(params)
    hp_lal, hc_lal = wf.generate_td_polarizations()

    hp = hp_lal.data.data
    hc = hc_lal.data.data
    epoch = float(hp_lal.epoch)
    dt = hp_lal.deltaT
    t_wf = epoch + np.arange(len(hp)) * dt

    dyn = wf.model.dynamics
    M_total = wf.model.M
    m1_frac = wf.model.m_1
    m2_frac = wf.model.m_2

    # Convert EOB geometric time to physical seconds and align the end of the
    # dynamics array (merger) to the polarization peak.
    t_dyn = dyn[:, 0] * M_total * G_OVER_C3
    peak_idx = int(np.argmax(np.abs(hp)))
    t_peak = epoch + peak_idx * dt
    t_dyn = t_dyn - t_dyn[-1] + t_peak

    r = dyn[:, 1]
    phi = dyn[:, 2]

    # Two-body positions in COM frame: heavier body sits closer to origin.
    x1 = m2_frac * r * np.cos(phi)
    y1 = m2_frac * r * np.sin(phi)
    x2 = -m1_frac * r * np.cos(phi)
    y2 = -m1_frac * r * np.sin(phi)

    # Display-frequency trim: keep only the part of the inspiral where
    # the (2,2) GW frequency permanently exceeds f22_display. For
    # eccentric orbits the instantaneous f_GW oscillates, so we use the
    # running minimum from the end — once it exceeds the threshold,
    # f_GW never dips below it again.
    if f22_display is not None and f22_display > 0:
        dphi_dt = np.gradient(phi, t_dyn)
        f_gw22 = np.abs(dphi_dt) / np.pi  # f_GW = 2*f_orb = dφ/dt / π
        f_gw_min_future = np.minimum.accumulate(f_gw22[::-1])[::-1]
        idx_trim = int(np.searchsorted(f_gw_min_future, f22_display))
        if 0 < idx_trim < len(t_dyn) - 2:
            t_dyn = t_dyn[idx_trim:]
            r = r[idx_trim:]
            phi = phi[idx_trim:]
            x1 = x1[idx_trim:]
            y1 = y1[idx_trim:]
            x2 = x2[idx_trim:]
            y2 = y2[idx_trim:]
            pol_idx = int(np.searchsorted(t_wf, t_dyn[0]))
            t_wf = t_wf[pol_idx:]
            hp = hp[pol_idx:]
            hc = hc[pol_idx:]

    return {
        'trajectory': {
            't': t_dyn,
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
            'r': r,
            'phi': phi,
        },
        'polarizations': {
            't': t_wf,
            'hp': hp,
            'hc': hc,
        },
        'meta': {
            'm1': m1,
            'm2': m2,
            's1': spin1z,
            's2': spin2z,
            'eccentricity': eccentricity,
            'rel_anomaly_rad': rel_anomaly_rad,
            'M_total': M_total,
            'm1_frac': m1_frac,
            'm2_frac': m2_frac,
            'epoch': epoch,
            'dt': dt,
        },
    }


def downsample(arr, max_points=3000):
    """Stride-downsample ``arr`` to at most ``max_points`` samples."""
    if len(arr) <= max_points:
        return arr
    stride = max(1, len(arr) // max_points)
    return arr[::stride]
