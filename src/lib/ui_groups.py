# ui_groups.py
# GroupMixin — group management methods extracted from UIsub (Phase 5 refactor).
# These methods operate on dd_groups / df_project and emit refresh signals.
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import ui_groups
#   ui_groups.uistate       = uistate
#   ui_groups.config        = config
#   ui_groups.uiplot        = uiplot
#   ui_groups.CustomCheckBox = CustomCheckBox

from __future__ import annotations

import pickle
import re
from pathlib import Path

from PyQt5 import QtCore, QtWidgets

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]
CustomCheckBox = None  # type: ignore[assignment]


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
            return dict_groups
        return {}

    def group_save_dd(
        self, dd_groups=None
    ):  # dd_groups is a dict of dicts: {group_ID (int): {group_name: str, color: str, show: bool, rec_IDs: [str]}}
        self.group_update_dfp()
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

    def get_groupsOfRec(self, rec_ID):  # returns a set of all 'group ID' that have rec_ID in their 'rec_IDs' list
        return list([key for key, value in self.dd_groups.items() if rec_ID in value["rec_IDs"]])

    # ------------------------------------------------------------------
    # Create / remove
    # ------------------------------------------------------------------

    def group_new(self):
        print(f"Adding new group to dd_groups: {self.dd_groups}")
        if len(self.dd_groups) > 8:  # TODO: hardcoded max nr of groups: move to bw cfg
            print("Maximum of 9 groups allowed for now.")
            return
        group_ID = 1  # start at 1; no group_0
        if self.dd_groups:
            while group_ID in self.dd_groups.keys():
                group_ID += 1
        self.dd_groups[group_ID] = {
            "group_name": f"group {group_ID}",
            "color": uistate.colors[group_ID - 1],
            "show": "True",
            "rec_IDs": [],
            "sample": None,
        }
        self.group_save_dd()
        self.group_controls_add(group_ID)

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
            self.dd_groups = {}
            self.group_cache_purge()
            self.group_controls_remove()
        else:
            if group_ID in self.dd_groups:
                del self.dd_groups[group_ID]
            self.group_cache_purge([group_ID])
            self.group_controls_remove(group_ID)
        self.group_save_dd()

    def group_rename(self, group_ID, new_group_name):
        if new_group_name in [group["group_name"] for group in self.dd_groups.values()]:
            print(f"Group name {new_group_name} already exists.")
        elif re.match(r"^[a-zA-Z0-9_ -]+$", str(new_group_name)) is not None:  # True if valid filename
            self.dd_groups[group_ID]["group_name"] = new_group_name
            self.group_save_dd()
            self.groupControlsRefresh()
        else:
            print(f"Group name {new_group_name} is not a valid name.")

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
        selected_sweeps = sorted(uistate.x_select.get("output", set()))
        if not selected_sweeps:
            print("No sweeps selected for test set.")
            return
        self.dd_testsets[set_ID] = {
            "set_name": f"set {set_ID}",
            "color": uistate.colors[set_ID - 1 % len(uistate.colors)],
            "show": True,
            "sweeps": selected_sweeps,
            "description": f"Test set {set_ID} created from selection",
        }
        self.testset_save_dd()
        self.testset_controls_add(set_ID)
        print(f"Created test set {set_ID} with {len(selected_sweeps)} sweeps: {selected_sweeps}")
        self.graphRefresh()

    def testset_remove_last_empty(self):
        if not self.dd_testsets:
            print("No test sets to remove.")
            return
        last_set_ID = max(self.dd_testsets.keys())
        if self.dd_testsets[last_set_ID]["sweeps"]:
            print(f"{last_set_ID} is not empty.")
            return
        self.testset_remove(last_set_ID)

    def testset_remove_last(self):
        if self.dd_testsets:
            last_set_ID = max(self.dd_testsets.keys())
            self.testset_remove(last_set_ID)

    def testset_remove(self, set_ID=None):
        if set_ID is None:
            self.dd_testsets = {}
            self.testset_controls_remove()
        else:
            if set_ID in self.dd_testsets:
                del self.dd_testsets[set_ID]
            self.testset_controls_remove(set_ID)
        self.testset_save_dd()
        self.graphRefresh()

    def testset_rename(self, set_ID, new_set_name):
        if new_set_name in [s["set_name"] for s in self.dd_testsets.values()]:
            print(f"Test set name {new_set_name} already exists.")
        elif re.match(r"^[a-zA-Z0-9_ -]+$", str(new_set_name)) is not None:  # True if valid filename
            self.dd_testsets[set_ID]["set_name"] = new_set_name
            self.testset_save_dd()
            self.testsetControlsRefresh()
            self.graphRefresh()
        else:
            print(f"Test set name {new_set_name} is not a valid name.")

    # ------------------------------------------------------------------
    # Recording ↔ group assignment
    # ------------------------------------------------------------------

    def group_rec_assign(self, rec_ID, group_ID):
        if rec_ID not in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].append(rec_ID)
            self.group_cache_purge([group_ID])
            df_groupmean = self.get_dfgroupmean(group_ID)
            x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
            uiplot.addGroup(group_ID, dict_group, self.V2mV(df_groupmean), x_pos=x_pos)

    def group_rec_ungroup(self, rec_ID, group_ID):
        if rec_ID in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].remove(rec_ID)
            self.group_cache_purge([group_ID])
            df_groupmean = self.get_dfgroupmean(group_ID)
            if self.dd_groups[group_ID]["rec_IDs"]:
                x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
                uiplot.addGroup(group_ID, dict_group, self.V2mV(df_groupmean), x_pos=x_pos)

    def group_selection(self, group_ID):
        dfp = self.get_df_project()
        if uistate.df_recs2plot is None:
            print("No parsed files selected.")
            # TODO: set selection to clicked group
            return
        selected_rec_IDs = dfp.loc[uistate.list_idx_select_recs, "ID"].tolist()  # selected rec_IDs
        all_in_group = all(rec_ID in self.dd_groups[group_ID]["rec_IDs"] for rec_ID in selected_rec_IDs)
        if all_in_group:  # If all selected_rec_IDs are in the group_ID, ungroup them
            for rec_ID in selected_rec_IDs:
                self.group_rec_ungroup(rec_ID, group_ID)
        else:  # Otherwise, add all selected_rec_IDs to the group_ID
            for rec_ID in selected_rec_IDs:
                self.group_rec_assign(rec_ID, group_ID)
        self.group_save_dd()
        self.set_df_project(dfp)
        self.tableUpdate()
        self.graphRefresh()

    # ------------------------------------------------------------------
    # Test Set tagging (Phase 1)
    # ------------------------------------------------------------------
    def add_to_data_set(self):
        """Replaces previous compare stub. Captures current sweep selection and creates a new Test Set (set_ID + default name 'set N')."""
        if not uistate.list_idx_select_recs:
            print("No recording selected for test set.")
            return
        if not uistate.x_select.get("output"):
            print("No sweeps selected. Drag on output graph or use sweep range controls first.")
            return
        self.testset_new()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def group_cache_purge(self, group_IDs=None):  # clear cache so that a new group mean is calculated
        if not self.dict_group_means:
            print("No groups to purge.")
            return
        if not group_IDs:  # if no group IDs are passed purge all groups
            group_IDs = list(self.dict_group_means.keys())
        print(f"group_cache_purge: {group_IDs}, len(group): {len(group_IDs)}")
        for group_ID in group_IDs:
            if group_ID in self.dict_group_means:
                del self.dict_group_means[group_ID]
            path_group_mean_cache = Path(f"{self.dict_folders['cache']}/group_{group_ID}_mean.parquet")
            if path_group_mean_cache.exists:  # TODO: Upon adding a group, both of these conditions trigger. How?
                print(f"{path_group_mean_cache} found when checking for existence...")
                try:
                    path_group_mean_cache.unlink()
                    print("...and was successfully unlinked.")
                except FileNotFoundError:
                    print("...but NOT when attempting to unlink.")
            uiplot.unPlotGroup(group_ID)
            if group_ID in self.dd_groups and self.dd_groups[group_ID]["rec_IDs"]:
                x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
                uiplot.addGroup(group_ID, self.dd_groups[group_ID], self.V2mV(self.get_dfgroupmean(group_ID)), x_pos=x_pos)

    # ------------------------------------------------------------------
    # Qt widget controls
    # ------------------------------------------------------------------

    def group_controls_add(self, group_ID):  # Create menu for adding to group and checkbox for showing group
        group_name = self.dd_groups[group_ID]["group_name"]
        # print(f"group_controls_add, group_ID: {group_ID}, type: {type(group_ID)} group_name: {group_name}")
        dict_group = self.dd_groups.get(group_ID)
        if not dict_group:
            print(f" - {group_ID} not found in self.dd_groups:")
            print(self.dd_groups)
            return
        color = dict_group["color"]
        str_ID = str(group_ID)
        setattr(
            self,
            f"actionAddTo_{str_ID}",
            QtWidgets.QAction(f"Add selection to {group_name}"),
        )
        self.new_group_menu_item = getattr(self, f"actionAddTo_{str_ID}")
        self.new_group_menu_item.triggered.connect(lambda checked, add_group_ID=group_ID: self.group_selection(add_group_ID))
        self.new_group_menu_item.setShortcut(f"{str_ID}")
        self.menuGroups.addAction(self.new_group_menu_item)
        self.new_checkbox = CustomCheckBox(group_ID)
        self.new_checkbox.rightClicked.connect(self.triggerGroupRename)  # str_ID is passed by CustomCheckBox
        self.new_checkbox.setObjectName(f"checkBox_group_{str_ID}")
        self.new_checkbox.setText(f"{str_ID}. {group_name}")
        self.new_checkbox.setStyleSheet(f"background-color: {color};")  # Set the background color
        self.new_checkbox.setMaximumWidth(100)  # Set the maximum width
        self.new_checkbox.setChecked(bool(dict_group["show"]))
        self.new_checkbox.stateChanged.connect(lambda state, group_ID=group_ID: self.groupCheckboxChanged(state, group_ID))
        self.verticalLayoutGroups.addWidget(self.new_checkbox)

    def group_controls_remove(self, group_ID=None):
        if group_ID is None:  # if group_ID is not provided, remove all group controls
            for i in range(1, 10):  # clear group controls 1-9
                self.group_controls_remove(i)
        else:
            str_ID = str(group_ID)
            # Correctly identify the widget by its full object name used during creation
            widget_name = f"checkBox_group_{str_ID}"
            widget = self.centralwidget.findChild(QtWidgets.QWidget, widget_name)
            if widget:
                print(f"Removing widget {widget_name}")
                widget.deleteLater()
            # else:
            #     print(f"Widget {widget_name} not found.")
            # get the action named actionAddTo_{group} and remove it
            action = getattr(self, f"actionAddTo_{str_ID}", None)
            if action:
                self.menuGroups.removeAction(action)
                delattr(self, f"actionAddTo_{str_ID}")

    # ------------------------------------------------------------------
    # Test Set controls (mirrors group_controls_* but targets verticalLayoutTestSet,
    # uses set_ID, set_name, checkBox_testset_{ID}, and calls triggerTestSetRename)
    # ------------------------------------------------------------------

    def testsetControlsRefresh(self):
        self.testset_controls_remove()
        for set_ID in self.dd_testsets.keys():
            self.testset_controls_add(set_ID)

    def testset_controls_add(self, set_ID):  # Create checkbox for test set (modeled on group_controls_add)
        dict_set = self.dd_testsets.get(set_ID)
        if not dict_set:
            print(f" - {set_ID} not found in self.dd_testsets:")
            print(self.dd_testsets)
            return
        set_name = dict_set["set_name"]
        color = dict_set["color"]
        str_ID = str(set_ID)
        self.new_testset_checkbox = CustomCheckBox(set_ID)
        self.new_testset_checkbox.rightClicked.connect(self.triggerTestSetRename)  # set_ID is passed by CustomCheckBox
        self.new_testset_checkbox.setObjectName(f"checkBox_testset_{str_ID}")
        self.new_testset_checkbox.setText(f"{str_ID}. {set_name}")
        self.new_testset_checkbox.setStyleSheet(f"background-color: {color};")  # Set the background color
        self.new_testset_checkbox.setMaximumWidth(100)  # Set the maximum width
        self.new_testset_checkbox.setChecked(bool(dict_set.get("show", True)))
        self.new_testset_checkbox.stateChanged.connect(lambda state, set_ID=set_ID: self.testsetCheckboxChanged(state, set_ID))
        self.verticalLayoutTestSet.addWidget(self.new_testset_checkbox)
        setattr(self, f"checkBox_testset_{str_ID}", self.new_testset_checkbox)

    def testset_controls_remove(self, set_ID=None):
        if set_ID is None:  # if set_ID is not provided, remove all test set controls
            for i in range(1, 10):  # clear test set controls 1-9
                self.testset_controls_remove(i)
        else:
            str_ID = str(set_ID)
            # Correctly identify the widget by its full object name used during creation
            widget_name = f"checkBox_testset_{str_ID}"
            widget = self.centralwidget.findChild(QtWidgets.QWidget, widget_name)
            if widget:
                print(f"Removing widget {widget_name}")
                widget.deleteLater()
            attr_name = f"checkBox_testset_{str_ID}"
            if hasattr(self, attr_name):
                delattr(self, attr_name)

    # ------------------------------------------------------------------
    # df_project sync
    # ------------------------------------------------------------------

    def group_update_dfp(self, rec_ID=None, reset=False):
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
        self.set_df_project(df_p)
        self.tableFormat()
