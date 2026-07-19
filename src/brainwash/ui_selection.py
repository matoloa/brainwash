# ui_selection.py
# SelectionMixin — visibility, show logic, rec/group selection handling
# extracted from UIsub (Phase 1 of ui mixin extraction plan).
#
# Uses self.uistate / self.uiplot set on UIsub at construction (see ui.py).

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets

from brainwash_ui import color_events, recording_cache, stim_intensity, view_state
from ui_widgets import StimTableShortcutFilter, StimUaItemDelegate

logger = logging.getLogger(__name__)

_STIM_STRENGTH_LABEL_DEFAULT = "IO - Input µA"
_STIM_STRENGTH_PENDING_MSG = "Press Apply to update results"
_STIM_STRENGTH_ORANGE = "#e67e22"


class SelectionMixin:
    """Mixin that provides rec/group visibility logic (update_show) and selection helpers.

    Host: ``protocols.SelectionHost``

    Host requirements:
        - self.dd_groups, self.get_groupsOfRec()
        - self.get_df_project(), self.get_dft(), self.get_dffilter()
        - self.update_filter_settings(), self.update_experiment_type_radio_buttons()
        - self.formatTableStimLayout(), self.setButtonParse()
        - self.graphUpdate(), self.zoomAuto(), self.graphRefresh()
        - self.usage()
        - self.uistate.plot.dict_rec_labels, self.uistate.plot.dict_group_labels, etc.
        - self.uistate.plot.list_idx_select_recs, self.uistate.plot.list_idx_select_stims
        - self._is_io_mode()
        - self.dict_folders (for save_cfg in setViewToolVisible)
    """

    def _is_rec_visible(self, v: dict, selected_ids: set, selected_stims: set, valid_pp_ids: set | None = None) -> bool:
        """Predicate: should this rec-label entry be visible given current UI state."""
        if v.get("is_zero_width"):
            return False
        # ID type may be int/str/numpy across df vs artist metadata
        rid = v.get("rec_ID")
        if rid not in selected_ids and str(rid) not in {str(x) for x in selected_ids}:
            return False

        axis = v.get("axis")
        role = v.get("role")
        stim = v.get("stim")
        if not view_state.axm_stim_entry_passes_stim_gate(
            axis=axis,
            role=role,
            stim=stim,
            n_selected_recs=len(selected_ids),
            selected_stims=selected_stims,
        ):
            return False

        # Phase 0 PP mode display guard
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if is_pp and axis in ("ax1", "ax2"):
            if valid_pp_ids is not None and v["rec_ID"] not in valid_pp_ids:
                return False
        # x_mode filtering: lines tagged with a specific x_mode are only visible
        # when that mode is active.  Lines with x_mode=None (mean, event, axe
        # markers) are always eligible.
        # Time mode reuses sweep-mode artists (same underlying data — sweep
        # numbers — with a FuncFormatter converting tick labels to time units),
        # so x_mode="sweep" lines are visible in both "sweep" and "time" modes.
        x_mode = v.get("x_mode")
        is_io = self._is_io_mode()
        if x_mode is not None and x_mode != self.uistate.x_axis:
            if not (x_mode == "sweep" and self.uistate.x_axis == "time"):
                return False
        if is_io and v.get("line") and v["line"].get_label().endswith(" IO trendline"):
            if not self.uistate.project.checkBox.get("io_trendline", False):
                return False
        aspect = v.get("aspect")
        axis = v.get("axis")
        if view_state.suppress_io_output_for_stim_dirty(
            experiment_type=self.uistate.experiment.experiment_type,
            io_input=self.uistate.experiment.io_input,
            dirty=bool(getattr(self.uistate.plot, "stim_intensity_dirty", False)),
            x_mode=x_mode,
            axis=axis,
        ):
            return False
        if aspect and not self.uistate.project.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
                return False
        # Relative mode: volley has no relative series — hide ax1/ax2 output
        # (incl. means). Checkbox state is preserved; event markers stay on axe.
        norm_active = self.uistate.project.checkBox["norm_EPSP"]
        if view_state.suppress_volley_under_norm(aspect, norm_active=norm_active, axis=axis):
            return False
        # special case for *_mean aspects (volley_amp_mean, volley_slope_mean): independent of parent volley per requirement
        if aspect in ("volley_amp_mean", "volley_slope_mean"):
            return self.uistate.project.checkBox.get(aspect, False)
        if aspect and aspect.endswith("_mean") and not self.uistate.project.checkBox.get(aspect.replace("_mean", ""), True):
            if axis == "axe" or not is_io:
                return False
        # norm/raw switch: only EPSP amp/slope have a norm variant.
        # Only applies to ax1/ax2 output lines — markers on axe represent physical
        # measurement positions and are always shown regardless of normalisation.
        variant = v.get("variant")
        if axis in ("ax1", "ax2"):
            if variant == "norm" and not norm_active:
                return False
            if variant == "raw" and norm_active and aspect in ("EPSP_amp", "EPSP_slope"):
                return False
        return True

    def _is_group_visible(self, v: dict, selected_groups: set | None) -> bool:
        """Predicate: should this group-label entry be visible given current UI state.

        When selected_groups is None (no recordings selected), all checkbox-ticked
        groups are shown on ax1/ax2 regardless of recording membership.
        """
        if selected_groups is not None and v["group_ID"] not in selected_groups:
            return False
        # x_mode filtering: group lines tagged with a specific x_mode are only
        # visible when that mode is active.
        x_mode = v.get("x_mode")
        is_io = self._is_io_mode()
        if x_mode is not None and x_mode != self.uistate.x_axis:
            if not (x_mode == "sweep" and self.uistate.x_axis == "time"):
                return False
        if is_io and v.get("line") and v["line"].get_label().endswith(" IO trendline"):
            if not self.uistate.project.checkBox.get("io_trendline", False):
                return False
        aspect = v.get("aspect")
        axis = v.get("axis")
        if view_state.suppress_io_output_for_stim_dirty(
            experiment_type=self.uistate.experiment.experiment_type,
            io_input=self.uistate.experiment.io_input,
            dirty=bool(getattr(self.uistate.plot, "stim_intensity_dirty", False)),
            x_mode=x_mode,
            axis=axis,
        ):
            return False
        if aspect and not self.uistate.project.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
                return False
        # Relative mode: volley has no relative series — hide group volley output.
        # Checkbox state is preserved for when relative mode is turned off.
        norm_active = self.uistate.project.checkBox["norm_EPSP"]
        if view_state.suppress_volley_under_norm(aspect, norm_active=norm_active, axis=axis):
            return False
        # special case for *_mean aspects (volley_amp_mean, volley_slope_mean): independent of parent volley per requirement
        if aspect in ("volley_amp_mean", "volley_slope_mean"):
            return self.uistate.project.checkBox.get(aspect, False)
        if aspect and aspect.endswith("_mean") and not self.uistate.project.checkBox.get(aspect.replace("_mean", ""), True):
            if axis == "axe" or not is_io:
                return False
        variant = v.get("variant")
        is_pp = self.uistate.experiment.experiment_type == "PP"
        if not is_pp:
            if variant == "norm" and not norm_active:
                return False
            if variant == "raw" and norm_active:
                return False
        if not self.dd_groups[v["group_ID"]]["show"]:
            return False
        return True

    def update_show(self, reset=False):
        if reset:
            for v in self.uistate.plot.dict_rec_labels.values():
                v["line"].set_visible(False)
            self.uistate.plot.dict_rec_show = {}
            if self.dd_groups is not None:
                for v in self.uistate.plot.dict_group_labels.values():
                    for key in ["line", "fill"]:
                        obj = v[key]
                        if hasattr(obj, "set_visible"):
                            obj.set_visible(False)
                        elif hasattr(obj, "patches"):
                            for p in obj.patches:
                                p.set_visible(False)
                        elif hasattr(obj, "lines"):
                            for l in obj.lines:
                                if l is not None:
                                    if isinstance(l, (list, tuple)):
                                        for sub_l in l:
                                            if sub_l is not None:
                                                sub_l.set_visible(False)
                                    else:
                                        l.set_visible(False)
                        elif hasattr(obj, "get_children"):
                            for c in obj.get_children():
                                if c is not None:
                                    c.set_visible(False)
                self.uistate.plot.dict_group_show = {}
            # Important: Don't return here! Keep processing the rest of the method
            # so the currently selected recordings/stims/groups get turned back on.

        if self.uistate.plot.df_recs2plot is None:
            # No recordings selected — hide all rec lines but keep checkbox-ticked
            # groups visible on ax1/ax2.
            for v in self.uistate.plot.dict_rec_labels.values():
                v["line"].set_visible(False)
            self.uistate.plot.dict_rec_show = {}
            if self.dd_groups is not None:
                new_group_show = {}
                is_pp = self.uistate.experiment.experiment_type == "PP"
                for k, v in self.uistate.plot.dict_group_labels.items():
                    visible = self._is_group_visible(v, selected_groups=None)
                    if is_pp and v.get("is_overlay"):
                        visible = False
                    # respect current n_unit level
                    current_level = self.uistate.stat_test.buttonGroup_test_n
                    if v.get("level") and v.get("level") != current_level:
                        visible = False
                    for key in ["line", "fill"]:
                        obj = v[key]
                        if hasattr(obj, "set_visible"):
                            obj.set_visible(visible)
                        elif hasattr(obj, "patches"):
                            for p in obj.patches:
                                p.set_visible(visible)
                        elif hasattr(obj, "lines"):
                            for l in obj.lines:
                                if l is not None:
                                    if isinstance(l, (list, tuple)):
                                        for sub_l in l:
                                            if sub_l is not None:
                                                sub_l.set_visible(visible)
                                    else:
                                        l.set_visible(visible)
                        elif hasattr(obj, "get_children"):
                            for c in obj.get_children():
                                c.set_visible(visible)
                    for aux in v.get("pp_aux_artists") or []:
                        if aux is not None and hasattr(aux, "set_visible"):
                            aux.set_visible(visible)
                    if visible:
                        new_group_show[k] = v
                self.uistate.plot.dict_group_show = new_group_show
            return

        selected_ids = set(self.uistate.plot.df_recs2plot["ID"])
        # Resolve stim numbers from table model (multi-rec intersection uses real stim ids)
        if hasattr(self, "_selected_stim_numbers"):
            selected_stims = self._selected_stim_numbers()
        else:
            selected_stims = {int(i) + 1 for i in (self.uistate.plot.list_idx_select_stims or [])}
        # print(f"update_show, selected_ids: {selected_ids}, selected_stims: {selected_stims}")

        is_pp = self.uistate.experiment.experiment_type == "PP"
        valid_pp_ids = set()
        if is_pp:
            df_p = self.get_df_project()
            for rec_id in selected_ids:
                matches = df_p[df_p["ID"] == rec_id]
                if not matches.empty:
                    rec_name = matches.iloc[0]["recording_name"]
                    dft = self.dict_ts.get(rec_name)
                    if dft is not None and len(dft) == 2:
                        valid_pp_ids.add(rec_id)

        # rec lines
        new_rec_show = {}
        for k, v in self.uistate.plot.dict_rec_labels.items():
            visible = self._is_rec_visible(v, selected_ids, selected_stims, valid_pp_ids)
            v["line"].set_visible(visible)
            if visible:
                new_rec_show[k] = v
        self.uistate.plot.dict_rec_show = new_rec_show

        # group lines
        if self.dd_groups is not None:
            is_pp = self.uistate.experiment.experiment_type == "PP"
            selected_groups = {group for rec_ID in selected_ids for group in self.get_groupsOfRec(rec_ID)}
            new_group_show = {}
            for k, v in self.uistate.plot.dict_group_labels.items():
                visible = self._is_group_visible(v, selected_groups)

                if is_pp:
                    if selected_ids:
                        # Rec view: hide normal group artists, show overlay
                        if not v.get("is_overlay"):
                            visible = False
                    else:
                        # Group view: show normal group artists, hide overlay
                        if v.get("is_overlay"):
                            visible = False

                # Level-aware visibility for n_unit (recording/slice/subject)
                current_level = self.uistate.stat_test.buttonGroup_test_n
                if v.get("level") and v.get("level") != current_level:
                    visible = False

                for key in ["line", "fill"]:
                    obj = v[key]
                    if hasattr(obj, "set_visible"):
                        obj.set_visible(visible)
                    elif hasattr(obj, "patches"):
                        for p in obj.patches:
                            p.set_visible(visible)
                    elif hasattr(obj, "lines"):
                        for l in obj.lines:
                            if l is not None:
                                if isinstance(l, (list, tuple)):
                                    for sub_l in l:
                                        if sub_l is not None:
                                            sub_l.set_visible(visible)
                                else:
                                    l.set_visible(visible)
                    elif hasattr(obj, "get_children"):
                        for c in obj.get_children():
                            if c is not None:
                                c.set_visible(visible)
                for aux in v.get("pp_aux_artists") or []:
                    if aux is not None and hasattr(aux, "set_visible"):
                        aux.set_visible(visible)
                if visible:
                    new_group_show[k] = v
            self.uistate.plot.dict_group_show = new_group_show

            # enforce n_unit level visibility for groups (separate artists per level)
            if hasattr(self.uiplot, "update_group_level_visibility"):
                self.uiplot.update_group_level_visibility()

        # Event/stim marker colors (Rec | Stim | Group) — after visibility settled
        self.apply_event_colors(draw=False)

    def apply_event_colors(self, *, draw: bool = True) -> None:
        """Recolor axe/axm stim-related artists per color_events policy (#6)."""
        store = getattr(self.uistate.plot, "dict_rec_labels", None) or {}
        if not store:
            return

        radio = color_events.normalize_color_events_by(getattr(self.uistate.project, "color_events_by", "rec"))
        df_sel = getattr(self.uistate.plot, "df_recs2plot", None)
        if df_sel is None or getattr(df_sel, "empty", True) or "ID" not in getattr(df_sel, "columns", []):
            selected_ids = []
        else:
            selected_ids = list(df_sel["ID"].tolist())

        if hasattr(self, "_selected_stim_numbers"):
            selected_stims = self._selected_stim_numbers()
        else:
            selected_stims = {int(stim) + 1 for stim in (self.uistate.plot.list_idx_select_stims or [])}
        n_rec = len(selected_ids)
        n_stim = len(selected_stims) if selected_stims else 0
        if n_stim == 0 and selected_ids:
            # Fall back to unique stim tags among event artists for selected recs
            stims = set()
            for v in store.values():
                if not isinstance(v, dict):
                    continue
                if v.get("rec_ID") not in selected_ids and str(v.get("rec_ID")) not in {str(x) for x in selected_ids}:
                    continue
                if v.get("stim") is not None:
                    try:
                        stims.add(int(v["stim"]))
                    except (TypeError, ValueError):
                        stims.add(v["stim"])
            n_stim = len(stims)

        mode = color_events.effective_color_events_mode(radio, n_rec, n_stim)

        def _set_event_artist_color(line, color) -> None:
            if line is None or color is None:
                return
            try:
                if hasattr(line, "set_color"):
                    line.set_color(color)
                if hasattr(line, "set_markerfacecolor"):
                    line.set_markerfacecolor(color)
                if hasattr(line, "set_markeredgecolor"):
                    line.set_markeredgecolor(color)
            except Exception:
                pass

        if mode == "default":
            # Restore build-time colours (measure_rgb / per-stim gradient at addRow)
            for _k, entry in store.items():
                if not color_events.artist_should_receive_event_color(entry):
                    continue
                _set_event_artist_color(entry.get("line"), entry.get("base_color"))
            if draw:
                for canvas_name in ("canvasMean", "canvasEvent", "canvasOutput"):
                    canvas = getattr(self, canvas_name, None)
                    if canvas is not None and hasattr(canvas, "draw_idle"):
                        canvas.draw_idle()
            return

        # Full table display order (not only selected) → stable rec hues
        display_order = []
        model_df = None
        if hasattr(self, "_table_model_df"):
            model_df = self._table_model_df()
        if model_df is not None and not getattr(model_df, "empty", True) and "ID" in model_df.columns:
            display_order = list(model_df["ID"].tolist())
        else:
            display_order = list(selected_ids)
        rec_index_map = color_events.rec_gradient_index_map(display_order)

        # Full *detected* stim domain on selected recs (not only field-selected stims)
        # so blob color matches event color for the same stim number.
        domain_rec_ids = selected_ids if selected_ids else display_order
        full_stim_domain = color_events.collect_stim_domain_for_recs(store, domain_rec_ids)
        stim_index_map = color_events.stim_gradient_index_map(full_stim_domain)

        if mode == "rec":
            n_grad = max(len(display_order), 1)
        elif mode == "stim":
            n_grad = max(len(full_stim_domain), 1)
        else:
            n_grad = 1
        if hasattr(self, "uiplot") and hasattr(self.uiplot, "get_dict_gradient"):
            gradient = self.uiplot.get_dict_gradient(n_grad)
        else:
            gradient = {i: "black" for i in range(n_grad)}

        dd_groups = getattr(self, "dd_groups", None) or {}

        for _k, entry in store.items():
            if not color_events.artist_should_receive_event_color(entry):
                continue
            rid = entry.get("rec_ID")
            color = color_events.resolve_event_artist_color(
                mode=mode,
                rec_ID=rid,
                stim=entry.get("stim"),
                stim_index_map=stim_index_map,
                rec_index_map=rec_index_map,
                gradient=gradient,
                dd_groups=dd_groups,
            )
            _set_event_artist_color(entry.get("line"), color)

        if draw:
            for canvas_name in ("canvasMean", "canvasEvent", "canvasOutput"):
                canvas = getattr(self, canvas_name, None)
                if canvas is not None and hasattr(canvas, "draw_idle"):
                    canvas.draw_idle()

    def update_sample_checkbox(self):
        """Updates checkBox_is_group_sample enabled/checked state. Called from tableProjSelectionChanged"""
        if len(self.uistate.plot.list_idx_select_recs) != 1 or not hasattr(self, "checkBox_is_group_sample"):
            self.checkBox_is_group_sample.setEnabled(False)
            self.checkBox_is_group_sample.setChecked(False)
            return
        prow = self.get_prow()
        if prow is None:
            self.checkBox_is_group_sample.setEnabled(False)
            self.checkBox_is_group_sample.setChecked(False)
            return
        rec_ID = prow["ID"]
        rec_str = str(rec_ID)
        groups = self.get_groupsOfRec(rec_ID)
        enabled = len(groups) > 0
        checked = enabled and all(str(self.dd_groups.get(g, {}).get("sample")) == rec_str for g in groups)
        self.uistate.project.checkBox["is_group_sample"] = checked
        checkbox = self.checkBox_is_group_sample
        checkbox.blockSignals(True)
        checkbox.setEnabled(enabled)
        checkbox.setChecked(checked)
        checkbox.blockSignals(False)

    def _update_io_stim_frame_visibility(self) -> None:
        """Show IO stim-µA frame only when pin ∧ experiment_type io ∧ input stim."""
        if not hasattr(self, "frameToolType_sub_io_stim"):
            return
        exp = self.uistate.experiment
        pin = self.uistate.project.viewTools.get("frameToolType_sub_io_stim", ["", True])[1]
        visible = view_state.should_show_io_stim_frame(
            exp.experiment_type,
            exp.io_input,
            pin_visible=bool(pin),
        )
        self.frameToolType_sub_io_stim.setVisible(visible)
        if visible:
            self.refresh_stim_strength_table()

    def _ensure_stim_strength_table_configured(self) -> None:
        """One-time edit triggers, delegate (Enter→next row), focus policy."""
        table = getattr(self, "tableWidget_stim_strength", None)
        if table is None or getattr(table, "_stim_strength_configured", False):
            return
        table._stim_strength_configured = True
        table.setFocusPolicy(QtCore.Qt.StrongFocus)
        table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.SelectedClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.AnyKeyPressed
        )
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setTabKeyNavigation(True)
        # Don't let the tools scroll area eat the first keystroke
        table.setFocusProxy(None)
        # Beat group digit shortcuts (actionAddTo_2 = "2") so µA typing works.
        # Filter must be a QObject — not UIsub (mixin host is not a valid QObject filter).
        guard = StimTableShortcutFilter(table)
        table.installEventFilter(guard)
        table.viewport().installEventFilter(guard)
        self._stim_strength_shortcut_filter = guard
        delegate = StimUaItemDelegate(table)
        delegate.enter_pressed.connect(self._stim_strength_enter_next_row)
        table.setItemDelegateForColumn(1, delegate)
        self._stim_strength_delegate = delegate

    def _stim_strength_enter_next_row(self, row: int) -> None:
        """After Enter commits a µA cell, move edit focus to the next bin."""
        table = getattr(self, "tableWidget_stim_strength", None)
        if table is None:
            return
        next_row = int(row) + 1
        if next_row >= table.rowCount():
            return

        def _open_next():
            table.setCurrentCell(next_row, 1)
            item = table.item(next_row, 1)
            if item is not None:
                table.editItem(item)

        QtCore.QTimer.singleShot(0, _open_next)

    def refresh_stim_strength_table(self) -> None:
        """Fill tableWidget_stim_strength for the selected rec (bins only)."""
        if not hasattr(self, "tableWidget_stim_strength"):
            return
        self._ensure_stim_strength_table_configured()
        table = self.tableWidget_stim_strength
        label = getattr(self, "label_io_input_stim", None)
        # Don't rebuild mid-edit (would drop the first keystrokes of the next cell)
        if table.state() == QtWidgets.QAbstractItemView.EditingState:
            return

        def _set_label(text: str) -> None:
            if label is not None:
                label.setText(text)

        def _clear_table(*, message: str) -> None:
            _set_label(message)
            table.blockSignals(True)
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["bin", "µA"])
            table.setRowCount(0)
            table.blockSignals(False)
            table.setFixedHeight(stim_intensity.table_height_for_rows(0, row_height=max(table.verticalHeader().defaultSectionSize(), 20)))

        exp = self.uistate.experiment
        pin = self.uistate.project.viewTools.get("frameToolType_sub_io_stim", ["", True])[1]
        if not view_state.should_show_io_stim_frame(exp.experiment_type, exp.io_input, pin_visible=bool(pin)):
            return

        idxs = self.uistate.plot.list_idx_select_recs or []
        if len(idxs) != 1:
            _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — select one rec")
            return

        try:
            prow = self.get_prow()
        except Exception:
            prow = None
        if prow is None or (isinstance(prow, pd.DataFrame) and prow.empty):
            _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — select one rec")
            return
        if isinstance(prow, pd.DataFrame):
            prow = prow.iloc[0]

        bin_size = prow.get("bin_size") if hasattr(prow, "get") else prow["bin_size"]
        if bin_size is None or pd.isna(bin_size) or int(bin_size) < 1:
            _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — set bin size")
            return

        bin_size = int(bin_size)
        try:
            dff = self.get_dffilter(prow)
            if dff is None or dff.empty or "sweep" not in dff.columns:
                _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — no sweeps")
                return
            max_sweep = int(pd.to_numeric(dff["sweep"], errors="coerce").max())
            n_bins = stim_intensity.n_bins_from_max_sweep(max_sweep, bin_size)
            n_sweeps = max_sweep + 1  # 0-based inclusive
        except Exception as e:
            logger.debug("refresh_stim_strength_table: %s", e)
            _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — set bin size")
            return

        if n_bins < 1:
            _clear_table(message=f"{_STIM_STRENGTH_LABEL_DEFAULT} — no bins")
            return

        rec = prow["recording_name"]
        folder = self.dict_folders.get("stim_intensity")
        path = recording_cache.stim_intensity_csv_path(str(folder), rec) if folder is not None else None
        series_df = stim_intensity.load_stim_intensity_csv(path) if path else stim_intensity.load_stim_intensity_csv("")
        bin_vals = stim_intensity.bin_values_from_sweep_series(
            series_df, n_bins=n_bins, bin_size=bin_size
        )

        _set_label(_STIM_STRENGTH_LABEL_DEFAULT)
        table.blockSignals(True)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["bin", "µA"])
        table.setRowCount(n_bins)
        table.verticalHeader().setVisible(False)
        for i in range(n_bins):
            lab = QtWidgets.QTableWidgetItem(f"bin{i}")
            lab.setFlags(lab.flags() & ~QtCore.Qt.ItemIsEditable)
            table.setItem(i, 0, lab)
            val = bin_vals[i]
            text = "" if not np.isfinite(val) else f"{val:g}"
            ua = QtWidgets.QTableWidgetItem(text)
            ua.setFlags(
                QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable
            )
            table.setItem(i, 1, ua)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        row_h = max(table.verticalHeader().defaultSectionSize(), 20)
        hdr_h = table.horizontalHeader().height() or 24
        th = stim_intensity.table_height_for_rows(n_bins, row_height=row_h, header_height=hdr_h)
        table.setFixedHeight(th)
        if n_bins > stim_intensity.TABLE_VISIBLE_ROW_CAP:
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        else:
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # Grow parent frame so absolute-geometry table is not clipped
        frame = getattr(self, "frameToolType_sub_io_stim", None)
        if frame is not None:
            top = table.geometry().y()
            frame.setMinimumHeight(top + th + 8)
        table.blockSignals(False)
        # Stash for save path
        self._stim_strength_table_meta = {
            "rec": rec,
            "bin_size": bin_size,
            "n_bins": n_bins,
            "n_sweeps": n_sweeps,
            "path": path,
        }
        btn = getattr(self, "pushButton_io_stim_strength_apply", None)
        if btn is not None:
            btn.setEnabled(bool(getattr(self.uistate.plot, "stim_intensity_dirty", False)))

    def _stim_intensity_dirty_active(self) -> bool:
        return (
            bool(getattr(self.uistate.plot, "stim_intensity_dirty", False))
            and self.uistate.experiment.experiment_type == "io"
            and self.uistate.experiment.io_input == "stim"
        )

    def _set_stim_intensity_dirty(self, dirty: bool) -> None:
        self.uistate.plot.stim_intensity_dirty = bool(dirty)
        btn = getattr(self, "pushButton_io_stim_strength_apply", None)
        if btn is not None:
            btn.setEnabled(bool(dirty) and self._is_io_mode() and self.uistate.experiment.io_input == "stim")
        # Defer hide/statusbar work so it does not run inside editor close / next key
        QtCore.QTimer.singleShot(0, self._apply_stim_intensity_dirty_ui)

    def _show_stim_intensity_pending_statusbar(self) -> None:
        if hasattr(self, "_set_statusbar_appearance"):
            self.uistate.stat_test.statusbar_state = "stim_intensity_pending"
            self._set_statusbar_appearance(
                _STIM_STRENGTH_ORANGE,
                text_color="white",
                bold=True,
                text=_STIM_STRENGTH_PENDING_MSG,
            )

    def _draw_output_canvases(self) -> None:
        for cname in ("canvasOutput", "canvasMean", "canvasEvent"):
            c = getattr(self, cname, None)
            if c is not None:
                try:
                    c.draw_idle()
                except Exception:
                    pass

    def _apply_stim_intensity_dirty_ui(self) -> None:
        """Hide IO output and show orange Apply warning while dirty; else restore."""
        try:
            self.update_show()
        except Exception:
            pass
        self._draw_output_canvases()
        if self._stim_intensity_dirty_active():
            self._show_stim_intensity_pending_statusbar()
            return
        if getattr(self.uistate.stat_test, "statusbar_state", None) == "stim_intensity_pending":
            self.uistate.stat_test.statusbar_state = None
            if hasattr(self, "update_test"):
                try:
                    self.update_test()
                except Exception:
                    if hasattr(self, "_set_statusbar_appearance"):
                        self._set_statusbar_appearance(clear=True)
            elif hasattr(self, "_set_statusbar_appearance"):
                self._set_statusbar_appearance(clear=True)

    def _write_stim_strength_table_to_csv(self) -> bool:
        """Expand current table bins → sweep CSV. Returns False if nothing to write."""
        meta = getattr(self, "_stim_strength_table_meta", None)
        table = getattr(self, "tableWidget_stim_strength", None)
        if not meta or table is None or not meta.get("path"):
            return False
        n_bins = int(meta["n_bins"])
        bin_size = int(meta["bin_size"])
        n_sweeps = int(meta["n_sweeps"])
        bin_values: list[float | None] = []
        for i in range(n_bins):
            item = table.item(i, 1)
            text = item.text().strip() if item is not None else ""
            if text == "":
                bin_values.append(None)
                continue
            try:
                bin_values.append(float(text.replace(",", ".")))
            except ValueError:
                bin_values.append(None)
        mapping = stim_intensity.expand_bin_values_to_sweeps(
            bin_values, bin_size=bin_size, n_sweeps=n_sweeps
        )
        stim_intensity.save_stim_intensity_csv(meta["path"], stim_intensity.frame_from_series(mapping))
        return True

    def on_stim_strength_cell_changed(self, row: int, column: int) -> None:
        """Save CSV (cheap) and mark dirty — no full IO rebuild until Apply."""
        if column != 1:
            return
        if getattr(self, "_stim_strength_table_updating", False):
            return
        table = getattr(self, "tableWidget_stim_strength", None)
        # Ignore spurious changes while the table is being rebuilt
        if table is not None and table.signalsBlocked():
            return
        if not self._write_stim_strength_table_to_csv():
            return
        if self._is_io_mode() and self.uistate.experiment.io_input == "stim":
            self._set_stim_intensity_dirty(True)

    def on_stim_strength_apply(self) -> None:
        """Apply: ensure CSV saved, clear dirty, single IO refresh."""
        self.usage("on_stim_strength_apply")
        self._write_stim_strength_table_to_csv()
        self.uistate.plot.stim_intensity_dirty = False
        btn = getattr(self, "pushButton_io_stim_strength_apply", None)
        if btn is not None:
            btn.setEnabled(False)
        if getattr(self.uistate.stat_test, "statusbar_state", None) == "stim_intensity_pending":
            self.uistate.stat_test.statusbar_state = None
        if self._is_io_mode() and self.uistate.experiment.io_input == "stim":
            try:
                self.exorcise()
                self.triggerRefresh()
            except Exception as e:
                logger.debug("on_stim_strength_apply refresh: %s", e)
            if hasattr(self, "update_test"):
                try:
                    self.update_test()
                except Exception:
                    pass
        else:
            self._apply_stim_intensity_dirty_ui()

    def clear_stim_intensity_dirty(self) -> None:
        """Drop pending Apply state (e.g. leave IO or leave Stim input). CSVs unchanged."""
        if not getattr(self.uistate.plot, "stim_intensity_dirty", False):
            btn = getattr(self, "pushButton_io_stim_strength_apply", None)
            if btn is not None:
                btn.setEnabled(False)
            return
        self.uistate.plot.stim_intensity_dirty = False
        btn = getattr(self, "pushButton_io_stim_strength_apply", None)
        if btn is not None:
            btn.setEnabled(False)
        if getattr(self.uistate.stat_test, "statusbar_state", None) == "stim_intensity_pending":
            self.uistate.stat_test.statusbar_state = None
            if hasattr(self, "_set_statusbar_appearance"):
                # Restore via update_test if available after caller finishes mode switch
                pass

    def setViewToolVisible(self, frame, visible=None):
        """Toggle visibility of tool frames (hierarchy, timetable, etc) and sync menu state + persist."""
        self.usage(f"setViewToolVisible {frame} {visible}")
        if frame in self.uistate.project.viewTools:
            if visible is None:
                visible = not self.uistate.project.viewTools[frame][1]
            self.uistate.project.viewTools[frame][1] = visible
            if frame == "frameToolType_sub_io_stim":
                # Pin only; mode gates applied by helper (must not show under non-IO / non-stim).
                self._update_io_stim_frame_visibility()
            else:
                getattr(self, frame).setVisible(visible)

            # Sync the menu action if it exists
            text = self.uistate.project.viewTools[frame][0]
            if hasattr(self, "menuView"):
                for action in self.menuView.actions():
                    if action.text() == text:
                        if action.isChecked() != visible:
                            action.setChecked(visible)
                        break
        else:
            if visible is None:
                visible = not getattr(self, frame).isVisible()
            getattr(self, frame).setVisible(visible)

        self.uistate.save_cfg(projectfolder=self.dict_folders["project"])
