"""Pure series/layout descriptors for addRow, addGroup, graphRefresh (no matplotlib/Qt)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from brainwash_ui import plot_drag, plot_model
from ui_state_parts import measure_rgb

IO_INPUT_TO_XCOL = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim_intensity"}
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

# Stable x slots for recording PP view (and group aspect ordering).
# Volley must never share the EPSP amp/slope slot when toggled on later.
PP_ASPECT_X = {
    "EPSP_amp": 1,
    "EPSP_slope": 2,
    "volley_amp": 3,
    "volley_slope": 4,
}

PP_ASPECT_LABELS = {
    "EPSP_amp": "EPSP Amp",
    "EPSP_slope": "EPSP Slope",
    "volley_amp": "Volley Amp",
    "volley_slope": "Volley Slope",
}

# Short tokens for x-tick labels: "Ctl amp (n=6)"
PP_ASPECT_TICK = {
    "EPSP_amp": "amp",
    "EPSP_slope": "slope",
    "volley_amp": "volley amp",
    "volley_slope": "volley slope",
}


def pp_group_x_position(dd_groups: dict | None, group_ID) -> int:
    """1-based x slot among groups that have recordings (stable dict order)."""
    if not dd_groups:
        return 1
    ordered = [gid for gid, g in dd_groups.items() if g.get("rec_IDs")]
    if group_ID not in ordered:
        return 1
    return 1 + ordered.index(group_ID)


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
    """Enabled PP aspects for layout/build.

    Volley aspects are omitted under Relative (norm_EPSP): no relative volley
    series exists. Checkbox state is left unchanged and reapplied when relative
    mode is off.
    """
    norm = bool(checkbox.get("norm_EPSP", False))
    out: list[tuple[str, str]] = []
    for asp, axid in PP_ASPECT_AXES:
        if not checkbox.get(asp, True):
            continue
        if norm and asp in ("volley_amp", "volley_slope"):
            continue
        out.append((asp, axid))
    return out


def pp_bar_layout(active_aspects: list[tuple[str, str]]) -> list[tuple[str, str, float, float]]:
    """Return (aspect, axid, x_offset, bar_width) per enabled PP aspect.

    Offsets follow the stable aspect order (amp, slope, volley amp, volley slope)
    across the shared twinx x-space so each box sits on its own tick — volley never
    stacks on the EPSP amp slot.
    """
    if not active_aspects:
        return []
    n_active = len(active_aspects)
    bar_width = 0.8 / max(1, n_active)
    start_offset = -0.4 + (bar_width / 2)
    # Order by fixed aspect slot so EPSP amp / volley amp keep distinct columns.
    ordered = sorted(active_aspects, key=lambda t: PP_ASPECT_X.get(t[0], 99))
    configs: list[tuple[str, str, float, float]] = []
    for i, (asp, axid) in enumerate(ordered):
        offset = start_offset + (i * bar_width)
        configs.append((asp, axid, offset, bar_width * 0.9))
    return configs


PPR_ASPECTS = ("EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope")


def ppr_by_sweep_from_dfoutput(
    dfoutput: pd.DataFrame | None,
    aspect: str,
    sweeps=None,
) -> dict[int, float]:
    """Per-sweep PPR (stim2/stim1) for one aspect. Pure; used by plot + formal stats.

    If ``sweeps`` is a non-empty sequence, only those sweep indices are returned
    (still requires both stims on that sweep). Empty/None → all pairable sweeps.
    """
    if dfoutput is None or getattr(dfoutput, "empty", True):
        return {}
    if "stim" not in dfoutput.columns or "sweep" not in dfoutput.columns:
        return {}
    if aspect not in dfoutput.columns:
        return {}
    out_sweeps = dfoutput[dfoutput["sweep"].notna()]
    if sweeps is not None and isinstance(sweeps, (list, tuple)) and len(sweeps) > 0:
        want = {int(s) for s in sweeps}
        out_sweeps = out_sweeps[out_sweeps["sweep"].map(lambda s: int(s) if pd.notna(s) else s).isin(want)]
    out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
    out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
    common = out1.index.intersection(out2.index).dropna()
    if common.empty:
        return {}
    v1 = out1.loc[common, aspect].to_numpy(dtype=float)
    v2 = out2.loc[common, aspect].to_numpy(dtype=float)
    ppr = compute_ppr(v1, v2)
    out: dict[int, float] = {}
    for sw, val in zip(common, ppr):
        if np.isfinite(val):
            out[int(sw)] = float(val)
    return out


def rec_mean_ppr_from_dfoutput(dfoutput: pd.DataFrame | None) -> dict[str, float]:
    """Mean PPR (stim2/stim1) per aspect from a recording dfoutput. Pure; no artists."""
    if dfoutput is None or getattr(dfoutput, "empty", True):
        return {}
    if "stim" not in dfoutput.columns or "sweep" not in dfoutput.columns:
        return {}
    means: dict[str, float] = {}
    for aspect in PPR_ASPECTS:
        by_sw = ppr_by_sweep_from_dfoutput(dfoutput, aspect)
        if by_sw:
            means[aspect] = float(np.mean(list(by_sw.values())))
    return means


def extract_rec_ppr_means(dict_rec_labels: dict, rec_ids: list) -> dict:
    """Fallback: per-recording PPR means from raw PPR line artists (legacy)."""
    rec_ppr: dict = {}
    rec_id_set = set(rec_ids)
    for rec_id in rec_ids:
        rec_ppr[rec_id] = {}
    for _key, linedict in dict_rec_labels.items():
        rec_id = linedict.get("rec_ID")
        if rec_id not in rec_id_set:
            continue
        if "PPR" not in _key or linedict.get("variant") != "raw":
            continue
        aspect = linedict.get("aspect")
        if not aspect:
            continue
        y_data = plot_drag.artist_ydata(linedict["line"])
        if y_data.size == 0:
            continue
        valid_y = [float(y) for y in y_data if np.isfinite(y)]
        if valid_y:
            rec_ppr[rec_id][aspect] = float(np.mean(valid_y))
    return rec_ppr


@dataclass
class PprLevelAggregate:
    ppr_data: dict[str, list[float]] = field(
        default_factory=lambda: {a: [] for a in PPR_ASPECTS}
    )
    # Parallel unit labels (rec_ID or subject/slice key) for each value in ppr_data
    rec_id_order: dict[str, list] = field(
        default_factory=lambda: {a: [] for a in PPR_ASPECTS}
    )


def aggregate_ppr_at_level(
    rec_ppr: dict,
    level: str,
    df_project: pd.DataFrame | None,
) -> PprLevelAggregate:
    agg = PprLevelAggregate()
    if level == "recording" or level in (None, ""):
        for rec_id, aspect_vals in rec_ppr.items():
            for asp, val in aspect_vals.items():
                if asp in agg.ppr_data:
                    agg.ppr_data[asp].append(val)
                    agg.rec_id_order[asp].append(rec_id)
        return agg

    rec_to_unit: dict = {}
    if df_project is not None:
        for rec_id in rec_ppr:
            mm = df_project[df_project["ID"] == rec_id]
            if mm.empty:
                continue
            pr = mm.iloc[0]
            if level == "subject":
                uk = str(pr.get("subject", "unknown"))
            else:
                uk = f"{pr.get('subject', 'unknown')}_{pr.get('slice', '1')}"
            rec_to_unit[rec_id] = uk

    unit_asp: dict[str, dict[str, list[float]]] = {}
    for rec_id, aspect_vals in rec_ppr.items():
        uk = rec_to_unit.get(rec_id, rec_id)
        bucket = unit_asp.setdefault(uk, {})
        for asp, val in aspect_vals.items():
            bucket.setdefault(asp, []).append(val)
    for uk, aspect_map in unit_asp.items():
        for asp, vlist in aspect_map.items():
            if asp in agg.ppr_data and vlist:
                agg.ppr_data[asp].append(float(np.mean(vlist)))
                agg.rec_id_order[asp].append(uk)
    return agg


def pp_group_scatter_jitter(n: int, rng=None) -> np.ndarray:
    if n <= 1:
        return np.array([0.0])
    gen = rng if rng is not None else np.random
    return gen.uniform(-0.06, 0.06, size=n)


@dataclass(frozen=True)
class PpGroupScatterPointSpec:
    x: float
    y: float
    rec_id: object


@dataclass(frozen=True)
class PpGroupBarPlotSpec:
    """Legacy bar±SEM spec (tests / fallback). Prefer PpGroupBoxPlotSpec."""

    aspect: str
    axid: str
    bar_x: float
    bar_width: float
    mean_val: float
    sem_val: float
    overlay_x: int
    scatter_points: tuple[PpGroupScatterPointSpec, ...]
    scatter_color: str


@dataclass(frozen=True)
class PpGroupBoxPlotSpec:
    """Group PP summary: box (distribution) + unit dots + n for tick label."""

    aspect: str
    axid: str
    box_x: float
    box_width: float
    values: tuple[float, ...]
    n: int
    tick_label: str
    scatter_points: tuple[PpGroupScatterPointSpec, ...]
    scatter_color: str


@dataclass(frozen=True)
class PpGroupBarStoreItem:
    suffix: str
    rec_id: object | None
    is_overlay: bool


def pp_group_bar_store_items(spec: PpGroupBarPlotSpec) -> tuple[PpGroupBarStoreItem, ...]:
    items: list[PpGroupBarStoreItem] = [
        PpGroupBarStoreItem("bar", None, False),
        PpGroupBarStoreItem("err", None, False),
    ]
    for pt in spec.scatter_points:
        items.append(PpGroupBarStoreItem(f"{pt.rec_id} point", pt.rec_id, False))
    return tuple(items)


def pp_group_box_store_items(spec: PpGroupBoxPlotSpec) -> tuple[PpGroupBarStoreItem, ...]:
    items: list[PpGroupBarStoreItem] = [PpGroupBarStoreItem("box", None, False)]
    for pt in spec.scatter_points:
        items.append(PpGroupBarStoreItem(f"{pt.rec_id} point", pt.rec_id, False))
    return tuple(items)


DEPRECATED_EPSP_OUTPUT_SUFFIXES = (
    ("EPSP amp", "EPSP_amp"),
    ("EPSP amp norm", "EPSP_amp_norm"),
    ("EPSP slope", "EPSP_slope"),
    ("EPSP slope norm", "EPSP_slope_norm"),
)


def deprecated_epsp_output_refresh_labels(rec_name: str) -> tuple[tuple[str, str], ...]:
    return tuple((f"{rec_name} {suffix}", col) for suffix, col in DEPRECATED_EPSP_OUTPUT_SUFFIXES)


def build_pp_group_bar_plot_specs(
    *,
    aggregate: PprLevelAggregate,
    x_pos: float,
    level: str,
    checkbox: dict,
    settings: dict,
    rng=None,
) -> list[PpGroupBarPlotSpec]:
    """Legacy mean±SEM bar specs (kept for tests)."""
    specs: list[PpGroupBarPlotSpec] = []
    overlay_map = pp_overlay_x_map(checkbox)
    for aspect, axid, offset, bar_w in pp_bar_layout(pp_active_aspects(checkbox)):
        vals = aggregate.ppr_data.get(aspect, [])
        if not vals:
            continue
        mean_val, sem_val = mean_sem(vals)
        bar_x = x_pos + offset
        scatter_points: tuple[PpGroupScatterPointSpec, ...] = ()
        scatter_color = measure_rgb(settings, aspect, "white")
        unit_ids = aggregate.rec_id_order.get(aspect, [])
        if unit_ids and len(unit_ids) == len(vals):
            jitter = pp_group_scatter_jitter(len(vals), rng=rng)
            scatter_points = tuple(
                PpGroupScatterPointSpec(bar_x + float(j), float(val), rid)
                for j, val, rid in zip(jitter, vals, unit_ids)
            )
        specs.append(
            PpGroupBarPlotSpec(
                aspect=aspect,
                axid=axid,
                bar_x=bar_x,
                bar_width=bar_w,
                mean_val=mean_val,
                sem_val=sem_val,
                overlay_x=overlay_map.get(aspect, 1),
                scatter_points=scatter_points,
                scatter_color=scatter_color,
            )
        )
    return specs


def build_pp_group_box_plot_specs(
    *,
    aggregate: PprLevelAggregate,
    x_pos: float,
    group_name: str,
    checkbox: dict,
    settings: dict,
    rng=None,
) -> list[PpGroupBoxPlotSpec]:
    """Box + unit dots + n tick label for group PP summary."""
    specs: list[PpGroupBoxPlotSpec] = []
    for aspect, axid, offset, bar_w in pp_bar_layout(pp_active_aspects(checkbox)):
        vals = [float(v) for v in aggregate.ppr_data.get(aspect, []) if np.isfinite(v)]
        if not vals:
            continue
        box_x = x_pos + offset
        unit_ids = list(aggregate.rec_id_order.get(aspect, []))
        # Align unit ids with filtered vals if needed
        if len(unit_ids) != len(aggregate.ppr_data.get(aspect, [])):
            unit_ids = [f"u{i}" for i in range(len(vals))]
        else:
            raw = aggregate.ppr_data.get(aspect, [])
            unit_ids = [uid for uid, v in zip(unit_ids, raw) if np.isfinite(v)]
        jitter = pp_group_scatter_jitter(len(vals), rng=rng)
        scatter_points = tuple(
            PpGroupScatterPointSpec(box_x + float(j), float(val), rid)
            for j, val, rid in zip(jitter, vals, unit_ids)
        )
        n = len(vals)
        aspect_tick = PP_ASPECT_TICK.get(aspect, aspect)
        specs.append(
            PpGroupBoxPlotSpec(
                aspect=aspect,
                axid=axid,
                box_x=box_x,
                box_width=bar_w,
                values=tuple(vals),
                n=n,
                tick_label=f"{group_name} {aspect_tick} (n={n})",
                scatter_points=scatter_points,
                scatter_color=measure_rgb(settings, aspect, "white"),
            )
        )
    return specs


def collect_io_group_scatter_xy(
    dict_rec_labels: dict,
    rec_ids: list,
    variant: str,
) -> tuple[np.ndarray, np.ndarray] | None:
    rec_id_set = set(rec_ids)
    all_x: list[np.ndarray] = []
    all_y: list[np.ndarray] = []
    suffix = f"{variant} IO scatter"
    for key, linedict in dict_rec_labels.items():
        if linedict.get("x_mode") != "io" or linedict.get("rec_ID") not in rec_id_set:
            continue
        if not key.endswith(suffix):
            continue
        scatter = linedict["line"]
        offsets = scatter.get_offsets()
        if len(offsets) == 0:
            continue
        all_x.append(offsets[:, 0])
        all_y.append(offsets[:, 1])
    if not all_x:
        return None
    return np.concatenate(all_x), np.concatenate(all_y)


@dataclass(frozen=True)
class IoGroupScatterPlotSpec:
    label: str
    storage_key: str
    variant: str
    aspect: str
    level: str
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class IoGroupTrendlinePlotSpec:
    label: str
    storage_key: str
    variant: str
    aspect: str
    level: str
    x: np.ndarray
    y: np.ndarray


def build_io_group_plot_specs(
    group_name: str,
    x_vals: np.ndarray,
    y_vals: np.ndarray,
    *,
    y_col_base: str,
    variant: str,
    level: str,
    force_through_zero: bool,
) -> list[IoGroupScatterPlotSpec | IoGroupTrendlinePlotSpec]:
    specs: list[IoGroupScatterPlotSpec | IoGroupTrendlinePlotSpec] = []
    scatter_label = f"{group_name} {variant} IO scatter"
    specs.append(
        IoGroupScatterPlotSpec(
            label=scatter_label,
            storage_key=plot_model.level_storage_key(scatter_label, level),
            variant=variant,
            aspect=y_col_base,
            level=level,
            x=x_vals,
            y=y_vals,
        )
    )
    reg = compute_io_regression(x_vals, y_vals, force_through_zero=force_through_zero)
    if reg is not None:
        trend_label = f"{group_name} {variant} IO trendline"
        specs.append(
            IoGroupTrendlinePlotSpec(
                label=trend_label,
                storage_key=plot_model.level_storage_key(trend_label, level),
                variant=variant,
                aspect=y_col_base,
                level=level,
                x=reg.x_line,
                y=reg.y_line,
            )
        )
    return specs


def pp_overlay_x_map(checkbox: dict) -> dict[str, int]:
    """Enabled aspects → stable x slot (1=amp, 2=slope, 3=volley amp, 4=volley slope).

    Fixed slots so volley never lands on the EPSP amp tick when both are shown.
    Volley slots are omitted under Relative mode (same rule as pp_active_aspects).
    """
    norm = bool(checkbox.get("norm_EPSP", False))
    return {
        asp: x
        for asp, x in PP_ASPECT_X.items()
        if checkbox.get(asp, True) and not (norm and asp in ("volley_amp", "volley_slope"))
    }


def pp_group_tick_from_bar(x_left: float, bar_width: float) -> float:
    """Center x of a bar/box given left edge and width."""
    return float(x_left) + float(bar_width) / 2.0


def pp_has_visible_rec_ppr(dict_rec_show: dict) -> bool:
    for key in dict_rec_show:
        if "PPR" in key and "marker" not in key:
            return True
    return False


def collect_pp_group_bar_patch_specs(
    dict_group_show: dict,
    current_level: str,
    group_display_name,
    *,
    axis: str | None = None,
) -> list[tuple[float, float, str]]:
    """(x_left, width, tick_label) from visible PP group containers.

    Supports box metadata (pp_box_*) and legacy bar patches.
    If axis is set (ax1/ax2), only that panel's boxes are included.
    """
    specs: list[tuple[float, float, str]] = []
    for key, val in dict_group_show.items():
        if "PPR" not in key or val.get("is_overlay"):
            continue
        if "point" in key:
            continue
        level = val.get("level")
        if level is not None and level != current_level:
            continue
        if axis is not None and val.get("axis") not in (None, axis):
            continue
        # Prefer stored box/bar geometry (works for boxplot PathPatch + export)
        if val.get("pp_box_x") is not None:
            try:
                x = float(val["pp_box_x"])
                w = float(val.get("pp_box_width", 0.5))
                tick_label = val.get("pp_tick_label") or group_display_name(key.split(" PPR")[0])
                specs.append((x - w / 2.0, w, tick_label))
                continue
            except Exception:
                pass
        line = val.get("line")
        if line is None or not hasattr(line, "patches"):
            continue
        try:
            patch = line.patches[0]
            base_name = key.split(" PPR")[0]
            specs.append((patch.get_x(), patch.get_width(), group_display_name(base_name)))
        except Exception:
            pass
    return specs


@dataclass(frozen=True)
class PpGraphRefreshXAxisPlan:
    ticks: tuple[float, ...]
    ticklabels: tuple[str, ...]
    ax1_xlabel: str | None
    ax2_xlabel: str | None
    hide_all: bool
    labels_only: bool


def build_pp_graph_refresh_xaxis_plan(
    bar_specs: list[tuple[float, float, str]],
    checkbox: dict,
    *,
    pp_has_recs: bool,
) -> PpGraphRefreshXAxisPlan:
    """PP output x-tick/label plan for graphRefresh (no matplotlib)."""
    x_ticks, x_ticklabels = pp_group_tick_label_map(bar_specs)
    if x_ticks:
        return PpGraphRefreshXAxisPlan(
            ticks=tuple(x_ticks),
            ticklabels=tuple(x_ticklabels),
            ax1_xlabel="",
            ax2_xlabel="",
            hide_all=False,
            labels_only=True,
        )
    if pp_has_recs:
        rec_ticks, rec_labels = pp_recording_view_ticks(checkbox)
        if not rec_ticks:
            return PpGraphRefreshXAxisPlan((), (), "No aspect selected", None, hide_all=True, labels_only=False)
        return PpGraphRefreshXAxisPlan(
            ticks=tuple(rec_ticks),
            ticklabels=tuple(rec_labels),
            ax1_xlabel="",
            ax2_xlabel="",
            hide_all=False,
            labels_only=True,
        )
    return PpGraphRefreshXAxisPlan((), (), None, None, hide_all=True, labels_only=False)


def pp_group_tick_label_map(bar_specs: list[tuple[float, float, str]]) -> tuple[list[float], list[str]]:
    """Build sorted PP xticks from (x_left, width, display_label); one tick per box center."""
    items: list[tuple[float, str]] = []
    seen: set[float] = set()
    for x_left, width, label in bar_specs:
        center = round(pp_group_tick_from_bar(x_left, width), 4)
        if center in seen:
            # Keep distinct labels: nudge key slightly if collision (multi-aspect)
            center = center + 1e-3 * len(items)
        seen.add(center)
        items.append((center, label))
    items.sort(key=lambda t: t[0])
    return [c for c, _ in items], [lab for _, lab in items]


def pp_group_xlim_from_ticks(ticks: list[float] | tuple[float, ...], pad: float = 0.6) -> tuple[float, float] | None:
    """X limits so every box/tick fits with side padding."""
    if not ticks:
        return None
    tmin, tmax = float(min(ticks)), float(max(ticks))
    if tmin == tmax:
        return (tmin - pad, tmax + pad)
    return (tmin - pad, tmax + pad)


def pp_recording_view_ticks(checkbox: dict) -> tuple[list[int], list[str]]:
    """X ticks for recording PP view — positions must match pp_overlay_x_map (sequential)."""
    x_map = pp_overlay_x_map(checkbox)
    ticks: list[int] = []
    labels: list[str] = []
    for asp, _axid in PP_ASPECT_AXES:
        if asp not in x_map:
            continue
        ticks.append(x_map[asp])
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
        ("EPSP_amp", "ax1", measure_rgb(settings, "EPSP_amp", "blue")),
        ("EPSP_slope", "ax2", measure_rgb(settings, "EPSP_slope", (0.45, 0.55, 0.95))),
        ("volley_amp", "ax1", measure_rgb(settings, "volley_amp", "green")),
        ("volley_slope", "ax2", measure_rgb(settings, "volley_slope", (0.35, 0.7, 0.35))),
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
    """One PPR series per aspect present in data at its fixed x slot.

    Checkbox only affects which series are visible later (update_show); positions
    stay fixed so enabling volley never places it on the EPSP amp tick.
    """
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
                x_val=PP_ASPECT_X[aspect],
                n_points=len(v1),
            )
        )
    return specs


@dataclass(frozen=True)
class PpRecordingPlotSpec:
    label: str
    aspect: str
    axid: str
    color: str
    variant: str
    x: np.ndarray
    y: np.ndarray


def build_pp_recording_plot_specs(
    dfoutput: pd.DataFrame,
    label: str,
    checkbox: dict,
    settings: dict,
) -> list[PpRecordingPlotSpec]:
    """PP PPR scatter specs for addRow (raw + norm variants per aspect)."""
    out_sweeps = dfoutput[dfoutput["sweep"].notna()]
    out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
    out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
    common_sweeps = out1.index.intersection(out2.index).dropna()
    if common_sweeps.empty:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base_specs = pp_recording_ppr_specs(
            out1.loc[common_sweeps],
            out2.loc[common_sweeps],
            checkbox,
            settings,
        )
    plot_specs: list[PpRecordingPlotSpec] = []
    for base in base_specs:
        for variant in ("raw", "norm"):
            plot_specs.append(
                PpRecordingPlotSpec(
                    label=f"{label} PPR {base.aspect} {variant}",
                    aspect=base.aspect,
                    axid=base.axid,
                    color=base.color,
                    variant=variant,
                    x=np.full(base.n_points, base.x_val),
                    y=base.ppr,
                )
            )
    return plot_specs


def out_line_xy_from_df(
    dfoutput: pd.DataFrame,
    stim_num: int,
    column: str,
    x_mode: str = "sweep",
) -> tuple[np.ndarray, np.ndarray] | None:
    """Sweep/stim-mode output line x/y for updateOutLineFromDf."""
    df_stim = dfoutput[dfoutput["stim"] == stim_num]
    if df_stim.empty or column not in df_stim.columns:
        return None
    x_col = x_mode if x_mode in df_stim.columns else "sweep"
    return df_stim[x_col].values, df_stim[column].values


def build_ppr_overlay_refresh_specs(
    rec_label: str,
    dfoutput: pd.DataFrame,
    aspect: str,
    checkbox: dict,
    settings: dict,
    existing_labels: frozenset[str],
) -> list[PpRecordingPlotSpec]:
    """PP PPR overlay refresh specs for updateOutLineFromDf when label is missing."""
    out_sweeps = dfoutput[dfoutput["sweep"].notna()]
    out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
    out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
    common_sweeps = out1.index.intersection(out2.index).dropna()
    if common_sweeps.empty:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base_specs = pp_recording_ppr_specs(
            out1.loc[common_sweeps],
            out2.loc[common_sweeps],
            checkbox,
            settings,
        )
    specs: list[PpRecordingPlotSpec] = []
    for base in base_specs:
        if base.aspect != aspect:
            continue
        for variant in ("raw", "norm"):
            label = f"{rec_label} PPR {aspect} {variant}"
            if label not in existing_labels:
                continue
            specs.append(
                PpRecordingPlotSpec(
                    label=label,
                    aspect=aspect,
                    axid=base.axid,
                    color=base.color,
                    variant=variant,
                    x=np.full(base.n_points, base.x_val),
                    y=base.ppr,
                )
            )
    return specs


@dataclass(frozen=True)
class StimAggregatePlotSpec:
    line_label: str
    shade_label: str | None
    axid: str
    aspect: str
    variant: str
    color: str
    x: np.ndarray
    y: np.ndarray
    sem: np.ndarray | None


def build_stim_aggregate_plot_specs(
    dfoutput: pd.DataFrame,
    label: str,
    settings: dict,
) -> list[StimAggregatePlotSpec]:
    """Stim-mode aggregate line + SEM shade specs for addRow."""
    out_stim = dfoutput[dfoutput["sweep"].isna()]
    if out_stim.empty:
        return []
    df_sweeps = dfoutput[dfoutput["sweep"].notna()]
    df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)
    stims = out_stim["stim"].values
    specs: list[StimAggregatePlotSpec] = []
    for suffix, axid, col, color, variant in stim_aggregate_line_configs(settings):
        if col not in out_stim.columns:
            continue
        aspect = col.replace("_norm", "")
        sem_vals = stim_aggregate_sem(df_sem, out_stim, col)
        specs.append(
            StimAggregatePlotSpec(
                line_label=f"{label} {suffix}",
                shade_label=f"{label} {suffix} shade" if sem_vals is not None else None,
                axid=axid,
                aspect=aspect,
                variant=variant,
                color=color,
                x=stims,
                y=out_stim[col].values,
                sem=sem_vals,
            )
        )
    return specs


def stim_aggregate_line_configs(settings: dict) -> list[tuple[str, str, str, str, str]]:
    return [
        ("EPSP amp", "ax1", "EPSP_amp", measure_rgb(settings, "EPSP_amp"), "raw"),
        ("EPSP amp norm", "ax1", "EPSP_amp_norm", measure_rgb(settings, "EPSP_amp"), "norm"),
        ("EPSP slope", "ax2", "EPSP_slope", measure_rgb(settings, "EPSP_slope"), "raw"),
        ("EPSP slope norm", "ax2", "EPSP_slope_norm", measure_rgb(settings, "EPSP_slope"), "norm"),
        ("volley amp", "ax1", "volley_amp", measure_rgb(settings, "volley_amp"), "raw"),
        ("volley slope", "ax2", "volley_slope", measure_rgb(settings, "volley_slope"), "raw"),
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
class IoScatterRefreshSpec:
    label: str
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class IoTrendlineRefreshSpec:
    label: str
    x: np.ndarray
    y: np.ndarray


IoRefreshSpec = IoScatterRefreshSpec | IoTrendlineRefreshSpec


def build_io_refresh_specs_for_rec(
    rec_name: str,
    dict_rec_labels: dict,
    dfoutput: pd.DataFrame,
    io_input: str,
    io_output: str,
    *,
    force_through_zero: bool,
) -> list[IoRefreshSpec]:
    """IO scatter/trendline refresh data for updateStimLines (no matplotlib artists)."""
    specs: list[IoRefreshSpec] = []
    for key, linedict in dict_rec_labels.items():
        if not key.startswith(rec_name):
            continue
        variant = linedict.get("variant", "raw")
        if key.endswith(" IO scatter") and linedict.get("x_mode") == "io":
            xy = io_scatter_xy(dfoutput, io_input, io_output, variant=variant)
            if xy is not None:
                specs.append(IoScatterRefreshSpec(label=key, x=xy[0], y=xy[1]))
        elif key.endswith(" IO trendline") and linedict.get("x_mode") == "io":
            line_xy = io_trendline_xy(
                dfoutput,
                io_input,
                io_output,
                variant=variant,
                force_through_zero=force_through_zero,
            )
            if line_xy is not None:
                specs.append(IoTrendlineRefreshSpec(label=key, x=line_xy[0], y=line_xy[1]))
    return specs


@dataclass(frozen=True)
class StimAggregateRefreshSpec:
    line_label: str
    shade_label: str | None
    x: np.ndarray
    y: np.ndarray
    sem: np.ndarray | None
    axid: str
    aspect: str
    variant: str
    color_setting_key: str


def build_stim_aggregate_refresh_specs(
    rec_name: str,
    dfoutput: pd.DataFrame,
    settings: dict,
    existing_labels: frozenset[str],
) -> list[StimAggregateRefreshSpec]:
    """Stim-mode aggregate line + SEM refresh data for updateStimLines."""
    out_stim = dfoutput[dfoutput["sweep"].isna()]
    if out_stim.empty:
        return []
    df_sweeps = dfoutput[dfoutput["sweep"].notna()]
    df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)
    stims = out_stim["stim"].values
    specs: list[StimAggregateRefreshSpec] = []
    for suffix, axid, col, _color, variant in stim_aggregate_line_configs(settings):
        line_label = f"{rec_name} {suffix}"
        if line_label not in existing_labels:
            continue
        if col not in out_stim.columns:
            continue
        aspect = col.replace("_norm", "")
        sem_vals = stim_aggregate_sem(df_sem, out_stim, col)
        shade_label = f"{line_label} shade"
        specs.append(
            StimAggregateRefreshSpec(
                line_label=line_label,
                shade_label=shade_label if sem_vals is not None and shade_label in existing_labels else None,
                x=stims,
                y=out_stim[col].values,
                sem=sem_vals,
                axid=axid,
                aspect=aspect,
                variant=variant,
                color_setting_key=f"rgb_{aspect}",
            )
        )
    return specs


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