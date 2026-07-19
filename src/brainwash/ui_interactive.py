import logging
import warnings

import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtGui, QtWidgets

from brainwash_ui import plot_drag, plot_identity, plot_series
from brainwash import analysis_v3 as analysis
from brainwash import ui_plot
from ui_state_parts import measure_rgb

logger = logging.getLogger(__name__)


class InteractivePlotMixin:
    #####################################################
    #          Mouseover, click and drag events         #
    #####################################################

    def _groups_only_output_select_ok(self, canvas) -> bool:
        """True when output sweep select is allowed with no recording selected."""
        if canvas is not self.canvasOutput:
            return False
        if self.uistate.plot.list_idx_select_recs:
            return False
        exp = self.uistate.experiment.experiment_type
        if exp in ("io", "PP"):
            return False
        domain = self._groups_output_sweep_domain()
        return bool(domain)

    def _groups_output_sweep_domain(self) -> list[int]:
        return plot_drag.group_output_sweep_domain(
            getattr(self.uistate.plot, "dict_group_show", None),
            getattr(self.uistate.plot, "dict_group_labels", None),
        )

    def graphClicked(self, event, canvas):  # graph click event
        if event.button == 2:  # middle click, reset zoom on the clicked graph
            if canvas == self.canvasOutput and self.uistate.plot.ax1 is not None:
                if not self.uistate.plot.list_idx_select_recs:
                    # Groups visible on ax1/ax2 with no single recording selected: fit from current groups
                    self._fit_output_zoom_to_groups()
                self.zoomReset(self.uistate.plot.ax1)
            elif self.uistate.plot.list_idx_select_recs:
                if canvas == self.canvasMean and self.uistate.plot.axm is not None:
                    self.zoomReset(self.uistate.plot.axm)
                elif canvas == self.canvasEvent and self.uistate.plot.axe is not None:
                    self.zoomReset(self.uistate.plot.axe)
            return

        groups_only_output = self._groups_only_output_select_ok(canvas)
        if not self.uistate.plot.list_idx_select_recs and not groups_only_output:
            return
        x = event.xdata
        if x is None:  # clicked outside graph; do nothing
            return
        self.usage("graphClicked")
        if event.button == 3:  # right click, deselect
            if self.uistate.plot.dragging:
                return
            # Groups-only: only clear output sweep selection (mean canvas stays rec-gated)
            if groups_only_output and canvas is not self.canvasOutput:
                return
            self.mouse_drag = None
            self.mouse_release = None
            self.uistate.plot.x_drag = None
            # Clear texts + selection state immediately (lightweight) for responsive feel and
            # so that any immediate readers (tagging etc.) see the cleared range.
            # Defer the artist removes (xDeselect + clear_axe mean) + stim buttons + draws.
            if canvas == self.canvasMean:
                self.lineEdit_mean_selection_start.setText("")
                self.lineEdit_mean_selection_end.setText("")
                self.uistate.plot.x_select["mean_start"] = None
                self.uistate.plot.x_select["mean_end"] = None
            else:
                self.lineEdit_sweeps_range_from.setText("")
                self.lineEdit_sweeps_range_to.setText("")
                self.uistate.plot.x_select["output"] = set()
                self.uistate.plot.x_select["output_start"] = None
                self.uistate.plot.x_select["output_end"] = None
            QtCore.QTimer.singleShot(0, lambda c=canvas: self._finalize_deselect(c))
            return

        # left clicked on a graph
        # Groups-only output: sweep range for lineEdits / test sets (no prow / no axe mean)
        if groups_only_output:
            if self.uistate.experiment.experiment_type == "io":
                return
            self.uistate.plot.dragging = True
            sweep_numbers = self._groups_output_sweep_domain()
            if not sweep_numbers:
                self.uistate.plot.dragging = False
                return
            self.uistate.plot.x_on_click = plot_drag.snap_sweep_index(sweep_numbers, x)
            self.uistate.plot.x_select["output_start"] = self.uistate.plot.x_on_click
            self.lineEdit_sweeps_range_from.setText(str(self.uistate.plot.x_on_click))
            self.connectDragRelease(x_range=sweep_numbers, rec_ID=None, graph="output")
            return

        self.uistate.plot.dragging = True
        prow = self.get_prow()
        if prow is None:
            self.uistate.plot.dragging = False
            return

        if (
            (canvas == self.canvasEvent) and (len(self.uistate.plot.list_idx_select_recs) == 1) and (len(self.uistate.plot.list_idx_select_stims) == 1)
        ):  # Event canvas left-clicked with just one rec and stim selected, middle graph: editing detected events
            self.uistate.plot.dft_temp = self.get_dft(prow).copy()
            trow = self.uistate.plot.dft_temp.loc[self.uistate.plot.list_idx_select_stims[0]]
            rec_filter = prow["filter"]
            rec_name = prow["recording_name"]
            if rec_filter != "voltage":
                label_core = f"{rec_name} ({rec_filter})"
            else:
                label_core = rec_name
            label = f"{label_core} - stim {trow['stim']}"
            from brainwash_ui import plot_identity as pi

            dict_event = pi.find_entry_by_display_label(self.uistate.plot.dict_rec_labels, label)[1]
            if dict_event is None:
                # Metadata fallback: event trace on axe for this stim
                hits = pi.find_rec_entries(
                    self.uistate.plot.dict_rec_labels,
                    rec_ID=prow["ID"],
                    stim=trow["stim"],
                    axis="axe",
                    role=pi.ROLE_EVENT_TRACE,
                )
                dict_event = hits[0][1] if hits else None
            if dict_event is None:
                self.uistate.plot.dragging = False
                return
            data_x = plot_drag.artist_xdata(dict_event["line"])
            data_y = plot_drag.artist_ydata(dict_event["line"])
            self.uistate.plot.x_on_click = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
            # print(f"self.uistate.plot.x_on_click: {self.uistate.plot.x_on_click}")
            if event.inaxes is not None:
                if (event.button == 1 or event.button == 3) and (self.uistate.plot.mouseover_action is not None):
                    action = self.uistate.plot.mouseover_action
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
            if self.uistate.plot.mean_mouseover_stim_select is not None:
                self.uistate.plot.dragging = False
                self.stimSelectionChanged()
                return
            dfmean = self.get_dfmean(prow)  # Required for event dragging, x and y
            time_values = dfmean["time"].values
            self.uistate.plot.x_on_click = time_values[np.abs(time_values - x).argmin()]
            self.uistate.plot.x_select["mean_start"] = self.uistate.plot.x_on_click
            self.lineEdit_mean_selection_start.setText(f"{self.uistate.plot.x_select['mean_start'] * 1000:g}")
            self.update_stim_buttons()
            self.connectDragRelease(x_range=time_values, rec_ID=prow["ID"], graph="mean")
        elif canvas == self.canvasOutput:  # Output canvas (bottom graph) left-clicked: click and drag to select specific sweeps
            if self.uistate.experiment.experiment_type == "io":
                self.uistate.plot.dragging = False
                return
            sweep_numbers = list(range(0, int(prow["sweeps"])))
            self.uistate.plot.x_on_click = plot_drag.snap_sweep_index(sweep_numbers, x)
            self.uistate.plot.x_select["output_start"] = self.uistate.plot.x_on_click
            self.lineEdit_sweeps_range_from.setText(str(self.uistate.plot.x_on_click))
            self.connectDragRelease(x_range=sweep_numbers, rec_ID=prow["ID"], graph="output")

    # pyqtSlot decorators
    def clear_axm_stim_hover_chrome(self, *, draw: bool = True) -> None:
        """Reset axm stim-marker hover (alpha/zorder) and clear pending stim click target.

        Multi-rec selection disables click-to-select stims; leftover lit markers confuse.
        """
        from brainwash_ui import plot_identity as pi

        self.uistate.plot.mean_mouseover_stim_select = None
        for _k, entry in (self.uistate.plot.dict_rec_labels or {}).items():
            if not isinstance(entry, dict):
                continue
            if entry.get("axis") != "axm" or entry.get("role") != pi.ROLE_STIM_MARKER:
                continue
            line = entry.get("line")
            if line is None:
                continue
            try:
                line.set_zorder(0)
                line.set_alpha(0.4)
            except Exception:
                pass
        if draw and getattr(self.uistate.plot, "axm", None) is not None:
            try:
                self.uistate.plot.axm.figure.canvas.draw_idle()
            except Exception:
                pass

    @QtCore.pyqtSlot()
    def meanMouseover(self, event):  # determine which event is being mouseovered
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        self.uistate.plot.mean_mouseover_stim_select = None  # Always clear on movement initially
        # Multi-rec: no stim click/hover affordance on axm (selection via fields only)
        n_sel = len(self.uistate.plot.list_idx_select_recs or [])
        if n_sel != 1:
            self.clear_axm_stim_hover_chrome(draw=True)
            return
        dft = self.uistate.plot.df_rec_select_time
        if dft is None or dft.empty:
            # print("No single recording selected with timepoints to mouseover.")
            return
        n_stims = len(dft)
        if n_stims < 1:
            # print("Not enough stims to mouseover.")
            return
        # One recording selected: define mouseover zones for every detected stim
        prow = self.get_prow()
        if prow is None:
            return

        axm = self.uistate.plot.axm
        self.uistate.plot.mean_mouseover_stim_select = None  # stim that will be selected if clicked
        self.uistate.plot.mean_stim_x_ranges = {}  # dict: stim_num: (x_start, x_end)
        # Margins are set pixel-based by _recalc_axm_detection_zones; recompute
        # here only as a fallback when they have not been initialised yet.
        if self.uistate.plot.mean_x_margin is None or self.uistate.plot.mean_y_margin is None:
            self.uistate.setMarginsAxm(axm=axm, pixels=ui_plot.STIM_MARKER_SIZE // 2 + 5)
        y_range = (
            -self.uistate.plot.mean_y_margin,
            self.uistate.plot.mean_y_margin,
        )  # stim markers should be at y~0

        # build detection zones for each stim
        for row in dft.itertuples(index=False):
            stim = row.stim
            t_stim = row.t_stim
            x_range = t_stim - self.uistate.plot.mean_x_margin, t_stim + self.uistate.plot.mean_x_margin
            self.uistate.plot.mean_stim_x_ranges[stim] = x_range
        from brainwash_ui import plot_identity as pi

        def _axm_stim_marker_line(stim_num):
            hits = pi.find_rec_entries(
                self.uistate.plot.dict_rec_labels,
                rec_ID=prow["ID"],
                stim=stim_num,
                axis="axm",
                role=pi.ROLE_STIM_MARKER,
            )
            if hits:
                return hits[0][1].get("line")
            # Fallback: display_label (respects blind aliases on entry)
            for _k, ent in (self.uistate.plot.dict_rec_labels or {}).items():
                if not isinstance(ent, dict):
                    continue
                if ent.get("rec_ID") != prow["ID"] and str(ent.get("rec_ID")) != str(prow["ID"]):
                    continue
                if ent.get("axis") != "axm" or ent.get("role") != pi.ROLE_STIM_MARKER:
                    continue
                if pi._stim_equal(ent.get("stim"), stim_num):
                    return ent.get("line")
            return None

        # check if mouse is within any of the stim zones
        for stim, x_range in self.uistate.plot.mean_stim_x_ranges.items():
            line = _axm_stim_marker_line(stim)
            if x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]:
                self.uistate.plot.mean_mouseover_stim_select = stim
                if line is not None:
                    line.set_zorder(10)
                    line.set_alpha(1.0)
                break
            else:
                if line is not None:
                    line.set_zorder(0)
                    line.set_alpha(0.4)

        axm.figure.canvas.draw_idle()

    def eventMouseover(self, event):  # determine which event is being mouseovered
        if self.uistate.plot.df_rec_select_data is None:  # no single recording/stim combo selected
            return
        p = self.uistate.plot
        axe = p.axe

        def plotMouseover(action, axe):
            alpha = 0.8
            linewidth = 3 if "resize" in action else 10
            if "slope" in action:
                if "EPSP" in action:
                    x_range = (
                        p.EPSP_slope_start_xy[0],
                        p.EPSP_slope_end_xy[0],
                    )
                    y_range = (
                        p.EPSP_slope_start_xy[1],
                        p.EPSP_slope_end_xy[1],
                    )
                    color = measure_rgb(self.uistate.project.settings, "EPSP_slope")
                elif "volley" in action:
                    x_range = (
                        p.volley_slope_start_xy[0],
                        p.volley_slope_end_xy[0],
                    )
                    y_range = (
                        p.volley_slope_start_xy[1],
                        p.volley_slope_end_xy[1],
                    )
                    color = measure_rgb(self.uistate.project.settings, "volley_slope")

                if self.uistate.plot.mouseover_blob is None:
                    self.uistate.plot.mouseover_blob = axe.scatter(x_range[1], y_range[1], color=color, s=100, alpha=alpha)
                else:
                    self.uistate.plot.mouseover_blob.set_offsets([x_range[1], y_range[1]])
                    self.uistate.plot.mouseover_blob.set_sizes([100])
                    self.uistate.plot.mouseover_blob.set_color(color)

                if self.uistate.plot.mouseover_plot is None:
                    self.uistate.plot.mouseover_plot = axe.plot(
                        x_range,
                        y_range,
                        color=color,
                        linewidth=linewidth,
                        alpha=alpha,
                        label="mouseover",
                    )
                else:
                    self.uistate.plot.mouseover_plot[0].set_data(x_range, y_range)
                    self.uistate.plot.mouseover_plot[0].set_linewidth(linewidth)
                    self.uistate.plot.mouseover_plot[0].set_alpha(alpha)
                    self.uistate.plot.mouseover_plot[0].set_color(color)

            elif "amp" in action:
                if "EPSP" in action:
                    x, y = p.EPSP_amp_xy
                    color = measure_rgb(self.uistate.project.settings, "EPSP_amp")
                elif "volley" in action:
                    x, y = p.volley_amp_xy
                    color = measure_rgb(self.uistate.project.settings, "volley_amp")

                if self.uistate.plot.mouseover_blob is None:
                    self.uistate.plot.mouseover_blob = axe.scatter(x, y, color=color, s=100, alpha=alpha)
                else:
                    self.uistate.plot.mouseover_blob.set_offsets([x, y])
                    self.uistate.plot.mouseover_blob.set_sizes([100])
                    self.uistate.plot.mouseover_blob.set_color(color)

        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        if event.inaxes == axe:
            zones = {}
            if self.uistate.project.checkBox["EPSP_amp"]:
                zones["EPSP amp move"] = p.EPSP_amp_move_zone
            if self.uistate.project.checkBox["EPSP_slope"]:
                zones["EPSP slope resize"] = p.EPSP_slope_resize_zone
                zones["EPSP slope move"] = p.EPSP_slope_move_zone
            if self.uistate.project.checkBox["volley_amp"]:
                zones["volley amp move"] = p.volley_amp_move_zone
            if self.uistate.project.checkBox["volley_slope"]:
                zones["volley slope resize"] = p.volley_slope_resize_zone
                zones["volley slope move"] = p.volley_slope_move_zone
            p.mouseover_action = None
            for action, zone in zones.items():
                if not plot_drag.point_in_zone(x, y, zone):
                    continue
                p.mouseover_action = action
                plotMouseover(action, axe)
                break

            if self.uistate.plot.mouseover_action is None:
                if self.uistate.plot.mouseover_blob is not None:
                    self.uistate.plot.mouseover_blob.set_sizes([0])
                if self.uistate.plot.mouseover_plot is not None:
                    self.uistate.plot.mouseover_plot[0].set_linewidth(0)

            axe.figure.canvas.draw_idle()

    @staticmethod
    def _get_nearest_point(mouse_disp_x, mouse_disp_y, x_array, y_array, transform):
        """Nearest scatter/line sample to the mouse in *display* (screen) space."""
        return plot_drag.nearest_point_index_display(
            mouse_disp_x,
            mouse_disp_y,
            x_array,
            y_array,
            transform,
        )

    def _draw_ghost_sweep(self, snippet_x, snippet_y, label_text):
        if self.uistate.plot.ghost_sweep is None:
            ghost_color = "white" if self.uistate.darkmode else "black"
            (self.uistate.plot.ghost_sweep,) = self.uistate.plot.axe.plot(snippet_x, snippet_y, color=ghost_color, alpha=0.5, zorder=0)
            if self.uistate.plot.ghost_label is None:
                self.uistate.plot.ghost_label = self.uistate.plot.axe.text(
                    1,
                    1,
                    label_text,
                    transform=self.uistate.plot.axe.transAxes,
                    ha="left",
                    va="bottom",
                )
            else:
                self.uistate.plot.ghost_label.set_text(label_text)
        else:
            self.uistate.plot.ghost_sweep.set_data(snippet_x, snippet_y)
            self.uistate.plot.ghost_label.set_text(label_text)

    def _draw_mouseover_blob(self, ax, x, y, color):
        if self.uistate.plot.mouseover_out_blob is None:
            self.uistate.plot.mouseover_out_blob = ax.scatter(x, y, color=color, s=150, alpha=0.8, zorder=10)
        else:
            if self.uistate.plot.mouseover_out_blob.axes != ax:
                self.uistate.plot.mouseover_out_blob.remove()
                self.uistate.plot.mouseover_out_blob = ax.scatter(x, y, color=color, s=150, alpha=0.8, zorder=10)
            else:
                self.uistate.plot.mouseover_out_blob.set_offsets([[x, y]])
                self.uistate.plot.mouseover_out_blob.set_color(color)

    def outputMouseover(self, event):
        handler = self.mouseover_loader()
        if handler:
            handler(event)

    def on_leave_output(self, event):
        self.exorcise()

    def exorcise(self):
        if self.uistate.plot.ghost_sweep is not None:
            self.uistate.plot.ghost_sweep.remove()
            self.uistate.plot.ghost_sweep = None
        if self.uistate.plot.ghost_label is not None:
            self.uistate.plot.ghost_label.remove()
            self.uistate.plot.ghost_label = None
        if self.uistate.plot.mouseover_out_blob is not None:
            try:
                self.uistate.plot.mouseover_out_blob.remove()
            except ValueError:
                pass
            self.uistate.plot.mouseover_out_blob = None
            if self.uistate.plot.ax1 is not None:
                self.uistate.plot.ax1.figure.canvas.draw_idle()
        if self.uistate.plot.axe is not None:
            self.uistate.plot.axe.figure.canvas.draw_idle()

    def connectDragRelease(self, x_range, rec_ID, graph):
        self.usage("connectDragRelease")
        # function to set up x scales for dragging and releasing on mean- and output canvases
        if graph == "mean":  # self.uistate.plot.axm
            canvas = self.canvasMean
        elif graph == "output":  # self.uistate.plot.ax1+ax2
            canvas = self.canvasOutput
        else:
            print("connectDragRelease: Incorrect graph reference.")
            return

        if rec_ID is None:
            # Groups-only output: snap domain is x_range itself (no rec artists).
            x_data = np.asarray(x_range, dtype=float)
            if x_data.size == 0:
                print("No group sweep domain. Cannot set up drag and release.")
                self.uistate.plot.dragging = False
                return
        else:
            candidates = plot_drag.drag_release_line_candidates(
                rec_ID,
                graph,
                dict_rec_show=self.uistate.plot.dict_rec_show,
                dict_rec_labels=self.uistate.plot.dict_rec_labels,
            )
            if not candidates:
                print("No lines found. Cannot set up drag and release.")
                self.uistate.plot.dragging = False
                return
            _max_x_line, x_data = max(candidates, key=lambda item: item[1][-1])
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
        if not self.uistate.plot.dragging:
            return
        if event.xdata is None:
            return
        x = event.xdata  # mouse x position
        if canvas == self.canvasMean:
            x_drag_val = plot_drag.snap_to_nearest_x(x_range, x)
        else:
            x_drag_val = plot_drag.snap_sweep_index(x_range, x)
        if x_drag_val == self.uistate.plot.x_drag_last:  # return if the pointer hasn't moved enough
            return
        self.uistate.plot.x_drag = x_drag_val
        self.uistate.plot.x_drag_last = x_drag_val
        if canvas == self.canvasMean:
            self.uistate.plot.x_select["mean_end"] = self.uistate.plot.x_drag
            self.lineEdit_mean_selection_end.setText(f"{self.uistate.plot.x_drag * 1000:g}")
        else:
            self.uistate.plot.x_select["output_end"] = self.uistate.plot.x_drag
            self.uistate.plot.x_select["output"] = plot_drag.output_sweep_range(
                self.uistate.plot.x_on_click,
                self.uistate.plot.x_drag,
            )
            # print(f"self.uistate.plot.x_select['output']: {self.uistate.plot.x_select['output']}")
        self.uiplot.xSelect(canvas=canvas)

    def drag_released(self, event, canvas):
        self.usage("drag_released")
        is_mean = canvas is self.canvasMean
        is_output = canvas is self.canvasOutput

        # Fallback: if motions did not populate x_drag (possible on some platforms/Wayland),
        # use the release event position (snapped) when it differs from the press point.
        # This prevents drags from being mis-treated as click-only single-sweep selections.
        if self.uistate.plot.x_drag is None and event is not None and event.xdata is not None:
            try:
                if is_output:
                    prow = self.get_prow()
                    cands = None
                    if prow is not None:
                        n = int(prow.get("sweeps", 0))
                        if n > 0:
                            cands = list(range(0, n))
                    elif not self.uistate.plot.list_idx_select_recs:
                        cands = self._groups_output_sweep_domain()
                    if cands:
                        rx = plot_drag.snap_sweep_index(cands, event.xdata)
                        if rx != self.uistate.plot.x_on_click:
                            self.uistate.plot.x_drag = rx
                else:
                    # mean graph: x is time (float)
                    if self.uistate.plot.x_on_click is not None and abs(event.xdata - self.uistate.plot.x_on_click) > 1e-9:
                        self.uistate.plot.x_drag = event.xdata
            except Exception:
                pass

        # Compute final selection state immediately (no heavy artist work yet)
        if self.uistate.plot.x_drag is None:  # click only
            if is_mean:
                self.uistate.plot.x_select["mean_end"] = None
            elif is_output:
                self.uistate.plot.x_select["output_end"] = None
                self.uistate.plot.x_select["output"] = {int(self.uistate.plot.x_on_click)}
        else:  # click and drag
            start, end = sorted((self.uistate.plot.x_on_click, self.uistate.plot.x_drag))
            if is_mean:
                self.uistate.plot.x_select["mean_start"] = start
                self.uistate.plot.x_select["mean_end"] = end
            elif is_output:
                self.uistate.plot.x_select["output_start"] = start
                self.uistate.plot.x_select["output_end"] = end
                self.uistate.plot.x_select["output"] = plot_drag.output_sweep_range(start, end)

        # Set the text fields synchronously for immediate user feedback (lightweight).
        # The more expensive canvas artist work is still deferred.
        if is_mean:
            if self.uistate.plot.x_select.get("mean_end") is None:
                self.lineEdit_mean_selection_end.setText("")
                if self.uistate.plot.x_select.get("mean_start") is not None:
                    self.lineEdit_mean_selection_start.setText(f"{self.uistate.plot.x_select['mean_start'] * 1000:g}")
            else:
                self.lineEdit_mean_selection_start.setText(f"{self.uistate.plot.x_select.get('mean_start', 0) * 1000:g}")
                self.lineEdit_mean_selection_end.setText(f"{self.uistate.plot.x_select.get('mean_end', 0) * 1000:g}")
        elif is_output:
            if self.uistate.plot.x_select.get("output_end") is None:
                self.lineEdit_sweeps_range_to.setText("")
                if self.uistate.plot.x_select.get("output_start") is not None:
                    self.lineEdit_sweeps_range_from.setText(str(self.uistate.plot.x_select["output_start"]))
            else:
                self.lineEdit_sweeps_range_from.setText(str(self.uistate.plot.x_select.get("output_start", "")))
                self.lineEdit_sweeps_range_to.setText(str(self.uistate.plot.x_select.get("output_end", "")))

        # Cleanup event bindings immediately; release the handler fast
        for cid in (self.mouse_drag, self.mouse_release):
            if cid is not None:
                try:
                    canvas.mpl_disconnect(cid)
                except Exception:
                    pass
        self.mouse_drag = None
        self.mouse_release = None
        self.uistate.plot.x_drag = None
        self.uistate.plot.dragging = False

        # Defer only the matplotlib artist changes + draw_idle (update_axe_mean/xSelect).
        # Widget text has already been set above. Doing remove/plot/axv + draw from inside
        # the button_release handler can break the Wayland connection.
        QtCore.QTimer.singleShot(0, lambda c=canvas, m=is_mean, o=is_output: self._finalize_drag_release(c, m, o))

    def _finalize_drag_release(self, canvas, is_mean, is_output):
        """Deferred canvas work only (after texts were set sync in drag_released).
        We still defer the artist mutations + draw_idle for Wayland safety.
        """
        try:
            if is_mean:
                self.uiplot.xSelect(canvas=canvas)
            elif is_output:
                # axe mean of selected sweeps is rec-only
                if self.uistate.plot.list_idx_select_recs:
                    self.uiplot.update_axe_mean()
                self.uiplot.xSelect(canvas=canvas)
        except Exception as ex:
            print(f"_finalize_drag_release error: {ex}")

    def _finalize_deselect(self, canvas):
        """Deferred handler for right-click deselect (artists + stim buttons).
        Text fields were already cleared synchronously for responsiveness.
        """
        try:
            if canvas == self.canvasMean:
                self.uiplot.xDeselect(ax=self.uistate.plot.axm, reset=True)
            else:
                self.uiplot.xDeselect(ax=self.uistate.plot.ax1, reset=True)
            self.update_stim_buttons()
        except Exception as ex:
            print(f"_finalize_deselect error: {ex}")

    def mouseoverUpdate(self):
        self.usage("mouseoverUpdate")
        self.mouseoverDisconnect()
        n_recs = len(self.uistate.plot.list_idx_select_recs or [])
        n_stims = len(self.uistate.plot.list_idx_select_stims or [])
        from brainwash_ui import color_events

        if n_recs == 1:
            self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
            self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
        if self.uistate.plot.list_idx_select_recs and self.uistate.plot.list_idx_select_stims:
            self._update_marker_data()

        if n_recs > 1:
            self.exorcise()
            self.graphRefresh(reeval_formal_test=False)
            return
        if n_recs == 0:
            # No rec → no sweep ghost (group means alone are not a ghost source)
            self.exorcise()
            self.graphRefresh(reeval_formal_test=False)
            return
        # Multi-stim (or none): color-code overlays; no axe event-marker mouseover/drag.
        # Mean (axm) stim pick still works for single-rec multi-stim.
        if not color_events.event_mouseover_enabled(n_recs, n_stims):
            self.mouseoverMean = self.canvasMean.mpl_connect("motion_notify_event", self.meanMouseover)
            self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
            self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
            self.graphRefresh(reeval_formal_test=False)
            return
        prow = self.get_prow()
        if prow is None:
            logger.debug("mouseoverUpdate: prow is None, skip output hover / ghost")
            self.exorcise()
            self.graphRefresh(reeval_formal_test=False)
            return
        rec_ID = prow["ID"]
        trow = self.get_trow()
        if trow is None:
            logger.debug("mouseoverUpdate: trow is None, calling graphRefresh and returning")
            self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
            self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
            self.graphRefresh(reeval_formal_test=False)
            return
        stim_num = trow["stim"]
        self.uistate.setMargins(axe=self.uistate.plot.axe)
        from brainwash_ui import plot_identity as pi

        # Amp also has amp_x/amp_y/amp_zero with aspect=EPSP_amp on axe; only the
        # aspect_marker handle may set the amp move zone (slope has one handle).
        dict_labels = {
            key: value
            for key, value in self.uistate.plot.dict_rec_labels.items()
            if isinstance(value, dict)
            and str(value.get("rec_ID")) == str(rec_ID)
            and pi._stim_equal(value.get("stim"), stim_num)
            and plot_drag.is_axe_aspect_drag_handle(value)
        }

        if not dict_labels:
            self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
            self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
            self.graphRefresh()
            return

        for key, value in dict_labels.items():
            line = value["line"]
            disp = str(value.get("display_label") or key)
            aspect = value.get("aspect")
            if aspect == "EPSP_amp" or disp.endswith("EPSP amp marker"):
                x, y = plot_drag.artist_xy_first(line)
                self.uistate.updatePointDragZone(aspect="EPSP amp move", x=x, y=y)
            elif aspect == "volley_amp" or disp.endswith("volley amp marker"):
                x, y = plot_drag.artist_xy_first(line)
                self.uistate.updatePointDragZone(aspect="volley amp move", x=x, y=y)
            elif aspect == "EPSP_slope" or disp.endswith("EPSP slope marker"):
                self.uistate.updateDragZones(
                    aspect="EPSP slope",
                    x=plot_drag.artist_xdata(line),
                    y=plot_drag.artist_ydata(line),
                )
            elif aspect == "volley_slope" or disp.endswith("volley slope marker"):
                self.uistate.updateDragZones(
                    aspect="volley slope",
                    x=plot_drag.artist_xdata(line),
                    y=plot_drag.artist_ydata(line),
                )

        self.mouseoverMean = self.canvasMean.mpl_connect("motion_notify_event", self.meanMouseover)
        self.mouseoverEvent = self.canvasEvent.mpl_connect("motion_notify_event", self.eventMouseover)
        self.mouseoverOutput = self.canvasOutput.mpl_connect("motion_notify_event", self.outputMouseover)
        self.mouseLeaveOutput = self.canvasOutput.mpl_connect("axes_leave_event", self.on_leave_output)
        # print("mouseoverUpdate calls self.graphRefresh()")
        self.graphRefresh(reeval_formal_test=False)

    def _update_marker_data(self):
        self.usage("_update_marker_data")
        # update xy data of shown markers
        df_p = self.get_df_project()
        precision = self.uistate.project.settings["precision"]

        aspects = [
            ("EPSP_slope", " EPSP slope marker", True),
            ("EPSP_amp", " EPSP amp marker", False),
            ("volley_slope", " volley slope marker", True),
            ("volley_amp", " volley amp marker", False),
        ]

        for aspect_prefix, marker_suffix, is_slope in aspects:
            markers = {
                k: v
                for k, v in self.uistate.plot.dict_rec_show.items()
                if isinstance(v, dict)
                and (
                    v.get("aspect") == aspect_prefix
                    and v.get("role") in ("aspect_marker", None)
                    or str(v.get("display_label") or k).endswith(marker_suffix.strip())
                    or str(k).endswith(marker_suffix)
                )
            }
            for marker in markers.values():
                p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
                dfmean = self.get_dfmean(row=p_row)
                df_t = self.get_dft(row=p_row)
                if df_t is None or (hasattr(df_t, "empty") and df_t.empty):
                    continue
                stim_num = marker["stim"]
                t_match = df_t.loc[df_t["stim"] == stim_num]
                if t_match.empty:
                    continue
                t_row = t_match.squeeze()
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
        # self.usage("mouseoverDisconnect")
        # drop any prior mouseover event connections and plots
        for conn_attr, canvas_attr in (
            ("mouseoverMean", "canvasMean"),
            ("mouseoverEvent", "canvasEvent"),
            ("mouseoverOutput", "canvasOutput"),
            ("mouseLeaveOutput", "canvasOutput"),
        ):
            if hasattr(self, conn_attr):
                cid = getattr(self, conn_attr)
                canvas = getattr(self, canvas_attr, None)
                if cid is not None and canvas is not None:
                    try:
                        canvas.mpl_disconnect(cid)
                    except Exception:
                        pass
                try:
                    delattr(self, conn_attr)
                except AttributeError:
                    setattr(self, conn_attr, None)

        if self.uistate.plot.mouseover_plot is not None:
            try:
                self.uistate.plot.mouseover_plot[0].remove()
            except Exception:
                pass
            self.uistate.plot.mouseover_plot = None
        if self.uistate.plot.mouseover_blob is not None:
            try:
                self.uistate.plot.mouseover_blob.remove()
            except Exception:
                pass
            self.uistate.plot.mouseover_blob = None
        if self.uistate.plot.mouseover_out is not None:
            try:
                self.uistate.plot.mouseover_out[0].remove()
            except Exception:
                pass
            self.uistate.plot.mouseover_out = None
        if self.uistate.plot.mouseover_out_blob is not None:
            try:
                self.uistate.plot.mouseover_out_blob.remove()
            except Exception:
                pass
            self.uistate.plot.mouseover_out_blob = None
        self.uistate.plot.mouseover_action = None

    def eventDragSlope(self, event, action, data_x, data_y, prior_slope_start, prior_slope_end):  # graph dragging event
        # self.usage("eventDragSlope")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None or action is None:
            return
        x = event.xdata
        self.uistate.plot.x_drag = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
        if self.uistate.plot.x_drag == self.uistate.plot.x_drag_last:  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = self.uistate.project.settings["precision"]
        time_diff = self.uistate.plot.x_drag - self.uistate.plot.x_on_click
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
        self.uistate.plot.x_drag_last = self.uistate.plot.x_drag
        # update the mouseover plot
        self.uistate.plot.mouseover_plot[0].set_data([x_start, x_end], [y_start, y_end])
        if blob:
            self.uistate.plot.mouseover_blob.set_offsets([x_end, y_end])
        self.canvasEvent.draw_idle()
        self.eventDragUpdate(x_start, x_end, precision)

    def eventDragPoint(self, event, data_x, data_y, prior_amp):  # maingraph dragging event
        # self.usage("eventDragPoint")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None:
            return
        x = event.xdata
        self.uistate.plot.x_drag = data_x[np.abs(data_x - x).argmin()]  # time-value of the nearest index
        if self.uistate.plot.x_drag == self.uistate.plot.x_drag_last:  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = self.uistate.project.settings["precision"]
        time_diff = self.uistate.plot.x_drag - self.uistate.plot.x_on_click
        x_point = round(prior_amp + time_diff, precision)
        idx = (np.abs(data_x - x_point)).argmin()
        y_point = data_y[idx]
        # print (f"x_point: {x_point}, y_point: {y_point}")
        # remember the last x index
        self.uistate.plot.x_drag_last = self.uistate.plot.x_drag
        # update the mouseover plot
        self.uistate.plot.mouseover_blob.set_offsets([x_point, y_point])
        self.canvasEvent.draw_idle()
        self.eventDragUpdate(x_point, x_point, precision)

    def eventDragUpdate(self, x_start, x_end, precision):
        handler = self.drag_update_loader()
        if handler:
            handler(x_start, x_end, precision)

    def eventDragReleased(self, event, data_x, data_y):
        handler = self.drag_release_loader()
        if handler:
            handler(event, data_x, data_y)

    def _eventDragReleased(self, event, data_x, data_y):  # graph release event
        # TODO: Overhaul this whole magic-string-mess
        self.usage("eventDragReleased")
        if self.uistate.plot.mouseover_action is None:
            self.uistate.plot.dragging = False
            if getattr(self, "mouse_release", None) is not None:
                self.canvasEvent.mpl_disconnect(self.mouse_release)
                self.mouse_release = None
            if getattr(self, "mouse_drag", None) is not None:
                self.canvasEvent.mpl_disconnect(self.mouse_drag)
                self.mouse_drag = None
            self.mouseoverUpdate()
            return
        print(f" - self.uistate.plot.mouseover_action: {self.uistate.plot.mouseover_action}")
        self.canvasEvent.mpl_disconnect(self.mouse_drag)
        self.canvasEvent.mpl_disconnect(self.mouse_release)
        self.uistate.plot.x_drag_last = None
        if self.uistate.plot.x_drag is None or self.uistate.plot.x_drag == self.uistate.plot.x_on_click:  # nothing to update (no movement or same position)
            print("x_drag is None or x_drag == x_on_click")
            self.mouseoverUpdate()
            return

        dft_temp = self.uistate.plot.dft_temp  # copied on clicked, updated while dragging
        stim_idx = self.uistate.plot.list_idx_select_stims[0]
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
                self.uistate.updateDragZones,
            ),
            "EPSP amp move": (
                "t_EPSP_amp_method",
                "EPSP amp",
                {
                    "t_EPSP_amp": trow_temp["t_EPSP_amp"],
                    "t_EPSP_amp_halfwidth": trow_temp["t_EPSP_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                self.uistate.updatePointDragZone,
            ),
            "volley slope": (
                "t_volley_slope_method",
                "volley slope",
                {
                    "t_volley_slope_start": trow_temp["t_volley_slope_start"],
                    "t_volley_slope_end": trow_temp["t_volley_slope_end"],
                },
                self.uistate.updateDragZones,
            ),
            "volley amp move": (
                "t_volley_amp_method",
                "volley amp",
                {
                    "t_volley_amp": trow_temp["t_volley_amp"],
                    "t_volley_amp_halfwidth": trow_temp["t_volley_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                self.uistate.updatePointDragZone,
            ),
        }
        # Build a dict_t of new measuring points and update drag zones
        dict_t_updates = {}
        for action, values in action_mapping.items():
            if self.uistate.plot.mouseover_action.startswith(action):
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
                self.uistate.plot.mouseover_action,
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
        if not self.uistate.project.checkBox["timepoints_per_stim"] and n_stims > 1:
            dft_to_update = self.uistate.plot.dft_temp.copy()
            if method_field in dict_t_updates:
                dft_to_update[method_field] = dict_t_updates[method_field]
        else:
            dft_to_update = self.uistate.plot.dft_temp.iloc[[stim_idx]].copy()
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
            if not self.uistate.project.checkBox["timepoints_per_stim"] and n_stims > 1:
                for s in new_dfoutput["stim"].unique():
                    dft_temp.loc[dft_temp["stim"] == s, "volley_amp_mean"] = new_dfoutput[new_dfoutput["stim"] == s]["volley_amp"].mean()
            else:
                dft_temp.loc[dft_temp.index[stim_idx], "volley_amp_mean"] = new_dfoutput["volley_amp"].mean()
        elif aspect == "volley slope":
            if not self.uistate.project.checkBox["timepoints_per_stim"] and n_stims > 1:
                for s in new_dfoutput["stim"].unique():
                    dft_temp.loc[dft_temp["stim"] == s, "volley_slope_mean"] = new_dfoutput[new_dfoutput["stim"] == s]["volley_slope"].mean()
            else:
                dft_temp.loc[dft_temp.index[stim_idx], "volley_slope_mean"] = new_dfoutput["volley_slope"].mean()

        if self.uistate.project.checkBox["timepoints_per_stim"] or n_stims == 1:
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
        self.uiplot.updateStimLines(rec_name=rec_name, dfoutput=self.V2mV(dfoutput))

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

        self.uiplot.update(
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
            if pd.isna(rec_filter) or not rec_filter or rec_filter == "none":
                rec_filter = "voltage"
            display_name = plot_identity.display_recording_name(
                prow["ID"],
                prow["recording_name"],
                blind=bool(getattr(self.uistate.project, "blind_recordings", False)),
                aliases=getattr(self.uistate.project, "blind_aliases", None),
            )
            stem = plot_series.recording_plot_label(display_name, rec_filter)
            labelbase = f"{stem} - stim {trow['stim']}"
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

            self.uiplot.updateAmpMarker(
                labelamp,
                x,
                y,
                amp_x,
                amp_zero_plot,
                amp=amp,
                rec_ID=prow["ID"],
                stim=trow["stim"],
                aspect_field=column_name,
            )

        if aspect in ["EPSP amp", "volley amp"]:
            # print(f" - {aspect} updated")
            if self.uistate.project.checkBox["timepoints_per_stim"]:
                update_amp_marker(trow, aspect, prow, dfmean, dfoutput)
            else:
                dft = self.get_dft(prow)
                for i, i_trow in dft.iterrows():
                    update_amp_marker(i_trow, aspect, prow, dfmean, dfoutput)

        # update groups
        affected_groups = self.get_groupsOfRec(prow["ID"])
        self.group_cache_purge(affected_groups)  # all levels (data/settings change invalidates all)

        # We MUST run update_show BEFORE rebuilding the groups so that
        # the dict_rec_labels (which dict_group_show relies on for PPR data gathering)
        # matches the visible state expectations.
        self.mouseoverUpdate()
        self.update_show()

        for group_ID in affected_groups:
            self.clear_group_level(group_ID)  # all levels stale after rec edit
            level = self.uistate.stat_test.buttonGroup_test_n
            df_groupmean = self.get_dfgroupmean(group_ID, level=level)
            x_pos = plot_series.pp_group_x_position(self.dd_groups, group_ID)
            self.uiplot.addGroup(group_ID, self.dd_groups[group_ID], self.V2mV(df_groupmean), x_pos=x_pos, level=level)

        self.update_show()  # Re-apply visibility rules to the newly added group artists
        # Group membership change can affect formal test results; clear cached so safeguard won't redraw stale
        if hasattr(self, "clear_formal_test_results"):
            self.clear_formal_test_results()
        self.graphRefresh()  # Refresh the canvas to draw the new groups
        self.update_amp_lineEdits()
        self.update_slope_lineEdits()
        self.zoomAuto(skip_axe=True)

        if self.config.talkback:
            self.talkback()

    # --- Phase 3: Loaders (Dispatchers) ---

    def mouseover_loader(self):
        experiment_type = self.uistate.experiment.experiment_type
        if experiment_type == "io":
            return self._mouseover_output_io
        elif experiment_type == "PP":
            return self._mouseover_output_pp
        elif self.uistate.x_axis == "stim":
            return self._mouseover_output_stim
        else:
            return self._mouseover_output_time

    def drag_update_loader(self):
        experiment_type = self.uistate.experiment.experiment_type
        if experiment_type == "io":
            return self._drag_update_io
        elif experiment_type == "PP":
            return self._drag_update_pp
        elif self.uistate.x_axis == "stim":
            return self._drag_update_time
        else:
            return self._drag_update_time

    def drag_release_loader(self):
        experiment_type = self.uistate.experiment.experiment_type
        if experiment_type == "io":
            return self._drag_release_io
        elif experiment_type == "PP":
            return self._drag_release_pp
        elif self.uistate.x_axis == "stim":
            return self._drag_release_time
        else:
            return self._drag_release_time

    # --- Phase 2: Specialized Mouseover Strategies ---

    def _mouseover_output_time(self, event):
        if event.inaxes == self.uistate.plot.ax1:
            str_ax = 'ax1'
        elif event.inaxes == self.uistate.plot.ax2:
            str_ax = 'ax2'
        else:
            str_ax = None
        ax = self.uiplot.get_axis(str_ax) if str_ax else None
        if event.inaxes not in (self.uistate.plot.ax1, self.uistate.plot.ax2) or str_ax is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        if event.inaxes != ax:
            x, y = ax.transData.inverted().transform((event.x, event.y))
        else:
            x, y = event.xdata, event.ydata
        if x is None or y is None or not (self.uistate.slopeView() or self.uistate.ampView()):
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        n_recs = len(self.uistate.plot.list_idx_select_recs or [])
        if n_recs != 1:
            # Ghost is a per-recording voltage snippet; multi-rec / no-rec: never draw it.
            # (Group-mean hover previously synthesized a ghost from the first rec in the group
            # when EPSP_slope/ax2 was hovered — incorrect with no rec selected.)
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return

        prow = self.get_prow()
        rec_id = prow["ID"] if prow is not None else None
        if rec_id is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return

        # Prefer the hovered ax's per-sweep line (correct stim/offset), fallback to any ax
        dict_out = {
            key: value
            for key, value in self.uistate.plot.dict_rec_show.items()
            if value.get("rec_ID") == rec_id and value.get("axis") == str_ax and (value.get("aspect") in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]) and hasattr(value.get("line"), "get_xdata")
        }
        if not dict_out:
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if value.get("rec_ID") == rec_id and value.get("axis") in ("ax1", "ax2") and (value.get("aspect") in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]) and hasattr(value.get("line"), "get_xdata")
            }
        if not dict_out:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        dict_pop = list(dict_out.values())[0]
        rec_ID_for_snippet = dict_pop.get("rec_ID")

        x_data = plot_drag.artist_xdata(dict_pop["line"])
        y_data = plot_drag.artist_ydata(dict_pop["line"])

        out_x_idx = int(np.nanargmin(np.abs(x_data - x)))
        x_val = x_data[out_x_idx]
        out_x_val = x_val
        out_y_val = y_data[out_x_idx]

        if out_x_idx == self.uistate.plot.last_out_x_idx:
            return

        rec_ID = rec_ID_for_snippet
        df_p = self.get_df_project()
        p_row_df = df_p[df_p["ID"] == rec_ID]
        if p_row_df.empty:
            return
        p_row = p_row_df.iloc[0]
        df_t = self.get_dft(p_row)
        if df_t is None or (hasattr(df_t, "empty") and df_t.empty):
            return
        rec_filter = p_row["filter"]

        stim = dict_pop.get("stim")
        if stim is None:
            stim = 1

        t_match = df_t[df_t["stim"] == stim]
        if t_match.empty:
            return
        t_row = t_match.iloc[0]
        offset = t_row["t_stim"]

        bin_size = p_row.get("bin_size")
        if pd.notna(bin_size):
            dfsource = self.get_dfbin(p_row)
            ghost_label_text = f"bin {int(x_val)}"
        else:
            dfsource = self.get_dffilter(p_row)
            ghost_label_text = f"sweep {int(x_val)}"

        if dfsource is None or (hasattr(dfsource, "empty") and dfsource.empty):
            return
        dfsweep = dfsource[dfsource["sweep"] == x_val]
        if dfsweep.empty:
            return
        snippet_x = dfsweep["time"] - offset
        snippet_y = dfsweep[rec_filter]
        if getattr(snippet_x, "empty", False) or len(snippet_x) == 0:
            return

        if self.uistate.plot.mouseover_out_blob is not None:
            try:
                self.uistate.plot.mouseover_out_blob.remove()
            except ValueError:
                pass
            self.uistate.plot.mouseover_out_blob = None

        self._draw_ghost_sweep(snippet_x, snippet_y, ghost_label_text)
        self.uistate.plot.axe.figure.canvas.draw_idle()
        self.uistate.plot.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw_idle()


    def _mouseover_output_stim(self, event):
        str_ax = "ax2" if self.uistate.slopeView() else "ax1" if self.uistate.ampView() else None
        ax = self.uiplot.get_axis(str_ax) if str_ax else None
        if event.inaxes not in (self.uistate.plot.ax1, self.uistate.plot.ax2) or str_ax is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        if event.inaxes != ax:
            x, y = ax.transData.inverted().transform((event.x, event.y))
        else:
            x, y = event.xdata, event.ydata
        if x is None or y is None or not (self.uistate.slopeView() or self.uistate.ampView()):
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        n_recs = len(self.uistate.plot.list_idx_select_recs or [])
        if n_recs > 1:
            self.exorcise()
            return

        if n_recs == 1:
            prow = self.get_prow()
            rec_id = prow["ID"] if prow is not None else None
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if rec_id is not None and value.get("rec_ID") == rec_id and value.get("axis") == str_ax and not str(value.get("aspect", "")).endswith("_mean") and hasattr(value.get("line"), "get_xdata")
            }
        else:
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if value.get("axis") == str_ax and (value.get("aspect") in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]) and hasattr(value.get("line"), "get_xdata")
            }
        if not dict_out:
            return

        dict_pop = list(dict_out.values())[0]
        x_data = plot_drag.artist_xdata(dict_pop["line"])
        y_data = plot_drag.artist_ydata(dict_pop["line"])

        out_x_idx = int(np.nanargmin(np.abs(x_data - x)))
        x_val = x_data[out_x_idx]

        if out_x_idx == self.uistate.plot.last_out_x_idx:
            return

        rec_ID = dict_pop["rec_ID"]
        df_p = self.get_df_project()
        p_row_df = df_p[df_p["ID"] == rec_ID]
        if p_row_df.empty:

            return
        p_row = p_row_df.iloc[0]
        df_t = self.get_dft(p_row)
        rec_filter = p_row["filter"]
        settings = self.uistate.project.settings

        stim_num = int(x_val)
        matching = df_t[df_t["stim"] == stim_num]
        if matching.empty:
            return
        t_row = matching.iloc[0]
        t_stim = t_row["t_stim"]

        dfmean = self.get_dfmean(row=p_row)
        window_start = t_stim + settings["event_start"]
        window_end = t_stim + settings["event_end"]
        snippet = dfmean[(dfmean["time"] >= window_start) & (dfmean["time"] <= window_end)].copy()
        snippet_x = snippet["time"] - t_stim
        snippet_y = snippet[rec_filter]
        ghost_label_text = f"stim {stim_num}"

        if self.uistate.plot.mouseover_out_blob is not None:
            try:
                self.uistate.plot.mouseover_out_blob.remove()
            except ValueError:
                pass
            self.uistate.plot.mouseover_out_blob = None

        self._draw_ghost_sweep(snippet_x, snippet_y, ghost_label_text)
        self.uistate.plot.axe.figure.canvas.draw_idle()
        self.uistate.plot.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw_idle()

    def _mouseover_output_pp(self, event):
        str_ax = "ax2" if self.uistate.slopeView() else "ax1" if self.uistate.ampView() else None
        ax = self.uiplot.get_axis(str_ax) if str_ax else None
        if event.inaxes not in (self.uistate.plot.ax1, self.uistate.plot.ax2) or str_ax is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        if event.inaxes != ax:
            x, y = ax.transData.inverted().transform((event.x, event.y))
        else:
            x, y = event.xdata, event.ydata
        if x is None or y is None or not (self.uistate.slopeView() or self.uistate.ampView()):
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        n_recs = len(self.uistate.plot.list_idx_select_recs or [])
        if n_recs > 1:
            self.exorcise()
            return

        if n_recs == 1:
            prow = self.get_prow()
            rec_id = prow["ID"] if prow is not None else None
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if rec_id is not None and value.get("rec_ID") == rec_id and value.get("axis") == str_ax and not str(value.get("aspect", "")).endswith("_mean") and hasattr(value.get("line"), "get_xdata")
            }
        else:
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if value.get("axis") == str_ax and (value.get("aspect") in ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]) and hasattr(value.get("line"), "get_xdata")
            }
        if not dict_out:
            return

        dict_pop = list(dict_out.values())[0]
        x_data = plot_drag.artist_xdata(dict_pop["line"])
        y_data = plot_drag.artist_ydata(dict_pop["line"])

        # Screen-space nearest (event.x/y are display coords; not data-range fractions).
        out_x_idx = self._get_nearest_point(event.x, event.y, x_data, y_data, ax.transData)
        if out_x_idx is None:
            return

        x_val = x_data[out_x_idx]
        out_x_val = x_val
        out_y_val = y_data[out_x_idx]

        rec_ID = dict_pop["rec_ID"]
        df_p = self.get_df_project()
        p_row_df = df_p[df_p["ID"] == rec_ID]
        if p_row_df.empty:

            return
        p_row = p_row_df.iloc[0]

        dfoutput = self.get_dfdiff(row=p_row) if self.uistate.project.checkBox.get("paired_stims", False) else self.get_dfoutput(row=p_row)
        out_sweeps = dfoutput[dfoutput["sweep"].notna()]
        out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
        out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
        common_sweeps = out1.index.intersection(out2.index).dropna()
        if len(common_sweeps) > 0:
            safe_idx = min(out_x_idx, len(common_sweeps) - 1)
            x_val = common_sweeps[safe_idx]

        if out_x_idx == self.uistate.plot.last_out_x_idx:
            return

        df_t = self.get_dft(p_row)
        rec_filter = p_row["filter"]

        stim = dict_pop.get("stim")
        if stim is None:
            stim = 1

        t_row = df_t[df_t["stim"] == stim].iloc[0]
        offset = t_row["t_stim"]

        if pd.notna(p_row["bin_size"]):
            dfsource = self.get_dfbin(p_row)
            ghost_label_text = f"bin {int(x_val)}"
        else:
            dfsource = self.get_dffilter(p_row)
            ghost_label_text = f"sweep {int(x_val)}"

        dfsweep = dfsource[dfsource["sweep"] == x_val]
        snippet_x = dfsweep["time"] - offset
        snippet_y = dfsweep[rec_filter]

        aspect = dict_pop.get("aspect", "EPSP_amp")
        highlight_color = self.uistate.project.settings.get(f"rgb_{aspect}", "red")

        self._draw_mouseover_blob(ax, out_x_val, out_y_val, highlight_color)
        self._draw_ghost_sweep(snippet_x, snippet_y, ghost_label_text)
        self.uistate.plot.axe.figure.canvas.draw_idle()
        self.uistate.plot.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw_idle()

    def _mouseover_output_io(self, event):
        str_ax = "ax1"
        ax = self.uiplot.get_axis(str_ax) if str_ax else None
        if event.inaxes not in (self.uistate.plot.ax1, self.uistate.plot.ax2) or str_ax is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        if event.inaxes != ax:
            x, y = ax.transData.inverted().transform((event.x, event.y))
        else:
            x, y = event.xdata, event.ydata
        if x is None or y is None:
            if self.uistate.plot.ghost_sweep is not None:
                self.exorcise()
            return
        n_recs = len(self.uistate.plot.list_idx_select_recs or [])
        if n_recs > 1:
            self.exorcise()
            return

        if n_recs == 1:
            prow = self.get_prow()
            rec_id = prow["ID"] if prow is not None else None
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if rec_id is not None and value.get("rec_ID") == rec_id and value["axis"] == str_ax and value.get("x_mode") == "io" and hasattr(value["line"], "get_offsets")
            }
        else:
            dict_out = {
                key: value
                for key, value in self.uistate.plot.dict_rec_show.items()
                if value["axis"] == str_ax and value.get("x_mode") == "io" and hasattr(value["line"], "get_offsets")
            }
        if not dict_out:
            return

        dict_pop = list(dict_out.values())[0]
        rec_ID = dict_pop["rec_ID"]
        df_p = self.get_df_project()
        p_row_df = df_p[df_p["ID"] == rec_ID]
        if p_row_df.empty:

            return
        p_row = p_row_df.iloc[0]

        dfoutput = self.get_dfdiff(row=p_row) if self.uistate.project.checkBox["paired_stims"] else self.get_dfoutput(row=p_row)
        dfoutput = self.V2mV(dfoutput)
        df_sweeps = dfoutput[dfoutput["sweep"].notna()].reset_index(drop=True)
        io_input = self.uistate.experiment.io_input
        io_output = self.uistate.experiment.io_output
        x_col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim_intensity"}.get(io_input, "volley_amp")
        y_col = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")

        if x_col not in df_sweeps.columns or y_col not in df_sweeps.columns:
            return

        df_sweeps = df_sweeps.dropna(subset=[x_col, y_col]).reset_index(drop=True)

        x_array = df_sweeps[x_col].values.astype(float)
        y_array = df_sweeps[y_col].values.astype(float)

        # Screen-space nearest: equal weight per pixel (wide axes no longer over-weight Y).
        out_x_idx = self._get_nearest_point(event.x, event.y, x_array, y_array, ax.transData)
        if out_x_idx is None:
            return

        x_val = df_sweeps["sweep"].iloc[out_x_idx]
        out_x_val = x_array[out_x_idx]
        out_y_val = y_array[out_x_idx]

        if out_x_idx == self.uistate.plot.last_out_x_idx:
            return

        df_t = self.get_dft(p_row)
        rec_filter = p_row["filter"]
        stim = df_sweeps["stim"].iloc[out_x_idx]

        t_row = df_t[df_t["stim"] == stim].iloc[0]
        offset = t_row["t_stim"]

        if pd.notna(p_row["bin_size"]):
            dfsource = self.get_dfbin(p_row)
            ghost_label_text = f"bin {int(x_val)}"
        else:
            dfsource = self.get_dffilter(p_row)
            ghost_label_text = f"sweep {int(x_val)}"

        dfsweep = dfsource[dfsource["sweep"] == x_val]
        snippet_x = dfsweep["time"] - offset
        snippet_y = dfsweep[rec_filter]

        aspect = dict_pop.get("aspect", "EPSP_amp")
        highlight_color = self.uistate.project.settings.get(f"rgb_{aspect}", "red")

        self._draw_mouseover_blob(ax, out_x_val, out_y_val, highlight_color)
        self._draw_ghost_sweep(snippet_x, snippet_y, ghost_label_text)
        self.uistate.plot.axe.figure.canvas.draw_idle()
        self.uistate.plot.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw_idle()

    # --- Phase 2: Specialized Drag Update Strategies ---

    def _update_dft_temp_from_drag(self, x_start, x_end, precision, *, propagate_linked_stims: bool) -> bool:
        """Update dft_temp while dragging on the event plot."""
        action = self.uistate.plot.mouseover_action
        if action is None:
            return False
        aspect = "_".join(action.split()[:2])
        stim_idx = self.uistate.plot.list_idx_select_stims[0]
        prow = self.get_prow()
        if prow is None:
            return False
        n_stims = prow["stims"]
        dft_temp = self.uistate.plot.dft_temp
        stim_offset = dft_temp.at[stim_idx, "t_stim"]
        dict_t: dict = {}

        if aspect in ["EPSP_slope", "volley_slope"]:
            slope_width = round(x_end - x_start, precision)
            dict_t = {
                f"t_{aspect}_start": round(x_start + stim_offset, precision),
                f"t_{aspect}_end": round(x_end + stim_offset, precision),
                f"t_{aspect}_width": round(slope_width, precision),
            }
        elif aspect in ["EPSP_amp", "volley_amp"]:
            dict_t = {
                "t_stim": stim_offset,
                f"t_{aspect}": round(x_start + stim_offset, precision),
            }
        else:
            return False

        for key, value in dict_t.items():
            dft_temp.at[stim_idx, key] = value
            if propagate_linked_stims and not self.uistate.project.checkBox["timepoints_per_stim"] and n_stims > 1:
                offset = dft_temp.at[stim_idx, "t_stim"] - dft_temp.at[stim_idx, key]
                for i, i_trow in dft_temp.iterrows():
                    dft_temp.at[i, key] = round(i_trow["t_stim"] - offset, precision)
        return True

    def _set_mouseover_out_preview(self, axis, drag_x, drag_y, *, color, linestyle, marker_style, msize):
        """Thick overlay of the selected recording's output while dragging (never group)."""
        if axis is None:
            return
        if self.uistate.plot.mouseover_out is None:
            self.uistate.plot.mouseover_out = axis.plot(
                drag_x,
                drag_y,
                color=color,
                linewidth=3,
                linestyle=linestyle,
                marker=marker_style,
                markersize=msize,
                zorder=5,
            )
        else:
            line = self.uistate.plot.mouseover_out[0]
            if getattr(line, "axes", None) != axis:
                try:
                    line.remove()
                except Exception:
                    pass
                self.uistate.plot.mouseover_out = axis.plot(
                    drag_x,
                    drag_y,
                    color=color,
                    linewidth=3,
                    linestyle=linestyle,
                    marker=marker_style,
                    markersize=msize,
                    zorder=5,
                )
            else:
                line.set_data(drag_x, drag_y)
                line.set_marker(marker_style)
                line.set_linestyle(linestyle)
                line.set_color(color)
                line.set_markersize(msize)
        self.canvasOutput.draw_idle()

    def _preview_rec_output_while_dragging(self, *, mode: str) -> None:
        """Live morph of the *selected recording* output series (not group means).

        Restored after the UI-refactor deferral of build_dfoutput to release only;
        group artists still update on drag release only.

        Gated by project.checkBox['aspect_preview'] (default True). When off,
        drag still updates dft_temp and the axe chrome; output recomputes on release.
        """
        if not self.uistate.project.checkBox.get("aspect_preview", True):
            return
        action = self.uistate.plot.mouseover_action
        if action is None:
            return
        aspect = "_".join(action.split()[:2])  # EPSP_amp / EPSP_slope / volley_*
        stim_idx = self.uistate.plot.list_idx_select_stims[0]
        prow = self.get_prow()
        if prow is None:
            return
        n_stims = prow["stims"]
        dft_temp = self.uistate.plot.dft_temp
        trow_temp = dft_temp.iloc[stim_idx]

        if not self.uistate.project.checkBox["timepoints_per_stim"] and n_stims > 1:
            dft_to_update = dft_temp.copy()
        else:
            dft_to_update = dft_temp.iloc[[stim_idx]].copy()

        # Ensure measure_waveform / build_dfoutput has required fields
        for col in (
            "t_EPSP_amp_halfwidth",
            "t_volley_amp_halfwidth",
            "norm_output_from",
            "norm_output_to",
            "stim",
            "amp_zero",
            "t_stim",
        ):
            if col in trow_temp.index and col not in dft_to_update.columns:
                dft_to_update[col] = trow_temp[col]

        rec_filter = prow.get("filter")
        if pd.isna(rec_filter) or not rec_filter or rec_filter == "none":
            rec_filter = "voltage"

        if pd.notna(prow.get("bin_size")):
            dffilter = self.get_dfbin(prow)
        else:
            dffilter = self.get_dffilter(row=prow)

        # Axis / series for this aspect
        if aspect in ("EPSP_slope", "volley_slope"):
            axis = self.uistate.plot.ax2
        else:
            axis = self.uistate.plot.ax1

        color = self.uistate.project.settings.get(f"rgb_{aspect}", "black")
        msize = 6

        try:
            if mode == "time" and self.uistate.x_axis == "stim" and len(getattr(self.uistate.plot, "df_rec_select_time", []) or []) > 1:
                # Stim-mode aggregate: single point per stim from mean waveform
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
                val = measured.get(aspect, np.nan)
                # measure_waveform returns SI amp; output graph uses mV for amp columns
                if aspect in ("EPSP_amp", "volley_amp") and val is not None and val == val:
                    val = float(val) * 1000.0
                drag_y = np.array([val])
                marker_style, linestyle = "o", "None"
            elif mode == "pp":
                out = analysis.build_dfoutput(
                    dffilter=dffilter,
                    dfmean=self.get_dfmean(row=prow),
                    dft=dft_to_update,
                    quick=True,
                    filter=rec_filter,
                )
                out = self.V2mV(out)
                out_sweeps = out[out["sweep"].notna()]
                out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
                out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
                common_sweeps = out1.index.intersection(out2.index).dropna()
                if not common_sweeps.empty and aspect in out1.columns:
                    o1 = out1.loc[common_sweeps]
                    o2 = out2.loc[common_sweeps]
                    v1 = o1[aspect].values.astype(float)
                    v2 = o2[aspect].values.astype(float)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        ppr = plot_series.compute_ppr(v1, v2)
                    x_val = plot_series.pp_overlay_x_map(self.uistate.project.checkBox).get(aspect, 1)
                    drag_x = np.full(len(common_sweeps), x_val)
                    drag_y = ppr
                    marker_style, linestyle = "o", "None"
                else:
                    if aspect in ("EPSP_amp", "EPSP_slope"):
                        outkey = f"{aspect}_norm" if self.uistate.project.checkBox["norm_EPSP"] else aspect
                    else:
                        outkey = aspect
                    if outkey not in out.columns:
                        return
                    drag_x = out["sweep"].values
                    drag_y = out[outkey].values
                    marker_style = "o" if len(drag_x) == 1 else "None"
                    linestyle = "-"
            elif mode == "io":
                out = analysis.build_dfoutput(
                    dffilter=dffilter,
                    dfmean=self.get_dfmean(row=prow),
                    dft=dft_to_update,
                    quick=True,
                    filter=rec_filter,
                )
                out = self.V2mV(out)
                io_input = self.uistate.experiment.io_input
                io_output = self.uistate.experiment.io_output
                x_col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(io_input, "volley_amp")
                y_col = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")
                out_sweeps = out[out["sweep"].notna()].dropna(subset=[x_col, y_col])
                drag_x = out_sweeps[x_col].values
                drag_y = out_sweeps[y_col].values
                marker_style, linestyle = "o", "None"
                color = self.uistate.project.settings.get(f"rgb_{y_col}", "black")
                msize = 10
                axis = self.uistate.plot.ax1
            else:
                # default time / train: per-sweep series for this recording
                out = analysis.build_dfoutput(
                    dffilter=dffilter,
                    dfmean=self.get_dfmean(row=prow),
                    dft=dft_to_update,
                    quick=True,
                    filter=rec_filter,
                )
                out = self.V2mV(out)
                if aspect in ("EPSP_amp", "EPSP_slope"):
                    outkey = f"{aspect}_norm" if self.uistate.project.checkBox["norm_EPSP"] else aspect
                else:
                    outkey = aspect
                if outkey not in out.columns:
                    return
                # Sweep-mode rows only for the series morph
                out_sw = out[out["sweep"].notna()] if "sweep" in out.columns else out
                drag_x = out_sw["sweep"].values if "sweep" in out_sw.columns else np.arange(len(out_sw))
                drag_y = out_sw[outkey].values
                marker_style = "o" if len(drag_x) == 1 else "None"
                linestyle = "-"
        except Exception as exc:
            logger.debug("live drag preview failed: %s", exc)
            return

        self._set_mouseover_out_preview(
            axis,
            drag_x,
            drag_y,
            color=color,
            linestyle=linestyle,
            marker_style=marker_style,
            msize=msize,
        )

    def _drag_update_time(self, x_start, x_end, precision):
        if not self._update_dft_temp_from_drag(x_start, x_end, precision, propagate_linked_stims=True):
            return
        self._preview_rec_output_while_dragging(mode="time")

    def _drag_update_pp(self, x_start, x_end, precision):
        if not self._update_dft_temp_from_drag(x_start, x_end, precision, propagate_linked_stims=True):
            return
        self._preview_rec_output_while_dragging(mode="pp")

    def _drag_update_io(self, x_start, x_end, precision):
        if not self._update_dft_temp_from_drag(x_start, x_end, precision, propagate_linked_stims=False):
            return
        self._preview_rec_output_while_dragging(mode="io")

    # --- Phase 2: Specialized Drag Release Strategies ---

    def _drag_release_time(self, event, data_x, data_y):
        return self._eventDragReleased(event, data_x, data_y)

    def _drag_release_pp(self, event, data_x, data_y):
        return self._eventDragReleased(event, data_x, data_y)

    def _drag_release_io(self, event, data_x, data_y):
        return self._eventDragReleased(event, data_x, data_y)

    def zoomOnScroll(self, event, graph):
        if graph == "mean":
            canvas = self.canvasMean
            ax = self.uistate.plot.axm
        elif graph == "event":
            canvas = self.canvasEvent
            ax = self.uistate.plot.axe
        elif graph == "output":
            canvas = self.canvasOutput
            slope_left = self.uistate.slopeOnly()
            ax = self.uistate.plot.ax2
            ax1 = self.uistate.plot.ax1

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
        ymin0 = self.uistate.project.checkBox["output_ymin0"]
        if on_x:  # check this first; x takes precedence
            ax.set_xlim(x - (x - ax.get_xlim()[0]) / zoom, x + (ax.get_xlim()[1] - x) / zoom)
        elif "slope_left" in locals():  # on output
            if on_left:
                if slope_left:  # scroll left y zoom output slope y
                    ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: self.uistate.project.checkBox...
                    ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
                else:  # scroll left y to zoom output amp y
                    ymin = 0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom  # TODO: self.uistate.project.checkBox...
                    ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
            elif on_right and not slope_left:  # scroll right y to zoom output slope y
                ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: self.uistate.project.checkBox...
                ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
            else:  # default, scroll graph to zoom all
                ax1.set_xlim(
                    x - (x - ax1.get_xlim()[0]) / zoom,
                    x + (ax1.get_xlim()[1] - x) / zoom,
                )
                ymin = 0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom  # TODO: self.uistate.project.checkBox...
                ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
                ymin = 0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom  # TODO: self.uistate.project.checkBox...
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

        canvas.draw_idle()

        # After zooming, the pixel→data scale has changed, so the
        # mouseover detection zones must be recalculated against the new limits.
        if graph == "event":
            self._recalc_axe_drag_zones()
        elif graph == "mean":
            self._recalc_axm_detection_zones()
