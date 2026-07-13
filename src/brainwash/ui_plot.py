import time  # counting time for functions
import warnings

from brainwash_ui import plot_drag, plot_model, plot_series, plot_stim, plot_testsets

import matplotlib.pyplot as plt  # for the scatterplot
import numpy as np
import pandas as pd
from collections import defaultdict

# import seaborn as sns
from matplotlib import style
from matplotlib.colors import LinearSegmentedColormap

# from matplotlib.lines import Line2D  # for custom legend; TODO: still used?
from matplotlib.ticker import FuncFormatter
from matplotlib.transforms import blended_transform_factory

STIM_MARKER_SIZE = 10  # diameter in points; drives both rendering and hit-zone calculation


class UIplot:
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated: {self.uistate.anyView()}")

    def heatmap(self, df):
        ax1 = self.uistate.plot.ax1
        ax2 = self.uistate.plot.ax2

        if not hasattr(self.uistate.plot, "dict_heatmap"):
            self.uistate.plot.dict_heatmap = {}

        sweeps = df["sweep"].values
        pcols = [c for c in df.columns if c.startswith("p_")]

        for col in pcols:
            ps = df[col].values
            axis_id = plot_model.heatmap_axis_for_column(col)
            if axis_id is None:
                continue
            ax = ax1 if axis_id == "ax1" else ax2
            ymin, ymax = ax.get_ylim()
            y = ymin + (ymax - ymin) * plot_model.heatmap_y_fraction(col)

            for x, p in plot_model.significant_heatmap_points(sweeps, ps):
                color, alpha = plot_model.p_value_color_alpha(p)
                sc = ax.scatter([x], [y], marker="o", color=[color], alpha=alpha)
                self.uistate.plot.dict_heatmap.setdefault(col, {})[x] = sc

        ax1.figure.canvas.draw_idle()
        ax2.figure.canvas.draw_idle()

    def heatunmap(self):
        d = self.uistate.plot.dict_heatmap
        if not d:
            return
        ax = self.uistate.plot.ax1
        # print(f"heatunmap: {d}")
        for col in list(d.keys()):
            for x, sc in list(d[col].items()):
                try:
                    sc.remove()
                except:
                    pass
            d[col].clear()

        d.clear()
        ax.figure.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Formal statistical test markers (v0.16) — independent of Heatmap
    # ------------------------------------------------------------------

    def show_test_markers(self, results):
        """Draw significance markers for formal t-test results on Test Sets.
        - x-position: center (mean) of the test set sweeps.
        - Convention (matches legend): amp high (top), slope low (bottom) when both shown;
          single-aspect view places that aspect high (top-right).
        - By convention: "*" for p/q < 0.05, "**" < 0.01, "***" < 0.001; "ns" otherwise.
          Uses the q-value for the level if FDR was applied, else the raw p-value.
        - Marker is white in darkmode, black otherwise (bare text, no box/background).
        - "ns" uses a muted gray appropriate for the current mode.
        For paired t-test: shows exactly one marker (centered between the two test sets).
        Otherwise shows one label per computed aspect per shown test set.
        Uses uistate.plot.dict_test_markers for storage (values are Text artists).
        """
        ax1 = self.uistate.plot.ax1
        ax2 = self.uistate.plot.ax2
        if ax1 is None or ax2 is None:
            return

        if not hasattr(self.uistate.plot, "dict_test_markers"):
            self.uistate.plot.dict_test_markers = {}

        d = self.uistate.plot.dict_test_markers
        self.clear_test_markers(draw=False)

        st = self.uistate.stat_test
        specs = plot_model.build_test_marker_specs(
            results,
            test_type=st.test_type,
            t_variant=st.test_t_variant,
            wilcox_variant=st.test_wilcox_variant,
            amp_view=self.uistate.ampView(),
            slope_view=self.uistate.slopeView(),
            dark=bool(self.uistate.darkmode),
        )
        axes = {"ax1": ax1, "ax2": ax2}
        for spec in specs:
            target_ax = axes.get(spec.axis)
            if target_ax is None:
                continue
            try:
                trans = blended_transform_factory(target_ax.transData, target_ax.transAxes)
                txt = target_ax.text(
                    spec.x,
                    spec.y_frac,
                    spec.label,
                    transform=trans,
                    ha="center",
                    va=spec.va,
                    fontsize=13,
                    fontweight="bold",
                    color=spec.color,
                    zorder=12,
                )
                d.setdefault(spec.storage_pcol, {})[spec.x] = txt
            except Exception:
                pass

        try:
            ax1.figure.canvas.draw_idle()
            ax2.figure.canvas.draw_idle()
        except Exception:
            pass

    def clear_test_markers(self, draw=True):
        d = self.uistate.plot.dict_test_markers
        if not d:
            return
        for col in list(d.keys()):
            for x, sc in list(d[col].items()):
                try:
                    sc.remove()
                except Exception:
                    pass
            d[col].clear()
        d.clear()
        if draw:
            try:
                self.uistate.plot.ax1.figure.canvas.draw_idle()
                self.uistate.plot.ax2.figure.canvas.draw_idle()
            except Exception:
                pass

    def create_barplot(self, dict_group_color_ratio_SEM, str_aspect, output_path):
        plt.figure(figsize=(6, 6))
        group_names = []
        ratios = []
        SEMs = []
        colors = []

        # Extract information from the dictionary
        for group, (color, ratio, group_SEM) in dict_group_color_ratio_SEM.items():
            group_names.append(group)
            ratios.append(ratio)
            SEMs.append(group_SEM)
            colors.append(color)

        # Increase the font size for all text in the plot
        plt.rcParams.update({"font.size": 14})  # Adjust the size as needed

        # Create the bar plot with narrower bars
        bars = plt.bar(group_names, ratios, color=colors, width=0.4)  # Adjust the width for narrower bars

        # Add error bars (SEM) to each bar
        x_positions = np.arange(len(group_names))  # Get the x positions of the bars
        plt.errorbar(x_positions, ratios, yerr=SEMs, fmt="none", capsize=5, color="black")

        # Add a dashed line at 1
        plt.axhline(y=100, color="black", linestyle="--")

        # Set labels and title with increased font size
        # plt.xlabel('Group', fontsize=16)
        plt.ylabel(f"{str_aspect}, % of stim 1", fontsize=16)
        plt.title("Paired Pulse Ratio (50ms)", fontsize=18)

        # Increase tick labels size
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)

        plt.savefig(output_path)
        plt.close()
        print(f"Saved barplot to {output_path}")

    def create_scatterplot(self, dict_rec_legend_color_df, x_aspect, y_aspect, dd_r_lines, output_path):
        print(f"Creating scatter plot for {len(dict_rec_legend_color_df)} records")
        plt.figure(figsize=(8, 6))

        # Iterate over each record in dict_rec_legend_color_df
        for label, (legend, color, df) in dict_rec_legend_color_df.items():
            plt.scatter(df[x_aspect], df[y_aspect], label=legend, color=color)
            if label in dd_r_lines:
                x, y = dd_r_lines[label]["x"], dd_r_lines[label]["y"]
                plt.plot(x, y, linestyle="--", linewidth=2, color=color)  # Use the same color for regression line

        plt.title(f"Scatter plot of {x_aspect} vs {y_aspect} with Regression Lines")
        plt.xlabel(x_aspect)
        plt.ylabel(y_aspect)

        # Remove duplicate legends
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())

        plt.grid(True)
        plt.savefig(output_path)
        plt.close()
        print(f"Saved scatter plot to {output_path}")

    def xDeselect(self, ax, reset=False, draw=True):
        # clear previous axvlines and axvspans
        ax1, ax2 = self.uistate.plot.ax1, self.uistate.plot.ax2
        if ax == ax1 or ax == ax2:
            axlines = ax1.get_lines() + ax2.get_lines()
            axpatches = ax1.patches + ax2.patches
            if reset:
                self.uistate.plot.x_select["output"] = set()
                self.uistate.plot.x_select["output_start"] = None
                self.uistate.plot.x_select["output_end"] = None
                self.clear_testset_spans(draw=False)  # clear on full output reset per Phase 2
        else:  # axm
            axlines = list(ax.get_lines())
            axpatches = list(ax.patches)
            if reset:
                self.uistate.plot.x_select["mean_start"] = None
                self.uistate.plot.x_select["mean_end"] = None

        for line in axlines:
            if line.get_label().startswith("xSelect"):
                try:
                    line.remove()
                except Exception:
                    pass
        for patch in axpatches:
            if patch.get_label().startswith("xSelect"):
                try:
                    patch.remove()
                except Exception:
                    pass
        if reset:
            self.clear_axe_mean()
            # axe mean artists live on the event canvas (uistate.plot.axe), not necessarily
            # the canvas of the ax that was passed (e.g. right-click deselect on output graph).
            # Force a redraw of axe so removal becomes visible.
            if draw and self.uistate.plot.axe is not None:
                try:
                    self.uistate.plot.axe.figure.canvas.draw_idle()
                except Exception:
                    pass
        if draw:
            ax.figure.canvas.draw_idle()

    def xSelect(self, canvas, draw=True):
        # draws a selected range of x values on <canvas>
        if canvas == self.uistate.plot.axm.figure.canvas:
            ax = self.uistate.plot.axm
            self.xDeselect(ax, draw=False)
            if self.uistate.plot.x_select["mean_start"] is None:
                return
            if self.uistate.plot.x_select["mean_end"] is None:
                # print(f"Selected x: {self.uistate.plot.x_select['mean_start']}")
                ax.axvline(
                    x=self.uistate.plot.x_select["mean_start"],
                    color="blue",
                    label="xSelect_x",
                )
            else:
                start, end = (
                    self.uistate.plot.x_select["mean_start"],
                    self.uistate.plot.x_select["mean_end"],
                )
                # print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color="blue", label="xSelect_start")
                ax.axvline(x=end, color="blue", label="xSelect_end")
                ax.axvspan(start, end, color="blue", alpha=0.1, label="xSelect_span")
        else:  # canvasOutput
            if self.uistate.project.checkBox["EPSP_slope"]:
                ax = self.uistate.plot.ax2
            else:
                ax = self.uistate.plot.ax1
            self.xDeselect(ax, draw=False)  # will clear both ax1 and ax2, if fed either one
            if self.uistate.plot.x_select["output_end"] is None:
                # If only the start is selected, draw a line at the start
                # print(f"Selected x: {self.uistate.plot.x_select['output_start']}")
                ax.axvline(
                    x=self.uistate.plot.x_select["output_start"],
                    color="blue",
                    label="xSelect_x",
                )
            else:
                # If both start and end are selected, draw the range
                start, end = (
                    self.uistate.plot.x_select["output_start"],
                    self.uistate.plot.x_select["output_end"],
                )
                # print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color="blue", label="xSelect_start")
                ax.axvline(x=end, color="blue", label="xSelect_end")
                ax.axvspan(start, end, color="blue", alpha=0.1, label="xSelect_span")

        if draw:
            canvas.draw_idle()

    def clear_axe_mean(self):
        # if uistate.plot.dict_rec_labels exists and contains keys that start with "axe mean selected sweeps", remove their lines and del the items
        if self.uistate.plot.dict_rec_labels:
            for key in [k for k in self.uistate.plot.dict_rec_labels if k.startswith("axe mean selected sweeps")]:
                try:
                    self.uistate.plot.dict_rec_labels[key]["line"].remove()
                except Exception:
                    pass
                try:
                    del self.uistate.plot.dict_rec_labels[key]
                except Exception:
                    pass
        else:
            print(" - - - - No dict_rec_labels to clear mean sweeps from")

    def clear_testset_spans(self, draw=True):
        """Clear all test set axvspan patches (labeled testset_span_*) from output graph (ax1/ax2 only)."""
        if not hasattr(self.uistate.plot, "testset_spans") or not self.uistate.plot.testset_spans:
            if draw and self.uistate.plot.ax1 is not None:
                self.uistate.plot.ax1.figure.canvas.draw_idle()
            return
        for spans in self.uistate.plot.testset_spans.values():
            for patch in spans.values():
                try:
                    patch.remove()
                except Exception:
                    pass
        self.uistate.plot.testset_spans = {}
        if draw and self.uistate.plot.ax1 is not None:
            self.uistate.plot.ax1.figure.canvas.draw_idle()

    def clear_sample_artists(self, draw=True, hide=False):
        """Clear or hide sample overlay artists/inset. hide=True clears the dict (explicit reset on every redraw)."""
        if not hasattr(self.uistate.plot, "sample_artists") or self.uistate.plot.sample_artists is None:
            self.uistate.plot.sample_artists = {}
            if draw and self.uistate.plot.ax1 is not None:
                self.uistate.plot.ax1.figure.canvas.draw_idle()
            return
        if hide and hasattr(self.uistate.plot, "sample_inset") and self.uistate.plot.sample_inset is not None:
            for artist in self.uistate.plot.sample_artists.values():
                try:
                    artist.set_visible(False)
                except Exception:
                    pass
            self.uistate.plot.sample_inset.set_visible(False)
            self.uistate.plot.sample_inset.set_axis_off()
            self.uistate.plot.sample_artists = {}
        else:
            for artist in self.uistate.plot.sample_artists.values():
                try:
                    artist.remove()
                except Exception:
                    pass
            self.uistate.plot.sample_artists = {}
            if hasattr(self.uistate.plot, "sample_inset") and self.uistate.plot.sample_inset is not None:
                try:
                    self.uistate.plot.sample_inset.remove()
                except Exception:
                    pass
                self.uistate.plot.sample_inset = None
        if draw and self.uistate.plot.ax1 is not None:
            self.uistate.plot.ax1.figure.canvas.draw_idle()

    def sample_overlay(self, dd_groups, dd_testset, dd_shown_samples):
        """Only (re)draw inset+traces when sample_dirty or visibility changed.
        Inset created once and reused (visibility + set_data); clear/hide on toggle.
        Supports multiple test sets (solid for first, dashed for second, dotted beyond).
        Callers set dirty flag on group/sample changes."""

        if not hasattr(self.uistate.plot, "sample_dirty"):
            self.uistate.plot.sample_dirty = True
        if not hasattr(self.uistate.plot, "sample_inset"):
            self.uistate.plot.sample_inset = None
        if not hasattr(self.uistate.plot, "sample_artists"):
            self.uistate.plot.sample_artists = {}

        should_show = plot_testsets.sample_overlay_should_show(dd_shown_samples)

        if self.uistate.plot.sample_inset is None:
            if self.uistate.plot.ax1 is None or not should_show:
                return
            self.uistate.plot.sample_inset = self.uistate.plot.ax1.inset_axes(list(plot_testsets.SAMPLE_INSET_BOUNDS))
            self.uistate.plot.sample_inset.set_zorder(10)
            inset = self.uistate.plot.sample_inset
            inset.set_facecolor((0, 0, 0, 0))
            inset.patch.set_alpha(0.0)
            for spine in inset.spines.values():
                spine.set_visible(False)
            inset.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
            inset.set_axis_off()

        inset = self.uistate.plot.sample_inset

        if not should_show:
            if inset.get_visible():
                self.clear_sample_artists(draw=False, hide=True)
                self.uistate.plot.sample_dirty = False
            return
        if not self.uistate.plot.sample_dirty and inset.get_visible():
            return

        self.clear_sample_artists(draw=False, hide=True)
        inset.set_visible(True)
        inset.set_zorder(10)
        inset.set_axis_off()
        inset.clear()
        for spine in inset.spines.values():
            spine.set_visible(False)
        inset.tick_params(axis="both", which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
        self.uistate.plot.sample_artists = {}

        if dd_shown_samples is None or not bool(dd_shown_samples):
            self.uistate.plot.sample_dirty = False
            return

        # Force full artist clear (hide=True) on every redraw. This resets the inset
        # completely when visible_test_list changes (adding a testset or toggling any set).
        # This eliminates the "must toggle first set first" quirk.
        self.clear_sample_artists(draw=False, hide=True)

        # Also reset sample_inset visibility and zorder after the full clear.
        # This ensures the inset is always in a clean state when the number of
        # visible test sets changes. Combine with the per-test cache and
        # graphRefresh clears for robust multi-testset sample overlay.
        inset.set_visible(True)
        inset.set_zorder(10)
        inset.set_axis_off()

        filter_col = self.uistate.project.settings.get("filter") or "voltage"
        trace_specs = plot_testsets.build_sample_overlay_trace_specs(
            dd_groups,
            dd_testset,
            dd_shown_samples,
            filter_col=filter_col,
        )
        for spec in trace_specs:
            group_ID, test_id, stim_num = spec.artist_key
            key = spec.artist_key
            if key in self.uistate.plot.sample_artists:
                line = self.uistate.plot.sample_artists[key]
                line.set_data(spec.time, spec.y)
                line.set_linestyle(spec.linestyle)
                line.set_zorder(11)
                line.set_visible(True)
            else:
                (line,) = inset.plot(
                    spec.time,
                    spec.y,
                    color=spec.color,
                    alpha=0.75,
                    linewidth=1.0,
                    linestyle=spec.linestyle,
                    label=f"sample_g{group_ID}_t{test_id}_s{stim_num}",
                    zorder=11,
                )
                self.uistate.plot.sample_artists[key] = line

        ylim = plot_testsets.sample_overlay_ylim(trace_specs)
        if ylim is not None:
            inset.set_ylim(*ylim)
        inset.set_xlim(*plot_testsets.SAMPLE_INSET_XLIM)
        inset.relim()
        inset.autoscale_view(scalex=False)

        self.uistate.plot.sample_dirty = False
        if self.uistate.plot.ax1 is not None:
            self.uistate.plot.ax1.figure.canvas.draw_idle()

    def visualize_test_sets(self, dd_testset, draw=True):
        """Draw gray axvspan for each shown test set on ax1/ax2 (twinx) only.
        Uses min/max of sweeps (assumes continuous/sorted per clarifications).
        Gray with low alpha, no legend entry, stores artists in uistate.plot.testset_spans.
        """
        self.clear_testset_spans(draw=False)
        if not dd_testset or self.uistate.plot.ax1 is None:
            if draw and self.uistate.plot.ax1 is not None:
                self.uistate.plot.ax1.figure.canvas.draw_idle()
            return
        for spec in plot_testsets.testset_span_specs(dd_testset):
            ax = self.get_axis(spec.ax_name)
            if ax is None:
                continue
            span = ax.axvspan(
                spec.start,
                spec.end,
                color=spec.color,
                alpha=spec.alpha,
                label=f"{plot_testsets.TESTSET_SPAN_LABEL_PREFIX}{spec.set_id}",
                zorder=spec.zorder,
            )
            self.uistate.plot.testset_spans.setdefault(spec.set_id, {})[spec.ax_name] = span
        if draw and self.uistate.plot.ax1 is not None:
            self.uistate.plot.ax1.figure.canvas.draw_idle()

    def update_axe_mean(self, draw=True):
        """
        updates the mean of selected sweeps drawn on axe, called by ui.py after:
        * releasing drag on output, selecting sweeps
        * clicking odd/even buttons
        * TODO: writing sweep range in text boxes
        """
        self.clear_axe_mean()
        # if exactly one RECORDING is selected, plot the mean of selected SWEEPS one axe, if any
        if self.uistate.plot.x_select["output"] and len(self.uistate.plot.list_idx_select_recs) == 1:
            idx_rec = self.uistate.plot.list_idx_select_recs[0]
            rec_ID = self.uistate.plot.df_recs2plot.loc[idx_rec, "ID"]
            selected = self.uistate.plot.x_select["output"]
            df_t = self.uistate.plot.df_rec_select_time
            stim_colors = self.get_dict_gradient(len(df_t))
            for spec in plot_stim.build_axe_mean_plot_specs(
                rec_ID,
                selected,
                self.uistate.plot.df_rec_select_data,
                df_t,
                self.uistate.project.settings,
                stim_colors,
            ):
                self.plot_line(
                    spec.label,
                    spec.axid,
                    spec.x,
                    spec.y,
                    spec.color,
                    spec.rec_id,
                    stim=spec.stim,
                    alpha=spec.alpha,
                )
                self.uistate.plot.dict_rec_labels[spec.label]["line"].set_visible(True)
        if draw:
            self.uistate.plot.axe.figure.canvas.draw_idle()

    def styleUpdate(self):
        axm, axe, ax1, ax2 = (
            self.uistate.plot.axm,
            self.uistate.plot.axe,
            self.uistate.plot.ax1,
            self.uistate.plot.ax2,
        )
        colors = plot_model.plot_style_colors(dark=bool(self.uistate.darkmode))
        style.use(colors.mpl_style)
        for ax in [axm, axe, ax1, ax2]:
            ax.figure.patch.set_facecolor(colors.figure_facecolor)
            ax.set_facecolor(colors.axes_facecolor)
            ax.xaxis.label.set_color(colors.label_color)
            ax.yaxis.label.set_color(colors.label_color)
            ax.tick_params(colors=colors.tick_color)

        # 3.4.2: refresh sample overlays after style change (light/dark compatibility)
        if hasattr(self.uistate, "dd_group_samples") and self.uistate.plot.dd_group_samples:
            if hasattr(self.uistate, "refresh_samples"):
                self.uistate.refresh_samples()
            else:
                self.sample_overlay(dd_groups=getattr(self, "dd_groups", None), dd_testset=None, dd_shown_samples=self.uistate.plot.dd_group_samples)
            self.uistate.plot.sample_dirty = True

    def hideAll(self):
        axm, axe, ax1, ax2 = (
            self.uistate.plot.axm,
            self.uistate.plot.axe,
            self.uistate.plot.ax1,
            self.uistate.plot.ax2,
        )
        for ax in [axm, axe, ax1, ax2]:
            if ax is not None:
                lines = ax.get_lines()
                if len(lines) > 0:
                    for line in lines:
                        line.set_visible(False)
                patches = list(ax.patches)
                if len(patches) > 0:
                    for patch in patches:
                        patch.set_visible(False)
                legend = ax.get_legend()
                if legend is not None:
                    legend.remove()
        print("All lines hidden")

    def unPlot(self, rec_ID=None):
        dict_rec = self.uistate.plot.dict_rec_labels
        dict_show = self.uistate.plot.dict_rec_show
        if rec_ID is None:
            keys_to_remove = list(dict_rec.keys())
        else:
            keys_to_remove = [key for key, value in dict_rec.items() if rec_ID == value["rec_ID"]]
        for key in keys_to_remove:
            try:
                dict_rec[key]["line"].remove()
            except Exception:
                pass
            del dict_rec[key]
            if key in dict_show:
                del dict_show[key]
        if rec_ID is None:
            uis = self.uistate
            uis.mouseover_plot = None
            uis.mouseover_blob = None
            uis.mouseover_out = None
            uis.mouseover_action = None
            # Clear formal test markers on full rec clear (test will re-apply on next graphRefresh if active)
            if hasattr(self, "clear_test_markers"):
                self.clear_test_markers(draw=False)
            uis.ghost_sweep = None
            uis.ghost_label = None

    def unPlotGroup(self, group_ID=None, level=None):
        """Remove group artists.

        If level is provided, only remove artists for that specific n_unit level
        (recording/slice/subject). This supports keeping separate artist sets
        per level so we can toggle instead of always destroying/recreating.
        """
        dict_group = self.uistate.plot.dict_group_labels
        dict_group_show = self.uistate.plot.dict_group_show
        if group_ID is None:
            keys_to_remove = list(dict_group.keys())  # Remove all if group_ID is None
            if hasattr(self, "clear_test_markers"):
                self.clear_test_markers(draw=False)
        else:
            keys_to_remove = [key for key, value in dict_group.items() if group_ID == value["group_ID"]]

        if level is not None:
            keys_to_remove = [
                k for k in keys_to_remove
                if dict_group.get(k, {}).get("level") == level
            ]
        for key in keys_to_remove:
            artist = dict_group[key].get("line")
            if artist is not None:
                if hasattr(artist, "remove"):
                    try:
                        artist.remove()
                    except Exception:
                        pass
                if isinstance(artist, tuple) or isinstance(artist, list):
                    for a in artist:
                        try:
                            a.remove()
                        except:
                            pass
                if hasattr(artist, "patches"):
                    for p in artist.patches:
                        try:
                            p.remove()
                        except:
                            pass
                if hasattr(artist, "lines"):
                    for l in artist.lines:
                        if l is not None:
                            if isinstance(l, (list, tuple)):
                                for sub_l in l:
                                    if sub_l is not None:
                                        try:
                                            sub_l.remove()
                                        except:
                                            pass
                            else:
                                try:
                                    l.remove()
                                except:
                                    pass

            # Some containers might be stored under "fill" instead of "line" depending on legacy structure
            artist = dict_group[key].get("fill")
            if artist is not None and artist is not dict_group[key].get("line"):
                if hasattr(artist, "remove"):
                    try:
                        artist.remove()
                    except Exception:
                        pass

            del dict_group[key]
            if key in dict_group_show:
                del dict_group_show[key]

    def _level_key(self, base_label, level):
        return plot_model.level_storage_key(base_label, level)

    def _display_label(self, key):
        return plot_model.display_label_from_key(key)

    def update_group_level_visibility(self, active_level=None):
        """Toggle visibility of group artists so only the current n_unit level is shown.

        This allows keeping separate artist sets (mean + SEM) per level
        and switching cheaply via visibility instead of unplot/replot.
        Integrates with the level filter already present in update_show.
        """
        if active_level is None:
            active_level = self.uistate.stat_test.buttonGroup_test_n

        # Ensure only artists for the active level (or untagged) are visible.
        # We set visibility here for level, and let update_show handle selection rules.
        dict_group = self.uistate.plot.dict_group_labels

        for k, v in list(dict_group.items()):
            if v.get("group_ID") is not None:
                is_correct_level = (v.get("level") == active_level) or (v.get("level") is None)
                visible_for_level = is_correct_level
                for key in ["line", "fill"]:
                    obj = v.get(key)
                    if obj is not None:
                        try:
                            if hasattr(obj, "set_visible"):
                                obj.set_visible(visible_for_level)
                            elif hasattr(obj, "patches"):
                                for p in obj.patches:
                                    p.set_visible(visible_for_level)
                            elif hasattr(obj, "lines"):
                                for l in (obj.lines if isinstance(obj.lines, (list, tuple)) else [obj.lines]):
                                    if l is not None:
                                        if isinstance(l, (list, tuple)):
                                            for sub_l in l:
                                                if sub_l is not None:
                                                    sub_l.set_visible(visible_for_level)
                                        else:
                                            l.set_visible(visible_for_level)
                        except Exception:
                            pass

        # Rebuild show dict for the level (caller should invoke full update_show for selection rules if needed)
        if hasattr(self.uistate.plot, "dict_group_show"):
            new_show = {k: v for k, v in dict_group.items()
                        if v.get("group_ID") is not None and ((v.get("level") == active_level) or (v.get("level") is None))}
            self.uistate.plot.dict_group_show = new_show

    def _apply_pp_graph_refresh_xaxis(self, ax1, ax2, plan):
        if plan.ax1_xlabel is not None:
            ax1.set_xlabel(plan.ax1_xlabel)
        if plan.ax2_xlabel is not None:
            ax2.set_xlabel(plan.ax2_xlabel)
        if plan.ticks:
            ax1.set_xticks(plan.ticks)
            ax1.set_xticklabels(plan.ticklabels)
            ax2.set_xticks(plan.ticks)
            ax2.set_xticklabels(plan.ticklabels)
        if plan.hide_all:
            ax1.tick_params(axis="x", bottom=False, labelbottom=False)
            ax2.tick_params(axis="x", bottom=False, labelbottom=False)
        elif plan.labels_only:
            ax1.tick_params(axis="x", bottom=False, labelbottom=True)
            ax2.tick_params(axis="x", bottom=False, labelbottom=True)

    def graphRefresh(self, dd_groups, dd_testset=None, dd_shown_samples=None):
        # show only selected and imported lines, only appropriate aspects
        uistate = self.uistate
        if uistate.plot.axm is None:
            print("No axes to refresh")
            return
        t0 = time.time()

        # Set recordings and group legends
        dd_recs = uistate.plot.dict_rec_show
        dd_group_show = uistate.plot.dict_group_show
        axids = ["ax1", "ax2"]
        legend_loc = list(
            plot_model.output_legend_locations(
                experiment_type=uistate.experiment.experiment_type,
                slope_only=uistate.slopeOnly(),
            )
        )
        is_pp = uistate.experiment.experiment_type == "PP"
        current_level = uistate.stat_test.buttonGroup_test_n
        for axid, loc in zip(axids, legend_loc):
            axis_legend = plot_model.output_axis_legend_map(
                dd_recs,
                dd_group_show,
                axid=axid,
                current_level=current_level,
                include_groups=axid in ("ax1", "ax2"),
            )
            axis = getattr(uistate.plot, axid)
            if axis_legend and not is_pp:
                try:
                    # Tweaked: smaller fontsize for compactness with groups + recs; explicit lists for safety
                    leg = axis.legend(list(axis_legend.values()), list(axis_legend.keys()), loc=loc, fontsize=8)
                except TypeError:
                    # Fallback if zorder was passed from ui.py wrapper (matplotlib version issue)
                    leg = axis.legend(list(axis_legend.values()), list(axis_legend.keys()), loc=loc, fontsize=8)
                if leg is not None:
                    leg.set_zorder(10)
            else:
                if axis.get_legend():
                    axis.get_legend().remove()

        for axid in ["axm", "axe"]:
            axis = getattr(uistate.plot, axid)
            if axis.get_legend():
                axis.get_legend().remove()

        # print(f" - - graphRefresh: legends: {round((time.time() - t0) * 1000)} ms")
        # t1 = time.time()

        # arrange axes and labels
        axm, axe, ax1, ax2 = (
            self.uistate.plot.axm,
            self.uistate.plot.axe,
            self.uistate.plot.ax1,
            self.uistate.plot.ax2,
        )

        axm.axis("off")

        axe.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 1e3:.1f}"))
        axe.set_ylabel(plot_model.EVENT_AXIS_YLABEL)
        axe.xaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t * 1e3:.1f}"))
        axe.set_xlabel(plot_model.EVENT_AXIS_XLABEL)

        exp_type = uistate.experiment.experiment_type
        axis_labels = plot_model.output_axis_ylabels(
            experiment_type=exp_type,
            io_output=uistate.experiment.io_output,
            norm_epsP=bool(uistate.project.checkBox["norm_EPSP"]),
        )
        ax1.set_ylabel(axis_labels.ax1_ylabel)
        ax2.set_ylabel(axis_labels.ax2_ylabel)
        fmt_mode = plot_model.output_axis_format_mode(exp_type)
        if fmt_mode.show_output_x_tick_marks:
            ax1.tick_params(axis="x", bottom=True, length=3.5)
            ax2.tick_params(axis="x", bottom=True, length=3.5)
        if fmt_mode.use_g_formatters:
            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            if fmt_mode.time_x_formatter_on_ax2:
                ax2.xaxis.set_major_formatter(uistate.x_axis_formatter())
            else:
                ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))

        # Add horizontal dotted grid lines at 100%, 200%, 300% for PPR
        if exp_type == "PP":
            # clear previous dashed lines if we didn't just exorcise
            for ax in [ax1, ax2]:
                lines_to_remove = [line for line in ax.lines if line.get_linestyle() == ":" and line.get_color() == "gray"]
                for line in lines_to_remove:
                    try:
                        line.remove()
                    except:
                        pass

            for y_val in plot_model.pp_reference_grid_y_values():
                ax1.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)
                ax2.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)
        if exp_type == "PP":
            bar_specs = []
            if hasattr(self.uistate.plot, "dict_group_show"):
                bar_specs = plot_series.collect_pp_group_bar_patch_specs(
                    uistate.plot.dict_group_show,
                    current_level,
                    lambda base: self._display_label(base),
                )
            pp_has_recs = hasattr(self.uistate.plot, "dict_rec_show") and plot_series.pp_has_visible_rec_ppr(
                uistate.plot.dict_rec_show
            )
            pp_xplan = plot_series.build_pp_graph_refresh_xaxis_plan(
                bar_specs,
                uistate.project.checkBox,
                pp_has_recs=pp_has_recs,
            )
            self._apply_pp_graph_refresh_xaxis(ax1, ax2, pp_xplan)

        if exp_type != "PP":
            ax1.set_xlabel(uistate.x_axis_xlabel())
            ax1.xaxis.set_major_locator(uistate.x_axis_locator())
            ax2.xaxis.set_major_locator(uistate.x_axis_locator())
        # print(f"output_xlim: {uistate.project.zoom['output_xlim']}")
        ax1.figure.subplots_adjust(bottom=0.2)
        self.oneAxisLeft()
        # print(f" - - graphRefresh: axis setup: {round((time.time() - t1) * 1000)} ms")
        # t1 = time.time()

        # maintain drag selections through reselection
        if uistate.plot.x_select["mean_start"] is not None:
            self.xSelect(canvas=axm.figure.canvas, draw=False)
        if uistate.plot.x_select["output_start"] is not None:
            if uistate.project.checkBox["EPSP_slope"]:
                self.xSelect(canvas=ax2.figure.canvas, draw=False)
            else:
                self.xSelect(canvas=ax1.figure.canvas, draw=False)

        # visualize test sets (Phase 2) - spans persist independently of xSelect
        if dd_testset is not None:
            self.visualize_test_sets(dd_testset=dd_testset, draw=False)
            self.uistate.plot.sample_dirty = True
            self.sample_overlay(dd_groups=dd_groups, dd_testset=dd_testset, dd_shown_samples=dd_shown_samples or {})

        # refresh samples (Phase 3.4.3) - create inset (transparent bg; axis visibility + traces controlled in sample_overlay; no sharex/sharey)
        if not hasattr(self.uistate.plot, "sample_inset"):
            if self.uistate.plot.ax1 is not None:
                self.uistate.plot.sample_inset = self.uistate.plot.ax1.inset_axes([0.02, 0.68, 0.33, 0.30])
                self.uistate.plot.sample_inset.set_zorder(10)
                self.uistate.plot.sample_inset.set_facecolor((0, 0, 0, 0))
                self.uistate.plot.sample_inset.set_axis_off()
                self.uistate.plot.sample_dirty = True
        if hasattr(self.uistate, "refresh_samples"):
            self.uistate.refresh_samples()
        elif hasattr(self, "uisub") and hasattr(self.uisub, "refresh_samples"):
            self.uisub.refresh_samples()

        # 0-hline for Events
        if not "Events y zero marker" in self.uistate.plot.dict_rec_labels:
            hline0 = self.uistate.plot.axe.axhline(0, linestyle="dotted", alpha=0.3)
            self.uistate.plot.dict_rec_labels["Events y zero marker"] = {
                "rec_ID": None,
                "stim": None,
                "variant": None,
                "line": hline0,
                "axis": "axe",
            }
        uistate.plot.dict_rec_labels["Events y zero marker"]["line"].set_visible(True)

        # 100-hline for relative Output
        if uistate.project.checkBox["norm_EPSP"]:
            if not "Output y 100% marker" in self.uistate.plot.dict_rec_labels:
                hline100ax1 = self.uistate.plot.ax1.axhline(
                    100,
                    linestyle="dotted",
                    alpha=0.3,
                    color=uistate.project.settings["rgb_EPSP_amp"],
                )
                hline100ax2 = self.uistate.plot.ax2.axhline(
                    100,
                    linestyle="dotted",
                    alpha=0.3,
                    color=uistate.project.settings["rgb_EPSP_slope"],
                )
                self.uistate.plot.dict_rec_labels["output amp 100% marker"] = {
                    "rec_ID": None,
                    "stim": None,
                    "variant": None,
                    "line": hline100ax1,
                    "axis": "ax1",
                }
                self.uistate.plot.dict_rec_labels["output slope 100% marker"] = {
                    "rec_ID": None,
                    "stim": None,
                    "variant": None,
                    "line": hline100ax2,
                    "axis": "ax2",
                }
            uistate.plot.dict_rec_labels["output amp 100% marker"]["line"].set_visible(uistate.ampView())
            uistate.plot.dict_rec_labels["output slope 100% marker"]["line"].set_visible(uistate.slopeView())
        # print(f" - - graphRefresh: markers/hlines: {round((time.time() - t1) * 1000)} ms")
        # t1 = time.time()

        # update mean of selected sweeps on axe
        self.update_axe_mean(draw=False)
        # print(f" - - graphRefresh: update_axe_mean: {round((time.time() - t1) * 1000)} ms")
        # t1 = time.time()

        # redraw
        axm.figure.canvas.draw_idle()
        # print(f" - - graphRefresh: draw axm: {round((time.time() - t1) * 1000)} ms")
        # t1 = time.time()
        axe.figure.canvas.draw_idle()
        # print(f" - - graphRefresh: draw axe: {round((time.time() - t1) * 1000)} ms")
        # t1 = time.time()
        ax1.figure.canvas.draw_idle()  # ax2 should be on the same canvas
        # print(f" - - graphRefresh: draw ax1/ax2: {round((time.time() - t1) * 1000)} ms")

        # Re-apply formal test * / ns labels after full refresh (they attach to ax1/ax2 and
        # should normally survive, but this guarantees they reappear if any clear happened).
        if uistate.stat_test.formal_test_results:
            try:
                self.show_test_markers(uistate.stat_test.formal_test_results)
            except Exception:
                pass

        print(f" - - graphRefresh total: {round((time.time() - t0) * 1000)} ms")

    def oneAxisLeft(self):
        ax1, ax2 = self.uistate.plot.ax1, self.uistate.plot.ax2
        uistate = self.uistate
        # sets ax1 and ax2 visibility and position
        ax1.set_visible(True)
        ax2.set_visible(True)
        ax1.xaxis.set_visible(True)
        ax2.xaxis.set_visible(False)

        amp_view = uistate.ampView()
        slope_view = uistate.slopeView()
        show_amp, show_slope = plot_model.output_axis_y_visibility(amp_view=amp_view, slope_view=slope_view)
        ax1.yaxis.set_visible(show_amp)
        ax2.yaxis.set_visible(show_slope)

        if plot_model.slope_yaxis_on_left(slope_only=uistate.slopeOnly()):
            ax2.yaxis.set_label_position("left")
            ax2.yaxis.set_ticks_position("left")
        else:
            ax2.yaxis.set_label_position("right")
            ax2.yaxis.set_ticks_position("right")

    def get_axis(self, axisname):  # returns the axis object by name (using only object references failed in some cases)
        axis_dict = {
            "axm": self.uistate.plot.axm,
            "axe": self.uistate.plot.axe,
            "ax1": self.uistate.plot.ax1,
            "ax2": self.uistate.plot.ax2,
        }
        return axis_dict.get(axisname, None)

    def get_dict_gradient(self, n_stims):
        colors = [
            (1, 0.3, 0),
            "green",
            (0, 0.3, 1),
        ]  # RGB for a redder orange and a tealer blue
        cmap = LinearSegmentedColormap.from_list("", colors)
        return {i: cmap(i / n_stims) for i in range(n_stims)}

    def plot_line(
        self,
        label,
        axid,
        x,
        y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        width=1,
        alpha=None,
        variant="raw",
        x_mode=None,
        marker=None,
        markersize=None,
        linestyle="-",
    ):
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        zorder = 0 if width > 1 else 1
        if is_pp and axid in ("ax1", "ax2") and "PPR" in label:
            zorder = 4  # Ensure rec blobs paint OVER the group overlays
        alpha = alpha if alpha is not None else self.uistate.project.settings["alpha_line"]
        kwargs = {"color": color, "label": label, "alpha": alpha, "linewidth": width, "zorder": zorder, "linestyle": linestyle}
        if marker is not None:
            kwargs["marker"] = marker
        if markersize is not None:
            kwargs["markersize"] = markersize
        (line,) = self.get_axis(axid).plot(x, y, **kwargs)
        line.set_visible(False)
        self.uistate.plot.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": line,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_shade(
        self,
        label,
        axid,
        x,
        y_mean,
        sem,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        variant="raw",
        x_mode="stim",
    ):
        alpha = self.uistate.project.settings.get("alpha_shade", 0.3)
        fill = self.get_axis(axid).fill_between(x, y_mean - sem, y_mean + sem, alpha=alpha, color=color, zorder=0)
        fill.set_visible(False)
        self.uistate.plot.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": fill,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_marker(
        self,
        label,
        axid,
        x,
        y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        variant="raw",
        x_mode=None,
    ):
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        (marker,) = self.get_axis(axid).plot(
            x,
            y,
            marker="o",
            markerfacecolor=color,
            markeredgecolor=color,
            markersize=STIM_MARKER_SIZE,
            alpha=0.4,
            zorder=0,
            label=label,
        )
        marker.set_visible(False)
        self.uistate.plot.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": marker,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_amp_width(
        self,
        label,
        axid,
        x,
        amp_x,
        amp_y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        variant="raw",
        x_mode=None,
    ):
        is_zero_width = amp_x[0] == amp_x[1]
        (xline,) = self.get_axis(axid).plot(
            amp_x,
            [amp_y[1], amp_y[1]],
            color=color,
            label=f"{label} x",
            alpha=self.uistate.project.settings["alpha_line"],
            zorder=2,
            linewidth=2,
        )
        (yline,) = self.get_axis(axid).plot(
            [x, x],
            amp_y,
            color=color,
            label=f"{label} y",
            alpha=self.uistate.project.settings["alpha_line"],
            zorder=2,
            linewidth=2,
        )
        xline.set_visible(False)
        yline.set_visible(False)
        self.uistate.plot.dict_rec_labels[f"{label} x marker"] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": xline,
            "axis": axid,
            "is_zero_width": is_zero_width,
            "x_mode": x_mode,
        }
        self.uistate.plot.dict_rec_labels[f"{label} y marker"] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": yline,
            "axis": axid,
            "is_zero_width": False,
            "x_mode": x_mode,
        }

    def plot_vline(
        self,
        label,
        axid,
        x,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        linewidth=8,
        variant="raw",
        x_mode=None,
    ):
        vline = self.get_axis(axid).axvline(
            x=x,
            color=color,
            alpha=self.uistate.project.settings["alpha_mark"],
            label=label,
            linewidth=linewidth,
            zorder=0,
        )
        vline.set_visible(False)
        self.uistate.plot.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": vline,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_hline(
        self,
        label,
        axid,
        y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        linewidth=1,
        variant="raw",
        x_mode=None,
    ):
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        hline = self.get_axis(axid).axhline(
            y=y,
            color=color,
            alpha=self.uistate.project.settings["alpha_mark"],
            label=label,
            linewidth=linewidth,
            zorder=0,
        )
        hline.set_visible(False)
        self.uistate.plot.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": hline,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_group_lines(self, axid, group_ID, dict_group, df_groupmean, aspect=None, level=None):
        """Plot group mean line + SEM fill for a given aspect.

        level (if provided) is stored on the artist entry so we can keep
        separate plot sets for recording/slice/subject and toggle them.
        """
        group_name = dict_group["group_name"]
        color = dict_group["color"]
        axis = self.get_axis(axid)
        if aspect is None:
            aspect = plot_series.default_group_aspect(axid)
        eff_level = level or self.uistate.stat_test.buttonGroup_test_n
        series = plot_series.extract_group_mean_series(df_groupmean, aspect)
        x_vals = series.x
        y_mean_vals = series.y_mean
        y_sem_vals = series.y_sem
        line_specs = plot_model.build_group_line_specs(
            group_name,
            aspect,
            eff_level,
            include_norm=series.y_norm is not None,
        )
        raw_spec = line_specs[0]
        (meanline,) = axis.plot(
            x_vals,
            y_mean_vals,
            color=color,
            label=raw_spec.display_label,
            alpha=self.uistate.project.settings["alpha_line"],
            zorder=1,
            linewidth=2.0,
        )
        meanfill = axis.fill_between(x_vals, y_mean_vals - y_sem_vals, y_mean_vals + y_sem_vals, alpha=0.25, color=color, zorder=0)
        meanline.set_visible(False)
        meanfill.set_visible(False)
        self.uistate.plot.dict_group_labels[raw_spec.storage_key] = {
            **plot_model.group_line_label_entry(
                group_ID=group_ID,
                aspect=aspect,
                variant=raw_spec.variant,
                axis=axid,
                level=eff_level,
            ),
            "line": meanline,
            "fill": meanfill,
        }

        if series.y_norm is not None:
            norm_spec = line_specs[1]
            y_norm_vals = series.y_norm
            y_norm_sem_vals = series.y_norm_sem
            (normline,) = axis.plot(
                x_vals,
                y_norm_vals,
                color=color,
                label=norm_spec.display_label,
                alpha=self.uistate.project.settings["alpha_line"],
                zorder=1,
                linewidth=2.0,
            )
            normfill = axis.fill_between(x_vals, y_norm_vals - y_norm_sem_vals, y_norm_vals + y_norm_sem_vals, alpha=0.25, color=color, zorder=0)
            normline.set_visible(False)
            normfill.set_visible(False)
            self.uistate.plot.dict_group_labels[norm_spec.storage_key] = {
                **plot_model.group_line_label_entry(
                    group_ID=group_ID,
                    aspect=aspect,
                    variant=norm_spec.variant,
                    axis=axid,
                    level=eff_level,
                ),
                "line": normline,
                "fill": normfill,
            }

    def _render_stim_event_plot_spec(self, spec, rec_ID):
        if isinstance(spec, plot_stim.StimMarkerPlotSpec):
            self.plot_marker(
                spec.label,
                spec.axid,
                spec.x,
                spec.y,
                spec.color,
                rec_ID,
                aspect=spec.aspect,
                stim=spec.stim,
            )
        elif isinstance(spec, plot_stim.StimVlinePlotSpec):
            self.plot_vline(spec.label, spec.axid, spec.x, spec.color, rec_ID, stim=spec.stim)
        elif isinstance(spec, plot_stim.StimAmpWidthPlotSpec):
            self.plot_amp_width(
                spec.label,
                spec.axid,
                spec.x_center,
                spec.amp_x,
                spec.amp_y,
                spec.color,
                rec_ID,
                aspect=spec.aspect,
                stim=spec.stim,
            )
        elif isinstance(spec, plot_stim.StimHlinePlotSpec):
            self.plot_hline(
                spec.label,
                spec.axid,
                spec.y,
                spec.color,
                rec_ID,
                aspect=spec.aspect,
                stim=spec.stim,
                x_mode=spec.x_mode,
            )
        else:
            self.plot_line(
                spec.label,
                spec.axid,
                spec.x,
                spec.y,
                spec.color,
                rec_ID,
                aspect=spec.aspect,
                stim=spec.stim,
                variant=spec.variant,
                x_mode=spec.x_mode,
                width=spec.width,
            )

    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)
        skip_output = plot_series.skip_pp_recording_output(self.uistate.experiment.experiment_type, n_stims)
        label = plot_series.recording_plot_label(rec_name, rec_filter)

        if self.uistate.experiment.experiment_type == "io":
            _, y_col_base = plot_series.io_axis_columns(
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
            )
            axid = "ax1"
            color = self.uistate.project.settings.get(f"rgb_{y_col_base}", "black")
            force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
            for spec in plot_series.build_io_recording_plot_specs(
                dfoutput,
                label,
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
                force_through_zero=force0,
            ):
                if isinstance(spec, plot_series.IoScatterPlotSpec):
                    scatter = self.get_axis(axid).scatter(
                        spec.x,
                        spec.y,
                        c=[color],
                        alpha=0.8,
                        label=spec.label,
                        s=20,
                        zorder=2,
                    )
                    scatter.set_visible(False)
                    self.uistate.plot.dict_rec_labels[spec.label] = {
                        **plot_model.io_rec_label_entry(
                            rec_ID=rec_ID,
                            aspect=spec.aspect,
                            variant=spec.variant,
                            axis=axid,
                        ),
                        "line": scatter,
                    }
                else:
                    (trendline,) = self.get_axis(axid).plot(
                        spec.x,
                        spec.y,
                        color=color,
                        linestyle="--",
                        alpha=0.8,
                        label=spec.label,
                        zorder=1,
                    )
                    trendline.set_visible(False)
                    self.uistate.plot.dict_rec_labels[spec.label] = {
                        **plot_model.io_rec_label_entry(
                            rec_ID=rec_ID,
                            aspect=spec.aspect,
                            variant=spec.variant,
                            axis=axid,
                        ),
                        "line": trendline,
                    }

        # Add meanline to Mean
        self.plot_line(
            f"mean {label}",
            "axm",
            dfmean["time"],
            dfmean[rec_filter],
            "black",
            rec_ID=rec_ID,
        )

        dict_gradient = self.get_dict_gradient(n_stims)
        settings = self.uistate.project.settings

        for spec in plot_stim.build_stim_event_plot_specs(
            label,
            dft,
            dfmean,
            dfoutput,
            rec_filter,
            settings,
            dict_gradient,
        ):
            self._render_stim_event_plot_spec(spec, rec_ID)

        if self.uistate.experiment.experiment_type == "PP" and not skip_output:
            for spec in plot_series.build_pp_recording_plot_specs(
                dfoutput,
                label,
                self.uistate.project.checkBox,
                settings,
            ):
                self.plot_line(
                    spec.label,
                    spec.axid,
                    spec.x,
                    spec.y,
                    spec.color,
                    rec_ID,
                    aspect=spec.aspect,
                    stim=None,
                    variant=spec.variant,
                    x_mode="sweep",
                    marker="o",
                    markersize=10,
                    linestyle="None",
                )

        for spec in plot_series.build_stim_aggregate_plot_specs(dfoutput, label, settings):
            self.plot_line(
                spec.line_label,
                spec.axid,
                spec.x,
                spec.y,
                spec.color,
                rec_ID,
                aspect=spec.aspect,
                variant=spec.variant,
                x_mode="stim",
            )
            if spec.sem is not None and spec.shade_label is not None:
                self.plot_shade(
                    spec.shade_label,
                    spec.axid,
                    spec.x,
                    spec.y,
                    spec.sem,
                    spec.color,
                    rec_ID,
                    aspect=spec.aspect,
                    variant=spec.variant,
                    x_mode="stim",
                )

    def _render_pp_group_bar_spec(self, spec, group_ID, group_name, color, level):
        bar_artist = self.get_axis(spec.axid).bar(
            [spec.bar_x],
            [spec.mean_val],
            width=spec.bar_width,
            color=color,
            edgecolor="black",
            alpha=1.0,
            zorder=2,
            label=f"{group_name} PPR {spec.aspect} bar",
        )
        err_artist = self.get_axis(spec.axid).errorbar(
            [spec.bar_x],
            [spec.mean_val],
            yerr=[spec.sem_val],
            fmt="none",
            ecolor="black",
            elinewidth=1.5,
            capsize=5,
            capthick=1.5,
            zorder=3,
            label=f"{group_name} PPR {spec.aspect} err",
        )
        scat_artists = []
        for pt in spec.scatter_points:
            scat_art = self.get_axis(spec.axid).scatter(
                [pt.x],
                [pt.y],
                color=spec.scatter_color,
                edgecolor="black",
                zorder=4,
                s=40,
                label=f"{group_name} PPR {spec.aspect} {pt.rec_id} point",
            )
            scat_artists.append((scat_art, pt.rec_id))

        overlay_bar_artist = self.get_axis(spec.axid).bar(
            [spec.overlay_x],
            [spec.mean_val],
            width=0.4,
            color=color,
            edgecolor="black",
            alpha=0.2,
            zorder=2,
            label=f"{group_name} PPR {spec.aspect} overlay_bar",
        )
        overlay_err_artist = self.get_axis(spec.axid).errorbar(
            [spec.overlay_x],
            [spec.mean_val],
            yerr=[spec.sem_val],
            fmt="none",
            ecolor="black",
            elinewidth=1.5,
            capsize=5,
            capthick=1.5,
            zorder=3,
            label=f"{group_name} PPR {spec.aspect} overlay_err",
        )

        items_to_store = [
            (bar_artist, "bar", None, False),
            (err_artist, "err", None, False),
            (overlay_bar_artist, "overlay_bar", None, True),
            (overlay_err_artist, "overlay_err", None, True),
        ]
        for art, rid in scat_artists:
            items_to_store.append((art, f"{rid} point", rid, False))

        for artist, suffix, rec_id_val, is_overlay in items_to_store:
            if hasattr(artist, "set_visible"):
                artist.set_visible(False)
            elif hasattr(artist, "patches"):
                for p in artist.patches:
                    p.set_visible(False)
            elif hasattr(artist, "lines"):
                for l in artist.lines:
                    if l is not None:
                        if isinstance(l, (list, tuple)):
                            for sub_l in l:
                                if sub_l is not None:
                                    sub_l.set_visible(False)
                        else:
                            l.set_visible(False)

            d = {
                **plot_model.pp_group_bar_label_entry(
                    group_ID=group_ID,
                    aspect=spec.aspect,
                    level=level,
                    axis=spec.axid,
                    rec_ID=rec_id_val,
                    is_overlay=is_overlay,
                ),
                "line": artist,
                "fill": artist,
            }
            ppr_storage_key = self._level_key(f"{group_name} PPR {spec.aspect} {suffix}", level)
            self.uistate.plot.dict_group_labels[ppr_storage_key] = d

    def _render_io_group_plot_spec(self, spec, group_ID, color):
        if isinstance(spec, plot_series.IoGroupScatterPlotSpec):
            scatter = self.get_axis("ax1").scatter(
                spec.x,
                spec.y,
                c=[color],
                alpha=0.3,
                label=spec.label,
                s=20,
                zorder=2,
            )
            scatter.set_visible(False)
            self.uistate.plot.dict_group_labels[spec.storage_key] = {
                **plot_model.io_group_label_entry(
                    group_ID=group_ID,
                    aspect=spec.aspect,
                    variant=spec.variant,
                    axis="ax1",
                    level=spec.level,
                ),
                "line": scatter,
                "fill": scatter,
            }
        else:
            (trendline,) = self.get_axis("ax1").plot(
                spec.x,
                spec.y,
                color=color,
                linestyle="-",
                linewidth=2,
                alpha=0.9,
                label=spec.label,
                zorder=3,
            )
            trendline.set_visible(False)
            self.uistate.plot.dict_group_labels[spec.storage_key] = {
                **plot_model.io_group_label_entry(
                    group_ID=group_ID,
                    aspect=spec.aspect,
                    variant=spec.variant,
                    axis="ax1",
                    level=spec.level,
                ),
                "line": trendline,
                "fill": trendline,
            }

    def addGroup(self, group_ID, dict_group, df_groupmean, x_pos=1, level=None):
        """Add (or update) group artists for the given level.

        If level is None, it is taken from uistate.stat_test.buttonGroup_test_n.
        """
        # plot group meanlines and SEMs
        eff_level = level or self.uistate.stat_test.buttonGroup_test_n
        exp_type = self.uistate.experiment.experiment_type
        if exp_type == "PP":
            group_name = dict_group["group_name"]
            color = dict_group["color"]
            level = eff_level or self.uistate.stat_test.buttonGroup_test_n
            rec_ppr = plot_series.extract_rec_ppr_means(
                self.uistate.plot.dict_rec_labels,
                dict_group["rec_IDs"],
            )
            df_p = None
            try:
                if hasattr(self, "uisub") and self.uisub and hasattr(self.uisub, "get_df_project"):
                    df_p = self.uisub.get_df_project()
            except Exception:
                df_p = None
            aggregate = plot_series.aggregate_ppr_at_level(rec_ppr, level, df_p)
            for bar_spec in plot_series.build_pp_group_bar_plot_specs(
                aggregate=aggregate,
                x_pos=x_pos,
                level=level,
                checkbox=self.uistate.project.checkBox,
                settings=self.uistate.project.settings,
            ):
                try:
                    self._render_pp_group_bar_spec(bar_spec, group_ID, group_name, color, level)
                except Exception as e:
                    print(f"DEBUG: addGroup error in drawing loop: {e}")
            return

        if exp_type == "io":
            _, y_col_base = plot_series.io_axis_columns(
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
            )
            color = dict_group["color"]
            group_name = dict_group["group_name"]
            io_level = self.uistate.stat_test.buttonGroup_test_n
            force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
            for variant in ("raw", "norm"):
                xy = plot_series.collect_io_group_scatter_xy(
                    self.uistate.plot.dict_rec_labels,
                    dict_group["rec_IDs"],
                    variant,
                )
                if xy is None:
                    continue
                for spec in plot_series.build_io_group_plot_specs(
                    group_name,
                    xy[0],
                    xy[1],
                    y_col_base=y_col_base,
                    variant=variant,
                    level=io_level,
                    force_through_zero=force0,
                ):
                    self._render_io_group_plot_spec(spec, group_ID, color)
            return

        eff_level = self.uistate.stat_test.buttonGroup_test_n
        for axid, aspect, _col in plot_series.group_mean_plots_for_df(df_groupmean):
            self.plot_group_lines(axid, group_ID, dict_group, df_groupmean, aspect=aspect, level=eff_level)

    def update(
        self,
        prow,
        trow,
        aspect,
        data_x,
        data_y,
        amp=None,
        dfoutput=None,
        amp_zero_plot=None,
    ):
        """
        Updates the existing plotted artists stored in `self.uistate.plot.dict_rec_labels`.
        Parameters
        - prow (pandas.Series): df_project row for selected recording.
        - trow (pandas.Series): dft (timepoint) row for selected stim.
        - aspect (str): One of 'EPSP slope', 'volley slope', 'EPSP amp', 'volley amp'.
            Controls which markers/lines are updated.
        - data_x (np.ndarray-like): x-values (time or shifted time) corresponding to
            the event window or mean trace used to sample y-values for marker placement.
        - data_y (np.ndarray-like): y-values aligned with `data_x` (voltage trace).
        - amp (float, optional): amplitude value used for drawing amplitude markers
        - dfoutput (DataFrame, optional): when provided, the amp output line is
            populated directly from this dataframe (full-width mean) instead of
            copying from the live-drag mouseover_out (single-point).
        """

        data_x, data_y = plot_stim.validate_drag_update_inputs(prow, trow, aspect, data_x, data_y, amp)
        norm = self.uistate.project.checkBox["norm_EPSP"]
        stim_offset = trow["t_stim"]
        label_core = plot_stim.drag_update_label_core(
            prow["recording_name"],
            prow.get("filter"),
            trow["stim"],
            aspect,
        )
        is_pp = self.uistate.experiment.experiment_type == "PP"
        stim_num = trow["stim"]

        if aspect in plot_stim.SLOPE_DRAG_ASPECTS:
            x_data, y_data = plot_stim.slope_marker_xy(trow, aspect, stim_offset, data_x, data_y)
            self.updateLine(f"{label_core} marker", x_data, y_data)
            out_label = plot_stim.drag_output_label(label_core, aspect, norm)
            if aspect == "volley slope":
                if is_pp and dfoutput is not None:
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, plot_stim.slope_output_column(aspect, norm))
                elif not is_pp:
                    self.updateOutMean(f"{label_core} mean", trow.get("volley_slope_mean"))
            elif is_pp and dfoutput is not None:
                self.updateOutLineFromDf(out_label, dfoutput, stim_num, plot_stim.slope_output_column(aspect, norm))
            else:
                self.updateOutLine(out_label)
        elif aspect in plot_stim.AMP_DRAG_ASPECTS:
            geom = plot_stim.amp_drag_geometry(trow, aspect, stim_offset, data_x, data_y, amp_zero_plot)
            self.updateAmpMarker(label_core, geom.t_amp, geom.y_position, geom.amp_x, geom.amp_zero, amp=amp)
            out_label = plot_stim.drag_output_label(label_core, aspect, norm)
            col = plot_stim.amp_output_column(aspect, norm)
            if aspect == "volley amp":
                if dfoutput is not None:
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, col)
                elif not is_pp:
                    self.updateOutLine(label_core)
                if not is_pp:
                    self.updateOutMean(f"{label_core} mean", trow.get("volley_amp_mean"))
            elif dfoutput is not None:
                self.updateOutLineFromDf(out_label, dfoutput, stim_num, col)
            elif not is_pp:
                self.updateOutLine(out_label)

    def updateAmpMarker(self, labelbase, x, y, amp_x, amp_zero, amp=None, draw=False):
        axe = self.uistate.plot.axe
        print(f"updateAmpMarker called with labelbase: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        x = np.atleast_1d(x)
        y = np.atleast_1d(y)
        print(f"updateAmpMarker: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        self.uistate.plot.dict_rec_labels[f"{labelbase} marker"]["line"].set_data(x, y)
        amp_si = plot_stim.resolve_drag_amp_si(amp, float(y[0]), amp_zero)
        if amp_si is not None:
            is_zero_width = amp_x[0] == amp_x[1]
            amp_y = plot_stim.amp_width_y_coords(amp_si, amp_zero)
            self.uistate.plot.dict_rec_labels[f"{labelbase} x marker"]["line"].set_data(amp_x, [amp_y[1], amp_y[1]])
            self.uistate.plot.dict_rec_labels[f"{labelbase} y marker"]["line"].set_data([x[0], x[0]], amp_y)
            self.uistate.plot.dict_rec_labels[f"{labelbase} x marker"]["is_zero_width"] = is_zero_width
            self.uistate.plot.dict_rec_labels[f"{labelbase} y marker"]["is_zero_width"] = False
        if draw:
            axe.figure.canvas.draw_idle()

    def updateLine(self, plot_to_update, x_data, y_data, draw=False):
        axe = self.uistate.plot.axe
        dict_line = self.uistate.plot.dict_rec_labels[plot_to_update]
        dict_line["line"].set_data(x_data, y_data)
        if draw:
            axe.figure.canvas.draw_idle()

    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.plot.mouseover_out
        if mouseover_out is None:
            print(f"updateOutLine: mouseover_out is None, skipping update for '{label}'")
            return
        if label not in self.uistate.plot.dict_rec_labels:
            return
        linedict = self.uistate.plot.dict_rec_labels[label]
        linedict["line"].set_xdata(plot_drag.artist_xdata(mouseover_out[0]))
        linedict["line"].set_ydata(plot_drag.artist_ydata(mouseover_out[0]))

    def updateStimLines(self, rec_name: str, dfoutput: "pd.DataFrame") -> None:
        """Refresh all stim-mode output artists for *rec_name* from *dfoutput*.

        Called after a drag-release that updates a stim-mode row so that the
        ax1/ax2 stim-mode lines (x_mode="stim") reflect the new measurements
        without requiring a full graphRefresh.

        The stim-mode artists are identified by their x_mode == "stim" entry in
        dict_rec_labels.  Their labels follow the pattern
        ``"{rec_name} {aspect}"`` (no stim-number suffix), e.g.
        ``"rec1 EPSP amp"``.

        Column mapping (matches addRow):
            label suffix          → dfoutput column
            "EPSP amp"            → "EPSP_amp"
            "EPSP amp norm"       → "EPSP_amp_norm"
            "EPSP slope"          → "EPSP_slope"
            "EPSP slope norm"     → "EPSP_slope_norm"
            "volley amp"          → "volley_amp"
            "volley slope"        → "volley_slope"
        """
        force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
        dict_rec_labels = self.uistate.plot.dict_rec_labels
        for spec in plot_series.build_io_refresh_specs_for_rec(
            rec_name,
            dict_rec_labels,
            dfoutput,
            self.uistate.experiment.io_input,
            self.uistate.experiment.io_output,
            force_through_zero=force0,
        ):
            linedict = dict_rec_labels[spec.label]
            if isinstance(spec, plot_series.IoScatterRefreshSpec):
                linedict["line"].set_offsets(np.c_[spec.x, spec.y])
                print(f"updateStimLines: refreshed IO scatter '{spec.label}'")
            else:
                linedict["line"].set_data(spec.x, spec.y)
                print(f"updateStimLines: refreshed IO trendline '{spec.label}'")

        existing_labels = frozenset(dict_rec_labels.keys())
        for spec in plot_series.build_stim_aggregate_refresh_specs(
            rec_name,
            dfoutput,
            self.uistate.project.settings,
            existing_labels,
        ):
            linedict = dict_rec_labels[spec.line_label]
            linedict["line"].set_xdata(spec.x)
            linedict["line"].set_ydata(spec.y)
            print(f"updateStimLines: refreshed '{spec.line_label}'")

            if spec.shade_label is not None and spec.sem is not None:
                old_shade_dict = dict_rec_labels[spec.shade_label]
                try:
                    old_shade_dict["line"].remove()
                except Exception:
                    pass
                color = self.uistate.project.settings.get(spec.color_setting_key, "black")
                self.plot_shade(
                    spec.shade_label,
                    spec.axid,
                    spec.x,
                    spec.y,
                    spec.sem,
                    color,
                    old_shade_dict["rec_ID"],
                    aspect=spec.aspect,
                    variant=spec.variant,
                    x_mode="stim",
                )
                dict_rec_labels[spec.shade_label]["line"].set_visible(linedict["line"].get_visible())

    def updateOutLineFromDf(self, label, dfoutput, stim_num, column, x_axis=None):
        """Populate an output line directly from a dfoutput DataFrame.

        Used on drag-release for amp aspects so that the persisted full-width
        mean values are reflected in the plot, rather than the single-point
        live-drag preview held in mouseover_out.

        Parameters
        - label: key in dict_rec_labels to update
        - dfoutput: the fully-recalculated output DataFrame
        - stim_num: stim number (1-based) to filter dfoutput rows
        - column: column name to use for y-values (e.g. 'EPSP_amp' or 'EPSP_amp_norm')
        """
        print(f"updateOutLineFromDf: {label}, stim={stim_num}, col={column}")
        xy = plot_series.out_line_xy_from_df(dfoutput, stim_num, column)
        if xy is None:
            print(f"updateOutLineFromDf: no data for stim={stim_num} col={column}, falling back to updateOutLine")
            self.updateOutLine(label)
            return

        if label not in self.uistate.plot.dict_rec_labels:
            if self.uistate.experiment.experiment_type == "PP":
                rec_label = label.split(" - stim ")[0]
                aspect = column.replace("_norm", "")
                for spec in plot_series.build_ppr_overlay_refresh_specs(
                    rec_label,
                    dfoutput,
                    aspect,
                    self.uistate.project.checkBox,
                    self.uistate.project.settings,
                    frozenset(self.uistate.plot.dict_rec_labels.keys()),
                ):
                    line = self.uistate.plot.dict_rec_labels[spec.label]["line"]
                    line.set_xdata(spec.x)
                    line.set_ydata(spec.y)
            return

        linedict = self.uistate.plot.dict_rec_labels[label]
        x_mode = linedict.get("x_mode", "sweep")
        xy = plot_series.out_line_xy_from_df(dfoutput, stim_num, column, x_mode=x_mode)
        if xy is None:
            self.updateOutLine(label)
            return
        linedict["line"].set_xdata(xy[0])
        linedict["line"].set_ydata(xy[1])

    def updateOutMean(self, label, mean):
        print(f"updateOutMean: {label}, {mean}")
        mouseover_out = self.uistate.plot.mouseover_out
        if mouseover_out is None:
            print(f"updateOutMean: mouseover_out is None, skipping update for '{label}'")
            return
        if label not in self.uistate.plot.dict_rec_labels:
            return
        linedict = self.uistate.plot.dict_rec_labels[label]
        x_len = len(plot_drag.artist_xdata(linedict["line"]))
        linedict["line"].set_xdata(plot_drag.artist_xdata(mouseover_out[0]))
        linedict["line"].set_ydata([mean] * x_len)
        # linedict['line'].set_ydata(mean)

    #####################################################################
    #     #DEPRECATED FUNCTIONS - TO BE REMOVED IN FUTURE RELEASES      #
    #####################################################################

    def updateEPSPout(self, rec_name, out):  # TODO: update this last remaining ax-cycle to use the dict
        # OBSOLETE - called by norm, does not operate on stim-specific data!
        ax1, ax2 = self.uistate.plot.ax1, self.uistate.plot.ax2
        for line in ax1.get_lines():
            if line.get_label() == f"{rec_name} EPSP amp":
                line.set_ydata(out["EPSP_amp"])
            if line.get_label() == f"{rec_name} EPSP amp norm":
                line.set_ydata(out["EPSP_amp_norm"])
                ax1.figure.canvas.draw_idle()
        for line in ax2.get_lines():
            if line.get_label() == f"{rec_name} EPSP slope":
                line.set_ydata(out["EPSP_slope"])
            if line.get_label() == f"{rec_name} EPSP slope norm":
                line.set_ydata(out["EPSP_slope_norm"])
                ax2.figure.canvas.draw_idle()
