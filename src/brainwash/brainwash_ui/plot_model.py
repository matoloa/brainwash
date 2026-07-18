"""Pure plot descriptors (no matplotlib/Qt). UIplot view layer renders these."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestMarkerSpec:
    x: float
    y_frac: float
    va: str
    label: str
    color: str
    axis: str
    storage_pcol: str


def p_value_color_alpha(p: float) -> tuple[tuple[float, float, float], float]:
    """RGB color and alpha for heatmap significance dots (p <= 0.05 only)."""
    alpha = 0.5
    if p < 0.005:
        color = (1.0, 0.0, 0.0)
    else:
        t = (0.05 - p) / 0.045
        g = 1.0 - t
        color = (1.0, g, 0.0)
    return color, alpha


def significance_label(val) -> str:
    if isinstance(val, (int, float)) and val == val and val < 0.001:
        return "***"
    if isinstance(val, (int, float)) and val == val and val < 0.01:
        return "**"
    if isinstance(val, (int, float)) and val == val and val < 0.05:
        return "*"
    return "ns"


def marker_text_color(is_sig: bool, *, dark: bool) -> str:
    if is_sig:
        return "white" if dark else "black"
    return "#aaaaaa" if dark else "#555555"


def effective_test_pvalue(res: dict, pcol: str):
    qcol = "q_" + pcol[2:]
    pval = res.get(pcol)
    qval = res.get(qcol)
    if isinstance(qval, (int, float)) and qval == qval:
        return qval
    return pval


def marker_x_for_results(results: list, *, variant: str) -> float | None:
    if not results:
        return None
    res0 = results[0]
    sweeps = res0.get("sweeps", []) or []
    if not sweeps:
        return None
    try:
        x = float(sum(sweeps) / len(sweeps))
    except Exception:
        return None
    if variant in ("paired", "one-sample"):
        # Prefer sweeps2 on the same result (unit-aligned paired contrast); fall back to 2nd row.
        sweeps2 = res0.get("sweeps2") or []
        if not sweeps2 and len(results) >= 2:
            sweeps2 = results[1].get("sweeps", []) or []
        if sweeps2:
            try:
                x2 = float(sum(sweeps2) / len(sweeps2))
                x = (x + x2) / 2.0
            except Exception:
                pass
    return x


def aspect_placements(res: dict, *, amp_view: bool, slope_view: bool) -> list[tuple[str, str, float, str]]:
    """Return (pcol, axis_id, y_frac, va) for one result row."""
    amp_pcols = [k for k in res.keys() if k.startswith("p_") and "amp" in k]
    slope_pcols = [k for k in res.keys() if k.startswith("p_") and "slope" in k]
    placements: list[tuple[str, str, float, str]] = []
    if amp_view and slope_view:
        for pcol in amp_pcols:
            placements.append((pcol, "ax1", 0.94, "top"))
        for pcol in slope_pcols:
            placements.append((pcol, "ax2", 0.06, "bottom"))
    elif amp_view:
        for pcol in amp_pcols:
            placements.append((pcol, "ax1", 0.94, "top"))
    elif slope_view:
        for pcol in slope_pcols:
            placements.append((pcol, "ax2", 0.94, "top"))
    return placements


def build_test_marker_specs(
    results: list | None,
    *,
    test_type: str,
    t_variant: str,
    wilcox_variant: str,
    amp_view: bool,
    slope_view: bool,
    dark: bool,
) -> list[TestMarkerSpec]:
    if not results:
        return []
    # t-test / Wilcoxon variants only; ANOVA/Friedman/Cluster are not "paired" markers.
    if test_type == "Wilcoxon":
        variant = wilcox_variant
    elif test_type == "t-test":
        variant = t_variant
    else:
        variant = "unpaired"
    # Paired / one-sample: one marker (midpoint of the two test-set windows).
    is_single = variant in ("paired", "one-sample")
    specs: list[TestMarkerSpec] = []

    for idx, res in enumerate(results):
        if is_single and idx != 0:
            continue
        x = marker_x_for_results(results if is_single else [res], variant=variant if is_single else "unpaired")
        if x is None:
            continue
        for pcol, axis, y_frac, va in aspect_placements(res, amp_view=amp_view, slope_view=slope_view):
            val = effective_test_pvalue(res, pcol)
            label = significance_label(val)
            color = marker_text_color(label != "ns", dark=dark)
            specs.append(
                TestMarkerSpec(
                    x=x,
                    y_frac=y_frac,
                    va=va,
                    label=label,
                    color=color,
                    axis=axis,
                    storage_pcol=pcol,
                )
            )
    return specs


@dataclass(frozen=True)
class GroupLineVariantSpec:
    display_label: str
    storage_key: str
    variant: str


def group_line_display_labels(group_name: str, aspect: str) -> tuple[str, str]:
    str_aspect = aspect.replace("_", " ")
    return f"{group_name} {str_aspect} mean", f"{group_name} {str_aspect} norm"


def build_group_line_specs(
    group_name: str,
    aspect: str,
    level: str,
    *,
    include_norm: bool,
) -> list[GroupLineVariantSpec]:
    mean_label, norm_label = group_line_display_labels(group_name, aspect)
    specs = [
        GroupLineVariantSpec(
            display_label=mean_label,
            storage_key=level_storage_key(mean_label, level),
            variant="raw",
        )
    ]
    if include_norm:
        specs.append(
            GroupLineVariantSpec(
                display_label=norm_label,
                storage_key=level_storage_key(norm_label, level),
                variant="norm",
            )
        )
    return specs


def rec_label_entry(
    *,
    rec_ID,
    aspect=None,
    variant: str = "raw",
    stim=None,
    axis: str,
    x_mode=None,
) -> dict:
    """Shared dict_rec_labels metadata (caller adds ``line`` artist)."""
    return {
        "rec_ID": rec_ID,
        "aspect": aspect,
        "variant": variant,
        "stim": stim,
        "axis": axis,
        "x_mode": x_mode,
    }


def amp_width_marker_entry(
    *,
    rec_ID,
    aspect=None,
    variant: str = "raw",
    stim=None,
    axis: str,
    x_mode=None,
    is_zero_width: bool,
) -> dict:
    """Amp-width x/y marker metadata (extends rec_label_entry)."""
    return {
        **rec_label_entry(
            rec_ID=rec_ID,
            aspect=aspect,
            variant=variant,
            stim=stim,
            axis=axis,
            x_mode=x_mode,
        ),
        "is_zero_width": is_zero_width,
    }


def reference_hline_label_entry(*, axis: str, variant=None) -> dict:
    """Reference hline metadata for graphRefresh (events zero, output 100%)."""
    return {
        "rec_ID": None,
        "stim": None,
        "variant": variant,
        "axis": axis,
    }


def io_rec_label_entry(
    *,
    rec_ID,
    aspect: str,
    variant: str,
    axis: str = "ax1",
) -> dict:
    return rec_label_entry(
        rec_ID=rec_ID,
        aspect=aspect,
        variant=variant,
        stim=None,
        axis=axis,
        x_mode="io",
    )


def io_group_label_entry(
    *,
    group_ID,
    aspect: str,
    variant: str,
    axis: str,
    level: str,
) -> dict:
    return {
        "group_ID": group_ID,
        "aspect": aspect,
        "variant": variant,
        "stim": None,
        "axis": axis,
        "x_mode": "io",
        "level": level,
    }


def pp_group_bar_label_entry(
    *,
    group_ID,
    aspect: str,
    level: str,
    axis: str,
    rec_ID=None,
    is_overlay: bool = False,
) -> dict:
    entry = {
        "group_ID": group_ID,
        "aspect": aspect,
        "variant": "raw",
        "stim": None,
        "axis": axis,
        "x_mode": "sweep",
        "is_container": True,
        "is_overlay": is_overlay,
        "level": level,
    }
    if rec_ID is not None:
        entry["rec_ID"] = rec_ID
    return entry


def group_line_label_entry(
    *,
    group_ID,
    aspect: str,
    variant: str,
    axis: str,
    level: str,
) -> dict:
    return {
        "group_ID": group_ID,
        "stim": None,
        "aspect": aspect,
        "variant": variant,
        "axis": axis,
        "x_mode": "sweep",
        "level": level,
    }


def level_storage_key(base_label: str, level: str | None) -> str:
    if not level or level == "recording":
        return base_label
    return f"{base_label}_{level}"


def display_label_from_key(key: str) -> str:
    for suf in ("_subject", "_slice", "_recording"):
        if key.endswith(suf):
            return key[: -len(suf)]
    return key


def _is_io_trendline_legend_key(key: str) -> bool:
    """Trendlines share group color; omit from legend (scatter entry is enough)."""
    return " IO trendline" in str(key)


def output_axis_legend_map(
    dd_recs: dict,
    dd_group_show: dict,
    *,
    axid: str,
    current_level: str,
    include_groups: bool,
) -> dict[str, object]:
    """Legend label → artist line for one output axis (graphRefresh)."""
    recs_on_axis = {
        key: value
        for key, value in dd_recs.items()
        if value["axis"] == axid and not key.endswith(" marker") and not _is_io_trendline_legend_key(key)
    }
    axis_legend = {key: value["line"] for key, value in recs_on_axis.items()}
    if include_groups:
        for key, value in dd_group_show.items():
            if value["axis"] != axid:
                continue
            if _is_io_trendline_legend_key(key):
                continue
            level = value.get("level")
            if level is not None and level != current_level:
                continue
            display_key = display_label_from_key(key)
            if _is_io_trendline_legend_key(display_key):
                continue
            axis_legend[display_key] = value["line"]
    return axis_legend


def output_legend_locations(*, experiment_type: str, slope_only: bool) -> tuple[str, str]:
    """Legend anchor per output axis (ax1, ax2)."""
    if experiment_type == "io":
        return "lower right", "lower right"
    if slope_only:
        return "upper right", "upper right"
    return "upper right", "lower right"


def heatmap_axis_for_column(col: str) -> str | None:
    if "amp" in col:
        return "ax1"
    if "slope" in col:
        return "ax2"
    return None


def heatmap_y_fraction(col: str) -> float:
    return 0.92 if "amp" in col else 0.08


def significant_heatmap_points(sweeps, ps) -> list[tuple[float, float]]:
    """Sweep index and p-value pairs with finite p <= 0.05."""
    out: list[tuple[float, float]] = []
    for x, p in zip(sweeps, ps):
        if isinstance(p, (int, float)) and p == p and p <= 0.05:
            out.append((float(x), float(p)))
    return out


def output_axis_y_visibility(*, amp_view: bool, slope_view: bool) -> tuple[bool, bool]:
    if not amp_view and not slope_view:
        return False, False
    return amp_view, slope_view


def slope_yaxis_on_left(*, slope_only: bool) -> bool:
    return slope_only


@dataclass(frozen=True)
class OneAxisLeftPlan:
    ax1_yaxis_visible: bool
    ax2_yaxis_visible: bool
    ax2_yaxis_on_left: bool


def build_one_axis_left_plan(*, amp_view: bool, slope_view: bool, slope_only: bool) -> OneAxisLeftPlan:
    show_amp, show_slope = output_axis_y_visibility(amp_view=amp_view, slope_view=slope_view)
    return OneAxisLeftPlan(
        ax1_yaxis_visible=show_amp,
        ax2_yaxis_visible=show_slope,
        ax2_yaxis_on_left=slope_yaxis_on_left(slope_only=slope_only),
    )


@dataclass(frozen=True)
class OutputAxisLabels:
    ax1_ylabel: str
    ax2_ylabel: str


def output_axis_ylabels(*, experiment_type: str, io_output: str, norm_epsP: bool) -> OutputAxisLabels:
    if experiment_type == "io":
        if "slope" in io_output.lower():
            ax1 = "EPSP Slope %" if norm_epsP else "EPSP Slope (mV/ms)"
        else:
            ax1 = "EPSP Amplitude %" if norm_epsP else "EPSP Amplitude (mV)"
        return OutputAxisLabels(ax1, "")
    if experiment_type == "PP":
        # Ratio stim2/stim1 (not percent); reference grid at 1, 2, 3
        return OutputAxisLabels("PPR Amp", "PPR Slope")
    if norm_epsP:
        return OutputAxisLabels("Amplitude %", "Slope %")
    return OutputAxisLabels("Amplitude (mV)", "Slope (mV/ms)")


def pp_reference_grid_y_values() -> tuple[float, float, float]:
    return (1.0, 2.0, 3.0)


EVENT_AXIS_YLABEL = "Voltage (mV)"
EVENT_AXIS_XLABEL = "Time (ms)"


@dataclass(frozen=True)
class OutputAxisFormatMode:
    use_g_formatters: bool
    time_x_formatter_on_ax2: bool
    show_output_x_tick_marks: bool


@dataclass(frozen=True)
class PlotStyleColors:
    mpl_style: str
    figure_facecolor: str
    axes_facecolor: str
    label_color: str
    tick_color: str


def plot_style_colors(*, dark: bool) -> PlotStyleColors:
    if dark:
        return PlotStyleColors("dark_background", "#333333", "#333333", "white", "white")
    return PlotStyleColors("default", "white", "white", "black", "black")


def output_axis_format_mode(experiment_type: str) -> OutputAxisFormatMode:
    if experiment_type == "io":
        return OutputAxisFormatMode(use_g_formatters=True, time_x_formatter_on_ax2=False, show_output_x_tick_marks=False)
    if experiment_type == "PP":
        return OutputAxisFormatMode(use_g_formatters=True, time_x_formatter_on_ax2=False, show_output_x_tick_marks=False)
    return OutputAxisFormatMode(use_g_formatters=True, time_x_formatter_on_ax2=True, show_output_x_tick_marks=True)