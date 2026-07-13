# ui_parse.py
# ParseMixin — parse orchestration, progress, reanalyze, addData, etc.
# extracted from UIsub (Phase 3 of ui mixin extraction plan).
#
# Module-level singletons are injected by ui.py (same pattern as other mixins):
#
#   import ui_parse
#   ui_parse.uistate = uistate
#   ui_parse.config  = config
#   ui_parse.uiplot  = uiplot

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import pandas as pd
from PyQt5 import QtCore, QtWidgets

import parse
import ui_widgets  # for ParseDataThread, ProgressBarManager, Filetreesub etc. (consistent with ui_table, ui_graph)
import uuid

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ParseMixin:
    """Mixin that provides parse/import orchestration, progress bars, reanalyze, addData, etc.

    Host requirements:
        - self.df_project, self.get_df_project(), self.set_df_project()
        - self.dict_folders
        - self.uiFreeze(), self.uiThaw()
        - self.update_test(), self.setButtonParse(), self.tableUpdate(), self.graphPreload(), self.graphUpdate()
        - self.update_recs2plot(), self.update_show(), self.update_amp_lineEdits(), self.update_slope_lineEdits()
        - self.refresh_samples(), self.group_cache_purge(), self.get_groupsOfRec()
        - self.rename_files_by_rec_name()
        - self._cleanup_threads(), self._threads, self._current_parse_thread
        - self.progressBar, self.progressBarManager
        - self.graphRefresh()
        - ui_widgets.ParseDataThread, ui_widgets.ProgressBarManager, ui_widgets.InputDialogPopup
        - uistate.plot.list_idx_select_recs, uistate.project.list_idx_recs2preload, etc.
    """

    def addData(self, dfAdd):  # concatenate dataframes of old and new data
        # Check for unique names in dfAdd, vs df_p and dfAdd
        # Adds (<lowest integer that makes unique>) to the end of non-unique recording_names
        df_p = self.get_df_project()
        list_recording_names = set(df_p["recording_name"])
        for index, row in dfAdd.iterrows():
            check_recording_name = row["recording_name"]
            if check_recording_name.endswith("_mean.parquet"):
                print("recording_name must not end with _mean.parquet - appending _X")  # must not collide with internal naming
                check_recording_name = check_recording_name + "_X"
                dfAdd.at[index, "recording_name"] = check_recording_name
            if check_recording_name in list_recording_names:
                # print(index, check_recording_name, "already exists!")
                i = 1
                new_recording_name = check_recording_name + "(" + str(i) + ")"
                while new_recording_name in list_recording_names:
                    i += 1
                    new_recording_name = check_recording_name + "(" + str(i) + ")"
                print("New name:", new_recording_name)
                list_recording_names.add(new_recording_name)
                dfAdd.at[index, "recording_name"] = new_recording_name
            else:
                list_recording_names.add(check_recording_name)
        df_p = pd.concat([df_p, dfAdd])
        df_p.reset_index(drop=True, inplace=True)
        df_p["groups"] = df_p["groups"].fillna(" ")
        df_p["sweeps"] = df_p["sweeps"].fillna("...")
        # v0.16_n: migration will be called inside set_df_project (hierarchy defaults)
        self.set_df_project(df_p)
        self.tableUpdate(restore_selection=True)  # new helper ensures selection is restored after adding data
        logger.debug("addData: %s", self.get_df_project())
        print("addData:", self.get_df_project())

    def purgeRecordingData(self, rec_ID, rec_name):
        def removeFromCache(cache_name):
            cache = getattr(self, cache_name)
            if rec_name in cache.keys():
                cache.pop(rec_name, None)

        def removeFromDisk(folder_name, file_suffix):
            file_path = Path(self.dict_folders[folder_name] / (rec_name + file_suffix))
            if file_path.exists():
                file_path.unlink()
            else:
                print(f"purgeRecordingData: file not found: {file_path}")

        groups2purge = self.get_groupsOfRec(rec_ID)
        if groups2purge:  # if rec_ID is in groups, purge those group caches and update dd_groups
            # print(f"purgeRecordingData: {rec_name} in groups: {groups2purge}")
            for group_ID in groups2purge:  # remove rec_ID from rec_IDs of all affected groups
                print(f"purgeRecordingData: pre  {self.dd_groups[group_ID]['rec_IDs']}")
                self.dd_groups[group_ID]["rec_IDs"].remove(rec_ID)
                print(f"purgeRecordingData: post {self.dd_groups[group_ID]['rec_IDs']}")
            self.group_save_dd()
            for group_ID in groups2purge:
                self.clear_group_level(group_ID)  # all levels for affected
            self.refresh_samples()
        # clear recording caches
        for cache_name in [
            "dict_datas",
            "dict_means",
            "dict_filters",
            "dict_bins",
            "dict_outputs",
            "dict_diffs",
        ]:
            removeFromCache(cache_name)
        for folder_name, file_suffix in [
            ("data", ".parquet"),
            ("timepoints", ".parquet"),
            ("cache", "_mean.parquet"),
            ("cache", "_filter.parquet"),
            ("cache", "_bin.parquet"),
            ("cache", "_output.parquet"),
        ]:
            removeFromDisk(folder_name, file_suffix)

    def parseData(self):
        if hasattr(self, "_current_parse_thread") and self._current_parse_thread is not None:
            print("parseData: already parsing, ignoring duplicate call")
            return
        self.uiFreeze()  # Thawed at the end of graphPreload()
        # Clean up any existing thread before starting a new one
        self._cleanup_threads()
        df_p = self.get_df_project()
        df_p_to_update = df_p[df_p["sweeps"] == "..."].copy()
        if len(df_p_to_update) > 0:
            print(f"parseData: {len(df_p_to_update)} files to parse.")
            thread = ui_widgets.ParseDataThread(df_p_to_update, self.dict_folders, self)
            self._current_parse_thread = thread  # Store reference for use in callbacks
            thread.progress.connect(self.updateProgressBar)
            thread.sub_progress.connect(self.updateSubProgressBar)
            thread.status_update.connect(self.updateStatusBar)
            thread.finished.connect(self.onParseDataFinished)
            thread.finished.connect(thread.deleteLater)  # Auto-cleanup when done
            thread.finished.connect(lambda: self._threads.remove(thread) if thread in self._threads else None)
            thread.finished.connect(lambda: setattr(self, "_current_parse_thread", None))
            self._threads.append(thread)
            thread.start()
            self.progressBarManager = ui_widgets.ProgressBarManager(self.progressBar, len(df_p_to_update))
            self.progressBarManager.__enter__()
            # Loading takes control of statusbar (messages pushed via update* callbacks).
            # Non-error state: use default color (darkmode sensitive).

    def updateProgressBar(self, i):
        self.progressBarManager.update(i, "Parsing file ")

    def updateSubProgressBar(self, idx, total):
        self.progressBarManager.update_sub(idx, total)

    def updateStatusBar(self, text):
        self.progressBarManager.set_status(text)

    def onParseDataFinished(self):
        print("onParseDataFinished: entered")
        self.progressBarManager.__exit__(None, None, None)
        if hasattr(self, "_current_parse_thread") and self._current_parse_thread is not None:
            thread = self._current_parse_thread
            if thread.rows:
                rows2add = pd.concat(thread.rows, axis=1).transpose()
                df_p = self.get_df_project()
                df_p = pd.concat([df_p[df_p["sweeps"] != "..."], rows2add]).reset_index(drop=True)
                self.set_df_project(df_p)
                # Get the indices of the new rows, as they are in df_p
                uistate.project.list_idx_recs2preload = df_p.index[df_p.index >= len(df_p) - len(rows2add)].tolist()
        self.setButtonParse()
        self.progressBarManager.__exit__(None, None, None)
        # Return control to test warnings (graphPreload will take over again if needed)
        self.update_test()
        print("onParseDataFinished: calling graphPreload")
        self.graphPreload()

    def setButtonParse(self):
        logger.debug("setButtonParse")
        print("setButtonParse")
        unparsed = self.df_project["sweeps"].eq("...").any()
        self.pushButtonParse.setVisible(bool(unparsed))
        self.frameParseOptions.setVisible(bool(unparsed))

    def slotAddDfData(self, df):
        self.addData(df)

    # Additional related for completeness in parse flow
    def triggerAddData(self):  # creates file tree for file selection
        self.dialog = QtWidgets.QDialog()
        self.ftree = ui_widgets.Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.exec_()

    def triggerParse(self):  # parse non-parsed files and folders in self.df_project
        self.parseData()

    def reanalyze_recordings(self):
        if not uistate.plot.list_idx_select_recs:
            print("No recordings selected for reanalysis.")
            return
        df_p = self.get_df_project()
        for idx in uistate.plot.list_idx_select_recs:
            prow = df_p.loc[idx]
            if str(prow.get("sweeps", "...")) == "...":
                continue
            print(f"Reanalyzing {prow['recording_name']}...")
            # purge old analysis
            self.purgeRecordingData(prow["ID"], prow["recording_name"])
            uiplot.unPlot(prow["ID"])
            # re-add will trigger reparse/reanalysis via existing flow
            # For simplicity, we re-trigger parse if needed, but since it was parsed, we can call graphUpdate after
        self.graphUpdate()
        self.update_show(reset=True)

    def duplicate_recording(self, source_p_row, new_name=None):
        # duplicate a recording row and its data files
        if new_name is None:
            new_name = source_p_row["recording_name"] + "_copy"
        df_p = self.get_df_project()
        new_row = source_p_row.copy()
        new_row["recording_name"] = new_name
        new_row["ID"] = str(int(df_p["ID"].max() or 0) + 1)  # simplistic new ID
        df_p = pd.concat([df_p, pd.DataFrame([new_row])], ignore_index=True)
        self.set_df_project(df_p)
        # copy files
        for folder, suffix in [
            ("data", ".parquet"),
            ("timepoints", ".parquet"),
            ("cache", "_mean.parquet"),
            ("cache", "_filter.parquet"),
            ("cache", "_bin.parquet"),
            ("cache", "_output.parquet"),
        ]:
            src = Path(self.dict_folders[folder]) / (source_p_row["recording_name"] + suffix)
            dst = Path(self.dict_folders[folder]) / (new_name + suffix)
            if src.exists():
                import shutil
                shutil.copy(src, dst)
        self.tableUpdate(restore_selection=True)
        print(f"Duplicated {source_p_row['recording_name']} as {new_name}")

    def create_recording(self, df_proj_row, rec, df_raw, status_callback=None):
        def create_row(df_proj_row, new_name, dict_meta):
            df_proj_new_row = df_proj_row.copy()
            df_proj_new_row["ID"] = str(uuid.uuid4())
            df_proj_new_row["recording_name"] = new_name
            df_proj_new_row["gain"] = uistate.project.lineEdit["import_gain"]  # capture gain at parse time
            df_proj_new_row["sweeps"] = dict_meta.get("nsweeps", None)
            df_proj_new_row["channel"] = ""  # dict_meta.get('channel', None)
            df_proj_new_row["sweep_duration"] = dict_meta.get("sweep_duration", None)
            df_proj_new_row["sampling_rate"] = dict_meta.get("sampling_rate", None)
            df_proj_new_row["resets"] = ""  # dict_meta.get('resets', None)
            # sweep_hz: inter-sweep rate derived from t0 timestamps; NaN if unavailable
            sweep_hz = dict_meta.get("sweep_hz", None)
            df_proj_new_row["sweep_hz"] = sweep_hz if sweep_hz is not None else float("nan")
            # Build pipe-delimited status flags; append "default Hz" when sweep_hz is absent
            status_flags = ["Read"]
            if sweep_hz is None:
                status_flags.append("default Hz")
            df_proj_new_row["status"] = "|".join(status_flags)
            return df_proj_new_row

        if status_callback:
            status_callback("building dataframe...")
        self.df2file(df=df_raw, filename=rec, key="data")  # persist raws
        dfmean, i_stim = parse.build_dfmean(df_raw)
        if status_callback:
            status_callback("writing to disk...")
        self.df2file(df=dfmean, filename=rec, key="mean")  # persist mean
        df = parse.zeroSweeps(df_raw, i_stim=i_stim)
        self.df2file(df=df, filename=rec, key="filter")  # persist zeroed
        dict_meta = parse.metadata(df)  # extract metadata
        df_proj_new_row = create_row(df_proj_row=df_proj_row, new_name=rec, dict_meta=dict_meta)
        return df_proj_new_row

    def deleteSelectedRows(self):
        # moved some purge logic here too for parse flow
        if not uistate.plot.list_idx_select_recs:
            print("No files selected.")
            return
        df_p = self.get_df_project()
        reselect_id = None
        last_deleted_idx = uistate.plot.list_idx_select_recs[-1]
        if last_deleted_idx < len(df_p) - 1:
            reselect_id = df_p.at[last_deleted_idx + 1, "ID"]

        for index in uistate.plot.list_idx_select_recs:
            rec_name = df_p.at[index, "recording_name"]
            rec_ID = df_p.at[index, "ID"]
            sweeps = df_p.at[index, "sweeps"]
            if sweeps != "...":  # if the file is parsed:
                print(f"Deleting {rec_name}...")
                self.purgeRecordingData(rec_ID, rec_name)
                uiplot.unPlot(rec_ID)

        df_p.drop(uistate.plot.list_idx_select_recs, inplace=True)
        df_p.reset_index(inplace=True, drop=True)

        if reselect_id is not None:
            new_idx = df_p[df_p["ID"] == reselect_id].index
            if not new_idx.empty:
                uistate.plot.list_idx_select_recs = [new_idx[0]]
            else:
                uistate.plot.list_idx_select_recs = []
        elif len(df_p) > 0:
            uistate.plot.list_idx_select_recs = [len(df_p) - 1]
        else:
            uistate.plot.list_idx_select_recs = []

        self.set_df_project(df_p)
        self.tableUpdate(restore_selection=True, target_idx=None)
        self.tableProjSelectionChanged()
