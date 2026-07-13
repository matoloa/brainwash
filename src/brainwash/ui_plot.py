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
            self.uistate.plot.sample_inset = self.uistate.plot.ax1.inset_axes([0.02, 0.68, 0.20, 0.30])
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

        all_ys = []
        # Get ordered list of *shown* test sets (from dd_testset) once; used for
        # consistent line styles (solid/dashed/dotted) across groups.
        visible_test_list = [tid for tid, tset in sorted((dd_testset or {}).items()) if tset.get("show", False)]
        for g_idx, (group_ID, inner) in enumerate(dd_shown_samples.items()):
            # Robust lookup for group_ID (int vs str keys are a common silent-continue source
            # in this codebase; dd_shown_samples uses int keys from dict construction while
            # dd_groups often normalizes to str)
            if not inner or str(group_ID) not in {str(k) for k in (dd_groups or {})}:
                continue
            group_dict = (dd_groups or {}).get(str(group_ID), (dd_groups or {}).get(group_ID, {}))
            if not group_dict.get("show", True):
                continue
            color = group_dict.get("color", "#0000ff")
            for t_idx, test_id_raw in enumerate(visible_test_list):
                if str(test_id_raw) not in {str(k) for k in inner.keys()}:
                    continue
                test_id = str(test_id_raw)
                df = inner.get(test_id_raw) or inner.get(test_id)
                if df is None or df.empty:
                    continue
                col = self.uistate.project.settings.get("filter") or "voltage"
                if col not in df.columns:
                    col = df.columns[-1]  # safe fallback
                linestyle = "-" if t_idx == 0 else "--" if t_idx == 1 else ":"
                # y_offset = g_idx * 0.25  # larger offset for visibility on inset
                for stim_num in sorted(df.get("stim", pd.Series([1])).unique()):
                    df_event = df[df["stim"] == stim_num].copy() if "stim" in df.columns else df.copy()
                    y_data = df_event[col].values  # + y_offset
                    # Only use data after the artefact for ylim calculation
                    mask = df_event["time"].values > 0.001
                    all_ys.extend(y_data[mask])
                    key = (group_ID, test_id, stim_num)
                    if key in self.uistate.plot.sample_artists:
                        line = self.uistate.plot.sample_artists[key]
                        line.set_data(df_event["time"].values, y_data)
                        line.set_linestyle(linestyle)
                        line.set_zorder(11)
                        line.set_visible(True)
                    else:
                        (line,) = inset.plot(
                            df_event["time"].values,
                            y_data,
                            color=color,
                            alpha=0.75,
                            linewidth=1.0,
                            linestyle=linestyle,
                            label=f"sample_g{group_ID}_t{test_id}_s{stim_num}",
                            zorder=11,
                        )
                        # print(f"*** DF: {df_event}")
                        self.uistate.plot.sample_artists[key] = line

        if all_ys:
            ymin, ymax = min(all_ys), max(all_ys)
            inset.set_ylim(ymin * 1.1, ymax + 0.0001)
        inset.set_xlim(-0.005, 0.035)  # aligned event window
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
            # print(f" - selected sweep(s): {self.uistate.plot.x_select['output']}")
            # build mean of selected sweeps
            idx_rec = self.uistate.plot.list_idx_select_recs[0]
            rec_ID = self.uistate.plot.df_recs2plot.loc[idx_rec, "ID"]
            selected = self.uistate.plot.x_select["output"]
            df = self.uistate.plot.df_rec_select_data
            col = self.uistate.project.settings.get("filter") or "voltage"
            df_sweeps = df[df["sweep"].isin(selected)]
            df_mean = df_sweeps.groupby("time", as_index=False)[col].mean()
            # calculate offset for t_stim
            df_t = self.uistate.plot.df_rec_select_time
            n_stims = len(df_t)
            dict_gradient = self.get_dict_gradient(n_stims)
            alpha = self.uistate.project.settings["alpha_line"] / 2  # make mean-of-selected-lines more transparent
            for i_stim, t_row in df_t.iterrows():
                color = dict_gradient[i_stim]
                stim_num = i_stim + 1  # 1-numbering (visible to user)
                stim_str = f"- stim {stim_num}"
                t_stim = t_row["t_stim"]
                # add to Events
                window_start = t_stim + self.uistate.project.settings["event_start"]
                window_end = t_stim + self.uistate.project.settings["event_end"]
                df_event = df_mean[(df_mean["time"] >= window_start) & (df_mean["time"] <= window_end)].copy()
                df_event["time"] = df_event["time"] - t_stim  # shift event so that t_stim is at time 0
                self.plot_line(
                    f"axe mean selected sweeps {stim_str}",
                    "axe",
                    df_event["time"],
                    df_event[col],
                    color,
                    rec_ID,
                    stim=stim_num,
                    alpha=alpha,
                )
                self.uistate.plot.dict_rec_labels[f"axe mean selected sweeps {stim_str}"]["line"].set_visible(True)
        if draw:
            self.uistate.plot.axe.figure.canvas.draw_idle()

    def styleUpdate(self):
        axm, axe, ax1, ax2 = (
            self.uistate.plot.axm,
            self.uistate.plot.axe,
            self.uistate.plot.ax1,
            self.uistate.plot.ax2,
        )
        if self.uistate.darkmode:
            style.use("dark_background")
            for ax in [axm, axe, ax1, ax2]:
                ax.figure.patch.set_facecolor("#333333")
                ax.set_facecolor("#333333")
                ax.xaxis.label.set_color("white")
                ax.yaxis.label.set_color("white")
                ax.tick_params(colors="white")
            # print("Dark mode activated")
        else:
            style.use("default")
            for ax in [axm, axe, ax1, ax2]:
                ax.figure.patch.set_facecolor("white")
                ax.set_facecolor("white")
                ax.xaxis.label.set_color("black")
                ax.yaxis.label.set_color("black")
                ax.tick_params(colors="black")
            # print("Default mode activated")

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
        for axid, loc in zip(axids, legend_loc):
            recs_on_axis = {key: value for key, value in dd_recs.items() if value["axis"] == axid and not key.endswith(" marker")}
            axis_legend = {key: value["line"] for key, value in recs_on_axis.items()}
            if axid in ["ax1", "ax2"]:
                current_level = uistate.stat_test.buttonGroup_test_n
                groups_on_axis = {
                    key: value for key, value in dd_group_show.items()
                    if value["axis"] == axid and (value.get("level") == current_level or value.get("level") is None)
                }
                # use clean display labels (strip level suffix if present)
                for key, value in groups_on_axis.items():
                    display_key = self._display_label(key)
                    axis_legend[display_key] = value["line"]
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
        axe.set_ylabel("Voltage (mV)")
        axe.xaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t * 1e3:.1f}"))
        axe.set_xlabel("Time (ms)")

        exp_type = uistate.experiment.experiment_type
        axis_labels = plot_model.output_axis_ylabels(
            experiment_type=exp_type,
            io_output=uistate.experiment.io_output,
            norm_epsP=bool(uistate.project.checkBox["norm_EPSP"]),
        )
        ax1.set_ylabel(axis_labels.ax1_ylabel)
        ax2.set_ylabel(axis_labels.ax2_ylabel)
        if exp_type == "io":
            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        elif exp_type == "PP":
            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        else:
            ax1.tick_params(axis="x", bottom=True, length=3.5)
            ax2.tick_params(axis="x", bottom=True, length=3.5)
            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.xaxis.set_major_formatter(uistate.x_axis_formatter())

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
            ax1.set_xlabel("")
            ax2.set_xlabel("")

            # Re-collect the true integer X positions for group labels, ignoring the sub-offsets used for the individual bars
            bar_specs: list[tuple[float, float, str]] = []
            current_level = uistate.stat_test.buttonGroup_test_n
            if hasattr(self.uistate.plot, "dict_group_show"):
                for key, val in uistate.plot.dict_group_show.items():
                    if "PPR" in key and hasattr(val["line"], "patches") and not val.get("is_overlay"):
                        if val.get("level") and val.get("level") != current_level:
                            continue
                        try:
                            patch = val["line"].patches[0]
                            bar_specs.append(
                                (
                                    patch.get_x(),
                                    patch.get_width(),
                                    self._display_label(key.split(" PPR")[0]),
                                )
                            )
                        except Exception:
                            pass

            x_ticks, x_ticklabels = plot_series.pp_group_tick_label_map(bar_specs)
            group_name_to_x = dict(zip(x_ticks, x_ticklabels))

            if not x_ticks:
                ax1.tick_params(axis="x", bottom=False, labelbottom=False)
                ax2.tick_params(axis="x", bottom=False, labelbottom=False)
            else:
                ax1.set_xticks(x_ticks)
                ax1.set_xticklabels(x_ticklabels)
                ax2.set_xticks(x_ticks)
                ax2.set_xticklabels(x_ticklabels)

                # Turn off the tick *marks* (the physical lines), leaving just the labels
                ax1.tick_params(axis="x", bottom=False, labelbottom=True)
                ax2.tick_params(axis="x", bottom=False, labelbottom=True)

        # Check if recordings are visible instead of groups
        pp_has_recs = False
        if exp_type == "PP" and hasattr(self.uistate.plot, "dict_rec_show"):
            for key, val in uistate.plot.dict_rec_show.items():
                if "PPR" in key and "marker" not in key:
                    pp_has_recs = True
                    break

        if exp_type == "PP" and pp_has_recs and not group_name_to_x:
            x_ticks, x_ticklabels = plot_series.pp_recording_view_ticks(uistate.project.checkBox)

            if not x_ticks:
                ax1.set_xlabel("No aspect selected")
                ax1.tick_params(axis="x", bottom=False, labelbottom=False)
                ax2.tick_params(axis="x", bottom=False, labelbottom=False)
            else:
                ax1.set_xlabel("")
                ax2.set_xlabel("")
                ax1.set_xticks(x_ticks)
                ax1.set_xticklabels(x_ticklabels)
                ax2.set_xticks(x_ticks)
                ax2.set_xticklabels(x_ticklabels)
                ax1.tick_params(axis="x", bottom=False, labelbottom=True)
                ax2.tick_params(axis="x", bottom=False, labelbottom=True)

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
        str_aspect = aspect.replace("_", " ")
        eff_level = level or self.uistate.stat_test.buttonGroup_test_n
        label_mean = f"{group_name} {str_aspect} mean"
        label_norm = f"{group_name} {str_aspect} norm"
        mean_storage_key = self._level_key(label_mean, eff_level)
        norm_storage_key = self._level_key(label_norm, eff_level)
        series = plot_series.extract_group_mean_series(df_groupmean, aspect)
        x_vals = series.x
        y_mean_vals = series.y_mean
        y_sem_vals = series.y_sem
        (meanline,) = axis.plot(
            x_vals,
            y_mean_vals,
            color=color,
            label=label_mean,
            alpha=self.uistate.project.settings["alpha_line"],
            zorder=1,
            linewidth=2.0,
        )

        if series.y_norm is not None:
            y_norm_vals = series.y_norm
            y_norm_sem_vals = series.y_norm_sem
            (normline,) = axis.plot(
                x_vals,
                y_norm_vals,
                color=color,
                label=label_norm,
                alpha=self.uistate.project.settings["alpha_line"],
                zorder=1,
                linewidth=2.0,
            )

        meanfill = axis.fill_between(x_vals, y_mean_vals - y_sem_vals, y_mean_vals + y_sem_vals, alpha=0.25, color=color, zorder=0)

        if series.y_norm is not None:
            normfill = axis.fill_between(x_vals, y_norm_vals - y_norm_sem_vals, y_norm_vals + y_norm_sem_vals, alpha=0.25, color=color, zorder=0)

        meanline.set_visible(False)
        meanfill.set_visible(False)
        self.uistate.plot.dict_group_labels[mean_storage_key] = {
            "group_ID": group_ID,
            "stim": None,
            "aspect": aspect,
            "variant": "raw",
            "axis": axid,
            "line": meanline,
            "fill": meanfill,
            "x_mode": "sweep",
            "level": eff_level,
        }

        if series.y_norm is not None:
            normline.set_visible(False)
            normfill.set_visible(False)
            self.uistate.plot.dict_group_labels[norm_storage_key] = {
                "group_ID": group_ID,
                "stim": None,
                "aspect": aspect,
                "variant": "norm",
                "axis": axid,
                "line": normline,
                "fill": normfill,
                "x_mode": "sweep",
                "level": eff_level,
            }

    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)
        skip_output = plot_series.skip_pp_recording_output(self.uistate.experiment.experiment_type, n_stims)
        label = plot_series.recording_plot_label(rec_name, rec_filter)

        if self.uistate.experiment.experiment_type == "io":
            x_col, y_col_base = plot_series.io_axis_columns(
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
            )
            axid = "ax1"
            color = self.uistate.project.settings.get(f"rgb_{y_col_base}", "black")
            df_sweeps = dfoutput[dfoutput["sweep"].notna()]
            force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
            for variant in ["raw", "norm"]:
                y_col = plot_series.io_y_column(y_col_base, variant=variant)
                df_clean = plot_series.io_scatter_frame(df_sweeps, x_col, y_col)
                if df_clean is None:
                    continue

                scatter = self.get_axis(axid).scatter(
                    df_clean[x_col].values,
                    df_clean[y_col].values,
                    c=[color],
                    alpha=0.8,
                    label=f"{label} {variant} IO scatter",
                    s=20,
                    zorder=2,
                )
                scatter.set_visible(False)
                self.uistate.plot.dict_rec_labels[f"{label} {variant} IO scatter"] = {
                    "rec_ID": rec_ID,
                    "aspect": y_col_base,
                    "variant": variant,
                    "stim": None,
                    "line": scatter,
                    "axis": axid,
                    "x_mode": "io",
                }

                reg = plot_series.compute_io_regression(
                    df_clean[x_col].values,
                    df_clean[y_col].values,
                    force_through_zero=force0,
                )
                if reg is not None:
                    (trendline,) = self.get_axis(axid).plot(
                        reg.x_line,
                        reg.y_line,
                        color=color,
                        linestyle="--",
                        alpha=0.8,
                        label=f"{label} {variant} IO trendline",
                        zorder=1,
                    )
                    trendline.set_visible(False)
                    self.uistate.plot.dict_rec_labels[f"{label} {variant} IO trendline"] = {
                        "rec_ID": rec_ID,
                        "aspect": y_col_base,
                        "variant": variant,
                        "stim": None,
                        "line": trendline,
                        "axis": axid,
                        "x_mode": "io",
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

        for i_stim, t_row in dft.iterrows():
            color = dict_gradient[i_stim]
            stim_num = plot_stim.stim_num_from_index(i_stim)
            stim_str = f"- stim {stim_num}"
            t_stim = t_row["t_stim"]
            out = dfoutput[dfoutput["stim"] == stim_num]
            amp_zero_plot, _y_at_stim = plot_stim.amp_zero_and_y_at_stim(dfmean, t_stim, rec_filter)
            plot_stim.shift_stim_times(t_row, t_stim)

            self.plot_marker(f"mean {label} {stim_str} marker", "axm", t_stim, 0, color, rec_ID)
            self.plot_vline(
                f"mean {label} {stim_str} selection marker",
                "axm",
                t_stim,
                color,
                rec_ID,
                stim=stim_num,
            )

            df_event = plot_stim.event_window_df(
                dfmean, t_stim, settings["event_start"], settings["event_end"], rec_filter
            )
            self.plot_line(
                f"{label} {stim_str}",
                "axe",
                df_event["time"],
                df_event[rec_filter],
                color,
                rec_ID,
                stim=stim_num,
            )

            out_stim_row = out[out["sweep"].isna()]

            if not np.isnan(t_row["t_EPSP_amp"]):
                x_position = t_row["t_EPSP_amp"]
                y_position = plot_stim.y_at_event_time(df_event, x_position, rec_filter)
                self.plot_marker(
                    f"{label} {stim_str} EPSP amp marker",
                    "axe",
                    x_position,
                    y_position,
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                )
                amp_x = (
                    x_position - t_row["t_EPSP_amp_halfwidth"],
                    x_position + t_row["t_EPSP_amp_halfwidth"],
                )
                epsp_amp_val = plot_stim.resolve_epsp_amp_si(
                    out_stim_row, df_event, x_position, t_row, rec_filter, amp_zero_plot
                )
                amp_y = (amp_zero_plot, amp_zero_plot - epsp_amp_val)
                self.plot_amp_width(
                    f"{label} {stim_str} EPSP amp",
                    "axe",
                    x_position,
                    amp_x,
                    amp_y,
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                )
                self.plot_line(
                    f"{label} {stim_str} EPSP amp",
                    "ax1",
                    out["sweep"],
                    out["EPSP_amp"],
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                    variant="raw",
                    x_mode="sweep",
                )
                self.plot_line(
                    f"{label} {stim_str} EPSP amp norm",
                    "ax1",
                    out["sweep"],
                    out["EPSP_amp_norm"],
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                    variant="norm",
                    x_mode="sweep",
                )
                self.plot_line(
                    f"{label} {stim_str} amp_zero marker",
                    "axe",
                    list(plot_stim.AMP_ZERO_PRE_WINDOW),
                    [amp_zero_plot, amp_zero_plot],
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                )

            epsp_slope = plot_stim.slope_segment(
                df_event, t_row["t_EPSP_slope_start"], t_row["t_EPSP_slope_end"], rec_filter
            )
            if epsp_slope is not None:
                self.plot_line(
                    f"{label} {stim_str} EPSP slope marker",
                    "axe",
                    [epsp_slope.x_start, epsp_slope.x_end],
                    [epsp_slope.y_start, epsp_slope.y_end],
                    settings["rgb_EPSP_slope"],
                    rec_ID,
                    aspect="EPSP_slope",
                    stim=stim_num,
                    width=5,
                )
                self.plot_line(
                    f"{label} {stim_str} EPSP slope",
                    "ax2",
                    out["sweep"],
                    out["EPSP_slope"],
                    settings["rgb_EPSP_slope"],
                    rec_ID,
                    aspect="EPSP_slope",
                    stim=stim_num,
                    variant="raw",
                    x_mode="sweep",
                )
                self.plot_line(
                    f"{label} {stim_str} EPSP slope norm",
                    "ax2",
                    out["sweep"],
                    out["EPSP_slope_norm"],
                    settings["rgb_EPSP_slope"],
                    rec_ID,
                    aspect="EPSP_slope",
                    stim=stim_num,
                    variant="norm",
                    x_mode="sweep",
                )

            if not np.isnan(t_row["t_volley_amp"]):
                x_position = t_row["t_volley_amp"]
                y_position = plot_stim.y_at_event_time(df_event, x_position, rec_filter)
                volley_color = settings["rgb_volley_amp"]
                self.plot_marker(
                    f"{label} {stim_str} volley amp marker",
                    "axe",
                    t_row["t_volley_amp"],
                    y_position,
                    volley_color,
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                )
                amp_x = (
                    x_position - t_row["t_volley_amp_halfwidth"],
                    x_position + t_row["t_volley_amp_halfwidth"],
                )
                volley_amp_mean = plot_stim.resolve_volley_amp_si(
                    t_row, out_stim_row, df_event, x_position, rec_filter, amp_zero_plot
                )
                amp_y = amp_zero_plot, amp_zero_plot - volley_amp_mean
                self.plot_amp_width(
                    f"{label} {stim_str} volley amp",
                    "axe",
                    x_position,
                    amp_x,
                    amp_y,
                    volley_color,
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                )
                self.plot_hline(
                    f"{label} {stim_str} volley amp mean",
                    "ax1",
                    plot_stim.volley_amp_hline_mv(volley_amp_mean),
                    volley_color,
                    rec_ID,
                    aspect="volley_amp_mean",
                    stim=stim_num,
                    x_mode="sweep",
                )
                self.plot_line(
                    f"{label} {stim_str} volley amp",
                    "ax1",
                    out["sweep"],
                    out["volley_amp"],
                    volley_color,
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                    x_mode="sweep",
                )

            volley_slope = plot_stim.slope_segment(
                df_event, t_row["t_volley_slope_start"], t_row["t_volley_slope_end"], rec_filter
            )
            if volley_slope is not None:
                self.plot_line(
                    f"{label} {stim_str} volley slope marker",
                    "axe",
                    [volley_slope.x_start, volley_slope.x_end],
                    [volley_slope.y_start, volley_slope.y_end],
                    settings["rgb_volley_slope"],
                    rec_ID,
                    aspect="volley_slope",
                    stim=stim_num,
                    width=5,
                )
                volley_slope_mean = plot_stim.resolve_volley_slope_mean(t_row, out_stim_row, out)
                self.plot_hline(
                    f"{label} {stim_str} volley slope mean",
                    "ax2",
                    volley_slope_mean,
                    settings["rgb_volley_slope"],
                    rec_ID,
                    aspect="volley_slope_mean",
                    stim=stim_num,
                    x_mode="sweep",
                )
                self.plot_line(
                    f"{label} {stim_str} volley slope",
                    "ax2",
                    out["sweep"],
                    out["volley_slope"],
                    settings["rgb_volley_slope"],
                    rec_ID,
                    aspect="volley_slope",
                    stim=stim_num,
                    x_mode="sweep",
                )

        if self.uistate.experiment.experiment_type == "PP" and not skip_output:
            out_sweeps = dfoutput[dfoutput["sweep"].notna()]
            out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
            out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
            common_sweeps = out1.index.intersection(out2.index).dropna()
            if not common_sweeps.empty:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    for spec in plot_series.pp_recording_ppr_specs(
                        out1.loc[common_sweeps],
                        out2.loc[common_sweeps],
                        self.uistate.project.checkBox,
                        settings,
                    ):
                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {spec.aspect} {variant}",
                                spec.axid,
                                np.full(spec.n_points, spec.x_val),
                                spec.ppr,
                                spec.color,
                                rec_ID,
                                aspect=spec.aspect,
                                stim=None,
                                variant=variant,
                                x_mode="sweep",
                                marker="o",
                                markersize=10,
                                linestyle="None",
                            )

        out_stim = dfoutput[dfoutput["sweep"].isna()]
        if not out_stim.empty:
            df_sweeps = dfoutput[dfoutput["sweep"].notna()]
            df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)
            stims = out_stim["stim"].values
            for suffix, axid, col, color, variant in plot_series.stim_aggregate_line_configs(settings):
                if col not in out_stim.columns:
                    continue
                aspect = col.replace("_norm", "")
                self.plot_line(
                    f"{label} {suffix}",
                    axid,
                    stims,
                    out_stim[col].values,
                    color,
                    rec_ID,
                    aspect=aspect,
                    variant=variant,
                    x_mode="stim",
                )
                sem_vals = plot_series.stim_aggregate_sem(df_sem, out_stim, col)
                if sem_vals is not None:
                    self.plot_shade(
                        f"{label} {suffix} shade",
                        axid,
                        stims,
                        out_stim[col].values,
                        sem_vals,
                        color,
                        rec_ID,
                        aspect=aspect,
                        variant=variant,
                        x_mode="stim",
                    )

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

            # Find all PPR lines for recordings in this group
            # collect per-rec PPR means
            rec_ppr = {}
            for rec_id in dict_group["rec_IDs"]:
                rec_ppr[rec_id] = {}
                for key, linedict in self.uistate.plot.dict_rec_labels.items():
                    if linedict.get("rec_ID") == rec_id and "PPR" in key and linedict.get("variant") == "raw":
                        aspect = linedict.get("aspect")
                        if aspect:
                            y_data = plot_drag.artist_ydata(linedict["line"])
                            if y_data.size > 0:
                                valid_y = [y for y in y_data if np.isfinite(y)]
                                if valid_y:
                                    rec_ppr[rec_id][aspect] = np.mean(valid_y)

            level = eff_level or self.uistate.stat_test.buttonGroup_test_n
            ppr_data = {"EPSP_amp": [], "EPSP_slope": [], "volley_amp": [], "volley_slope": []}
            rec_id_order = {"EPSP_amp": [], "EPSP_slope": [], "volley_amp": [], "volley_slope": []}
            if level == "recording":
                for rec_id, ad in rec_ppr.items():
                    for asp, v in ad.items():
                        if asp in ppr_data:
                            ppr_data[asp].append(v)
                            rec_id_order[asp].append(rec_id)
            else:
                # aggregate at unit level
                df_p = None
                try:
                    if hasattr(self, "uisub") and self.uisub and hasattr(self.uisub, "get_df_project"):
                        df_p = self.uisub.get_df_project()
                except Exception:
                    df_p = None
                rec_to_unit = {}
                if df_p is not None:
                    for rec_id in rec_ppr:
                        mm = df_p[df_p["ID"] == rec_id]
                        if not mm.empty:
                            pr = mm.iloc[0]
                            if level == "subject":
                                uk = str(pr.get("subject", "unknown"))
                            else:
                                uk = f"{pr.get('subject', 'unknown')}_{pr.get('slice', '1')}"
                            rec_to_unit[rec_id] = uk
                unit_asp = defaultdict(lambda: defaultdict(list))
                for rec_id, ad in rec_ppr.items():
                    uk = rec_to_unit.get(rec_id, rec_id)
                    for asp, v in ad.items():
                        unit_asp[uk][asp].append(v)
                for uk, ad in unit_asp.items():
                    for asp, vlist in ad.items():
                        if asp in ppr_data and vlist:
                            ppr_data[asp].append(np.mean(vlist))

            active_aspects = plot_series.pp_active_aspects(self.uistate.project.checkBox)
            configs = plot_series.pp_bar_layout(active_aspects)

            for aspect, axid, offset, bar_w in configs:
                vals = ppr_data[aspect]
                if vals:
                    try:
                        mean_val, sem_val = plot_series.mean_sem(vals)
                        bar_x = x_pos + offset
                    except Exception as e:
                        print(f"DEBUG: addGroup error in math loop: {e}")
                        continue

                    try:
                        # 1. Plot the bar
                        bar_artist = self.get_axis(axid).bar(
                            [bar_x],
                            [mean_val],
                            width=bar_w,
                            color=color,
                            edgecolor="black",
                            alpha=1.0,
                            zorder=2,
                            label=f"{group_name} PPR {aspect} bar",
                        )
                        # 2. Plot error bars
                        err_artist = self.get_axis(axid).errorbar(
                            [bar_x],
                            [mean_val],
                            yerr=[sem_val],
                            fmt="none",
                            ecolor="black",
                            elinewidth=1.5,
                            capsize=5,
                            capthick=1.5,
                            zorder=3,
                            label=f"{group_name} PPR {aspect} err",
                        )
                        # 3. Plot individual points (only at recording level; at higher n_unit the 'vals' are unit aggregates)
                        scat_artists = []
                        if level == "recording" and 'rec_id_order' in locals() and aspect in rec_id_order:
                            # Jitter the points slightly along the X axis so they don't overlap perfectly
                            jitter = np.random.uniform(-0.06, 0.06, size=len(vals)) if len(vals) > 1 else np.array([0])
                            x_jittered = [bar_x] * len(vals) + jitter
                            aspect_color = self.uistate.project.settings.get(f"rgb_{aspect}", "white")

                            for j, (val, rid) in enumerate(zip(vals, rec_id_order[aspect])):
                                xj = x_jittered[j]
                                scat_art = self.get_axis(axid).scatter(
                                    [xj], [val], color=aspect_color, edgecolor="black", zorder=4, s=40, label=f"{group_name} PPR {aspect} {rid} point"
                                )
                                scat_artists.append((scat_art, rid))

                        # 4. Create overlay artists for Rec View
                        overlay_x = plot_series.pp_overlay_x_map(self.uistate.project.checkBox).get(aspect, 1)

                        overlay_bar_artist = self.get_axis(axid).bar(
                            [overlay_x],
                            [mean_val],
                            width=0.4,
                            color=color,
                            edgecolor="black",
                            alpha=0.2,
                            zorder=2,
                            label=f"{group_name} PPR {aspect} overlay_bar",
                        )
                        overlay_err_artist = self.get_axis(axid).errorbar(
                            [overlay_x],
                            [mean_val],
                            yerr=[sem_val],
                            fmt="none",
                            ecolor="black",
                            elinewidth=1.5,
                            capsize=5,
                            capthick=1.5,
                            zorder=3,
                            label=f"{group_name} PPR {aspect} overlay_err",
                        )

                        # Store artists so they can be hidden/shown or cleared
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
                                "group_ID": group_ID,
                                "aspect": aspect,
                                "variant": "raw",
                                "stim": None,
                                "line": artist,
                                "fill": artist,
                                "axis": axid,
                                "x_mode": "sweep",
                                "is_container": True,
                                "is_overlay": is_overlay,
                                "level": level,
                            }
                            if rec_id_val is not None:
                                d["rec_ID"] = rec_id_val
                            ppr_storage_key = self._level_key(f"{group_name} PPR {aspect} {suffix}", level)
                            self.uistate.plot.dict_group_labels[ppr_storage_key] = d
                    except Exception as e:
                        print(f"DEBUG: addGroup error in drawing loop: {e}")
                        continue
            return

        if exp_type == "io":
            _, y_col_base = plot_series.io_axis_columns(
                self.uistate.experiment.io_input,
                self.uistate.experiment.io_output,
            )
            axid = "ax1"
            color = dict_group["color"]
            group_name = dict_group["group_name"]

            for variant in ["raw", "norm"]:
                all_x = []
                all_y = []

                # find scatters in uistate.plot.dict_rec_labels
                for key, linedict in self.uistate.plot.dict_rec_labels.items():
                    if linedict.get("x_mode") == "io" and linedict.get("rec_ID") in dict_group["rec_IDs"]:
                        if key.endswith(f"{variant} IO scatter"):
                            scatter = linedict["line"]
                            offsets = scatter.get_offsets()
                            if len(offsets) > 0:
                                all_x.append(offsets[:, 0])
                                all_y.append(offsets[:, 1])

                if all_x and all_y:
                    x_vals = np.concatenate(all_x)
                    y_vals = np.concatenate(all_y)

                    scatter = self.get_axis(axid).scatter(
                        x_vals,
                        y_vals,
                        c=[color],
                        alpha=0.3,
                        label=f"{group_name} {variant} IO scatter",
                        s=20,
                        zorder=2,
                    )
                    scatter.set_visible(False)
                    io_level = self.uistate.stat_test.buttonGroup_test_n
                    io_storage_key = self._level_key(f"{group_name} {variant} IO scatter", io_level)
                    self.uistate.plot.dict_group_labels[io_storage_key] = {
                        "group_ID": group_ID,
                        "aspect": y_col_base,
                        "variant": variant,
                        "stim": None,
                        "line": scatter,
                        "fill": scatter,
                        "axis": axid,
                        "x_mode": "io",
                        "level": io_level,
                    }

                    reg = plot_series.compute_io_regression(
                        x_vals,
                        y_vals,
                        force_through_zero=bool(self.uistate.project.checkBox.get("io_force0", False)),
                    )
                    if reg is not None:
                        (trendline,) = self.get_axis(axid).plot(
                            reg.x_line,
                            reg.y_line,
                            color=color,
                            linestyle="-",
                            linewidth=2,
                            alpha=0.9,
                            label=f"{group_name} {variant} IO trendline",
                            zorder=3,
                        )
                        trendline.set_visible(False)
                        io_trend_key = self._level_key(f"{group_name} {variant} IO trendline", io_level)
                        self.uistate.plot.dict_group_labels[io_trend_key] = {
                            "group_ID": group_ID,
                            "aspect": y_col_base,
                            "variant": variant,
                            "stim": None,
                            "line": trendline,
                            "fill": trendline,
                            "axis": axid,
                            "x_mode": "io",
                            "level": io_level,
                        }
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

        # Validate input formats
        if not isinstance(prow, pd.Series):
            raise TypeError(f"prow must be pandas.Series, got {type(prow).__name__}")
        if not isinstance(trow, (pd.Series, dict)):
            raise TypeError(f"trow must be pandas.Series or dict, got {type(trow).__name__}")
        if isinstance(trow, dict) and not trow:
            raise ValueError("trow dict is empty")

        valid_aspects = ["EPSP slope", "volley slope", "EPSP amp", "volley amp"]
        if aspect not in valid_aspects:
            raise ValueError(f"aspect must be one of {valid_aspects}, got '{aspect}'")
        if not isinstance(data_x, np.ndarray):
            try:
                data_x = np.asarray(data_x)
            except (TypeError, ValueError):
                raise TypeError(f"data_x must be array-like, got {type(data_x).__name__}")
        if not isinstance(data_y, np.ndarray):
            try:
                data_y = np.asarray(data_y)
            except (TypeError, ValueError):
                raise TypeError(f"data_y must be array-like, got {type(data_y).__name__}")

        if len(data_x) != len(data_y):
            raise ValueError(f"data_x and data_y must have same length, got {len(data_x)} and {len(data_y)}")

        if amp is not None and not isinstance(amp, (int, float, np.number)):
            raise TypeError(f"amp must be numeric or None, got {type(amp).__name__}")

        # Validate required keys in trow
        required_keys = ["t_stim", "stim"]
        for key in required_keys:
            if key not in trow:
                raise KeyError(f"trow missing required key: '{key}'")

        # TODO: unspaghetti this mess
        norm = self.uistate.project.checkBox["norm_EPSP"]
        stim_offset = trow["t_stim"]
        rec_filter = prow.get("filter")
        rec_name = prow["recording_name"]
        if rec_filter != "voltage":
            label_core = f"{rec_name} ({rec_filter}) - stim {trow['stim']} {aspect}"
        else:
            label_core = f"{rec_name} - stim {trow['stim']} {aspect}"

        if aspect in ["EPSP slope", "volley slope"]:
            x_start = trow[f"t_{aspect.replace(' ', '_')}_start"] - stim_offset
            x_end = trow[f"t_{aspect.replace(' ', '_')}_end"] - stim_offset
            y_start = data_y[np.abs(data_x - x_start).argmin()]
            y_end = data_y[np.abs(data_x - x_end).argmin()]
            self.updateLine(f"{label_core} marker", [x_start, x_end], [y_start, y_end])

            is_pp = self.uistate.experiment.experiment_type == "PP"

            if aspect == "volley slope":
                volley_slope_mean = trow.get("volley_slope_mean")
                if is_pp:
                    stim_num = trow["stim"]
                    if dfoutput is not None:
                        self.updateOutLineFromDf(label_core, dfoutput, stim_num, aspect.replace(" ", "_"))
                else:
                    self.updateOutMean(f"{label_core} mean", volley_slope_mean)
            else:  # EPSP slope
                if norm:
                    label_core += " norm"
                if is_pp and dfoutput is not None:
                    stim_num = trow["stim"]
                    col = f"EPSP_slope_norm" if norm else "EPSP_slope"
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, col)
                else:
                    self.updateOutLine(label_core)
        elif aspect in ["EPSP amp", "volley amp"]:
            key = aspect.replace(" ", "_")
            t_amp = trow[f"t_{key}"] - stim_offset
            y_position = data_y[np.abs(data_x - t_amp).argmin()]
            amp_x = (
                t_amp - trow[f"t_{key}_halfwidth"],
                t_amp + trow[f"t_{key}_halfwidth"],
            )
            # amp_zero_plot: mean of axe data_y in the pre-stim region (data_x < 0).
            # data_x is already shifted so t_stim = 0, data_y is raw voltage.
            # This matches exactly what axe displays, regardless of filter column
            # or DC offset — and is consistent with addRow's amp_zero_plot.
            if amp_zero_plot is None:
                pre_stim_mask = (data_x >= -0.002) & (data_x < -0.001)
                amp_zero_plot = float(data_y[pre_stim_mask].mean()) if pre_stim_mask.any() else y_position
            self.updateAmpMarker(label_core, t_amp, y_position, amp_x, amp_zero_plot, amp=amp)
            is_pp = self.uistate.experiment.experiment_type == "PP"
            if aspect == "volley amp":
                volley_amp_mean = trow.get("volley_amp_mean")
                if dfoutput is not None:
                    stim_num = trow["stim"]
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, key)
                elif not is_pp:
                    self.updateOutLine(label_core)
                if not is_pp:
                    self.updateOutMean(f"{label_core} mean", volley_amp_mean)
            else:  # EPSP amp
                if norm:
                    label_core += " norm"
                if dfoutput is not None:
                    stim_num = trow["stim"]
                    col = f"{key}_norm" if norm else key
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, col)
                elif not is_pp:
                    self.updateOutLine(label_core)

    def updateAmpMarker(self, labelbase, x, y, amp_x, amp_zero, amp=None, draw=False):
        axe = self.uistate.plot.axe
        print(f"updateAmpMarker called with labelbase: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        x = np.atleast_1d(x)
        y = np.atleast_1d(y)
        print(f"updateAmpMarker: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        self.uistate.plot.dict_rec_labels[f"{labelbase} marker"]["line"].set_data(x, y)
        if amp is None or pd.isna(amp):
            amp = -(y[0] - amp_zero)

        if amp is not None and not pd.isna(amp):
            expected_amp = -(y[0] - amp_zero)
            if abs(expected_amp) > 1e-6 and abs(amp / expected_amp) > 50:
                amp = amp / 1000.0
            elif abs(expected_amp) <= 1e-6 and abs(amp) > 1e-3:
                amp = amp / 1000.0

            is_zero_width = amp_x[0] == amp_x[1]
            amp_y = amp_zero, (0 - amp) + amp_zero
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
        # Refresh IO scatter plot if it exists for this recording
        io_input = self.uistate.experiment.io_input
        io_output = self.uistate.experiment.io_output
        force0 = bool(self.uistate.project.checkBox.get("io_force0", False))
        for key, linedict in self.uistate.plot.dict_rec_labels.items():
            if key.startswith(rec_name) and key.endswith(" IO scatter") and linedict.get("x_mode") == "io":
                xy = plot_series.io_scatter_xy(
                    dfoutput, io_input, io_output, variant=linedict.get("variant", "raw")
                )
                if xy is not None:
                    linedict["line"].set_offsets(np.c_[xy[0], xy[1]])
                    print(f"updateStimLines: refreshed IO scatter '{key}'")

            elif key.startswith(rec_name) and key.endswith(" IO trendline") and linedict.get("x_mode") == "io":
                line_xy = plot_series.io_trendline_xy(
                    dfoutput,
                    io_input,
                    io_output,
                    variant=linedict.get("variant", "raw"),
                    force_through_zero=force0,
                )
                if line_xy is not None:
                    linedict["line"].set_data(line_xy[0], line_xy[1])
                    print(f"updateStimLines: refreshed IO trendline '{key}'")

        out_stim = dfoutput[dfoutput["sweep"].isna()]
        if out_stim.empty:
            return

        df_sweeps = dfoutput[dfoutput["sweep"].notna()]
        df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)

        for suffix, col in plot_series.STIM_MODE_SUFFIX_TO_COL.items():
            label = f"{rec_name} {suffix}"
            if label not in self.uistate.plot.dict_rec_labels:
                continue
            if col not in out_stim.columns:
                continue
            linedict = self.uistate.plot.dict_rec_labels[label]
            linedict["line"].set_xdata(out_stim["stim"].values)
            linedict["line"].set_ydata(out_stim[col].values)
            print(f"updateStimLines: refreshed '{label}'")

            shade_label = f"{label} shade"
            sem_vals = plot_series.stim_aggregate_sem(df_sem, out_stim, col)
            if shade_label in self.uistate.plot.dict_rec_labels and sem_vals is not None:
                old_shade_dict = self.uistate.plot.dict_rec_labels[shade_label]
                try:
                    old_shade_dict["line"].remove()
                except Exception:
                    pass

                axid = old_shade_dict["axis"]
                rec_ID = old_shade_dict["rec_ID"]
                aspect = old_shade_dict["aspect"]
                variant = old_shade_dict["variant"]
                color_setting_key = f"rgb_{aspect}"
                color = self.uistate.project.settings.get(color_setting_key, "black")

                self.plot_shade(
                    shade_label,
                    axid,
                    out_stim["stim"].values,
                    out_stim[col].values,
                    sem_vals,
                    color,
                    rec_ID,
                    aspect=aspect,
                    variant=variant,
                    x_mode="stim",
                )

                self.uistate.plot.dict_rec_labels[shade_label]["line"].set_visible(linedict["line"].get_visible())

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
        df_stim = dfoutput[dfoutput["stim"] == stim_num]
        if df_stim.empty or column not in df_stim.columns:
            print(f"updateOutLineFromDf: no data for stim={stim_num} col={column}, falling back to updateOutLine")
            self.updateOutLine(label)
            return

        if label not in self.uistate.plot.dict_rec_labels:
            is_pp = self.uistate.experiment.experiment_type == "PP"
            if is_pp:
                rec_label = label.split(" - stim ")[0]
                aspect = column.replace("_norm", "")
                out_sweeps = dfoutput[dfoutput["sweep"].notna()]
                out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                common_sweeps = out1.index.intersection(out2.index).dropna()
                if not common_sweeps.empty:
                    o1 = out1.loc[common_sweeps]
                    o2 = out2.loc[common_sweeps]
                    if aspect in o1.columns and aspect in o2.columns:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = plot_series.compute_ppr(
                                o1[aspect].values.astype(float),
                                o2[aspect].values.astype(float),
                            )
                        for variant in ["raw", "norm"]:
                            ppr_label = f"{rec_label} PPR {aspect} {variant}"
                            if ppr_label in self.uistate.plot.dict_rec_labels:
                                linedict = self.uistate.plot.dict_rec_labels[ppr_label]
                                line = linedict["line"]
                                overlay_x = plot_series.pp_overlay_x_map(self.uistate.project.checkBox).get(aspect, 1)
                                line.set_xdata(np.full(len(common_sweeps), overlay_x))
                                line.set_ydata(ppr)
            return

        linedict = self.uistate.plot.dict_rec_labels[label]
        x_col = linedict.get("x_mode", "sweep")
        if x_col not in df_stim.columns:
            x_col = "sweep"
        linedict["line"].set_xdata(df_stim[x_col].values)
        linedict["line"].set_ydata(df_stim[column].values)

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
