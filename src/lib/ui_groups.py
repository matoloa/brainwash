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
    """Mixin that provides all group-management behaviour for UIsub."""

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
    # Recording ↔ group assignment
    # ------------------------------------------------------------------

    def group_rec_assign(self, rec_ID, group_ID):
        if rec_ID not in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].append(rec_ID)
            self.group_cache_purge([group_ID])
            df_groupmean = self.get_dfgroupmean(group_ID)
            uiplot.addGroup(group_ID, dict_group, df_groupmean)

    def group_rec_ungroup(self, rec_ID, group_ID):
        if rec_ID in self.dd_groups[group_ID]["rec_IDs"]:
            dict_group = self.dd_groups[group_ID]
            dict_group["rec_IDs"].remove(rec_ID)
            self.group_cache_purge([group_ID])
            df_groupmean = self.get_dfgroupmean(group_ID)
            if self.dd_groups[group_ID]["rec_IDs"]:
                uiplot.addGroup(group_ID, dict_group, df_groupmean)

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
                uiplot.addGroup(group_ID, self.dd_groups[group_ID], self.get_dfgroupmean(group_ID))

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
            QtWidgets.QAction(f"Add selection to {group_name}", self),
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
    # df_project sync
    # ------------------------------------------------------------------

    def group_update_dfp(self, rec_ID=None, reset=False):
        # update dfp['groups'] based on dd_groups
        def group_list(rec_ID):
            list_rec_in_groups = []
            for group_ID, group_v in self.dd_groups.items():
                if rec_ID in group_v["rec_IDs"]:
                    list_rec_in_groups.append(group_v["group_name"])
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
