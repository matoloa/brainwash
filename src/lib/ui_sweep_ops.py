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

import uuid

import numpy as np
import pandas as pd
import parse

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

    def triggerSplitByTime(self):
        self.usage("triggerSplitByTime")
        self.sweep_split_by_time()

    def triggerKeepSelectedTime(self):
        self.usage("triggerKeepSelectedTime")
        self.time_keep_selected()

    def triggerDiscardSelectedTime(self):
        self.usage("triggerDiscardSelectedTime")
        self.time_discard_selected()

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
        for rec_idx in uistate.list_idx_select_recs:
            p_row = self.df_project.iloc[rec_idx]
            n_sweeps = p_row["sweeps"]
            if n_sweeps > n_sweeps_all:
                n_sweeps_all = n_sweeps

        selected_sweeps = uistate.x_select["output"]
        other_sweeps = set(range(n_sweeps_all)) - selected_sweeps
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

        # copy original df_project for loop: self.df_project will be modified
        original_df_project = self.get_df_project().copy()

        for rec_idx in uistate.list_idx_select_recs:
            source_row = original_df_project.iloc[rec_idx]
            source_name = source_row["recording_name"]
            rec_A = source_name + "_A"
            rec_B = source_name + "_B"
            print(
                f"Will split {source_name} into:\n"
                f"  {rec_A}: {len(selected_sweeps)} sweeps {min(selected_sweeps)}-{max(selected_sweeps)}\n"
                f"  {rec_B}: {len(other_sweeps)} sweeps {min(other_sweeps)}-{max(other_sweeps)}"
            )

            # --- Read source data exactly once ---
            df_source = self.get_dfdata(source_row).copy()

            # --- Partition in memory and renumber each half ---
            df_A = df_source[df_source["sweep"].isin(selected_sweeps)].reset_index(
                drop=True
            )
            df_B = df_source[df_source["sweep"].isin(other_sweeps)].reset_index(
                drop=True
            )
            df_A = self.sweep_shift_gaps(df_A, selected_sweeps)
            df_B = self.sweep_shift_gaps(df_B, other_sweeps)

            n_sweeps_A = len(df_A["sweep"].unique())
            n_sweeps_B = len(df_B["sweep"].unique())
            sweep_duration_A = parse.metadata(df_A)["sweep_duration"]
            sweep_duration_B = parse.metadata(df_B)["sweep_duration"]

            # --- Register rec_B in df_project (new row, new ID) ---
            df_proj_B = source_row.copy()
            df_proj_B["ID"] = str(uuid.uuid4())
            df_proj_B["recording_name"] = rec_B
            df_proj_B["sweeps"] = n_sweeps_B
            df_proj_B["sweep_duration"] = sweep_duration_B
            self.df_project = pd.concat(
                [self.get_df_project(), pd.DataFrame([df_proj_B])], ignore_index=True
            )

            # --- Rename source files to rec_A names (filesystem rename only, no data written) ---
            self.rename_files_by_rec_name(old_name=source_name, new_name=rec_A)

            # --- Update rec_A entry in df_project ---
            self.df_project.loc[
                self.df_project["ID"] == source_row["ID"], "recording_name"
            ] = rec_A
            self.df_project.loc[self.df_project["ID"] == source_row["ID"], "sweeps"] = (
                n_sweeps_A
            )
            self.df_project.loc[
                self.df_project["ID"] == source_row["ID"], "sweep_duration"
            ] = sweep_duration_A

            # --- Write both halves directly (no intermediate full copy) ---
            self.df2file(df=df_A, rec=rec_A, key="data")
            self.df2file(df=df_B, rec=rec_B, key="data")

            # --- Clear stale cache for both halves ---
            for rec_name in (rec_A, rec_B):
                self._clear_rec_cache(rec_name)

            self.save_df_project()
            uiplot.unPlot(source_row["ID"])
            row_A = self.df_project[self.df_project["ID"] == source_row["ID"]].iloc[0]
            row_B = self.df_project[self.df_project["recording_name"] == rec_B].iloc[0]
            self.graphUpdate(row=row_A)
            self.graphUpdate(row=row_B)

        self.resetCacheDicts()
        self.sweep_unselect()
        self.recalculate()  # outputs, binning, group handling

    # ------------------------------------------------------------------
    # Time-based crop (keep / discard)
    # ------------------------------------------------------------------

    def _time_selection_valid(self):
        """Return (start_s, end_s) from mean_start/mean_end, or None if invalid.

        mean_start is required and must be non-zero.  mean_end is optional;
        if absent the selection is treated as a single point (start only),
        which is only meaningful for split — callers that need a range must
        check that end_s is not None themselves.
        """
        mean_start = uistate.x_select.get("mean_start")
        mean_end = uistate.x_select.get("mean_end")
        if not mean_start:
            print("time_selection_valid: no time selection on mean graph.")
            return None
        start_s = float(mean_start)
        end_s = float(mean_end) if mean_end else None
        return start_s, end_s

    def time_crop_by_ID(self, rec_ID, keep_start_s, keep_end_s):
        """Crop every sweep of recording *rec_ID* to [keep_start_s, keep_end_s].

        Rows outside the window are removed.  The kept time axis is
        re-zeroed per-sweep so it starts from 0.  sweep_duration and the
        data file are updated; all cache is cleared.
        """
        p_row = self.df_project[self.df_project["ID"] == rec_ID].iloc[0]
        rec_name = p_row["recording_name"]
        df = self.get_dfdata(p_row).copy()

        mask = (df["time"] >= keep_start_s) & (df["time"] <= keep_end_s)
        df_cropped = df[mask].copy().reset_index(drop=True)

        if df_cropped.empty:
            print(
                f"time_crop_by_ID: time window [{keep_start_s}, {keep_end_s}] s "
                f"contains no samples in '{rec_name}' — skipping."
            )
            return

        # Re-zero time per-sweep so each sweep starts at 0.
        offset = df_cropped.groupby("sweep")["time"].transform("min")
        df_cropped["time"] = (df_cropped["time"] - offset).round(9)

        new_sweep_duration = parse.metadata(df_cropped)["sweep_duration"]
        self.df2file(df=df_cropped, rec=rec_name, key="data")
        self.df_project.loc[self.df_project["ID"] == rec_ID, "sweep_duration"] = (
            new_sweep_duration
        )
        self.save_df_project()
        self._clear_rec_cache(rec_name)
        print(
            f"time_crop_by_ID: '{rec_name}' cropped to "
            f"{keep_start_s * 1000:g}–{keep_end_s * 1000:g} ms "
            f"(new sweep_duration {new_sweep_duration * 1000:g} ms)."
        )

    def time_keep_selected(self):
        """Keep only the selected time window in every selected recording.

        Requires mean_start and mean_end to both be set.
        """
        if not uistate.list_idx_select_recs:
            print("time_keep_selected: no recordings selected.")
            return
        sel = self._time_selection_valid()
        if sel is None:
            return
        start_s, end_s = sel
        if end_s is None:
            print("time_keep_selected: a time range (start and end) is required.")
            return

        n_recs = len(uistate.list_idx_select_recs)
        dur_ms = round((end_s - start_s) * 1000)
        if not confirm(
            title="Keep only selected time",
            message=(
                f"Keep only {start_s * 1000:g}–{end_s * 1000:g} ms "
                f"({dur_ms} ms) in "
                f"{n_recs} selected recording{'s' if n_recs != 1 else ''}?\n"
                "This action cannot be undone."
            ),
        ):
            print("time_keep_selected: cancelled by user.")
            return

        for rec_idx in uistate.list_idx_select_recs:
            rec_ID = self.df_project.at[rec_idx, "ID"]
            self.time_crop_by_ID(rec_ID, keep_start_s=start_s, keep_end_s=end_s)

        self.resetCacheDicts()
        self.recalculate()

    def time_discard_selected(self):
        """Remove the selected time window from every sweep of every selected recording.

        Requires mean_start and mean_end to both be set.  The two remaining
        fragments are concatenated per sweep with the second fragment
        re-zeroed so time is continuous from 0.
        """
        if not uistate.list_idx_select_recs:
            print("time_discard_selected: no recordings selected.")
            return
        sel = self._time_selection_valid()
        if sel is None:
            return
        start_s, end_s = sel
        if end_s is None:
            print("time_discard_selected: a time range (start and end) is required.")
            return

        n_recs = len(uistate.list_idx_select_recs)
        dur_ms = round((end_s - start_s) * 1000)
        if not confirm(
            title="Discard selected time",
            message=(
                f"Remove {start_s * 1000:g}–{end_s * 1000:g} ms "
                f"({dur_ms} ms) from "
                f"{n_recs} selected recording{'s' if n_recs != 1 else ''}?\n"
                "This action cannot be undone."
            ),
        ):
            print("time_discard_selected: cancelled by user.")
            return

        for rec_idx in uistate.list_idx_select_recs:
            rec_ID = self.df_project.at[rec_idx, "ID"]
            p_row = self.df_project[self.df_project["ID"] == rec_ID].iloc[0]
            rec_name = p_row["recording_name"]
            df = self.get_dfdata(p_row).copy()

            df_before = df[df["time"] < start_s].copy()
            df_after = df[df["time"] > end_s].copy()

            if df_before.empty and df_after.empty:
                print(
                    f"time_discard_selected: discarding [{start_s}, {end_s}] s "
                    f"leaves nothing in '{rec_name}' — skipping."
                )
                continue

            # Re-zero the 'after' fragment per-sweep so it continues from
            # where 'before' left off, then join and re-zero everything to 0.
            if not df_before.empty and not df_after.empty:
                before_end = df_before.groupby("sweep")["time"].transform("max")
                after_start = df_after.groupby("sweep")["time"].transform("min")
                # shift 'after' so it immediately follows 'before' with one dt gap
                dt = df["time"].diff().dropna().mode().iloc[0]
                df_after = df_after.copy()
                df_after["time"] = (
                    df_after["time"] - after_start + before_end + dt
                ).round(9)
                df_joined = pd.concat([df_before, df_after]).reset_index(drop=True)
            elif df_before.empty:
                df_joined = df_after.copy().reset_index(drop=True)
            else:
                df_joined = df_before.copy().reset_index(drop=True)

            # Re-zero the whole thing to start at 0 per sweep.
            offset = df_joined.groupby("sweep")["time"].transform("min")
            df_joined["time"] = (df_joined["time"] - offset).round(9)

            new_sweep_duration = parse.metadata(df_joined)["sweep_duration"]
            self.df2file(df=df_joined, rec=rec_name, key="data")
            self.df_project.loc[self.df_project["ID"] == rec_ID, "sweep_duration"] = (
                new_sweep_duration
            )
            self.save_df_project()
            self._clear_rec_cache(rec_name)
            print(
                f"time_discard_selected: '{rec_name}' had "
                f"{start_s * 1000:g}–{end_s * 1000:g} ms removed "
                f"(new sweep_duration {new_sweep_duration * 1000:g} ms)."
            )

        self.resetCacheDicts()
        self.recalculate()

    # ------------------------------------------------------------------
    # Time-based split
    # ------------------------------------------------------------------

    def _next_free_time_split_pair(self, base_name: str) -> tuple[str, str]:
        """Return the first consecutive letter pair (_a/_b, _c/_d, …) whose
        suffixed names do not already exist in df_project for *base_name*.

        The pairs are built from consecutive lowercase alphabet pairs:
          pair 0 → ('_a', '_b')
          pair 1 → ('_c', '_d')
          pair 2 → ('_e', '_f')
          …

        The search stops at the first pair where *neither* ``base_name + suf_a``
        nor ``base_name + suf_b`` is already taken.  This means a second
        split on the same recording will produce ``_c``/``_d``, a third
        ``_e``/``_f``, etc.
        """
        existing = set(self.get_df_project()["recording_name"].values)
        for i in range(13):  # a-z gives 13 pairs
            suf_a = chr(ord("a") + i * 2)  # a, c, e, g, …
            suf_b = chr(ord("a") + i * 2 + 1)  # b, d, f, h, …
            name_a = f"{base_name}_{suf_a}"
            name_b = f"{base_name}_{suf_b}"
            if name_a not in existing and name_b not in existing:
                return name_a, name_b
        raise RuntimeError(
            f"_next_free_time_split_pair: all 13 letter pairs are taken for '{base_name}'"
        )

    def _clear_rec_cache(self, rec_name: str):
        """Delete all cache / timepoint files for *rec_name*."""
        for suffix in (
            "_mean.parquet",
            "_filter.parquet",
            "_bin.parquet",
            "_output.parquet",
        ):
            p = self.dict_folders["cache"] / (rec_name + suffix)
            if p.exists():
                p.unlink()
                if config.verbose:
                    print(f"Deleted cache file: {p}")
        tp = self.dict_folders["timepoints"] / (rec_name + ".parquet")
        if tp.exists():
            tp.unlink()
            if config.verbose:
                print(f"Deleted cache file: {tp}")

    def sweep_split_by_time(self):
        """Split each selected recording at a within-sweep time point (ms).

        If ``uistate.x_select["mean_start"]`` is set and non-zero the value is
        used directly (it is already in seconds).  Otherwise the user is
        prompted for a split time in milliseconds.

        The data are partitioned into two halves for every selected recording:

        * Part **a** — rows where ``time < split_s`` (first event / baseline).
        * Part **b** — rows where ``time >= split_s`` (second event), with the
          time axis re-zeroed to 0.

        Both halves keep all sweeps.  The resulting recordings are named using
        the next free consecutive letter pair for the base recording name:
        first split → ``_a`` / ``_b``, second split of the same base →
        ``_c`` / ``_d``, and so on.

        The source recording's files are renamed to ``_a`` (its df_project row
        is updated in place); ``_b`` is written as a new data file with a new
        df_project row.  This mirrors sweep_split_by_selected: the data/
        parquet is a working copy made at import time, not the original raw
        file, so mutating it is correct.
        """
        if not uistate.list_idx_select_recs:
            print("sweep_split_by_time: no recordings selected.")
            return

        # --- Resolve split time: use mean_start if set, else ask ---
        mean_start = uistate.x_select.get("mean_start")
        if mean_start is not None and mean_start != 0:
            split_s = float(mean_start)
            print(f"sweep_split_by_time: using mean_start = {split_s} s")
        else:
            from ui import (
                InputDialogPopup,  # local import avoids circular at module level
            )

            dlg = InputDialogPopup()
            raw = dlg.showInputDialog(
                title="Split recording by time",
                query="Split time (ms)",
            )
            if raw is None:
                print("sweep_split_by_time: cancelled.")
                return
            raw = raw.replace(",", ".")
            try:
                split_ms = float(raw)
            except ValueError:
                print(f"sweep_split_by_time: '{raw}' is not a valid number.")
                return
            if split_ms <= 0:
                print(
                    f"sweep_split_by_time: split time must be > 0 ms (got {split_ms})."
                )
                return
            split_s = split_ms / 1000.0

        # --- Build confirmation message ---
        n_recs = len(uistate.list_idx_select_recs)
        split_ms = split_s * 1000.0
        # Derive sweep duration from the first selected recording for the summary.
        first_row = self.get_df_project().iloc[uistate.list_idx_select_recs[0]]
        sweep_duration = first_row.get("sweep_duration")
        try:
            sweep_duration = float(sweep_duration)
            dur_a_ms = round(split_ms)
            dur_b_ms = round((sweep_duration - split_s) * 1000.0)
            duration_line = f"→ two parts of {dur_a_ms} ms and {dur_b_ms} ms per sweep"
            if dur_a_ms <= 0 or dur_b_ms <= 0:
                duration_line = "(warning: split is outside the sweep's time range)"
        except (TypeError, ValueError):
            duration_line = ""

        msg_lines = [
            f"Split {n_recs} selected recording{'s' if n_recs != 1 else ''}",
            f"at t = {split_ms:g} ms",
        ]
        if duration_line:
            msg_lines.append(duration_line)
        msg_lines.append("This action cannot be undone.")
        if not confirm(
            title="Split recordings by time",
            message="\n".join(msg_lines),
        ):
            print("sweep_split_by_time: cancelled by user.")
            return

        original_df_project = self.get_df_project().copy()

        for rec_idx in uistate.list_idx_select_recs:
            source_row = original_df_project.iloc[rec_idx]
            source_name = source_row["recording_name"]

            # Determine next-free suffix pair for this base name.
            try:
                rec_a, rec_b = self._next_free_time_split_pair(source_name)
            except RuntimeError as exc:
                print(f"sweep_split_by_time: {exc}")
                continue

            print(
                f"sweep_split_by_time: splitting '{source_name}' at t={split_s}s "
                f"→ '{rec_a}' (part a) and '{rec_b}' (part b)."
            )

            # --- Read source data exactly once ---
            df_source = self.get_dfdata(source_row)
            if df_source is None:
                print(
                    f"sweep_split_by_time: could not read data for '{source_name}', skipping."
                )
                continue
            df_source = df_source.copy()

            # --- Partition in memory ---
            df_a = df_source[df_source["time"] < split_s].copy().reset_index(drop=True)
            df_b = df_source[df_source["time"] >= split_s].copy().reset_index(drop=True)

            if df_a.empty:
                print(
                    f"sweep_split_by_time: split_s={split_s}s is at or before the first sample "
                    f"in '{source_name}'; part 'a' is empty — skipping."
                )
                continue
            if df_b.empty:
                print(
                    f"sweep_split_by_time: split_s={split_s}s is beyond the last sample "
                    f"in '{source_name}'; part 'b' is empty — skipping."
                )
                continue

            # Re-zero time in part 'b' per-sweep so it starts from 0.
            split_offset = df_b.groupby("sweep")["time"].transform("min")
            df_b["time"] = (df_b["time"] - split_offset).round(9)

            n_sweeps_a = df_a["sweep"].nunique()
            n_sweeps_b = df_b["sweep"].nunique()
            sweep_duration_a = parse.metadata(df_a)["sweep_duration"]
            sweep_duration_b = parse.metadata(df_b)["sweep_duration"]

            print(
                f"  {rec_a}: {n_sweeps_a} sweep{'s' if n_sweeps_a != 1 else ''}, "
                f"t < {split_s}s\n"
                f"  {rec_b}: {n_sweeps_b} sweep{'s' if n_sweeps_b != 1 else ''}, "
                f"t >= {split_s}s (re-zeroed)"
            )

            # --- Register rec_b in df_project (new row, new ID) ---
            df_proj_b = source_row.copy()
            df_proj_b["ID"] = str(uuid.uuid4())
            df_proj_b["recording_name"] = rec_b
            df_proj_b["sweeps"] = n_sweeps_b
            df_proj_b["sweep_duration"] = sweep_duration_b
            self.df_project = pd.concat(
                [self.get_df_project(), pd.DataFrame([df_proj_b])], ignore_index=True
            )

            # --- Rename source files to rec_a names (filesystem rename only) ---
            self.rename_files_by_rec_name(old_name=source_name, new_name=rec_a)

            # --- Update rec_a entry in df_project (reuses source row's ID) ---
            self.df_project.loc[
                self.df_project["ID"] == source_row["ID"], "recording_name"
            ] = rec_a
            self.df_project.loc[self.df_project["ID"] == source_row["ID"], "sweeps"] = (
                n_sweeps_a
            )
            self.df_project.loc[
                self.df_project["ID"] == source_row["ID"], "sweep_duration"
            ] = sweep_duration_a

            # --- Write both halves as source data files ---
            self.df2file(df=df_a, rec=rec_a, key="data")
            self.df2file(df=df_b, rec=rec_b, key="data")

            # --- Clear stale cache for both halves ---
            self._clear_rec_cache(rec_a)
            self._clear_rec_cache(rec_b)

            self.save_df_project()
            uiplot.unPlot(source_row["ID"])
            row_a = self.df_project[self.df_project["ID"] == source_row["ID"]].iloc[0]
            row_b = self.df_project[self.df_project["recording_name"] == rec_b].iloc[0]
            self.graphUpdate(row=row_a)
            self.graphUpdate(row=row_b)

        self.resetCacheDicts()
        self.recalculate()
