import os

import h5py
import numpy as np
from django.conf import settings


def load_asd():
    """Load fiducial ASD for H1 and L1 from static data."""
    path = os.path.join(settings.STATICFILES_DIRS[0], 'data', 'asd_fiducial.hdf5')
    with h5py.File(path, 'r') as f:
        h1_asd = f['asds/H1'][0]
        l1_asd = f['asds/L1'][0]
    return h1_asd, l1_asd


def downsample(arr, max_points=3000):
    """Downsample array to max_points by uniform striding."""
    if len(arr) <= max_points:
        return arr
    stride = max(1, len(arr) // max_points)
    return arr[::stride]


def whiten_signal_and_generate_noise(hp_td, dt, asd, delta_f_asd=0.0625):
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


def peters_a(c0, e):
    """Peters (1964) semi-major axis from eccentricity."""
    return c0 * e ** (12.0 / 19.0) * (1 + 121.0 / 304.0 * e ** 2) ** (870.0 / 2299.0) / (1 - e ** 2)


def solve_e_from_a(c0, a_target):
    """Numerically invert Peters' relation using bisection (robust for high e)."""
    lo, hi = 1e-8, 1 - 1e-12
    for _ in range(200):
        mid = (lo + hi) / 2
        a_mid = peters_a(c0, mid)
        if a_mid < a_target:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < 1e-12:
            break
    return (lo + hi) / 2


def capture_eccentricity_distribution(sigma_1d_kms, Mtot_solar=45.0, mu_solar=11.25,
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
