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


@dataclass(frozen=True)
class StimMarkerPlotSpec:
    label: str
    axid: str
    x: float
    y: float
    color: str
    aspect: str | None = None
    stim: int | None = None


@dataclass(frozen=True)
class StimVlinePlotSpec:
    label: str
    axid: str
    x: float
    color: str
    stim: int | None = None


@dataclass(frozen=True)
class StimLinePlotSpec:
    label: str
    axid: str
    x: object
    y: object
    color: str
    stim: int | None = None
    aspect: str | None = None
    variant: str = "raw"
    x_mode: str | None = None
    width: int = 1


@dataclass(frozen=True)
class StimAmpWidthPlotSpec:
    label: str
    axid: str
    x_center: float
    amp_x: tuple[float, float]
    amp_y: tuple[float, float]
    color: str
    aspect: str
    stim: int


@dataclass(frozen=True)
class StimHlinePlotSpec:
    label: str
    axid: str
    y: float
    color: str
    aspect: str
    stim: int
    x_mode: str = "sweep"


StimEventPlotSpec = (
    StimMarkerPlotSpec | StimVlinePlotSpec | StimLinePlotSpec | StimAmpWidthPlotSpec | StimHlinePlotSpec
)


def _stim_label_suffix(stim_num: int) -> str:
    return f"- stim {stim_num}"


def build_stim_event_plot_specs(
    label: str,
    dft: pd.DataFrame,
    dfmean: pd.DataFrame,
    dfoutput: pd.DataFrame,
    rec_filter: str,
    settings: dict,
    stim_colors: dict[int, str],
) -> list[StimEventPlotSpec]:
    """Per-stim event/marker/output descriptors for addRow (no matplotlib artists)."""
    specs: list[StimEventPlotSpec] = []
    for i_stim, t_row in dft.iterrows():
        color = stim_colors[i_stim]
        stim_num = stim_num_from_index(i_stim)
        stim_str = _stim_label_suffix(stim_num)
        t_stim = t_row["t_stim"]
        out = dfoutput[dfoutput["stim"] == stim_num]
        amp_zero_plot, _y_at_stim = amp_zero_and_y_at_stim(dfmean, t_stim, rec_filter)
        shift_stim_times(t_row, t_stim)

        specs.append(StimMarkerPlotSpec(f"mean {label} {stim_str} marker", "axm", t_stim, 0.0, color))
        specs.append(
            StimVlinePlotSpec(f"mean {label} {stim_str} selection marker", "axm", t_stim, color, stim=stim_num)
        )

        df_event = event_window_df(
            dfmean, t_stim, settings["event_start"], settings["event_end"], rec_filter
        )
        specs.append(
            StimLinePlotSpec(
                f"{label} {stim_str}",
                "axe",
                df_event["time"].values,
                df_event[rec_filter].values,
                color,
                stim=stim_num,
            )
        )

        out_stim_row = out[out["sweep"].isna()]

        if not np.isnan(t_row["t_EPSP_amp"]):
            x_position = t_row["t_EPSP_amp"]
            y_position = y_at_event_time(df_event, x_position, rec_filter)
            specs.append(
                StimMarkerPlotSpec(
                    f"{label} {stim_str} EPSP amp marker",
                    "axe",
                    x_position,
                    y_position,
                    settings["rgb_EPSP_amp"],
                    aspect="EPSP_amp",
                    stim=stim_num,
                )
            )
            amp_x = (
                x_position - t_row["t_EPSP_amp_halfwidth"],
                x_position + t_row["t_EPSP_amp_halfwidth"],
            )
            epsp_amp_val = resolve_epsp_amp_si(out_stim_row, df_event, x_position, t_row, rec_filter, amp_zero_plot)
            amp_y = (amp_zero_plot, amp_zero_plot - epsp_amp_val)
            specs.append(
                StimAmpWidthPlotSpec(
                    f"{label} {stim_str} EPSP amp",
                    "axe",
                    x_position,
                    amp_x,
                    amp_y,
                    settings["rgb_EPSP_amp"],
                    "EPSP_amp",
                    stim_num,
                )
            )
            specs.extend(
                [
                    StimLinePlotSpec(
                        f"{label} {stim_str} EPSP amp",
                        "ax1",
                        out["sweep"].values,
                        out["EPSP_amp"].values,
                        settings["rgb_EPSP_amp"],
                        stim=stim_num,
                        aspect="EPSP_amp",
                        variant="raw",
                        x_mode="sweep",
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} EPSP amp norm",
                        "ax1",
                        out["sweep"].values,
                        out["EPSP_amp_norm"].values,
                        settings["rgb_EPSP_amp"],
                        stim=stim_num,
                        aspect="EPSP_amp",
                        variant="norm",
                        x_mode="sweep",
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} amp_zero marker",
                        "axe",
                        list(AMP_ZERO_PRE_WINDOW),
                        [amp_zero_plot, amp_zero_plot],
                        settings["rgb_EPSP_amp"],
                        stim=stim_num,
                        aspect="EPSP_amp",
                    ),
                ]
            )

        epsp_slope = slope_segment(
            df_event, t_row["t_EPSP_slope_start"], t_row["t_EPSP_slope_end"], rec_filter
        )
        if epsp_slope is not None:
            specs.extend(
                [
                    StimLinePlotSpec(
                        f"{label} {stim_str} EPSP slope marker",
                        "axe",
                        [epsp_slope.x_start, epsp_slope.x_end],
                        [epsp_slope.y_start, epsp_slope.y_end],
                        settings["rgb_EPSP_slope"],
                        stim=stim_num,
                        aspect="EPSP_slope",
                        width=5,
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} EPSP slope",
                        "ax2",
                        out["sweep"].values,
                        out["EPSP_slope"].values,
                        settings["rgb_EPSP_slope"],
                        stim=stim_num,
                        aspect="EPSP_slope",
                        variant="raw",
                        x_mode="sweep",
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} EPSP slope norm",
                        "ax2",
                        out["sweep"].values,
                        out["EPSP_slope_norm"].values,
                        settings["rgb_EPSP_slope"],
                        stim=stim_num,
                        aspect="EPSP_slope",
                        variant="norm",
                        x_mode="sweep",
                    ),
                ]
            )

        if not np.isnan(t_row["t_volley_amp"]):
            x_position = t_row["t_volley_amp"]
            y_position = y_at_event_time(df_event, x_position, rec_filter)
            volley_color = settings["rgb_volley_amp"]
            specs.append(
                StimMarkerPlotSpec(
                    f"{label} {stim_str} volley amp marker",
                    "axe",
                    t_row["t_volley_amp"],
                    y_position,
                    volley_color,
                    aspect="volley_amp",
                    stim=stim_num,
                )
            )
            amp_x = (
                x_position - t_row["t_volley_amp_halfwidth"],
                x_position + t_row["t_volley_amp_halfwidth"],
            )
            volley_amp_mean = resolve_volley_amp_si(
                t_row, out_stim_row, df_event, x_position, rec_filter, amp_zero_plot
            )
            amp_y = (amp_zero_plot, amp_zero_plot - volley_amp_mean)
            specs.append(
                StimAmpWidthPlotSpec(
                    f"{label} {stim_str} volley amp",
                    "axe",
                    x_position,
                    amp_x,
                    amp_y,
                    volley_color,
                    "volley_amp",
                    stim_num,
                )
            )
            specs.extend(
                [
                    StimHlinePlotSpec(
                        f"{label} {stim_str} volley amp mean",
                        "ax1",
                        volley_amp_hline_mv(volley_amp_mean),
                        volley_color,
                        "volley_amp_mean",
                        stim_num,
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} volley amp",
                        "ax1",
                        out["sweep"].values,
                        out["volley_amp"].values,
                        volley_color,
                        stim=stim_num,
                        aspect="volley_amp",
                        x_mode="sweep",
                    ),
                ]
            )

        volley_slope = slope_segment(
            df_event, t_row["t_volley_slope_start"], t_row["t_volley_slope_end"], rec_filter
        )
        if volley_slope is not None:
            volley_slope_mean = resolve_volley_slope_mean(t_row, out_stim_row, out)
            specs.extend(
                [
                    StimLinePlotSpec(
                        f"{label} {stim_str} volley slope marker",
                        "axe",
                        [volley_slope.x_start, volley_slope.x_end],
                        [volley_slope.y_start, volley_slope.y_end],
                        settings["rgb_volley_slope"],
                        stim=stim_num,
                        aspect="volley_slope",
                        width=5,
                    ),
                    StimHlinePlotSpec(
                        f"{label} {stim_str} volley slope mean",
                        "ax2",
                        volley_slope_mean,
                        settings["rgb_volley_slope"],
                        "volley_slope_mean",
                        stim_num,
                    ),
                    StimLinePlotSpec(
                        f"{label} {stim_str} volley slope",
                        "ax2",
                        out["sweep"].values,
                        out["volley_slope"].values,
                        settings["rgb_volley_slope"],
                        stim=stim_num,
                        aspect="volley_slope",
                        x_mode="sweep",
                    ),
                ]
            )

    return specs


DRAG_UPDATE_ASPECTS = ("EPSP slope", "volley slope", "EPSP amp", "volley amp")
SLOPE_DRAG_ASPECTS = frozenset({"EPSP slope", "volley slope"})
AMP_DRAG_ASPECTS = frozenset({"EPSP amp", "volley amp"})


def validate_drag_update_inputs(prow, trow, aspect, data_x, data_y, amp) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(prow, pd.Series):
        raise TypeError(f"prow must be pandas.Series, got {type(prow).__name__}")
    if not isinstance(trow, (pd.Series, dict)):
        raise TypeError(f"trow must be pandas.Series or dict, got {type(trow).__name__}")
    if isinstance(trow, dict) and not trow:
        raise ValueError("trow dict is empty")
    if aspect not in DRAG_UPDATE_ASPECTS:
        raise ValueError(f"aspect must be one of {DRAG_UPDATE_ASPECTS}, got '{aspect}'")
    try:
        x_arr = np.asarray(data_x)
        y_arr = np.asarray(data_y)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"data_x/data_y must be array-like: {exc}") from exc
    if len(x_arr) != len(y_arr):
        raise ValueError(f"data_x and data_y must have same length, got {len(x_arr)} and {len(y_arr)}")
    if amp is not None and not isinstance(amp, (int, float, np.number)):
        raise TypeError(f"amp must be numeric or None, got {type(amp).__name__}")
    for key in ("t_stim", "stim"):
        if key not in trow:
            raise KeyError(f"trow missing required key: '{key}'")
    return x_arr, y_arr


def drag_update_label_core(rec_name: str, rec_filter, stim, aspect: str) -> str:
    if rec_filter != "voltage":
        return f"{rec_name} ({rec_filter}) - stim {stim} {aspect}"
    return f"{rec_name} - stim {stim} {aspect}"


def drag_output_label(label_core: str, aspect: str, norm_epsp: bool) -> str:
    if norm_epsp and aspect in ("EPSP slope", "EPSP amp"):
        return f"{label_core} norm"
    return label_core


def slope_output_column(aspect: str, norm_epsp: bool) -> str:
    if aspect == "EPSP slope":
        return "EPSP_slope_norm" if norm_epsp else "EPSP_slope"
    return aspect.replace(" ", "_")


def amp_output_column(aspect: str, norm_epsp: bool) -> str:
    key = aspect.replace(" ", "_")
    if aspect == "EPSP amp" and norm_epsp:
        return f"{key}_norm"
    return key


def slope_marker_xy(trow, aspect: str, stim_offset: float, data_x: np.ndarray, data_y: np.ndarray) -> tuple[list, list]:
    key = aspect.replace(" ", "_")
    x_start = trow[f"t_{key}_start"] - stim_offset
    x_end = trow[f"t_{key}_end"] - stim_offset
    y_start = float(data_y[np.abs(data_x - x_start).argmin()])
    y_end = float(data_y[np.abs(data_x - x_end).argmin()])
    return [x_start, x_end], [y_start, y_end]


def amp_zero_from_drag_trace(data_x: np.ndarray, data_y: np.ndarray, y_fallback: float) -> float:
    pre_stim_mask = (data_x >= AMP_ZERO_PRE_WINDOW[0]) & (data_x < AMP_ZERO_PRE_WINDOW[1])
    if pre_stim_mask.any():
        return float(data_y[pre_stim_mask].mean())
    return float(y_fallback)


@dataclass(frozen=True)
class AmpDragGeometry:
    t_amp: float
    y_position: float
    amp_x: tuple[float, float]
    amp_zero: float


def amp_drag_geometry(
    trow,
    aspect: str,
    stim_offset: float,
    data_x: np.ndarray,
    data_y: np.ndarray,
    amp_zero_plot: float | None = None,
) -> AmpDragGeometry:
    key = aspect.replace(" ", "_")
    t_amp = trow[f"t_{key}"] - stim_offset
    y_position = float(data_y[np.abs(data_x - t_amp).argmin()])
    amp_x = (
        t_amp - trow[f"t_{key}_halfwidth"],
        t_amp + trow[f"t_{key}_halfwidth"],
    )
    if amp_zero_plot is None:
        amp_zero_plot = amp_zero_from_drag_trace(data_x, data_y, y_position)
    return AmpDragGeometry(t_amp=t_amp, y_position=y_position, amp_x=amp_x, amp_zero=amp_zero_plot)


def resolve_drag_amp_si(amp, y_position: float, amp_zero: float) -> float | None:
    if amp is None or pd.isna(amp):
        amp = -(y_position - amp_zero)
    if amp is None or pd.isna(amp):
        return None
    expected_amp = -(y_position - amp_zero)
    if abs(expected_amp) > 1e-6 and abs(amp / expected_amp) > 50:
        amp = amp / 1000.0
    elif abs(expected_amp) <= 1e-6 and abs(amp) > 1e-3:
        amp = amp / 1000.0
    return float(amp)


def amp_width_y_coords(amp_si: float, amp_zero: float) -> tuple[float, float]:
    return amp_zero, (0 - amp_si) + amp_zero


def amp_x_is_zero_width(amp_x) -> bool:
    return amp_x[0] == amp_x[1]


def mean_of_selected_sweeps(df: pd.DataFrame, selected, col: str) -> pd.DataFrame:
    df_sweeps = df[df["sweep"].isin(selected)]
    return df_sweeps.groupby("time", as_index=False)[col].mean()


@dataclass(frozen=True)
class AxeMeanLinePlotSpec:
    label: str
    axid: str
    x: object
    y: object
    color: object
    rec_id: str
    stim: int
    alpha: float


def build_axe_mean_plot_specs(
    rec_id: str,
    selected_sweeps,
    df_rec_data: pd.DataFrame,
    df_rec_time: pd.DataFrame,
    settings: dict,
    stim_colors: dict[int, str],
) -> list[AxeMeanLinePlotSpec]:
    """Mean-of-selected-sweeps trace descriptors for update_axe_mean (no matplotlib artists)."""
    col = settings.get("filter") or "voltage"
    df_mean = mean_of_selected_sweeps(df_rec_data, selected_sweeps, col)
    alpha = settings["alpha_line"] / 2
    specs: list[AxeMeanLinePlotSpec] = []
    for i_stim, t_row in df_rec_time.iterrows():
        color = stim_colors[i_stim]
        stim_num = stim_num_from_index(i_stim)
        stim_str = _stim_label_suffix(stim_num)
        t_stim = t_row["t_stim"]
        df_event = event_window_df(df_mean, t_stim, settings["event_start"], settings["event_end"], col)
        specs.append(
            AxeMeanLinePlotSpec(
                label=f"axe mean selected sweeps {stim_str}",
                axid="axe",
                x=df_event["time"],
                y=df_event[col],
                color=color,
                rec_id=rec_id,
                stim=stim_num,
                alpha=alpha,
            )
        )
    return specs