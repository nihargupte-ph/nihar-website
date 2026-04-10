import numpy as np


CATALOG_RUNS = ('O1', 'O2', 'O3', 'O4a')

# GWTC uses "GW190521_030229" while the HDF5 file uses "GW190521".
GWTC_TO_HDF5_ALIASES = {
    'GW190521_030229': 'GW190521',
}

# Eccentricity boundary between the "quasicircular" and "eccentric" bins
# of the population prior the catalog page lets the user reweight
# against. Must match the constant in
# ``scripts/generate_o4a_trajectories.py`` and the JS file.
QC_BOUNDARY = 0.05

# Posterior columns the catalog JS actually consumes — everything else
# is dropped from the JSON response to keep the payload small. The JS
# treats per-sample ``weights`` as uniform when absent.
CATALOG_POSTERIOR_COLUMNS = (
    'mass_1',
    'mass_2',
    'chi_1',
    'chi_2',
    'eccentricity',
    'relativistic_anomaly',
)

# Per-column rounding precision (decimal places) for the JSON payload.
# Float repr in Python is ~17 chars; rounding cuts that down by ~4x
# without affecting the heatmap binning.
CATALOG_POSTERIOR_PRECISION = {
    'mass_1':               2,
    'mass_2':               2,
    'chi_1':                3,
    'chi_2':                3,
    'eccentricity':         4,
    'relativistic_anomaly': 3,
}

# Trajectory dataset columns shipped to the JS. Coordinates and time
# are rounded to a few decimals; strain rows are rounded to a fixed
# number of significant figures since they span ~20 orders of magnitude
# but the JS normalizes by their peak before display.
TRAJECTORY_DECIMAL_COLS = {
    't':          5,
    't_ringdown': 5,
    'x1':         3,
    'y1':         3,
    'x2':         3,
    'y2':         3,
}
TRAJECTORY_SIGFIG_COLS = ('hp', 'hc', 'hp_ringdown', 'hc_ringdown')


def round_sig(arr: np.ndarray, sig: int) -> list:
    """Round each value in ``arr`` to ``sig`` significant figures.

    Decimal-place rounding flattens strain values (~1e-22) to zero, so
    we route them through ``f'{x:.{sig}g}'`` and parse back. The format
    string is what guarantees a clean float64 round-trip — a multiply /
    divide approach picks up float error from the 10**N factor.
    Returns a Python list directly so callers can ship it as JSON.
    """
    arr = np.asarray(arr, dtype=np.float64)
    fmt = f'.{sig}g'
    return [float(format(x, fmt)) if x != 0.0 else 0.0 for x in arr]
