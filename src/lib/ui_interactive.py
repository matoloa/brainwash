import logging

import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtGui, QtWidgets

from lib import analysis_v3 as analysis
from lib import ui_plot

logger = logging.getLogger(__name__)

uistate = None
config = None
uiplot = None


class InteractivePlotMixin:
    #####################################################
    #          Mouseover, click and drag events         #
    #####################################################

    def graphClicked(self, event, canvas):  # graph click event
        if not uistate.list_idx_select_recs:  # no recording selected; do nothing
            return
        x = event.xdata
        if x is None:  # clicked outside graph; do nothing
            return
        self.usage("graphClicked")
        if event.button == 2:  # middle click, reset zoom
            # print(f"axis: {axis}, type {type(axis)}")
            self.zoomAuto()
            return
        if event.button == 3:  # right click, deselect
            if uistate.dragging:
                return
            self.mouse_drag = None
            self.mouse_release = None
            uistate.x_drag = None
            if canvas == self.canvasMean:
                uiplot.xDeselect(ax=uistate.axm, reset=True)
                self.lineEdit_mean_selection_start.setText("")
                self.lineEdit_mean_selection_end.setText("")
            else:
                uiplot.xDeselect(ax=uistate.ax1, reset=True)
                self.lineEdit_sweeps_range_from.setText("")
                self.lineEdit_sweeps_range_to.setText("")
            self.update_stim_buttons()
            return

        # left clicked on a graph
        uistate.dragging = True
        prow = self.get_prow()
        if prow is None:
            uistate.dragging = False
            return

        if (
            (canvas == self.canvasEvent) and (len(uistate.list_idx_select_recs) == 1) and (len(uistate.list_idx_select_stims) == 1)
        ):  # Event canvas left-clicked with just one rec and stim selected, middle graph: editing detected events
            uistate.dft_temp = self.get_dft(prow).copy()
            trow = uistate.dft_temp.loc[uistate.list_idx_select_stims[0]]
            rec_filter = prow["filter"]
            rec_name = prow["recording_name"]
            if rec_filter != "voltage":
                label_core = f"{rec_name} ({rec_filter})"
            else:
                label_core = rec_name
            label = f"{label_core} - stim {trow['stim']}"
            dict_event = uistate.dict_rec_labels[label]
            data_x = dict_event["line"].get_xdata()
            data_y = dict_event["line"].get_ydata()
            uistate.x_on_click = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
            # print(f"uistate.x_on_click: {uistate.x_on_click}")
            if event.inaxes is not None:
                if (event.button == 1 or event.button == 3) and (uistate.mouseover_action is not None):
                    action = uistate.mouseover_action
                    # print(f"mouseover action: {action}")
                    if action.startswith("EPSP slope"):
                        start, end = (
                            trow["t_EPSP_slope_start"] - trow["t_stim"],
                            trow["t_EPSP_slope_end"] - trow["t_stim"],
                        )
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragSlope(event, action, data_x, data_y, start, end),
                        )
                    elif action == "EPSP amp move":
                        start = trow["t_EPSP_amp"] - trow["t_stim"]
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragPoint(event, data_x, data_y, start),
                        )
                    elif action.startswith("volley slope"):
                        start, end = (
                            trow["t_volley_slope_start"] - trow["t_stim"],
                            trow["t_volley_slope_end"] - trow["t_stim"],
                        )
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragSlope(event, action, data_x, data_y, start, end),
                        )
                    elif action == "volley amp move":
                        start = trow["t_volley_amp"] - trow["t_stim"]
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragPoint(event, data_x, data_y, start),
                        )
                    self.mouse_release = self.canvasEvent.mpl_connect(
                        "button_release_event",
                        lambda event: self.eventDragReleased(event, data_x, data_y),
                    )

        elif canvas == self.canvasMean:  # Mean canvas (top graph) left-clicked: overview and selecting ranges for finding relevant stims
            if uistate.mean_mouseover_stim_select is not None:
                uistate.dragging = False
                self.stimSelectionChanged()
                return
            dfmean = self.get_dfmean(prow)  # Required for event dragging, x and y
            time_values = dfmean["time"].values
            uistate.x_on_click = time_values[np.abs(time_values - x).argmin()]
            uistate.x_select["mean_start"] = uistate.x_on_click
            self.lineEdit_mean_selection_start.setText(f"{uistate.x_select['mean_start'] * 1000:g}")
            self.update_stim_buttons()
            self.connectDragRelease(x_range=time_values, rec_ID=prow["ID"], graph="mean")
        elif canvas == self.canvasOutput:  # Output canvas (bottom graph) left-clicked: click and drag to select specific sweeps
            if getattr(uistate, "experiment_type", "time") == "io":
                uistate.dragging = False
                return
            sweep_numbers = list(range(0, int(prow["sweeps"])))
            uistate.x_on_click = sweep_numbers[np.abs(sweep_numbers - x).argmin()]
            uistate.x_select["output_start"] = uistate.x_on_click
            self.lineEdit_sweeps_range_from.setText(str(uistate.x_on_click))
            self.connectDragRelease(x_range=sweep_numbers, rec_ID=prow["ID"], graph="output")

    # pyqtSlot decorators
    @QtCore.pyqtSlot()
    def meanMouseover(self, event):  # determine which event is being mouseovered
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        uistate.mean_mouseover_stim_select = None  # Always clear on movement initially
        dft = uistate.df_rec_select_time
        if dft is None or dft.empty:
            # print("No single recording selected with timepoints to mouseover.")
            return
        n_stims = len(dft)
        if n_stims < 1:
            # print("Not enough stims to mouseover.")
            return
        # One recording selected, with 2 or more stims, define mouseover zones
        prow = self.get_prow()
        if prow is None:
            return
        rec_name = f"{prow['recording_name']}"
        rec_filter = prow["filter"]  # the filter currently used for this recording
        if rec_filter != "voltage":
            label_core = f"{rec_name} ({rec_filter})"
        else:
            label_core = rec_name

        axm = uistate.axm
        uistate.mean_mouseover_stim_select = None  # name of stim that will be selected if clicked
        uistate.mean_stim_x_ranges = {}  # dict: stim_num: (x_start, x_end)
        # Margins are set pixel-based by _recalc_axm_detection_zones; recompute
        # here only as a fallback when they have not been initialised yet.
        if uistate.mean_x_margin is None or uistate.mean_y_margin is None:
            uistate.setMarginsAxm(axm=axm, pixels=ui_plot.STIM_MARKER_SIZE // 2 + 5)
        y_range = (
            -uistate.mean_y_margin,
            uistate.mean_y_margin,
        )  # stim markers should be at y~0

        # build detection zones for each stim
        for row in dft.itertuples(index=False):
            stim = row.stim
            t_stim = row.t_stim
            x_range = t_stim - uistate.mean_x_margin, t_stim + uistate.mean_x_margin
            uistate.mean_stim_x_ranges[stim] = x_range
        # check if mouse is within any of the stim zones
        for stim, x_range in uistate.mean_stim_x_ranges.items():
            if x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]:
                uistate.mean_mouseover_stim_select = stim
                # print(f"meanMouseover of {uistate.mean_mouseover_stim_select}: x={x}, y={y}")
                # find corresponding selection marker:
                stim_str = f"- stim {stim}"
                label = f"mean {label_core} {stim_str} marker"
                stim_marker = uistate.dict_rec_labels.get(label)
                # print(f"{label}: {stim_marker}")
                # zorder mouseovered marker to top, alpha 1
                if stim_marker is not None:
                    stim_marker_line = stim_marker.get("line")
                    stim_marker_line.set_zorder(10)
                    stim_marker_line.set_alpha(1.0)
                break
            else:
                # reset all stim markers to default zorder and alpha
                stim_str = f"- stim {stim}"
                label = f"mean {label_core} {stim_str} marker"
                stim_marker = uistate.dict_rec_labels.get(label)
                if stim_marker is not None:
                    stim_marker_line = stim_marker.get("line")
                    stim_marker_line.set_zorder(0)
                    stim_marker_line.set_alpha(0.4)

        axm.figure.canvas.draw()

    def eventMouseover(self, event):  # determine which event is being mouseovered
        if uistate.df_rec_select_data is None:  # no single recording/stim combo selected
            return
        axe = uistate.axe

        def plotMouseover(action, axe):
            alpha = 0.8
            linewidth = 3 if "resize" in action else 10
            if "slope" in action:
                if "EPSP" in action:
                    x_range = (
                        uistate.EPSP_slope_start_xy[0],
                        uistate.EPSP_slope_end_xy[0],
                    )
                    y_range = (
                        uistate.EPSP_slope_start_xy[1],
                        uistate.EPSP_slope_end_xy[1],
                    )
                    color = uistate.settings["rgb_EPSP_slope"]
                elif "volley" in action:
                    x_range = (
                        uistate.volley_slope_start_xy[0],
                        uistate.volley_slope_end_xy[0],
                    )
                    y_range = (
                        uistate.volley_slope_start_xy[1],
                        uistate.volley_slope_end_xy[1],
                    )
                    color = uistate.settings["rgb_volley_slope"]

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(x_range[1], y_range[1], color=color, s=100, alpha=alpha)
                else:
                    uistate.mouseover_blob.set_offsets([x_range[1], y_range[1]])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)

                if uistate.mouseover_plot is None:
                    uistate.mouseover_plot = axe.plot(
                        x_range,
                        y_range,
                        color=color,
                        linewidth=linewidth,
                        alpha=alpha,
                        label="mouseover",
                    )
                else:
                    uistate.mouseover_plot[0].set_data(x_range, y_range)
                    uistate.mouseover_plot[0].set_linewidth(linewidth)
                    uistate.mouseover_plot[0].set_alpha(alpha)
                    uistate.mouseover_plot[0].set_color(color)

            elif "amp" in action:
                if "EPSP" in action:
                    x, y = uistate.EPSP_amp_xy
                    color = uistate.settings["rgb_EPSP_amp"]
                elif "volley" in action:
                    x, y = uistate.volley_amp_xy
                    color = uistate.settings["rgb_volley_amp"]

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(x, y, color=color, s=100, alpha=alpha)
                else:
                    uistate.mouseover_blob.set_offsets([x, y])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)

        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        if event.inaxes == axe:
            zones = {}
            if uistate.checkBox["EPSP_amp"]:
                zones["EPSP amp move"] = uistate.EPSP_amp_move_zone
            if uistate.checkBox["EPSP_slope"]:
                zones["EPSP slope resize"] = uistate.EPSP_slope_resize_zone
                zones["EPSP slope move"] = uistate.EPSP_slope_move_zone
            if uistate.checkBox["volley_amp"]:
                zones["volley amp move"] = uistate.volley_amp_move_zone
            if uistate.checkBox["volley_slope"]:
                zones["volley slope resize"] = uistate.volley_slope_resize_zone
                zones["volley slope move"] = uistate.volley_slope_move_zone
            uistate.mouseover_action = None
            for action, zone in zones.items():
                if not zone:
                    continue
                if zone["x"][0] <= x <= zone["x"][1] and zone["y"][0] <= y <= zone["y"][1]:
                    uistate.mouseover_action = action
                    plotMouseover(action, axe)

                    # Debugging block
                    if False:
                        prow = self.get_prow()
                        rec_name = prow["recording_name"]
                        rec_ID = prow["ID"]
                        trow = self.get_trow()
                        # new_dict = {key: value for key, value in uistate.dict_rec_labels.items() if value.get('stim') == stim_num and value.get('rec_ID') == rec_ID and value.get('axis') == 'ax2'}
                        # EPSP_slope = new_dict.get(f"{rec_name} - stim {stim_num} EPSP slope")
                        EPSP_slope = uistate.dict_rec_labels.get(f"{rec_name} - stim {trow['stim']} EPSP slope")
                        line = EPSP_slope.get("line")
                        line.set_linewidth(10)
                        print(f"{EPSP_slope} - {action}")
                    break

            if uistate.mouseover_action is None:
                if uistate.mouseover_blob is not None:
                    uistate.mouseover_blob.set_sizes([0])
                if uistate.mouseover_plot is not None:
                    uistate.mouseover_plot[0].set_linewidth(0)

            axe.figure.canvas.draw()

    @staticmethod
    def _get_nearest_point(x, y, x_array, y_array, x_range, y_range):
        dx = (x_array - x) / x_range
        dy = (y_array - y) / y_range
        distances = dx**2 + dy**2
        if np.all(np.isnan(distances)):
            return None
        return int(np.nanargmin(distances))

    def _draw_ghost_sweep(self, snippet_x, snippet_y, label_text):
        if uistate.ghost_sweep is None:
            ghost_color = "white" if uistate.darkmode else "black"
            (uistate.ghost_sweep,) = uistate.axe.plot(snippet_x, snippet_y, color=ghost_color, alpha=0.5, zorder=0)
            if uistate.ghost_label is None:
                uistate.ghost_label = uistate.axe.text(
                    1,
                    1,
                    label_text,
                    transform=uistate.axe.transAxes,
                    ha="left",
                    va="bottom",
                )
            else:
                uistate.ghost_label.set_text(label_text)
        else:
            uistate.ghost_sweep.set_data(snippet_x, snippet_y)
            uistate.ghost_label.set_text(label_text)

    def _draw_mouseover_blob(self, ax, x, y, color):
        if getattr(uistate, "mouseover_out_blob", None) is None:
            uistate.mouseover_out_blob = ax.scatter(x, y, color=color, s=150, alpha=0.8, zorder=10)
        else:
            if uistate.mouseover_out_blob.axes != ax:
                uistate.mouseover_out_blob.remove()
                uistate.mouseover_out_blob = ax.scatter(x, y, color=color, s=150, alpha=0.8, zorder=10)
            else:
                uistate.mouseover_out_blob.set_offsets([[x, y]])
                uistate.mouseover_out_blob.set_color(color)

    def outputMouseover(self, event):  # determine which event is being mouseovered
        experiment_type = getattr(uistate, "experiment_type", "time")
        is_io = experiment_type == "io"
        is_pp = experiment_type == "PP"
        if is_io:
            str_ax = "ax1"
        else:
            str_ax = "ax2" if uistate.slopeView() else "ax1" if uistate.ampView() else None

        ax = getattr(uistate, str_ax) if str_ax else None

        if event.inaxes not in (uistate.ax1, uistate.ax2) or str_ax is None:
            if uistate.ghost_sweep is not None:
                self.exorcise()
            return

        # Ensure x,y are in the coordinates of the target axis (ax1 or ax2)
        # because twinx() puts ax2 on top, intercepting events with ax2's y-scale.
        if event.inaxes != ax:
            x, y = ax.transData.inverted().transform((event.x, event.y))
        else:
            x, y = event.xdata, event.ydata

        if x is None or y is None or not (uistate.slopeView() or uistate.ampView() or is_io):
            if uistate.ghost_sweep is not None:  # remove ghost sweep if outside output graph
                self.exorcise()
            return
        if len(uistate.list_idx_select_recs) != 1:
            self.exorcise()
            return
        # find a visible line
        if is_io:
            dict_out = {
                key: value
                for key, value in uistate.dict_rec_show.items()
                if value["axis"] == str_ax and value.get("x_mode") == "io" and hasattr(value["line"], "get_offsets")
            }
        else:
            dict_out = {
                key: value
                for key, value in uistate.dict_rec_show.items()
                if value["axis"] == str_ax and (value["aspect"] in ["EPSP_amp", "EPSP_slope"]) and hasattr(value["line"], "get_xdata")
            }
        if not dict_out:
            return
        # dict_out contains exactly the active line/scatter due to rec selection limits
        dict_pop = list(dict_out.values())[0]

        rec_ID = dict_pop["rec_ID"]
        df_p = self.get_df_project()
        p_row = df_p[df_p["ID"] == rec_ID].iloc[0]

        if is_io:
            dfoutput = self.get_dfdiff(row=p_row) if uistate.checkBox["paired_stims"] else self.get_dfoutput(row=p_row)
            dfoutput = self.V2mV(dfoutput)
            df_sweeps = dfoutput[dfoutput["sweep"].notna()].reset_index(drop=True)
            io_input = getattr(uistate, "io_input", "vamp")
            io_output = getattr(uistate, "io_output", "EPSPamp")
            x_col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(io_input, "volley_amp")
            y_col = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")

            if x_col not in df_sweeps.columns or y_col not in df_sweeps.columns:
                return

            df_sweeps = df_sweeps.dropna(subset=[x_col, y_col]).reset_index(drop=True)

            x_array = df_sweeps[x_col].values.astype(float)
            y_array = df_sweeps[y_col].values.astype(float)

            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            if x_range == 0:
                x_range = 1
            if y_range == 0:
                y_range = 1

            out_x_idx = self._get_nearest_point(x, y, x_array, y_array, x_range, y_range)
            if out_x_idx is None:
                return
            x_val = df_sweeps["sweep"].iloc[out_x_idx]
            out_x_val = x_array[out_x_idx]
            out_y_val = y_array[out_x_idx]
        else:
            x_data = dict_pop["line"].get_xdata()
            y_data = dict_pop["line"].get_ydata()
            if is_pp:
                xlim = ax.get_xlim()
                ylim = ax.get_ylim()
                x_range = xlim[1] - xlim[0]
                y_range = ylim[1] - ylim[0]
                if x_range == 0:
                    x_range = 1
                if y_range == 0:
                    y_range = 1
                out_x_idx = self._get_nearest_point(x, y, x_data, y_data, x_range, y_range)
                if out_x_idx is None:
                    return
            else:
                # find closest x_index
                out_x_idx = int(np.nanargmin(np.abs(x_data - x)))

            x_val = x_data[out_x_idx]
            out_x_val = x_val
            out_y_val = y_data[out_x_idx]

            if is_pp:
                dfoutput = self.get_dfdiff(row=p_row) if uistate.checkBox.get("paired_stims", False) else self.get_dfoutput(row=p_row)
                out_sweeps = dfoutput[dfoutput["sweep"].notna()]
                out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                common_sweeps = out1.index.intersection(out2.index).dropna()
                if len(common_sweeps) > 0:
                    safe_idx = min(out_x_idx, len(common_sweeps) - 1)
                    x_val = common_sweeps[safe_idx]

        # print(f"* * * outputMouseover: out_x_idx={out_x_idx}, sweeps={sweeps}")

        if out_x_idx == getattr(uistate, "last_out_x_idx", None):  # prevent update if same x
            return

        df_t = self.get_dft(p_row)
        rec_filter = p_row["filter"]
        settings = uistate.settings

        if uistate.x_axis == "stim" and not is_io:
            # Ghost waveform: show the dfmean snippet for the hovered stim.
            # out_x_idx is a positional index into x_data; recover actual stim number.
            stim_num = int(x_val)
            matching = df_t[df_t["stim"] == stim_num]
            if matching.empty:
                return
            t_row = matching.iloc[0]
            t_stim = t_row["t_stim"]

            # Slice dfmean around this stim's event window (same as addRow)
            dfmean = self.get_dfmean(row=p_row)
            window_start = t_stim + settings["event_start"]
            window_end = t_stim + settings["event_end"]
            snippet = dfmean[(dfmean["time"] >= window_start) & (dfmean["time"] <= window_end)].copy()
            snippet_x = snippet["time"] - t_stim  # shift so t_stim = 0
            snippet_y = snippet[rec_filter]
            ghost_label_text = f"stim {stim_num}"
        else:  # sweep (or time or io — same source data)
            if is_io:
                stim = df_sweeps["stim"].iloc[out_x_idx]
            else:
                stim = dict_pop.get("stim")
                if stim is None:
                    stim = 1

            t_row = df_t[df_t["stim"] == stim].iloc[0]
            offset = t_row["t_stim"]

            if pd.notna(p_row["bin_size"]):
                dfsource = self.get_dfbin(p_row)
            else:
                dfsource = self.get_dffilter(p_row)

            dfsweep = dfsource[dfsource["sweep"] == x_val]  # select only rows where sweep == x_val
            snippet_x = dfsweep["time"] - offset
            snippet_y = dfsweep[rec_filter]

            if pd.notna(p_row["bin_size"]):
                ghost_label_text = f"bin {int(x_val)}"
            else:
                ghost_label_text = f"sweep {int(x_val)}"

        aspect = dict_pop.get("aspect", "EPSP_amp")
        highlight_color = uistate.settings.get(f"rgb_{aspect}", "red")

        if is_io or is_pp:
            self._draw_mouseover_blob(ax, out_x_val, out_y_val, highlight_color)
        else:
            if getattr(uistate, "mouseover_out_blob", None) is not None:
                try:
                    uistate.mouseover_out_blob.remove()
                except ValueError:
                    pass
                uistate.mouseover_out_blob = None

        self._draw_ghost_sweep(snippet_x, snippet_y, ghost_label_text)
        uistate.axe.figure.canvas.draw()
        uistate.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw()

    def on_leave_output(self, event):
        self.exorcise()

    def exorcise(self):
        if uistate.ghost_sweep is not None:
            uistate.ghost_sweep.remove()
            uistate.ghost_sweep = None
        if uistate.ghost_label is not None:
            uistate.ghost_label.remove()
            uistate.ghost_label = None
        if getattr(uistate, "mouseover_out_blob", None) is not None:
            try:
                uistate.mouseover_out_blob.remove()
            except ValueError:
                pass
            uistate.mouseover_out_blob = None
            if getattr(uistate, "ax1", None) is not None:
                uistate.ax1.figure.canvas.draw_idle()
        if getattr(uistate, "axe", None) is not None:
            uistate.axe.figure.canvas.draw()

    def connectDragRelease(self, x_range, rec_ID, graph):
        self.usage("connectDragRelease")
        # function to set up x scales for dragging and releasing on mean- and output canvases
        if graph == "mean":  # uistate.axm
            canvas = self.canvasMean
            filtered_values = [value["line"] for value in uistate.dict_rec_labels.values() if value["rec_ID"] == rec_ID and value["axis"] == "axm"]
        elif graph == "output":  # uistate.ax1+ax2
            canvas = self.canvasOutput
            filtered_values = [
                value["line"]
                for value in uistate.dict_rec_labels.values()
                if value["rec_ID"] == rec_ID and (value["axis"] == "ax1" or value["axis"] == "ax2")
            ]
        else:
            print("connectDragRelease: Incorrect graph reference.")
            return

        filtered_values = [line for line in filtered_values if len(line.get_xdata()) > 0]
        max_x_line = max(filtered_values, key=lambda line: line.get_xdata()[-1], default=None)
        if max_x_line is None:
            print("No lines found. Cannot set up drag and release.")
            return
        x_data = max_x_line.get_xdata()
        self.mouse_drag = canvas.mpl_connect(
            "motion_notify_event",
            lambda event: self.xDrag(event, canvas=canvas, x_data=x_data, x_range=x_range),
        )
        self.mouse_release = canvas.mpl_connect(
            "button_release_event",
            lambda event: self.drag_released(event, canvas=canvas),
        )

    def xDrag(self, event, canvas, x_data, x_range):
        # self.usage("xDrag")
        if not uistate.dragging:
            return
        if event.xdata is None:
            return
        x = event.xdata  # mouse x position
        x_drag_val = x_range[np.abs(x_range - x).argmin()]
        if x_drag_val == uistate.x_drag_last:  # return if the pointer hasn't moved enough
            return
        uistate.x_drag = x_drag_val
        uistate.x_drag_last = x_drag_val
        if canvas == self.canvasMean:
            uistate.x_select["mean_end"] = uistate.x_drag
            self.lineEdit_mean_selection_end.setText(f"{uistate.x_drag * 1000:g}")
        else:
            uistate.x_select["output_end"] = uistate.x_drag
            uistate.x_select["output"] = set(
                range(
                    min(uistate.x_on_click, uistate.x_drag),
                    max(uistate.x_on_click, uistate.x_drag) + 1,
                )
            )
            # print(f"uistate.x_select['output']: {uistate.x_select['output']}")
        uiplot.xSelect(canvas=canvas)

    def drag_released(self, event, canvas):
        self.usage("drag_released")
        is_mean = canvas is self.canvasMean
        is_output = canvas is self.canvasOutput

        if uistate.x_drag is None:  # click only
            if is_mean:
                self.lineEdit_mean_selection_end.setText("")
                uistate.x_select["mean_end"] = None
                self.lineEdit_mean_selection_start.setText(f"{uistate.x_select['mean_start'] * 1000:g}")
            elif is_output:
                self.lineEdit_sweeps_range_to.setText("")
                uistate.x_select["output_end"] = None
                uistate.x_select["output"] = {uistate.x_on_click}  # ensure set type
                uiplot.update_axe_mean()
        else:  # click and drag
            start, end = sorted((uistate.x_on_click, uistate.x_drag))
            if is_mean:
                uistate.x_select["mean_start"] = start
                uistate.x_select["mean_end"] = end
                self.lineEdit_mean_selection_start.setText(f"{start * 1000:g}")
                self.lineEdit_mean_selection_end.setText(f"{end * 1000:g}")
            elif is_output:
                uistate.x_select["output_start"] = start
                uistate.x_select["output_end"] = end
                uistate.x_select["output"] = set(range(start, end + 1))
                self.lineEdit_sweeps_range_from.setText(str(start))
                self.lineEdit_sweeps_range_to.setText(str(end))
                uiplot.update_axe_mean()
        # cleanup
        canvas.mpl_disconnect(self.mouse_drag)
        canvas.mpl_disconnect(self.mouse_release)
        self.mouse_drag = None
        self.mouse_release = None
        uistate.x_drag = None
        uistate.dragging = False

        uiplot.xSelect(canvas=canvas)

    def mouseoverUpdate(self):
        self.usage("mouseoverUpdate")
        self.mouseoverDisconnect()
        # if only one item is selected, make a new mouseover event connection
        if uistate.list_idx_select_recs and uistate.list_idx_select_stims:
            self._update_marker_data()

        if len(uistate.list_idx_select_recs) != 1:
            print("(multi-rec-selection) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return
        if len(uistate.list_idx_select_stims) != 1:
            print("(multi-stim-selection) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return
        # print(f"mouseoverUpdate: {uistate.list_idx_select_recs[0]}, {type(uistate.list_idx_select_recs[0])}")
        prow = self.get_prow()
        if prow is None:
            logger.debug("mouseoverUpdate: prow is None, calling graphRefresh and returning")
            self.graphRefresh()
            return
        rec_ID = prow["ID"]
        trow = self.get_trow()
        if trow is None:
            logger.debug("mouseoverUpdate: trow is None, calling graphRefresh and returning")
            self.graphRefresh()
            return
        stim_num = trow["stim"]
        uistate.setMargins(axe=uistate.axe)
        dict_labels = {
            key: value
            for key, value in uistate.dict_rec_labels.items()
            if key.endswith(" marker") and value["rec_ID"] == rec_ID and value["axis"] == "axe" and value["stim"] == stim_num
        }

        if not dict_labels:
            print("(no labels) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return

        for label, value in dict_labels.items():
            line = value["line"]
            if label.endswith("EPSP amp marker"):
                uistate.updatePointDragZone(aspect="EPSP amp move", x=line.get_xdata()[0], y=line.get_ydata()[0])
            elif label.endswith("volley amp marker"):
                uistate.updatePointDragZone(
                    aspect="volley amp move",
                    x=line.get_xdata()[0],
                    y=line.get_ydata()[0],
                )
            elif label.endswith("EPSP slope marker"):
                uistate.updateDragZones(aspect="EPSP slope", x=line.get_xdata(), y=line.get_ydata())
            elif label.endswith("volley slope marker"):
                uistate.updateDragZones(aspect="volley slope", x=line.get_xdata(), y=line.get_ydata())

        self.mouseoverMean = self.canvasMean.mpl_connect("motion_notify_event", self.meanMouseover)
        self.mouseoverEvent = self.canvasEvent.mpl_connect("motion_notify_event", self.eventMouseover)
        self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
        self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
        # print("mouseoverUpdate calls self.graphRefresh()")
        self.graphRefresh()

    def _update_marker_data(self):
        self.usage("_update_marker_data")
        # update xy data of shown markers
        df_p = self.get_df_project()
        precision = uistate.settings["precision"]

        aspects = [
            ("EPSP_slope", " EPSP slope marker", True),
            ("EPSP_amp", " EPSP amp marker", False),
            ("volley_slope", " volley slope marker", True),
            ("volley_amp", " volley amp marker", False),
        ]

        for aspect_prefix, marker_suffix, is_slope in aspects:
            markers = {k: v for k, v in uistate.dict_rec_show.items() if k.endswith(marker_suffix)}
            for marker in markers.values():
                p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
                dfmean = self.get_dfmean(row=p_row)
                df_t = self.get_dft(row=p_row)
                stim_num = marker["stim"]
                t_row = df_t.loc[df_t["stim"] == stim_num].squeeze()
                t_stim = round(t_row["t_stim"], precision)

                if is_slope:
                    x_start = round(t_row[f"t_{aspect_prefix}_start"], precision)
                    x_end = round(t_row[f"t_{aspect_prefix}_end"], precision)
                    if not analysis.valid(x_start, x_end):
                        print(f"ERROR - {aspect_prefix}_markers: invalid x_start or x_end in _update_marker_data")
                        return
                    event_x_start = round(t_row[f"t_{aspect_prefix}_start"] - t_stim, precision)
                    event_x_end = round(t_row[f"t_{aspect_prefix}_end"] - t_stim, precision)
                    y_start = dfmean.loc[(dfmean["time"] - x_start).abs().idxmin(), "voltage"]
                    y_end = dfmean.loc[(dfmean["time"] - x_end).abs().idxmin(), "voltage"]
                    marker["line"].set_data([event_x_start, event_x_end], [y_start, y_end])
                else:
                    x_start = round(t_row[f"t_{aspect_prefix}"], precision)
                    if not analysis.valid(x_start):
                        print(f"ERROR - {aspect_prefix}_markers: invalid x_start in _update_marker_data")
                        return
                    event_x_start = round(t_row[f"t_{aspect_prefix}"] - t_stim, precision)
                    y_start = dfmean.loc[(dfmean["time"] - x_start).abs().idxmin(), "voltage"]
                    marker["line"].set_data([event_x_start, event_x_start], [y_start, y_start])

    def mouseoverDisconnect(self):
        self.usage("mouseoverDisconnect")
        # drop any prior mouseover event connections and plots
        if hasattr(self, "mouseover"):
            self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
            self.canvasOutput.mpl_disconnect(self.mouseoverOutput)
        if uistate.mouseover_plot is not None:
            uistate.mouseover_plot[0].remove()
            uistate.mouseover_plot = None
        if uistate.mouseover_blob is not None:
            uistate.mouseover_blob.remove()
            uistate.mouseover_blob = None
        if uistate.mouseover_out is not None:
            uistate.mouseover_out[0].remove()
            uistate.mouseover_out = None
        if getattr(uistate, "mouseover_out_blob", None) is not None:
            try:
                uistate.mouseover_out_blob.remove()
            except ValueError:
                pass
            uistate.mouseover_out_blob = None
        uistate.mouseover_action = None

    def eventDragSlope(self, event, action, data_x, data_y, prior_slope_start, prior_slope_end):  # graph dragging event
        # self.usage("eventDragSlope")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None or action is None:
            return
        x = event.xdata
        uistate.x_drag = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
        if uistate.x_drag == uistate.x_drag_last:  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = uistate.settings["precision"]
        time_diff = uistate.x_drag - uistate.x_on_click
        # get the x values of the slope
        blob = True  # only moving amplitudes and resizing slopes have a blob
        if action.endswith("resize"):
            x_start = prior_slope_start
        elif action.endswith("move"):
            x_start = round(prior_slope_start + time_diff, precision)
            blob = False
        x_end = round(prior_slope_end + time_diff, precision)
        # prevent resizing below 1 index - TODO: make it flip instead
        if x_end <= x_start:
            x_start_index = np.where(data_x == x_start)[0][0]
            x_end = data_x[x_start_index + 1]
        # get y values
        x_indices = np.searchsorted(data_x, [x_start, x_end])
        y_start, y_end = data_y[x_indices]
        # remember the last x index
        uistate.x_drag_last = uistate.x_drag
        # update the mouseover plot
        uistate.mouseover_plot[0].set_data([x_start, x_end], [y_start, y_end])
        if blob:
            uistate.mouseover_blob.set_offsets([x_end, y_end])
        self.canvasEvent.draw()
        self.eventDragUpdate(x_start, x_end, precision)

    def eventDragPoint(self, event, data_x, data_y, prior_amp):  # maingraph dragging event
        # self.usage("eventDragPoint")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None:
            return
        x = event.xdata
        uistate.x_drag = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
        if uistate.x_drag == uistate.x_drag_last:  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = uistate.settings["precision"]
        time_diff = uistate.x_drag - uistate.x_on_click
        x_point = round(prior_amp + time_diff, precision)
        idx = (np.abs(data_x - x_point)).argmin()
        y_point = data_y[idx]
        # print (f"x_point: {x_point}, y_point: {y_point}")
        # remember the last x index
        uistate.x_drag_last = uistate.x_drag
        # update the mouseover plot
        uistate.mouseover_blob.set_offsets([x_point, y_point])
        self.canvasEvent.draw()
        self.eventDragUpdate(x_point, x_point, precision)

    def eventDragUpdate(self, x_start, x_end, precision):
        # TODO: Overhaul this whole magic-string-mess
        """
        Updates output graph uistate.mouseover_out while dragging event markers
        x_start: new start time of slope or amplitude
        x_end: new end time of slope (same as x_start for amplitude)
        precision: number of decimal places to round to
        * updates uistate.dft_temp in place: overwrites dft on release
        * builds a dict_t and feeds it to analysis.build_dfoutput
        * updates uistate.mouseover_out plot data
        TODO: fix for dfstimoutput
        """

        # self.usage("eventDragUpdate")
        def handle_slope(aspect, x_start, x_end, precision, stim_offset):
            slope_width = round(x_end - x_start, precision)
            slope_start_key = f"t_{aspect}_start"
            slope_end_key = f"t_{aspect}_end"
            slope_width_key = f"t_{aspect}_width"
            return {
                slope_start_key: round(x_start + stim_offset, precision),
                slope_end_key: round(x_end + stim_offset, precision),
                slope_width_key: round(slope_width, precision),
            }

        def handle_amp(aspect, x_start, stim_offset, precision):
            amp_key = f"t_{aspect}"
            return {
                "t_stim": stim_offset,
                amp_key: round(x_start + stim_offset, precision),
            }

        action = uistate.mouseover_action
        if action is None:
            return
        aspect = "_".join(action.split()[:2])
        stim_idx = uistate.list_idx_select_stims[0]
        prow = self.get_prow()
        n_stims = prow["stims"]
        dft_temp = uistate.dft_temp  # set when clicked
        stim_offset = dft_temp.at[stim_idx, "t_stim"]
        is_io = getattr(uistate, "experiment_type", "time") == "io"
        dict_t = None
        if aspect in ["EPSP_slope", "volley_slope"]:
            axis = uistate.ax1 if is_io else uistate.ax2
            dict_t = handle_slope(aspect, x_start, x_end, precision, stim_offset)
        elif aspect in ["EPSP_amp", "volley_amp"]:
            axis = uistate.ax1
            dict_t = handle_amp(aspect, x_start, stim_offset, precision)

        for key, value in dict_t.items():
            dft_temp.at[stim_idx, key] = value
            if not uistate.checkBox["timepoints_per_stim"] and n_stims > 1:  # update all timepoints in df_t
                offset = dft_temp.at[stim_idx, "t_stim"] - dft_temp.at[stim_idx, key]
                for i, i_trow in dft_temp.iterrows():
                    dft_temp.at[i, key] = round(i_trow["t_stim"] - offset, precision)

        trow_temp = dft_temp.iloc[stim_idx]
        dict_t["t_EPSP_amp_halfwidth"] = trow_temp["t_EPSP_amp_halfwidth"]
        dict_t["t_volley_amp_halfwidth"] = trow_temp["t_volley_amp_halfwidth"]
        dict_t["norm_output_from"] = trow_temp["norm_output_from"]
        dict_t["norm_output_to"] = trow_temp["norm_output_to"]

        dict_t["stim"] = trow_temp["stim"]
        dict_t["amp_zero"] = trow_temp["amp_zero"]

        if is_io or (not uistate.checkBox["timepoints_per_stim"] and n_stims > 1):
            dft_to_update = uistate.dft_temp.copy()
        else:
            dft_to_update = uistate.dft_temp.iloc[[stim_idx]].copy()

        rec_filter = prow.get("filter")

        if uistate.x_axis == "stim" and not is_io and len(uistate.df_rec_select_time) > 1:
            # In stim mode the output x-axis is stim-numbered.  The per-sweep
            # build_dfoutput result has sweep-space x-values which are meaningless
            # here.  Instead, re-measure dfmean around the stim window — exactly
            # the same logic used in build_dfoutput's stim-mode section and in
            # the 8.4 release-path block — so the preview point lands at the
            # correct stim x-position and reflects the dfmean aggregate.
            dfmean = self.get_dfmean(row=prow)
            dict_t_stim = dft_to_update.iloc[0].to_dict()
            t_stim = dict_t_stim.get("t_stim", 0.0)
            t_win_start = t_stim - 0.002
            t_win_end = dict_t_stim.get("t_EPSP_amp", t_stim + 0.01) + dict_t_stim.get(
                "t_EPSP_amp_width",
                2 * dict_t_stim.get("t_EPSP_amp_halfwidth", 0.001),
            )
            snippet = dfmean[(dfmean["time"] >= t_win_start) & (dfmean["time"] <= t_win_end)].copy().reset_index(drop=True)
            measured = analysis.measure_waveform(snippet, dict_t_stim, filter=rec_filter)
            stim_num = int(dict_t_stim["stim"])
            drag_x = np.array([stim_num])
            drag_y = np.array([measured.get(aspect, np.nan)])
            outkey = aspect  # norm not applied in stim-mode preview
            marker_style = "o"
            linestyle = "None"
        else:
            if pd.notna(prow.get("bin_size")):
                dffilter = self.get_dfbin(prow)
            else:
                dffilter = self.get_dffilter(row=prow)
            out = analysis.build_dfoutput(
                dffilter=dffilter,
                dfmean=self.get_dfmean(row=prow),
                dft=dft_to_update,
                quick=True,
                filter=rec_filter,
            )
            out = self.V2mV(out)
            if is_io:
                io_input = getattr(uistate, "io_input", "vamp")
                io_output = getattr(uistate, "io_output", "EPSPamp")
                x_col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(io_input, "volley_amp")
                y_col = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")

                out_sweeps = out[out["sweep"].notna()].dropna(subset=[x_col, y_col])
                drag_x = out_sweeps[x_col].values
                drag_y = out_sweeps[y_col].values
                marker_style = "o"
                linestyle = "None"
                aspect = y_col
            else:
                # norm handling for EPSP
                if aspect in ["EPSP_amp", "EPSP_slope"]:
                    aspect_norm = f"{aspect}_norm"
                    outkey = aspect_norm if uistate.checkBox["norm_EPSP"] else aspect
                else:
                    outkey = aspect

                is_pp = getattr(uistate, "experiment_type", "time") == "PP"
                if is_pp:
                    out_sweeps = out[out["sweep"].notna()]
                    out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                    out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                    common_sweeps = out1.index.intersection(out2.index).dropna()
                    if not common_sweeps.empty:
                        o1 = out1.loc[common_sweeps]
                        o2 = out2.loc[common_sweeps]
                        v1 = o1[aspect].values.astype(float)
                        v2 = o2[aspect].values.astype(float)
                        import warnings

                        import numpy as np

                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            ppr = v2 / v1
                            ppr[~np.isfinite(ppr)] = np.nan
                        x_val_map = {}
                        i = 1
                        for key in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]:
                            if uistate.checkBox.get(key, True):
                                x_val_map[key] = i
                                i += 1
                        x_val = x_val_map.get(aspect, 1)
                        drag_x = np.full(len(common_sweeps), x_val)
                        drag_y = ppr
                        marker_style = "o"
                        linestyle = "None"
                    else:
                        drag_x = out["sweep"]
                        drag_y = out[outkey]
                        marker_style = "o" if len(drag_x) == 1 else "None"
                        linestyle = "-"
                else:
                    drag_x = out["sweep"]
                    drag_y = out[outkey]
                    marker_style = "o" if len(drag_x) == 1 else "None"
                    linestyle = "-"

        msize = 10 if is_io else 6
        if getattr(uistate, "mouseover_out", None) is None:
            uistate.mouseover_out = axis.plot(
                drag_x,
                drag_y,
                color=uistate.settings.get(f"rgb_{aspect}", "black"),
                linewidth=3,
                linestyle=linestyle,
                marker=marker_style,
                markersize=msize,
            )
        else:
            if getattr(uistate.mouseover_out[0], "axes", None) != axis:
                uistate.mouseover_out[0].remove()
                uistate.mouseover_out = axis.plot(
                    drag_x,
                    drag_y,
                    color=uistate.settings.get(f"rgb_{aspect}", "black"),
                    linewidth=3,
                    linestyle=linestyle,
                    marker=marker_style,
                    markersize=msize,
                )
            else:
                uistate.mouseover_out[0].set_data(drag_x, drag_y)
                uistate.mouseover_out[0].set_marker(marker_style)
                uistate.mouseover_out[0].set_linestyle(linestyle)
                uistate.mouseover_out[0].set_color(uistate.settings.get(f"rgb_{aspect}", "black"))
                uistate.mouseover_out[0].set_markersize(msize)

        self.canvasOutput.draw()

    def eventDragReleased(self, event, data_x, data_y):  # graph release event
        # TODO: Overhaul this whole magic-string-mess
        self.usage("eventDragReleased")
        if getattr(uistate, "mouseover_action", None) is None:
            uistate.dragging = False
            if getattr(self, "mouse_release", None) is not None:
                self.canvasEvent.mpl_disconnect(self.mouse_release)
                self.mouse_release = None
            if getattr(self, "mouse_drag", None) is not None:
                self.canvasEvent.mpl_disconnect(self.mouse_drag)
                self.mouse_drag = None
            self.mouseoverUpdate()
            return
        print(f" - uistate.mouseover_action: {uistate.mouseover_action}")
        self.canvasEvent.mpl_disconnect(self.mouse_drag)
        self.canvasEvent.mpl_disconnect(self.mouse_release)
        uistate.x_drag_last = None
        if uistate.x_drag is None or uistate.x_drag == uistate.x_on_click:  # nothing to update (no movement or same position)
            print("x_drag is None or x_drag == x_on_click")
            self.mouseoverUpdate()
            return

        dft_temp = uistate.dft_temp  # copied on clicked, updated while dragging
        stim_idx = uistate.list_idx_select_stims[0]
        trow_temp = dft_temp.iloc[stim_idx]

        # Map drag actions to (0:method value, 1:aspect name, 2:{new measuring points}, 3:plot update function)
        action_mapping = {
            "EPSP slope": (
                "t_EPSP_slope_method",
                "EPSP slope",
                {
                    "t_EPSP_slope_start": trow_temp["t_EPSP_slope_start"],
                    "t_EPSP_slope_end": trow_temp["t_EPSP_slope_end"],
                },
                uistate.updateDragZones,
            ),
            "EPSP amp move": (
                "t_EPSP_amp_method",
                "EPSP amp",
                {
                    "t_EPSP_amp": trow_temp["t_EPSP_amp"],
                    "t_EPSP_amp_halfwidth": trow_temp["t_EPSP_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                uistate.updatePointDragZone,
            ),
            "volley slope": (
                "t_volley_slope_method",
                "volley slope",
                {
                    "t_volley_slope_start": trow_temp["t_volley_slope_start"],
                    "t_volley_slope_end": trow_temp["t_volley_slope_end"],
                },
                uistate.updateDragZones,
            ),
            "volley amp move": (
                "t_volley_amp_method",
                "volley amp",
                {
                    "t_volley_amp": trow_temp["t_volley_amp"],
                    "t_volley_amp_halfwidth": trow_temp["t_volley_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                uistate.updatePointDragZone,
            ),
        }
        # Build a dict_t of new measuring points and update drag zones
        dict_t_updates = {}
        for action, values in action_mapping.items():
            if uistate.mouseover_action.startswith(action):
                method_field = values[0]
                aspect = values[1]
                dict_t_updates = values[2]
                update_function = values[3]
                dict_t_updates[method_field] = "manual"
                dict_t_updates.update(
                    {
                        "stim": trow_temp["stim"],
                        "t_stim": trow_temp["t_stim"],
                        "norm_output_from": trow_temp["norm_output_from"],
                        "norm_output_to": trow_temp["norm_output_to"],
                    }
                )
                update_function()
                break
        else:
            logger.warning(
                "eventDragReleased: mouseover_action '%s' did not match any known action; aborting update.",
                uistate.mouseover_action,
            )
            self.mouseoverUpdate()
            return

        # update selected row of dft_temp with the values from dict_t
        for key, value in dict_t_updates.items():
            dft_temp.loc[dft_temp.index[stim_idx], key] = value
            # old_trow = self.get_trow()
            # print(f" - * - stim{old_trow['stim']} {key} was {old_trow[key]}, set to {dft_temp.loc[dft_temp.index[stim_idx], key]}.")

        prow = self.get_prow()
        rec_name = prow["recording_name"]
        dfmean = self.get_dfmean(row=prow)

        # update dfoutput; dict and file, with normalized columns if applicable
        dfoutput = self.get_dfoutput(row=prow)
        if pd.notna(prow.get("bin_size")):
            dffilter = self.get_dfbin(prow)
        else:
            dffilter = self.get_dffilter(row=prow)
        stim_num = trow_temp["stim"]

        n_stims = prow["stims"]
        if not uistate.checkBox["timepoints_per_stim"] and n_stims > 1:
            dft_to_update = uistate.dft_temp.copy()
            if method_field in dict_t_updates:
                dft_to_update[method_field] = dict_t_updates[method_field]
        else:
            dft_to_update = uistate.dft_temp.iloc[[stim_idx]].copy()
            dft_to_update.update(pd.DataFrame([dict_t_updates]))

        rec_filter = prow.get("filter")
        if pd.isna(rec_filter) or not rec_filter or rec_filter == "none":
            rec_filter = "voltage"

        new_dfoutput = analysis.build_dfoutput(
            dffilter=dffilter,
            dfmean=dfmean,
            dft=dft_to_update,
            filter=rec_filter,
        )
        # print(f"dfoutput: {dfoutput}")
        # update volley means
        if aspect == "volley amp":
            if not uistate.checkBox["timepoints_per_stim"] and n_stims > 1:
                for s in new_dfoutput["stim"].unique():
                    dft_temp.loc[dft_temp["stim"] == s, "volley_amp_mean"] = new_dfoutput[new_dfoutput["stim"] == s]["volley_amp"].mean()
            else:
                dft_temp.loc[dft_temp.index[stim_idx], "volley_amp_mean"] = new_dfoutput["volley_amp"].mean()
        elif aspect == "volley slope":
            if not uistate.checkBox["timepoints_per_stim"] and n_stims > 1:
                for s in new_dfoutput["stim"].unique():
                    dft_temp.loc[dft_temp["stim"] == s, "volley_slope_mean"] = new_dfoutput[new_dfoutput["stim"] == s]["volley_slope"].mean()
            else:
                dft_temp.loc[dft_temp.index[stim_idx], "volley_slope_mean"] = new_dfoutput["volley_slope"].mean()

        if uistate.checkBox["timepoints_per_stim"] or n_stims == 1:
            new_dfoutput["stim"] = int(stim_num)

        dfoutput.set_index(["stim", "sweep"], inplace=True)
        new_dfoutput.set_index(["stim", "sweep"], inplace=True)
        dfoutput = dfoutput.astype(float)
        new_dfoutput = new_dfoutput.astype(float)
        dfoutput.update(new_dfoutput)
        dfoutput.reset_index(inplace=True)
        new_dfoutput.reset_index(inplace=True)

        # --- 8.4: Refresh the stim-mode row (sweep==NaN) for this stim ---
        # build_dfoutput with dft_single (len=1) only produces sweep-mode rows.
        # Re-measure dfmean around the stim window so the stim-mode aggregate
        # reflects the new timepoints after the drag.
        if len(dft_temp) > 1:
            stims_to_update = dft_to_update["stim"].tolist()
            for s_num in stims_to_update:
                dict_t_stim = dft_to_update[dft_to_update["stim"] == s_num].iloc[0].to_dict()
                t_stim = dict_t_stim.get("t_stim", 0.0)
                t_win_start = t_stim - 0.002
                t_win_end = dict_t_stim.get("t_EPSP_amp", t_stim + 0.01) + dict_t_stim.get(
                    "t_EPSP_amp_width",
                    2 * dict_t_stim.get("t_EPSP_amp_halfwidth", 0.001),
                )
                snippet = dfmean[(dfmean["time"] >= t_win_start) & (dfmean["time"] <= t_win_end)].copy().reset_index(drop=True)
                measured = analysis.measure_waveform(snippet, dict_t_stim, filter=prow.get("filter", "voltage"))
                # Update the stim-mode row in dfoutput
                stim_mask = (dfoutput["stim"] == int(s_num)) & dfoutput["sweep"].isna()
                if stim_mask.any():
                    for col, val in measured.items():
                        if col in dfoutput.columns:
                            dfoutput.loc[stim_mask, col] = val
                else:
                    # Stim-mode row doesn't exist yet (shouldn't happen, but be safe)
                    stim_row = {"stim": int(s_num), "sweep": np.nan}
                    stim_row.update(measured)
                    stim_row["EPSP_amp_norm"] = np.nan
                    stim_row["EPSP_slope_norm"] = np.nan
                    dfoutput = pd.concat([dfoutput, pd.DataFrame([stim_row])], ignore_index=True)

        self.persistOutput(rec_name=rec_name, dfoutput=dfoutput, p_row=prow)
        uiplot.updateStimLines(rec_name=rec_name, dfoutput=self.V2mV(dfoutput))

        self.set_dft(rec_name, dft_temp)
        new_dft = self.get_dft(prow)
        self.tableStimModel.setData(new_dft)
        self.formatTableStimLayout(new_dft)
        self.set_rec_status(rec_name=rec_name)
        trow = self.get_trow()
        if trow is None:
            logger.debug("eventDragReleased: trow is None after drag commit, falling back to mouseoverUpdate")
            self.mouseoverUpdate()
            return

        if aspect not in ["EPSP amp", "EPSP slope", "volley amp", "volley slope"]:
            self.mouseoverUpdate()
            return

        stim_offset = trow["t_stim"]
        rec_filter = prow.get("filter", "voltage")
        _pre_stim = dfmean[(dfmean["time"] >= stim_offset - 0.002) & (dfmean["time"] < stim_offset - 0.001)]
        amp_zero_plot = _pre_stim[rec_filter].mean() if not _pre_stim.empty else dfmean.loc[(dfmean["time"] - stim_offset).abs().idxmin(), rec_filter]

        uiplot.update(
            prow=prow,
            trow=trow,
            aspect=aspect,
            data_x=data_x,
            data_y=data_y,
            dfoutput=self.V2mV(dfoutput),
            amp_zero_plot=amp_zero_plot,
        )

        def update_amp_marker(trow, aspect, prow, dfmean, dfoutput):
            rec_filter = prow.get("filter", "voltage")
            if rec_filter != "voltage":
                label_core = f"{rec_name} ({rec_filter})"
            else:
                label_core = rec_name
            labelbase = f"{label_core} - stim {trow['stim']}"
            labelamp = f"{labelbase} {aspect}"
            column_name = aspect.replace(" ", "_")
            t_aspect = f"t_{column_name}"
            stim_offset = trow["t_stim"]
            x = trow[t_aspect] - stim_offset
            y = dfmean.loc[(dfmean["time"] - trow[t_aspect]).abs().idxmin(), rec_filter]

            out_stim = dfoutput.loc[dfoutput["stim"] == trow["stim"]]
            out_agg = out_stim[out_stim["sweep"].isna()]

            t_amp = trow[t_aspect] - stim_offset
            amp_x = (
                t_amp - trow[f"{t_aspect}_halfwidth"],
                t_amp + trow[f"{t_aspect}_halfwidth"],
            )

            _pre_stim = dfmean[(dfmean["time"] >= stim_offset - 0.002) & (dfmean["time"] < stim_offset - 0.001)]
            amp_zero_plot = (
                _pre_stim[rec_filter].mean() if not _pre_stim.empty else dfmean.loc[(dfmean["time"] - stim_offset).abs().idxmin(), rec_filter]
            )

            if not out_agg.empty:
                amp = out_agg[column_name].values[0]
            else:
                t_amp_val = trow[t_aspect]
                half = trow.get(f"{t_aspect}_halfwidth", 0)
                if half == 0:
                    amp_val = dfmean.loc[(dfmean["time"] - t_amp_val).abs().idxmin(), rec_filter]
                else:
                    amp_val = dfmean.loc[(dfmean["time"] >= t_amp_val - half) & (dfmean["time"] <= t_amp_val + half), rec_filter].mean()
                amp = -(amp_val - amp_zero_plot)

            uiplot.updateAmpMarker(labelamp, x, y, amp_x, amp_zero_plot, amp=amp)

        if aspect in ["EPSP amp", "volley amp"]:
            # print(f" - {aspect} updated")
            if uistate.checkBox["timepoints_per_stim"]:
                update_amp_marker(trow, aspect, prow, dfmean, dfoutput)
            else:
                dft = self.get_dft(prow)
                for i, i_trow in dft.iterrows():
                    update_amp_marker(i_trow, aspect, prow, dfmean, dfoutput)

        # update groups
        affected_groups = self.get_groupsOfRec(prow["ID"])
        self.group_cache_purge(affected_groups)

        # We MUST run update_show BEFORE rebuilding the groups so that
        # the dict_rec_labels (which dict_group_show relies on for PPR data gathering)
        # matches the visible state expectations.
        self.mouseoverUpdate()
        self.update_show()

        for group_ID in affected_groups:
            uiplot.unPlotGroup(group_ID=group_ID)
            df_groupmean = self.get_dfgroupmean(group_ID)
            x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
            uiplot.addGroup(group_ID, self.dd_groups[group_ID], self.V2mV(df_groupmean), x_pos=x_pos)

        self.update_show()  # Re-apply visibility rules to the newly added group artists
        self.graphRefresh()  # Refresh the canvas to draw the new groups
        self.update_amp_lineEdits()
        self.update_slope_lineEdits()
        self.zoomAuto(skip_axe=True)

        if config.talkback:
            self.talkback()

    def zoomOnScroll(self, event, graph):
        if graph == "mean":
            canvas = self.canvasMean
            ax = uistate.axm
        elif graph == "event":
            canvas = self.canvasEvent
            ax = uistate.axe
        elif graph == "output":
            canvas = self.canvasOutput
            slope_left = uistate.slopeOnly()
            ax = uistate.ax2
            ax1 = uistate.ax1

        if event.button == "up":
            zoom = 1.1
        else:
            zoom = 1 / 1.1

        if event.xdata is None or event.ydata is None:  # if the scroll event was outside the axes, extrapolate x and y
            x_display, y_display = ax.transAxes.inverted().transform((event.x, event.y))
            x = x_display * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
            y = y_display * (ax.get_ylim()[1] - ax.get_ylim()[0]) + ax.get_ylim()[0]
        else:
            x = event.xdata
            y = event.ydata

        left = 0.12 * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
        right = 0.88 * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
        bottom = 0.08 * (ax.get_ylim()[1] - ax.get_ylim()[0]) + ax.get_ylim()[0]
        on_x = y <= bottom
        on_left = x <= left
        on_right = x >= right

        # Apply the zoom
        ymin0 = uistate.checkBox["output_ymin0"]
        if on_x:  # check this first; x takes precedence
            ax.set_xlim(x - (x - ax.get_xlim()[0]) / zoom, x + (ax.get_xlim()[1] - x) / zoom)
        elif "slope_left" in locals():  # on output
            if on_left:
                if slope_left:  # scroll left y zoom output slope y
                    ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: uistate.checkBox...
                    ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
                else:  # scroll left y to zoom output amp y
                    ymin = 0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom  # TODO: uistate.checkBox...
                    ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
            elif on_right and not slope_left:  # scroll right y to zoom output slope y
                ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: uistate.checkBox...
                ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
            else:  # default, scroll graph to zoom all
                ax1.set_xlim(
                    x - (x - ax1.get_xlim()[0]) / zoom,
                    x + (ax1.get_xlim()[1] - x) / zoom,
                )
                ymin = 0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom  # TODO: uistate.checkBox...
                ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
                ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: uistate.checkBox...
                ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
        else:  # on mean or event graphs
            if on_left:  # scroll left x to zoom mean or event x
                ax.set_ylim(y - (y - ax.get_ylim()[0]) / zoom, y + (ax.get_ylim()[1] - y) / zoom)
            else:
                ax.set_xlim(x - (x - ax.get_xlim()[0]) / zoom, x + (ax.get_xlim()[1] - x) / zoom)
                ax.set_ylim(y - (y - ax.get_ylim()[0]) / zoom, y + (ax.get_ylim()[1] - y) / zoom)

        # TODO: this block is dev visualization for debugging
        if False:
            if hasattr(ax, "hline"):  # If the line exists, update it
                ax.hline.set_ydata(bottom)
            else:  # Otherwise, create a new line
                ax.hline = ax.axhline(y=bottom, color="r", linestyle="--")

        canvas.draw()

        # After zooming, the pixel→data scale has changed, so the
        # mouseover detection zones must be recalculated against the new limits.
        if graph == "event":
            self._recalc_axe_drag_zones()
        elif graph == "mean":
            self._recalc_axm_detection_zones()
