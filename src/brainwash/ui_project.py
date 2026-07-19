# ui_project.py
# ProjectMixin — project-level file I/O and bootstrapping extracted from UIsub (Phase 5 refactor).
# These methods handle project lifecycle (new/open/load/save), global config (bw_cfg),
# file persistence helpers (df2file, persistOutput), init methods (bootstrap, loadProject),
# UI signal wiring (connectUIstate, applyConfigStates), hierarchy edits, and recording rename.
#
# Also owns df_projectTemplate — the schema/factory for the project DataFrame.
# ui.py imports it from here directly.
#
# Uses self.uistate / self.config / self.uiplot on UIsub (see ui.py).

from __future__ import annotations

import logging
import os
import re
import socket
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml
from PyQt5 import QtCore, QtWidgets

import brainwash.parse as parse
import ui_widgets
from project_schema import INT_COLUMNS, df_projectTemplate

logger = logging.getLogger(__name__)


class ProjectMixin:
    """Mixin that provides project I/O, bootstrapping, and persistence helpers for UIsub.

    Config policy (v0.16+): bw_cfg.yaml location is now centralized in
    ui.py:Config.__init__ (readonly _find_file + frozen-aware writable path).
    write_bw_cfg always succeeds (mkdir + logging). Old squashfs configs ignored.
    """

    # ------------------------------------------------------------------
    # Output persistence helper
    # ------------------------------------------------------------------

    def persistOutput(self, rec_name, dfoutput, p_row=None):
        # Column order for the persisted output file.
        # gain and bin_size belong in df_project, not here.
        # sweep holds raw sweep numbers normally, or bin numbers when binning is
        # active (get_dfbin already assigns bin numbers into the sweep column).
        column_order = [
            "stim",
            "sweep",
            "EPSP_slope",
            "EPSP_slope_norm",
            "EPSP_amp",
            "EPSP_amp_norm",
            "volley_amp",
            "volley_slope",
        ]
        # Clean up column order, save to dict and file.
        missing_columns = set(column_order) - set(dfoutput.columns)
        extra_columns = set(dfoutput.columns) - set(column_order)
        if missing_columns:
            print(f"Warning: The following columns in column_order don't exist in dfoutput: {missing_columns}")
        if extra_columns:
            print(f"Warning: The following columns exist in dfoutput but not in column_order: {extra_columns}")
        dfoutput = dfoutput.reindex(columns=column_order)
        self.dict_outputs[rec_name] = dfoutput
        # Select cache key based on bin state (Phase 6).
        if p_row is not None and pd.notna(p_row["bin_size"]):
            cache_key = "output_bin"
        else:
            cache_key = "output"
        self.df2file(df=dfoutput, filename=rec_name, key=cache_key)

        # invalidate global unit caches for the subject/slice of this rec (globals are full avg)
        if hasattr(self, "_invalidate_global_units_for_rec"):
            rec_id = p_row["ID"] if p_row is not None and "ID" in p_row else rec_name
            try:
                self._invalidate_global_units_for_rec(rec_id)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Bootstrapping — general (non-project-specific) UI init
    # ------------------------------------------------------------------

    def bootstrap(self, mainwindow):  # set up general (non-project specific) UI
        # move mainwindow to default position (TODO: to be stored in brainwash/cfg.yaml)
        self.mainwindow = mainwindow
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.mainwindow.setGeometry(
            0,
            0,
            int(screen.width() * 0.999) - getattr(self.config, "work_space", 0),
            int(screen.height()) - self.config.terminal_space,
        )

        self.get_bw_cfg()  # load/create bw global config file (not project specific)
        self.setupMenus()
        self.setupCanvases()  # for graphs, and connect graphClicked(event, <canvas>)

        self.fqdn = socket.getfqdn()  # get computer name and local domain, for project file

        # debug mode; for printing widget focus every 1000ms
        if self.config.track_widget_focus:
            self.timer = QtCore.QTimer(self.mainwindow)
            self.timer.timeout.connect(self.checkFocus)
            self.timer.start(1000)

    # ------------------------------------------------------------------
    # Project loading
    # ------------------------------------------------------------------

    def loadProject(self, project=None):
        self.setupFolders()
        self.resetCacheDicts()  # initiate/clear internal storage dicts
        self.setupTableProj()
        self.setupTableStim()
        # If local project.brainwash exists, load it, otherwise create it
        projectpath = Path(self.dict_folders["project"] / "project.brainwash")
        if projectpath.exists():
            self.load_df_project(self.dict_folders["project"])
        else:
            print(f"Project file {self.dict_folders['project'] / 'project.brainwash'} not found, creating new project file")
            self.df_project = df_projectTemplate()
        # If local cfg.pkl exists, load it, otherwise create it
        self.uistate.reset()
        self.uistate.load_cfg(
            projectfolder=self.dict_folders["project"],
            bw_version=self.config.version,
            force_reset=self.config.force_cfg_reset,
        )
        if self.uistate.project.blind_recordings:
            self._ensure_blind_aliases()
        self._update_window_title()

        # Load group data
        self.dd_groups = self.group_get_dd()
        self.group_update_dfp()
        # Load test set data (integer set_ID based, defaults "set 1", "set 2", ...; persisted in test_sets.pkl)
        self.dd_testsets = self.testset_get_dd()
        self.dd_group_samples = {}  # phase 3.3: group_ID -> {test_ID: df}; populated lazily via get_ddgroup_sample()
        # Talkback optional (#7): usage.yaml + slice dumps under projects_folder/talkback/
        if getattr(self.config, "talkback", False) and hasattr(self, "setupTalkback"):
            self.setupTalkback()
        # Set up canvases and graphs
        self.groupControlsRefresh()  # add group controls to UI
        self.testsetControlsRefresh()  # add test set controls to verticalLayoutTestSet (mirrors group pattern)
        self.connectUIstate()  # connect UI elements to uistate
        self.applyConfigStates()  # apply config states to UI elements
        self.graphAxes()
        self.darkmode()  # set darkmode if set in bw_cfg. Requires tables and canvases be loaded!
        self.setTableStimVisibility(self.uistate.project.showTimetable)
        self.setupToolBar()
        self._sync_blinded_toolframe()
        self._sync_blind_menu_action()
        if hasattr(self, "_sync_talkback_menu_action"):
            self._sync_talkback_menu_action()
        if hasattr(self, "tableUpdate"):
            self.tableUpdate(restore_selection=False)
        # set focus to TableProj, so that arrows work immediately
        self.tableProj.setFocus()
        self.updating_tableProj = False  # v0.16_n: init guard used by tableUpdate() (called from set_df_project)

    # ------------------------------------------------------------------
    # Global config (bw_cfg.yaml)
    # ------------------------------------------------------------------

    def get_bw_cfg(self):
        """Load global bw_cfg.yaml (or set defaults). Path now comes from
        Config (single source of truth, handles frozen/AppImage/XDG/portable).
        Old in-squashfs configs are ignored; new writable location is used.
        """
        # Set default values
        self.user_documents = Path.home() / "Documents"
        self.projects_folder = self.user_documents / "Brainwash Projects"
        self.projectname = "My Project"
        self.uistate.darkmode = True
        self.uistate.project.showTimetable = False
        self.uistate.plot.showHeatmap = False
        # Global preferences (bw_cfg.yaml only; not per-project cfg.pkl)
        self.always_blind_new_projects = False
        self.config.talkback = False

        # Load config if present
        if self.config.bw_cfg_yaml is not None:
            self.bw_cfg_yaml = Path(self.config.bw_cfg_yaml)
            if self.bw_cfg_yaml.exists():
                with self.bw_cfg_yaml.open("r") as file:
                    cfg = yaml.safe_load(file) or {}
                    projectfolder = Path(cfg.get("projects_folder", "")) / cfg.get("projectname", "")
                    if projectfolder.exists():
                        self.user_documents = Path(cfg.get("user_documents", self.user_documents))
                        self.projects_folder = Path(cfg.get("projects_folder", self.projects_folder))
                        self.projectname = cfg.get("projectname", self.projectname)
                    self.uistate.darkmode = cfg.get("darkmode", True)
                    self.uistate.project.showTimetable = cfg.get("showTimetable", False)
                    self.uistate.plot.showHeatmap = cfg.get("showHeatmap", False)
                    self.always_blind_new_projects = bool(cfg.get("always_blind_new_projects", False))
                    self.config.talkback = bool(cfg.get("talkback", False))
        else:
            self.bw_cfg_yaml = None  # Make sure it's defined for consistency

    def write_bw_cfg(self):  # Save global program settings
        """Write bw_cfg.yaml using path from Config (now guaranteed writable).
        Creates parent dir (XDG or portable .config) on first run.
        """
        if self.config.transient or self.bw_cfg_yaml is None:
            return
        cfg = {
            "user_documents": str(self.user_documents),
            "projects_folder": str(self.projects_folder),
            "projectname": self.projectname,
            "darkmode": self.uistate.darkmode,
            "showTimetable": self.uistate.project.showTimetable,
            "showHeatmap": self.uistate.plot.showHeatmap,
            "always_blind_new_projects": bool(getattr(self, "always_blind_new_projects", False)),
            "talkback": bool(getattr(self.config, "talkback", False)),
        }
        path = Path(self.bw_cfg_yaml)  # ensure Path
        path.parent.mkdir(parents=True, exist_ok=True)  # critical for XDG/portable
        with path.open("w+") as file:
            yaml.safe_dump(cfg, file)
        logger.info("Wrote bw_cfg.yaml → %s (darkmode=%s, projects_folder=%s)", path, cfg.get("darkmode"), cfg.get("projects_folder"))

    # ------------------------------------------------------------------
    # File write helpers
    # ------------------------------------------------------------------

    def df2file(self, df, filename=None, key=None, rec=None):
        if filename is None:
            filename = rec
        print(f"df2file: filename={filename}, key={key}")
        if self.config.transient:
            return
        self.dict_folders["cache"].mkdir(exist_ok=True)
        filetype = "parquet"
        if key is None:
            filepath = f"{self.dict_folders['cache']}/{filename}.{filetype}"
        elif key == "timepoints":
            filepath = f"{self.dict_folders['timepoints']}/{filename}.{filetype}"
        elif key == "data":
            filepath = f"{self.dict_folders['data']}/{filename}.{filetype}"
            self.dict_folders["data"].mkdir(exist_ok=True)
        elif key == "sweeptimes":
            from brainwash_ui import recording_cache

            self.dict_folders["data"].mkdir(exist_ok=True)
            filepath = recording_cache.sweeptimes_parquet_path(str(self.dict_folders["data"]), filename)
        else:
            filepath = f"{self.dict_folders['cache']}/{filename}_{key}.{filetype}"

        df.to_parquet(filepath, index=False)
        print(f"saved {filepath}")

    def write_recording_samples(self, rec_name, df, *, source_kind=None, sweeptimes=None):
        """Persist lean samples + sweeptimes for *rec_name*.

        If *df* still has clock columns, builds sweeptimes from them (unless
        *sweeptimes* is provided). If *df* is already lean, keeps/subsets
        existing sweeptimes when possible, else writes a null-clock table.
        """
        from brainwash_ui import recording_cache

        has_clock = df is not None and (("datetime" in df.columns) or ("t0" in df.columns))
        samples = parse.lean_samples(df) if df is not None else parse.lean_samples(pd.DataFrame())
        if sweeptimes is None:
            if has_clock:
                kind = source_kind or parse.infer_source_kind(df=df)
                sweeptimes = parse.build_sweeptimes(df, source_kind=kind)
            else:
                path_st = Path(recording_cache.sweeptimes_parquet_path(str(self.dict_folders["data"]), rec_name))
                if path_st.exists():
                    old = pd.read_parquet(path_st)
                    keep = samples["sweep"].unique() if len(samples) else []
                    sweeptimes = parse.subset_sweeptimes(old, keep)
                else:
                    kind = source_kind or "unknown"
                    sweeptimes = parse.build_sweeptimes(samples.assign(t0=np.nan), source_kind=kind)
        self.df2file(df=samples, filename=rec_name, key="data")
        self.df2file(df=sweeptimes, filename=rec_name, key="sweeptimes")
        # Drop in-memory raw cache so next get_dfdata reloads lean samples
        if hasattr(self, "dict_datas") and rec_name in self.dict_datas:
            self.dict_datas.pop(rec_name, None)
        return samples, sweeptimes

    def get_sweeptimes_df(self, rec_name):
        """Load data/{rec}_sweeptimes.parquet or None if missing."""
        from brainwash_ui import recording_cache

        path = Path(recording_cache.sweeptimes_parquet_path(str(self.dict_folders["data"]), rec_name))
        if not path.exists():
            return None
        return pd.read_parquet(path)

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def newProject(self):
        self.dict_folders["project"].mkdir(exist_ok=True)  # make sure the project folder exists
        # Find lowest integer to append to new_project_name to make it unique
        date = datetime.now().strftime("%Y-%m-%d")
        i = 0
        unique_project_name = "Project " + date  # Initialize with a base name
        while True:
            if i > 0:
                unique_project_name = "Project " + date + "(" + str(i) + ")"
            if not (self.projects_folder / unique_project_name).exists():
                break  # Found a unique name, exit loop
            if self.config.verbose:
                print(f"*** {unique_project_name} already exists")
            i += 1

        # Proceed with project creation using unique_project_name
        self.clearProject()
        print("\n" * 5)
        self.projectname = unique_project_name
        new_projectfolder = self.projects_folder / unique_project_name
        new_projectfolder.mkdir()
        self.loadProject()
        self.set_df_project()
        self.write_bw_cfg()
        # Global pref only — does not affect Open of existing projects.
        if getattr(self, "always_blind_new_projects", False) and hasattr(self, "triggerBlindRecordings"):
            self.triggerBlindRecordings()

    def openProject(self, str_projectfolder):
        self.clearProject()
        self.load_df_project(str_projectfolder)
        self.loadProject()
        return

    def clearProject(self):
        self.uiplot.unPlot()  # all rec plots
        self.uiplot.unPlotGroup()  # all group plots (all levels, full project clear)
        self.graphWipe()  # for good measure

    def renameProject(self):  # changes name of project folder and updates .cfg
        from ui_widgets import InputDialogPopup

        RenameDialog = InputDialogPopup()
        new_project_name = RenameDialog.showInputDialog(title="Rename project", query="")
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if self.config.verbose:
                print(f"Project name {new_project_name} already exists")
        elif re.match(r"^[a-zA-Z0-9_ -]+$", str(new_project_name)) is not None:  # True if valid filename
            dict_old = self.dict_folders
            self.projectname = new_project_name
            self.dict_folders = self.build_dict_folders()
            dict_old["project"].rename(self.dict_folders["project"])
            if Path(dict_old["cache"]).exists():
                dict_old["cache"].rename(self.dict_folders["cache"])
            self.write_bw_cfg()  # update boot-up-path in bw_cfg.yaml to new project folder
            self._update_window_title()
        else:
            print(f"Project name {new_project_name} is not a valid path.")

    # ------------------------------------------------------------------
    # df_project access
    # ------------------------------------------------------------------

    def get_df_project(
        self,
    ):  # returns a copy of the persistent df_project TODO: make these functions the only way to get to it.
        return self.df_project

    def set_df_project(self, df=None):  # persists df and saves it to .csv
        print("set_df_project")
        if df is None:
            self.df_project = df_projectTemplate()
        else:
            # Restore nullable-integer dtypes that pd.concat can degrade to
            # object when mixing Int64 rows with newly-parsed Series rows.
            for col in INT_COLUMNS:
                if col in df.columns:
                    df[col] = df[col].astype(pd.Int64Dtype())
            # sweeps is a mixed-type sentinel column: unparsed rows hold the
            # string "..." while parsed rows hold a numeric sweep count.
            # pd.concat can coerce the numeric values to strings (e.g. "1440")
            # when object-dtype rows are concatenated with Int64 rows.
            # Restore: convert anything that looks numeric back to int, leave
            # "..." strings alone.
            if "sweeps" in df.columns:

                def _coerce_sweeps(v):
                    if v == "...":
                        return v
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        return v

                df["sweeps"] = df["sweeps"].apply(_coerce_sweeps)

            # v0.16_n: enforce hierarchy defaults (new projects, imports, bulk edits)
            df = self._migrate_hierarchy(df)
            self.df_project = df
        self.save_df_project()
        if hasattr(self, "tableUpdate"):
            self.tableUpdate(restore_selection=False)  # set_df_project is called from many contexts; let caller control selection restore to avoid recursion
        # Note: full table refresh (tableUpdate/tableFormat) is performed by the calling UIsub methods (e.g. applyHierarchyToSelection, addData, trigger*).

    def load_df_project(self, str_projectfolder):  # reads or builds project cfg and groups. Reads fileversion of df_project and saves bw_cfg
        self.graphWipe()
        self.resetCacheDicts()  # clear internal caches
        path_projectfolder = Path(str_projectfolder)
        self.projectname = str(path_projectfolder.stem)
        self.projects_folder = path_projectfolder.parent
        print(f"load_df_project: {self.projectname}")
        self.dict_folders = self.build_dict_folders()
        self.df_project = pd.read_csv(str(path_projectfolder / "project.brainwash"), dtype={"group_IDs": str})
        # Backfill any columns added to the schema since this project was last saved
        for col in df_projectTemplate().columns:
            if col not in self.df_project.columns:
                self.df_project[col] = None
        # Restore nullable-integer dtypes lost during CSV round-trip (CSV
        # reads integer-with-NaN columns as float64, producing "1.0" display).
        for col in INT_COLUMNS:
            if col in self.df_project.columns:
                self.df_project[col] = self.df_project[col].astype(pd.Int64Dtype())

        # Ensure filter_params is an object column to accept dicts/json
        if "filter_params" in self.df_project.columns:
            self.df_project["filter_params"] = self.df_project["filter_params"].astype(object)

        # Ensure filter column defaults to "voltage" instead of NaN, None, or "none"
        if "filter" in self.df_project.columns:
            self.df_project["filter"] = self.df_project["filter"].fillna("voltage")
            self.df_project.loc[self.df_project["filter"] == "none", "filter"] = "voltage"
            self.df_project.loc[self.df_project["filter"] == "", "filter"] = "voltage"

        # v0.16_n: enforce statistical_protocol defaults (subject/slice hierarchy)
        self.df_project = self._migrate_hierarchy(self.df_project)

        self._backfill_sweep_hz()
        self._backfill_stims()
        self.uistate.load_cfg(self.dict_folders["project"], self.config.version)
        self.syncJournalExportMenu()
        self.tableUpdate(restore_selection=False)  # initial load; selection set by later tableProjSelectionChanged
        self.write_bw_cfg()

    def _backfill_stims(self):
        """Fill df_project.stims from timepoints parquet when the count is NA.

        stims is only written when dft is first created. Loading an existing
        timepoints file never updated the project column, so older/partial
        projects can show NA for parsed recordings that already have dft on disk.
        """
        df_p = self.df_project
        if df_p is None or df_p.empty or "stims" not in df_p.columns:
            return
        missing = df_p["stims"].isna()
        if not missing.any():
            return
        tp_dir = self.dict_folders.get("timepoints")
        if tp_dir is None:
            return
        from brainwash_ui import recording_cache

        updated = 0
        for idx in df_p.index[missing]:
            rec = df_p.at[idx, "recording_name"]
            path = Path(recording_cache.timepoints_parquet_path(str(tp_dir), rec))
            if not path.exists():
                continue
            try:
                dft = pd.read_parquet(path)
                n = len(dft)
                if n > 0:
                    df_p.at[idx, "stims"] = n
                    updated += 1
            except Exception as exc:
                print(f"_backfill_stims: skipping {rec}: {exc}")
        if updated:
            print(f"_backfill_stims: set stims for {updated} recording(s)")
            self.save_df_project()

    def _backfill_sweep_hz(self):
        """Recompute sweep_hz for recordings where it is NaN.

        Older projects (or IBW imports before the datetime fallback was added
        to parse.metadata) may have sweep_hz=NaN even though the raw data
        parquet contains enough timing information to derive it.  This runs
        once per project load and only touches recordings that need it.
        """
        df_p = self.df_project
        missing = df_p["sweep_hz"].isna()
        if not missing.any():
            return
        data_dir = self.dict_folders.get("data")
        if data_dir is None or not data_dir.exists():
            return
        updated = 0
        from brainwash_ui import recording_cache

        for idx in df_p.index[missing]:
            rec = df_p.at[idx, "recording_name"]
            path_st = Path(recording_cache.sweeptimes_parquet_path(str(data_dir), rec))
            path_data = Path(recording_cache.data_parquet_path(str(data_dir), rec))
            try:
                sweep_hz = None
                if path_st.exists():
                    st = pd.read_parquet(path_st)
                    sweep_hz = parse.compute_sweep_hz(None, sweeptimes=st)
                elif path_data.exists():
                    # Legacy fat data parquet with per-sample datetime
                    schema = pq.read_schema(str(path_data))
                    available = set(schema.names)
                    if "sweep" in available and "datetime" in available:
                        df_raw = pd.read_parquet(str(path_data), columns=["sweep", "datetime"])
                        sweep_hz = parse.compute_sweep_hz(df_raw)
                if sweep_hz is not None:
                    df_p.at[idx, "sweep_hz"] = sweep_hz
                    # Clear the "default Hz" status flag.
                    flags = [f for f in str(df_p.at[idx, "status"]).split("|") if f != "default Hz"]
                    df_p.at[idx, "status"] = "|".join(flags)
                    updated += 1
            except Exception as exc:
                print(f"_backfill_sweep_hz: skipping {rec}: {exc}")
        if updated:
            print(f"_backfill_sweep_hz: computed sweep_hz for {updated} recording(s)")
            self.save_df_project()

    def _migrate_hierarchy(self, df: pd.DataFrame) -> pd.DataFrame:
        """v0.16_n: Apply statistical_protocol defaults on load/import.

        - Adds 'subject'/'slice' columns if missing (backcompat).
        - Lowest-unique-integer subjects (respects manual values; fills gaps).
        - Default slice="1" (one-slice-per-animal assumption).
        - Uses string dtype for both (flexible labels; Option A from plan).
        - Called from load_df_project, set_df_project, and import paths.
        """
        if "subject" not in df.columns:
            df["subject"] = None
        if "slice" not in df.columns:
            df["slice"] = None

        # Force string dtype (prevents int64 inference from numeric defaults like "1"/"2")
        for col in ("subject", "slice"):
            if df[col].dtype != "object" and not pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].astype("object")

        # Canonical string keys so stats n_unit collapse treats 1 / "1" / 1.0 as one subject
        try:
            from brainwash_stats.data import _normalize_hierarchy_key
        except Exception:
            _normalize_hierarchy_key = lambda v: None if pd.isna(v) else str(v).strip()

        for i, row in df.iterrows():
            for hcol in ("subject", "slice"):
                raw = row.get(hcol)
                if pd.isna(raw) or str(raw).strip() == "":
                    continue
                canon = _normalize_hierarchy_key(raw)
                if canon is not None:
                    df.at[i, hcol] = canon

        # Lowest-unique-integer subjects (string)
        existing_subs = set()
        for s in df["subject"].dropna().unique():
            c = _normalize_hierarchy_key(s)
            if c is not None:
                existing_subs.add(c)
        next_id = 1
        for i, row in df.iterrows():
            subj = row.get("subject")
            if pd.isna(subj) or str(subj).strip() == "":
                while str(next_id) in existing_subs:
                    next_id += 1
                df.at[i, "subject"] = str(next_id)
                existing_subs.add(str(next_id))
                next_id += 1
            slc = row.get("slice")
            if pd.isna(slc) or str(slc).strip() == "":
                df.at[i, "slice"] = "1"
        return df

    def save_df_project(self):  # writes df_project to .csv
        path = self.dict_folders["project"] / "project.brainwash"
        self.df_project.to_csv(str(path), index=False)

    def setupFolders(self):
        self.dict_folders = self.build_dict_folders()
        # DEBUG: clear cache and timepoints folders
        if self.config.clear_cache:
            self.deleteFolder(self.dict_folders["cache"])
        if self.config.clear_timepoints:
            self.deleteFolder(self.dict_folders["timepoints"])
        if self.config.clear_project_folder:
            self.deleteFolder(self.dict_folders["project"])
        # Make sure the necessary folders exist
        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)
        if not os.path.exists(self.dict_folders["cache"]):
            os.makedirs(self.dict_folders["cache"])
        if not os.path.exists(self.dict_folders["timepoints"]):
            os.makedirs(self.dict_folders["timepoints"])
        if not os.path.exists(self.dict_folders["stim_intensity"]):
            os.makedirs(self.dict_folders["stim_intensity"])

    def setupToolBar(self):
        # apply viewstates for tool frames in the toolbar
        for frame, (text, state) in list(self.uistate.project.viewTools.items()):
            if frame == "frameToolType_sub_io_stim":
                continue  # pin ∧ IO ∧ stim — applied below
            if hasattr(self, frame):
                getattr(self, frame).setVisible(state)
        self.frameToolFilter_sub_Savgol.setVisible(self.uistate.project.settings.get("filter", "voltage") == "savgol")
        if hasattr(self, "frameToolType_sub_io"):
            self.frameToolType_sub_io.setVisible(self._is_io_mode())
        self._update_io_stim_frame_visibility()
        if hasattr(self, "frameToolTest"):
            self.frameToolTest.setVisible(self._should_show_stat_test_frame())  # controlled ONLY by menu or hide button (viewTools); no auto-hide on IO
        if hasattr(self, "frameToolTestOptions"):
            self.frameToolTestOptions.setVisible(True)
        # Blinded strip is not in viewTools (cannot hide via View menu)
        self._sync_blinded_toolframe()

    # ------------------------------------------------------------------
    # Recording name blinding (#5) — display only
    # ------------------------------------------------------------------

    def _update_window_title(self):
        """Window title: Brainwash {version} - {project}[ - BLINDED][ - Talkback online]."""
        if not hasattr(self, "mainwindow") or self.mainwindow is None:
            return
        version = getattr(self.config, "version", "")
        name = getattr(self, "projectname", "") or ""
        title = f"Brainwash {version} - {name}"
        if getattr(self.uistate.project, "blind_recordings", False):
            title += " - BLINDED"
        if getattr(self.config, "talkback", False):
            title += " - Talkback online"
        self.mainwindow.setWindowTitle(title)

    def _ensure_blind_aliases(self, *, force_new: bool = False):
        """Ensure rec_ID → Rec n map for the current blind episode.

        force_new: discard any map and mint a fresh random bijection (Blind recordings).
        Otherwise preserve the episode map and only fill in newly added IDs.
        """
        from brainwash_ui import plot_identity

        df_p = self.get_df_project() if hasattr(self, "get_df_project") else getattr(self, "df_project", None)
        if df_p is None or getattr(df_p, "empty", True) or "ID" not in getattr(df_p, "columns", []):
            self.uistate.project.blind_aliases = {}
            return
        existing = None if force_new else (self.uistate.project.blind_aliases or None)
        self.uistate.project.blind_aliases = plot_identity.build_blind_aliases(
            df_p["ID"].tolist(),
            existing=existing,
        )

    def _sync_rec_display_labels_for_blind(self):
        """Rewrite dict_rec_labels display_label stems real↔blind without changing storage keys."""
        from brainwash_ui import plot_identity

        proj = self.uistate.project
        blind = bool(proj.blind_recordings)
        aliases = proj.blind_aliases or {}
        df_p = self.get_df_project() if hasattr(self, "get_df_project") else getattr(self, "df_project", None)
        id_to_real = {}
        if df_p is not None and not getattr(df_p, "empty", True) and "ID" in df_p.columns:
            for _, row in df_p.iterrows():
                rid = row["ID"]
                real = row.get("recording_name", "")
                id_to_real[rid] = real
                id_to_real[str(rid)] = real

        store = getattr(self.uistate.plot, "dict_rec_labels", None) or {}
        for _key, entry in store.items():
            if not isinstance(entry, dict):
                continue
            rid = entry.get("rec_ID")
            real = id_to_real.get(rid)
            if real is None:
                real = id_to_real.get(str(rid))
            if real is None:
                continue
            display = plot_identity.display_recording_name(rid, real, blind=True, aliases=aliases)
            old_label = entry.get("display_label") or ""
            if blind:
                new_label = plot_identity.replace_recording_stem(str(old_label), str(real), str(display))
            else:
                new_label = plot_identity.replace_recording_stem(str(old_label), str(display), str(real))
            entry["display_label"] = new_label
            line = entry.get("line")
            if line is not None and hasattr(line, "set_label"):
                try:
                    cur = line.get_label()
                    if cur and not str(cur).startswith("_"):
                        if blind:
                            line.set_label(plot_identity.replace_recording_stem(str(cur), str(real), str(display)))
                        else:
                            line.set_label(plot_identity.replace_recording_stem(str(cur), str(display), str(real)))
                    else:
                        line.set_label(new_label)
                except Exception:
                    pass

    def _sync_blinded_toolframe(self):
        """Show compact Blinded strip at top of tools when blinded; hide when not.

        Not registered in viewTools — no View-menu hide. Double-click × unblinds.
        """
        if not hasattr(self, "verticalLayout_2"):
            return
        blind = bool(getattr(self.uistate.project, "blind_recordings", False))
        frame = getattr(self, "frameToolBlinded", None)
        if frame is None:
            parent = getattr(self, "scrollAreaWidgetContentsTools", None)
            frame = QtWidgets.QFrame(parent)
            frame.setObjectName("frameToolBlinded")
            size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            frame.setSizePolicy(size_policy)
            frame.setMinimumSize(QtCore.QSize(201, 36))
            frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
            frame.setFrameShadow(QtWidgets.QFrame.Raised)
            row = QtWidgets.QHBoxLayout(frame)
            row.setContentsMargins(8, 4, 4, 4)
            row.setSpacing(4)
            label = QtWidgets.QLabel("Blinded")
            label.setObjectName("label_blinded")
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            remove_btn = ui_widgets.EntityRemoveButton(0, "BLINDED", object_prefix="blind_unblind")
            remove_btn.removeRequested.connect(lambda _id: self.triggerUnblindRecordings())
            remove_btn.hoverEntered.connect(self._on_blind_unblind_hover_enter)
            remove_btn.hoverLeft.connect(self._on_entity_remove_hover_leave)
            row.addWidget(label, 1)
            row.addWidget(remove_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.verticalLayout_2.insertWidget(0, frame)
            self.frameToolBlinded = frame
            self._blind_unblind_btn = remove_btn
        frame.setVisible(blind)

    def _on_blind_unblind_hover_enter(self, _entity_ID, _entity_name):
        if not hasattr(self, "set_statusbar"):
            return
        self.uistate.stat_test.statusbar_state = "attention"
        self.set_statusbar("attention", "Double-click to unblind")

    def _clear_recording_selection(self):
        """Deselect project table and clear plot selection lists (after Blind)."""
        if hasattr(self, "tableProj") and self.tableProj is not None:
            try:
                self.tableProj.clearSelection()
            except Exception:
                pass
        if hasattr(self, "uistate"):
            self.uistate.plot.list_idx_select_recs = []
            self.uistate.plot.df_recs2plot = None

    def _sync_blind_menu_action(self):
        """Data menu: Blind recordings only; hidden while blinded (unblind via strip ×)."""
        action = getattr(self, "actionBlindRecordings", None)
        if action is None:
            return
        action.setText("Blind recordings")
        action.setVisible(not bool(getattr(self.uistate.project, "blind_recordings", False)))
        action.setEnabled(True)

    def _sync_talkback_menu_action(self):
        action = getattr(self, "actionTalkback", None)
        if action is None:
            return
        action.setChecked(bool(getattr(self.config, "talkback", False)))

    def triggerTalkback(self, checked=False):
        """Data menu: global talkback on/off → bw_cfg.yaml + window title."""
        self.config.talkback = bool(checked)
        if hasattr(self, "actionTalkback"):
            self.actionTalkback.setChecked(self.config.talkback)
        self.write_bw_cfg()
        if self.config.talkback and hasattr(self, "setupTalkback"):
            self.setupTalkback()
        if hasattr(self, "_update_window_title"):
            self._update_window_title()
        # Log the toggle only when enabling (usage() no-ops when talkback is off)
        if hasattr(self, "usage"):
            self.usage(f"triggerTalkback → {self.config.talkback}")

    def triggerAlwaysBlindNewProjects(self, checked=False):
        """Data menu checkbox → global bw_cfg.yaml; applied only on New project."""
        self.always_blind_new_projects = bool(checked)
        if hasattr(self, "actionAlwaysBlindNewProjects"):
            self.actionAlwaysBlindNewProjects.setChecked(self.always_blind_new_projects)
        self.write_bw_cfg()
        if hasattr(self, "usage"):
            self.usage(f"triggerAlwaysBlindNewProjects → {self.always_blind_new_projects}")

    def triggerBlindRecordings(self):
        """Data → Blind recordings: new random aliases, deselect, sort by display name."""
        if getattr(self.uistate.project, "blind_recordings", False):
            return
        # Each Blind episode mints a fresh map (unblind destroyed the previous one).
        self._ensure_blind_aliases(force_new=True)
        self.uistate.project.blind_recordings = True
        self.uistate.project.project_table_sort = {"column": "recording_name", "order": 0}
        self._clear_recording_selection()
        self._apply_blind_ui_state(restore_selection=False)
        if hasattr(self, "_save_cfg_now"):
            self._save_cfg_now()
        elif hasattr(self, "dict_folders"):
            self.uistate.save_cfg(projectfolder=self.dict_folders["project"])
        if hasattr(self, "usage"):
            self.usage("triggerBlindRecordings")

    def triggerUnblindRecordings(self):
        """Blinded toolframe × only: restore real names; destroy placeholders."""
        if not getattr(self.uistate.project, "blind_recordings", False):
            return
        # Rewrite legends while aliases still present, then destroy the episode map.
        self.uistate.project.blind_recordings = False
        self._sync_rec_display_labels_for_blind()
        self.uistate.project.blind_aliases = {}
        self._apply_blind_ui_state(skip_label_rewrite=True, restore_selection=True)
        if hasattr(self, "_save_cfg_now"):
            self._save_cfg_now()
        elif hasattr(self, "dict_folders"):
            self.uistate.save_cfg(projectfolder=self.dict_folders["project"])
        if hasattr(self, "usage"):
            self.usage("triggerUnblindRecordings")

    def _apply_blind_ui_state(self, *, skip_label_rewrite: bool = False, restore_selection: bool = True):
        """Title, strip, table DisplayRole, legend stems, menu label, graph refresh."""
        if not skip_label_rewrite and getattr(self.uistate.project, "blind_recordings", False):
            self._sync_rec_display_labels_for_blind()
        self._update_window_title()
        self._sync_blinded_toolframe()
        self._sync_blind_menu_action()
        if hasattr(self, "tableUpdate"):
            self.tableUpdate(restore_selection=restore_selection)
        if hasattr(self, "graphRefresh"):
            self.graphRefresh(reeval_formal_test=False)

    def build_dict_folders(self):
        dict_folders = {
            "project": self.projects_folder / self.projectname,  # path to project folder
            "data": self.projects_folder / self.projectname / "data",  # path to project data subfolder
            "timepoints": self.projects_folder / self.projectname / "timepoints",  # path to project timepoints subfolder
            "stim_intensity": self.projects_folder / self.projectname / "stim_intensity",  # user-owned stim µA CSVs
            "cache": self.projects_folder / f"cache {self.config.version}" / self.projectname,  # path to project cache subfolder
        }
        return dict_folders

    def setSplitterSizes(self, *splitter_names):
        """Set splitter sizes from persisted proportions in self.uistate.project.splitter.
        Moved here in Phase 5 polish (lifecycle/setup belongs with ProjectMixin).
        """
        for splitter_name in splitter_names:
            splitter = getattr(self, splitter_name)
            proportions = self.uistate.project.splitter.get(splitter_name, [])
            widgets = [splitter.widget(i) for i in range(splitter.count())]
            if len(proportions) != len(widgets):
                continue

            is_horizontal = splitter.orientation() == QtCore.Qt.Horizontal
            total_size = splitter.window().width() if is_horizontal else splitter.window().height()

            if total_size < 100:
                total_size = 1580 if is_horizontal else 1205

            unbounded_prop = sum(p for p in proportions if type(p) == float)
            fixed_px = sum(p for p in proportions if type(p) != float)
            remaining_px = max(0, total_size - fixed_px)

            # Store the original size policies of the widgets, and set their size policy to QtWidgets.QSizePolicy.Ignored
            original_policies = []
            sizes = []
            for i, widget in enumerate(widgets):
                original_policies.append(widget.sizePolicy())
                widget.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

                p = proportions[i]
                if type(p) != float:
                    sizes.append(int((p / total_size) * 100000))
                else:
                    if unbounded_prop > 0:
                        target_px = (p / unbounded_prop) * remaining_px
                        sizes.append(int((target_px / total_size) * 100000))
                    else:
                        sizes.append(0)

            splitter.setSizes(sizes)
            for widget, policy in zip(widgets, original_policies):
                widget.setSizePolicy(policy)

    # ------------------------------------------------------------------
    # UI wiring + hierarchy + recording rename (Phase 5 polish)
    # ------------------------------------------------------------------

    def connectUIstate(self, disconnect=False):  # ternary (dis)connect of UI elements
        # experiment type radio button group
        if hasattr(self, "buttonGroup_type"):
            if disconnect:
                try:
                    self.buttonGroup_type.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_type.buttonClicked.connect(self.experiment_type_changed)
        # IO input radio button group
        if hasattr(self, "buttonGroup_io_i"):
            if disconnect:
                try:
                    self.buttonGroup_io_i.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_io_i.buttonClicked.connect(self.io_input_changed)
        # IO output radio button group
        if hasattr(self, "buttonGroup_io_o"):
            if disconnect:
                try:
                    self.buttonGroup_io_o.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_io_o.buttonClicked.connect(self.io_output_changed)
        # filter radio button group
        if disconnect:
            try:
                self.buttonGroup_filter.buttonClicked.disconnect()
            except TypeError:
                pass
        else:
            self.buttonGroup_filter.buttonClicked.connect(self.filter_mode_changed)
        # test type radio button group
        if hasattr(self, "buttonGroup_test"):
            if disconnect:
                try:
                    self.buttonGroup_test.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_test.buttonClicked.connect(self.test_type_changed)
        # test t variant radio button group
        if hasattr(self, "buttonGroup_test_t_variant"):
            if disconnect:
                try:
                    self.buttonGroup_test_t_variant.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_test_t_variant.buttonClicked.connect(self.test_t_variant_changed)
        # test t tails radio button group
        if hasattr(self, "buttonGroup_test_t_tails"):
            if disconnect:
                try:
                    self.buttonGroup_test_t_tails.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_test_t_tails.buttonClicked.connect(self.test_t_tails_changed)
        # test wilcox variant radio button group
        if hasattr(self, "buttonGroup_wilcoxon_variant"):
            if disconnect:
                try:
                    self.buttonGroup_wilcoxon_variant.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_wilcoxon_variant.buttonClicked.connect(self.test_wilcox_variant_changed)
        # test wilcox tails radio button group
        if hasattr(self, "buttonGroup_wilcoxon_tails"):
            if disconnect:
                try:
                    self.buttonGroup_wilcoxon_tails.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_wilcoxon_tails.buttonClicked.connect(self.test_wilcox_tails_changed)
        # v0.16_n_stats: n_unit radio group (minimal wiring per clarification; exact match to test_t_variant_changed pattern)
        if hasattr(self, "buttonGroup_test_n"):
            if disconnect:
                try:
                    self.buttonGroup_test_n.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_test_n.buttonClicked.connect(self.n_unit_changed)
        if hasattr(self, "buttonGroup_display_timecourse"):
            if disconnect:
                try:
                    self.buttonGroup_display_timecourse.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_display_timecourse.buttonClicked.connect(self.display_timecourse_style_changed)
        if hasattr(self, "buttonGroup_display_color"):
            if disconnect:
                try:
                    self.buttonGroup_display_color.buttonClicked.disconnect()
                except TypeError:
                    pass
            else:
                self.buttonGroup_display_color.buttonClicked.connect(self.display_color_events_changed)
        # hide buttons
        hide_buttons = {
            "pushButton_hide_stim": "frameToolStim",
            "pushButton_hide_sweeps": "frameToolSweeps",
            "pushButton_hide_tag": "frameToolTag",
            "pushButton_hide_bin": "frameToolBin",
            "pushButton_hide_type": "frameToolType",
            "pushButton_hide_filter": "frameToolFilter",
            "pushButton_hide_y_axis": "frameToolYscale",
            "pushButton_hide_display": "frameToolDisplay",
            "pushButton_hide_aspect": "frameToolAspect",
            "pushButton_hide_slope_width": "frameToolAspectSlope",
            "pushButton_hide_amplitude_width": "frameToolAspectAmp",
            "pushButton_hide_test": "frameToolTest",
            "pushButton_hide_IO_input_stim": "frameToolType_sub_io_stim",
        }
        for btn_name, frame_name in hide_buttons.items():
            if hasattr(self, btn_name):
                btn = getattr(self, btn_name)
                if disconnect:
                    try:
                        btn.clicked.disconnect()
                    except TypeError:
                        pass
                else:
                    btn.clicked.connect(lambda checked, f=frame_name: self.setViewToolVisible(f, visible=False))
        # IO stim strength table (bins → µA CSV) + Apply
        if hasattr(self, "tableWidget_stim_strength"):
            tw = self.tableWidget_stim_strength
            if disconnect:
                try:
                    tw.cellChanged.disconnect()
                except TypeError:
                    pass
            else:
                tw.cellChanged.connect(self.on_stim_strength_cell_changed)
        if hasattr(self, "pushButton_io_stim_strength_apply"):
            btn = self.pushButton_io_stim_strength_apply
            if disconnect:
                try:
                    btn.clicked.disconnect()
                except TypeError:
                    pass
            else:
                btn.clicked.connect(self.on_stim_strength_apply)
                btn.setEnabled(bool(getattr(self.uistate.plot, "stim_intensity_dirty", False)))
        # checkBoxes (project dict + stat_test-only widgets)
        checkbox_keys = list(self.uistate.project.checkBox.keys()) + ["test_fdr", "test_sw", "test_levene"]
        for key in checkbox_keys:
            if not hasattr(self, f"checkBox_{key}"):
                continue
            checkBox = getattr(self, f"checkBox_{key}")
            if disconnect:
                try:
                    checkBox.stateChanged.disconnect()
                except TypeError:
                    pass
            else:
                checkBox.stateChanged.connect(lambda state, key=key: self.viewSettingsChanged(key, state))
        # lineEdits
        for lineEdit in [
            self.lineEdit_split_at_time,
            self.lineEdit_import_gain,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editImportOptions(le))
        for lineEdit in [
            self.lineEdit_mean_selection_start,
            self.lineEdit_mean_selection_end,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editMeanSelectRange(le))
        for lineEdit in [
            self.lineEdit_sweeps_range_from,
            self.lineEdit_sweeps_range_to,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editSweepSelectRange(le))
        for lineEdit in [
            self.lineEdit_norm_EPSP_start,
            self.lineEdit_norm_EPSP_end,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editNormRange(le))
        # v0.16_n: hierarchy line-edits (Phase 1 two-way binding)
        if hasattr(self, "lineEdit_hierarchy_subject"):
            le = self.lineEdit_hierarchy_subject
            if disconnect:
                try:
                    le.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                le.editingFinished.connect(lambda: self.applyHierarchyToSelection("subject"))
        if hasattr(self, "lineEdit_hierarchy_slice"):
            le = self.lineEdit_hierarchy_slice
            if disconnect:
                try:
                    le.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                le.editingFinished.connect(lambda: self.applyHierarchyToSelection("slice"))
        for lineEdit in [
            self.lineEdit_EPSP_amp_halfwidth,
            self.lineEdit_volley_amp_halfwidth,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editAmpHalfwidth(le))
        for lineEdit in [
            self.lineEdit_EPSP_slope_width,
            self.lineEdit_volley_slope_width,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editSlopeWidth(le))
        for lineEdit in [
            self.lineEdit_bin_size,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editBinSize(le))
        for lineEdit in [
            self.lineEdit_savgol_window,
            self.lineEdit_savgol_poly,
        ]:
            if disconnect:
                try:
                    lineEdit.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                lineEdit.editingFinished.connect(lambda le=lineEdit: self.editSavgolParams(le))
        # one-sample t-test value (new in v0.16 science_test)
        if hasattr(self, "lineEdit_test_t_one_sample_value"):
            if disconnect:
                try:
                    self.lineEdit_test_t_one_sample_value.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                self.lineEdit_test_t_one_sample_value.editingFinished.connect(
                    lambda le=self.lineEdit_test_t_one_sample_value: self.editTestTOneSampleValue(le)
                )
        # one-sample wilcoxon value
        if hasattr(self, "lineEdit_wilcoxon_one_sample_value"):
            if disconnect:
                try:
                    self.lineEdit_wilcoxon_one_sample_value.editingFinished.disconnect()
                except TypeError:
                    pass
            else:
                self.lineEdit_wilcoxon_one_sample_value.editingFinished.connect(
                    lambda le=self.lineEdit_wilcoxon_one_sample_value: self.editTestWilcoxOneSampleValue(le)
                )

        # pushButtons
        for str_button, str_function in self.uistate.project.pushButtons.items():
            button, func = getattr(self, str_button), getattr(self, str_function)
            if disconnect:
                try:
                    button.pressed.disconnect()
                except TypeError:
                    pass
            else:
                button.pressed.connect(func)
        # SplitterMoved
        for splitter_name in self.uistate.project.splitter.keys():
            splitter = getattr(self, splitter_name)
            if disconnect:
                try:
                    splitter.splitterMoved.disconnect()
                except TypeError:
                    pass
            else:
                splitter.splitterMoved.connect(lambda pos, index, sn=splitter_name: self.onSplitterMoved(sn, pos, index))

    def applyConfigStates(self):
        if hasattr(self, "actionToggleProjectTable"):
            self.actionToggleProjectTable.setChecked(self.uistate.project.detailedProjectTable)

        if hasattr(self, "actionToggleTimetable"):
            self.actionToggleTimetable.setChecked(self.uistate.project.detailedTimetable)

        # Project table column sort from cfg (column name → model index + header arrow)
        if hasattr(self, "_sync_tablemodel_sort_from_project_pref"):
            self._sync_tablemodel_sort_from_project_pref(getattr(self, "df_project", None))
            if hasattr(self, "tablemodel") and getattr(self.tablemodel, "_sort_column", None) is not None:
                try:
                    self._suppress_table_sort_persist = True
                    self.tablemodel.sort(self.tablemodel._sort_column, self.tablemodel._sort_order)
                finally:
                    self._suppress_table_sort_persist = False
            if hasattr(self, "_sync_project_table_sort_indicator"):
                self._sync_project_table_sort_indicator()

        if hasattr(self, "actionTimetable"):
            self.actionTimetable.setChecked(self.uistate.project.showTimetable)

        if hasattr(self, "menuView"):
            for frame, (text, state) in self.uistate.project.viewTools.items():
                for action in self.menuView.actions():
                    if action.text() == text:
                        action.setChecked(state)
                        break

        # Disconnect signals to prevent editingFinished from triggering from .setText
        self.connectUIstate(disconnect=True)

        for key, value in self.uistate.project.checkBox.items():
            if hasattr(self, f"checkBox_{key}"):
                checkBox = getattr(self, f"checkBox_{key}")
                checkBox.setChecked(value)

        # Stat-test options live on uistate.stat_test (not project.checkBox); must sync widgets at launch
        for key in ("test_fdr", "test_sw", "test_levene"):
            if hasattr(self, f"checkBox_{key}"):
                getattr(self, f"checkBox_{key}").setChecked(bool(getattr(self.uistate.stat_test, key, False)))

        if self.uistate.project.settings.get("filter") == "savgol":
            self.radioButton_filter_savgol.setChecked(True)
        else:
            self.radioButton_filter_none.setChecked(True)

        # Output series style (Dots / Line); default dots
        style = getattr(self.uistate.project, "output_line_style", "dots")
        if style not in ("dots", "line"):
            style = "dots"
        self.uistate.project.output_line_style = style
        self.uistate.plot.output_line_style = style
        if hasattr(self, "radioButton_display_dots") and hasattr(self, "radioButton_display_line"):
            if style == "line":
                self.radioButton_display_line.setChecked(True)
            else:
                self.radioButton_display_dots.setChecked(True)

        # Color events by (Rec | Stim | Group); default rec
        ceb = getattr(self.uistate.project, "color_events_by", "rec")
        if ceb not in ("rec", "stim", "group"):
            ceb = "rec"
        self.uistate.project.color_events_by = ceb
        if hasattr(self, "radioButton_display_color_rec"):
            if ceb == "stim" and hasattr(self, "radioButton_display_color_stim_number"):
                self.radioButton_display_color_stim_number.setChecked(True)
            elif ceb == "group" and hasattr(self, "radioButton_display_color_group"):
                self.radioButton_display_color_group.setChecked(True)
            else:
                self.radioButton_display_color_rec.setChecked(True)

        self.lineEdit_savgol_window.setText(str(self.uistate.project.lineEdit.get("savgol_window", 9)))
        self.lineEdit_savgol_poly.setText(str(self.uistate.project.lineEdit.get("savgol_poly", 3)))

        self.lineEdit_norm_EPSP_start.setText(f"{self.uistate.project.lineEdit['norm_EPSP_from']}")
        self.lineEdit_norm_EPSP_end.setText(f"{self.uistate.project.lineEdit['norm_EPSP_to']}")
        self.lineEdit_split_at_time.setText(f"{self.uistate.project.lineEdit['split_at_time'] * 1000:g}")
        self.lineEdit_EPSP_amp_halfwidth.setText(f"{self.uistate.project.lineEdit['EPSP_amp_halfwidth_ms']}")
        self.lineEdit_volley_amp_halfwidth.setText(f"{self.uistate.project.lineEdit['volley_amp_halfwidth_ms']}")
        self.lineEdit_EPSP_slope_width.setText(f"{self.uistate.project.lineEdit.get('EPSP_slope_width_ms', 0)}")
        self.lineEdit_volley_slope_width.setText(f"{self.uistate.project.lineEdit.get('volley_slope_width_ms', 0)}")

        # apply experiment type radio button selection from config
        if hasattr(self, "buttonGroup_type"):
            type_radio_name = self._TYPE_TO_RADIO.get(self.uistate.experiment.experiment_type, "radioButton_type_time")
            if hasattr(self, type_radio_name):
                getattr(self, type_radio_name).setChecked(True)

        # apply IO input/output radio button selection from config
        if hasattr(self, "buttonGroup_io_i"):
            io_i_name = self._IO_I_TO_RADIO.get(self.uistate.experiment.io_input, "radioButton_io_vamp")
            if hasattr(self, io_i_name):
                getattr(self, io_i_name).setChecked(True)

        if hasattr(self, "buttonGroup_io_o"):
            io_o_name = self._IO_O_TO_RADIO.get(self.uistate.experiment.io_output, "radioButton_io_EPSPamp")
            if hasattr(self, io_o_name):
                getattr(self, io_o_name).setChecked(True)

        # apply test radio button selections from config
        if hasattr(self, "buttonGroup_test"):
            test_radio_name = self._TEST_TO_RADIO.get(self.uistate.stat_test.test_type, "radioButton_test_none")
            if hasattr(self, test_radio_name):
                getattr(self, test_radio_name).setChecked(True)
        if hasattr(self, "buttonGroup_test_t_variant"):
            variant_name = self._TEST_T_VARIANT_TO_RADIO.get(self.uistate.stat_test.test_t_variant, "radioButton_test_t_variant_unpaired")
            if hasattr(self, variant_name):
                getattr(self, variant_name).setChecked(True)
        if hasattr(self, "buttonGroup_test_t_tails"):
            tails_name = self._TEST_T_TAILS_TO_RADIO.get(self.uistate.stat_test.test_t_tails, "radioButton_test_t_tails_two")
            if hasattr(self, tails_name):
                getattr(self, tails_name).setChecked(True)
        if hasattr(self, "buttonGroup_wilcoxon_variant"):
            wilcox_variant_name = self._TEST_WILCOX_VARIANT_TO_RADIO.get(
                self.uistate.stat_test.test_wilcox_variant, "radioButton_wilcoxon_variant_paired"
            )
            if hasattr(self, wilcox_variant_name):
                getattr(self, wilcox_variant_name).setChecked(True)
        if hasattr(self, "buttonGroup_wilcoxon_tails"):
            wilcox_tails_name = self._TEST_WILCOX_TAILS_TO_RADIO.get(
                self.uistate.stat_test.test_wilcox_tails, "radioButton_wilcoxon_tails_two"
            )
            if hasattr(self, wilcox_tails_name):
                getattr(self, wilcox_tails_name).setChecked(True)
        # v0.16_n_stats: default n_unit radio to subject (per clarification + plan Phase 0)
        if hasattr(self, "buttonGroup_test_n"):
            default_n = self.uistate.stat_test.buttonGroup_test_n
            radio_name = self._TEST_N_TO_RADIO.get(default_n, "radioButton_test_n_subject")
            if hasattr(self, radio_name):
                getattr(self, radio_name).setChecked(True)

        if hasattr(self, "frameToolTest_sub_t"):
            self.frameToolTest_sub_t.setVisible(self.uistate.stat_test.test_type == "t-test")
            # hook the one-sample value lineEdit (default 0.0 from UIState)
            if hasattr(self, "lineEdit_test_t_one_sample_value"):
                val = self.uistate.stat_test.label_test_t_one_sample_value
                self.lineEdit_test_t_one_sample_value.setText(str(val))
        if hasattr(self, "frameToolTest_sub_ANOVA"):
            self.frameToolTest_sub_ANOVA.setVisible(self.uistate.stat_test.test_type in ("ANOVA", "ANCOVA"))
            if self.uistate.stat_test.test_type in ("ANOVA", "ANCOVA"):
                self.update_anova_label()
        if hasattr(self, "frameToolTest_sub_wilcoxon"):
            self.frameToolTest_sub_wilcoxon.setVisible(self.uistate.stat_test.test_type == "Wilcoxon")
            if self.uistate.stat_test.test_type == "Wilcoxon" and hasattr(self, "lineEdit_wilcoxon_one_sample_value"):
                val = self.uistate.stat_test.label_test_wilcox_one_sample_value
                self.lineEdit_wilcoxon_one_sample_value.setText(str(val))
        if hasattr(self, "_update_one_sample_ref_visibility"):
            self._update_one_sample_ref_visibility()
        # experiment_type drives IO regression; ANCOVA is normal test_type radio

        # Ensure tools column is treated as fixed pixels
        if len(self.uistate.project.splitter.get("h_splitterMaster", [])) == 4:
            if type(self.uistate.project.splitter["h_splitterMaster"][3]) == float:
                self.uistate.project.splitter["h_splitterMaster"][3] = 300

        # apply splitter proportions from project config, then show/hide dft and
        # re-apply sizes (hidden panes do not keep setSizes until visible)
        self.setSplitterSizes(*self.uistate.project.splitter.keys())
        self.setTableStimVisibility(self.uistate.project.showTimetable, initialize=True)
        self.connectUIstate()
        # Initial evaluation of test condition warnings on the statusbar (after config/test radios restored)
        self.update_test()

    def triggerHideHierarchy(self):
        self.usage("triggerHideHierarchy")
        self.setViewToolVisible("frameToolHierarchy", False)

    # v0.16_n Phase 1: selection → hierarchy line-edits (uniform/mixed logic like update_amp_lineEdits)
    def refreshHierarchyLineEdits(self, df_p=None):
        if df_p is None:
            df_p = self.get_df_project()
        if not hasattr(self, "lineEdit_hierarchy_subject"):
            return
        # prevent recursive editingFinished during setText
        self.connectUIstate(disconnect=True)
        idxs = self.uistate.plot.list_idx_select_recs or []
        if not idxs:
            self.lineEdit_hierarchy_subject.setText("")
            self.lineEdit_hierarchy_slice.setText("")
            self.connectUIstate()
            return
        # Prefer ID → df_project (source of truth after writes); avoids model/df index confusion.
        subs = []
        slices_list = []
        if hasattr(self, "_project_rows_for_selected"):
            selected = self._project_rows_for_selected()
            if not selected.empty:
                if "subject" in selected.columns:
                    subs = [str(v) for v in selected["subject"] if pd.notna(v)]
                if "slice" in selected.columns:
                    slices_list = [str(v) for v in selected["slice"] if pd.notna(v)]
        if not subs and not slices_list:
            # Fallback: model rows (list_idx must be table-model indices)
            model_df = getattr(getattr(self, "tablemodel", None), "_data", None)
            if model_df is not None and not model_df.empty and "subject" in model_df.columns:
                n = len(model_df)
                for i in idxs:
                    if 0 <= int(i) < n:
                        row = model_df.iloc[int(i)]
                        if pd.notna(row.get("subject")):
                            subs.append(str(row["subject"]))
                        if pd.notna(row.get("slice")):
                            slices_list.append(str(row["slice"]))
            else:
                subs = [str(df_p.at[i, "subject"]) for i in idxs if i in df_p.index and pd.notna(df_p.at[i, "subject"])]
                slices_list = [str(df_p.at[i, "slice"]) for i in idxs if i in df_p.index and pd.notna(df_p.at[i, "slice"])]
        subj_val = subs[0] if len(set(subs)) == 1 else ""
        slice_val = slices_list[0] if len(set(slices_list)) == 1 else ""
        self.lineEdit_hierarchy_subject.setText(subj_val)
        self.lineEdit_hierarchy_slice.setText(slice_val)
        self.connectUIstate()

    # v0.16_n Phase 1: line-edit edit → selected rows (immediate bulk assign)
    def applyHierarchyToSelection(self, col):
        """Write subject/slice from hierarchy lineEdit to selected recordings.

        Downstream: persist project, invalidate unit-level group/global caches and plots,
        replot groups, recompute active formal tests + statusbar (n and p depend on hierarchy).
        """
        self.usage(f"applyHierarchyToSelection({col})")
        le_name = f"lineEdit_hierarchy_{col}"
        if not hasattr(self, le_name):
            return
        text = getattr(self, le_name).text().strip()
        # Map view selection → recording IDs (table may be sorted independently of df_project)
        if hasattr(self, "_selected_recording_ids"):
            rec_ids = self._selected_recording_ids()
        else:
            idxs = self.uistate.plot.list_idx_select_recs or []
            model_df = getattr(getattr(self, "tablemodel", None), "_data", None)
            src = model_df if model_df is not None and not getattr(model_df, "empty", True) else self.get_df_project()
            rec_ids = [src.iloc[int(i)]["ID"] for i in idxs if 0 <= int(i) < len(src)]
        if not rec_ids:
            return
        df_p = self.get_df_project().copy()
        norm = getattr(self, "_norm_rec_id", lambda v: str(v))
        id_key = df_p["ID"].map(norm)
        mask = id_key.isin({norm(r) for r in rec_ids})
        if not mask.any():
            return
        if text:
            # Canonical string keys (1 / 1.0 / "1" → "1") so n_unit aggregation counts one unit
            try:
                from brainwash_stats.data import _normalize_hierarchy_key

                canon = _normalize_hierarchy_key(text)
                df_p.loc[mask, col] = canon if canon is not None else str(text).strip()
            except Exception:
                df_p.loc[mask, col] = str(text).strip()
        else:
            df_p.loc[mask, col] = pd.NA  # explicit NA; displays as blank
        selected_ids = list(rec_ids)

        # 1) Persist hierarchy into df_project (and table model)
        self.set_df_project(df_p)
        self.tableUpdate(restore_selection=False)
        # Reselect by ID on the *displayed* (possibly sorted) model — never df_project positions.
        if hasattr(self, "_select_project_table_rows") and hasattr(self, "_model_rows_for_rec_ids"):
            to_select = self._model_rows_for_rec_ids(selected_ids)
            self._select_project_table_rows(to_select)
        elif hasattr(self, "_select_project_table_rows") and hasattr(self, "_rows_for_rec_ids"):
            to_select = self._rows_for_rec_ids(self.get_df_project(), selected_ids)
            self._select_project_table_rows(to_select)
        else:
            self.tableUpdate(restore_selection=True)
        if hasattr(self, "update_recs2plot"):
            self.update_recs2plot()
        self.refreshHierarchyLineEdits()

        # 2) Invalidate anything that embeds old subject/slice aggregation
        if hasattr(self, "dict_global_units"):
            self.dict_global_units.clear()
        # Slice/subject group means + their artists (recording-level means unchanged)
        if hasattr(self, "group_cache_purge"):
            self.group_cache_purge(levels=["slice", "subject"])
        if hasattr(self.uiplot, "unPlotGroup"):
            self.uiplot.unPlotGroup()

        # 3) Rebuild group plots at current n_unit (if groups exist)
        if hasattr(self, "graphGroups"):
            self.graphGroups()
        if hasattr(self, "update_show"):
            self.update_show()

        # 4) Formal tests join subject/slice from df_project on each compute — force fresh run
        if hasattr(self, "clear_formal_test_results"):
            self.clear_formal_test_results()
        if hasattr(self, "update_test"):
            self.update_test()

        # 5) Canvas refresh (markers/statusbar already updated; avoid double test reeval)
        if hasattr(self, "graphRefresh"):
            self.graphRefresh(reeval_formal_test=False)

    def renameRecording(self):
        # renames all instances of selected recording_name in df_project, and their associated files
        if len(self.uistate.plot.list_idx_select_recs) != 1:
            print("Rename: please select one row only for renaming.")
            return
        df_p = self.get_df_project()
        old_recording_name = df_p.at[self.uistate.plot.list_idx_select_recs[0], "recording_name"]
        RenameDialog = ui_widgets.InputDialogPopup()
        new_recording_name = RenameDialog.showInputDialog(title="Rename recording", query=old_recording_name)
        # check if the new name is a valid filename
        if new_recording_name is not None and re.match(r"^[a-zA-Z0-9_ -]+$", str(new_recording_name)) is not None:
            list_recording_names = set(df_p["recording_name"])
            if not new_recording_name in list_recording_names:  # prevent duplicates
                self.rename_files_by_rec_name(old_name=old_recording_name, new_name=new_recording_name)
                df_p.at[self.uistate.plot.list_idx_select_recs[0], "recording_name"] = new_recording_name
                # For paired recordings: also rename any references to old_recording_name in df_p['paired_recording']
                df_p.loc[df_p["paired_recording"] == old_recording_name, "paired_recording"] = new_recording_name
                self.set_df_project(df_p)
                self.tableUpdate(restore_selection=True)  # preserve the renamed row selection
                self.update_recs2plot()
                old_recording_ID = df_p.at[self.uistate.plot.list_idx_select_recs[0], "ID"]
                self.uiplot.unPlot(old_recording_ID)
                self.graphUpdate(row=df_p.loc[self.uistate.plot.list_idx_select_recs[0]])
                self.update_show(reset=True)
            else:
                print(f"new_recording_name {new_recording_name} already exists")
        else:
            print(f"new_recording_name {new_recording_name} is not a valid filename")

    def rename_files_by_rec_name(self, old_name, new_name):
        from brainwash_ui import recording_cache

        data_sample = Path(recording_cache.data_parquet_path(str(self.dict_folders["data"]), old_name))
        if not data_sample.exists():
            print(f"recording_rename_files: file not found: {data_sample}")
            raise FileNotFoundError

        for old_path in recording_cache.iter_recording_disk_files(self.dict_folders, old_name):
            if not old_path.exists():
                continue
            # Replace trailing /{old_name}… with /{new_name}… on the same parent
            new_path = old_path.parent / old_path.name.replace(old_name, new_name, 1)
            if old_path != new_path:
                old_path.rename(new_path)

        # Stim intensity: path helper strips a redundant .csv so we never get .csv.csv
        if "stim_intensity" in self.dict_folders:
            old_si = Path(recording_cache.stim_intensity_csv_path(str(self.dict_folders["stim_intensity"]), old_name))
            new_si = Path(recording_cache.stim_intensity_csv_path(str(self.dict_folders["stim_intensity"]), new_name))
            if old_si.exists() and old_si != new_si:
                new_si.parent.mkdir(parents=True, exist_ok=True)
                old_si.rename(new_si)
            # Migrate accidental double-suffix files from earlier builds
            legacy = Path(self.dict_folders["stim_intensity"]) / f"{old_name}.csv.csv"
            if legacy.exists() and not new_si.exists():
                legacy.rename(new_si)

    def set_rec_status(self, rec_name=None):  # TODO: should run on ID - not name!
        # Updates df_project['status'] to 'manual' if there is a single manual point, else 'default' if there is a default point, else 'auto'
        # TODO: expand this to cover more issues with recordings and specify algorithm used.
        def status(rec_name, dfp, marker_list):
            prow = dfp[dfp["recording_name"] == rec_name]
            if isinstance(prow, pd.DataFrame):
                p_series = prow.iloc[0]
            else:
                p_series = prow
            dft = self.get_dft(p_series)
            for marker in marker_list:
                if marker in dft.values:
                    dfp.loc[dfp["recording_name"] == rec_name, "status"] = marker
                    logger.debug("set_rec_status: %s set to status = '%s'", rec_name, marker)
                    print(f"set_rec_status: {rec_name} set to status = '{marker}'")
                    return
            dfp.loc[dfp["recording_name"] == rec_name, "status"] = "auto"
            return

        # in order of priority, look for these markers in the timepoints dataframe
        marker_list = ["manual", "default"]
        dfp = self.get_df_project()

        if rec_name is not None:
            status(rec_name, dfp, marker_list)
        else:
            for i, row in dfp.iterrows():
                status(row["recording_name"], dfp, marker_list)

        self.set_df_project(dfp)
        # tableUpdate() touches Qt widgets and must only run on the GUI thread.
        # Worker threads (e.g. graphPreloadThread) call set_rec_status too, so
        # guard the call to avoid a cross-thread Qt deadlock.
        if QtCore.QThread.currentThread() is QtWidgets.QApplication.instance().thread():
            self.tableUpdate(restore_selection=False)  # worker thread; do not touch selection model

    # (DataFrame helpers in DataFrameMixin)

