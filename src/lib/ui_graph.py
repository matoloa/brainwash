# ui_graph.py
# GraphCoordinatorMixin — graph setup, refresh, preload, groups, update, zoom helpers
# extracted from UIsub (Phase 2 of ui mixin extraction plan).
#
# Module-level singletons are injected by ui.py (same pattern as other mixins):
#
#   import ui_graph
#   ui_graph.uistate = uistate
#   ui_graph.config  = config
#   ui_graph.uiplot  = uiplot

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd
from PyQt5 import QtWidgets

import matplotlib.collections as mcoll

import ui_plot
import ui_widgets  # for MplCanvas, graphPreloadThread, ProgressBarManager

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class GraphCoordinatorMixin:
    """Mixin that provides graph coordination, preload, groups, update, and zoom logic.

    Host requirements:
        - self.dd_groups, self.get_ddgroup_sample, self.group_get_dd, self.testset_get_dd
        - self.get_df_project(), self.get_dfmean(), self.get_dft(), self.get_dffilter(), self.get_dfoutput(), self.get_dfdiff(), self.V2mV()
        - self.get_dfgroupmean(), self.graphGroups (calls uiplot)
        - self.uiFreeze, self.uiThaw, self.update_test, self.update_show, self.setButtonParse
        - self.mouseoverDisconnect, self.mouseoverUpdate, self._cleanup_threads, self._threads
        - self.progressBar, self.progressBarManager (ui_widgets)
        - self.graphClicked, self.zoomOnScroll
        - self.refreshHierarchyLineEdits, self.update_amp_lineEdits, self.update_slope_lineEdits
        - uistate.ax*, uistate.zoom, uistate.settings, uistate.checkBox, etc.
        - uiplot.graphRefresh, uiplot.addGroup, uiplot.addRow, uiplot.clear_sample_artists
        - ui_widgets.graphPreloadThread, ui_widgets.ProgressBarManager, ui_widgets.MplCanvas
    """

    def graphRefresh(self, reeval_formal_test: bool = True):
        self.usage("graphRefresh")
        dd_groups = self.group_get_dd()
        dd_testset = self.testset_get_dd()
        dd_shown_samples = {}

        if hasattr(self, "dd_group_samples"):
            self.dd_group_samples = {}
        if hasattr(uiplot, "uistate"):
            uiplot.uistate.sample_dirty = True
        if hasattr(uiplot, "clear_sample_artists"):
            uiplot.clear_sample_artists(draw=False)

        # First check if ANY test set has show == True
        any_test_shown = any(t.get("show", False) is True or str(t.get("show", False)).lower() in ("true", "1", "t") for t in dd_testset.values())

        if not any_test_shown:
            # uiplot.graphRefresh will always need dd_groups; no testsets → pass only that
            uiplot.graphRefresh(dd_groups=dd_groups, dd_testset=dd_testset, dd_shown_samples=dd_shown_samples)
            if reeval_formal_test:
                # Re-evaluate any active formal test + statusbar (single entry point)
                self.update_test()
            return

        # Any test is shown → we will pass dd_testset as second argument.
        # Check if any group is shown (accounting for legacy string "True" artefact). TODO: Address legacy string issue
        any_group_shown = any(g.get("show") in (True, "True", "true", 1, "1") for g in dd_groups.values())

        if any_group_shown:
            # Check if any shown group has samples to display. If not, skip building and passing dd_shown_samples
            has_shown_sample = any(g.get("sample") is not None for g in dd_groups.values() if g.get("show") in (True, "True", "true", 1, "1"))
            if not has_shown_sample:
                uiplot.graphRefresh(dd_groups=dd_groups, dd_testset=dd_testset, dd_shown_samples=dd_shown_samples)
                if reeval_formal_test:
                    # Re-evaluate any active formal test + statusbar (single entry point)
                    self.update_test()
                return

            # Build dd_shown_samples = {group_ID: inner_dict_from_get_ddgroup_sample}
            # (only for groups that are both shown *and* have a sample)
            dd_shown_samples = {}
            for group_ID, gdict in dd_groups.items():
                if gdict.get("show") in (True, "True", "true", 1, "1") and gdict.get("sample") is not None:
                    inner = self.get_ddgroup_sample(group_ID)
                    if inner:
                        dd_shown_samples[group_ID] = inner

            uiplot.graphRefresh(
                dd_groups=dd_groups,
                dd_testset=dd_testset,
                dd_shown_samples=dd_shown_samples,
            )
        else:
            uiplot.graphRefresh(dd_groups=dd_groups, dd_testset=dd_testset, dd_shown_samples=dd_shown_samples)

        if reeval_formal_test:
            # Re-evaluate any active formal test + statusbar after draw (single entry point)
            # This does not affect the independent Heatmap (H) path.
            self.update_test()

    def graphWipe(self):  # removes all plots from canvasEvent and canvasOutput
        self.exorcise()
        uistate.dict_rec_labels = {}
        uistate.dict_rec_show = {}
        uistate.dict_group_labels = {}
        uistate.dict_group_show = {}
        if hasattr(self, "canvasMean"):
            self.canvasMean.figure.legends.clear()
            self.canvasMean.axes.cla()
            self.canvasMean.draw_idle()
        if hasattr(self, "canvasEvent"):
            self.canvasEvent.figure.legends.clear()
            self.canvasEvent.axes.cla()
            self.canvasEvent.draw_idle()
        if hasattr(self, "canvasOutput"):
            for ax in self.canvasOutput.figure.axes:
                ax.cla()
                ax.legend_ = None
            self.canvasOutput.draw_idle()

    def graphAxes(self):  # plot selected row(s), or clear graph if empty
        print("graphAxes")
        uistate.axm = self.canvasMean.axes
        uistate.axe = self.canvasEvent.axes
        ax1 = self.canvasOutput.axes
        if uistate.ax2 is not None and hasattr(uistate, "ax2"):  # remove ax2 if it exists
            uistate.ax2.remove()
        ax2 = ax1.twinx()
        uistate.ax2 = ax2  # Store the ax2 instance
        uistate.ax1 = ax1
        # connect scroll event if not already connected #TODO: when graphAxes is called only once, the check should be redundant
        if not hasattr(self, "scroll_event_connected") or not self.scroll_event_connected:
            self.canvasMean.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="mean"),
            )
            self.canvasEvent.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="event"),
            )
            self.canvasOutput.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="output"),
            )
            self.scroll_event_connected = True
        df_p = self.get_df_project()
        if df_p.empty:
            return
        self.graphPreload()

    def graphPreload(self):  # plot and hide imported recordings
        print("graphPreload: entered")
        self.usage("graphPreload")
        self.uiFreeze()  # Freeze UI, thaw on graphPreloadFinished
        t0 = time.time()
        self.mouseoverDisconnect()
        # Clean up any existing thread before starting a new one
        self._cleanup_threads()
        if not uistate.list_idx_recs2preload:
            print("graphPreload: list_idx_recs2preload empty, falling back to all parsed recordings")
            df_p = self.get_df_project()
            uistate.list_idx_recs2preload = df_p[~df_p["sweeps"].eq("...")].index.tolist()
        if not uistate.list_idx_recs2preload:
            print("graphPreload: nothing to preload, returning early")
            self.uiThaw()
            self.update_test()
            self.setButtonParse()
            return
        print(f"graphPreload: starting thread for {len(uistate.list_idx_recs2preload)} recordings: {uistate.list_idx_recs2preload}")
        self.progressBar.setValue(0)
        thread = ui_widgets.graphPreloadThread(uistate, uiplot, self)
        thread.finished.connect(lambda: self.ongraphPreloadFinished(t0))
        thread.finished.connect(thread.deleteLater)  # Auto-cleanup when done
        thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
        self._threads.append(thread)

        # Create ProgressBarManager and connect progress signal
        if len(uistate.list_idx_recs2preload) > 0:
            self.progressBarManager = ui_widgets.ProgressBarManager(self.progressBar, len(uistate.list_idx_recs2preload))

            def _preload_progress(i):
                self.progressBarManager.update(i, "Preloading recording")

            thread.progress.connect(_preload_progress)
            thread.start()
            self.progressBarManager.__enter__()  # Show progress bar
        else:
            print("No new recordings to preload.")

    def ongraphPreloadFinished(self, t0):
        self.graphGroups()
        print(f"Preloaded recordings and groups in {time.time() - t0:.2f} seconds.")
        # Do NOT call graphRefresh() here — tableProjSelectionChanged() below ends
        # with mouseoverUpdate() → graphRefresh(), so calling it here would double-draw.
        self.progressBarManager.__exit__(None, None, None)  # Hide progress bar
        # Return control to test warnings
        self.update_test()
        self.tableUpdate(restore_selection=False)  # parse completion; preserve existing selection via uistate
        self.uiThaw()
        self.tableProjSelectionChanged()

    def graphGroups(self):
        # Get all group IDs
        if not self.dd_groups:
            return
        all_group_ids = set(self.dd_groups.keys())
        if not all_group_ids:
            return
        groups_with_records = {group_id: group_info for group_id, group_info in self.dd_groups.items() if group_info["rec_IDs"]}
        already_plotted_groups = set(uistate.get_groupSet())
        groups_to_plot = all_group_ids & set(groups_with_records.keys()) - already_plotted_groups
        if groups_to_plot:
            for group_ID in groups_to_plot:
                dict_group = self.dd_groups[group_ID]
                level = getattr(uistate, "buttonGroup_test_n", "recording")
                group_mean_data = self.get_dfgroupmean(group_ID, level=level)
                # print(f"graphGroups: Adding group {group_ID} to plot: {group_mean_data}")
                x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
                uiplot.addGroup(group_ID, dict_group, self.V2mV(group_mean_data), x_pos=x_pos)

    def graphUpdate(self, df=None, row=None, reeval_formal_test: bool = True):
        def processRow(row):
            dfmean = self.get_dfmean(row=row)
            dft = self.get_dft(row=row)
            print(f"graphUpdate dft: {dft}")
            if dft is None or (hasattr(dft, "empty") and dft.empty):
                print(f"graphUpdate: skipping row {row.get('recording_name', '?')} (no dft/stims)")
                return
            is_pp = getattr(uistate, "experiment_type", "time") == "PP"
            dfoutput = self.get_dfdiff(row=row) if (uistate.checkBox["paired_stims"] and not is_pp) else self.get_dfoutput(row=row)
            if dfoutput is not None:
                uiplot.addRow(p_row=row, dft=dft, dfmean=dfmean, dfoutput=self.V2mV(dfoutput))

        def processDataFrame(df):
            list_to_plot = [
                rec_id for rec_id in df["ID"].tolist()
                if pd.notna(rec_id) and rec_id not in uistate.get_recSet()
            ]
            for rec_id in list_to_plot:
                matching = df[df["ID"] == rec_id]
                if matching.empty:
                    print(f"graphUpdate: no matching row for rec_id {rec_id}, skipping")
                    continue
                row = matching.iloc[0]
                processRow(row)

        if row is not None:
            processRow(row)
        else:
            df = df if df is not None else self.get_df_project()
            if df is not None and not df.empty:
                processDataFrame(df)
        self.graphGroups()
        self.update_show()
        self.zoomAuto()
        print("graphUpdate calls self.graphRefresh()")
        self.graphRefresh(reeval_formal_test=reeval_formal_test)

    def setupCanvases(self):
        def setup_graph(graph):
            graph.setLayout(QtWidgets.QVBoxLayout())
            canvas = ui_widgets.MplCanvas(parent=graph)
            graph.layout().addWidget(canvas)
            canvas.mpl_connect("button_press_event", lambda event: self.graphClicked(event, canvas))
            canvas.show()
            return canvas

        self.canvasMean = setup_graph(self.graphMean)
        self.canvasEvent = setup_graph(self.graphEvent)
        self.canvasOutput = setup_graph(self.graphOutput)

    def onSplitterMoved(self, splitter_name, pos, index):
        splitter = getattr(self, splitter_name)
        total_size = sum(splitter.sizes())
        if total_size == 0:
            return

        old_proportions = uistate.splitter.get(splitter_name, [])
        sizes = splitter.sizes()
        unbounded_px = sum(size for i, size in enumerate(sizes) if i >= len(old_proportions) or type(old_proportions[i]) == float)

        proportions = []
        for i, size in enumerate(sizes):
            if i < len(old_proportions) and type(old_proportions[i]) != float:
                proportions.append(int(size))  # Keep as fixed pixel value
            else:
                proportions.append(float(size / unbounded_px if unbounded_px > 0 else 0.0))

        # print(f"{splitter_name}, total_size: {total_size}, Proportions: {proportions}")
        uistate.splitter[splitter_name] = proportions
        if splitter_name == "h_splitterMaster" and self.h_splitterMaster.widget(1).isVisible():
            # Recompute graph zooms when the output splitter moves, because the
            # artists' screen positions changed and the hit-test zones for
            # mouseover/selection are now stale.
            self.zoomAuto(reset=True)
            # Ensure the new limits are applied to the canvases.
            for ax in (uistate.ax1, uistate.ax2):
                if ax is not None:
                    try:
                        ax.figure.canvas.draw_idle()
                    except Exception:
                        pass

    @staticmethod
    def _xlim_from_artists(axis, pad=0.05, min_span=1e-9):
        all_x = []
        for line in axis.get_lines():
            if not line.get_visible():
                continue
            if line.get_transform() != axis.transData:
                continue
            xdata = np.asarray(line.get_xdata(), dtype=float).ravel()
            mask = np.isfinite(xdata)
            if mask.any():
                all_x.append(xdata[mask])

        for coll in axis.collections:
            if not coll.get_visible():
                continue
            if isinstance(coll, mcoll.PolyCollection):
                for path in coll.get_paths():
                    vertices = path.vertices
                    if vertices.size == 0:
                        continue
                    xdata = vertices[:, 0]
                    mask = np.isfinite(xdata)
                    if mask.any():
                        all_x.append(xdata[mask])
            elif isinstance(coll, mcoll.PathCollection):
                if coll.get_offset_transform() != axis.transData:
                    continue
                offsets = coll.get_offsets()
                if len(offsets) > 0:
                    xdata = offsets[:, 0]
                    mask = np.isfinite(xdata)
                    if mask.any():
                        all_x.append(xdata[mask])

        if not all_x:
            return None
        xall = np.concatenate(all_x)
        lo, hi = float(xall.min()), float(xall.max())
        span = hi - lo
        if span < min_span:
            span = max(abs(hi), min_span)
            lo, hi = hi - span, hi + span
        lo = lo - pad * span
        hi = hi + pad * span
        return (lo, hi)

    @staticmethod
    def _ylim_from_artists(axis, pad=0.10, min_span=1e-9, x_min=None, x_max=None, ymin=None):
        """Return (ymin, ymax) from all finite y-data on *axis*, with fractional padding.

        Skips single-point artists (vlines, markers) whose y-span would otherwise
        collapse the range, and ignores invisible lines.  Returns None when no
        usable data is found so callers can fall back to a sensible default.

        x_min / x_max: if given, only y-values whose corresponding x falls within
        [x_min, x_max] are considered.  Useful for excluding a stim artefact that
        sits at the left edge of the event window.

        ymin: if given, forces the returned lower bound to exactly this value,
        overriding the data-fitted bottom entirely.  Pass 0 when the checkbox
        "output_ymin0" is checked so that the bottom is always anchored at zero,
        matching the behaviour of zoomOnScroll.
        """
        all_y = []
        for line in axis.get_lines():
            if not line.get_visible():
                continue
            if line.get_transform() != axis.transData:
                continue
            xdata = np.asarray(line.get_xdata(), dtype=float).ravel()
            ydata = np.asarray(line.get_ydata(), dtype=float).ravel()
            mask = np.isfinite(ydata)
            if x_min is not None:
                mask &= xdata >= x_min
            if x_max is not None:
                mask &= xdata <= x_max
            finite = ydata[mask]
            if finite.size == 0:
                continue
            if finite.size == 1 and "marker" in line.get_label():  # skip physical point markers on axe/axm
                continue
            all_y.append(finite)

        for coll in axis.collections:
            if not coll.get_visible():
                continue
            if isinstance(coll, mcoll.PolyCollection):
                for path in coll.get_paths():
                    vertices = path.vertices
                    if vertices.size == 0:
                        continue
                    xdata = vertices[:, 0]
                    ydata = vertices[:, 1]
                    mask = np.isfinite(ydata)
                    if x_min is not None:
                        mask &= xdata >= x_min
                    if x_max is not None:
                        mask &= xdata <= x_max
                    finite = ydata[mask]
                    if finite.size > 0:
                        all_y.append(finite)
            elif isinstance(coll, mcoll.PathCollection):
                if coll.get_offset_transform() != axis.transData:
                    continue
                offsets = coll.get_offsets()
                if len(offsets) == 0:
                    continue
                xdata = offsets[:, 0]
                ydata = offsets[:, 1]
                mask = np.isfinite(ydata)
                if x_min is not None:
                    mask &= xdata >= x_min
                if x_max is not None:
                    mask &= xdata <= x_max
                finite = ydata[mask]
                if finite.size > 0:
                    all_y.append(finite)

        if not all_y:
            return None
        yall = np.concatenate(all_y)
        lo, hi = float(yall.min()), float(yall.max())
        span = hi - lo
        if span < min_span:  # flat data — expand symmetrically
            span = max(abs(hi), min_span)
            lo, hi = hi - span, hi + span
        lo = lo - pad * span
        hi = hi + pad * span
        if ymin is not None:
            lo = ymin
        return (lo, hi)

    def _recalc_axe_drag_zones(self):
        """Recalculate axe mouseover detection zone margins after any zoom change.

        Must be called after axe limits have been committed so that the
        pixel→data transform reflects the new scale.
        """
        if uistate.mouseover_action is None:
            return
        uistate.setMargins(axe=uistate.axe)
        if uistate.mouseover_action in ("EPSP slope", "volley slope"):
            if uistate.mouseover_plot is None:
                return
            uistate.updateDragZones()
        elif uistate.mouseover_action in ("EPSP amp move", "volley amp move"):
            if uistate.mouseover_blob is None:
                return
            uistate.updatePointDragZone()

    def _recalc_axm_detection_zones(self):
        """Recalculate axm mouseover detection zone margins after any zoom change.

        Must be called after axm limits have been committed so that the
        pixel→data transform reflects the new scale.

        The hit zone is set to the marker radius (STIM_MARKER_SIZE / 2) plus a
        5-pixel buffer on every side, so the whole rendered blob is always inside
        the detection area with a small margin to spare.
        """
        if uistate.df_rec_select_time is None or uistate.df_rec_select_time.empty:
            return
        pixels = ui_plot.STIM_MARKER_SIZE // 2 + 5
        uistate.setMarginsAxm(axm=uistate.axm, pixels=pixels)

    def zoomAuto(self, reset=False, skip_axe=False):
        # set and apply Auto-zoom parameters for all axes
        self.usage("zoomAuto")
        prow = self.get_prow()

        ymin_clamp = 0 if self._is_io_mode() else (0 if uistate.checkBox["output_ymin0"] else None)

        if prow is None or str(prow.get("sweeps", "...")) == "...":
            logger.debug("zoomAuto: no (parsed) recording selected, fitting to visible groups")
            self._fit_output_zoom_to_groups()
            self.zoomReset(uistate.ax1)
            self.zoomReset(uistate.ax2)
            return

        # axm: derive from raw mean voltage data with fractional padding.
        # _ylim_from_artists is intentionally not used here: axm also contains
        # axvline artists (stim selection markers) whose y-data spans [0, 1] in
        # axes-fraction space and would corrupt the range.
        sdur = prow.get("sweep_duration", 1.0)
        if not np.isfinite(sdur) or sdur <= 0:
            sdur = 1.0
        uistate.zoom["mean_xlim"] = (0, sdur)
        dfmean = self.get_dfmean(prow)
        try:
            vmin = float(dfmean["voltage"].min())
            vmax = float(dfmean["voltage"].max())
            if not (np.isfinite(vmin) and np.isfinite(vmax)):
                raise ValueError("nonfinite")
        except Exception:
            vmin, vmax = -1.0, 1.0
        pad = 0.10
        span = vmax - vmin
        if not np.isfinite(span) or span <= 0:
            span = 2.0
        uistate.zoom["mean_ylim"] = (vmin - pad * span, vmax + pad * span)
        if not skip_axe:
            # axe: fit to plotted event artists, skipping the stim artefact by starting
            # 0.5 ms after t=0 (the stim); x-axis on axe is already shifted so t=0 is
            # the stim, so the offset is absolute, not relative to event_start.
            artefact_offset = 0.0005  # seconds after t_stim=0 — clears the artefact spike
            artist_ylim = self._ylim_from_artists(uistate.axe, x_min=artefact_offset)
            ymax = artist_ylim[1] if artist_ylim else 0.0002
            ymin = artist_ylim[0] if artist_ylim else -0.0015

            # Calibrate ymin from the visible dfmeans in the 1ms to 9ms window
            # to ensure immunity against single-sweep noise and large artefacts.
            visible_df_mins = []
            dfp = self.get_df_project()
            visible_rec_ids = {v["rec_ID"] for v in uistate.dict_rec_show.values() if "rec_ID" in v and v.get("axis") == "axe"}
            if not visible_rec_ids and prow is not None:
                visible_rec_ids = {prow["ID"]}

            for rec_id in visible_rec_ids:
                matching_rows = dfp[dfp["ID"] == rec_id]
                if matching_rows.empty:
                    continue
                r = matching_rows.iloc[0]
                rec_dfmean = self.get_dfmean(r)
                rec_dft = self.get_dft(r)
                if rec_dft is None or (hasattr(rec_dft, "empty") and rec_dft.empty):
                    continue

                for _, t_row in rec_dft.iterrows():
                    t_stim = t_row.get("t_stim", 0.0)
                    mask = (rec_dfmean["time"] >= t_stim + 0.001) & (rec_dfmean["time"] <= t_stim + 0.009)
                    dfmean_window = rec_dfmean[mask]
                    if not dfmean_window.empty:
                        visible_df_mins.append(float(dfmean_window["voltage"].min()))

            if visible_df_mins:
                df_min = min(visible_df_mins)
                span = ymax - df_min if ymax > df_min else abs(df_min)
                ymin = df_min - 0.10 * span

            uistate.zoom["event_ylim"] = (ymin, ymax)
            ey = uistate.zoom["event_ylim"]
            if not (np.isfinite(ey[0]) and np.isfinite(ey[1])):
                uistate.zoom["event_ylim"] = (-0.0015, 0.0002)
            uistate.zoom["event_xlim"] = (
                uistate.settings["event_start"],
                uistate.settings["event_end"],
            )
        # ax1 / ax2: fit to plotted output artists; fall back to (0, 1.5).
        # Clamp bottom to zero only when output_ymin0 is checked.

        dft = self.get_dft(row=prow)

        if self._is_io_mode():
            xlim1 = self._xlim_from_artists(uistate.ax1, pad=0)
            xlim2 = self._xlim_from_artists(uistate.ax2, pad=0)
            if xlim1 and xlim2:
                out_xmax = max(xlim1[1], xlim2[1])
            elif xlim1:
                out_xmax = xlim1[1]
            elif xlim2:
                out_xmax = xlim2[1]
            else:
                out_xmax = 1.0

            out_xmax = out_xmax * 1.15 if out_xmax > 0 else 1.0
            out_xmin = 0
            uistate.zoom["output_xlim"] = (out_xmin, out_xmax)

            y1 = self._ylim_from_artists(uistate.ax1, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            uistate.zoom["output_ax1_ylim"] = (0, y1[1] * 1.15 if y1 and y1[1] > 0 else 1.5)
            uistate.zoom["output_ax2_ylim"] = (0, y2[1] * 1.15 if y2 and y2[1] > 0 else 1.5)
        elif getattr(uistate, "experiment_type", "time") == "PP":
            uistate.zoom["output_xlim"] = uistate.x_axis_xlim(prow, dft=dft)
            # In PP mode, lock the Y-axis to dynamically start at 0 and scale up to include all active data,
            # snapping to clean multiples of 100 if possible.
            out_xmin, out_xmax = uistate.zoom["output_xlim"]

            y1 = self._ylim_from_artists(uistate.ax1, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)

            def snap_pp_max(y_bounds):
                if not y_bounds:
                    return 3.0
                return max(3.0, (int(y_bounds[1] / 1.0) + 1) * 1.0)

            # Unify the PP mode axes so they always share identical Y-axis boundaries
            uistate.zoom["output_ax1_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
            uistate.zoom["output_ax2_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
        else:
            uistate.zoom["output_xlim"] = uistate.x_axis_xlim(prow, dft=dft)
            out_xmin, out_xmax = uistate.zoom["output_xlim"]

            uistate.zoom["output_ax1_ylim"] = self._ylim_from_artists(uistate.ax1, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (
                0,
                1.5,
            )
            uistate.zoom["output_ax2_ylim"] = self._ylim_from_artists(uistate.ax2, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (
                0,
                1.5,
            )
        if skip_axe:
            self.zoomReset(uistate.axm)
            self.zoomReset(uistate.ax1)
            self.zoomReset(uistate.ax2)
        else:
            self.zoomReset()
        self._recalc_axe_drag_zones()
        self._recalc_axm_detection_zones()

    def _fit_output_zoom_to_groups(self):
        """Compute output xlim/ylim from currently visible artists (groups) and store in uistate.zoom.
        Used when no single recording is selected.
        """
        ymin_clamp = 0 if self._is_io_mode() else (0 if uistate.checkBox["output_ymin0"] else None)

        if self._is_io_mode():
            xlim1 = self._xlim_from_artists(uistate.ax1, pad=0)
            xlim2 = self._xlim_from_artists(uistate.ax2, pad=0)
            if xlim1 and xlim2:
                out_xmax = max(xlim1[1], xlim2[1])
            elif xlim1:
                out_xmax = xlim1[1]
            elif xlim2:
                out_xmax = xlim2[1]
            else:
                out_xmax = 1.0
            out_xmax = out_xmax * 1.15 if out_xmax > 0 else 1.0
            out_xmin = 0
            uistate.zoom["output_xlim"] = (out_xmin, out_xmax)

            y1 = self._ylim_from_artists(uistate.ax1, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            uistate.zoom["output_ax1_ylim"] = (0, y1[1] * 1.15 if y1 and y1[1] > 0 else 1.5)
            uistate.zoom["output_ax2_ylim"] = (0, y2[1] * 1.15 if y2 and y2[1] > 0 else 1.5)
        elif getattr(uistate, "experiment_type", "time") == "PP":
            uistate.zoom["output_xlim"] = uistate.x_axis_xlim(prow=None, dft=None)
            out_xmin, out_xmax = uistate.zoom["output_xlim"]

            y1 = self._ylim_from_artists(uistate.ax1, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)

            def snap_pp_max(y_bounds):
                if not y_bounds:
                    return 3.0
                return max(3.0, (int(y_bounds[1] / 1.0) + 1) * 1.0)

            uistate.zoom["output_ax1_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
            uistate.zoom["output_ax2_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
        else:
            xlim1 = self._xlim_from_artists(uistate.ax1)
            xlim2 = self._xlim_from_artists(uistate.ax2)

            if xlim1 and xlim2:
                out_xmin, out_xmax = min(xlim1[0], xlim2[0]), max(xlim1[1], xlim2[1])
            elif xlim1:
                out_xmin, out_xmax = xlim1
            elif xlim2:
                out_xmin, out_xmax = xlim2
            else:
                out_xmin, out_xmax = (0, 1)

            uistate.zoom["output_xlim"] = (out_xmin, out_xmax)
            uistate.zoom["output_ax1_ylim"] = self._ylim_from_artists(uistate.ax1, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (0, 1.5)
            uistate.zoom["output_ax2_ylim"] = self._ylim_from_artists(uistate.ax2, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (0, 1.5)

    def zoomReset(self, axis=None):
        # self.usage("zoomReset")
        if axis is None:
            for axis in [
                uistate.axm,
                uistate.axe,
                uistate.ax1,
                uistate.ax2,
            ]:
                # print(f"zoomReset: all canvases: {axis}")
                self.zoomReset(axis)
            return
        if axis == uistate.axm:
            logger.debug("zoomReset: axm")
            # print("zoomReset: axm")
            mx = uistate.zoom.get("mean_xlim", (0, 1))
            my = uistate.zoom.get("mean_ylim", (-1, 1))
            if not (np.isfinite(mx[0]) and np.isfinite(mx[1])):
                mx = (0, 1)
            if not (np.isfinite(my[0]) and np.isfinite(my[1])):
                my = (-1, 1)
            axis.axes.set_xlim(mx)
            axis.axes.set_ylim(my)
            self._recalc_axm_detection_zones()
            axis.figure.canvas.draw_idle()
        elif axis == uistate.axe:
            logger.debug("zoomReset: axe")
            # print("zoomReset: axe")
            ex = uistate.zoom.get("event_xlim", (uistate.settings.get("event_start", 0), uistate.settings.get("event_end", 0.05)))
            ey = uistate.zoom.get("event_ylim", (-0.0015, 0.0002))
            if not (np.isfinite(ex[0]) and np.isfinite(ex[1])):
                ex = (0, 0.05)
            if not (np.isfinite(ey[0]) and np.isfinite(ey[1])):
                ey = (-0.0015, 0.0002)
            axis.axes.set_xlim(ex)
            axis.axes.set_ylim(ey)
            axis.figure.canvas.draw_idle()
        elif axis == uistate.ax1 or axis == uistate.ax2:
            logger.debug("zoomReset: ax1/ax2")
            # print("zoomReset: ax1/ax2")
            ox = uistate.zoom.get("output_xlim", (0, 1))
            oy1 = uistate.zoom.get("output_ax1_ylim", (0, 1.5))
            oy2 = uistate.zoom.get("output_ax2_ylim", (0, 1.5))
            if not (np.isfinite(ox[0]) and np.isfinite(ox[1])):
                ox = (0, 1)
            if not (np.isfinite(oy1[0]) and np.isfinite(oy1[1])):
                oy1 = (0, 1.5)
            if not (np.isfinite(oy2[0]) and np.isfinite(oy2[1])):
                oy2 = (0, 1.5)
            uistate.ax1.axes.set_xlim(ox)
            uistate.ax2.axes.set_xlim(ox)
            uistate.ax1.axes.set_ylim(oy1)
            uistate.ax2.axes.set_ylim(oy2)
            uistate.ax1.figure.canvas.draw_idle()
        else:
            raise ValueError("zoomReset: unknown axis")

    def _fit_output_zoom_to_groups(self):
        """Compute output xlim/ylim from currently visible artists (groups) and store in uistate.zoom.
        Used when no single recording is selected.
        """
        ymin_clamp = 0 if self._is_io_mode() else (0 if uistate.checkBox["output_ymin0"] else None)

        if self._is_io_mode():
            xlim1 = self._xlim_from_artists(uistate.ax1, pad=0)
            xlim2 = self._xlim_from_artists(uistate.ax2, pad=0)
            if xlim1 and xlim2:
                out_xmax = max(xlim1[1], xlim2[1])
            elif xlim1:
                out_xmax = xlim1[1]
            elif xlim2:
                out_xmax = xlim2[1]
            else:
                out_xmax = 1.0
            out_xmax = out_xmax * 1.15 if out_xmax > 0 else 1.0
            out_xmin = 0
            uistate.zoom["output_xlim"] = (out_xmin, out_xmax)

            y1 = self._ylim_from_artists(uistate.ax1, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax)
            uistate.zoom["output_ax1_ylim"] = (0, y1[1] * 1.15 if y1 and y1[1] > 0 else 1.5)
            uistate.zoom["output_ax2_ylim"] = (0, y2[1] * 1.15 if y2 and y2[1] > 0 else 1.5)
        elif getattr(uistate, "experiment_type", "time") == "PP":
            uistate.zoom["output_xlim"] = uistate.x_axis_xlim(prow=None, dft=None)
            out_xmin, out_xmax = uistate.zoom["output_xlim"]

            y1 = self._ylim_from_artists(uistate.ax1, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)
            y2 = self._ylim_from_artists(uistate.ax2, pad=0.1, ymin=0, x_min=out_xmin, x_max=out_xmax)

            def snap_pp_max(y_bounds):
                if not y_bounds:
                    return 3.0
                return max(3.0, (int(y_bounds[1] / 1.0) + 1) * 1.0)

            uistate.zoom["output_ax1_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
            uistate.zoom["output_ax2_ylim"] = (0, max(snap_pp_max(y1), snap_pp_max(y2)))
        else:
            xlim1 = self._xlim_from_artists(uistate.ax1)
            xlim2 = self._xlim_from_artists(uistate.ax2)

            if xlim1 and xlim2:
                out_xmin, out_xmax = min(xlim1[0], xlim2[0]), max(xlim1[1], xlim2[1])
            elif xlim1:
                out_xmin, out_xmax = xlim1
            elif xlim2:
                out_xmin, out_xmax = xlim2
            else:
                out_xmin, out_xmax = (0, 1)

            uistate.zoom["output_xlim"] = (out_xmin, out_xmax)
            uistate.zoom["output_ax1_ylim"] = self._ylim_from_artists(uistate.ax1, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (0, 1.5)
            uistate.zoom["output_ax2_ylim"] = self._ylim_from_artists(uistate.ax2, ymin=ymin_clamp, x_min=out_xmin, x_max=out_xmax) or (0, 1.5)
