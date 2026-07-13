# ui_project.py
# ProjectMixin — project-level file I/O and bootstrapping extracted from UIsub (Phase 5 refactor).
# These methods handle project lifecycle (new/open/load/save), global config (bw_cfg),
# file persistence helpers (df2file, persistOutput), and the two main init methods
# (bootstrap, loadProject).
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

import pandas as pd
import pyarrow.parquet as pq
import yaml
from PyQt5 import QtCore, QtWidgets

import lib.parse as parse
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
        self.mainwindow.setWindowTitle(f"Brainwash {self.config.version} - {self.projectname}")

        # Load group data
        self.dd_groups = self.group_get_dd()
        self.group_update_dfp()
        # Load test set data (integer set_ID based, defaults "set 1", "set 2", ...; persisted in test_sets.pkl)
        self.dd_testsets = self.testset_get_dd()
        self.dd_group_samples = {}  # phase 3.3: group_ID -> {test_ID: df}; populated lazily via get_ddgroup_sample()
        if self.config.talkback:
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
        else:
            filepath = f"{self.dict_folders['cache']}/{filename}_{key}.{filetype}"

        df.to_parquet(filepath, index=False)
        print(f"saved {filepath}")

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
            self.mainwindow.setWindowTitle(f"Brainwash {self.config.version} - {self.projectname}")
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
        self.uistate.load_cfg(self.dict_folders["project"], self.config.version)
        self.syncJournalExportMenu()
        self.tableUpdate(restore_selection=False)  # initial load; selection set by later tableProjSelectionChanged
        self.write_bw_cfg()

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
        for idx in df_p.index[missing]:
            rec = df_p.at[idx, "recording_name"]
            path_data = data_dir / f"{rec}.parquet"
            if not path_data.exists():
                continue
            try:
                # Read only the columns needed — fast even for large files.
                schema = pq.read_schema(str(path_data))
                available = set(schema.names)
                if "sweep" not in available or "datetime" not in available:
                    continue
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

        # Lowest-unique-integer subjects (string)
        existing_subs = set(df["subject"].dropna().astype(str).unique())
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

    def setupToolBar(self):
        # apply viewstates for tool frames in the toolbar
        for frame, (text, state) in list(self.uistate.project.viewTools.items()):
            if hasattr(self, frame):
                getattr(self, frame).setVisible(state)
        self.frameToolFilter_sub_Savgol.setVisible(self.uistate.project.settings.get("filter", "voltage") == "savgol")
        if hasattr(self, "frameToolType_sub_io"):
            self.frameToolType_sub_io.setVisible(self._is_io_mode())
        if hasattr(self, "frameToolTest"):
            self.frameToolTest.setVisible(self._should_show_stat_test_frame())  # controlled ONLY by menu or hide button (viewTools); no auto-hide on IO
        if hasattr(self, "frameToolTestOptions"):
            self.frameToolTestOptions.setVisible(True)

    def build_dict_folders(self):
        dict_folders = {
            "project": self.projects_folder / self.projectname,  # path to project folder
            "data": self.projects_folder / self.projectname / "data",  # path to project data subfolder
            "timepoints": self.projects_folder / self.projectname / "timepoints",  # path to project timepoints subfolder
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
