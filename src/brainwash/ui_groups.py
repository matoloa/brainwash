# ui_groups.py
# GroupMixin — group management methods extracted from UIsub (Phase 5 refactor).
# These methods operate on dd_groups / df_project and emit refresh signals.
#
# Uses self.uistate / self.config / self.uiplot on UIsub (see ui.py).

from __future__ import annotations

import pickle
import re
from pathlib import Path

import pandas as pd
from PyQt5 import QtCore, QtWidgets

from brainwash_ui import plot_series
from ui_widgets import CustomCheckBox, EntityRemoveButton

class GroupMixin:
    """Mixin that provides all group-management behaviour for UIsub.

    Also manages dd_testsets (loaded in loadProject() via testset_get_dd()).
    """

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def group_get_dd(
        self,
    ):  # dd_groups is a dict of dicts: {group_ID (int): {group_name: str, color: str, show: bool, rec_IDs: [str]}}
        path_dd_groups = Path(self.dict_folders["project"] / "groups.pkl")
        if path_dd_groups.exists():
            with open(path_dd_groups, "rb") as f:
                dict_groups = pickle.load(f)
            # migration for v0.15 sample feature: ensure every group dict has "sample": None (fixes persistence for old groups.pkl so checkbox re-checks correctly)
            for g in dict_groups.values():
                if "sample" not in g:
                    g["sample"] = None
                elif g["sample"] is not None:
                    g["sample"] = str(g["sample"])  # normalize rec_ID to str
            return dict_groups
        return {}

    def group_save_dd(
        self, dd_groups=None, *, restore_selection: bool = True
    ):  # dd_groups is a dict of dicts: {group_ID (int): {group_name: str, color: str, show: bool, rec_IDs: [str]}}
        self.group_update_dfp(restore_selection=restore_selection)
        if dd_groups is None:
            dd_groups = self.dd_groups
        path_dd_groups = Path(self.dict_folders["project"] / "groups.pkl")
        with open(path_dd_groups, "wb") as f:
            pickle.dump(dd_groups, f)

    # ------------------------------------------------------------------
    # Test set persistence (parallel to groups, uses test_sets.pkl and integer set_ID)
    # ------------------------------------------------------------------

    def testset_get_dd(self):
        # dd_testsets: {set_ID (int): {"set_name": str, "color": str, "show": bool, "sweeps": [int], "description": str}}
        path_dd_testsets = Path(self.dict_folders["project"] / "test_sets.pkl")
        if path_dd_testsets.exists():
            with open(path_dd_testsets, "rb") as f:
                dict_testsets = pickle.load(f)
            return dict_testsets
        return {}

    def testset_save_dd(self, dd_testsets=None):
        if dd_testsets is None:
            dd_testsets = self.dd_testsets
        path_dd_testsets = Path(self.dict_folders["project"] / "test_sets.pkl")
        with open(path_dd_testsets, "wb") as f:
            pickle.dump(dd_testsets, f)

    def group_samples_get_dd(self):
        """Returns the full dd_group_samples dict (shape: {group_ID: {test_ID: df}, ...}).
        If not yet populated, triggers get_ddgroup_sample(None) which builds/purges
        all groups that have a "sample" pointer (per refresh_samples() pattern).
        Mirrors testset_get_dd / group_get_dd helpers for consistency with ui.py:graphRefresh.
        """
        return self.get_ddgroup_sample(None)

    def get_groupsOfRec(self, rec_ID):  # returns a set of all 'group ID' that have rec_ID in their 'rec_IDs' list
        if rec_ID is None:
            return []
        rec_str = str(rec_ID)
        return [key for key, value in self.dd_groups.items() if any(rec_str == str(r) for r in value.get("rec_IDs", []))]

    # ------------------------------------------------------------------
    # Create / remove
    # ------------------------------------------------------------------

    def group_ensure(self, group_ID: int) -> bool:
        """Create group *group_ID* (1–9) if missing. Returns True if group exists afterward."""
        try:
            group_ID = int(group_ID)
        except (TypeError, ValueError):
            return False
        if group_ID < 1 or group_ID > 9:
            print(f"group_ensure: invalid group_ID {group_ID} (allowed 1–9).")
            return False
        if group_ID in self.dd_groups:
            return True
        if len(self.dd_groups) > 8:
            print("Maximum of 9 groups allowed for now.")
            return False
        colors = self.uistate.project.colors
        color = colors[(group_ID - 1) % len(colors)] if colors else "#808080"
        self.dd_groups[group_ID] = {
            "group_name": f"group {group_ID}",
            "color": color,
            "show": True,
            "rec_IDs": [],
            "sample": None,
        }
        print(f"group_ensure: created group {group_ID}")
        if hasattr(self, "usage"):
            self.usage(f"group_ensure created group_{group_ID}")
        self.group_save_dd()
        self.ensure_groups_list_header()
        self.group_controls_add(group_ID)
        if hasattr(self, "turn_heatmap_off"):
            self.turn_heatmap_off()
        if hasattr(self, "apply_statistical_test_if_active"):
            self.apply_statistical_test_if_active()
        return True

    def group_new(self):
        """Create the next free group ID (legacy; digit keys use group_ensure)."""
        print(f"Adding new group to dd_groups: {self.dd_groups}")
        if len(self.dd_groups) > 8:  # TODO: hardcoded max nr of groups: move to bw cfg
            print("Maximum of 9 groups allowed for now.")
            return
        group_ID = 1  # start at 1; no group_0
        if self.dd_groups:
            while group_ID in self.dd_groups.keys():
                group_ID += 1
        self.group_ensure(group_ID)

    def group_digit_assign(self, group_ID: int):
        """Digit-key path: ensure group exists, then toggle-assign selection."""
        if not self.group_ensure(group_ID):
            return
        if hasattr(self, "usage"):
            self.usage(f"group_digit_assign → group_{int(group_ID)}")
        self.group_selection(group_ID)

    def group_remove_last_empty(self):
        if not self.dd_groups:
            print("No groups to remove.")
            return
        last_group_ID = max(self.dd_groups.keys())
        if self.dd_groups[last_group_ID]["rec_IDs"]:
            print(f"{last_group_ID} is not empty.")
            return
        self.group_remove(last_group_ID)

    def group_remove_last(self):
        if self.dd_groups:
            last_group_ID = max(self.dd_groups.keys())
            self.group_remove(last_group_ID)

    def group_remove(self, group_ID=None):
        if group_ID is None:
            self.uiplot.unPlotGroup()  # all
            self.dd_groups = {}
            self.group_cache_purge()
            self.group_controls_remove()
        else:
            if group_ID in self.dd_groups:
                self.uiplot.unPlotGroup(group_ID)  # all levels
                del self.dd_groups[group_ID]
            self.group_cache_purge([group_ID])  # will also unplot per level
            self.group_controls_remove(group_ID)
        self.group_save_dd()
        self.refresh_samples()  # 3.4.3: group removal must trigger sample refresh
        if hasattr(self, "apply_statistical_test_if_active"):
            self.apply_statistical_test_if_active()

    def group_rename(self, group_ID, new_group_name):
        if not new_group_name:
            return
        if new_group_name in [group["group_name"] for group in self.dd_groups.values()]:
            print(f"Group name {new_group_name} already exists.")
        elif re.match(r"^[a-zA-Z0-9_ -]+$", str(new_group_name)) is not None:  # True if valid filename
            self.dd_groups[group_ID]["group_name"] = new_group_name
            self.group_save_dd()  # syncs df_project["groups"] column via group_update_dfp
            self.groupControlsRefresh()
            # Legend / artist keys bake in group_name at addGroup time; graphRefresh
            # does not re-plot groups already in dict_group_labels — rebuild this group.
            self._replot_group_after_rename(group_ID)
            if hasattr(self, "clear_formal_test_results"):
                self.clear_formal_test_results()
            if hasattr(self, "apply_statistical_test_if_active"):
                self.apply_statistical_test_if_active()
            if hasattr(self, "update_show"):
                self.update_show()
            if hasattr(self, "graphRefresh"):
                self.graphRefresh()
            if hasattr(self, "mouseoverUpdate"):
                self.mouseoverUpdate()
        else:
            print(f"Group name {new_group_name} is not a valid name.")

    def _replot_group_after_rename(self, group_ID):
        """Drop and re-add plot artists so output legend uses the new group name."""
        if not hasattr(self, "uiplot") or group_ID not in self.dd_groups:
            return
        dict_group = self.dd_groups[group_ID]
        self.uiplot.unPlotGroup(group_ID)  # all levels; keys contain old name
        if not dict_group.get("rec_IDs"):
            return
        level = self.uistate.stat_test.buttonGroup_test_n
        if not hasattr(self, "get_dfgroupmean"):
            return
        df_groupmean = self.get_dfgroupmean(group_ID, level=level)
        if df_groupmean is None or getattr(df_groupmean, "empty", False):
            return
        x_pos = plot_series.pp_group_x_position(self.dd_groups, group_ID)
        ydf = self.V2mV(df_groupmean) if hasattr(self, "V2mV") else df_groupmean
        self.uiplot.addGroup(group_ID, dict_group, ydf, x_pos=x_pos, level=level)

    # ------------------------------------------------------------------
    # Test Set Create / remove / rename (modeled exactly on groups but using set_ID and default names 'set N')
    # ------------------------------------------------------------------

    def testset_new(self):
        print(f"Adding new test set to dd_testsets: {self.dd_testsets}")
        if len(self.dd_testsets) > 8:  # TODO: hardcoded max nr of sets: move to bw cfg
            print("Maximum of 9 test sets allowed for now.")
            return
        set_ID = 1  # start at 1; no set_0
        if self.dd_testsets:
            while set_ID in self.dd_testsets.keys():
                set_ID += 1
        selected_sweeps = sorted(self.uistate.plot.x_select.get("output", set()))
        if not selected_sweeps:
            print("No sweeps selected for test set.")
            return
        colors = self.uistate.project.colors or ["#808080"]
        self.dd_testsets[set_ID] = {
            "set_name": f"set {set_ID}",
            "color": colors[(set_ID - 1) % len(colors)],
            "show": True,
            "sweeps": selected_sweeps,
            "description": f"Test set {set_ID} created from selection",
        }
        self.testset_save_dd()
        self.ensure_testsets_list_header()
        self.testset_controls_add(set_ID)
        print(f"Created test set {set_ID} with {len(selected_sweeps)} sweeps: {selected_sweeps}")
        if hasattr(self, "usage"):
            self.usage(f"testset_new set_{set_ID} n_sweeps={len(selected_sweeps)}")
        self.refresh_samples()  # ensure sample data for new test set
        # Changing test sets requires fresh statistical markers (invalidate cached results so graph safeguard does not redraw stale)
        if hasattr(self, "clear_formal_test_results"):
            self.clear_formal_test_results()
        self.graphRefresh()
        # graphRefresh (default) re-evaluates test via update_test() (recomputes + show_test_markers) after draw

    def testset_remove_last(self):
        if self.dd_testsets:
            last_set_ID = max(self.dd_testsets.keys())
            self.testset_remove(last_set_ID)

    def testset_remove(self, set_ID=None):
        if set_ID is None:
            self.dd_testsets = {}
            self.testset_controls_remove()
            if hasattr(self, "usage"):
                self.usage("testset_remove all")
        else:
            if set_ID in self.dd_testsets:
                del self.dd_testsets[set_ID]
            self.testset_controls_remove(set_ID)
            if hasattr(self, "usage"):
                self.usage(f"testset_remove set_{set_ID}")
        self.testset_save_dd()
        self.refresh_samples()  # testset CRUD must keep samples in sync
        # Test set removal requires fresh markers for remaining sets
        if hasattr(self, "clear_formal_test_results"):
            self.clear_formal_test_results()
        self.graphRefresh()
        # graphRefresh (default) re-evaluates test via update_test() (recomputes + show_test_markers) after draw

    def testset_rename(self, set_ID, new_set_name):
        if new_set_name in [s["set_name"] for s in self.dd_testsets.values()]:
            print(f"Test set name {new_set_name} already exists.")
        elif re.match(r"^[a-zA-Z0-9_ -]+$", str(new_set_name)) is not None:  # True if valid filename
            self.dd_testsets[set_ID]["set_name"] = new_set_name
            self.testset_save_dd()
            self.testsetControlsRefresh()
            if hasattr(self, "usage"):
                self.usage(f"testset_rename set_{set_ID}")
            self.graphRefresh()
            # graphRefresh (default) re-evaluates test via update_test() (refreshes table with updated name)
        else:
            print(f"Test set name {new_set_name} is not a valid name.")

    # ------------------------------------------------------------------
    # Recording ↔ group assignment
    # ------------------------------------------------------------------

    def group_rec_assign(self, rec_ID, group_ID):
        if rec_ID not in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].append(rec_ID)
            self.uiplot.unPlotGroup(group_ID)  # all levels stale after membership change
            self.group_cache_purge([group_ID])  # all levels
            level = self.uistate.stat_test.buttonGroup_test_n
            df_groupmean = self.get_dfgroupmean(group_ID, level=level)
            x_pos = plot_series.pp_group_x_position(self.dd_groups, group_ID)
            self.uiplot.addGroup(group_ID, dict_group, self.V2mV(df_groupmean), x_pos=x_pos, level=level)
            # v0.16: membership change may affect active statistical test
            if hasattr(self, "apply_statistical_test_if_active"):
                self.apply_statistical_test_if_active()

    def group_rec_ungroup(self, rec_ID, group_ID):
        if rec_ID in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].remove(rec_ID)
            self.uiplot.unPlotGroup(group_ID)  # all levels stale
            self.group_cache_purge([group_ID])  # all levels
            level = self.uistate.stat_test.buttonGroup_test_n
            df_groupmean = self.get_dfgroupmean(group_ID, level=level)
            if self.dd_groups[group_ID]["rec_IDs"]:
                x_pos = plot_series.pp_group_x_position(self.dd_groups, group_ID)
                self.uiplot.addGroup(group_ID, dict_group, self.V2mV(df_groupmean), x_pos=x_pos, level=level)
            # v0.16: membership change may affect active statistical test
            if hasattr(self, "apply_statistical_test_if_active"):
                self.apply_statistical_test_if_active()

    @staticmethod
    def _norm_rec_id(val) -> str:
        """Normalize recording IDs for robust equality (int/float/str/numpy)."""
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        try:
            if hasattr(val, "item"):
                val = val.item()
        except Exception:
            pass
        if isinstance(val, float):
            if val.is_integer():
                return str(int(val))
            return str(val)
        if isinstance(val, int):
            return str(val)
        s = str(val).strip()
        if re.fullmatch(r"-?\d+\.0+", s):
            return s.split(".", 1)[0]
        return s

    def _project_table_row_ids(self, row_indices: list[int]) -> list:
        """IDs for view/model rows (model may be sorted independently of df_project)."""
        model_df = getattr(getattr(self, "tablemodel", None), "_data", None)
        src = model_df if model_df is not None and not getattr(model_df, "empty", True) else self.get_df_project()
        out = []
        n = len(src)
        for i in row_indices:
            if 0 <= i < n:
                out.append(src.iloc[i]["ID"])
        return out

    def _rows_for_rec_ids(self, df_p, rec_ids: list, preferred_order: list[int] | None = None) -> list[int]:
        """Map rec IDs → row indices in the *displayed* project table (sorted model when present).

        Must not use unsorted df_project positions for QTableView selection — after a column
        sort, model row ≠ df_project row and selection/lineEdits desync.
        """
        if hasattr(self, "_model_rows_for_rec_ids"):
            hits = self._model_rows_for_rec_ids(rec_ids)
            if hits:
                return hits
        # Fallback: map against df_p (or model) by normalized ID
        model_df = getattr(getattr(self, "tablemodel", None), "_data", None)
        src = model_df if model_df is not None and not getattr(model_df, "empty", True) and "ID" in getattr(model_df, "columns", []) else df_p
        if src is None or getattr(src, "empty", True) or "ID" not in src.columns:
            n = len(df_p) if df_p is not None else 0
            if preferred_order:
                return [int(i) for i in preferred_order if 0 <= int(i) < n]
            return []
        order = {self._norm_rec_id(rid): n for n, rid in enumerate(rec_ids)}
        to_select = sorted(
            (i for i, rid in enumerate(src["ID"].tolist()) if self._norm_rec_id(rid) in order),
            key=lambda i: order[self._norm_rec_id(src["ID"].iloc[i])],
        )
        if to_select:
            return to_select
        n = len(src)
        if preferred_order:
            return [int(i) for i in preferred_order if 0 <= int(i) < n]
        return []

    def _select_project_table_rows(self, row_indices: list[int]) -> None:
        """Select exact *model* rows in the project table; no last-row fallback.

        Blocks selectionChanged side effects. row_indices must be table-model rows
        (from _rows_for_rec_ids / _model_rows_for_rec_ids), not unsorted df_project indices.
        """
        model_df = getattr(getattr(self, "tablemodel", None), "_data", None)
        n = len(model_df) if model_df is not None else len(self.get_df_project())
        to_select = [int(i) for i in row_indices if 0 <= int(i) < n]
        self.uistate.plot.list_idx_select_recs = to_select

        was_updating = getattr(self, "updating_tableProj", False)
        self.updating_tableProj = True
        try:
            self.tableProj.clearSelection()
            if not to_select:
                return
            selection = QtCore.QItemSelection()
            col_last = max(0, self.tablemodel.columnCount(QtCore.QModelIndex()) - 1)
            for idx in to_select:
                top_left = self.tablemodel.index(idx, 0)
                bottom_right = self.tablemodel.index(idx, col_last)
                if top_left.isValid() and bottom_right.isValid():
                    selection.select(top_left, bottom_right)
            sm = self.tableProj.selectionModel()
            sm.select(
                selection,
                QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows,
            )
            # Keyboard nav uses currentIndex, not selection alone — without this,
            # arrow keys jump from row 0 after a model reset / programmatic select.
            current_row = to_select[-1]
            current = self.tablemodel.index(current_row, 0)
            if current.isValid():
                sm.setCurrentIndex(current, QtCore.QItemSelectionModel.NoUpdate)
            self.tableProj.scrollTo(current if current.isValid() else self.tablemodel.index(to_select[0], 0))
            self.tableProj.setFocus()
            self.uistate.plot.list_idx_select_recs = to_select
        finally:
            self.updating_tableProj = was_updating

    def group_selection(self, group_ID):
        """Toggle group membership for the current project-table selection.

        Conserves multi-selection across table model resets (setData / unsort).
        """
        if group_ID not in self.dd_groups:
            if not self.group_ensure(group_ID):
                return
        # Prefer live Qt selection; fall back to uistate (e.g. keyboard shortcut via menu).
        selected_indices: list[int] = []
        if hasattr(self, "tableProj") and self.tableProj.selectionModel() is not None:
            selected_indices = sorted({idx.row() for idx in self.tableProj.selectionModel().selectedRows()})
        if not selected_indices:
            selected_indices = [int(i) for i in (self.uistate.plot.list_idx_select_recs or [])]
        if not selected_indices:
            print("No recordings selected.")
            return

        selected_rec_IDs = self._project_table_row_ids(selected_indices)
        if not selected_rec_IDs:
            print("No recordings selected.")
            return

        # Membership lists may mix str/int IDs — compare as str
        member_ids = {str(r) for r in self.dd_groups[group_ID]["rec_IDs"]}
        all_in_group = all(str(rec_ID) in member_ids for rec_ID in selected_rec_IDs)
        if all_in_group:
            for rec_ID in selected_rec_IDs:
                self.group_rec_ungroup(rec_ID, group_ID)
            action = "ungroup"
        else:
            for rec_ID in selected_rec_IDs:
                self.group_rec_assign(rec_ID, group_ID)
            action = "assign"
        if hasattr(self, "usage"):
            self.usage(f"group_selection {action} group_{group_ID} n={len(selected_rec_IDs)}")

        # Persist groups + refresh table without intermediate last-row selection restore.
        self.uistate.plot.list_idx_select_recs = list(selected_indices)
        self.group_save_dd(restore_selection=False)

        dfp = self.get_df_project()
        to_select = self._rows_for_rec_ids(dfp, selected_rec_IDs, preferred_order=selected_indices)
        self._select_project_table_rows(to_select)

        # addGroup creates artists with set_visible(False); visibility is applied only
        # in update_show. selection restore blocks selectionChanged, so we must call it.
        if hasattr(self, "update_recs2plot"):
            self.update_recs2plot()
        if hasattr(self, "update_show"):
            self.update_show()

        if hasattr(self, "clear_formal_test_results"):
            self.clear_formal_test_results()
        self.graphRefresh()

    # ------------------------------------------------------------------
    # Test Set tagging (Phase 1)
    # ------------------------------------------------------------------
    def add_to_data_set(self):
        """Create a test set from the current output sweep selection (x_select).

        Does not require a recording selection: test sets are project-level sweep
        lists (usable with groups-only output view).
        """
        if not self.uistate.plot.x_select.get("output"):
            print("No sweeps selected. Drag on output graph or use sweep range controls first.")
            return
        self.testset_new()  # persists, UI controls, refresh_samples, graphRefresh

    # ------------------------------------------------------------------
    # Sample designation (Phase 3.1)
    # ------------------------------------------------------------------
    def set_group_sample(self, rec_ID: str | None = None):
        if rec_ID is None:
            if len(self.uistate.plot.list_idx_select_recs) != 1:
                return
            df_p = self.get_df_project()
            idx = self.uistate.plot.list_idx_select_recs[0]
            rec_ID = str(df_p.iloc[idx]["ID"]) if not df_p.empty else None
            if rec_ID is None:
                return
            for g in self.get_groupsOfRec(rec_ID):
                self.dd_groups[g]["sample"] = None
            self.group_save_dd()
            self.refresh_samples()
            return
        rec_str = str(rec_ID)
        group_IDs = self.get_groupsOfRec(rec_ID)
        if not group_IDs:
            return
        is_current_for_all = all(str(self.dd_groups.get(g, {}).get("sample")) == rec_str for g in group_IDs)
        if is_current_for_all:
            for g in group_IDs:
                self.dd_groups[g]["sample"] = None
        else:
            for g in group_IDs:
                self.dd_groups[g]["sample"] = rec_str
        self.group_save_dd()
        self.refresh_samples()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def group_cache_purge(self, group_IDs=None, levels=None):  # clear cache so that a new group mean is calculated
        if hasattr(self, "turn_heatmap_off"):
            self.turn_heatmap_off()
        if not self.dict_group_means and not getattr(self, "dict_global_units", None):
            print("No groups to purge.")
            return
        if not group_IDs:  # if no group IDs are passed purge all groups
            # collect unique group ids from tuple keys too
            gids = set()
            for k in list(self.dict_group_means.keys()):
                if isinstance(k, tuple) and len(k) >= 1:
                    gids.add(k[0])
                else:
                    gids.add(k)
            group_IDs = list(gids)
            if hasattr(self, "dict_global_units"):
                self.dict_global_units.clear()
        print(f"group_cache_purge: {group_IDs}, levels={levels}")
        for group_ID in group_IDs:
            # remove level-aware keys
            keys_to_del = []
            for k in list(self.dict_group_means.keys()):
                if isinstance(k, tuple) and k[0] == group_ID:
                    if levels is None or k[1] in levels:
                        keys_to_del.append(k)
                elif k == group_ID and (levels is None or "recording" in (levels or [])):
                    keys_to_del.append(k)
            for k in keys_to_del:
                if k in self.dict_group_means:
                    del self.dict_group_means[k]

                # destroy corresponding plot artists at the same place we destroy the df cache (per-level)
                try:
                    lvl = k[1] if isinstance(k, tuple) else "recording"
                    self.uiplot.unPlotGroup(group_ID, level=lvl)
                except (NameError, AttributeError, TypeError):
                    pass

            # delete possible parquet variants
            base = f"{self.dict_folders['cache']}/group_{group_ID}"
            for lvl in ([""] + [f"_{l}" for l in (levels or ["recording", "slice", "subject"])]):
                p = Path(f"{base}{lvl}_mean.parquet")
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass

            # also purge samples
            group_name = self.dd_groups.get(group_ID, {}).get("group_name", f"group_{group_ID}")
            self.group_sample_cache_purge(group_ID)
            if hasattr(self, "dd_group_samples") and group_ID in self.dd_group_samples:
                del self.dd_group_samples[group_ID]

    def group_sample_cache_purge(self, group_ID=None):
        list_group_IDs_to_purge = [group_ID] if group_ID is not None else list(self.dd_groups.keys())
        cache_dir = Path(self.dict_folders["cache"])
        for group_ID in list_group_IDs_to_purge:
            group_name = self.dd_groups.get(group_ID, {}).get("group_name", f"group_{group_ID}")
            for sample_file in cache_dir.glob(f"{group_name}_sample_*.parquet"):
                if sample_file.exists():
                    sample_file.unlink()

    def clear_group_level(self, group_ID, level=None):
        """Clear df cache and plot artists for a specific level (or all if level=None).

        This is the convenience for level-granular staleness.
        """
        levels = [level] if level else None
        self.group_cache_purge([group_ID], levels=levels)
        try:
            self.uiplot.unPlotGroup(group_ID, level=level)
        except (NameError, AttributeError, Exception):
            pass

    # ------------------------------------------------------------------
    # Sample refresh (Phase 3.4.3 - full implementation)
    # ------------------------------------------------------------------
    def refresh_samples(self):
        """Dedicated refresh for samples. Loops over groups with non-None "sample"
        key and calls self.get_ddgroup_sample(g) (this triggers build/persist
        of <group_name>_sample.parquet with 'stim' column + t=0). Sets
        self.uistate.plot.sample_dirty=True so next graphRefresh (which receives
        dd_shown_samples from ui.py) will redraw the overlay via sample_overlay.
        """
        if not hasattr(self, "dd_group_samples"):
            self.dd_group_samples = {}
        for group_ID, gdict in self.dd_groups.items():
            if gdict.get("sample") is not None:
                # always clear in-memory cache to avoid stale dd_group_samples
                # when new test sets are added (forces rebuild from per-test
                # parquet or fresh computation using current shown testsets)
                if group_ID in self.dd_group_samples:
                    del self.dd_group_samples[group_ID]

                if self.config.verbose:
                    print(f"refresh_samples: rebuilding sample for group_ID={group_ID}")
                self.get_ddgroup_sample(group_ID)
                self.group_sample_cache_purge(group_ID)

        # ensure redraw on next graphRefresh
        self.uistate.plot.sample_dirty = True

    # ------------------------------------------------------------------
    # Qt widget controls
    # ------------------------------------------------------------------

    def ensure_groups_list_header(self):
        """Bold 'Groups' header above the group checkbox list (once)."""
        existing = getattr(self, "_groups_list_header", None)
        if existing is not None:
            return
        if hasattr(self, "centralwidget"):
            found = self.centralwidget.findChild(QtWidgets.QLabel, "label_groups_header")
            if found is not None:
                self._groups_list_header = found
                return
        lbl = QtWidgets.QLabel("Groups")
        lbl.setObjectName("label_groups_header")
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.verticalLayoutGroups.insertWidget(0, lbl)
        self._groups_list_header = lbl

    def setup_group_digit_shortcuts(self):
        """Permanent digit 1–9 actions: ensure group N exists, then assign selection.

        Shortcuts are WindowShortcut; SelectionMixin / event filter still block
        digits while focus is in text-entry widgets (stim µA, etc.).
        """
        if getattr(self, "_group_digit_shortcuts_ready", False):
            return
        for n in range(1, 10):
            action = QtWidgets.QAction(f"Assign selection to group {n}")
            action.setObjectName(f"actionGroupDigit_{n}")
            action.setShortcut(f"{n}")
            action.setShortcutContext(QtCore.Qt.WindowShortcut)
            action.triggered.connect(lambda checked=False, gid=n: self.group_digit_assign(gid))
            self.menuGroups.addAction(action)
            setattr(self, f"actionGroupDigit_{n}", action)
        self._group_digit_shortcuts_ready = True

    def group_controls_add(self, group_ID):  # Checkbox for showing group (digit shortcuts are global)
        group_name = self.dd_groups[group_ID]["group_name"]
        dict_group = self.dd_groups.get(group_ID)
        if not dict_group:
            print(f" - {group_ID} not found in self.dd_groups:")
            print(self.dd_groups)
            return
        self.ensure_groups_list_header()
        color = dict_group["color"]
        str_ID = str(group_ID)

        row = QtWidgets.QWidget()
        row.setObjectName(f"group_row_{str_ID}")
        row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        checkbox = CustomCheckBox(group_ID)
        checkbox.rightClicked.connect(self.triggerGroupRename)
        checkbox.setObjectName(f"checkBox_group_{str_ID}")
        checkbox.setText(f"{str_ID}. {group_name}")
        checkbox.setStyleSheet(f"background-color: {color};")
        checkbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        checkbox.setMinimumWidth(0)
        checkbox.setMaximumWidth(16777215)
        show = dict_group.get("show", True)
        if isinstance(show, str):
            checked = show.strip().lower() in ("true", "1", "yes")
        else:
            checked = bool(show)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(lambda state, gid=group_ID: self.groupCheckboxChanged(state, gid))

        remove_btn = EntityRemoveButton(group_ID, group_name, object_prefix="group_remove")
        remove_btn.removeRequested.connect(self.triggerRemoveGroup)
        remove_btn.hoverEntered.connect(self._on_group_remove_hover_enter)
        remove_btn.hoverLeft.connect(self._on_entity_remove_hover_leave)

        row_layout.addWidget(checkbox, 1)
        row_layout.addWidget(remove_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.verticalLayoutGroups.addWidget(row)
        self.new_checkbox = checkbox
        setattr(self, f"checkBox_group_{str_ID}", checkbox)
        setattr(self, f"group_row_{str_ID}", row)

    def group_controls_remove(self, group_ID=None):
        if group_ID is None:  # if group_ID is not provided, remove all group controls
            for i in range(1, 10):  # clear group controls 1-9
                self.group_controls_remove(i)
        else:
            str_ID = str(group_ID)
            row_name = f"group_row_{str_ID}"
            row = None
            if hasattr(self, "centralwidget"):
                row = self.centralwidget.findChild(QtWidgets.QWidget, row_name)
            if row is None:
                row = getattr(self, row_name, None)
            if row is not None:
                print(f"Removing widget {row_name}")
                row.deleteLater()
            else:
                # Pre–row-widget bare checkbox
                widget_name = f"checkBox_group_{str_ID}"
                widget = self.centralwidget.findChild(QtWidgets.QWidget, widget_name) if hasattr(self, "centralwidget") else None
                if widget:
                    print(f"Removing widget {widget_name}")
                    widget.deleteLater()
            for attr_name in (f"checkBox_group_{str_ID}", f"group_row_{str_ID}"):
                if hasattr(self, attr_name):
                    delattr(self, attr_name)
            # Legacy per-group menu actions (pre–digit-global) if any remain
            action = getattr(self, f"actionAddTo_{str_ID}", None)
            if action is not None:
                self.menuGroups.removeAction(action)
                delattr(self, f"actionAddTo_{str_ID}")

    # ------------------------------------------------------------------
    # Test Set controls (mirrors group_controls_* but targets verticalLayoutTestSet)
    # ------------------------------------------------------------------

    def ensure_testsets_list_header(self):
        """Bold 'Test sets' header above the test set checkbox list (once)."""
        existing = getattr(self, "_testsets_list_header", None)
        if existing is not None:
            return
        if hasattr(self, "centralwidget"):
            found = self.centralwidget.findChild(QtWidgets.QLabel, "label_testsets_header")
            if found is not None:
                self._testsets_list_header = found
                return
        lbl = QtWidgets.QLabel("Test sets")
        lbl.setObjectName("label_testsets_header")
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.verticalLayoutTestSet.insertWidget(0, lbl)
        self._testsets_list_header = lbl

    def testsetControlsRefresh(self):
        self.ensure_testsets_list_header()
        self.testset_controls_remove()
        for set_ID in sorted(self.dd_testsets.keys()):
            print(f"testsetControlsRefresh, adding set_ID: {set_ID}")
            self.testset_controls_add(set_ID)

    def testset_controls_add(self, set_ID):
        dict_set = self.dd_testsets.get(set_ID)
        if not dict_set:
            print(f" - {set_ID} not found in self.dd_testsets:")
            print(self.dd_testsets)
            return
        self.ensure_testsets_list_header()
        set_name = dict_set["set_name"]
        color = dict_set["color"]
        str_ID = str(set_ID)

        row = QtWidgets.QWidget()
        row.setObjectName(f"testset_row_{str_ID}")
        row.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        checkbox = CustomCheckBox(set_ID)
        checkbox.rightClicked.connect(self.triggerTestSetRename)
        checkbox.setObjectName(f"checkBox_testset_{str_ID}")
        checkbox.setText(f"{str_ID}. {set_name}")
        checkbox.setStyleSheet(f"background-color: {color};")
        checkbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        checkbox.setMinimumWidth(0)
        checkbox.setMaximumWidth(16777215)
        show = dict_set.get("show", True)
        if isinstance(show, str):
            checked = show.strip().lower() in ("true", "1", "yes")
        else:
            checked = bool(show)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(lambda state, sid=set_ID: self.testsetCheckboxChanged(state, sid))

        remove_btn = EntityRemoveButton(set_ID, set_name, object_prefix="testset_remove")
        remove_btn.removeRequested.connect(self.triggerRemoveTestSet)
        remove_btn.hoverEntered.connect(self._on_testset_remove_hover_enter)
        remove_btn.hoverLeft.connect(self._on_entity_remove_hover_leave)

        row_layout.addWidget(checkbox, 1)
        row_layout.addWidget(remove_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.verticalLayoutTestSet.addWidget(row)
        self.new_testset_checkbox = checkbox
        setattr(self, f"checkBox_testset_{str_ID}", checkbox)
        setattr(self, f"testset_row_{str_ID}", row)

    def testset_controls_remove(self, set_ID=None):
        if set_ID is None:
            for i in range(1, 10):
                self.testset_controls_remove(i)
            return
        str_ID = str(set_ID)
        row_name = f"testset_row_{str_ID}"
        row = None
        if hasattr(self, "centralwidget"):
            row = self.centralwidget.findChild(QtWidgets.QWidget, row_name)
        if row is None:
            row = getattr(self, row_name, None)
        if row is not None:
            print(f"Removing widget {row_name}")
            row.deleteLater()
        else:
            widget_name = f"checkBox_testset_{str_ID}"
            widget = self.centralwidget.findChild(QtWidgets.QWidget, widget_name) if hasattr(self, "centralwidget") else None
            if widget:
                print(f"Removing widget {widget_name}")
                widget.deleteLater()
        for attr_name in (f"checkBox_testset_{str_ID}", f"testset_row_{str_ID}"):
            if hasattr(self, attr_name):
                delattr(self, attr_name)

    # ------------------------------------------------------------------
    # df_project sync
    # ------------------------------------------------------------------

    def group_update_dfp(self, rec_ID=None, reset=False, *, restore_selection: bool = True):
        # update dfp['groups'] based on dd_groups
        def group_list(rec_ID):
            list_rec_in_groups = []
            for group_ID, group_v in self.dd_groups.items():
                if rec_ID in group_v["rec_IDs"]:
                    name = group_v.get("group_name")
                    list_rec_in_groups.append(str(name) if name is not None else str(group_ID))
            return list_rec_in_groups

        df_p = self.get_df_project()
        if reset:
            df_p["groups"] = " "
        else:
            if rec_ID is not None:
                list_rec_in_groups = group_list(rec_ID)
                df_p.loc[df_p["ID"] == rec_ID, "groups"] = ", ".join(sorted(list_rec_in_groups)) if list_rec_in_groups else " "
            else:
                for i, row in df_p.iterrows():
                    rec_ID = row["ID"]
                    list_rec_in_groups = group_list(rec_ID)
                    df_p.at[i, "groups"] = ", ".join(sorted(list_rec_in_groups)) if list_rec_in_groups else " "
        # set_df_project always tableUpdate(restore=False); optional restore for callers.
        self.set_df_project(df_p)
        if restore_selection:
            self.tableUpdate(restore_selection=True)
