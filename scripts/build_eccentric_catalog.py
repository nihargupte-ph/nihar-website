"""Build the unified eccentric BBH catalog HDF5 from real LIGO posteriors.

Sources:
  1. ``eccentric_posterior_data_release.hdf5`` — 57 events from O1, O2, O3.
     Layout: ``<event>/samples/<column>`` direct datasets. These posteriors
     are already rejection-sampled upstream — no resampling is applied here,
     but events are capped at ``MAX_SAMPLES`` via uniform subsampling.
     Includes GW190701_203306, which we discard in favor of the deglitched
     version from source 3.
  2. ``posteriors_ecc.h5``                     — 81 events from O4a (GW23xxxx,
     GW24xxxx). Pandas-pytables layout: ``<event>/posterior`` block frame.
     These carry importance weights and are rejection-resampled here using
     dingo-style weight clipping.
  3. ``glitch_GW190701.h5``                    — Glitch-marginalized posterior
     for GW190701_203306. Replaces the data-release version of that event.

Output:
  ``static/data/posteriors_ecc.h5`` with the structure ::

      O1/<event>/<column>
      O2/<event>/<column>
      O3/<event>/<column>
      O4a/<event>/<column>

  O1–O3 events use the pre-rejection-sampled posteriors from the data
  release (capped at ``MAX_SAMPLES`` per event). O4a events are
  rejection-resampled with weight clipping (dingo-style). All output
  events have uniform weights; sample counts vary per event. Per-event
  source provenance and the original sample counts are preserved as
  group attributes.

Standardized columns (per event group)::

    mass_1, mass_2, chirp_mass, mass_ratio,
    chi_1, chi_2,
    eccentricity, relativistic_anomaly,
    theta_jn, luminosity_distance,
    ra, dec, psi, geocent_time, phase,
    log_likelihood, log_prior, weights

``mass_1``/``mass_2`` are derived from ``chirp_mass`` and ``mass_ratio``
(``q = m2/m1 <= 1``). ``relativistic_anomaly`` is renamed from
``mean_anomaly`` — both source files use the bilby convention where the
column called ``mean_anomaly`` is the SEOBNRv5EHM ``rel_anomaly`` parameter,
not the Keplerian mean anomaly. ``weights`` is uniform 1.0 for all events.

Run with::

    python scripts/build_eccentric_catalog.py
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "static" / "data" / "posteriors_ecc.h5"

SRC_RELEASE = Path("/home/n/Desktop/tmp/eccentric_posterior_data_release.hdf5")
SRC_O4A = Path("/home/n/Desktop/tmp/posteriors_ecc.h5")
SRC_GLITCH = Path("/home/n/Desktop/tmp/glitch_GW190701.h5")

# Maximum samples per event for pre-rejection-sampled data (O1-O3 release,
# glitch file). Events exceeding this are uniformly subsampled down.
MAX_SAMPLES = 5000

# Deterministic seed so re-running the build is reproducible.
RNG_SEED = 20240409

# Run buckets keyed by the YY in the GWyymmdd event name. O4a started in
# May 2023 and the data we have only spans through Nov 2023, so 23/24 are
# both O4a here. No O4b events in any source file yet.
RUN_BY_YEAR = {
    "15": "O1",
    "16": "O1",
    "17": "O2",
    "19": "O3",
    "20": "O3",
    "23": "O4a",
    "24": "O4a",
}

# Columns we write to every event group (in this order).
OUT_COLUMNS = (
    "mass_1",
    "mass_2",
    "chirp_mass",
    "mass_ratio",
    "chi_1",
    "chi_2",
    "eccentricity",
    "relativistic_anomaly",
    "theta_jn",
    "luminosity_distance",
    "ra",
    "dec",
    "psi",
    "geocent_time",
    "phase",
    "log_likelihood",
    "log_prior",
    "weights",
)

# Source columns we need to read. The release file uses these names directly;
# the pytables files store them under ``mean_anomaly`` (which we rename) and
# the rest match.
SRC_COLUMNS_NEEDED = (
    "chirp_mass",
    "mass_ratio",
    "chi_1",
    "chi_2",
    "eccentricity",
    "mean_anomaly",
    "theta_jn",
    "luminosity_distance",
    "ra",
    "dec",
    "psi",
    "geocent_time",
    "phase",
    "log_likelihood",
    "log_prior",
)


# ---------------------------------------------------------------------------
# Source-format readers
# ---------------------------------------------------------------------------

def _read_release_event(grp: h5py.Group) -> tuple[dict[str, np.ndarray], dict]:
    """Return (columns, attrs) for an event in the data-release file."""
    samples = grp["samples"]
    cols = {col: samples[col][...] for col in SRC_COLUMNS_NEEDED if col in samples}
    weights = samples["weights"][...] if "weights" in samples else None
    attrs = {k: v for k, v in grp.attrs.items()}
    return cols, weights, attrs


def _read_pytables_frame(grp: h5py.Group,
                         wanted: Iterable[str] | None = None) -> dict[str, np.ndarray]:
    """Decode a pandas-pytables ``DataFrame`` group into a column dict.

    Pandas writes one ``block{i}`` per dtype, with the column names in
    ``block{i}_items`` and the values in ``block{i}_values`` shaped
    ``(n_rows, n_cols_in_block)``. Some O4a events also include a string
    column block stored as a 1D object array — those are skipped because we
    never need them.

    If ``wanted`` is given, only those column names are decoded; this also
    lets us skip complex-typed nuisance columns (matched-filter SNRs) that
    h5py would otherwise materialize.
    """
    wanted_set = set(wanted) if wanted is not None else None
    out: dict[str, np.ndarray] = {}
    i = 0
    while f"block{i}_items" in grp:
        items_raw = grp[f"block{i}_items"][...]
        items = [s.decode() if isinstance(s, (bytes, np.bytes_)) else s
                 for s in items_raw]
        values_ds = grp[f"block{i}_values"]
        # Skip non-2D blocks (string/object columns pickled by pandas).
        if values_ds.ndim != 2:
            i += 1
            continue
        # Skip blocks whose columns we don't need so we don't materialize a
        # huge nuisance-parameter array (e.g. recalibration coefficients).
        if wanted_set is not None and not any(c in wanted_set for c in items):
            i += 1
            continue
        if wanted_set is None:
            values = values_ds[...]
            for j, col in enumerate(items):
                out[col] = values[:, j]
        else:
            for j, col in enumerate(items):
                if col in wanted_set:
                    out[col] = values_ds[:, j]
        i += 1
    return out


def _read_o4a_event(grp: h5py.Group) -> tuple[dict[str, np.ndarray], np.ndarray, dict]:
    frame = _read_pytables_frame(grp["posterior"],
                                 wanted=set(SRC_COLUMNS_NEEDED) | {"weights"})
    cols = {c: frame[c] for c in SRC_COLUMNS_NEEDED if c in frame}
    weights = frame.get("weights")
    attrs = {k: v for k, v in grp.attrs.items() if not k.startswith(("CLASS", "TITLE", "VERSION"))}
    return cols, weights, attrs


def _read_glitch_event(path: Path) -> tuple[dict[str, np.ndarray], np.ndarray | None, dict]:
    """Pull the glitch-marginalized posterior out of the deglitch file."""
    with h5py.File(path, "r") as f:
        frame = _read_pytables_frame(f["glitch_marginalized"],
                                     wanted=set(SRC_COLUMNS_NEEDED) | {"weights"})
    cols = {c: frame[c] for c in SRC_COLUMNS_NEEDED if c in frame}
    weights = frame.get("weights")  # absent — already SIR'd upstream
    attrs = {"source": "glitch_marginalized"}
    return cols, weights, attrs


# ---------------------------------------------------------------------------
# Resampling and derived quantities
# ---------------------------------------------------------------------------

def _clip_weights(weights: np.ndarray, num_clip: int) -> np.ndarray:
    """Clip the ``num_clip`` largest weights to their mean, then renormalize.

    Reduces variance of importance weights at the cost of a small bias.
    Uses the mean of the clipped group (not the minimum) to preserve their
    total weight, minimising bias (Elvira et al. 2018).
    """
    weights = weights.copy()
    clip_idx = np.argpartition(-weights, num_clip)[:num_clip]
    weights[clip_idx] = weights[clip_idx].mean()
    weights /= weights.mean()
    return weights


def _rejection_resample(weights: np.ndarray, rng: np.random.Generator,
                        max_samples_per_draw: int = 2,
                        clip: bool = True) -> np.ndarray:
    """Dingo-style rejection sampling with optional weight clipping.

    Returns an index array into the original samples. The output length
    varies per event. Each sample contributes at most
    ``max_samples_per_draw`` copies.

    Algorithm:
      1. Optionally clip the top ceil(sqrt(N)) weights to their mean.
      2. Scale weights so max(w_scaled) = ``max_samples_per_draw``.
      3. For each sample *i*:
           - deterministic copies = floor(w_scaled[i])
           - one stochastic extra copy with probability = fractional part
      4. Return the repeated index array.
    """
    w = np.asarray(weights, dtype=np.float64)
    w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
    total = w.sum()
    if total <= 0:
        return np.arange(len(w))

    if clip:
        num_clip = math.ceil(math.sqrt(len(w)))
        w = _clip_weights(w, num_clip)

    w_scaled = w * (max_samples_per_draw / w.max())
    n_det = np.floor(w_scaled).astype(int)
    p_frac = w_scaled - n_det
    extra = (rng.random(len(w)) < p_frac).astype(int)
    n_copies = n_det + extra
    return np.repeat(np.arange(len(w)), n_copies)


def _component_masses(chirp_mass: np.ndarray, mass_ratio: np.ndarray
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Convert (Mc, q) → (m1, m2) using the q = m2/m1 ≤ 1 convention.

    Mc = m1 * q^(3/5) / (1 + q)^(1/5)
    => m1 = Mc * (1 + q)^(1/5) / q^(3/5)
       m2 = q * m1
    """
    q = np.clip(mass_ratio, 1e-6, 1.0)
    m1 = chirp_mass * (1.0 + q) ** (1.0 / 5.0) / q ** (3.0 / 5.0)
    m2 = q * m1
    return m1, m2


def _build_event_columns(src_cols: dict[str, np.ndarray],
                         idx: np.ndarray) -> dict[str, np.ndarray]:
    """Slice source columns by ``idx`` and produce the output column dict.

    ``idx`` may be an identity range (pre-rejection-sampled data) or the
    output of ``_rejection_resample`` (variable length).
    """
    chirp_mass = src_cols["chirp_mass"][idx].astype(np.float32)
    mass_ratio = src_cols["mass_ratio"][idx].astype(np.float32)
    m1, m2 = _component_masses(chirp_mass.astype(np.float64),
                               mass_ratio.astype(np.float64))

    out: dict[str, np.ndarray] = {
        "mass_1": m1.astype(np.float32),
        "mass_2": m2.astype(np.float32),
        "chirp_mass": chirp_mass,
        "mass_ratio": mass_ratio,
        "chi_1": src_cols["chi_1"][idx].astype(np.float32),
        "chi_2": src_cols["chi_2"][idx].astype(np.float32),
        "eccentricity": src_cols["eccentricity"][idx].astype(np.float32),
        "relativistic_anomaly": src_cols["mean_anomaly"][idx].astype(np.float32),
        "theta_jn": src_cols["theta_jn"][idx].astype(np.float32),
        "luminosity_distance": src_cols["luminosity_distance"][idx].astype(np.float32),
        "ra": src_cols["ra"][idx].astype(np.float32),
        "dec": src_cols["dec"][idx].astype(np.float32),
        "psi": src_cols["psi"][idx].astype(np.float32),
        "geocent_time": src_cols["geocent_time"][idx].astype(np.float64),
        "phase": src_cols["phase"][idx].astype(np.float64),
        "log_likelihood": src_cols["log_likelihood"][idx].astype(np.float64),
        "log_prior": src_cols["log_prior"][idx].astype(np.float64),
        # Uniform weights post-resampling — kept so downstream consumers
        # that expect a ``weights`` column don't need a special case.
        "weights": np.ones(idx.shape[0], dtype=np.float64),
    }
    return out


# ---------------------------------------------------------------------------
# Event collection
# ---------------------------------------------------------------------------

def _run_for_event(name: str) -> str | None:
    """Map ``GWyymmdd[_HHMMSS]`` to its observing run, or None if unknown."""
    if not name.startswith("GW") or len(name) < 4:
        return None
    yy = name[2:4]
    return RUN_BY_YEAR.get(yy)


def _gather_release(rng: np.random.Generator) -> Iterable[tuple[str, str, dict, dict]]:
    """Yield ``(run, event, columns, attrs)`` from the data-release file.

    The O1–O3 data release has already been rejection-sampled upstream,
    so no importance resampling is applied — all samples are used
    directly, capped at ``MAX_SAMPLES`` via uniform subsampling.
    """
    with h5py.File(SRC_RELEASE, "r") as f:
        for name in sorted(f.keys()):
            if name == "GW190701_203306":
                # Replaced by glitch-marginalized version below.
                continue
            run = _run_for_event(name)
            if run is None:
                print(f"  SKIP release {name}: no run mapping")
                continue
            cols, weights, attrs = _read_release_event(f[name])
            n_in = next(iter(cols.values())).shape[0]
            if n_in > MAX_SAMPLES:
                idx = rng.choice(n_in, size=MAX_SAMPLES, replace=False)
            else:
                idx = np.arange(n_in)
            out_cols = _build_event_columns(cols, idx)
            attrs_clean = _clean_attrs(attrs)
            attrs_clean["source"] = "eccentric_posterior_data_release"
            attrs_clean["n_samples_original"] = n_in
            yield run, name, out_cols, attrs_clean


def _gather_glitch(rng: np.random.Generator) -> Iterable[tuple[str, str, dict, dict]]:
    """Yield the deglitched GW190701 event."""
    cols, weights, attrs = _read_glitch_event(SRC_GLITCH)
    name = "GW190701_203306"
    run = _run_for_event(name)
    n_in = next(iter(cols.values())).shape[0]
    if weights is not None:
        idx = _rejection_resample(weights, rng)
    elif n_in > MAX_SAMPLES:
        idx = rng.choice(n_in, size=MAX_SAMPLES, replace=False)
    else:
        idx = np.arange(n_in)
    out_cols = _build_event_columns(cols, idx)
    attrs_clean = _clean_attrs(attrs)
    attrs_clean["source"] = "glitch_GW190701/glitch_marginalized"
    attrs_clean["n_samples_original"] = n_in
    yield run, name, out_cols, attrs_clean


def _gather_o4a(rng: np.random.Generator) -> Iterable[tuple[str, str, dict, dict]]:
    """Yield ``(run, event, columns, attrs)`` from the O4a posteriors file.

    O4a posteriors carry importance weights with high max/mean ratios.
    Weight clipping + dingo-style rejection sampling reduces the variance
    and produces an unweighted sample set of variable length.
    """
    with h5py.File(SRC_O4A, "r") as f:
        for name in sorted(f.keys()):
            run = _run_for_event(name)
            if run is None:
                print(f"  SKIP o4a {name}: no run mapping")
                continue
            cols, weights, attrs = _read_o4a_event(f[name])
            n_in = next(iter(cols.values())).shape[0]
            if weights is not None:
                idx = _rejection_resample(weights, rng)
            else:
                idx = np.arange(n_in)
            out_cols = _build_event_columns(cols, idx)
            attrs_clean = _clean_attrs(attrs)
            attrs_clean["source"] = "posteriors_ecc_o4a"
            attrs_clean["n_samples_original"] = n_in
            attrs_clean["n_samples_out"] = len(idx)
            yield run, name, out_cols, attrs_clean


def _clean_attrs(attrs: dict) -> dict:
    """Coerce HDF5 attribute values to plain Python scalars/strings."""
    out = {}
    for k, v in attrs.items():
        if isinstance(v, (bytes, np.bytes_)):
            out[k] = v.decode()
        elif isinstance(v, np.generic):
            out[k] = v.item()
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    for src in (SRC_RELEASE, SRC_O4A, SRC_GLITCH):
        if not src.exists():
            raise SystemExit(f"missing source file: {src}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    rng = np.random.default_rng(RNG_SEED)

    counts: dict[str, int] = {"O1": 0, "O2": 0, "O3": 0, "O4a": 0}

    with h5py.File(OUTPUT, "w") as f_out:
        f_out.attrs["description"] = (
            "Unified eccentric BBH posterior catalog. O1-O3 events use "
            "pre-rejection-sampled posteriors from the data release; O4a "
            "events are rejection-resampled (dingo-style, with weight "
            "clipping) from importance-weighted posteriors. All events "
            "have uniform weights; sample counts vary per event."
        )
        f_out.attrs["synthetic"] = False
        f_out.attrs["generated_at"] = datetime.now(timezone.utc).isoformat()
        f_out.attrs["sources"] = np.array(
            [str(SRC_RELEASE.name), str(SRC_O4A.name), str(SRC_GLITCH.name)],
            dtype="S",
        )
        f_out.attrs["columns"] = np.array(OUT_COLUMNS, dtype="S")

        # Pre-create the run groups so the layout is stable even if a run
        # ends up with zero events.
        for run in ("O1", "O2", "O3", "O4a"):
            f_out.create_group(run)

        # Stream events from each source. Order matters only for GW190701:
        # we yield the data-release events first (skipping GW190701), then
        # the deglitched GW190701, then O4a.
        for run, name, cols, attrs in _gather_release(rng):
            _write_event(f_out, run, name, cols, attrs)
            counts[run] += 1

        for run, name, cols, attrs in _gather_glitch(rng):
            _write_event(f_out, run, name, cols, attrs)
            counts[run] += 1

        for run, name, cols, attrs in _gather_o4a(rng):
            _write_event(f_out, run, name, cols, attrs)
            counts[run] += 1

    total = sum(counts.values())
    print(f"Wrote {total} events to {OUTPUT}")
    for run in ("O1", "O2", "O3", "O4a"):
        print(f"  {run}: {counts[run]} events")


def _write_event(f_out: h5py.File, run: str, name: str,
                 cols: dict, attrs: dict) -> None:
    grp = f_out[run].create_group(name)
    for col in OUT_COLUMNS:
        grp.create_dataset(col, data=cols[col], compression="gzip")
    for k, v in attrs.items():
        grp.attrs[k] = v


if __name__ == "__main__":
    main()
