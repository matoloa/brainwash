from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt


@dataclass
class JournalTemplate:
    name: str
    # Figure dimensions in mm (converted to inches for matplotlib)
    width_mm: float
    height_mm: float
    # Font
    font_family: str = "Arial"
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
    "jneurosci_1col": JournalTemplate(name="JNeurosci (1 col)", width_mm=85, height_mm=60),
    "jneurosci_2col": JournalTemplate(name="JNeurosci (2 col)", width_mm=174, height_mm=120),
    "jphysiol_1col": JournalTemplate(name="JPhysiol (1 col)", width_mm=85, height_mm=65),
    "jphysiol_2col": JournalTemplate(name="JPhysiol (2 col)", width_mm=174, height_mm=130),
    "nature_1col": JournalTemplate(name="Nature (1 col)", width_mm=89, height_mm=65),
    "nature_2col": JournalTemplate(name="Nature (2 col)", width_mm=183, height_mm=130),
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
        is_io_mode = getattr(uistate, "experiment_type", "time") == "io"
        is_pp_mode = getattr(uistate, "experiment_type", "time") == "PP"
        if is_pp_mode:
            panels_to_render = [asp for asp in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"] if uistate.checkBox.get(asp, True)]
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
                for y_val in [1.0, 2.0, 3.0]:
                    ax.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)
            elif uistate.checkBox.get("norm_EPSP"):
                if panel == "amp":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.settings.get("rgb_EPSP_amp", "black"),
                    )
                elif panel == "slope":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.settings.get("rgb_EPSP_slope", "black"),
                    )
                elif panel == "io":
                    io_output = getattr(uistate, "io_output", "EPSPamp")
                    y_col_base = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.settings.get(f"rgb_{y_col_base}", "black"),
                    )

            # Re-plot data by identifying relevant lines from the existing interactive axes
            # We fetch data directly from the plotted group lines in uistate
            # to mirror exactly what was calculated, applying only new styling.
            has_data = False
            for label, info in uistate.dict_group_labels.items():
                group_id_str = str(info["group_ID"])
                # We only plot if the group ID is in selected_groups
                if group_id_str not in [str(g) for g in selected_groups]:
                    continue

                # Only plot lines that are currently toggled visible in the UI
                if label not in uistate.dict_group_show:
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
                    bar_info = uistate.dict_group_labels.get(bar_label)
                    if bar_info and hasattr(bar_info.get("line"), "patches") and len(bar_info["line"].patches) > 0:
                        p = bar_info["line"].patches[0]
                        orig_base_x = p.get_x() + p.get_width() / 2
                        shift = round(orig_base_x) - orig_base_x

                    if hasattr(line, "patches"):  # BarContainer
                        xdata = [round(p.get_x() + p.get_width() / 2) for p in line.patches]
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
                        aspect = info.get("aspect", "")
                        if "slope" in aspect.lower():
                            ax.set_ylabel(f"EPSP Slope %" if uistate.checkBox.get("norm_EPSP") else f"EPSP Slope (mV/ms)")
                        else:
                            ax.set_ylabel(f"EPSP Amplitude %" if uistate.checkBox.get("norm_EPSP") else f"EPSP Amplitude (mV)")
                        has_data = True
                    else:
                        continue
                else:
                    if panel == "amp" and axis_src == "ax1":
                        ax.set_ylabel("Amplitude %" if uistate.checkBox.get("norm_EPSP") else "Amplitude (mV)")
                        has_data = True
                    elif panel == "slope" and axis_src == "ax2":
                        ax.set_ylabel("Slope %" if uistate.checkBox.get("norm_EPSP") else "Slope (mV/ms)")
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
                    xdata = line.get_xdata().copy()
                    ydata = line.get_ydata().copy()

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
                    group_name_to_x = {}
                    for label, info in uistate.dict_group_labels.items():
                        if info.get("aspect") == panel and hasattr(info.get("line"), "patches"):
                            if "overlay" in label or info.get("is_overlay"):
                                continue
                            try:
                                patches = info["line"].patches
                                if patches:
                                    x_pos_float = patches[0].get_x() + patches[0].get_width() / 2
                                    x_pos_int = round(x_pos_float)
                                    group_name = label.split(" PPR")[0]
                                    group_name_to_x[x_pos_int] = group_name
                            except:
                                pass
                    x_ticks = sorted(list(group_name_to_x.keys()))
                    x_ticklabels = [group_name_to_x[x] for x in x_ticks]
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
                if show_inset and hasattr(uistate, "sample_inset") and uistate.sample_inset is not None and uistate.sample_inset.get_visible():
                    export_inset = ax.inset_axes([0.02, 0.68, 0.20, 0.30])
                    export_inset.set_zorder(10)
                    export_inset.set_facecolor((0, 0, 0, 0))
                    export_inset.patch.set_alpha(0.0)
                    for spine in export_inset.spines.values():
                        spine.set_visible(False)
                    export_inset.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
                    export_inset.set_axis_off()

                    all_ys = []
                    for key, line in getattr(uistate, "sample_artists", {}).items():
                        if len(key) == 3:
                            group_ID, test_id, stim_num = key
                        else:
                            continue

                        if str(group_ID) not in [str(g) for g in selected_groups]:
                            continue
                        if not line.get_visible():
                            continue

                        x_data = line.get_xdata()
                        y_data = line.get_ydata()
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

                fig.tight_layout()
                if panel == "io":
                    io_input = getattr(uistate, "io_input", "vamp")
                    io_output = getattr(uistate, "io_output", "EPSPamp")
                    panel_key = f"{io_input}-{io_output}"
                else:
                    panel_key = panel_name_map.get(panel, panel)
                figures[panel_key] = fig

    return figures


if __name__ == "__main__":

    class MockUIState:
        def __init__(self):
            self.checkBox = {"norm_EPSP": False}
            self.settings = {
                "rgb_EPSP_amp": (0, 0, 1),
                "rgb_EPSP_slope": (1, 0, 0),
            }
            self.dict_group_labels = {}
            self.dict_group_show = {}
            self.experiment_type = "io"
            self.io_input = "vamp"
            self.io_output = "EPSPamp"

        def x_axis_xlabel(self):
            return "Time (s)"

    mock_uistate = MockUIState()

    fig, ax = plt.subplots()
    x = [1, 2, 3]
    y = [2, 3, 4]
    yerr = [0.1, 0.2, 0.1]
    (line,) = ax.plot(x, y)
    fill = ax.fill_between(
        x,
        [yi - ye for yi, ye in zip(y, yerr)],
        [yi + ye for yi, ye in zip(y, yerr)],
    )

    mock_uistate.dict_group_labels["Group 1 EPSP amp mean"] = {
        "group_ID": 1,
        "axis": "ax1",
        "line": line,
        "fill": fill,
    }
    mock_uistate.dict_group_show["Group 1 EPSP amp mean"] = mock_uistate.dict_group_labels["Group 1 EPSP amp mean"]

    scatter = ax.scatter([1, 2, 3], [1.5, 2.5, 3.5], color="red")
    (trendline,) = ax.plot([1, 3], [1.5, 3.5], color="red", linestyle="--")

    mock_uistate.dict_group_labels["Group 2 raw IO scatter"] = {"group_ID": 2, "axis": "ax2", "line": scatter, "fill": None, "x_mode": "io"}
    mock_uistate.dict_group_show["Group 2 raw IO scatter"] = mock_uistate.dict_group_labels["Group 2 raw IO scatter"]

    mock_uistate.dict_group_labels["Group 2 raw IO trendline"] = {"group_ID": 2, "axis": "ax2", "line": trendline, "fill": None, "x_mode": "io"}
    mock_uistate.dict_group_show["Group 2 raw IO trendline"] = mock_uistate.dict_group_labels["Group 2 raw IO trendline"]

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
