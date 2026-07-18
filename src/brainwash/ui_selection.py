# ui_selection.py
# SelectionMixin — visibility, show logic, rec/group selection handling
# extracted from UIsub (Phase 1 of ui mixin extraction plan).
#
# Uses self.uistate / self.uiplot set on UIsub at construction (see ui.py).

from __future__ import annotations

import logging

import pandas as pd
from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


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
        if v["rec_ID"] not in selected_ids:
            return False
        if v["stim"] is not None and v["stim"] not in selected_stims:
            return False

        # Phase 0 PP mode display guard
        axis = v.get("axis")
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
        if aspect and not self.uistate.project.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
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
        norm_active = self.uistate.project.checkBox["norm_EPSP"]
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
        if aspect and not self.uistate.project.checkBox.get(aspect, True):
            if axis == "axe" or not is_io:
                return False
        # special case for *_mean aspects (volley_amp_mean, volley_slope_mean): independent of parent volley per requirement
        if aspect in ("volley_amp_mean", "volley_slope_mean"):
            return self.uistate.project.checkBox.get(aspect, False)
        if aspect and aspect.endswith("_mean") and not self.uistate.project.checkBox.get(aspect.replace("_mean", ""), True):
            if axis == "axe" or not is_io:
                return False
        variant = v.get("variant")
        norm_active = self.uistate.project.checkBox["norm_EPSP"]
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
        selected_stims = {stim + 1 for stim in self.uistate.plot.list_idx_select_stims}  # stim_select is 0-based (indices) - convert to stims
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

    def setViewToolVisible(self, frame, visible=None):
        """Toggle visibility of tool frames (hierarchy, timetable, etc) and sync menu state + persist."""
        self.usage(f"setViewToolVisible {frame} {visible}")
        if frame in self.uistate.project.viewTools:
            if visible is None:
                visible = not self.uistate.project.viewTools[frame][1]
            self.uistate.project.viewTools[frame][1] = visible
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
