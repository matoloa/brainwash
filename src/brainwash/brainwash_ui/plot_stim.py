"""Pure per-stim geometry for addRow (no matplotlib/Qt)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

STIM_TIME_VARIABLES = (
    "t_EPSP_amp",
    "t_EPSP_slope_start",
    "t_EPSP_slope_end",
    "t_volley_amp",
    "t_volley_slope_start",
    "t_volley_slope_end",
)

AMP_ZERO_PRE_WINDOW = (-0.002, -0.001)


def stim_num_from_index(i_stim: int) -> int:
    return i_stim + 1


def amp_zero_and_y_at_stim(dfmean: pd.DataFrame, t_stim: float, rec_filter: str) -> tuple[float, float]:
    """Return (amp_zero_plot, y_at_stim) per CONTRACT amp_zero window."""
    t_idx = (dfmean["time"] - t_stim).abs().idxmin()
    y_at_stim = float(dfmean.loc[t_idx, rec_filter])
    pre = dfmean[(dfmean["time"] >= t_stim + AMP_ZERO_PRE_WINDOW[0]) & (dfmean["time"] < t_stim + AMP_ZERO_PRE_WINDOW[1])]
    amp_zero = float(pre[rec_filter].mean()) if not pre.empty else y_at_stim
    return amp_zero, y_at_stim


def event_window_df(
    dfmean: pd.DataFrame,
    t_stim: float,
    event_start: float,
    event_end: float,
    rec_filter: str,
) -> pd.DataFrame:
    window_start = t_stim + event_start
    window_end = t_stim + event_end
    df_event = dfmean[(dfmean["time"] >= window_start) & (dfmean["time"] <= window_end)].copy()
    df_event["time"] = df_event["time"] - t_stim
    return df_event


def shift_stim_times(t_row: pd.Series, t_stim: float, variables: tuple[str, ...] = STIM_TIME_VARIABLES) -> None:
    for var in variables:
        t_row[var] -= t_stim


def y_at_event_time(df_event: pd.DataFrame, t_rel: float, rec_filter: str, *, default: float = 0.0) -> float:
    if df_event.empty:
        return default
    return float(df_event.loc[(df_event["time"] - t_rel).abs().idxmin(), rec_filter])


def _amp_val_in_window(df_event: pd.DataFrame, x_position: float, half: float, rec_filter: str, amp_zero_plot: float) -> float:
    if half == 0:
        amp_val = y_at_event_time(df_event, x_position, rec_filter, default=amp_zero_plot)
    else:
        window = df_event[(df_event["time"] >= x_position - half) & (df_event["time"] <= x_position + half)]
        amp_val = float(window[rec_filter].mean()) if not window.empty else amp_zero_plot
    return -(amp_val - amp_zero_plot)


def resolve_epsp_amp_si(
    out_stim_row: pd.DataFrame,
    df_event: pd.DataFrame,
    x_position: float,
    t_row: pd.Series,
    rec_filter: str,
    amp_zero_plot: float,
) -> float:
    if not out_stim_row.empty:
        val = out_stim_row["EPSP_amp"].values[0] / 1000.0
    else:
        val = np.nan
    if pd.isna(val):
        half = t_row.get("t_EPSP_amp_halfwidth", 0)
        val = _amp_val_in_window(df_event, x_position, half, rec_filter, amp_zero_plot)
    return float(val)


def resolve_volley_amp_si(
    t_row: pd.Series,
    out_stim_row: pd.DataFrame,
    df_event: pd.DataFrame,
    x_position: float,
    rec_filter: str,
    amp_zero_plot: float,
) -> float:
    volley_amp_mean = t_row.get("volley_amp_mean")
    if volley_amp_mean is not None and not pd.isna(volley_amp_mean):
        return float(volley_amp_mean)
    if not out_stim_row.empty:
        val = out_stim_row["volley_amp"].values[0] / 1000.0
    else:
        val = np.nan
    if pd.isna(val):
        half = t_row.get("t_volley_amp_halfwidth", 0)
        val = _amp_val_in_window(df_event, x_position, half, rec_filter, amp_zero_plot)
    return float(val)


def volley_amp_hline_mv(volley_amp_si: float) -> float:
    return volley_amp_si * 1000.0


@dataclass(frozen=True)
class SlopeSegment:
    x_start: float
    x_end: float
    y_start: float | None
    y_end: float | None


def slope_segment(df_event: pd.DataFrame, x_start: float, x_end: float, rec_filter: str) -> SlopeSegment | None:
    if np.isnan(x_start) or np.isnan(x_end):
        return None
    idx_s = (df_event["time"] - x_start).abs().idxmin()
    y_start = float(df_event.loc[idx_s, rec_filter]) if idx_s in df_event.index else None
    idx_e = (df_event["time"] - x_end).abs().idxmin()
    y_end = float(df_event.loc[idx_e, rec_filter]) if idx_e in df_event.index else None
    return SlopeSegment(x_start, x_end, y_start, y_end)


def resolve_volley_slope_mean(t_row: pd.Series, out_stim_row: pd.DataFrame, out: pd.DataFrame) -> float:
    volley_slope_mean = t_row.get("volley_slope_mean")
    if volley_slope_mean is not None and not pd.isna(volley_slope_mean):
        return float(volley_slope_mean)
    if not out_stim_row.empty:
        return float(out_stim_row["volley_slope"].values[0])
    return float(out["volley_slope"].mean())