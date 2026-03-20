import export_image
from PyQt5 import QtWidgets

uistate = None


class MenuMixin:
    def setupMenus(self):
        # File menu
        self.actionNew = QtWidgets.QAction("New project")
        self.actionNew.triggered.connect(self.triggerNewProject)
        self.actionNew.setShortcut("Ctrl+N")
        self.menuFile.addAction(self.actionNew)

        self.actionOpen = QtWidgets.QAction("Open project")
        self.actionOpen.triggered.connect(self.triggerOpenProject)
        self.actionOpen.setShortcut("Ctrl+O")
        self.menuFile.addAction(self.actionOpen)

        self.actionRenameProject = QtWidgets.QAction("Rename project")
        self.actionRenameProject.triggered.connect(self.renameProject)
        self.actionRenameProject.setShortcut("Ctrl+R")
        self.menuFile.addAction(self.actionRenameProject)

        self.actionExit = QtWidgets.QAction("Exit")
        self.actionExit.triggered.connect(QtWidgets.qApp.quit)
        # self.actionExit.setShortcut("Ctrl+Q")  # Set shortcut for Exit
        self.menuFile.addAction(self.actionExit)

        # Edit menu
        # self.actionUndo = QtWidgets.QAction("Undo", self) # TODO: Implement undo
        # self.actionUndo.triggered.connect(self.triggerUndo)
        # self.actionUndo.setShortcut("Ctrl+Z")
        # self.menuEdit.addAction(self.actionUndo)

        self.actionSetGain = QtWidgets.QAction("Set gain")
        self.actionSetGain.triggered.connect(self.triggerSetGain)
        self.actionSetGain.setShortcut("G")
        self.menuEdit.addAction(self.actionSetGain)

        self.actionSetSweepHz = QtWidgets.QAction("Set sweep Hz")
        self.actionSetSweepHz.triggered.connect(self.triggerSetSweepHz)
        self.menuEdit.addAction(self.actionSetSweepHz)

        self.menuEdit.addSeparator()

        self.actionSweepOpsHeader = QtWidgets.QAction(
            "   — sweep selection —"
        )  # not connected: section header
        self.menuEdit.addAction(self.actionSweepOpsHeader)

        self.actionKeepOnlySelectedSweeps = QtWidgets.QAction(
            "   Keep only selected sweeps"
        )
        self.actionKeepOnlySelectedSweeps.triggered.connect(
            self.triggerKeepSelectedSweeps
        )
        self.menuEdit.addAction(self.actionKeepOnlySelectedSweeps)

        self.actionRemoveSelectedSweeps = QtWidgets.QAction(
            "   Discard selected sweeps"
        )
        self.actionRemoveSelectedSweeps.triggered.connect(
            self.triggerRemoveSelectedSweeps
        )
        self.menuEdit.addAction(self.actionRemoveSelectedSweeps)

        self.actionSplitBySelectedSweeps = QtWidgets.QAction(
            "   Split recordings by selected sweeps"
        )
        self.actionSplitBySelectedSweeps.triggered.connect(
            self.triggerSplitBySelectedSweeps
        )
        self.menuEdit.addAction(self.actionSplitBySelectedSweeps)

        self.actionTimeOpsHeader = QtWidgets.QAction(
            "   — time selection —"
        )  # not connected: section header
        self.menuEdit.addAction(self.actionTimeOpsHeader)

        self.actionKeepOnlySelectedTime = QtWidgets.QAction(
            "   Keep only selected time"
        )
        self.actionKeepOnlySelectedTime.triggered.connect(self.triggerKeepSelectedTime)
        self.menuEdit.addAction(self.actionKeepOnlySelectedTime)

        self.actionDiscardSelectedTime = QtWidgets.QAction("   Discard selected time")
        self.actionDiscardSelectedTime.triggered.connect(
            self.triggerDiscardSelectedTime
        )
        self.menuEdit.addAction(self.actionDiscardSelectedTime)

        self.actionSplitByTime = QtWidgets.QAction("   Split recordings by time")
        self.actionSplitByTime.triggered.connect(self.triggerSplitByTime)
        self.menuEdit.addAction(self.actionSplitByTime)

        # View menu
        self.actionRefresh = QtWidgets.QAction("Refresh Graphs")
        self.actionRefresh.triggered.connect(self.triggerRefresh)
        self.actionRefresh.setShortcut("F5")
        self.menuView.addAction(self.actionRefresh)

        self.actionHeatmap = QtWidgets.QAction("Toggle Heatmap")
        self.actionHeatmap.setCheckable(True)
        self.actionHeatmap.setChecked(uistate.showHeatmap)
        self.actionHeatmap.setShortcut("H")
        self.actionHeatmap.triggered.connect(self.triggerShowHeatmap)
        self.menuView.addAction(self.actionHeatmap)

        self.actionDarkmode = QtWidgets.QAction("Toggle Darkmode")
        self.actionDarkmode.triggered.connect(self.triggerDarkmode)
        self.actionDarkmode.setShortcut("Alt+D")
        self.menuView.addAction(self.actionDarkmode)

        self.actionTimetable = QtWidgets.QAction("Toggle Timetable")
        self.actionTimetable.setCheckable(True)
        self.actionTimetable.setChecked(uistate.showTimetable)
        self.actionTimetable.setShortcut("Alt+T")
        self.actionTimetable.triggered.connect(self.triggerShowTimetable)
        self.menuView.addAction(self.actionTimetable)

        # Dynamically add a checkable toggle per toolbar panel (frame name → [title, visible])
        # lambda captures frame by default arg to avoid closure-over-loop-variable bug
        for frame, (text, initial_state) in uistate.viewTools.items():
            action = QtWidgets.QAction(f"Toggle {text}", self.menuView)
            action.setCheckable(True)
            action.setChecked(initial_state)
            action.triggered.connect(
                lambda state, frame=frame: self.toggleViewTool(frame)
            )
            self.menuView.addAction(action)

        # Data menu
        self.actionAddData = QtWidgets.QAction("Add data files")
        self.actionAddData.triggered.connect(self.triggerAddData)
        self.menuData.addAction(self.actionAddData)

        self.actionParse = QtWidgets.QAction("Import all added datafiles")
        self.actionParse.triggered.connect(self.triggerParse)
        self.actionParse.setShortcut("Ctrl+I")
        self.menuData.addAction(self.actionParse)

        self.actionDelete = QtWidgets.QAction("Delete selected data")
        self.actionDelete.triggered.connect(self.triggerDelete)
        self.actionDelete.setShortcut("DEL")
        self.menuData.addAction(self.actionDelete)

        self.actionRenameRecording = QtWidgets.QAction("Rename recording")
        self.actionRenameRecording.triggered.connect(self.triggerRenameRecording)
        self.actionRenameRecording.setShortcut("F2")
        self.menuData.addAction(self.actionRenameRecording)

        self.actionReAnalyzeRecordings = QtWidgets.QAction("Reanalyze selected")
        self.actionReAnalyzeRecordings.triggered.connect(self.triggerReanalyze)
        self.actionReAnalyzeRecordings.setShortcut("A")
        self.menuData.addAction(self.actionReAnalyzeRecordings)

        # Group menu
        self.actionNewGroup = QtWidgets.QAction("Add a group")
        self.actionNewGroup.triggered.connect(self.triggerNewGroup)
        self.actionNewGroup.setShortcut("+")
        self.menuGroups.addAction(self.actionNewGroup)

        self.actionRemoveEmptyGroup = QtWidgets.QAction("Remove last empty group")
        self.actionRemoveEmptyGroup.triggered.connect(self.triggerRemoveLastEmptyGroup)
        self.actionRemoveEmptyGroup.setShortcut("-")
        self.menuGroups.addAction(self.actionRemoveEmptyGroup)

        self.actionRemoveGroup = QtWidgets.QAction("Force remove last group")
        self.actionRemoveGroup.triggered.connect(self.triggerRemoveLastGroup)
        self.actionRemoveGroup.setShortcut("Ctrl+-")
        self.menuGroups.addAction(self.actionRemoveGroup)

        self.actionClearGroups = QtWidgets.QAction("Clear group(s) in selection")
        self.actionClearGroups.triggered.connect(self.triggerClearGroups)
        self.menuGroups.addAction(self.actionClearGroups)

        self.actionResetGroups = QtWidgets.QAction("Remove all groups")
        self.actionResetGroups.triggered.connect(self.triggerEditGroups)
        self.menuGroups.addAction(self.actionResetGroups)

        # Export menu (triggers → ExportMixin in export_data.py)
        # — Copy section —
        self.actionCopyProjectSummary = QtWidgets.QAction("Copy project summary")
        self.actionCopyProjectSummary.triggered.connect(self.triggerCopyProjectSummary)
        self.menuExport.addAction(self.actionCopyProjectSummary)

        self.actionCopyTimepoints = QtWidgets.QAction("Copy timepoints")
        self.actionCopyTimepoints.triggered.connect(self.triggerCopyTimepoints)
        self.actionCopyTimepoints.setShortcut("Ctrl+T")
        self.menuExport.addAction(self.actionCopyTimepoints)

        self.actionCopyOutput = QtWidgets.QAction("Copy output")
        self.actionCopyOutput.triggered.connect(self.triggerCopyOutput)
        self.actionCopyOutput.setShortcut("Ctrl+C")
        self.menuExport.addAction(self.actionCopyOutput)

        self.menuExport.addSeparator()

        # — Sweeps section —
        self.actionExportSweepsCsv = QtWidgets.QAction("Export sweeps to .csv")
        self.actionExportSweepsCsv.triggered.connect(self.triggerExportSweepsCsv)
        self.menuExport.addAction(self.actionExportSweepsCsv)

        self.menuExport.addSeparator()

        # — Output section —
        self.actionExportOutputCsv = QtWidgets.QAction("Export output to .csv")
        self.actionExportOutputCsv.triggered.connect(self.triggerExportOutputCsv)
        self.menuExport.addAction(self.actionExportOutputCsv)

        self.menuExport.addSeparator()

        # — Image section —
        self.actionExportToHeader = QtWidgets.QAction(
            "   — Export to... —", self.menuExport
        )
        self.menuExport.addAction(self.actionExportToHeader)

        self.journalActionGroup = QtWidgets.QActionGroup(self.menuExport)
        self.journalActionGroup.setExclusive(True)

        journals = {}
        for key, template in export_image.JOURNAL_TEMPLATES.items():
            if "_" in key:
                j_key = key.split("_")[0]
                if j_key not in journals:
                    j_name = template.name.split(" (")[0]
                    if j_key == "jneurosci":
                        j_name = "Neuroscience"
                    journals[j_key] = j_name

        for j_key, j_name in journals.items():
            action = QtWidgets.QAction(f"   {j_name}", self.menuExport)
            action.setCheckable(True)
            action.setData(j_key)
            if uistate.settings.get("journal_export", "jneurosci") == j_key:
                action.setChecked(True)
            action.triggered.connect(lambda checked, k=j_key: self.setJournalExport(k))
            self.journalActionGroup.addAction(action)
            self.menuExport.addAction(action)

        self.menuExport.addSeparator()

        self.actionExport1Col = QtWidgets.QAction(
            "Groups to 1 column image", self.menuExport
        )
        self.actionExport1Col.triggered.connect(self.triggerExport1Col)
        self.menuExport.addAction(self.actionExport1Col)

        self.actionExport2Col = QtWidgets.QAction(
            "Groups to 2 column image", self.menuExport
        )
        self.actionExport2Col.triggered.connect(self.triggerExport2Col)
        self.menuExport.addAction(self.actionExport2Col)

    def syncJournalExportMenu(self):
        journal = uistate.settings.get("journal_export", "jneurosci")
        for action in self.journalActionGroup.actions():
            if action.data() == journal:
                action.setChecked(True)
                break

    def setJournalExport(self, journal_key):
        uistate.settings["journal_export"] = journal_key
        if journal_key in export_image.JOURNAL_COLOR_PALETTES:
            palette = export_image.JOURNAL_COLOR_PALETTES[journal_key]
            uistate.colors = palette[:]
            if hasattr(self, "dd_groups") and self.dd_groups:
                for gid in sorted(self.dd_groups.keys()):
                    idx = (gid - 1) % len(palette) if isinstance(gid, int) else 0
                    self.dd_groups[gid]["color"] = palette[idx]
                if hasattr(self, "group_save_dd"):
                    self.group_save_dd()
            if hasattr(uistate, "dict_group_labels") and hasattr(self, "dd_groups"):
                for info in list(uistate.dict_group_labels.values()):
                    gid = info.get("group_ID")
                    if gid is not None:
                        gid_key = int(gid) if str(gid).isdigit() else gid
                        if gid_key in self.dd_groups:
                            new_color = self.dd_groups[gid_key]["color"]
                            for k in ("line", "fill"):
                                artist = info.get(k)
                                if artist is not None:
                                    artist.set_color(new_color)
            if hasattr(self, "group_cache_purge"):
                self.group_cache_purge()
            if hasattr(self, "groupControlsRefresh"):
                self.groupControlsRefresh()
        self.syncJournalExportMenu()
        if hasattr(self, "triggerRefresh"):
            self.triggerRefresh()
        if hasattr(self, "dict_folders") and "project" in self.dict_folders:
            uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def triggerExport1Col(self, checked=False):
        journal = uistate.settings.get("journal_export", "jneurosci")
        self.triggerExportOutputImage(f"{journal}_1col")

    def triggerExport2Col(self, checked=False):
        journal = uistate.settings.get("journal_export", "jneurosci")
        self.triggerExportOutputImage(f"{journal}_2col")
