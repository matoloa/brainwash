"""Pure series/layout descriptors for addRow, addGroup, graphRefresh (no matplotlib/Qt)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

IO_INPUT_TO_XCOL = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}
IO_OUTPUT_TO_YCOL = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}

GROUP_MEAN_COLUMNS = (
    ("EPSP_amp_mean", "ax1", "EPSP_amp"),
    ("EPSP_slope_mean", "ax2", "EPSP_slope"),
    ("volley_amp_mean", "ax1", "volley_amp"),
    ("volley_slope_mean", "ax2", "volley_slope"),
)

PP_ASPECT_AXES = (
    ("EPSP_amp", "ax1"),
    ("EPSP_slope", "ax2"),
    ("volley_amp", "ax1"),
    ("volley_slope", "ax2"),
)

PP_ASPECT_LABELS = {
    "EPSP_amp": "EPSP Amp",
    "EPSP_slope": "EPSP Slope",
    "volley_amp": "Volley Amp",
    "volley_slope": "Volley Slope",
}


@dataclass(frozen=True)
class IoRegressionLine:
    slope: float
    intercept: float
    x0: float
    x1: float

    @property
    def x_line(self) -> np.ndarray:
        return np.array([self.x0, self.x1])

    @property
    def y_line(self) -> np.ndarray:
        return self.slope * self.x_line + self.intercept


@dataclass(frozen=True)
class GroupMeanSeries:
    x: np.ndarray
    y_mean: np.ndarray
    y_sem: np.ndarray
    y_norm: np.ndarray | None
    y_norm_sem: np.ndarray | None


def io_axis_columns(io_input: str, io_output: str) -> tuple[str, str]:
    x_col = IO_INPUT_TO_XCOL.get(io_input, "volley_amp")
    y_col_base = IO_OUTPUT_TO_YCOL.get(io_output, "EPSP_amp")
    return x_col, y_col_base


def io_y_column(y_col_base: str, *, variant: str) -> str:
    return f"{y_col_base}_norm" if variant == "norm" else y_col_base


def recording_plot_label(rec_name: str, rec_filter: str) -> str:
    if rec_filter != "voltage":
        return f"{rec_name} ({rec_filter})"
    return rec_name


def skip_pp_recording_output(experiment_type: str, n_stims: int) -> bool:
    return experiment_type == "PP" and n_stims != 2


def compute_io_regression(
    x_vals: np.ndarray,
    y_vals: np.ndarray,
    *,
    force_through_zero: bool,
) -> IoRegressionLine | None:
    if len(x_vals) < 2:
        return None
    x_vals = np.asarray(x_vals, dtype=float)
    y_vals = np.asarray(y_vals, dtype=float)
    if force_through_zero:
        x_sq_sum = np.sum(x_vals**2)
        slope = np.sum(x_vals * y_vals) / x_sq_sum if x_sq_sum != 0 else 0.0
        intercept = 0.0
        x0 = 0.0
        x1 = float(x_vals.max())
    elif x_vals.max() - x_vals.min() < 1e-5:
        slope = 0.0
        intercept = float(np.mean(y_vals))
        x0 = float(x_vals.min())
        x1 = float(x_vals.max())
    else:
        x_mean = float(np.mean(x_vals))
        slope, c_cent = np.polyfit(x_vals - x_mean, y_vals, 1)
        intercept = float(c_cent - slope * x_mean)
        x0 = float(x_vals.min())
        x1 = float(x_vals.max())
    return IoRegressionLine(slope=float(slope), intercept=float(intercept), x0=x0, x1=x1)


def io_scatter_frame(df_sweeps: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame | None:
    if x_col not in df_sweeps.columns or y_col not in df_sweeps.columns:
        return None
    df_clean = df_sweeps.dropna(subset=[x_col, y_col])
    if df_clean.empty:
        return None
    return df_clean


def group_mean_plots_for_df(df_groupmean: pd.DataFrame) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for col, axid, aspect in GROUP_MEAN_COLUMNS:
        if col in df_groupmean.columns and df_groupmean[col].notna().any():
            out.append((axid, aspect, col))
    return out


def default_group_aspect(axid: str) -> str:
    return "EPSP_amp" if axid == "ax1" else "EPSP_slope"


def _aligned_sem(series: pd.Series, index) -> np.ndarray:
    sem = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if hasattr(sem, "reindex"):
        sem = sem.reindex(index).fillna(0.0)
    return np.asarray(sem).ravel()


def extract_group_mean_series(df_groupmean: pd.DataFrame, aspect: str) -> GroupMeanSeries:
    x = np.asarray(df_groupmean.sweep)
    y_mean = np.asarray(df_groupmean[f"{aspect}_mean"])
    sem_col = f"{aspect}_SEM"
    if sem_col in df_groupmean.columns:
        y_sem = _aligned_sem(df_groupmean[sem_col], df_groupmean.index)
    else:
        y_sem = np.zeros_like(y_mean, dtype=float)

    npts = len(x)
    if len(y_sem) != npts:
        y_sem = np.full(npts, float(y_sem[0]) if len(y_sem) else 0.0)

    norm_col = f"{aspect}_norm_mean"
    if norm_col in df_groupmean.columns:
        y_norm = np.asarray(df_groupmean[norm_col])
        norm_sem_col = f"{aspect}_norm_SEM"
        if norm_sem_col in df_groupmean.columns:
            y_norm_sem = _aligned_sem(df_groupmean[norm_sem_col], df_groupmean.index)
        else:
            y_norm_sem = np.zeros_like(y_norm, dtype=float)
        if len(y_norm_sem) != npts:
            y_norm_sem = np.full(npts, float(y_norm_sem[0]) if len(y_norm_sem) else 0.0)
    else:
        y_norm = None
        y_norm_sem = None

    return GroupMeanSeries(x=x, y_mean=y_mean, y_sem=y_sem, y_norm=y_norm, y_norm_sem=y_norm_sem)


def pp_active_aspects(checkbox: dict) -> list[tuple[str, str]]:
    return [(asp, axid) for asp, axid in PP_ASPECT_AXES if checkbox.get(asp, True)]


def pp_bar_layout(active_aspects: list[tuple[str, str]]) -> list[tuple[str, str, float, float]]:
    """Return (aspect, axid, x_offset, bar_width) per enabled PP aspect."""
    if not active_aspects:
        return []
    n_active = len(active_aspects)
    bar_width = 0.8 / max(1, n_active)
    start_offset = -0.4 + (bar_width / 2)
    configs: list[tuple[str, str, float, float]] = []
    for i, (asp, axid) in enumerate(active_aspects):
        offset = start_offset + (i * bar_width)
        configs.append((asp, axid, offset, bar_width * 0.9))
    return configs


def pp_overlay_x_map(checkbox: dict) -> dict[str, int]:
    x_val_map: dict[str, int] = {}
    idx = 1
    for key in ("EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"):
        if checkbox.get(key, True):
            x_val_map[key] = idx
            idx += 1
    return x_val_map


def pp_recording_view_ticks(checkbox: dict) -> tuple[list[int], list[str]]:
    ticks: list[int] = []
    labels: list[str] = []
    for i, (asp, _) in enumerate(PP_ASPECT_AXES, start=1):
        if checkbox.get(asp, True):
            ticks.append(i)
            labels.append(PP_ASPECT_LABELS[asp])
    return ticks, labels


def mean_sem(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    arr = np.asarray(vals, dtype=float)
    mean_val = float(np.mean(arr))
    sem_val = float(np.std(arr, ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0
    return mean_val, sem_val