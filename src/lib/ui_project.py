# ui_project.py
# ProjectMixin — project-level file I/O and bootstrapping extracted from UIsub (Phase 5 refactor).
# These methods handle project lifecycle (new/open/load/save), global config (bw_cfg),
# file persistence helpers (df2file, persistOutput), and the two main init methods
# (bootstrap, loadProject).
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import ui_project
#   ui_project.uistate          = uistate
#   ui_project.config           = config
#   ui_project.uiplot           = uiplot
#   ui_project.df_projectTemplate = df_projectTemplate
#   ui_project.InputDialogPopup = InputDialogPopup

from __future__ import annotations

import re
import socket
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from PyQt5 import QtCore, QtWidgets

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]
df_projectTemplate = None  # type: ignore[assignment]
InputDialogPopup = None  # type: ignore[assignment]


class ProjectMixin:
    """Mixin that provides project I/O, bootstrapping, and persistence helpers for UIsub."""

    # ------------------------------------------------------------------
    # Output persistence helper
    # ------------------------------------------------------------------

    def persistOutput(self, rec_name, dfoutput):
        # Determine column order based on the state of uistate.checkBox['output_per_stim']
        column_order = (
            [
                "stim",
                "bin",
                "EPSP_slope",
                "EPSP_slope_norm",
                "EPSP_amp",
                "EPSP_amp_norm",
                "volley_amp",
                "volley_slope",
            ]
            if uistate.checkBox["output_per_stim"]
            else [
                "stim",
                "sweep",
                "EPSP_slope",
                "EPSP_slope_norm",
                "EPSP_amp",
                "EPSP_amp_norm",
                "volley_amp",
                "volley_slope",
            ]
        )
        # Clean up column order, save to dict and file.
        missing_columns = set(column_order) - set(dfoutput.columns)
        extra_columns = set(dfoutput.columns) - set(column_order)
        if missing_columns:
            print(
                f"Warning: The following columns in column_order don't exist in dfoutput: {missing_columns}"
            )
        if extra_columns:
            print(
                f"Warning: The following columns exist in dfoutput but not in column_order: {extra_columns}"
            )
        dfoutput = dfoutput.reindex(columns=column_order)
        self.dict_outputs[rec_name] = dfoutput
        self.df2file(df=dfoutput, rec=rec_name, key="output")

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
            int(screen.width() * 0.96),
            int(screen.height()) - config.terminal_space,
        )

        self.get_bw_cfg()  # load/create bw global config file (not project specific)
        self.setupMenus()
        self.setupCanvases()  # for graphs, and connect graphClicked(event, <canvas>)

        self.fqdn = (
            socket.getfqdn()
        )  # get computer name and local domain, for project file

        # debug mode; for printing widget focus every 1000ms
        if config.track_widget_focus:
            self.timer = QtCore.QTimer(self)
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
            print(
                f"Project file {self.dict_folders['project'] / 'project.brainwash'} not found, creating new project file"
            )
            self.df_project = df_projectTemplate()
        # If local cfg.pkl exists, load it, otherwise create it
        uistate.reset()
        uistate.load_cfg(
            projectfolder=self.dict_folders["project"],
            bw_version=config.version,
            force_reset=config.force_cfg_reset,
        )
        self.mainwindow.setWindowTitle(
            f"Brainwash {config.version} - {self.projectname}"
        )

        # Load group data
        self.dd_groups = self.group_get_dd()
        self.group_update_dfp()
        if config.talkback:
            self.setupTalkback()
        # Set up canvases and graphs
        self.groupControlsRefresh()  # add group controls to UI
        self.connectUIstate()  # connect UI elements to uistate
        self.applyConfigStates()  # apply config states to UI elements
        self.graphAxes()
        self.darkmode()  # set darkmode if set in bw_cfg. Requires tables and canvases be loaded!
        self.setTableStimVisibility(uistate.showTimetable)
        self.setupToolBar()
        # set focus to TableProj, so that arrows work immediately
        self.tableProj.setFocus()
        self.updating_tableProj = False

    # ------------------------------------------------------------------
    # Global config (bw_cfg.yaml)
    # ------------------------------------------------------------------

    def get_bw_cfg(self):
        # Set default values
        self.user_documents = Path.home() / "Documents"
        self.projects_folder = self.user_documents / "Brainwash Projects"
        self.projectname = "My Project"
        uistate.darkmode = True
        uistate.showTimetable = False

        # Load config if present
        if config.bw_cfg_yaml is not None:
            self.bw_cfg_yaml = Path(config.bw_cfg_yaml)
            if self.bw_cfg_yaml.exists():
                with self.bw_cfg_yaml.open("r") as file:
                    cfg = yaml.safe_load(file) or {}
                    projectfolder = Path(cfg.get("projects_folder", "")) / cfg.get(
                        "projectname", ""
                    )
                    if projectfolder.exists():
                        self.user_documents = Path(
                            cfg.get("user_documents", self.user_documents)
                        )
                        self.projects_folder = Path(
                            cfg.get("projects_folder", self.projects_folder)
                        )
                        self.projectname = cfg.get("projectname", self.projectname)
                    uistate.darkmode = cfg.get("darkmode", False)
                    uistate.showTimetable = cfg.get("showTimetable", False)
        else:
            self.bw_cfg_yaml = None  # Make sure it's defined for consistency

    def write_bw_cfg(self):  # Save global program settings
        if config.transient or self.bw_cfg_yaml is None:
            return
        cfg = {
            "user_documents": str(self.user_documents),
            "projects_folder": str(self.projects_folder),
            "projectname": self.projectname,
            "darkmode": uistate.darkmode,
            "showTimetable": uistate.showTimetable,
        }
        # TODO: maybe this should go in a user-specific Brainwash folder
        with self.bw_cfg_yaml.open("w+") as file:
            yaml.safe_dump(cfg, file)

    # ------------------------------------------------------------------
    # File write helpers
    # ------------------------------------------------------------------

    def df2file(self, df, rec, key=None):
        # writes dict[rec] to <rec>_{dict}.parquet TODO: better description; replace "rec"
        if config.transient:
            return
        self.dict_folders["cache"].mkdir(exist_ok=True)
        filetype = "parquet"
        if key is None:
            filepath = f"{self.dict_folders['cache']}/{rec}.{filetype}"
        elif key == "timepoints":
            filepath = f"{self.dict_folders['timepoints']}/{rec}.{filetype}"
        elif key == "data":
            filepath = f"{self.dict_folders['data']}/{rec}.{filetype}"
            self.dict_folders["data"].mkdir(exist_ok=True)
        else:
            filepath = f"{self.dict_folders['cache']}/{rec}_{key}.{filetype}"

        df.to_parquet(filepath, index=False)
        print(f"saved {filepath}")

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def newProject(self):
        self.dict_folders["project"].mkdir(
            exist_ok=True
        )  # make sure the project folder exists
        # Find lowest integer to append to new_project_name to make it unique
        date = datetime.now().strftime("%Y-%m-%d")
        i = 0
        unique_project_name = "Project " + date  # Initialize with a base name
        while True:
            if i > 0:
                unique_project_name = "Project " + date + "(" + str(i) + ")"
            if not (self.projects_folder / unique_project_name).exists():
                break  # Found a unique name, exit loop
            if config.verbose:
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
        uiplot.unPlot()  # all rec plots
        uiplot.unPlotGroup()  # all group plots
        self.graphWipe()  # for good measure

    def renameProject(self):  # changes name of project folder and updates .cfg
        RenameDialog = InputDialogPopup()
        new_project_name = RenameDialog.showInputDialog(
            title="Rename project", query=""
        )
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if config.verbose:
                print(f"Project name {new_project_name} already exists")
        elif (
            re.match(r"^[a-zA-Z0-9_ -]+$", str(new_project_name)) is not None
        ):  # True if valid filename
            dict_old = self.dict_folders
            self.projectname = new_project_name
            self.dict_folders = self.build_dict_folders()
            dict_old["project"].rename(self.dict_folders["project"])
            if Path(dict_old["cache"]).exists():
                dict_old["cache"].rename(self.dict_folders["cache"])
            self.write_bw_cfg()  # update boot-up-path in bw_cfg.yaml to new project folder
            self.mainwindow.setWindowTitle(
                f"Brainwash {config.version} - {self.projectname}"
            )
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
            self.df_project = df
        self.save_df_project()

    def load_df_project(
        self, str_projectfolder
    ):  # reads or builds project cfg and groups. Reads fileversion of df_project and saves bw_cfg
        self.graphWipe()
        self.resetCacheDicts()  # clear internal caches
        path_projectfolder = Path(str_projectfolder)
        self.projectname = str(path_projectfolder.stem)
        print(f"load_df_project: {self.projectname}")
        self.dict_folders = self.build_dict_folders()
        self.df_project = pd.read_csv(
            str(path_projectfolder / "project.brainwash"), dtype={"group_IDs": str}
        )
        uistate.load_cfg(self.dict_folders["project"], config.version)
        self.tableFormat()
        self.write_bw_cfg()

    def save_df_project(self):  # writes df_project to .csv
        self.df_project.to_csv(
            str(self.dict_folders["project"] / "project.brainwash"), index=False
        )
