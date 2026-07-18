"""User-owned stimulus intensity series (µA) — CSV load/save/align (no Qt)."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

SWEEP_COL = "sweep"
INTENSITY_COL = "stim_intensity_uA"
CSV_COLUMNS = (SWEEP_COL, INTENSITY_COL)


def load_stim_intensity_csv(path: str | Path) -> pd.DataFrame:
    """Load stim intensity CSV. Missing file → empty frame with correct columns.

    Sanitizes: requires/renames known columns, coerces numeric, drops non-finite
    sweeps, keeps first value per sweep if duplicates.
    """
    path = Path(path)
    empty = pd.DataFrame(columns=list(CSV_COLUMNS))
    if not path.is_file():
        return empty

    try:
        df = pd.read_csv(path)
    except Exception:
        return empty

    if df is None or df.empty:
        return empty.copy()

    # Accept alternate headers lightly (intensity / uA)
    colmap: dict[str, str] = {}
    for c in df.columns:
        key = str(c).strip().lower()
        if key == SWEEP_COL:
            colmap[c] = SWEEP_COL
        elif key in (INTENSITY_COL, "stim_intensity", "intensity_ua", "ua", "intensity"):
            colmap[c] = INTENSITY_COL
    df = df.rename(columns=colmap)
    if SWEEP_COL not in df.columns or INTENSITY_COL not in df.columns:
        return empty.copy()

    out = df[[SWEEP_COL, INTENSITY_COL]].copy()
    out[SWEEP_COL] = pd.to_numeric(out[SWEEP_COL], errors="coerce")
    out[INTENSITY_COL] = pd.to_numeric(out[INTENSITY_COL], errors="coerce")
    out = out.dropna(subset=[SWEEP_COL])
    out[SWEEP_COL] = out[SWEEP_COL].astype(int)
    # Keep last duplicate sweep (user re-saved row wins)
    out = out.drop_duplicates(subset=[SWEEP_COL], keep="last")
    out = out.sort_values(SWEEP_COL).reset_index(drop=True)
    return out


def save_stim_intensity_csv(path: str | Path, df: pd.DataFrame) -> None:
    """Write canonical two-column CSV; creates parent directory if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if df is None or df.empty:
        pd.DataFrame(columns=list(CSV_COLUMNS)).to_csv(path, index=False)
        return
    out = df.copy()
    if SWEEP_COL not in out.columns or INTENSITY_COL not in out.columns:
        raise ValueError(f"DataFrame must have columns {CSV_COLUMNS}, got {list(out.columns)}")
    out = out[[SWEEP_COL, INTENSITY_COL]].copy()
    out[SWEEP_COL] = pd.to_numeric(out[SWEEP_COL], errors="coerce")
    out[INTENSITY_COL] = pd.to_numeric(out[INTENSITY_COL], errors="coerce")
    out = out.dropna(subset=[SWEEP_COL])
    out[SWEEP_COL] = out[SWEEP_COL].astype(int)
    out = out.drop_duplicates(subset=[SWEEP_COL], keep="last")
    out = out.sort_values(SWEEP_COL).reset_index(drop=True)
    out.to_csv(path, index=False)


def series_from_frame(df: pd.DataFrame) -> dict[int, float]:
    """Map sweep → intensity (NaN intensities omitted from dict)."""
    if df is None or df.empty:
        return {}
    if SWEEP_COL not in df.columns or INTENSITY_COL not in df.columns:
        return {}
    out: dict[int, float] = {}
    for _, row in df.iterrows():
        try:
            sw = int(row[SWEEP_COL])
        except (TypeError, ValueError):
            continue
        val = row[INTENSITY_COL]
        if pd.isna(val):
            continue
        out[sw] = float(val)
    return out


def frame_from_series(series: Mapping[int, float]) -> pd.DataFrame:
    if not series:
        return pd.DataFrame(columns=list(CSV_COLUMNS))
    sweeps = sorted(int(s) for s in series.keys())
    return pd.DataFrame(
        {
            SWEEP_COL: sweeps,
            INTENSITY_COL: [float(series[s]) if s in series else np.nan for s in sweeps],
        }
    )


def align_to_sweeps(
    series: Mapping[int, float] | pd.DataFrame | None,
    target_sweeps: Sequence[int],
) -> np.ndarray:
    """Float array length len(target_sweeps); missing → NaN.

    Accepts a sweep→value map or a load_stim_intensity_csv DataFrame.
    """
    if isinstance(series, pd.DataFrame):
        mapping = series_from_frame(series)
    elif series is None:
        mapping = {}
    else:
        mapping = {int(k): float(v) for k, v in series.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}

    n = len(target_sweeps)
    out = np.full(n, np.nan, dtype=float)
    for i, sw in enumerate(target_sweeps):
        try:
            key = int(sw)
        except (TypeError, ValueError):
            continue
        if key in mapping:
            out[i] = mapping[key]
    return out


def align_to_n_sweeps(
    series: Mapping[int, float] | pd.DataFrame | None,
    n_sweeps: int,
    *,
    sweep_start: int = 0,
) -> np.ndarray:
    """Align to consecutive sweeps ``sweep_start .. sweep_start+n_sweeps-1``."""
    if n_sweeps < 0:
        raise ValueError("n_sweeps must be >= 0")
    targets = list(range(sweep_start, sweep_start + n_sweeps))
    return align_to_sweeps(series, targets)


def expand_bin_values_to_sweeps(
    bin_values: Sequence[float | None],
    *,
    bin_size: int,
    n_sweeps: int,
    sweep_start: int = 0,
) -> dict[int, float]:
    """Map each bin intensity onto all member sweeps (for CSV write from bin table).

    Bin ``i`` covers sweeps ``[sweep_start + i*bin_size, sweep_start + (i+1)*bin_size)``
    clipped to ``n_sweeps`` total sweeps from ``sweep_start``.
    """
    if bin_size < 1:
        raise ValueError("bin_size must be >= 1")
    if n_sweeps < 0:
        raise ValueError("n_sweeps must be >= 0")
    out: dict[int, float] = {}
    for i, val in enumerate(bin_values):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if np.isnan(fval):
            continue
        lo = sweep_start + i * bin_size
        hi = min(sweep_start + (i + 1) * bin_size, sweep_start + n_sweeps)
        for sw in range(lo, hi):
            out[sw] = fval
    return out


def bin_values_from_sweep_series(
    series: Mapping[int, float] | pd.DataFrame | None,
    *,
    n_bins: int,
    bin_size: int,
    sweep_start: int = 0,
) -> np.ndarray:
    """One value per bin (mean of finite sweep intensities in that bin); else NaN."""
    if bin_size < 1:
        raise ValueError("bin_size must be >= 1")
    if isinstance(series, pd.DataFrame):
        mapping = series_from_frame(series)
    elif series is None:
        mapping = {}
    else:
        mapping = dict(series)
    out = np.full(n_bins, np.nan, dtype=float)
    for i in range(n_bins):
        lo = sweep_start + i * bin_size
        hi = lo + bin_size
        vals = [mapping[sw] for sw in range(lo, hi) if sw in mapping and np.isfinite(mapping[sw])]
        if vals:
            out[i] = float(np.mean(vals))
    return out
