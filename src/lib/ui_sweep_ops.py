# ui_sweep_ops.py
# SweepOpsMixin — sweep editing operations extracted from UIsub (Phase 5 refactor).
# These methods handle sweep selection validation, removal, reordering, and splitting.
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import ui_sweep_ops
#   ui_sweep_ops.uistate = uistate
#   ui_sweep_ops.config  = config
#   ui_sweep_ops.uiplot  = uiplot
#   ui_sweep_ops.confirm = confirm

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]
confirm = None  # type: ignore[assignment]


class SweepOpsMixin:
    """Mixin that provides all sweep-editing behaviour for UIsub."""

    # ------------------------------------------------------------------
    # Even / odd selection helper
    # ------------------------------------------------------------------

    def sweepsSelect(self, even: bool):
        if uistate.checkBox["EPSP_slope"]:
            ax = uistate.ax2
        else:
            ax = uistate.ax1
        uiplot.xDeselect(ax, reset=True)
        if len(uistate.list_idx_select_recs) == 0:
            return
        self.lineEdit_sweeps_range_from.setText("Even" if even else "Odd")
        self.lineEdit_sweeps_range_to.setText("")
        prow = self.get_prow()
        total_sweeps = prow["sweeps"]
        selected = {i for i in range(total_sweeps) if (i % 2 == 0) == even}
        uistate.x_select["output"] = selected
        print(f"Selected all {'even' if even else 'odd'}: {len(selected)} sweeps.")
        uiplot.update_axe_mean()

    # ------------------------------------------------------------------
    # Trigger slots (wired to menu / toolbar actions)
    # ------------------------------------------------------------------

    def triggerKeepSelectedSweeps(self):
        self.usage("triggerKeepSelectedSweeps")
        self.sweep_keep_selected()

    def triggerRemoveSelectedSweeps(self):
        self.usage("triggerRemoveSelectedSweeps")
        self.sweep_remove_selected()

    def triggerSplitBySelectedSweeps(self):
        self.usage("triggerSplitBySelectedSweeps")
        self.sweep_split_by_selected()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def sweep_selection_valid(self):
        n_recs = len(uistate.list_idx_select_recs)
        n_sweeps = len(uistate.x_select["output"])
        if not n_recs:
            print("No recordings selected")
            return False
        print(
            f"{n_recs} selected recording{'s' if n_recs != 1 else ''}: {uistate.list_idx_select_recs}"
        )
        if not n_sweeps:
            print("No sweeps selected")
            return False
        print(
            f"{n_sweeps} selected sweep{'s' if n_sweeps != 1 else ''}: {uistate.x_select['output']}"
        )
        return True

    def sweep_removal_valid_confirmed(self):
        if not self.sweep_selection_valid():
            return False
        # Confirm with the user before performing destructive removal across recordings
        selected_sweeps = (
            uistate.x_select.get("output")
            if isinstance(uistate.x_select, dict)
            else None
        )
        n_sweeps = len(selected_sweeps) if selected_sweeps else 0
        n_recs = len(uistate.list_idx_select_recs)
        title = "Remove sweeps"
        message = (
            f"Remove {n_sweeps} selected sweep{'s' if n_sweeps != 1 else ''}\n"
            f"from {n_recs} selected recording{'s' if n_recs != 1 else ''}?\n"
            "This action cannot be undone."
        )
        if not confirm(title=title, message=message):
            print("sweep_removal_valid_confirmed: cancelled by user")
            return False
        return True

    # ------------------------------------------------------------------
    # Core sweep manipulation
    # ------------------------------------------------------------------

    def sweep_shift_gaps(self, df, sweeps_removed):
        """Shifts all remaining sweeps down to close gaps after removal, e.g. removed {10, 11} → 12→10, 13→11, etc."""
        removed = np.array(
            sorted(sweeps_removed), dtype=np.int64
        )  # sorted array of removed sweep numbers
        s = df[
            "sweep"
        ].to_numpy()  # convert sweep column to numpy array for vectorized operations
        k = np.searchsorted(
            removed, s, side="right"
        )  # count how many removed sweeps are <= each sweep value
        df["sweep"] = (
            s - k
        )  # shift each sweep down by the count of removed sweeps before or equal to it
        return df  # return DataFrame with adjusted sweep numbering

    def sweep_remove_by_ID(self, rec_ID, selection=None):
        """
        Remove selected sweeps from the DATA FILE of a recording,
        renumbers remaining sweeps to a continuous sequence.
        Clears cached data for the recording.
        Parameters:
            rec_ID (str): The recording ID from which to remove sweeps.
        """
        self.usage("data_remove_sweeps_by_ID")
        p_row = self.df_project[self.df_project["ID"] == rec_ID].iloc[0]
        set_sweeps_to_remove = (
            selection if selection is not None else uistate.x_select["output"]
        )
        rec_name = p_row["recording_name"]
        df_data_copy = self.get_dfdata(p_row).copy()
        # check that selected sweeps exist in df_data
        sweeps_to_remove = set()
        for sweep in set_sweeps_to_remove:
            if sweep in df_data_copy["sweep"].values:
                sweeps_to_remove.add(sweep)
            else:
                print(f"Sweep {sweep} not found in recording '{rec_name}', skipping.")
        if not sweeps_to_remove:
            print(f"No valid sweeps to remove in recording '{rec_name}'.")
            return
        n_total_sweeps = p_row["sweeps"]
        print(
            f"Recording '{rec_name}': removing {len(sweeps_to_remove)} sweep{'s' if len(sweeps_to_remove) != 1 else ''} out of {n_total_sweeps}..."
        )
        print(f"Sweeps to remove: {sorted(sweeps_to_remove)}")

        df_data_filtered = df_data_copy[
            ~df_data_copy["sweep"].isin(sweeps_to_remove)
        ].reset_index(drop=True)  # remove selected sweeps
        print(
            f"Sweeps excluded, remaining sweeps: {df_data_filtered['sweep'].unique()}"
        )
        pruned_df = self.sweep_shift_gaps(
            df_data_filtered, sweeps_to_remove
        )  # renumber remaining sweeps to close gaps
        print(f"Gaps closed, remaining sweeps: {pruned_df['sweep'].unique()}")
        self.df2file(
            df=pruned_df, rec=rec_name, key="data"
        )  # overwrite data file with pruned data
        n_remaining_sweeps = len(pruned_df["sweep"].unique())
        df_project = self.get_df_project()
        df_project.loc[df_project["ID"] == rec_ID, "sweeps"] = (
            n_remaining_sweeps  # update sweeps count in df_project
        )
        self.save_df_project()
        print(
            f"Recording '{rec_name}': {n_remaining_sweeps} sweep{'s' if n_remaining_sweeps != 1 else ''} remain."
        )
        # clear cache files for the recording
        old_timepoints = self.dict_folders["timepoints"] / (rec_name + ".parquet")
        old_mean = self.dict_folders["cache"] / (rec_name + "_mean.parquet")
        old_filter = self.dict_folders["cache"] / (rec_name + "_filter.parquet")
        old_bin = self.dict_folders["cache"] / (rec_name + "_bin.parquet")
        old_output = self.dict_folders["cache"] / (rec_name + "_output.parquet")
        for old_file in [old_timepoints, old_mean, old_filter, old_bin, old_output]:
            if old_file.exists():
                old_file.unlink()
                if config.verbose:
                    print(f"Deleted cache file: {old_file}")
        return

    def sweep_keep_selected(self):
        # if selection is valid, invert it and call sweep_remove_selection (which clears selection)
        if not self.sweep_selection_valid():
            return
        n_sweeps_all = 0
        for rec_idx in (
            uistate.list_idx_select_recs
        ):  # get all sweeps from the longest selected recording
            p_row = self.df_project.iloc[rec_idx]
            n_sweeps = p_row["sweeps"]
            if n_sweeps > n_sweeps_all:
                n_sweeps_all = n_sweeps
        print(
            f"sweep_keep_selected: longest selected recording has {n_sweeps_all} sweep{'s' if n_sweeps_all != 1 else ''}."
        )
        set_sweeps_to_remove = uistate.x_select["output"]  # get selected sweeps
        uistate.x_select["output"] = (
            set(range(n_sweeps_all)) - set_sweeps_to_remove
        )  # inverse selection
        self.sweep_remove_selected()  # removes inverted selection and clears selection

    def sweep_remove_selected(self):
        # for each selected recording, remove selected sweeps, if they exist, and shift remaining sweep numbers to close gaps
        if not self.sweep_removal_valid_confirmed():
            return
        for rec_idx in uistate.list_idx_select_recs:
            rec_ID = self.df_project.at[rec_idx, "ID"]
            self.sweep_remove_by_ID(rec_ID)
        self.sweep_unselect()
        self.resetCacheDicts()
        self.recalculate()  # outputs, binning, group handling

    def sweep_unselect(self):
        # clear selections and recalculate outputs
        uistate.list_idx_select_recs = []  # clear uistate selection list
        uiplot.xDeselect(
            ax=uistate.ax1, reset=True
        )  # clear sweep selection: resets uistate.x_select
        self.lineEdit_sweeps_range_from.setText("")  # clear lineEdits
        self.lineEdit_sweeps_range_to.setText("")
        self.tableProj.clearSelection()  # clear visual effect of df_project selection

    def sweep_split_by_selected(self):
        if not self.sweep_selection_valid():
            return
        n_sweeps_all = 0
        for rec_idx in (
            uistate.list_idx_select_recs
        ):  # get all sweeps from the longest selected recording
            p_row = self.df_project.iloc[rec_idx]
            n_sweeps = p_row["sweeps"]
            if n_sweeps > n_sweeps_all:
                n_sweeps_all = n_sweeps
        selected_sweeps = uistate.x_select.get("output")
        n_sweeps = len(selected_sweeps)
        n_recs = len(uistate.list_idx_select_recs)
        title = "Split sweeps by selection"
        message = (
            f"Split {n_recs} selected recording{'s' if n_recs != 1 else ''}\n"
            f"by {n_sweeps} selected sweep{'s' if n_sweeps != 1 else ''}?\n"
            "This action cannot be undone."
        )
        if not confirm(title=title, message=message):
            print("sweep_split_by_selected: cancelled by user")
            return
        other_sweeps = set(range(n_sweeps_all)) - selected_sweeps
        # copy original df_project for loop: self.df_project will be modified
        original_df_project = self.get_df_project().copy()
        for rec_idx in uistate.list_idx_select_recs:
            source_row = original_df_project.iloc[rec_idx]
            source_name = source_row["recording_name"]
            rec_A = source_name + "_A"
            rec_B = source_name + "_B"
            print(
                f"Will split {source_name} into:\n {rec_A}: {len(selected_sweeps)} sweeps {min(selected_sweeps)}-{max(selected_sweeps)}\n {rec_B}: {len(other_sweeps)} sweeps {min(other_sweeps)}-{max(other_sweeps)}"
            )
            # Copy current recording to new rec_B
            self.duplicate_recording(source_p_row=source_row, new_name=rec_B)
            copy_row = self.df_project[self.df_project["recording_name"] == rec_B].iloc[
                0
            ]
            # rename original recording to rec_A
            self.df_project.loc[
                self.df_project["ID"] == source_row["ID"], "recording_name"
            ] = rec_A
            self.rename_files_by_rec_name(old_name=source_name, new_name=rec_A)
            # remove selected sweeps from A, all other sweeps from B, updates df_project and kills cache files
            self.sweep_remove_by_ID(source_row["ID"], selection=selected_sweeps)
            self.sweep_remove_by_ID(copy_row["ID"], selection=other_sweeps)
            uiplot.unPlot(source_row["ID"])
            self.graphUpdate(row=source_row)
        self.resetCacheDicts()
        self.sweep_unselect()
        self.recalculate()  # outputs, binning, group handling
