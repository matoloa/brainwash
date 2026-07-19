from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np

from brainwash_ui import plot_drag, plot_model, plot_series


@dataclass
class JournalTemplate:
    name: str
    # Figure dimensions in mm (converted to inches for matplotlib)
    width_mm: float
    height_mm: float
    # Font
    font_family: str = "sans-serif"  # Arial not available on Linux; sans-serif is reliable cross-platform
    font_size_axis_label: float = 7.0
    font_size_tick_label: float = 6.0
    font_size_legend: float = 6.0
    # Line widths in points
    linewidth_data: float = 0.75
    linewidth_axes: float = 0.5
    linewidth_error: float = 0.5
    # DPI for raster outputs
    dpi: int = 600
    # Which panels to include
    panels: list[Literal["event", "amp", "slope", "mean"]] = field(default_factory=lambda: ["event", "amp", "slope"])
    # Layout: "vertical" (stacked) or "horizontal" (side by side)
    layout: Literal["vertical", "horizontal"] = "vertical"


JOURNAL_TEMPLATES: dict[str, JournalTemplate] = {
    "jneurosci_1col": JournalTemplate(name="JNeurosci (1 col)", width_mm=85, height_mm=60, font_family="sans-serif"),
    "jneurosci_2col": JournalTemplate(name="JNeurosci (2 col)", width_mm=174, height_mm=120, font_family="sans-serif"),
    "jphysiol_1col": JournalTemplate(name="JPhysiol (1 col)", width_mm=85, height_mm=65, font_family="sans-serif"),
    "jphysiol_2col": JournalTemplate(name="JPhysiol (2 col)", width_mm=174, height_mm=130, font_family="sans-serif"),
    "nature_1col": JournalTemplate(name="Nature (1 col)", width_mm=89, height_mm=65, font_family="sans-serif"),
    "nature_2col": JournalTemplate(name="Nature (2 col)", width_mm=183, height_mm=130, font_family="sans-serif"),
}

DEFAULT_JOURNAL_EXPORT = "jneurosci"


def _export_artist_color(artist, default="black"):
    """Face/line color from a matplotlib artist (PathPatch box, bar, line, scatter)."""
    if artist is None:
        return default
    if hasattr(artist, "patches") and getattr(artist, "patches", None):
        try:
            return artist.patches[0].get_facecolor()
        except Exception:
            pass
    if hasattr(artist, "get_facecolor"):
        try:
            c = artist.get_facecolor()
            if c is not None:
                return c
        except Exception:
            pass
    if hasattr(artist, "get_facecolors"):
        try:
            fcs = artist.get_facecolors()
            if len(fcs):
                return fcs[0]
        except Exception:
            pass
    if hasattr(artist, "get_color"):
        try:
            return artist.get_color()
        except Exception:
            pass
    return default


def resolve_journal_export_key(settings_or_key) -> str:
    """Return a valid journal palette key (e.g. jneurosci).

    Project settings historically defaulted journal_export to None; dict.get(key, default)
    does not substitute when the key exists with value None → template 'None_1col'.
    """
    if isinstance(settings_or_key, dict):
        key = settings_or_key.get("journal_export", DEFAULT_JOURNAL_EXPORT)
    else:
        key = settings_or_key
    if key is None or key == "" or str(key).lower() in ("none", "null"):
        return DEFAULT_JOURNAL_EXPORT
    key = str(key)
    # Accept full template keys by stripping _1col/_2col
    if key in JOURNAL_TEMPLATES:
        return key.rsplit("_", 1)[0]
    known = {k.rsplit("_", 1)[0] for k in JOURNAL_TEMPLATES}
    if key in known:
        return key
    return DEFAULT_JOURNAL_EXPORT


def resolve_export_template_key(settings_or_journal, width: str = "1col") -> str:
    """Build a JOURNAL_TEMPLATES key like 'jneurosci_1col'."""
    journal = resolve_journal_export_key(settings_or_journal)
    w = width if width in ("1col", "2col") else "1col"
    key = f"{journal}_{w}"
    if key not in JOURNAL_TEMPLATES:
        key = f"{DEFAULT_JOURNAL_EXPORT}_{w}"
    return key


# Fractional y-span headroom above data for export * markers + brackets.
# Live time/sweep zoom uses pad≈0.2; export uses slightly more for bracket offset.
EXPORT_MARKER_TOP_PAD = 0.25


def _expand_export_ylim_for_markers(ax: matplotlib.axes.Axes, top_pad: float = EXPORT_MARKER_TOP_PAD) -> None:
    """Raise the top of ylim by a fraction of the current span (keep bottom).

    Markers sit near y_frac≈0.94; without headroom they sit on the top of SEM/data.
    Call after data are drawn and before _add_significance_markers.
    """
    ymin, ymax = ax.get_ylim()
    if not (np.isfinite(ymin) and np.isfinite(ymax)):
        return
    span = float(ymax) - float(ymin)
    if span <= 0:
        return
    ax.set_ylim(ymin, ymax + top_pad * span)


def _export_x_mode(uistate) -> str | None:
    """Best-effort x_axis mode from uistate (property or experiment_type)."""
    x_mode = getattr(uistate, "x_axis", None)
    if isinstance(x_mode, str) and x_mode:
        return x_mode
    exp = getattr(getattr(uistate, "experiment", None), "experiment_type", None)
    if exp in ("time", "timestamp"):
        return "time"
    if exp == "sweep":
        return "sweep"
    if exp == "train":
        return "stim"
    if exp == "io":
        return "io"
    return None


def _export_time_x_scale(uistate) -> float | None:
    """Factor mapping sweep-index → display time unit (s|min|h), or None if not time mode.

    Live axes keep data in sweep index and use TimeModeLocator + FuncFormatter.
    Export is more reliable if data are converted into display units so plain
    AutoLocator ticks match the xlabel (avoids raw '600' under Time (min)).
    """
    if _export_x_mode(uistate) != "time":
        return None
    p = getattr(uistate, "plot", None)
    if p is None:
        return None
    try:
        hz = float(getattr(p, "_time_sweep_hz", 1.0))
        div = float(getattr(p, "_time_divisor", 1.0))
        bin_s = float(getattr(p, "_time_bin_size", 1.0))
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(hz) and hz > 0 and np.isfinite(div) and div > 0 and np.isfinite(bin_s) and bin_s > 0):
        return None
    return bin_s / (hz * div)


def _scale_export_x(x, x_scale: float | None):
    """Apply sweep→display scale; pass through when x_scale is None."""
    if x_scale is None:
        return x
    arr = np.asarray(x, dtype=float)
    return arr * x_scale


def _configure_export_xaxis(ax: matplotlib.axes.Axes, uistate, *, x_scale: float | None = None) -> None:
    """Label + xlim for export. When x_scale is set, data/xlim are already in display units."""
    if hasattr(uistate, "x_axis_xlabel"):
        ax.set_xlabel(uistate.x_axis_xlabel())
    else:
        ax.set_xlabel("Time")

    # Prefer live output xlim (sweep index) when set; convert if data were scaled.
    try:
        zoom = getattr(getattr(uistate, "project", None), "zoom", None) or {}
        ox = zoom.get("output_xlim")
        if ox is not None and len(ox) == 2 and ox[1] is not None and np.isfinite(ox[0]) and np.isfinite(ox[1]):
            x0, x1 = float(ox[0]), float(ox[1])
            if x_scale is not None:
                x0, x1 = x0 * x_scale, x1 * x_scale
            ax.set_xlim(x0, x1)
    except Exception:
        pass

    # Data already in display units (or sweep/stim raw): use plain ticks.
    from matplotlib.ticker import AutoLocator, FuncFormatter, ScalarFormatter

    ax.xaxis.set_major_locator(AutoLocator())
    if x_scale is not None:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}"))
    elif _export_x_mode(uistate) == "time" and hasattr(uistate, "x_axis_formatter"):
        # Fallback if caller did not scale data
        ax.xaxis.set_major_locator(uistate.x_axis_locator())
        ax.xaxis.set_major_formatter(uistate.x_axis_formatter())
    elif _export_x_mode(uistate) == "stim" and hasattr(uistate, "x_axis_locator"):
        ax.xaxis.set_major_locator(uistate.x_axis_locator())
    else:
        ax.xaxis.set_major_formatter(ScalarFormatter())


JOURNAL_COLOR_PALETTES: dict[str, list[str]] = {
    "jneurosci": [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
    ],
    "jphysiol": [
        "#003366",
        "#0066CC",
        "#00CCFF",
        "#66CC99",
        "#339966",
        "#99CC00",
        "#CC9900",
        "#FF6600",
        "#990000",
    ],
    "nature": [
        "#999999",
        "#E69F00",
        "#56B4E9",
        "#009E73",
        "#F0E442",
        "#0072B2",
        "#D55E00",
        "#CC79A7",
    ],
}


def _add_significance_markers(
    ax: matplotlib.axes.Axes,
    panel: str,
    template: JournalTemplate,
    results: list[dict],
    is_pp_mode: bool,
    is_io_mode: bool,
    io_output: Optional[str],
    amp_view: bool,
    slope_view: bool,
    dark: bool,
    variant: str,
    fdr: bool,
    label_override: str | None = None,  # temporary for debugging p-value string in marker (Phase 0)
    x_scale: float | None = None,  # sweep-index → display units (time export)
) -> None:
    """
    Draw significance markers (*, **, ***, ns) on an export Axes.
    Mirrors the logic in ui_plot.py::show_test_markers but operates on a plain Axes
    and JournalTemplate (no live interactive axes or blended transforms).
    """
    if not results:
        return

    # Paired/one-sample: one marker centered between the two test-set windows
    is_single_marker = variant in ("paired", "one-sample")

    # Sweep-range bracket (journal convention): horizontal line + short vertical ticks
    # at min(sweeps) to max(sweeps). Sits ~1-2 pt below marker. Uses linewidth_axes.
    _xs = float(x_scale) if x_scale is not None else 1.0

    for idx, res in enumerate(results):
        sweeps = res.get("sweeps", []) or []
        if not sweeps:
            continue
        try:
            x = float(np.mean(sweeps)) * _xs
        except Exception:
            continue

        # Paired/one-sample: single centered marker between first and second set
        if is_single_marker:
            if idx != 0:
                continue
            try:
                sweeps2 = res.get("sweeps2") or []
                if not sweeps2 and len(results) >= 2:
                    sweeps2 = results[1].get("sweeps", []) or []
                if sweeps2:
                    x2 = float(np.mean(sweeps2)) * _xs
                    x = (x + x2) / 2.0
            except Exception:
                pass

        # Determine which p/q columns apply to this panel
        amp_pcols = [k for k in res.keys() if k.startswith("p_") and "amp" in k]
        slope_pcols = [k for k in res.keys() if k.startswith("p_") and "slope" in k]

        # For IO mode, map io_output to amp/slope semantics
        if is_io_mode:
            if io_output and "slope" in io_output.lower():
                amp_pcols, slope_pcols = [], slope_pcols
            else:
                amp_pcols, slope_pcols = amp_pcols, []

        # Compute placements (mirrors ui_plot.py:show_test_markers)
        # Convention: amp high (top), slope low (bottom) when both shown;
        # single-aspect view places that aspect high (top).
        placements: list[tuple[str, float, str]] = []
        if amp_view and slope_view:
            for pcol in amp_pcols:
                placements.append((pcol, 0.94, "top"))  # amp = high position
            for pcol in slope_pcols:
                placements.append((pcol, 0.06, "bottom"))  # slope = low position
        elif amp_view:
            for pcol in amp_pcols:
                placements.append((pcol, 0.94, "top"))
        elif slope_view:
            for pcol in slope_pcols:
                placements.append((pcol, 0.94, "top"))

        for pcol, y_frac, va in placements:
            if not pcol:
                continue
            qcol = "q_" + pcol[2:]
            pval = res.get(pcol)
            qval = res.get(qcol)
            val = qval if (isinstance(qval, (int, float)) and np.isfinite(qval)) else pval

            if isinstance(val, (int, float)) and np.isfinite(val):
                if val < 0.001:
                    label = "***"
                elif val < 0.01:
                    label = "**"
                elif val < 0.05:
                    label = "*"
                else:
                    label = "ns"
            else:
                label = "ns"

            if label_override is not None:
                label = label_override  # for debug/override (e.g. p-value string)

            is_sig = label != "ns"
            # Journal export always uses white/light background; never use white text.
            # Significant = black; ns = medium gray. Ignore 'dark' param for color.
            color = "black" if is_sig else "#555555"

            # Compute y position in data coordinates (mirrors ui_plot.py)
            # amp high (y_frac=0.94, top); slope low (y_frac=0.06, bottom) when both shown
            ymin, ymax = ax.get_ylim()
            y = ymin + (ymax - ymin) * y_frac

            # PP vertical offset: place near top of current y-range (above bars)
            if is_pp_mode:
                ymin2, ymax2 = ax.get_ylim()
                y = ymax2 * 0.92

            try:
                # Journal font scaling (clamped for 1-col vs 2-col templates)
                if template.width_mm < 90:
                    fontsize = max(template.font_size_axis_label * 1.5, 7.0)
                    fontsize = min(fontsize, 9.0)
                else:
                    fontsize = max(template.font_size_axis_label * 1.7, 8.0)
                    fontsize = min(fontsize, 11.0)
                ax.text(
                    x,
                    y,
                    label,
                    ha="center",
                    va=va,
                    fontsize=fontsize,
                    fontweight="bold",
                    color=color,
                    zorder=12,
                )

                # Draw sweep-range bracket (journal convention: underline + end ticks)
                # Many neuroscience journals (JNeurosci, JPhysiol, Nature) use this for test-set ranges
                # or error-bar groups; marker text sits above. Lowered offset avoids overlap with "*"/"ns".
                if sweeps and len(sweeps) >= 2:
                    x_min = float(min(sweeps)) * _xs
                    x_max = float(max(sweeps)) * _xs
                    # 1-col templates are tighter (smaller height_mm, denser y-scale); use larger relative offset.
                    offset_frac = 0.065 if template.width_mm < 90 else 0.04
                    bracket_y = y - (ymax - ymin) * offset_frac
                    lw = template.linewidth_axes * 1.5
                    # main horizontal underline
                    ax.plot([x_min, x_max], [bracket_y, bracket_y], color="black", linewidth=lw, zorder=11)
                    # short vertical ticks at ends (downward)
                    tick_len = (ymax - ymin) * 0.025
                    ax.plot([x_min, x_min], [bracket_y, bracket_y - tick_len], color="black", linewidth=lw, zorder=11)
                    ax.plot([x_max, x_max], [bracket_y, bracket_y - tick_len], color="black", linewidth=lw, zorder=11)
            except Exception:
                pass


def render_publication_figure(
    uistate,
    uiplot,
    template: JournalTemplate,
    selected_groups: list[str],
    group_names: Optional[dict[str, str]] = None,
) -> dict[str, matplotlib.figure.Figure]:
    """
    Render a standalone, publication-quality figure from ax1 and ax2 of selected groups.
    Returns a dictionary mapping panel names (e.g. 'amplitude', 'slope') to their respective matplotlib Figure.
    """
    rc_params = {
        "font.family": template.font_family,
        "axes.labelsize": template.font_size_axis_label,
        "xtick.labelsize": template.font_size_tick_label,
        "ytick.labelsize": template.font_size_tick_label,
        "legend.fontsize": template.font_size_legend,
        "lines.linewidth": template.linewidth_data,
        "axes.linewidth": template.linewidth_axes,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "black",
        "text.color": "black",
        "xtick.color": "black",
        "ytick.color": "black",
        "axes.labelcolor": "black",
        "savefig.facecolor": "white",
        "savefig.edgecolor": "white",
    }

    figures = {}
    panel_name_map = {
        "amp": "amplitude",
        "slope": "slope",
        "event": "event",
        "mean": "mean",
    }

    with matplotlib.rc_context(rc_params):
        is_io_mode = uistate.experiment.experiment_type == "io"
        is_pp_mode = uistate.experiment.experiment_type == "PP"
        if is_pp_mode:
            # Relative mode: volley has no relative series — omit volley panels
            # (checkbox state is preserved; ignored for export panel selection).
            _cb = uistate.project.checkBox
            _norm = bool(_cb.get("norm_EPSP", False))
            panels_to_render = [
                asp
                for asp in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]
                if _cb.get(asp, True) and not (_norm and asp.startswith("volley_"))
            ]
        elif is_io_mode:
            panels_to_render = ["io"]
        else:
            panels_to_render = template.panels

        for panel in panels_to_render:
            # Create a fresh figure for each panel using the provided template dimensions
            fig = matplotlib.figure.Figure(
                figsize=(template.width_mm / 25.4, template.height_mm / 25.4),
                dpi=template.dpi,
            )

            ax = fig.add_subplot(111)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            if is_pp_mode:
                for y_val in plot_model.pp_reference_grid_y_values():
                    ax.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)
            elif uistate.project.checkBox.get("norm_EPSP"):
                if panel == "amp":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.project.settings.get("rgb_EPSP_amp", "black"),
                    )
                elif panel == "slope":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.project.settings.get("rgb_EPSP_slope", "black"),
                    )
                elif panel == "io":
                    io_output = uistate.experiment.io_output
                    _, y_col_base = plot_series.io_axis_columns(uistate.experiment.io_input, io_output)
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.project.settings.get(f"rgb_{y_col_base}", "black"),
                    )

            # Re-plot data by identifying relevant lines from the existing interactive axes
            # We fetch data directly from the plotted group lines in uistate
            # to mirror exactly what was calculated, applying only new styling.
            has_data = False
            # Time mode: convert sweep-index x → display units so ticks match xlabel.
            x_scale = None if (is_pp_mode or is_io_mode) else _export_time_x_scale(uistate)
            axis_labels = plot_model.output_axis_ylabels(
                experiment_type=uistate.experiment.experiment_type,
                io_output=uistate.experiment.io_output if is_io_mode else "",
                norm_epsP=bool(uistate.project.checkBox.get("norm_EPSP")),
            )
            for label, info in uistate.plot.dict_group_labels.items():
                group_id_str = str(info["group_ID"])
                # We only plot if the group ID is in selected_groups
                if group_id_str not in [str(g) for g in selected_groups]:
                    continue

                # Only plot lines that are currently toggled visible in the UI
                if label not in uistate.plot.dict_group_show:
                    continue

                axis_src = info.get("axis")
                line = info.get("line")
                fill = info.get("fill")
                if not line:
                    continue

                is_io = info.get("x_mode") == "io"

                # Check if this line corresponds to the current panel

                # Color: stored group color (box export) > face of patch/box > line color
                group_color = info.get("pp_group_color")
                if group_color is None:
                    group_color = _export_artist_color(line, default="black")

                if is_pp_mode:
                    if info.get("aspect") != panel:
                        continue
                    if "overlay" in label or info.get("is_overlay"):
                        continue
                    aspect_str = panel.replace("_", " ").replace("amp", "amplitude")
                    ax.set_ylabel(f"PPR ({aspect_str})")  # ratio stim2/stim1
                    has_data = True

                    # Box summary (preferred): journal-thin black outline, group face color
                    if info.get("is_pp_box") and info.get("pp_values"):
                        bx = float(info.get("pp_box_x", 1.0))
                        bw = float(info.get("pp_box_width", 0.5))
                        vals = list(info["pp_values"])
                        lw = template.linewidth_axes
                        bp = ax.boxplot(
                            [vals],
                            positions=[bx],
                            widths=bw,
                            patch_artist=True,
                            showfliers=False,
                            manage_ticks=False,
                            whis=1.5,
                            boxprops=dict(linewidth=lw, edgecolor="black"),
                            whiskerprops=dict(color="black", linewidth=lw),
                            capprops=dict(color="black", linewidth=lw),
                            medianprops=dict(color="black", linewidth=lw),
                        )
                        for box in bp.get("boxes", []):
                            box.set_facecolor(group_color)
                            box.set_edgecolor("black")
                            box.set_alpha(0.85)
                            box.set_linewidth(lw)
                        for med in bp.get("medians", []):
                            med.set_color("black")
                            med.set_linewidth(lw)
                        for key in ("whiskers", "caps"):
                            for art in bp.get(key, []):
                                art.set_color("black")
                                art.set_linewidth(lw)
                        continue

                    # Unit scatter points (role or legacy display/key name)
                    disp = str(info.get("display_label") or label)
                    is_point = info.get("role") == "pp_point" or "point" in disp or "point" in str(label)
                    if is_point and hasattr(line, "get_offsets"):
                        try:
                            off = line.get_offsets()
                            if len(off):
                                ax.scatter(
                                    off[:, 0],
                                    off[:, 1],
                                    facecolors="white",
                                    edgecolors="black",
                                    linewidths=template.linewidth_axes,
                                    s=18,
                                    zorder=4,
                                )
                        except Exception:
                            pass
                        continue

                    # Legacy bar path — resolve companion bar by group_ID/aspect, not name-split key
                    shift = 0
                    bar_info = None
                    for _k, ent in (uistate.plot.dict_group_labels or {}).items():
                        if not isinstance(ent, dict):
                            continue
                        if ent.get("group_ID") != info.get("group_ID"):
                            continue
                        if ent.get("aspect") != info.get("aspect"):
                            continue
                        if ent.get("is_pp_box") or ent.get("role") == "pp_box":
                            bar_info = ent
                            break
                        bline = ent.get("line")
                        if bline is not None and hasattr(bline, "patches") and len(bline.patches) > 0:
                            bar_info = ent
                            break
                    if bar_info and hasattr(bar_info.get("line"), "patches") and len(bar_info["line"].patches) > 0:
                        p = bar_info["line"].patches[0]
                        orig_base_x = p.get_x() + p.get_width() / 2
                        shift = plot_series.pp_group_tick_from_bar(p.get_x(), p.get_width()) - orig_base_x

                    if hasattr(line, "patches"):  # BarContainer
                        xdata = [plot_series.pp_group_tick_from_bar(p.get_x(), p.get_width()) for p in line.patches]
                        ydata = [p.get_height() for p in line.patches]
                        width = 0.8  # Standard width
                        color = line.patches[0].get_facecolor()
                        ax.bar(xdata, ydata, width=width, color=color, edgecolor="black", alpha=1.0, linewidth=template.linewidth_data)
                    elif hasattr(line, "lines"):  # ErrorbarContainer
                        if len(line.lines) > 2 and line.lines[2]:
                            segments = line.lines[2][0].get_segments()
                            for seg in segments:
                                x_err = [seg[0][0] + shift, seg[1][0] + shift]
                                y_err = [seg[0][1], seg[1][1]]
                                ax.plot(x_err, y_err, color="black", linewidth=template.linewidth_error)
                    elif hasattr(line, "get_offsets"):  # Scatter points
                        offsets = line.get_offsets()
                        if len(offsets) == 0:
                            continue
                        xdata = offsets[:, 0] + shift
                        ydata = offsets[:, 1]

                        group_color = "black"
                        if bar_info and hasattr(bar_info.get("line"), "patches") and len(bar_info["line"].patches) > 0:
                            group_color = bar_info["line"].patches[0].get_facecolor()

                        ax.scatter(xdata, ydata, color="white", edgecolor="black", s=15, linewidth=template.linewidth_data, zorder=3)

                    continue

                if is_io:
                    # In IO mode, all groups are on ax1.  Use the aspect to determine panel.
                    if panel == "io":
                        ax.set_ylabel(axis_labels.ax1_ylabel)
                        has_data = True
                    else:
                        continue
                else:
                    if panel == "amp" and axis_src == "ax1":
                        ax.set_ylabel(axis_labels.ax1_ylabel)
                        has_data = True
                    elif panel == "slope" and axis_src == "ax2":
                        ax.set_ylabel(axis_labels.ax2_ylabel)
                        has_data = True
                    else:
                        # Ignore event/mean panels for now unless they match the source axis
                        # Future expansion could handle axm/axe
                        continue

                if hasattr(line, "get_offsets"):
                    offsets = line.get_offsets()
                    if len(offsets) == 0:
                        continue
                    xdata = offsets[:, 0].copy()
                    ydata = offsets[:, 1].copy()
                else:
                    xdata = plot_drag.artist_xdata(line).copy()
                    ydata = plot_drag.artist_ydata(line).copy()

                if hasattr(line, "get_color"):
                    color = line.get_color()
                elif hasattr(line, "get_facecolors") and len(line.get_facecolors()) > 0:
                    color = line.get_facecolors()[0]
                    if len(color) == 4:
                        color = color[:3]
                else:
                    color = "black"

                plot_label = group_names.get(group_id_str, label) if group_names else label

                yerr = None
                if not is_io and fill and len(fill.get_paths()) > 0:
                    verts = fill.get_paths()[0].vertices
                    yerr = []
                    for xi in xdata:
                        y_vals = [v[1] for v in verts if abs(v[0] - xi) < 1e-5]
                        if y_vals:
                            err_val = (max(y_vals) - min(y_vals)) / 2
                            yerr.append(err_val)
                        else:
                            yerr.append(0)

                # Sweep index → display time (min/s/h) before plotting
                xdata = _scale_export_x(xdata, x_scale)

                if yerr is not None:
                    ax.errorbar(
                        xdata,
                        ydata,
                        yerr=yerr,
                        label=plot_label,
                        color=color,
                        fmt="o",
                        markersize=3,
                        linewidth=template.linewidth_data,
                        elinewidth=template.linewidth_error,
                        capsize=0,
                    )
                elif is_io:
                    if "scatter" in label:
                        ax.plot(
                            xdata,
                            ydata,
                            label=plot_label,
                            color=color,
                            linestyle="none",
                            marker="o",
                            markersize=3,
                            alpha=0.3,
                        )
                    else:
                        ax.plot(
                            xdata,
                            ydata,
                            label=plot_label,
                            color=color,
                            linestyle="-",
                            linewidth=template.linewidth_data * 2,
                            alpha=0.9,
                        )
                else:
                    ax.plot(
                        xdata,
                        ydata,
                        label=plot_label,
                        color=color,
                        linestyle="none",
                        marker="o",
                        markersize=3,
                    )

            if has_data:
                ax.set_ylim(bottom=0)

                if is_pp_mode:
                    ax.set_xlabel("")
                    bar_specs: list[tuple[float, float, str]] = []
                    for label, info in uistate.plot.dict_group_labels.items():
                        if info.get("aspect") != panel:
                            continue
                        if info.get("is_overlay"):
                            continue
                        disp = str(info.get("display_label") or label)
                        if info.get("is_overlay") or info.get("role") == "pp_point":
                            continue
                        if info.get("is_pp_box") and info.get("pp_box_x") is not None:
                            bx = float(info["pp_box_x"])
                            bw = float(info.get("pp_box_width", 0.5))
                            tick_lab = info.get("pp_tick_label") or (
                                disp.split(" PPR")[0] if " PPR" in disp else disp
                            )
                            bar_specs.append((bx - bw / 2.0, bw, tick_lab))
                            continue
                        line_obj = info.get("line")
                        if not hasattr(line_obj, "patches"):
                            continue
                        try:
                            patches = line_obj.patches
                            if patches:
                                p = patches[0]
                                gname = disp.split(" PPR")[0] if " PPR" in disp else disp
                                bar_specs.append((p.get_x(), p.get_width(), gname))
                        except Exception:
                            pass
                    x_ticks, x_ticklabels = plot_series.pp_group_tick_label_map(bar_specs)
                    if x_ticks:
                        ax.set_xticks(x_ticks)
                        ax.set_xticklabels(x_ticklabels)

                        # Add a 0.6 pad on each side to create a clean visual boundary
                        # around the centered bars (since bars have width 0.8)
                        ax.set_xlim(min(x_ticks) - 0.6, max(x_ticks) + 0.6)
                        ax.tick_params(axis="x", bottom=False, labelbottom=True)
                else:
                    _configure_export_xaxis(ax, uistate, x_scale=x_scale)

                handles, labels = ax.get_legend_handles_labels()
                if labels:
                    # Omit IO trendlines — same color as group scatter; clutter-free legend.
                    # Legend text is display_label; legacy sessions may still end with the suffix.
                    from brainwash_ui import plot_identity as pi

                    by_label = {}
                    for h, lab in zip(handles, labels):
                        if not lab or str(lab).startswith("_"):
                            continue
                        if pi.entry_io_role({"role": None, "display_label": lab}, str(lab)) == pi.ROLE_IO_TREND:
                            continue
                        by_label[lab] = h
                    if by_label:
                        ax.legend(by_label.values(), by_label.keys(), frameon=False)

                show_inset = (is_io_mode and panel == "io") or (not is_io_mode and panel in ["amp", "slope"])
                if show_inset and hasattr(uistate, "sample_inset") and uistate.plot.sample_inset is not None and uistate.plot.sample_inset.get_visible():
                    export_inset = ax.inset_axes([0.02, 0.68, 0.20, 0.30])
                    export_inset.set_zorder(10)
                    export_inset.set_facecolor((0, 0, 0, 0))
                    export_inset.patch.set_alpha(0.0)
                    for spine in export_inset.spines.values():
                        spine.set_visible(False)
                    export_inset.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
                    export_inset.set_axis_off()

                    all_ys = []
                    for key, line in uistate.plot.sample_artists.items():
                        if len(key) == 3:
                            group_ID, test_id, stim_num = key
                        else:
                            continue

                        if str(group_ID) not in [str(g) for g in selected_groups]:
                            continue
                        if not line.get_visible():
                            continue

                        x_data = plot_drag.artist_xdata(line)
                        y_data = plot_drag.artist_ydata(line)
                        y_filtered = [y for x, y in zip(x_data, y_data) if x > 0.001]
                        all_ys.extend(y_filtered)

                        export_inset.plot(
                            x_data,
                            y_data,
                            color=line.get_color(),
                            alpha=0.75,
                            linewidth=template.linewidth_data,
                            linestyle=line.get_linestyle(),
                            zorder=11,
                        )

                    if all_ys:
                        ymin, ymax = min(all_ys), max(all_ys)
                        export_inset.set_ylim(ymin * 1.1, ymax + 0.0001)
                    export_inset.set_xlim(-0.005, 0.035)
                    export_inset.relim()
                    export_inset.autoscale_view(scalex=False)

                # Significance * markers: time/PP only. IO ANCOVA is statusbar + methods .md (PR-D).
                formal_results = uistate.stat_test.formal_test_results
                if formal_results and not is_io_mode:
                    # Headroom above data so * / ** / brackets are not flush with SEM tops.
                    _expand_export_ylim_for_markers(ax)
                    test_type = uistate.stat_test.test_type
                    if test_type == "Wilcoxon":
                        variant = uistate.stat_test.test_wilcox_variant
                    else:
                        variant = uistate.stat_test.test_t_variant
                    fdr_flag = bool(uistate.stat_test.test_fdr)
                    dark_flag = bool(uistate.darkmode)
                    # Per-panel visibility for significance markers (matches ui_plot.py:show_test_markers exactly).
                    # When both aspects selected: amp panel -> low y on ax1 (p_amp/**), slope panel -> high y on ax2 (p_slope/*).
                    if panel in ("amp", "amplitude", "EPSP_amp"):
                        amp_v = True
                        slope_v = False
                        label_override = None
                    elif panel in ("slope", "EPSP_slope"):
                        amp_v = False
                        slope_v = True
                        label_override = None
                    else:
                        amp_v = bool(uistate.project.checkBox.get("EPSP_amp", True))
                        slope_v = bool(uistate.project.checkBox.get("EPSP_slope", True))
                        label_override = None
                    io_out = uistate.experiment.io_output if is_io_mode else None
                    _add_significance_markers(
                        ax=ax,
                        panel=panel,
                        template=template,
                        results=formal_results,
                        is_pp_mode=is_pp_mode,
                        is_io_mode=is_io_mode,
                        io_output=io_out,
                        amp_view=amp_v,
                        slope_view=slope_v,
                        dark=dark_flag,
                        variant=variant,
                        fdr=fdr_flag,
                        label_override=label_override,  # NEW: "AM" for amp image, "SM" for slope image
                        x_scale=x_scale,
                    )

                fig.tight_layout()
                if panel == "io":
                    io_input = uistate.experiment.io_input
                    io_output = uistate.experiment.io_output
                    panel_key = f"{io_input}-{io_output}"
                else:
                    panel_key = panel_name_map.get(panel, panel)
                figures[panel_key] = fig

    return figures


def _figure_text_pstr(p, q=None, *, prefer_q: bool = False) -> str:
    val = q if prefer_q and isinstance(q, (int, float)) and np.isfinite(q) else p
    if not isinstance(val, (int, float)) or not np.isfinite(val):
        return "NA"
    if val < 0.001:
        return "<0.001"
    return f"{val:.3g}"


def _figure_text_unit_plural(n_unit: str) -> str:
    return "subjects" if n_unit == "subject" else f"{n_unit}s"


def _figure_text_unit_warning(n_unit: str) -> str | None:
    """Lead callout when *n* is not subject-level (species-neutral wording)."""
    if n_unit not in ("slice", "recording"):
        return None
    plural = _figure_text_unit_plural(n_unit)
    return (
        f"> **Note on statistical units:** Comparisons used the **{n_unit}** as the independent "
        f"observation (*n* counts {plural}, **not subjects**). If multiple {plural} derive from the "
        f"same subject (e.g. same animal, donor, or culture line), standard errors and *p*-values may "
        f"be anticonservative relative to a subject-level analysis. Consider subject-level aggregation "
        f"or mixed models for the final manuscript.\n"
        f"> <!-- Remove or rewrite this note if units are intentional and justified. -->"
    )


def _figure_text_force0_warning(*, force0: bool, exp_type: str | None = None) -> str | None:
    """Callout when IO regressions / ANCOVA are constrained through the origin (io_force0)."""
    if not force0:
        return None
    if exp_type is not None and exp_type != "io":
        return None
    return (
        "> **Note on forced-through-origin fits:** Trendlines and IO ANCOVA models were constrained "
        "to pass through the origin (`io_force0`). This is a strong modeling assumption: intercepts "
        "are not free, slopes and *r*² can differ from unconstrained least-squares, and results "
        "should be interpreted only if a zero intercept is scientifically justified "
        "(e.g. no response at zero input).\n"
        "> <!-- Remove or rewrite this note if force-through-zero is intentional and justified. -->"
    )


def _figure_text_paired_drop_warning(results: list | None) -> str | None:
    """Self-contained note when paired tests excluded incomplete unit pairs."""
    if not results:
        return None
    for res in results:
        if not isinstance(res, dict):
            continue
        try:
            n_dropped = int(res.get("n_dropped", 0) or 0)
        except (TypeError, ValueError):
            n_dropped = 0
        if n_dropped <= 0:
            continue
        n_pairs = res.get("n_pairs", res.get("n1"))
        try:
            n_pairs_i = int(n_pairs) if n_pairs is not None else None
        except (TypeError, ValueError):
            n_pairs_i = None
        lines = [
            "> **Note on incomplete pairs:** The analysis used **complete cases only**: "
            "statistical units were included only when every compared test set/condition had a finite "
            f"value after aggregation to the chosen unit. **{n_dropped}** unit(s) were excluded",
        ]
        if n_pairs_i is not None:
            lines[0] += f"; **{n_pairs_i}** complete unit(s) remained"
        lines[0] += "."
        dropped = res.get("paired_dropped") or []
        if dropped:
            lines.append(">")
            lines.append("> Excluded units:")
            for d in dropped:
                unit = d.get("unit", "?")
                reason = d.get("reason", "incomplete pair")
                lines.append(f"> - `{unit}`: {reason}")
        lines.append(
            "> <!-- Remove or rewrite this note if attrition is intentional and already described. -->"
        )
        return "\n".join(lines)
    return None


def _figure_text_dd_groups(group_names: dict | None) -> dict:
    """Map {gid: name} or {gid: {group_name: ...}} → statusbar-style dd_groups."""
    out: dict = {}
    for gid, val in (group_names or {}).items():
        if isinstance(val, dict):
            out[gid] = val
            # also index by str
            out[str(gid)] = val
        else:
            entry = {"group_name": str(val)}
            out[gid] = entry
            out[str(gid)] = entry
    return out


def _figure_text_panel_title(panel_hint: str | None, exp_type: str) -> str:
    if not panel_hint:
        return "[Panel title / what is plotted.]"
    p = str(panel_hint).lower()
    if p in ("amplitude", "amp", "epsp_amp"):
        return "[EPSP amplitude over time.]" if exp_type not in ("io", "PP") else "[EPSP amplitude.]"
    if p in ("slope", "epsp_slope"):
        return "[EPSP slope over time.]" if exp_type not in ("io", "PP") else "[EPSP slope.]"
    if "io" in p or "-" in p:  # e.g. vamp-EPSPamp
        return "[Input–output relationship.]"
    if "ppr" in p or exp_type == "PP":
        return f"[Paired-pulse ratio ({panel_hint}).]"
    return f"[{panel_hint}.]"


def _figure_text_measure_phrase(panel_hint: str | None, amp_on: bool, slope_on: bool, exp_type: str = "time") -> str:
    p = (panel_hint or "").lower()
    if exp_type == "PP":
        if p in ("amplitude", "amp", "epsp_amp") or "epsp_amp" in p:
            return "paired-pulse ratio (PPR) of EPSP amplitude (stim2/stim1)"
        if p in ("slope", "epsp_slope") or "epsp_slope" in p:
            return "paired-pulse ratio (PPR) of EPSP slope (stim2/stim1)"
        if "volley" in p and "slope" in p:
            return "paired-pulse ratio (PPR) of volley slope (stim2/stim1)"
        if "volley" in p:
            return "paired-pulse ratio (PPR) of volley amplitude (stim2/stim1)"
        if amp_on and slope_on:
            return "paired-pulse ratio (PPR; stim2/stim1)"
        if slope_on:
            return "paired-pulse ratio (PPR) of EPSP slope (stim2/stim1)"
        return "paired-pulse ratio (PPR) of EPSP amplitude (stim2/stim1)"
    if p in ("amplitude", "amp", "epsp_amp"):
        return "EPSP amplitude"
    if p in ("slope", "epsp_slope"):
        return "EPSP slope"
    if amp_on and slope_on:
        return "EPSP amplitude / slope"
    if slope_on:
        return "EPSP slope"
    return "EPSP amplitude"


def _figure_text_test_prose(test_type: str, variant: str, tails: str, fdr: bool) -> str:
    if test_type == "t-test":
        if variant == "paired":
            core = "paired two-sided Student's *t*-test"
        elif variant == "one-sample":
            core = "one-sample two-sided Student's *t*-test"
        else:
            core = "unpaired two-sided Student's *t*-test"
        if tails != "two-sided":
            core = core.replace("two-sided", tails)
        if fdr:
            core += " with Benjamini–Hochberg FDR correction"
        return core[0].upper() + core[1:]
    if test_type == "Wilcoxon":
        # UI/engine ship signed-rank only (paired or one-sample); no rank-sum.
        if variant == "one-sample":
            core = "one-sample two-sided Wilcoxon signed-rank test"
        else:
            core = "paired two-sided Wilcoxon signed-rank test"
        if tails != "two-sided":
            core = core.replace("two-sided", tails)
        if fdr:
            core += " with Benjamini–Hochberg FDR correction"
        return core[0].upper() + core[1:]
    if test_type == "ANOVA":
        return "Repeated-measures ANOVA (omnibus)"
    if test_type == "Friedman":
        return "Friedman test (repeated-measures omnibus)"
    if test_type == "Cluster perm.":
        # Prefer mode from formal results when available
        mode = None
        # callers pass only type/variant/tails/fdr — variant may be "between"/"paired" after fix
        if variant in ("between", "paired", "cluster"):
            mode = "paired" if variant == "paired" else "between" if variant == "between" else None
        if mode == "paired":
            return "Cluster permutation test (paired, within-group; recording-aligned differences)"
        return "Cluster permutation test (between groups; recording-level matrices)"
    if test_type == "ANCOVA":
        return "ANCOVA"
    return test_type


def _figure_text_group_n_phrase(results: list, group_map: dict, n_unit: str) -> str:
    """Best-effort 'Control (*n* = 6 subjects) and Drug (*n* = 7 subjects)'."""
    plural = _figure_text_unit_plural(n_unit)
    # Prefer group_ns on first result / config
    primary = results[0] if results else {}
    group_ns = primary.get("group_ns") or (primary.get("config") or {}).get("group_ns") or {}
    if group_ns:
        bits = []
        for gid, n in group_ns.items():
            name = group_map.get(gid) or group_map.get(str(gid))
            if isinstance(name, dict):
                name = name.get("group_name", f"Group {gid}")
            if not name:
                name = f"Group {gid}"
            bits.append(f"**{name}** (*n* = {n} {plural})")
        if len(bits) == 1:
            return bits[0]
        if len(bits) == 2:
            return f"{bits[0]} and {bits[1]}"
        return ", ".join(bits[:-1]) + f", and {bits[-1]}"
    # Fallback n1/n2 + group1/group2
    g1, g2 = primary.get("group1"), primary.get("group2")
    n1, n2 = primary.get("n1"), primary.get("n2")
    if g1 is not None and n1 is not None:
        def _nm(g):
            if isinstance(g, (list, tuple)):
                return ", ".join(str(group_map.get(x) or group_map.get(str(x)) or x) for x in g)
            return str(group_map.get(g) or group_map.get(str(g)) or g)

        if g2 is not None and n2 is not None and g1 != g2:
            return f"**{_nm(g1)}** (*n* = {n1} {plural}) and **{_nm(g2)}** (*n* = {n2} {plural})"
        return f"**{_nm(g1)}** (*n* = {n1} {plural})"
    if group_map:
        names = []
        for gid, val in group_map.items():
            if isinstance(gid, str) and gid.isdigit() is False and not isinstance(val, dict):
                # skip duplicate str keys if we also have int keys — still list unique names
                pass
            name = val.get("group_name") if isinstance(val, dict) else val
            if name and str(name) not in names:
                names.append(str(name))
        # dedupe preserving order (str/int double keys)
        seen = set()
        uniq = []
        for n in names:
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        if uniq:
            return " and ".join(f"**{n}**" for n in uniq[:4])
    return f"[groups; *n* at the {n_unit} level]"


def build_figure_text_md(uistate, template, group_names=None, panel_hint: str | None = None) -> str:
    """Journal figure-text skeleton (.md companion next to each PNG).

    Sectioned draft for paste into a caption: unit-of-analysis warning (if needed),
    author placeholders, statistics prose from formal results / statusbar sources,
    symbol legend, and a machine-readable checklist.
    """
    lines: list[str] = [
        "# Figure text skeleton",
        "<!-- Auto-generated by Brainwash. Replace [brackets]; keep or edit statistics. -->",
        "",
    ]

    exp_type = getattr(getattr(uistate, "experiment", None), "experiment_type", "time") if uistate else "time"
    st = getattr(uistate, "stat_test", None) if uistate else None
    test_type = getattr(st, "test_type", "None") if st else "None"
    n_unit = getattr(st, "buttonGroup_test_n", "subject") if st else "subject"
    results = list(getattr(st, "formal_test_results", None) or []) if st else []

    project = getattr(uistate, "project", None) if uistate else None
    cb = getattr(project, "checkBox", {}) if project else {}
    amp_on = bool(cb.get("EPSP_amp", True))
    slope_on = bool(cb.get("EPSP_slope", True))
    norm = bool(cb.get("norm_EPSP", False))

    group_map = dict(group_names or {})
    if not group_map and uistate is not None and hasattr(uistate, "plot"):
        for _k, v in getattr(uistate.plot, "dict_group_labels", {}).items() or []:
            if isinstance(v, dict) and "group_name" in v:
                group_map[str(v.get("group_ID", ""))] = v["group_name"]
    dd_groups = _figure_text_dd_groups(group_map)

    warn = _figure_text_unit_warning(n_unit)
    if warn:
        lines.extend([warn, ""])

    force0 = bool(cb.get("io_force0", False))
    if not force0 and results:
        cfg0 = results[0].get("config") if isinstance(results[0], dict) else None
        if isinstance(cfg0, dict):
            force0 = bool(cfg0.get("force_through_zero", False))
    force0_warn = _figure_text_force0_warning(force0=force0, exp_type=exp_type)
    if force0_warn:
        lines.extend([force0_warn, ""])

    paired_drop_warn = _figure_text_paired_drop_warning(results)
    if paired_drop_warn:
        lines.extend([paired_drop_warn, ""])

    lines.append("## Caption draft")
    lines.append("")
    lines.append(f"**{_figure_text_panel_title(panel_hint, exp_type)}**  ")
    lines.append(
        "[One sentence of experimental context: preparation, groups, intervention, time window.]"
    )
    lines.append("")

    measure = _figure_text_measure_phrase(panel_hint, amp_on, slope_on, exp_type=exp_type)
    x_phrase = {
        "time": "time",
        "timestamp": "time",
        "sweep": "sweep number",
        "train": "stimulus number",
        "io": "input (stimulus / volley)",
        "PP": "group",
    }.get(exp_type, "x")
    norm_note = " Data are normalized to baseline." if norm else ""
    group_n = _figure_text_group_n_phrase(results, group_map, n_unit)

    if exp_type == "PP":
        lines.append(
            f"Box plots (median, IQR, Tukey whiskers) of unit-level **{measure}** by **{x_phrase}** "
            f"for {group_n}, with individual unit values overlaid.{norm_note}"
        )
    else:
        lines.append(
            f"Group means (± SEM) of **{measure}** versus **{x_phrase}** for {group_n}.{norm_note}"
        )
    lines.append("")

    # --- Statistics section ---
    lines.append("### Statistics")
    lines.append("")

    no_test = test_type in (None, "None") or not results
    io_needs_ancova = exp_type == "io" and test_type != "ANCOVA"

    if no_test or io_needs_ancova:
        if exp_type == "io" and test_type != "ANCOVA":
            lines.append(
                "No formal statistical comparison was applied for this export "
                "(select **ANCOVA** under Input–Output to compute slope/group tests)."
            )
        else:
            lines.append("No formal statistical comparison was applied for this export.")
        lines.append("")
        lines.append("### Symbols")
        lines.append("")
        lines.append("(not applicable)")
        lines.append("")
        lines.append("### Checklist (from session)")
        lines.append("")
        lines.append(f"- Experiment type: `{exp_type}`")
        lines.append(f"- Test: `{test_type}`")
        lines.append(f"- n_unit: `{n_unit}`")
        if group_map:
            names = []
            for g, v in group_map.items():
                nm = v.get("group_name") if isinstance(v, dict) else v
                if nm and str(nm) not in names:
                    names.append(str(nm))
            lines.append(f"- Groups: {', '.join(names)}")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    fdr = bool(getattr(st, "test_fdr", False))
    sw = bool(getattr(st, "test_sw", False))
    levene = bool(getattr(st, "test_levene", False))
    if test_type == "Wilcoxon":
        variant = getattr(st, "test_wilcox_variant", "paired")
        tails = getattr(st, "test_wilcox_tails", "two-sided")
    elif test_type == "Cluster perm.":
        variant = "between"
        if results and isinstance(results[0], dict):
            variant = results[0].get("cluster_mode") or (results[0].get("config") or {}).get("variant") or "between"
        tails = "two-sided"
    else:
        variant = getattr(st, "test_t_variant", "unpaired")
        tails = getattr(st, "test_t_tails", "two-sided")

    # IO ANCOVA path
    if exp_type == "io" and test_type == "ANCOVA":
        from brainwash_ui import statusbar as statusbar_fmt

        methods = statusbar_fmt.format_io_ancova_methods_text(
            results, dd_groups=dd_groups, n_unit=n_unit
        )
        # Append slope / r² pairs from config (statusbar pairing)
        cfg = {}
        if results and isinstance(results[0], dict):
            cfg = results[0].get("config") or results[0]
        slopes = (cfg.get("slope_per_group") or {}) if isinstance(cfg, dict) else {}
        r2s = (cfg.get("r2_per_group") or {}) if isinstance(cfg, dict) else {}
        pair_bits = []
        for g, sl in slopes.items():
            if not (isinstance(sl, (int, float)) and np.isfinite(sl)):
                continue
            gname = dd_groups.get(g, dd_groups.get(str(g), {})).get("group_name", f"Group {g}")
            r2v = r2s.get(g)
            bit = f"{gname} slope = {sl:.3g}"
            if isinstance(r2v, (int, float)) and np.isfinite(r2v):
                bit += f", *r*² = {r2v:.2f}"
            pair_bits.append(bit)
        if pair_bits:
            methods = methods.rstrip(".") + ". Per-group fits: " + "; ".join(pair_bits) + "."
        lines.append(methods)
        # Verbose residual / normality notes (SW, Levene) — self-contained, no statusbar refs
        ass_prose = ""
        if isinstance(cfg, dict):
            ass_prose = statusbar_fmt.format_io_ancova_assumption_prose(cfg.get("assumptions") or {})
        sw_on = bool(getattr(st, "test_sw", False))
        lev_on = bool(getattr(st, "test_levene", False))
        if ass_prose or sw_on or lev_on:
            lines.append("")
            lines.append("### Assumption checks")
            lines.append("")
            if ass_prose:
                lines.append(ass_prose)
            else:
                # Checkboxes on but no residual stats stored
                if sw_on:
                    lines.append(
                        "Shapiro–Wilk was enabled for this session; no residual SW *p*-value is stored "
                        "in the formal result (insufficient residual *n* or check did not run)."
                    )
                if lev_on:
                    lines.append(
                        "Levene’s test was enabled for this session; no residual Levene *p*-value is stored "
                        "in the formal result (insufficient *n* or check did not run)."
                    )
        lines.append("")
        lines.append("### Symbols")
        lines.append("")
        lines.append(
            "IO ANCOVA is summarized in this text and the companion figure; "
            "significance * markers are not drawn on IO scatter panels."
        )
        lines.append("")
        lines.append("### Checklist (from session)")
        lines.append("")
        lines.append("- Test: ANCOVA (IO)")
        lines.append(f"- n_unit: `{n_unit}`")
        lines.append(f"- Assumption checks requested: SW=`{sw_on}`, Levene=`{lev_on}`")
        if isinstance(cfg, dict):
            lines.append(f"- Primary contrast: `{cfg.get('primary_contrast')}`")
            lines.append(f"- X / Y: `{cfg.get('x_col')}` / `{cfg.get('y_col')}`")
            lines.append(f"- force0: `{bool(cfg.get('force_through_zero'))}`")
            lines.append(f"- p_interaction: {_figure_text_pstr(cfg.get('p_interaction', cfg.get('slope_p')))}")
            lines.append(f"- p_group_ancova: {_figure_text_pstr(cfg.get('p_group_ancova'))}")
            ass = cfg.get("assumptions") or {}
            if ass.get("sw_p") is not None:
                lines.append(f"- SW residual p: {_figure_text_pstr(ass.get('sw_p'))}")
            if ass.get("levene_p") is not None:
                lines.append(f"- Levene residual p: {_figure_text_pstr(ass.get('levene_p'))}")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # Formal non-IO tests
    test_prose = _figure_text_test_prose(test_type, variant, tails, fdr)
    qty_note = ""
    if exp_type == "PP" or (
        results
        and isinstance(results[0], dict)
        and isinstance((results[0].get("config") or {}).get("quantity"), str)
        and "PPR" in (results[0].get("config") or {}).get("quantity", "")
    ):
        qty_note = (
            " Each unit value is the mean **paired-pulse ratio (PPR = stim2/stim1)** "
            "over the analysis window (all sweeps if no test set)."
        )
    stat_sentences = [
        f"{test_prose} at the **{n_unit}** level.{qty_note}",
    ]

    prefer_q = fdr
    set_clauses = []
    for res in results:
        if not isinstance(res, dict):
            continue
        set_name = res.get("set_name") or res.get("set_id") or "comparison"
        if set_name in ("__io_ancova__",):
            continue
        sweeps = res.get("sweeps") or []
        sweep_note = ""
        if sweeps:
            try:
                sweep_note = f" (sweeps {int(min(sweeps))}–{int(max(sweeps))})"
            except Exception:
                sweep_note = ""

        p_amp, p_slope = res.get("p_amp"), res.get("p_slope")
        q_amp, q_slope = res.get("q_amp"), res.get("q_slope")
        n1, n2 = res.get("n1"), res.get("n2")
        n_bit = ""
        if n1 is not None and n2 is not None and n1 != n2:
            n_bit = f"; *n* = {n1} vs {n2}"
        elif n1 is not None:
            n_bit = f"; *n* = {n1}"

        aspects = []
        ppr_prefix = "PPR of " if exp_type == "PP" else ""
        if amp_on and isinstance(p_amp, (int, float)) and np.isfinite(p_amp):
            lab = "*q*" if prefer_q and isinstance(q_amp, (int, float)) else "*p*"
            aspects.append(
                f"{ppr_prefix}EPSP amplitude {lab} = {_figure_text_pstr(p_amp, q_amp, prefer_q=prefer_q)}"
            )
        if slope_on and isinstance(p_slope, (int, float)) and np.isfinite(p_slope):
            lab = "*q*" if prefer_q and isinstance(q_slope, (int, float)) else "*p*"
            aspects.append(
                f"{ppr_prefix}EPSP slope {lab} = {_figure_text_pstr(p_slope, q_slope, prefer_q=prefer_q)}"
            )
        # Generic p_* keys (ANOVA multi-aspect etc.)
        if not aspects:
            for key in sorted(k for k in res.keys() if k.startswith("p_")):
                aspect = key[2:].replace("_", " ")
                if exp_type == "PP" and not aspect.upper().startswith("PPR"):
                    aspect = f"PPR {aspect}"
                qkey = "q_" + key[2:]
                val = res.get(key)
                qv = res.get(qkey)
                if isinstance(val, (int, float)) and np.isfinite(val):
                    lab = "*q*" if prefer_q and isinstance(qv, (int, float)) else "*p*"
                    aspects.append(f"{aspect} {lab} = {_figure_text_pstr(val, qv, prefer_q=prefer_q)}")

        if aspects:
            set_clauses.append(f"**{set_name}**{sweep_note}: " + "; ".join(aspects) + n_bit + ".")
        elif n_bit:
            set_clauses.append(f"**{set_name}**{sweep_note}{n_bit}.")

    if set_clauses:
        stat_sentences.append(" ".join(set_clauses))
    else:
        stat_sentences.append("See session checklist for per-comparison *p*-values.")

    eta_bits = []
    for r in results:
        if isinstance(r, dict) and isinstance(r.get("eta2"), (int, float)) and r["eta2"] > 0:
            eta_bits.append(f"η² = {r['eta2']:.2f}")
    if eta_bits:
        stat_sentences.append("Effect size: " + "; ".join(eta_bits) + ".")

    lines.append(" ".join(stat_sentences))
    lines.append("")

    # Self-contained SW / Levene section (no statusbar/console referral)
    from brainwash_ui import statusbar as statusbar_fmt

    ass_report = statusbar_fmt.format_formal_assumption_report(
        results, test_sw=sw, test_levene=levene, group_names=group_map
    )
    if ass_report or sw or levene:
        lines.append("### Assumption checks")
        lines.append("")
        if ass_report:
            lines.append(ass_report)
        else:
            lines.append("No Shapiro–Wilk or Levene checks were requested for this export.")
        lines.append("")

    lines.append("### Symbols")
    lines.append("")
    if fdr:
        lines.append(
            "\\* *q* < 0.05, \\*\\* *q* < 0.01, \\*\\*\\* *q* < 0.001 (FDR-adjusted); ns = not significant."
        )
    else:
        lines.append("\\* *p* < 0.05, \\*\\* *p* < 0.01, \\*\\*\\* *p* < 0.001; ns = not significant.")
    lines.append("")
    lines.append("### Checklist (from session)")
    lines.append("")
    lines.append(f"- Experiment type: `{exp_type}`")
    lines.append(f"- Test: `{test_type}` (variant=`{variant}`, tails=`{tails}`, FDR=`{fdr}`)")
    lines.append(f"- n_unit: `{n_unit}`")
    lines.append(f"- Aspects: amp=`{amp_on}`, slope=`{slope_on}`, norm=`{norm}`")
    lines.append(f"- Assumption checks requested: SW=`{sw}`, Levene=`{levene}`")
    if group_map:
        gbits = []
        for g, v in group_map.items():
            nm = v.get("group_name") if isinstance(v, dict) else v
            if nm and f"{g}={nm}" not in gbits:
                gbits.append(f"{g}={nm}")
        lines.append(f"- Groups: {', '.join(gbits)}")
    for res in results:
        if not isinstance(res, dict):
            continue
        sid = res.get("set_name") or res.get("set_id") or "?"
        pbits = []
        for key in sorted(k for k in res.keys() if k.startswith("p_")):
            pbits.append(f"{key}={_figure_text_pstr(res.get(key))}")
            qk = "q_" + key[2:]
            if res.get(qk) is not None:
                pbits.append(f"{qk}={_figure_text_pstr(res.get(qk))}")
        for key in sorted(k for k in res.keys() if k.startswith("sw_p") or k.startswith("levene_p")):
            pbits.append(f"{key}={_figure_text_pstr(res.get(key))}")
        for key in sorted(k for k in res.keys() if k.startswith("sw_skip_") or k.startswith("levene_skip_")):
            pbits.append(f"{key}={res.get(key)}")
        nbit = ""
        if res.get("n1") is not None:
            nbit = f", n1={res.get('n1')}, n2={res.get('n2')}"
        lines.append(f"- Set `{sid}`: " + (", ".join(pbits) if pbits else "no p-keys") + nbit)
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":

    class MockUIState:
        def __init__(self):
            self.checkBox = {"norm_EPSP": False, "EPSP_amp": True, "EPSP_slope": True}
            self.settings = {
                "rgb_EPSP_amp": (0, 0, 1),
                "rgb_EPSP_slope": (1, 0, 0),
            }
            self.dict_group_labels = {}
            self.dict_group_show = {str(i): {"group_ID": i} for i in range(1, 3)}
            self.formal_test_results = [
                {"set_name": "set1", "p_amp": 0.01, "p_slope": 0.04, "n1": 5, "n2": 5, "sweeps": [1, 2, 3]},
                {"set_name": "set2", "p_amp": 0.001, "p_slope": 0.06, "n1": 6, "n2": 6, "sweeps": [4, 5, 6]},
            ]
            self.test_type = "t-test"
            self.test_t_variant = "unpaired"
            self.test_fdr = False
            self.darkmode = False
            self.experiment_type = "time"
            self.io_input = "vamp"
            self.io_output = "EPSPamp"

        def x_axis_xlabel(self):
            return "Time (s)"

    mock_uistate = MockUIState()

    # Setup mock data for both amp (ax1) and slope (ax2) so both panels render
    fig, ax = plt.subplots()
    x = [1, 2, 3]
    y = [2, 3, 4]
    yerr = [0.1, 0.2, 0.1]
    (line_amp,) = ax.plot(x, y, label="amp")
    fill_amp = ax.fill_between(
        x,
        [yi - ye for yi, ye in zip(y, yerr)],
        [yi + ye for yi, ye in zip(y, yerr)],
    )
    mock_uistate.plot.dict_group_labels["Group 1 EPSP amp mean"] = {
        "group_ID": 1,
        "axis": "ax1",
        "line": line_amp,
        "fill": fill_amp,
    }
    mock_uistate.plot.dict_group_show["Group 1 EPSP amp mean"] = mock_uistate.plot.dict_group_labels["Group 1 EPSP amp mean"]

    (line_slope,) = ax.plot(x, [y_i * 0.5 for y_i in y], color="red", label="slope")
    fill_slope = ax.fill_between(
        x,
        [yi * 0.5 - ye for yi, ye in zip(y, yerr)],
        [yi * 0.5 + ye for yi, ye in zip(y, yerr)],
        color="red",
        alpha=0.3,
    )
    mock_uistate.plot.dict_group_labels["Group 2 EPSP slope mean"] = {
        "group_ID": 2,
        "axis": "ax2",
        "line": line_slope,
        "fill": fill_slope,
    }
    mock_uistate.plot.dict_group_show["Group 2 EPSP slope mean"] = mock_uistate.plot.dict_group_labels["Group 2 EPSP slope mean"]

    template = JOURNAL_TEMPLATES["jneurosci_1col"]
    try:
        figures = render_publication_figure(mock_uistate, None, template, ["1", "2"])
        print(f"Success! Returned figures: {list(figures.keys())}")

        export_dir = Path.home() / "Documents" / "Brainwash Projects" / "Export"
        export_dir.mkdir(exist_ok=True)
        for name, fig in figures.items():
            out_path = export_dir / f"test_jneurosci_1col_{name}.png"
            fig.savefig(out_path, dpi=template.dpi, bbox_inches="tight")
            print(f"Saved {out_path}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        plt.close("all")
    print("Test completed. Check exported PNGs for correct * / ** markers (amp=low **, slope=high * per latest per-panel fix).")
