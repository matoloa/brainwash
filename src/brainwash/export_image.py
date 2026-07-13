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
) -> None:
    """
    Draw significance markers (*, **, ***, ns) on an export Axes.
    Mirrors the logic in ui_plot.py::show_test_markers but operates on a plain Axes
    and JournalTemplate (no live interactive axes or blended transforms).
    """
    if not results:
        return

    # Determine if this is a single-marker variant (paired/one-sample)
    is_single_marker = variant in ("paired", "one-sample") and len(results) >= 2

    # Sweep-range bracket (journal convention): horizontal line + short vertical ticks
    # at min(sweeps) to max(sweeps). Sits ~1-2 pt below marker. Uses linewidth_axes.

    for idx, res in enumerate(results):
        sweeps = res.get("sweeps", []) or []
        if not sweeps:
            continue
        try:
            x = float(np.mean(sweeps))
        except Exception:
            continue

        # Paired/one-sample: single centered marker between first and second set
        if is_single_marker:
            if idx != 0:
                continue
            try:
                sweeps2 = results[1].get("sweeps", []) or []
                x2 = float(np.mean(sweeps2))
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
                    x_min = float(min(sweeps))
                    x_max = float(max(sweeps))
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
            panels_to_render = [asp for asp in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"] if uistate.project.checkBox.get(asp, True)]
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

                # Pre-extract color safely so PP mode can use it
                if hasattr(line, "patches") and len(line.patches) > 0:
                    group_color = line.patches[0].get_facecolor()
                elif hasattr(line, "get_color"):
                    group_color = line.get_color()
                elif hasattr(line, "get_facecolors") and len(line.get_facecolors()) > 0:
                    group_color = line.get_facecolors()[0]
                else:
                    group_color = "black"

                if is_pp_mode:
                    if info.get("aspect") != panel:
                        continue
                    if "overlay" in label:
                        continue  # Do not export overlays
                    aspect_str = panel.replace("_", " ").replace("amp", "amplitude")
                    ax.set_ylabel(f"PPR ({aspect_str})")
                    has_data = True

                    # Calculate offset to center elements back on their base integer group tick
                    shift = 0
                    bar_label = f"{label.split(' PPR')[0]} PPR {info.get('aspect')} bar"
                    bar_info = uistate.plot.dict_group_labels.get(bar_label)
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
                        if "overlay" in label or info.get("is_overlay"):
                            continue
                        line_obj = info.get("line")
                        if not hasattr(line_obj, "patches"):
                            continue
                        try:
                            patches = line_obj.patches
                            if patches:
                                p = patches[0]
                                bar_specs.append((p.get_x(), p.get_width(), label.split(" PPR")[0]))
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
                    ax.set_xlabel(uistate.x_axis_xlabel() if hasattr(uistate, "x_axis_xlabel") else "Time")

                handles, labels = ax.get_legend_handles_labels()
                if labels:
                    by_label = dict(zip(labels, handles))
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

                # Add significance markers if formal test results are present
                formal_results = uistate.stat_test.formal_test_results
                if formal_results:
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


def build_figure_text_md(uistate, template, group_names=None) -> str:
    """Pure helper (Phase 1+): returns journal-ready figure text/caption for .md companion file.
    Called from triggerExportOutputImage (the typewriter per revised plan). Reuses parsing
    patterns from _get_stat_test_warning (ui.py) and _add_significance_markers.
    Per-panel .md strategy (Option A): one .md per PNG with matching base name.
    """
    if not uistate or uistate.stat_test.test_type == "None":
        return "(Exported without statistical comparison overlay.)"

    test_type = uistate.stat_test.test_type
    results = uistate.stat_test.formal_test_results or []
    if not results:
        return "(Exported without statistical comparison overlay.)"

    # Extract config (defensive, mirrors ui.py/_get_stat_test_warning)
    fdr = bool(uistate.stat_test.test_fdr)
    variant = uistate.stat_test.test_t_variant
    if test_type == "Wilcoxon":
        variant = uistate.stat_test.test_wilcox_variant
    tails = uistate.stat_test.test_t_tails if test_type != "Wilcoxon" else uistate.stat_test.test_wilcox_tails
    sw = bool(uistate.stat_test.test_sw)
    levene = bool(uistate.stat_test.test_levene)
    norm = bool(uistate.project.checkBox.get("norm_EPSP", False))
    amp_enabled = bool(uistate.project.checkBox.get("EPSP_amp", True))
    slope_enabled = bool(uistate.project.checkBox.get("EPSP_slope", True))

    # Group names (fallback to set_name or generic)
    group_map = group_names or {}
    if not group_map and hasattr(uistate, "dict_group_labels"):
        for k, v in uistate.plot.dict_group_labels.items():
            if isinstance(v, dict) and "group_name" in v:
                group_map[str(v.get("group_ID", ""))] = v["group_name"]

    # Build core summary (reuses statusbar logic patterns; publication-polished)
    parts = []
    if test_type == "t-test":
        if variant == "paired":
            prefix = "Paired two-sided t-test"
        elif variant == "one-sample":
            prefix = "One-sample two-sided t-test"
        else:
            prefix = "Unpaired two-sided t-test"
        if fdr:
            prefix += " with FDR correction"
        if tails != "two-sided":
            prefix = prefix.replace("two-sided", tails)
        parts.append(prefix)
    elif test_type == "Wilcoxon":
        if variant == "paired":
            prefix = "Paired two-sided Wilcoxon signed-rank test"
        elif variant == "one-sample":
            prefix = "One-sample two-sided Wilcoxon signed-rank test"
        else:
            prefix = "Unpaired two-sided Wilcoxon rank-sum test"
        if fdr:
            prefix += " with FDR correction"
        if tails != "two-sided":
            prefix = prefix.replace("two-sided", tails)
        parts.append(prefix)
    elif test_type == "ANOVA":
        parts.append("Repeated-measures ANOVA (omnibus)")
    elif test_type == "Friedman":
        parts.append("Friedman test (repeated-measures omnibus)")
    elif test_type == "Cluster perm.":
        parts.append("Cluster permutation test (between-subjects)")
    else:
        parts.append(test_type)

    # Aspect-specific p-values + n (only enabled aspects; per result/set)
    # Matches statusbar logic + plan examples
    aspect_parts = []
    for res in results:
        set_name = res.get("set_name", res.get("set_id", "set"))
        n1 = res.get("n1", 0)
        n2 = res.get("n2", n1)
        n_str = f"n={n1}" if n1 == n2 else f"n1={n1}, n2={n2}"

        p_amp = res.get("p_amp")
        p_slope = res.get("p_slope")
        q_amp = res.get("q_amp")
        q_slope = res.get("q_slope")

        def pstr(p, q=None):
            val = q if (isinstance(q, (int, float)) and np.isfinite(q)) else p
            if not isinstance(val, (int, float)) or not np.isfinite(val):
                return "NA"
            if val < 0.001:
                return "<0.001"
            return f"{val:.3g}"

        shown_aspects = []
        if amp_enabled and isinstance(p_amp, (int, float)):
            shown_aspects.append(f"amp p={pstr(p_amp, q_amp)}")
        if slope_enabled and isinstance(p_slope, (int, float)):
            shown_aspects.append(f"slope p={pstr(p_slope, q_slope)}")
        if shown_aspects:
            aspect_parts.append(f"{set_name}: {', '.join(shown_aspects)} ({n_str})")

    if aspect_parts:
        parts.append("; ".join(aspect_parts))

    # Effect size / diagnostics (tiered by template.width_mm per Phase 3; reuse statusbar notes)
    eta_parts = []
    for r in results:
        if isinstance(r.get("eta2"), (int, float)) and r["eta2"] > 0:
            eta_parts.append(f"η²={r['eta2']:.2f}")
    if eta_parts:
        parts.extend(eta_parts)

    notes = []
    if fdr:
        notes.append("FDR")
    if sw:
        notes.append("SW")
    if levene:
        notes.append("Levene")
    if notes:
        parts.append("({})".format(", ".join(notes)))

    # Significance legend (journal standard; matches _add_significance_markers)
    parts.append("*p<0.05, **p<0.01, ***p<0.001")

    text = ". ".join([p for p in parts if p]) + "."
    # Journal tier (Phase 3): shorter for 1-col templates
    if getattr(template, "width_mm", 100) < 90 and len(text) > 100:
        text = text.replace("Repeated-measures ANOVA (omnibus)", "RM-ANOVA (omnibus)").replace("; ", ". ")[:95] + "."

    return text


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
