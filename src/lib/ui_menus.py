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

        # Export menu (triggers → ExportMixin in ui_export.py)
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

        self.actionExportSweepsIbw = QtWidgets.QAction("Export sweeps to .ibw")
        self.actionExportSweepsIbw.triggered.connect(self.triggerExportSweepsIbw)
        self.menuExport.addAction(self.actionExportSweepsIbw)

        self.menuExport.addSeparator()

        # — Output section —
        self.actionExportOutputCsv = QtWidgets.QAction("Export output to .csv")
        self.actionExportOutputCsv.triggered.connect(self.triggerExportOutputCsv)
        self.menuExport.addAction(self.actionExportOutputCsv)

        self.menuExport.addSeparator()

        # — Image section —
        self.actionExportOutputImage = QtWidgets.QAction("Output to image")
        self.actionExportOutputImage.triggered.connect(self.triggerExportOutputImage)
        self.menuExport.addAction(self.actionExportOutputImage)
