import time  # counting time for functions
import warnings

from brainwash_ui import plot_drag, plot_identity, plot_model, plot_series, plot_stim, plot_testsets

import matplotlib.pyplot as plt  # for the scatterplot
import numpy as np
import pandas as pd
from collections import defaultdict

# import seaborn as sns
from matplotlib import style
from matplotlib.colors import LinearSegmentedColormap

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
                # Do not clear testset spans: they reflect shown test sets, not temp selection.
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

            for aux in dict_group[key].get("pp_aux_artists") or []:
                if aux is not None and hasattr(aux, "remove"):
                    try:
                        aux.remove()
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
        """Hide group artists that are not for the active n_unit level.

        Active-level visibility is owned by update_show (selection / show checkboxes).
        This helper must not force-show active-level artists or rebuild dict_group_show
        from level alone — that clobbered selection rules after update_show.
        """
        if active_level is None:
            active_level = self.uistate.stat_test.buttonGroup_test_n

        dict_group = self.uistate.plot.dict_group_labels

        for _k, v in list(dict_group.items()):
            if v.get("group_ID") is None:
                continue
            is_correct_level = (v.get("level") == active_level) or (v.get("level") is None)
            if is_correct_level:
                continue
            for key in ["line", "fill"]:
                obj = v.get(key)
                if obj is not None:
                    try:
                        self._set_plot_artist_visible(obj, False)
                    except Exception:
                        pass

        # Drop non-active levels from the show index; keep selection-filtered active entries.
        if hasattr(self.uistate.plot, "dict_group_show"):
            show = self.uistate.plot.dict_group_show
            self.uistate.plot.dict_group_show = {
                k: v
                for k, v in show.items()
                if (v.get("level") == active_level) or (v.get("level") is None)
            }

    def _ensure_reference_hlines(self, uistate) -> None:
        if "Events y zero marker" not in self.uistate.plot.dict_rec_labels:
            hline0 = self.uistate.plot.axe.axhline(0, linestyle="dotted", alpha=0.3)
            self.uistate.plot.dict_rec_labels["Events y zero marker"] = {
                **plot_model.reference_hline_label_entry(axis="axe", display_label="Events y zero marker"),
                "line": hline0,
            }
        uistate.plot.dict_rec_labels["Events y zero marker"]["line"].set_visible(True)

        if uistate.project.checkBox["norm_EPSP"]:
            if "Output y 100% marker" not in self.uistate.plot.dict_rec_labels:
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
                    **plot_model.reference_hline_label_entry(axis="ax1", display_label="output amp 100% marker"),
                    "line": hline100ax1,
                }
                self.uistate.plot.dict_rec_labels["output slope 100% marker"] = {
                    **plot_model.reference_hline_label_entry(axis="ax2", display_label="output slope 100% marker"),
                    "line": hline100ax2,
                }
            uistate.plot.dict_rec_labels["output amp 100% marker"]["line"].set_visible(uistate.ampView())
            uistate.plot.dict_rec_labels["output slope 100% marker"]["line"].set_visible(uistate.slopeView())

    def _set_plot_artist_visible(self, artist, visible: bool) -> None:
        if hasattr(artist, "set_visible"):
            artist.set_visible(visible)
        elif hasattr(artist, "patches"):
            for patch in artist.patches:
                patch.set_visible(visible)
        elif hasattr(artist, "lines"):
            for line in artist.lines:
                if line is None:
                    continue
                if isinstance(line, (list, tuple)):
                    for sub_line in line:
                        if sub_line is not None:
                            sub_line.set_visible(visible)
                else:
                    line.set_visible(visible)

    def _apply_drag_output_update(
        self,
        update: plot_stim.DragOutputUpdate,
        dfoutput,
        stim_num: int,
        *,
        rec_ID=None,
        aspect_field=None,
        norm_epsp: bool = False,
    ) -> None:
        if update.method == "from_df":
            self.updateOutLineFromDf(
                update.label,
                dfoutput,
                stim_num,
                update.column,
                rec_ID=rec_ID,
                aspect_field=aspect_field,
                norm_epsp=norm_epsp or (update.column or "").endswith("_norm"),
            )
        elif update.method == "out_line":
            # Live preview may be absent (Preview off / cleared); use df when possible.
            col = update.column
            if not col and aspect_field:
                col = f"{aspect_field}_norm" if norm_epsp else aspect_field
            if self.uistate.plot.mouseover_out is None and dfoutput is not None and col:
                self.updateOutLineFromDf(
                    update.label,
                    dfoutput,
                    stim_num,
                    col,
                    rec_ID=rec_ID,
                    aspect_field=aspect_field,
                    norm_epsp=norm_epsp or str(col).endswith("_norm"),
                )
            else:
                self.updateOutLine(
                    update.label,
                    rec_ID=rec_ID,
                    stim=stim_num,
                    aspect_field=aspect_field,
                    norm_epsp=norm_epsp,
                )
        elif update.method == "out_mean":
            self.updateOutMean(update.label, update.mean_value, rec_ID=rec_ID, aspect_field=aspect_field)

    def _refresh_output_legends(self, uistate, *, is_pp: bool, current_level: str) -> None:
        dd_recs = uistate.plot.dict_rec_show
        dd_group_show = uistate.plot.dict_group_show
        legend_loc = list(
            plot_model.output_legend_locations(
                experiment_type=uistate.experiment.experiment_type,
                slope_only=uistate.slopeOnly(),
            )
        )
        for axid, loc in zip(["ax1", "ax2"], legend_loc):
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
                    leg = axis.legend(list(axis_legend.values()), list(axis_legend.keys()), loc=loc, fontsize=8)
                except TypeError:
                    leg = axis.legend(list(axis_legend.values()), list(axis_legend.keys()), loc=loc, fontsize=8)
                if leg is not None:
                    leg.set_zorder(10)
            elif axis.get_legend():
                axis.get_legend().remove()
        for axid in ["axm", "axe"]:
            axis = getattr(uistate.plot, axid)
            if axis.get_legend():
                axis.get_legend().remove()

    def _configure_event_axis(self, axe) -> None:
        axe.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 1e3:.1f}"))
        axe.set_ylabel(plot_model.EVENT_AXIS_YLABEL)
        axe.xaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t * 1e3:.1f}"))
        axe.set_xlabel(plot_model.EVENT_AXIS_XLABEL)

    def _configure_output_axes(self, uistate, ax1, ax2) -> str:
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
        if exp_type != "PP":
            ax1.set_xlabel(uistate.x_axis_xlabel())
            ax1.xaxis.set_major_locator(uistate.x_axis_locator())
            ax2.xaxis.set_major_locator(uistate.x_axis_locator())
        return exp_type

    def _apply_pp_reference_grid(self, ax1, ax2) -> None:
        for ax in [ax1, ax2]:
            lines_to_remove = [line for line in ax.lines if line.get_linestyle() == ":" and line.get_color() == "gray"]
            for line in lines_to_remove:
                try:
                    line.remove()
                except Exception:
                    pass
        for y_val in plot_model.pp_reference_grid_y_values():
            ax1.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)
            ax2.axhline(y_val, color="gray", linestyle=":", alpha=0.5, zorder=0)

    def _apply_pp_graph_refresh_axes(self, uistate, ax1, ax2, current_level: str) -> None:
        # Shared x ticks across twin axes: amp (ax1) + slope (ax2) sit side-by-side,
        # and only ax1 shows the bottom labels (oneAxisLeft hides ax2.xaxis).
        pp_has_recs = hasattr(self.uistate.plot, "dict_rec_show") and plot_series.pp_has_visible_rec_ppr(
            uistate.plot.dict_rec_show
        )
        bar_specs = []
        if hasattr(self.uistate.plot, "dict_group_show"):
            bar_specs = plot_series.collect_pp_group_bar_patch_specs(
                uistate.plot.dict_group_show,
                current_level,
                lambda base: self._display_label(base),
            )
        pp_xplan = plot_series.build_pp_graph_refresh_xaxis_plan(
            bar_specs,
            uistate.project.checkBox,
            pp_has_recs=pp_has_recs,
        )
        self._apply_pp_graph_refresh_xaxis(ax1, pp_xplan)
        self._apply_pp_graph_refresh_xaxis(ax2, pp_xplan)
        # Keep zoom state in sync so later zoomReset does not clamp the last group to the edge.
        if bar_specs and pp_xplan.ticks:
            xlim = plot_series.pp_group_xlim_from_ticks(pp_xplan.ticks, pad=0.6)
            if xlim is not None:
                uistate.project.zoom["output_xlim"] = xlim

    def _maintain_drag_selections(self, uistate, axm, ax1, ax2) -> None:
        if uistate.plot.x_select["mean_start"] is not None:
            self.xSelect(canvas=axm.figure.canvas, draw=False)
        if uistate.plot.x_select["output_start"] is not None:
            if uistate.project.checkBox["EPSP_slope"]:
                self.xSelect(canvas=ax2.figure.canvas, draw=False)
            else:
                self.xSelect(canvas=ax1.figure.canvas, draw=False)

    def _refresh_sample_inset_and_overlays(self, uistate, dd_groups, dd_testset, dd_shown_samples) -> None:
        if dd_testset is not None:
            self.visualize_test_sets(dd_testset=dd_testset, draw=False)
            self.uistate.plot.sample_dirty = True
            self.sample_overlay(dd_groups=dd_groups, dd_testset=dd_testset, dd_shown_samples=dd_shown_samples or {})
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

    def _draw_graph_canvases(self, axm, axe, ax1) -> None:
        axm.figure.canvas.draw_idle()
        axe.figure.canvas.draw_idle()
        ax1.figure.canvas.draw_idle()

    def _apply_pp_graph_refresh_xaxis(self, ax, plan):
        """Apply PP x ticks/labels/limits to one output axis."""
        if plan.ax1_xlabel is not None:
            ax.set_xlabel(plan.ax1_xlabel)
        if plan.ticks:
            ax.set_xticks(list(plan.ticks))
            ax.set_xticklabels(list(plan.ticklabels))
            xlim = plot_series.pp_group_xlim_from_ticks(plan.ticks, pad=0.6)
            if xlim is not None:
                ax.set_xlim(xlim)
        if plan.hide_all:
            ax.tick_params(axis="x", bottom=False, labelbottom=False)
        elif plan.labels_only:
            ax.tick_params(axis="x", bottom=False, labelbottom=True)

    def graphRefresh(self, dd_groups, dd_testset=None, dd_shown_samples=None):
        uistate = self.uistate
        if uistate.plot.axm is None:
            print("No axes to refresh")
            return
        t0 = time.time()
        is_pp = uistate.experiment.experiment_type == "PP"
        current_level = uistate.stat_test.buttonGroup_test_n
        axm, axe, ax1, ax2 = (
            self.uistate.plot.axm,
            self.uistate.plot.axe,
            self.uistate.plot.ax1,
            self.uistate.plot.ax2,
        )

        self._refresh_output_legends(uistate, is_pp=is_pp, current_level=current_level)
        axm.axis("off")
        self._configure_event_axis(axe)
        exp_type = self._configure_output_axes(uistate, ax1, ax2)
        if exp_type == "PP":
            self._apply_pp_reference_grid(ax1, ax2)
            self._apply_pp_graph_refresh_axes(uistate, ax1, ax2, current_level)
        ax1.figure.subplots_adjust(bottom=0.2)
        self.oneAxisLeft()
        self._maintain_drag_selections(uistate, axm, ax1, ax2)
        self._refresh_sample_inset_and_overlays(uistate, dd_groups, dd_testset, dd_shown_samples)
        self._ensure_reference_hlines(uistate)
        self.update_axe_mean(draw=False)
        self._draw_graph_canvases(axm, axe, ax1)
        if uistate.stat_test.formal_test_results:
            try:
                self.show_test_markers(uistate.stat_test.formal_test_results)
            except Exception:
                pass
        print(f" - - graphRefresh total: {round((time.time() - t0) * 1000)} ms")

    def oneAxisLeft(self):
        ax1, ax2 = self.uistate.plot.ax1, self.uistate.plot.ax2
        ax1.set_visible(True)
        ax2.set_visible(True)
        ax1.xaxis.set_visible(True)
        ax2.xaxis.set_visible(False)

        plan = plot_model.build_one_axis_left_plan(
            amp_view=self.uistate.ampView(),
            slope_view=self.uistate.slopeView(),
            slope_only=self.uistate.slopeOnly(),
        )
        ax1.yaxis.set_visible(plan.ax1_yaxis_visible)
        ax2.yaxis.set_visible(plan.ax2_yaxis_visible)
        if plan.ax2_yaxis_on_left:
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
        """Per-stim colors on axm: dark indigo-blue → purple (no orange = 'error' signal).

        Start is a darker blue than EPSP amp (0.2, 0.25, 0.85), then hue shifts toward purple.
        """
        if n_stims <= 0:
            return {}
        colors = [
            (0.12, 0.18, 0.55),  # indigo: darker blue than EPSP amp marker
            (0.35, 0.22, 0.72),  # blue → purple
            (0.58, 0.28, 0.82),  # purple / violet
        ]
        cmap = LinearSegmentedColormap.from_list("stim_indigo_violet", colors)
        denom = max(n_stims - 1, 1)
        return {i: cmap(i / denom) for i in range(n_stims)}

    def _output_line_style_kwargs(self) -> dict:
        """Marker/linestyle for ax1/ax2 output series from uistate.plot.output_line_style."""
        # Prefer project-persisted style; fall back to session / dots default.
        style = getattr(getattr(self.uistate, "project", None), "output_line_style", None)
        if style not in ("dots", "line"):
            style = getattr(self.uistate.plot, "output_line_style", "dots")
        if style == "dots":
            return {"marker": "o", "markersize": 3, "linestyle": "None"}
        return {"marker": None, "markersize": None, "linestyle": "-"}

    def apply_output_line_style(self, *, draw: bool = True) -> None:
        """Restyle existing ax1/ax2 Line2D artists (graphRefresh does not recreate them).

        Skips PathCollection/scatter and non-line artists. Group SEM fills are
        under key \"fill\" and are left unchanged.
        """
        kw = self._output_line_style_kwargs()
        marker = kw.get("marker")
        markersize = kw.get("markersize")
        linestyle = kw.get("linestyle")
        if linestyle is None:
            linestyle = "-"

        for store_name in ("dict_rec_labels", "dict_group_labels"):
            store = getattr(self.uistate.plot, store_name, None) or {}
            for _key, entry in store.items():
                if not isinstance(entry, dict):
                    continue
                if entry.get("axis") not in ("ax1", "ax2"):
                    continue
                line = entry.get("line")
                if line is None or not hasattr(line, "set_linestyle"):
                    continue
                try:
                    if marker:
                        line.set_linestyle("None")
                        line.set_marker(marker)
                        if markersize is not None:
                            line.set_markersize(markersize)
                    else:
                        line.set_marker("None")
                        line.set_linestyle(linestyle if linestyle not in (None, "None") else "-")
                except Exception:
                    pass

        if draw:
            ax1 = getattr(self.uistate.plot, "ax1", None)
            if ax1 is not None:
                ax1.figure.canvas.draw_idle()

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
        role=None,
    ):
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        if is_pp and axid in ("ax1", "ax2") and "PPR" in label:
            zorder = 4  # rec PPR blobs over group overlays
        elif axid in ("ax1", "ax2"):
            zorder = 2  # rec output over group means (zorder 1)
        else:
            zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.project.settings["alpha_line"]
        kwargs = {"color": color, "label": label, "alpha": alpha, "linewidth": width, "zorder": zorder, "linestyle": linestyle}
        if marker is not None:
            kwargs["marker"] = marker
        if markersize is not None:
            kwargs["markersize"] = markersize
        (line,) = self.get_axis(axid).plot(x, y, **kwargs)
        line.set_visible(False)
        if role is None:
            role = plot_identity.infer_rec_role(label, kind="line", axid=axid, aspect=aspect, variant=variant)
        storage_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=role, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[storage_key] = {
            **plot_model.rec_label_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                role=role,
                display_label=label,
            ),
            "line": line,
            "base_color": color,
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
        role=None,
    ):
        alpha = self.uistate.project.settings.get("alpha_shade", 0.3)
        fill = self.get_axis(axid).fill_between(x, y_mean - sem, y_mean + sem, alpha=alpha, color=color, zorder=0)
        fill.set_visible(False)
        if role is None:
            role = plot_identity.ROLE_SHADE
        storage_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=role, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[storage_key] = {
            **plot_model.rec_label_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                role=role,
                display_label=label,
            ),
            "line": fill,
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
        role=None,
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
        if role is None:
            role = plot_identity.infer_rec_role(label, kind="marker", axid=axid, aspect=aspect, variant=variant)
        storage_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=role, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[storage_key] = {
            **plot_model.rec_label_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                role=role,
                display_label=label,
            ),
            "line": marker,
            "base_color": color,
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
        is_zero_width = plot_stim.amp_x_is_zero_width(amp_x)
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
        x_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=plot_identity.ROLE_AMP_X, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        y_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=plot_identity.ROLE_AMP_Y, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[x_key] = {
            **plot_model.amp_width_marker_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                is_zero_width=is_zero_width,
                role=plot_identity.ROLE_AMP_X,
                display_label=f"{label} x marker",
            ),
            "line": xline,
            "base_color": color,
        }
        self.uistate.plot.dict_rec_labels[y_key] = {
            **plot_model.amp_width_marker_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                is_zero_width=False,
                role=plot_identity.ROLE_AMP_Y,
                display_label=f"{label} y marker",
            ),
            "line": yline,
            "base_color": color,
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
        role=None,
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
        if role is None:
            role = plot_identity.infer_rec_role(label, kind="vline", axid=axid, aspect=aspect, variant=variant)
        storage_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=role, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[storage_key] = {
            **plot_model.rec_label_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                role=role,
                display_label=label,
            ),
            "line": vline,
            "base_color": color,
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
        role=None,
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
        if role is None:
            role = plot_identity.infer_rec_role(label, kind="hline", axid=axid, aspect=aspect, variant=variant)
        storage_key = plot_identity.storage_key_rec(
            rec_ID=rec_ID, axis=axid, role=role, stim=stim, aspect=aspect, variant=variant, x_mode=x_mode
        )
        self.uistate.plot.dict_rec_labels[storage_key] = {
            **plot_model.rec_label_entry(
                rec_ID=rec_ID,
                aspect=aspect,
                variant=variant,
                stim=stim,
                axis=axid,
                x_mode=x_mode,
                role=role,
                display_label=label,
            ),
            "line": hline,
            "base_color": color,
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
            group_ID=group_ID,
            axis=axid,
        )
        raw_spec = line_specs[0]
        style_kw = self._output_line_style_kwargs()
        mean_plot_kw = {
            "color": color,
            "label": raw_spec.display_label,
            "alpha": self.uistate.project.settings["alpha_line"],
            "zorder": 1,
            "linewidth": 2.0,
            "linestyle": style_kw["linestyle"],
        }
        if style_kw["marker"] is not None:
            mean_plot_kw["marker"] = style_kw["marker"]
        if style_kw["markersize"] is not None:
            mean_plot_kw["markersize"] = style_kw["markersize"]
        (meanline,) = axis.plot(x_vals, y_mean_vals, **mean_plot_kw)
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
                display_label=raw_spec.display_label,
            ),
            "line": meanline,
            "fill": meanfill,
        }

        if series.y_norm is not None:
            norm_spec = line_specs[1]
            y_norm_vals = series.y_norm
            y_norm_sem_vals = series.y_norm_sem
            norm_plot_kw = {
                "color": color,
                "label": norm_spec.display_label,
                "alpha": self.uistate.project.settings["alpha_line"],
                "zorder": 1,
                "linewidth": 2.0,
                "linestyle": style_kw["linestyle"],
            }
            if style_kw["marker"] is not None:
                norm_plot_kw["marker"] = style_kw["marker"]
            if style_kw["markersize"] is not None:
                norm_plot_kw["markersize"] = style_kw["markersize"]
            (normline,) = axis.plot(x_vals, y_norm_vals, **norm_plot_kw)
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
                    display_label=norm_spec.display_label,
                ),
                "line": normline,
                "fill": normfill,
            }

    def _hide_plot_artist(self, artist) -> None:
        if hasattr(artist, "set_visible"):
            artist.set_visible(False)
        elif hasattr(artist, "patches"):
            for patch in artist.patches:
                patch.set_visible(False)
        elif hasattr(artist, "lines"):
            for line in artist.lines:
                if line is None:
                    continue
                if isinstance(line, (list, tuple)):
                    for sub_line in line:
                        if sub_line is not None:
                            sub_line.set_visible(False)
                else:
                    line.set_visible(False)

    def _render_io_recording_plot_spec(self, spec, rec_ID, color):
        axid = "ax1"
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
            sk = plot_identity.storage_key_rec(
                rec_ID=rec_ID,
                axis=axid,
                role=plot_identity.ROLE_IO_SCATTER,
                aspect=spec.aspect,
                variant=spec.variant,
                x_mode="io",
            )
            self.uistate.plot.dict_rec_labels[sk] = {
                **plot_model.io_rec_label_entry(
                    rec_ID=rec_ID,
                    aspect=spec.aspect,
                    variant=spec.variant,
                    axis=axid,
                    role=plot_identity.ROLE_IO_SCATTER,
                    display_label=spec.label,
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
            sk = plot_identity.storage_key_rec(
                rec_ID=rec_ID,
                axis=axid,
                role=plot_identity.ROLE_IO_TREND,
                aspect=spec.aspect,
                variant=spec.variant,
                x_mode="io",
            )
            self.uistate.plot.dict_rec_labels[sk] = {
                **plot_model.io_rec_label_entry(
                    rec_ID=rec_ID,
                    aspect=spec.aspect,
                    variant=spec.variant,
                    axis=axid,
                    role=plot_identity.ROLE_IO_TREND,
                    display_label=spec.label,
                ),
                "line": trendline,
            }

    def _render_pp_recording_plot_spec(self, spec, rec_ID):
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

    def _render_stim_aggregate_plot_spec(self, spec, rec_ID):
        style_kw = self._output_line_style_kwargs()
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
            marker=style_kw["marker"],
            markersize=style_kw["markersize"],
            linestyle=style_kw["linestyle"],
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
            style_kw = self._output_line_style_kwargs() if spec.axid in ("ax1", "ax2") else {}
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
                marker=style_kw.get("marker"),
                markersize=style_kw.get("markersize"),
                linestyle=style_kw.get("linestyle", "-"),
            )

    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)
        skip_output = plot_series.skip_pp_recording_output(self.uistate.experiment.experiment_type, n_stims)
        # Presentation stem only; storage keys use rec_ID. Real name stays in df_project.
        display_name = plot_identity.display_recording_name(
            rec_ID,
            rec_name,
            blind=bool(getattr(self.uistate.project, "blind_recordings", False)),
            aliases=getattr(self.uistate.project, "blind_aliases", None),
        )
        label = plot_series.recording_plot_label(display_name, rec_filter)

        if self.uistate.experiment.experiment_type == "io":
            _, y_col_base = plot_series.io_axis_columns(
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
            )
            color = self.uistate.project.settings.get(f"rgb_{y_col_base}", "black")
            force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
            for spec in plot_series.build_io_recording_plot_specs(
                dfoutput,
                label,
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
                force_through_zero=force0,
            ):
                self._render_io_recording_plot_spec(spec, rec_ID, color)

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
                self._render_pp_recording_plot_spec(spec, rec_ID)

        for spec in plot_series.build_stim_aggregate_plot_specs(dfoutput, label, settings):
            self._render_stim_aggregate_plot_spec(spec, rec_ID)

    def _render_pp_group_box_spec(self, spec, group_ID, group_name, color, level):
        """Draw box + unit dots; store geometry for ticks/export (no mean±SEM bar)."""
        ax = self.get_axis(spec.axid)
        vals = list(spec.values)
        bp = ax.boxplot(
            [vals],
            positions=[spec.box_x],
            widths=spec.box_width,
            patch_artist=True,
            showfliers=False,
            manage_ticks=False,
            whis=1.5,
        )
        for box in bp.get("boxes", []):
            box.set_facecolor(color)
            box.set_edgecolor("black")
            box.set_alpha(0.85)
            box.set_zorder(2)
        for med in bp.get("medians", []):
            med.set_color("black")
            med.set_linewidth(1.5)
            med.set_zorder(3)
        for key in ("whiskers", "caps"):
            for art in bp.get(key, []):
                art.set_color("black")
                art.set_zorder(2)

        box_artist = bp["boxes"][0] if bp.get("boxes") else None
        # Whiskers/medians/caps must share visibility with the box body (update_show
        # only flips line/fill keys).
        aux_artists = list(bp.get("medians", [])) + list(bp.get("whiskers", [])) + list(bp.get("caps", []))
        scat_artists = []
        for pt in spec.scatter_points:
            scat_art = ax.scatter(
                [pt.x],
                [pt.y],
                color=spec.scatter_color,
                edgecolor="black",
                zorder=4,
                s=40,
                label=f"{group_name} PPR {spec.aspect} {pt.rec_id} point",
            )
            scat_artists.append((scat_art, pt.rec_id))

        # Primary storage: box patch + metadata for ticks/export
        if box_artist is not None:
            self._hide_plot_artist(box_artist)
            for art in aux_artists:
                try:
                    self._hide_plot_artist(art)
                except Exception:
                    pass
            box_disp = f"{group_name} PPR {spec.aspect} box"
            box_key = plot_identity.storage_key_group(
                group_ID=group_ID,
                axis=spec.axid,
                role=plot_identity.ROLE_PP_BOX,
                aspect=spec.aspect,
                variant="raw",
                level=level,
                x_mode="sweep",
            )
            self.uistate.plot.dict_group_labels[box_key] = {
                **plot_model.pp_group_bar_label_entry(
                    group_ID=group_ID,
                    aspect=spec.aspect,
                    level=level,
                    axis=spec.axid,
                    rec_ID=None,
                    is_overlay=False,
                    role=plot_identity.ROLE_PP_BOX,
                    display_label=box_disp,
                ),
                "line": box_artist,
                "fill": box_artist,
                "pp_box_x": spec.box_x,
                "pp_box_width": spec.box_width,
                "pp_tick_label": spec.tick_label,
                "pp_values": list(spec.values),
                "pp_n": spec.n,
                "pp_group_color": color,
                "pp_aux_artists": aux_artists,
                "is_pp_box": True,
            }
        for scat_art, rid in scat_artists:
            self._hide_plot_artist(scat_art)
            pt_disp = f"{group_name} PPR {spec.aspect} {rid} point"
            pt_key = plot_identity.storage_key_group(
                group_ID=group_ID,
                axis=spec.axid,
                role=plot_identity.ROLE_PP_POINT,
                aspect=spec.aspect,
                variant="raw",
                level=level,
                x_mode="sweep",
                unit_id=rid,
            )
            self.uistate.plot.dict_group_labels[pt_key] = {
                **plot_model.pp_group_bar_label_entry(
                    group_ID=group_ID,
                    aspect=spec.aspect,
                    level=level,
                    axis=spec.axid,
                    rec_ID=rid,
                    is_overlay=False,
                    role=plot_identity.ROLE_PP_POINT,
                    display_label=pt_disp,
                ),
                "line": scat_art,
                "fill": scat_art,
            }

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
                    role=plot_identity.ROLE_IO_SCATTER,
                    display_label=spec.label,
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
                    role=plot_identity.ROLE_IO_TREND,
                    display_label=spec.label,
                ),
                "line": trendline,
                "fill": trendline,
            }

    def _host_get_df_project(self):
        """df_project for hierarchy (n_unit). Requires UIsub to set uiplot.uisub."""
        host = getattr(self, "uisub", None)
        if host is not None and hasattr(host, "get_df_project"):
            try:
                return host.get_df_project()
            except Exception:
                return None
        return None

    def _add_group_pp(self, group_ID, dict_group, x_pos, level):
        group_name = dict_group["group_name"]
        color = dict_group["color"]
        # Prefer data-driven PPR from dfoutput; fall back to artist scrape.
        rec_ppr: dict = {}
        host = getattr(self, "uisub", None)
        df_p = self._host_get_df_project()
        if host is not None and hasattr(host, "get_dfoutput") and df_p is not None and not df_p.empty:
            for rec_id in dict_group.get("rec_IDs", []):
                match = df_p[df_p["ID"] == rec_id]
                if match.empty:
                    # try string match
                    match = df_p[df_p["ID"].astype(str) == str(rec_id)]
                if match.empty:
                    continue
                try:
                    dfo = host.get_dfoutput(row=match.iloc[0])
                    means = plot_series.rec_mean_ppr_from_dfoutput(dfo)
                    if means:
                        rec_ppr[rec_id] = means
                except Exception:
                    continue
        if not rec_ppr:
            rec_ppr = plot_series.extract_rec_ppr_means(
                self.uistate.plot.dict_rec_labels,
                dict_group["rec_IDs"],
            )
        if level not in (None, "recording") and df_p is None:
            print(
                f"WARNING: PP group {group_ID} n_unit={level} without df_project; "
                "falling back to per-recording units (wire uiplot.uisub)."
            )
        aggregate = plot_series.aggregate_ppr_at_level(rec_ppr, level or "recording", df_p)
        for box_spec in plot_series.build_pp_group_box_plot_specs(
            aggregate=aggregate,
            x_pos=x_pos,
            group_name=group_name,
            checkbox=self.uistate.project.checkBox,
            settings=self.uistate.project.settings,
        ):
            try:
                self._render_pp_group_box_spec(box_spec, group_ID, group_name, color, level)
            except Exception as e:
                print(f"DEBUG: addGroup error in PP box drawing: {e}")

    def _add_group_io(self, group_ID, dict_group, level=None):
        _, y_col_base = plot_series.io_axis_columns(
            self.uistate.experiment.io_input,
            self.uistate.experiment.io_output,
        )
        color = dict_group["color"]
        group_name = dict_group["group_name"]
        io_level = level or self.uistate.stat_test.buttonGroup_test_n
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
                group_ID=group_ID,
                axis="ax1",
            ):
                self._render_io_group_plot_spec(spec, group_ID, color)

    def _add_group_means(self, group_ID, dict_group, df_groupmean, level):
        for axid, aspect, _col in plot_series.group_mean_plots_for_df(df_groupmean):
            self.plot_group_lines(axid, group_ID, dict_group, df_groupmean, aspect=aspect, level=level)

    def addGroup(self, group_ID, dict_group, df_groupmean, x_pos=1, level=None):
        """Add (or update) group artists for the given level.

        If level is None, it is taken from uistate.stat_test.buttonGroup_test_n.
        """
        eff_level = level or self.uistate.stat_test.buttonGroup_test_n
        exp_type = self.uistate.experiment.experiment_type
        if exp_type == "PP":
            self._add_group_pp(group_ID, dict_group, x_pos, eff_level)
            return
        if exp_type == "io":
            self._add_group_io(group_ID, dict_group, level=eff_level)
            return
        self._add_group_means(group_ID, dict_group, df_groupmean, eff_level)

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
        # Prefer display stem used at plot time (blind aliases) so string fallback still works
        rec_ID = prow["ID"]
        rec_filter = prow.get("filter")
        if pd.isna(rec_filter) or not rec_filter or rec_filter == "none":
            rec_filter = "voltage"
        display_name = plot_identity.display_recording_name(
            rec_ID,
            prow["recording_name"],
            blind=bool(getattr(self.uistate.project, "blind_recordings", False)),
            aliases=getattr(self.uistate.project, "blind_aliases", None),
        )
        label_core = plot_stim.drag_update_label_core(
            plot_series.recording_plot_label(display_name, rec_filter),
            "voltage",  # recording_plot_label already applied filter suffix
            trow["stim"],
            aspect,
        )
        is_pp = self.uistate.experiment.experiment_type == "PP"
        stim_num = trow["stim"]
        has_dfoutput = dfoutput is not None
        norm = self.uistate.project.checkBox["norm_EPSP"]
        aspect_field = aspect.replace(" ", "_")  # EPSP_amp / EPSP_slope / …

        if aspect in plot_stim.SLOPE_DRAG_ASPECTS:
            plan = plot_stim.build_slope_drag_update_plan(
                trow,
                aspect,
                trow["t_stim"],
                data_x,
                data_y,
                label_core,
                norm_epsp=norm,
                is_pp=is_pp,
                has_dfoutput=has_dfoutput,
            )
            self.updateLine(
                plan.marker_label,
                plan.marker_x,
                plan.marker_y,
                rec_ID=rec_ID,
                stim=stim_num,
                aspect_field=aspect_field,
            )
            for out_update in plan.output_updates:
                self._apply_drag_output_update(
                    out_update, dfoutput, stim_num, rec_ID=rec_ID, aspect_field=aspect_field, norm_epsp=norm
                )
        elif aspect in plot_stim.AMP_DRAG_ASPECTS:
            plan = plot_stim.build_amp_drag_update_plan(
                trow,
                aspect,
                trow["t_stim"],
                data_x,
                data_y,
                label_core,
                amp,
                amp_zero_plot,
                norm_epsp=norm,
                is_pp=is_pp,
                has_dfoutput=has_dfoutput,
            )
            geom = plan.geom
            self.updateAmpMarker(
                plan.label_core,
                geom.t_amp,
                geom.y_position,
                geom.amp_x,
                geom.amp_zero,
                amp=plan.amp,
                rec_ID=rec_ID,
                stim=stim_num,
                aspect_field=aspect_field,
            )
            for out_update in plan.output_updates:
                self._apply_drag_output_update(
                    out_update, dfoutput, stim_num, rec_ID=rec_ID, aspect_field=aspect_field, norm_epsp=norm
                )

    def _rec_entry_by_display(self, display_label: str):
        """Resolve dict_rec_labels entry by display_label (or legacy key)."""
        return plot_identity.find_entry_by_display_label(self.uistate.plot.dict_rec_labels, display_label)[1]

    def _resolve_rec_entry(
        self,
        display_label: str | None = None,
        *,
        rec_ID=None,
        stim=None,
        aspect=None,
        role=None,
        axis=None,
        variant=None,
        x_mode=None,
    ):
        """Prefer identity filters (rec_ID/stim/role/aspect); fall back to display_label."""
        store = self.uistate.plot.dict_rec_labels
        if rec_ID is not None and role is not None:
            hits = plot_identity.find_rec_entries(
                store,
                rec_ID=rec_ID,
                stim=stim,
                aspect=aspect,
                role=role,
                axis=axis,
                variant=variant,
                x_mode=x_mode,
            )
            if len(hits) == 1:
                return hits[0][1]
            if len(hits) > 1:
                if display_label:
                    for _k, ent in hits:
                        if ent.get("display_label") == display_label:
                            return ent
                return hits[0][1]
        if display_label:
            ent = self._rec_entry_by_display(display_label)
            if ent is not None:
                return ent
            return self.uistate.plot.dict_rec_labels.get(display_label)
        return None

    def updateAmpMarker(
        self,
        labelbase,
        x,
        y,
        amp_x,
        amp_zero,
        amp=None,
        draw=False,
        *,
        rec_ID=None,
        stim=None,
        aspect_field=None,
    ):
        axe = self.uistate.plot.axe
        x = np.atleast_1d(x)
        y = np.atleast_1d(y)
        marker_ent = self._resolve_rec_entry(
            f"{labelbase} marker",
            rec_ID=rec_ID,
            stim=stim,
            aspect=aspect_field,
            role=plot_identity.ROLE_ASPECT_MARKER,
            axis="axe",
        )
        if marker_ent is None:
            print(f"updateAmpMarker: missing marker for {labelbase!r}")
            return
        marker_ent["line"].set_data(x, y)
        amp_si = plot_stim.resolve_drag_amp_si(amp, float(y[0]), amp_zero)
        if amp_si is not None:
            is_zero_width = plot_stim.amp_x_is_zero_width(amp_x)
            amp_y = plot_stim.amp_width_y_coords(amp_si, amp_zero)
            x_ent = self._resolve_rec_entry(
                f"{labelbase} x marker",
                rec_ID=rec_ID,
                stim=stim,
                aspect=aspect_field,
                role=plot_identity.ROLE_AMP_X,
                axis="axe",
            )
            y_ent = self._resolve_rec_entry(
                f"{labelbase} y marker",
                rec_ID=rec_ID,
                stim=stim,
                aspect=aspect_field,
                role=plot_identity.ROLE_AMP_Y,
                axis="axe",
            )
            if x_ent is not None:
                x_ent["line"].set_data(amp_x, [amp_y[1], amp_y[1]])
                x_ent["is_zero_width"] = is_zero_width
            if y_ent is not None:
                y_ent["line"].set_data([x[0], x[0]], amp_y)
                y_ent["is_zero_width"] = False
        if draw:
            axe.figure.canvas.draw_idle()

    def updateLine(
        self,
        plot_to_update,
        x_data,
        y_data,
        draw=False,
        *,
        rec_ID=None,
        stim=None,
        aspect_field=None,
    ):
        axe = self.uistate.plot.axe
        dict_line = self._resolve_rec_entry(
            plot_to_update,
            rec_ID=rec_ID,
            stim=stim,
            aspect=aspect_field,
            role=plot_identity.ROLE_ASPECT_MARKER,
            axis="axe",
        )
        if dict_line is None:
            print(f"updateLine: missing {plot_to_update!r}")
            return
        dict_line["line"].set_data(x_data, y_data)
        if draw:
            axe.figure.canvas.draw_idle()

    def updateOutLine(self, label, *, rec_ID=None, stim=None, aspect_field=None, norm_epsp: bool = False):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.plot.mouseover_out
        if mouseover_out is None:
            print(f"updateOutLine: mouseover_out is None, skipping update for '{label}'")
            return
        role = plot_identity.ROLE_SERIES_NORM if norm_epsp else plot_identity.ROLE_SERIES
        linedict = self._resolve_rec_entry(
            label,
            rec_ID=rec_ID,
            stim=stim,
            aspect=aspect_field,
            role=role,
            axis=None,
            variant="norm" if norm_epsp else "raw",
            x_mode="sweep",
        )
        if linedict is None:
            return
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
        rec_ID = None
        for ent in dict_rec_labels.values():
            if isinstance(ent, dict) and ent.get("display_label", "").startswith(rec_name):
                rec_ID = ent.get("rec_ID")
                break
        for spec in plot_series.build_io_refresh_specs_for_rec(
            rec_name,
            dict_rec_labels,
            dfoutput,
            self.uistate.experiment.io_input,
            self.uistate.experiment.io_output,
            force_through_zero=force0,
            rec_ID=rec_ID,
        ):
            linedict = dict_rec_labels.get(spec.label) or self._rec_entry_by_display(spec.label)
            if linedict is None:
                continue
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
            dict_rec_labels=dict_rec_labels,
            rec_ID=rec_ID,
        ):
            linedict = dict_rec_labels.get(spec.line_label) or self._rec_entry_by_display(spec.line_label)
            if linedict is None:
                continue
            linedict["line"].set_xdata(spec.x)
            linedict["line"].set_ydata(spec.y)
            print(f"updateStimLines: refreshed '{spec.line_label}'")

            if spec.shade_label is not None and spec.sem is not None:
                old_shade_dict = dict_rec_labels.get(spec.shade_label) or self._rec_entry_by_display(spec.shade_label)
                if old_shade_dict is None:
                    continue
                try:
                    old_shade_dict["line"].remove()
                except Exception:
                    pass
                # Drop old storage key so plot_shade can re-register under identity key
                for k, v in list(dict_rec_labels.items()):
                    if v is old_shade_dict:
                        del dict_rec_labels[k]
                        break
                color = self.uistate.project.settings.get(spec.color_setting_key, "black")
                shade_disp = old_shade_dict.get("display_label") or f"{rec_name} shade"
                self.plot_shade(
                    shade_disp,
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
                new_shade = self._rec_entry_by_display(shade_disp)
                if new_shade is not None:
                    new_shade["line"].set_visible(linedict["line"].get_visible())

    def updateOutLineFromDf(
        self,
        label,
        dfoutput,
        stim_num,
        column,
        x_axis=None,
        *,
        rec_ID=None,
        aspect_field=None,
        norm_epsp: bool = False,
    ):
        """Populate an output line directly from a dfoutput DataFrame.

        Used on drag-release for amp aspects so that the persisted full-width
        mean values are reflected in the plot, rather than the single-point
        live-drag preview held in mouseover_out.

        Parameters
        - label: display_label fallback (identity preferred when rec_ID given)
        - dfoutput: the fully-recalculated output DataFrame
        - stim_num: stim number (1-based) to filter dfoutput rows
        - column: column name to use for y-values (e.g. 'EPSP_amp' or 'EPSP_amp_norm')
        """
        print(f"updateOutLineFromDf: {label}, stim={stim_num}, col={column}")
        xy = plot_series.out_line_xy_from_df(dfoutput, stim_num, column)
        if xy is None:
            print(f"updateOutLineFromDf: no data for stim={stim_num} col={column}, falling back to updateOutLine")
            self.updateOutLine(
                label, rec_ID=rec_ID, stim=stim_num, aspect_field=aspect_field, norm_epsp=norm_epsp
            )
            return

        role = plot_identity.ROLE_SERIES_NORM if norm_epsp or str(column).endswith("_norm") else plot_identity.ROLE_SERIES
        aspect = aspect_field or str(column).replace("_norm", "")
        linedict = self._resolve_rec_entry(
            label,
            rec_ID=rec_ID,
            stim=stim_num,
            aspect=aspect,
            role=role,
            variant="norm" if role == plot_identity.ROLE_SERIES_NORM else "raw",
            x_mode="sweep",
        )
        if linedict is None:
            if self.uistate.experiment.experiment_type == "PP":
                rec_label = label.split(" - stim ")[0]
                for spec in plot_series.build_ppr_overlay_refresh_specs(
                    rec_label,
                    dfoutput,
                    aspect,
                    self.uistate.project.checkBox,
                    self.uistate.project.settings,
                    frozenset(self.uistate.plot.dict_rec_labels.keys()),
                ):
                    ent = self.uistate.plot.dict_rec_labels.get(spec.label) or self._rec_entry_by_display(spec.label)
                    if ent is None:
                        continue
                    ent["line"].set_xdata(spec.x)
                    ent["line"].set_ydata(spec.y)
            return

        x_mode = linedict.get("x_mode", "sweep")
        xy = plot_series.out_line_xy_from_df(dfoutput, stim_num, column, x_mode=x_mode)
        if xy is None:
            self.updateOutLine(
                label, rec_ID=rec_ID, stim=stim_num, aspect_field=aspect_field, norm_epsp=norm_epsp
            )
            return
        linedict["line"].set_xdata(xy[0])
        linedict["line"].set_ydata(xy[1])

    def updateOutMean(self, label, mean, *, rec_ID=None, aspect_field=None):
        """Update a mean *axhline* (e.g. volley amp/slope mean) to a new y level.

        Must not copy geometry from mouseover_out: that artist is the live rec
        series preview (N sweeps) and pairing set_xdata(N) with set_ydata(2)
        from the hline's old length crashes matplotlib draw (broadcast mismatch).
        """
        print(f"updateOutMean: {label}, {mean}")
        linedict = self._resolve_rec_entry(
            label,
            rec_ID=rec_ID,
            aspect=aspect_field,
            role=plot_identity.ROLE_SERIES_MEAN_HLINE,
        )
        if linedict is None:
            return
        y = plot_stim.mean_hline_ydata(mean, x_len=2)
        if y is None:
            print(f"updateOutMean: invalid mean for '{label}', skip")
            return
        line = linedict["line"]
        # Heal prior corruption (series x glued onto an hline) by restoring a
        # two-point horizontal span on the current axes limits.
        x = plot_drag.artist_xdata(line)
        if x.size != 2:
            ax = getattr(line, "axes", None)
            if ax is not None:
                x0, x1 = ax.get_xlim()
                line.set_xdata([x0, x1])
            elif x.size > 0:
                line.set_xdata([float(x[0]), float(x[-1])])
            else:
                line.set_xdata([0.0, 1.0])
        line.set_ydata(y)

