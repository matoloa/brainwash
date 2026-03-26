import time  # counting time for functions

import matplotlib.pyplot as plt  # for the scatterplot
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import style
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D  # for custom legend; TODO: still used?
from matplotlib.ticker import FuncFormatter

STIM_MARKER_SIZE = 10  # diameter in points; drives both rendering and hit-zone calculation


class UIplot:
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated: {self.uistate.anyView()}")

    def heatmap(self, df):
        ax1 = self.uistate.ax1
        ax2 = self.uistate.ax2

        if not hasattr(self.uistate, "dict_heatmap"):
            self.uistate.dict_heatmap = {}

        sweeps = df["sweep"].values
        pcols = [c for c in df.columns if c.startswith("p_")]

        for col in pcols:
            ps = df[col].values
            sig = ps < 0.05
            xs = sweeps[sig]

            if "amp" in col:
                ax = ax1
            elif "slope" in col:
                ax = ax2
            else:
                continue

            for x in xs:
                sc = ax.scatter([x], [0], marker="o", color="red")
                self.uistate.dict_heatmap.setdefault(col, {})[x] = sc

        ax1.figure.canvas.draw()
        ax2.figure.canvas.draw()

    def heatunmap(self):
        d = getattr(self.uistate, "dict_heatmap", None)
        if d is None:
            return
        ax = self.uistate.ax1
        # print(f"heatunmap: {d}")
        for col in list(d.keys()):
            for x, sc in list(d[col].items()):
                try:
                    sc.remove()
                except:
                    pass
            d[col].clear()

        d.clear()
        ax.figure.canvas.draw()

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
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        if ax == ax1 or ax == ax2:
            axlines = ax1.get_lines() + ax2.get_lines()
            axpatches = ax1.patches + ax2.patches
            if reset:
                self.uistate.x_select["output"] = set()
                self.uistate.x_select["output_start"] = None
                self.uistate.x_select["output_end"] = None
        else:  # axm
            axlines = list(ax.get_lines())
            axpatches = list(ax.patches)
            if reset:
                self.uistate.x_select["mean_start"] = None
                self.uistate.x_select["mean_end"] = None

        for line in axlines:
            if line.get_label().startswith("xSelect"):
                line.remove()
        for patch in axpatches:
            if patch.get_label().startswith("xSelect"):
                patch.remove()
        if reset:
            self.clear_axe_mean()
        if draw:
            ax.figure.canvas.draw()

    def xSelect(self, canvas, draw=True):
        # draws a selected range of x values on <canvas>
        if canvas == self.uistate.axm.figure.canvas:
            ax = self.uistate.axm
            self.xDeselect(ax, draw=False)
            if self.uistate.x_select["mean_start"] is None:
                return
            if self.uistate.x_select["mean_end"] is None:
                # print(f"Selected x: {self.uistate.x_select['mean_start']}")
                ax.axvline(
                    x=self.uistate.x_select["mean_start"],
                    color="blue",
                    label="xSelect_x",
                )
            else:
                start, end = (
                    self.uistate.x_select["mean_start"],
                    self.uistate.x_select["mean_end"],
                )
                # print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color="blue", label="xSelect_start")
                ax.axvline(x=end, color="blue", label="xSelect_end")
                ax.axvspan(start, end, color="blue", alpha=0.1, label="xSelect_span")
        else:  # canvasOutput
            if self.uistate.checkBox["EPSP_slope"]:
                ax = self.uistate.ax2
            else:
                ax = self.uistate.ax1
            self.xDeselect(ax, draw=False)  # will clear both ax1 and ax2, if fed either one
            if self.uistate.x_select["output_end"] is None:
                # If only the start is selected, draw a line at the start
                # print(f"Selected x: {self.uistate.x_select['output_start']}")
                ax.axvline(
                    x=self.uistate.x_select["output_start"],
                    color="blue",
                    label="xSelect_x",
                )
            else:
                # If both start and end are selected, draw the range
                start, end = (
                    self.uistate.x_select["output_start"],
                    self.uistate.x_select["output_end"],
                )
                # print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color="blue", label="xSelect_start")
                ax.axvline(x=end, color="blue", label="xSelect_end")
                ax.axvspan(start, end, color="blue", alpha=0.1, label="xSelect_span")

        if draw:
            canvas.draw()

    def clear_axe_mean(self):
        # if uistate.dict_rec_labels exists and contains keys that start with "axe mean selected sweeps", remove their lines and del the items
        if self.uistate.dict_rec_labels:
            for key in [k for k in self.uistate.dict_rec_labels if k.startswith("axe mean selected sweeps")]:
                self.uistate.dict_rec_labels[key]["line"].remove()
                del self.uistate.dict_rec_labels[key]
        else:
            print(" - - - - No dict_rec_labels to clear mean sweeps from")

    def update_axe_mean(self, draw=True):
        """
        updates the mean of selected sweeps drawn on axe, called by ui.py after:
        * releasing drag on output, selecting sweeps
        * clicking odd/even buttons
        * TODO: writing sweep range in text boxes
        """
        self.clear_axe_mean()
        # if exactly one RECORDING is selected, plot the mean of selected SWEEPS one axe, if any
        if self.uistate.x_select["output"] and len(self.uistate.list_idx_select_recs) == 1:
            # print(f" - selected sweep(s): {self.uistate.x_select['output']}")
            # build mean of selected sweeps
            idx_rec = self.uistate.list_idx_select_recs[0]
            rec_ID = self.uistate.df_recs2plot.loc[idx_rec, "ID"]
            selected = self.uistate.x_select["output"]
            df = self.uistate.df_rec_select_data
            col = self.uistate.settings.get("filter") or "voltage"
            df_sweeps = df[df["sweep"].isin(selected)]
            df_mean = df_sweeps.groupby("time", as_index=False)[col].mean()
            # calculate offset for t_stim
            df_t = self.uistate.df_rec_select_time
            n_stims = len(df_t)
            dict_gradient = self.get_dict_gradient(n_stims)
            alpha = self.uistate.settings["alpha_line"] / 2  # make mean-of-selected-lines more transparent
            for i_stim, t_row in df_t.iterrows():
                color = dict_gradient[i_stim]
                stim_num = i_stim + 1  # 1-numbering (visible to user)
                stim_str = f"- stim {stim_num}"
                t_stim = t_row["t_stim"]
                # add to Events
                window_start = t_stim + self.uistate.settings["event_start"]
                window_end = t_stim + self.uistate.settings["event_end"]
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
                self.uistate.dict_rec_labels[f"axe mean selected sweeps {stim_str}"]["line"].set_visible(True)
        if draw:
            self.uistate.axe.figure.canvas.draw()

    def styleUpdate(self):
        axm, axe, ax1, ax2 = (
            self.uistate.axm,
            self.uistate.axe,
            self.uistate.ax1,
            self.uistate.ax2,
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

    def hideAll(self):
        axm, axe, ax1, ax2 = (
            self.uistate.axm,
            self.uistate.axe,
            self.uistate.ax1,
            self.uistate.ax2,
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
                        patch.remove()
                legend = ax.get_legend()
                if legend is not None:
                    legend.remove()
        print("All lines hidden")

    def unPlot(self, rec_ID=None):
        dict_rec = self.uistate.dict_rec_labels
        dict_show = self.uistate.dict_rec_show
        if rec_ID is None:
            keys_to_remove = list(dict_rec.keys())
        else:
            keys_to_remove = [key for key, value in dict_rec.items() if rec_ID == value["rec_ID"]]
        for key in keys_to_remove:
            dict_rec[key]["line"].remove()
            del dict_rec[key]
            if key in dict_show:
                del dict_show[key]
        if rec_ID is None:
            uis = self.uistate
            uis.mouseover_plot = None
            uis.mouseover_blob = None
            uis.mouseover_out = None
            uis.mouseover_action = None
            uis.ghost_sweep = None
            uis.ghost_label = None

    def unPlotGroup(self, group_ID=None):
        dict_group = self.uistate.dict_group_labels
        dict_group_show = self.uistate.dict_group_show
        if group_ID is None:
            keys_to_remove = list(dict_group.keys())  # Remove all if group_ID is None
        else:
            keys_to_remove = [key for key, value in dict_group.items() if group_ID == value["group_ID"]]
        for key in keys_to_remove:
            dict_group[key]["fill"].remove()
            dict_group[key]["line"].remove()
            del dict_group[key]
            if key in dict_group_show:
                del dict_group_show[key]

    def graphRefresh(self, dd_groups):
        # show only selected and imported lines, only appropriate aspects
        print("graphRefresh")
        uistate = self.uistate
        if uistate.axm is None:
            print("No axes to refresh")
            return
        t0 = time.time()

        # Set recordings and group legends
        dd_recs = uistate.dict_rec_show
        dd_groups = uistate.dict_group_show
        axids = ["ax1", "ax2"]
        legend_loc = ["upper right", "lower right"]
        for axid, loc in zip(axids, legend_loc):
            recs_on_axis = {key: value for key, value in dd_recs.items() if value["axis"] == axid and not key.endswith(" marker")}
            axis_legend = {key: value["line"] for key, value in recs_on_axis.items()}
            if axid in ["ax1", "ax2"]:
                groups_on_axis = {key: value for key, value in dd_groups.items() if value["axis"] == axid}
                axis_legend.update({key: value["line"] for key, value in groups_on_axis.items()})
            axis = getattr(uistate, axid)
            axis.legend(axis_legend.values(), axis_legend.keys(), loc=loc)

        for axid in ["axm", "axe"]:
            axis = getattr(uistate, axid)
            if axis.get_legend():
                axis.get_legend().remove()

        print(f" - - graphRefresh: legends: {round((time.time() - t0) * 1000)} ms")
        t1 = time.time()

        # arrange axes and labels
        axm, axe, ax1, ax2 = (
            self.uistate.axm,
            self.uistate.axe,
            self.uistate.ax1,
            self.uistate.ax2,
        )

        axm.axis("off")

        axe.set_xlim(uistate.zoom["event_xlim"])
        axe.set_ylim(uistate.zoom["event_ylim"])
        axe.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 1e3:.1f}"))
        axe.set_ylabel("Voltage (mV)")
        axe.xaxis.set_major_formatter(FuncFormatter(lambda t, _: f"{t * 1e3:.1f}"))
        axe.set_xlabel("Time (ms)")

        if uistate.checkBox["norm_EPSP"]:
            ax1.set_ylabel("Amplitude %")
            ax2.set_ylabel("Slope %")
        else:
            ax1.set_ylabel("Amplitude (mV)")
            ax2.set_ylabel("Slope (mV/ms)")
        ax1.set_ylim(uistate.zoom["output_ax1_ylim"])
        ax2.set_ylim(uistate.zoom["output_ax2_ylim"])
        ax1.set_xlim(uistate.zoom["output_xlim"])
        ax1.set_xlabel(uistate.x_axis_xlabel())
        ax1.xaxis.set_major_locator(uistate.x_axis_locator())
        ax1.xaxis.set_major_formatter(uistate.x_axis_formatter())
        print(f"output_xlim: {uistate.zoom['output_xlim']}")
        ax1.figure.subplots_adjust(bottom=0.2)
        self.oneAxisLeft()
        print(f" - - graphRefresh: axis setup: {round((time.time() - t1) * 1000)} ms")
        t1 = time.time()

        # maintain drag selections through reselection
        if uistate.x_select["mean_start"] is not None:
            self.xSelect(canvas=axm.figure.canvas, draw=False)
        if uistate.x_select["output_start"] is not None:
            if uistate.checkBox["EPSP_slope"]:
                self.xSelect(canvas=ax2.figure.canvas, draw=False)
            else:
                self.xSelect(canvas=ax1.figure.canvas, draw=False)

        # 0-hline for Events
        if not "Events y zero marker" in self.uistate.dict_rec_labels:
            hline0 = self.uistate.axe.axhline(0, linestyle="dotted", alpha=0.3)
            self.uistate.dict_rec_labels["Events y zero marker"] = {
                "rec_ID": None,
                "stim": None,
                "variant": None,
                "line": hline0,
                "axis": "axe",
            }
        uistate.dict_rec_labels["Events y zero marker"]["line"].set_visible(True)

        # 100-hline for relative Output
        if uistate.checkBox["norm_EPSP"]:
            if not "Output y 100% marker" in self.uistate.dict_rec_labels:
                hline100ax1 = self.uistate.ax1.axhline(
                    100,
                    linestyle="dotted",
                    alpha=0.3,
                    color=uistate.settings["rgb_EPSP_amp"],
                )
                hline100ax2 = self.uistate.ax2.axhline(
                    100,
                    linestyle="dotted",
                    alpha=0.3,
                    color=uistate.settings["rgb_EPSP_slope"],
                )
                self.uistate.dict_rec_labels["output amp 100% marker"] = {
                    "rec_ID": None,
                    "stim": None,
                    "variant": None,
                    "line": hline100ax1,
                    "axis": "ax1",
                }
                self.uistate.dict_rec_labels["output slope 100% marker"] = {
                    "rec_ID": None,
                    "stim": None,
                    "variant": None,
                    "line": hline100ax2,
                    "axis": "ax2",
                }
            uistate.dict_rec_labels["output amp 100% marker"]["line"].set_visible(uistate.ampView())
            uistate.dict_rec_labels["output slope 100% marker"]["line"].set_visible(uistate.slopeView())
        print(f" - - graphRefresh: markers/hlines: {round((time.time() - t1) * 1000)} ms")
        t1 = time.time()

        # update mean of selected sweeps on axe
        self.update_axe_mean(draw=False)
        print(f" - - graphRefresh: update_axe_mean: {round((time.time() - t1) * 1000)} ms")
        t1 = time.time()

        # redraw
        axm.figure.canvas.draw()
        print(f" - - graphRefresh: draw axm: {round((time.time() - t1) * 1000)} ms")
        t1 = time.time()
        axe.figure.canvas.draw()
        print(f" - - graphRefresh: draw axe: {round((time.time() - t1) * 1000)} ms")
        t1 = time.time()
        ax1.figure.canvas.draw()  # ax2 should be on the same canvas
        print(f" - - graphRefresh: draw ax1/ax2: {round((time.time() - t1) * 1000)} ms")
        print(f" - - graphRefresh total: {round((time.time() - t0) * 1000)} ms")

    def oneAxisLeft(self):
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        uistate = self.uistate
        # sets ax1 and ax2 visibility and position
        ax1.set_visible(True)
        ax2.set_visible(True)
        ax1.xaxis.set_visible(True)
        ax2.xaxis.set_visible(False)

        amp_view = uistate.ampView()
        slope_view = uistate.slopeView()

        if not amp_view and not slope_view:
            # Fallback for no slope/amp view
            ax1.yaxis.set_visible(False)
            ax2.yaxis.set_visible(False)
        else:
            ax1.yaxis.set_visible(amp_view)
            ax2.yaxis.set_visible(slope_view)

        # print(f"oneAxisLeft - uistate.ampView: {amp_view}, uistate.slopeView: {slope_view}, uistate.slopeOnly: {uistate.slopeOnly()}")
        if uistate.slopeOnly():
            ax2.yaxis.set_label_position("left")
            ax2.yaxis.set_ticks_position("left")
        else:
            ax2.yaxis.set_label_position("right")
            ax2.yaxis.set_ticks_position("right")

    def get_axis(self, axisname):  # returns the axis object by name (using only object references failed in some cases)
        axis_dict = {
            "axm": self.uistate.axm,
            "axe": self.uistate.axe,
            "ax1": self.uistate.ax1,
            "ax2": self.uistate.ax2,
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
    ):
        zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.settings["alpha_line"]
        (line,) = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder)
        line.set_visible(False)
        self.uistate.dict_rec_labels[label] = {
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
        alpha = self.uistate.settings.get("alpha_shade", 0.3)
        fill = self.get_axis(axid).fill_between(x, y_mean - sem, y_mean + sem, alpha=alpha, color=color, zorder=0)
        fill.set_visible(False)
        self.uistate.dict_rec_labels[label] = {
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
        self.uistate.dict_rec_labels[label] = {
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
            alpha=self.uistate.settings["alpha_line"],
            zorder=0,
        )
        (yline,) = self.get_axis(axid).plot(
            [x, x],
            amp_y,
            color=color,
            label=f"{label} y",
            alpha=self.uistate.settings["alpha_line"],
            zorder=0,
        )
        xline.set_visible(False)
        yline.set_visible(False)
        self.uistate.dict_rec_labels[f"{label} x marker"] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": xline,
            "axis": axid,
            "is_zero_width": is_zero_width,
            "x_mode": x_mode,
        }
        self.uistate.dict_rec_labels[f"{label} y marker"] = {
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
            alpha=self.uistate.settings["alpha_mark"],
            label=label,
            linewidth=linewidth,
            zorder=0,
        )
        vline.set_visible(False)
        self.uistate.dict_rec_labels[label] = {
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
        hline = self.get_axis(axid).axhline(
            y=y,
            color=color,
            alpha=self.uistate.settings["alpha_mark"],
            label=label,
            linewidth=linewidth,
            zorder=0,
        )
        hline.set_visible(False)
        self.uistate.dict_rec_labels[label] = {
            "rec_ID": rec_ID,
            "aspect": aspect,
            "variant": variant,
            "stim": stim,
            "line": hline,
            "axis": axid,
            "x_mode": x_mode,
        }

    def plot_group_lines(self, axid, group_ID, dict_group, df_groupmean):
        group_name = dict_group["group_name"]
        color = dict_group["color"]
        axis = self.get_axis(axid)
        if axid == "ax1":
            aspect = "EPSP_amp"
            str_aspect = "EPSP amp"
        else:
            aspect = "EPSP_slope"
            str_aspect = "EPSP slope"
        x = df_groupmean.sweep
        label_mean = f"{group_name} {str_aspect} mean"
        label_norm = f"{group_name} {str_aspect} norm"
        y_mean = df_groupmean[f"{aspect}_mean"]
        y_mean_SEM = df_groupmean[f"{aspect}_SEM"]
        y_norm = df_groupmean[f"{aspect}_norm_mean"]
        y_norm_SEM = df_groupmean[f"{aspect}_norm_SEM"]

        print(f"y_mean: {y_mean}")
        print(f"y_mean_SEM: {y_mean_SEM}")
        print(f"y_mean - y_mean_SEM: {y_mean - y_mean_SEM}")
        print(f"y_mean + y_mean_SEM: {y_mean + y_mean_SEM}")

        (meanline,) = axis.plot(
            x,
            y_mean,
            color=color,
            label=label_mean,
            alpha=self.uistate.settings["alpha_line"],
            zorder=0,
        )
        (normline,) = axis.plot(
            x,
            y_norm,
            color=color,
            label=label_norm,
            alpha=self.uistate.settings["alpha_line"],
            zorder=0,
        )
        meanfill = axis.fill_between(x, y_mean - y_mean_SEM, y_mean + y_mean_SEM, alpha=0.3, color=color)
        normfill = axis.fill_between(x, y_norm - y_norm_SEM, y_norm + y_norm_SEM, alpha=0.3, color=color)
        meanline.set_visible(False)
        normline.set_visible(False)
        meanfill.set_visible(False)
        normfill.set_visible(False)
        self.uistate.dict_group_labels[label_mean] = {
            "group_ID": group_ID,
            "stim": None,
            "aspect": aspect,
            "variant": "raw",
            "axis": axid,
            "line": meanline,
            "fill": meanfill,
            "x_mode": "sweep",
        }
        self.uistate.dict_group_labels[label_norm] = {
            "group_ID": group_ID,
            "stim": None,
            "aspect": aspect,
            "variant": "norm",
            "axis": axid,
            "line": normline,
            "fill": normfill,
            "x_mode": "sweep",
        }

    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)
        if rec_filter != "voltage":
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name

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

        settings = self.uistate.settings  # Event window, color, and alpha settings
        variables = [
            "t_EPSP_amp",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_volley_amp",
            "t_volley_slope_start",
            "t_volley_slope_end",
        ]

        # Process detected stims
        for i_stim, t_row in dft.iterrows():
            color = dict_gradient[i_stim]
            stim_num = i_stim + 1  # 1-numbering (visible to user)
            stim_str = f"- stim {stim_num}"
            t_stim = t_row["t_stim"]
            out = dfoutput[dfoutput["stim"] == stim_num]  # TODO: enable switch to dfdiff?
            _t_idx = (dfmean["time"] - t_stim).abs().idxmin()
            y_position = dfmean.loc[_t_idx, rec_filter]  # nearest-time lookup (float-safe)
            # amp_zero_plot: mean of rec_filter in the 2 ms before t_stim on dfmean.
            # Used for visual positioning on axe; matches the plotted local baseline.

            _pre_stim = dfmean[(dfmean["time"] >= t_stim - 0.002) & (dfmean["time"] < t_stim - 0.001)]
            amp_zero_plot = _pre_stim[rec_filter].mean() if not _pre_stim.empty else dfmean.loc[_t_idx, rec_filter]
            for var in variables:  # Convert all variables except t_stim to stim-specific time
                t_row[var] -= t_stim

            # add markers to Mean
            self.plot_marker(f"mean {label} {stim_str} marker", "axm", t_stim, 0, color, rec_ID)
            self.plot_vline(
                f"mean {label} {stim_str} selection marker",
                "axm",
                t_stim,
                color,
                rec_ID,
                stim=stim_num,
            )
            # add to Events
            window_start = t_stim + settings["event_start"]
            window_end = t_stim + settings["event_end"]

            df_event = dfmean[(dfmean["time"] >= window_start) & (dfmean["time"] <= window_end)].copy()
            df_event["time"] = df_event["time"] - t_stim  # shift event so that t_stim is at time 0
            self.plot_line(
                f"{label} {stim_str}",
                "axe",
                df_event["time"],
                df_event[rec_filter],
                color,
                rec_ID,
                stim=stim_num,
            )

            # plot markers on axe, output lines on ax1 and ax2
            out = dfoutput[dfoutput["stim"] == stim_num]  # TODO: enable switch to dfdiff?

            if not np.isnan(t_row["t_EPSP_amp"]):
                x_position = t_row["t_EPSP_amp"]
                y_position = df_event.loc[(df_event["time"] - x_position).abs().idxmin(), rec_filter] if not df_event.empty else 0
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
                amp_y = (
                    amp_zero_plot,
                    amp_zero_plot - (out["EPSP_amp"].mean() / 1000),
                )  # mV to V
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
                    [-0.002, -0.001],
                    [amp_zero_plot, amp_zero_plot],
                    settings["rgb_EPSP_amp"],
                    rec_ID,
                    aspect="EPSP_amp",
                    stim=stim_num,
                )  # TODO: hardcoded x

            x_start, x_end = t_row["t_EPSP_slope_start"], t_row["t_EPSP_slope_end"]
            if not (np.isnan(x_start) or np.isnan(x_end)):
                index = (df_event["time"] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event["time"] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(
                    f"{label} {stim_str} EPSP slope marker",
                    "axe",
                    [x_start, x_end],
                    [y_start, y_end],
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
                y_position = df_event.loc[(df_event["time"] - x_position).abs().idxmin(), rec_filter] if not df_event.empty else 0
                color = settings["rgb_volley_amp"]
                self.plot_marker(
                    f"{label} {stim_str} volley amp marker",
                    "axe",
                    t_row["t_volley_amp"],
                    y_position,
                    settings["rgb_volley_amp"],
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                )
                volley_amp_mean = t_row.get("volley_amp_mean")
                if volley_amp_mean is None:
                    volley_amp_mean = out["volley_amp"].mean()
                amp_x = (
                    x_position - t_row["t_volley_amp_halfwidth"],
                    x_position + t_row["t_volley_amp_halfwidth"],
                )
                amp_y = amp_zero_plot, amp_zero_plot - volley_amp_mean / 1000  # mV to V
                self.plot_amp_width(
                    f"{label} {stim_str} volley amp",
                    "axe",
                    x_position,
                    amp_x,
                    amp_y,
                    color,
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                )
                volley_amp_mean = t_row.get("volley_amp_mean")
                if volley_amp_mean is None:
                    volley_amp_mean = out["volley_amp"].mean()
                self.plot_hline(
                    f"{label} {stim_str} volley amp mean",
                    "ax1",
                    volley_amp_mean,
                    settings["rgb_volley_amp"],
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
                    settings["rgb_volley_amp"],
                    rec_ID,
                    aspect="volley_amp",
                    stim=stim_num,
                    x_mode="sweep",
                )

            x_start, x_end = t_row["t_volley_slope_start"], t_row["t_volley_slope_end"]
            if not (np.isnan(x_start) or np.isnan(x_end)):
                index = (df_event["time"] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event["time"] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(
                    f"{label} {stim_str} volley slope marker",
                    "axe",
                    [x_start, x_end],
                    [y_start, y_end],
                    settings["rgb_volley_slope"],
                    rec_ID,
                    aspect="volley_slope",
                    stim=stim_num,
                    width=5,
                )
                volley_slope_mean = t_row.get("volley_slope_mean")
                if volley_slope_mean is None:
                    volley_slope_mean = out["volley_slope"].mean()
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

        # Stim-mode aggregate lines (always created when stim-mode rows exist;
        # visibility controlled by x_mode filtering in _is_rec_visible).
        out_stim = dfoutput[dfoutput["sweep"].isna()]
        if not out_stim.empty:
            df_sweeps = dfoutput[dfoutput["sweep"].notna()]
            df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)

            configs = [
                ("EPSP amp", "ax1", "EPSP_amp", settings["rgb_EPSP_amp"], "raw"),
                ("EPSP amp norm", "ax1", "EPSP_amp_norm", settings["rgb_EPSP_amp"], "norm"),
                ("EPSP slope", "ax2", "EPSP_slope", settings["rgb_EPSP_slope"], "raw"),
                ("EPSP slope norm", "ax2", "EPSP_slope_norm", settings["rgb_EPSP_slope"], "norm"),
                ("volley amp", "ax1", "volley_amp", settings["rgb_volley_amp"], "raw"),
                ("volley slope", "ax2", "volley_slope", settings["rgb_volley_slope"], "raw"),
            ]

            stims = out_stim["stim"].values

            for suffix, axid, col, color, variant in configs:
                if col in out_stim.columns:
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
                    if col in df_sem.columns:
                        sem_vals = df_sem[col].reindex(out_stim["stim"]).values
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

    def addGroup(self, group_ID, dict_group, df_groupmean):
        # plot group meanlines and SEMs
        if df_groupmean["EPSP_amp_mean"].notna().any():
            self.plot_group_lines("ax1", group_ID, dict_group, df_groupmean)
        if df_groupmean["EPSP_slope_mean"].notna().any():
            self.plot_group_lines("ax2", group_ID, dict_group, df_groupmean)

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
        Updates the existing plotted artists stored in `self.uistate.dict_rec_labels`.
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
        norm = self.uistate.checkBox["norm_EPSP"]
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
            if aspect == "volley slope":
                volley_slope_mean = trow.get("volley_slope_mean")
                print(f" - - - volley_slope_mean: {volley_slope_mean}")
                # if volley_slope_mean is None:
                #    volley_slope_mean = self.uistate.mouseover_out[0].get_ydata().mean()
                self.updateOutMean(f"{label_core} mean", volley_slope_mean)
            else:  # EPSP slope
                if norm:
                    label_core += " norm"
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
            if aspect == "volley amp":
                volley_amp_mean = trow.get("volley_amp_mean")
                print(f" - - - volley_amp_mean: {volley_amp_mean}")
                if dfoutput is not None:
                    stim_num = trow["stim"]
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, key)
                else:
                    self.updateOutLine(label_core)
                self.updateOutMean(f"{label_core} mean", volley_amp_mean)
            else:  # EPSP amp
                if norm:
                    label_core += " norm"
                if dfoutput is not None:
                    stim_num = trow["stim"]
                    col = f"{key}_norm" if norm else key
                    self.updateOutLineFromDf(label_core, dfoutput, stim_num, col)
                else:
                    self.updateOutLine(label_core)

    def updateAmpMarker(self, labelbase, x, y, amp_x, amp_zero, amp=None, draw=False):
        axe = self.uistate.axe
        print(f"updateAmpMarker called with labelbase: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        x = np.atleast_1d(x)
        y = np.atleast_1d(y)
        print(f"updateAmpMarker: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        self.uistate.dict_rec_labels[f"{labelbase} marker"]["line"].set_data(x, y)
        if amp is not None:
            is_zero_width = amp_x[0] == amp_x[1]
            amp_y = amp_zero, (0 - amp) + amp_zero
            self.uistate.dict_rec_labels[f"{labelbase} x marker"]["line"].set_data(amp_x, [amp_y[1], amp_y[1]])
            self.uistate.dict_rec_labels[f"{labelbase} y marker"]["line"].set_data([x[0], x[0]], amp_y)
            self.uistate.dict_rec_labels[f"{labelbase} x marker"]["is_zero_width"] = is_zero_width
            self.uistate.dict_rec_labels[f"{labelbase} y marker"]["is_zero_width"] = False
        if draw:
            axe.figure.canvas.draw()

    def updateLine(self, plot_to_update, x_data, y_data, draw=False):
        axe = self.uistate.axe
        dict_line = self.uistate.dict_rec_labels[plot_to_update]
        dict_line["line"].set_data(x_data, y_data)
        if draw:
            axe.figure.canvas.draw()

    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutLine: mouseover_out is None, skipping update for '{label}'")
            return
        linedict = self.uistate.dict_rec_labels[label]
        linedict["line"].set_xdata(mouseover_out[0].get_xdata())
        linedict["line"].set_ydata(mouseover_out[0].get_ydata())

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
        out_stim = dfoutput[dfoutput["sweep"].isna()]
        if out_stim.empty:
            return

        suffix_to_col = {
            "EPSP amp": "EPSP_amp",
            "EPSP amp norm": "EPSP_amp_norm",
            "EPSP slope": "EPSP_slope",
            "EPSP slope norm": "EPSP_slope_norm",
            "volley amp": "volley_amp",
            "volley slope": "volley_slope",
        }

        df_sweeps = dfoutput[dfoutput["sweep"].notna()]
        df_sem = df_sweeps.groupby("stim").sem(numeric_only=True)

        for suffix, col in suffix_to_col.items():
            label = f"{rec_name} {suffix}"
            if label not in self.uistate.dict_rec_labels:
                continue
            if col not in out_stim.columns:
                continue
            linedict = self.uistate.dict_rec_labels[label]
            linedict["line"].set_xdata(out_stim["stim"].values)
            linedict["line"].set_ydata(out_stim[col].values)
            print(f"updateStimLines: refreshed '{label}'")

            shade_label = f"{label} shade"
            if shade_label in self.uistate.dict_rec_labels and col in df_sem.columns:
                old_shade_dict = self.uistate.dict_rec_labels[shade_label]
                try:
                    old_shade_dict["line"].remove()
                except Exception:
                    pass

                axid = old_shade_dict["axis"]
                rec_ID = old_shade_dict["rec_ID"]
                aspect = old_shade_dict["aspect"]
                variant = old_shade_dict["variant"]
                color_setting_key = f"rgb_{aspect}"
                color = self.uistate.settings.get(color_setting_key, "black")

                self.plot_shade(
                    shade_label,
                    axid,
                    out_stim["stim"].values,
                    out_stim[col].values,
                    df_sem[col].reindex(out_stim["stim"]).values,
                    color,
                    rec_ID,
                    aspect=aspect,
                    variant=variant,
                    x_mode="stim",
                )

                self.uistate.dict_rec_labels[shade_label]["line"].set_visible(linedict["line"].get_visible())

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
        linedict = self.uistate.dict_rec_labels[label]
        x_col = linedict.get("x_mode", "sweep")
        if x_col not in df_stim.columns:
            x_col = "sweep"
        linedict["line"].set_xdata(df_stim[x_col].values)
        linedict["line"].set_ydata(df_stim[column].values)

    def updateOutMean(self, label, mean):
        print(f"updateOutMean: {label}, {mean}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutMean: mouseover_out is None, skipping update for '{label}'")
            return
        linedict = self.uistate.dict_rec_labels[label]
        linedict["line"].set_xdata(mouseover_out[0].get_xdata())
        linedict["line"].set_ydata([mean] * len(linedict["line"].get_xdata()))
        # linedict['line'].set_ydata(mean)

    #####################################################################
    #     #DEPRECATED FUNCTIONS - TO BE REMOVED IN FUTURE RELEASES      #
    #####################################################################

    def updateEPSPout(self, rec_name, out):  # TODO: update this last remaining ax-cycle to use the dict
        # OBSOLETE - called by norm, does not operate on stim-specific data!
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        for line in ax1.get_lines():
            if line.get_label() == f"{rec_name} EPSP amp":
                line.set_ydata(out["EPSP_amp"])
            if line.get_label() == f"{rec_name} EPSP amp norm":
                line.set_ydata(out["EPSP_amp_norm"])
                ax1.figure.canvas.draw()
        for line in ax2.get_lines():
            if line.get_label() == f"{rec_name} EPSP slope":
                line.set_ydata(out["EPSP_slope"])
            if line.get_label() == f"{rec_name} EPSP slope norm":
                line.set_ydata(out["EPSP_slope_norm"])
                ax2.figure.canvas.draw()
