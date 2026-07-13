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


def pp_group_tick_from_bar(x_left: float, bar_width: float) -> int:
    return round(x_left + bar_width / 2)


def pp_group_tick_label_map(bar_specs: list[tuple[float, float, str]]) -> tuple[list[int], list[str]]:
    """Build sorted PP group xticks from (x_left, width, display_label) tuples."""
    name_by_x: dict[int, str] = {}
    for x_left, width, label in bar_specs:
        name_by_x[pp_group_tick_from_bar(x_left, width)] = label
    ticks = sorted(name_by_x.keys())
    return ticks, [name_by_x[x] for x in ticks]


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


def compute_ppr(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    ppr = np.asarray(v2, dtype=float) / np.asarray(v1, dtype=float)
    ppr[~np.isfinite(ppr)] = np.nan
    return ppr


def compute_ppr_percent(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    return compute_ppr(v1, v2) * 100.0


def pp_recording_aspect_configs(settings: dict) -> list[tuple[str, str, str]]:
    return [
        ("EPSP_amp", "ax1", settings.get("rgb_EPSP_amp", "blue")),
        ("EPSP_slope", "ax2", settings.get("rgb_EPSP_slope", "red")),
        ("volley_amp", "ax1", settings.get("rgb_volley_amp", "green")),
        ("volley_slope", "ax2", settings.get("rgb_volley_slope", "orange")),
    ]


@dataclass(frozen=True)
class PpRecordingPprSpec:
    aspect: str
    axid: str
    color: str
    ppr: np.ndarray
    x_val: int
    n_points: int


def pp_recording_ppr_specs(
    o1: pd.DataFrame,
    o2: pd.DataFrame,
    checkbox: dict,
    settings: dict,
) -> list[PpRecordingPprSpec]:
    x_map = pp_overlay_x_map(checkbox)
    specs: list[PpRecordingPprSpec] = []
    for aspect, axid, color in pp_recording_aspect_configs(settings):
        if aspect not in o1.columns or aspect not in o2.columns:
            continue
        v1 = o1[aspect].values.astype(float)
        v2 = o2[aspect].values.astype(float)
        specs.append(
            PpRecordingPprSpec(
                aspect=aspect,
                axid=axid,
                color=color,
                ppr=compute_ppr(v1, v2),
                x_val=x_map.get(aspect, 1),
                n_points=len(v1),
            )
        )
    return specs


def stim_aggregate_line_configs(settings: dict) -> list[tuple[str, str, str, str, str]]:
    return [
        ("EPSP amp", "ax1", "EPSP_amp", settings["rgb_EPSP_amp"], "raw"),
        ("EPSP amp norm", "ax1", "EPSP_amp_norm", settings["rgb_EPSP_amp"], "norm"),
        ("EPSP slope", "ax2", "EPSP_slope", settings["rgb_EPSP_slope"], "raw"),
        ("EPSP slope norm", "ax2", "EPSP_slope_norm", settings["rgb_EPSP_slope"], "norm"),
        ("volley amp", "ax1", "volley_amp", settings["rgb_volley_amp"], "raw"),
        ("volley slope", "ax2", "volley_slope", settings["rgb_volley_slope"], "raw"),
    ]


def stim_aggregate_sem(df_sem: pd.DataFrame, out_stim: pd.DataFrame, col: str) -> np.ndarray | None:
    if col not in df_sem.columns:
        return None
    return df_sem[col].reindex(out_stim["stim"]).values


STIM_MODE_SUFFIX_TO_COL = {
    "EPSP amp": "EPSP_amp",
    "EPSP amp norm": "EPSP_amp_norm",
    "EPSP slope": "EPSP_slope",
    "EPSP slope norm": "EPSP_slope_norm",
    "volley amp": "volley_amp",
    "volley slope": "volley_slope",
}


@dataclass(frozen=True)
class IoScatterPlotSpec:
    label: str
    variant: str
    aspect: str
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class IoTrendlinePlotSpec:
    label: str
    variant: str
    aspect: str
    x: np.ndarray
    y: np.ndarray


def build_io_recording_plot_specs(
    dfoutput: pd.DataFrame,
    label: str,
    io_input: str,
    io_output: str,
    *,
    force_through_zero: bool,
) -> list[IoScatterPlotSpec | IoTrendlinePlotSpec]:
    """Pure IO scatter/trendline data for addRow (no matplotlib artists)."""
    _, y_col_base = io_axis_columns(io_input, io_output)
    specs: list[IoScatterPlotSpec | IoTrendlinePlotSpec] = []
    for variant in ("raw", "norm"):
        xy = io_scatter_xy(dfoutput, io_input, io_output, variant=variant)
        if xy is None:
            continue
        specs.append(
            IoScatterPlotSpec(
                label=f"{label} {variant} IO scatter",
                variant=variant,
                aspect=y_col_base,
                x=xy[0],
                y=xy[1],
            )
        )
        line_xy = io_trendline_xy(
            dfoutput,
            io_input,
            io_output,
            variant=variant,
            force_through_zero=force_through_zero,
        )
        if line_xy is not None:
            specs.append(
                IoTrendlinePlotSpec(
                    label=f"{label} {variant} IO trendline",
                    variant=variant,
                    aspect=y_col_base,
                    x=line_xy[0],
                    y=line_xy[1],
                )
            )
    return specs


def io_scatter_xy(
    dfoutput: pd.DataFrame,
    io_input: str,
    io_output: str,
    *,
    variant: str,
) -> tuple[np.ndarray, np.ndarray] | None:
    x_col, y_col_base = io_axis_columns(io_input, io_output)
    y_col = io_y_column(y_col_base, variant=variant)
    df_sweeps = dfoutput[dfoutput["sweep"].notna()]
    df_clean = io_scatter_frame(df_sweeps, x_col, y_col)
    if df_clean is None:
        return None
    return df_clean[x_col].values, df_clean[y_col].values


def io_trendline_xy(
    dfoutput: pd.DataFrame,
    io_input: str,
    io_output: str,
    *,
    variant: str,
    force_through_zero: bool,
) -> tuple[np.ndarray, np.ndarray] | None:
    x_col, y_col_base = io_axis_columns(io_input, io_output)
    y_col = io_y_column(y_col_base, variant=variant)
    df_sweeps = dfoutput[dfoutput["sweep"].notna()]
    df_clean = io_scatter_frame(df_sweeps, x_col, y_col)
    if df_clean is None or len(df_clean) < 2:
        return None
    reg = compute_io_regression(
        df_clean[x_col].values,
        df_clean[y_col].values,
        force_through_zero=force_through_zero,
    )
    if reg is None:
        return None
    return reg.x_line, reg.y_line