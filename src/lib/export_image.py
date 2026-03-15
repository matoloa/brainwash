from dataclasses import dataclass, field
from typing import Literal

import matplotlib
import matplotlib.figure


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
    # DPI for raster outputs
    dpi: int = 600
    # Which panels to include
    panels: list[Literal["event", "amp", "slope", "mean"]] = field(
        default_factory=lambda: ["event", "amp", "slope"]
    )
    # Layout: "vertical" (stacked) or "horizontal" (side by side)
    layout: Literal["vertical", "horizontal"] = "vertical"


JOURNAL_TEMPLATES: dict[str, JournalTemplate] = {
    "jneurosci_1col": JournalTemplate(
        name="JNeurosci (1 col)", width_mm=85, height_mm=60
    ),
    "jneurosci_2col": JournalTemplate(
        name="JNeurosci (2 col)", width_mm=174, height_mm=120
    ),
    "jphysiol_1col": JournalTemplate(
        name="JPhysiol (1 col)", width_mm=85, height_mm=65
    ),
    "jphysiol_2col": JournalTemplate(
        name="JPhysiol (2 col)", width_mm=174, height_mm=130
    ),
    "nature_1col": JournalTemplate(name="Nature (1 col)", width_mm=89, height_mm=65),
    "nature_2col": JournalTemplate(name="Nature (2 col)", width_mm=183, height_mm=130),
}


def render_publication_figure(
    uistate,
    uiplot,
    template: JournalTemplate,
    selected_groups: list[str],
    group_names: dict[str, str] = None,
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
        for panel in template.panels:
            # Create a fresh figure for each panel using the provided template dimensions
            fig = matplotlib.figure.Figure(
                figsize=(template.width_mm / 25.4, template.height_mm / 25.4),
                dpi=template.dpi,
            )

            ax = fig.add_subplot(111)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            if uistate.checkBox.get("norm_EPSP"):
                if panel == "amp":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.settings["rgb_EPSP_amp"],
                    )
                elif panel == "slope":
                    ax.axhline(
                        100,
                        linestyle="dotted",
                        alpha=0.3,
                        color=uistate.settings["rgb_EPSP_slope"],
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

                # Check if this line corresponds to the current panel
                if panel == "amp" and axis_src == "ax1":
                    ax.set_ylabel(
                        "Amplitude %"
                        if uistate.checkBox.get("norm_EPSP")
                        else "Amplitude (mV)"
                    )
                elif panel == "slope" and axis_src == "ax2":
                    ax.set_ylabel(
                        "Slope %"
                        if uistate.checkBox.get("norm_EPSP")
                        else "Slope (mV/ms)"
                    )
                else:
                    # Ignore event/mean panels for now unless they match the source axis
                    # Future expansion could handle axm/axe
                    continue

                has_data = True
                xdata = line.get_xdata()
                ydata = line.get_ydata()
                color = line.get_color()

                plot_label = (
                    group_names.get(group_id_str, label) if group_names else label
                )

                yerr = None
                if fill and len(fill.get_paths()) > 0:
                    verts = fill.get_paths()[0].vertices
                    yerr = []
                    for xi in xdata:
                        y_vals = [v[1] for v in verts if abs(v[0] - xi) < 1e-5]
                        if y_vals:
                            yerr.append((max(y_vals) - min(y_vals)) / 2)
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
                        capsize=0,
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
                ax.set_xlabel(
                    uistate.x_axis_xlabel()
                    if hasattr(uistate, "x_axis_xlabel")
                    else "Time"
                )

                if ax.get_legend_handles_labels()[1]:
                    ax.legend(frameon=False)

                fig.tight_layout()
                panel_key = panel_name_map.get(panel, panel)
                figures[panel_key] = fig

    return figures
