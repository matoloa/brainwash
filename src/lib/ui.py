import os  # TODO: replace use by pathlib?
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# pandas 3.0 changed the default string dtype to Arrow-backed string[pyarrow],
# which rejects assignment of non-string values (int, float, etc.).
# The project DataFrame mixes strings, ints and floats in the same CSV-loaded
# DataFrame, so we opt back into the legacy object-dtype string behaviour.
pd.options.future.infer_string = False
from matplotlib import use as matplotlib_use

# TODO: kick these out to ui_plot.py
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtGui, QtWidgets, sip

matplotlib_use("Qt5Agg")

import importlib  # for reloading modules
import json  # for saving and loading dicts as strings
import pickle  # for saving and loading dicts
import re  # regular expressions
import socket  # getting computer name and localdomain for df_project['host'] (not reported in talkback)
import time  # counting time for functions

# used by talkback
import uuid  # generating unique talkback ID
from datetime import datetime  # used in project name defaults

import analysis_v2 as analysis

# brainwash files
import parse

# read and write
import toml  # for reading pyproject.toml
import ui_plot
import ui_state_classes
import yaml  # used by talkback

"""
####################################################################
#                    Table of Contents                             #
####################################################################

    Globals
    Custom sub-classes
    Main class (UIsub)
        Selection changers
        WIP section TODO: move to appopriate sections
        uisub inits
        triggers
        Data editing
        Data groups
        Writers (files, dicts)
        TODO: consolidate these sections
            Project functions
            df_p handling
            df_t handling
            table handling (df_p, df_t)
            internal dataframe handling
        Graph interface
        Mouseover + click and drag functions, zooms
        pyqtSlot decorators
    get_signals
    df_projectTemplate TODO: move to uistate?
    Mainguard
"""

# debug, tell me where you think you are now
debug_mode = os.getenv("BRAINWASH_DEBUG", "0") == "1"
if debug_mode:
    print(f"ui.py: os.getcwd(): {os.getcwd()}")
    print(f"ui.py: sys.path: {sys.path}")
    try:
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        print(f"ui.py: script_path: {script_path}")
    except:
        pass

####################################################################
#                             Globals                              #
####################################################################


class Config:
    def __init__(self):
        self.dev_mode = True  # Development mode
        # self.dev_mode = False # Deploy mode
        print(
            "\n" * 3
            + f"{'Development' if self.dev_mode else 'Deploy'} mode - {time.strftime('%H:%M:%S')}"
        )

        clear = False  # Clear all caches and temporary files at launch
        self.clear_project_folder = (
            clear  # Remove current project folder (datafiles) at launch
        )
        self.clear_cache = clear
        self.clear_timepoints = clear
        self.force_cfg_reset = clear

        self.transient = False  # Block persisting of files

        self.verbose = self.dev_mode
        self.talkback = not self.dev_mode
        self.hide_experimental = not self.dev_mode
        self.track_widget_focus = False
        self.terminal_space = (
            372 if self.dev_mode else 100
        )  # pixels reserved for viewing prints

        # get project_name and version number from pyproject.toml
        pathtoml = [
            i + "/pyproject.toml"
            for i in ["../..", "..", ".", "lib", "/lib"]
            if Path(i + "/pyproject.toml").is_file()
        ]
        # you will want this eventually so I fix it now
        pathbwcfgyaml = [
            i + "/bw_cfg.yaml"
            for i in ["../..", "..", ".", "lib", "/lib"]
            if Path(i + "/bw_cfg.yaml").is_file()
        ]
        if len(pathtoml) == 0:
            # not found, we may be in an appimage
            pathtoml = [
                i + "/pyproject.toml"
                for i in sys.path
                if Path(i + "/pyproject.toml").is_file()
            ]
            pathbwcfgyaml = [
                i + "/bw_cfg.yaml"
                for i in sys.path
                if Path(i + "/bw_cfg.yaml").is_file()
            ]
        pyproject = toml.load(pathtoml[0])
        self.bw_cfg_yaml = pathbwcfgyaml[0] if len(pathbwcfgyaml) == 1 else None
        self.program_name = pyproject["project"]["name"]
        self.version = pyproject["project"]["version"]


config = Config()
uistate = ui_state_classes.UIstate()  # global variable for storing state of UI
importlib.reload(ui_plot)
uiplot = ui_plot.UIplot(uistate)


####################################################################
#                       Custom sub-classes                         #
####################################################################


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data=None):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role=None):  # dataCell
        if role is None:
            value = self._data.iloc[index.row(), index.column()]
            return value
        if role == QtCore.Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def dataRow(self, index, role=None):
        # TODO: return entire selected row
        if role is None:
            value = self._data.iloc[index.row(), :]
            return value

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return str(self._data.columns[section])

            if orientation == QtCore.Qt.Vertical:
                return str(self._data.index[section])

    def setData(self, data: pd.DataFrame = None):
        self.beginResetModel()
        if data is None:
            self._data = pd.DataFrame()
        elif isinstance(data, pd.DataFrame):
            self._data = data
        else:
            return False
        self.endResetModel()
        return True

    def sort(self, column, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self._data = self._data.sort_values(
                self._data.columns[column], ascending=order == QtCore.Qt.AscendingOrder
            )
            self.layoutChanged.emit()
        except Exception as e:
            print(f"Error sorting table: {e}")


class FileTreeSelectorModel(
    QtWidgets.QFileSystemModel
):  # Paired with a FileTreeSelectorView
    paths_selected = QtCore.pyqtSignal(list)

    def __init__(self, parent=None, root_path="."):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.root_path = root_path
        self.checks = {}
        self.nodestack = []
        self.parent_index = self.setRootPath(self.root_path)
        self.root_index = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot)
        self.sort(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.directoryLoaded.connect(self._loaded)

    def _loaded(self, path):
        if config.verbose:
            print("_loaded", self.root_path, self.rowCount(self.parent_index))

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.CheckStateRole:
            return QtWidgets.QFileSystemModel.data(self, index, role)
        else:
            if index.column() == 0:
                return self.checkState(index)

    def flags(self, index):
        return (
            QtWidgets.QFileSystemModel.flags(self, index)
            | QtCore.Qt.ItemIsUserCheckable
        )

    def checkState(self, index):
        if index in self.checks:
            return self.checks[index]
        else:
            return QtCore.Qt.Unchecked

    def getCheckedPaths(self):
        paths = []
        for k, v in self.checks.items():
            if v == 2:  # Checked
                paths.append(format(self.filePath(k)))
        self.paths_selected.emit(paths)

    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            self.checks[index] = value
            if config.verbose:
                print("setData(): {}".format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def traverseDirectory(self, parentindex, callback=None):
        if self.verbose:
            print("traverseDirectory():")
        callback(parentindex)
        if self.hasChildren(parentindex):
            path = self.filePath(parentindex)
            it = QtCore.QDirIterator(path, self.filter() | QtCore.QDir.NoDotAndDotDot)
            while it.hasNext():
                childIndex = self.index(it.next())
                self.traverseDirectory(childIndex, callback=callback)
        else:
            print("no children")

    def printIndex(self, index):
        print("model printIndex(): {}".format(self.filePath(index)))


class FileTreeSelectorDialog(QtWidgets.QWidget):
    def __init__(self, parent=None, root_path="."):
        super().__init__(parent)

    def delayedInitForRootPath(self, root_path):
        self.root_path = str(root_path)

        # Model
        self.model = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # view
        self.view = QtWidgets.QTreeView()

        self.view.setObjectName("treeView_fileTreeSelector")
        self.view.setWindowTitle("Dir View")  # TODO:  Which title?
        self.view.setSortingEnabled(False)

        # Attach Model to View
        self.view.setModel(self.model)
        self.view.setRootIndex(self.model.parent_index)
        self.view.setAnimated(False)
        self.view.setIndentation(20)
        self.view.setColumnWidth(0, 250)
        self.view.setColumnWidth(1, 100)
        self.view.setColumnWidth(2, 50)
        self.view.setColumnHidden(3, True)

        # Misc
        self.node_stack = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(self.view)
        self.setLayout(windowlayout)

        # QtCore.QMetaObject.connectSlotsByName(self)

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_treeView_fileTreeSelector_clicked(self, index):
        self.model.getCheckedPaths()


class MplCanvas(FigureCanvasQTAgg):
    # graph window, setting parent to None to make it standalone
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        self.setParent(parent)


class CustomCheckBox(QtWidgets.QCheckBox):
    # Custom checkbox to allow right-click to rename group
    rightClicked = QtCore.pyqtSignal(int)  # Define a new signal that carries an integer

    def __init__(self, group_ID, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_ID = group_ID  # int 1-9

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit(self.group_ID)
        else:
            super().mousePressEvent(event)


class ProgressBarManager:
    def __init__(self, progressBar, total):
        self.progressBar = progressBar
        self.total = total
        print(f"*** Progressbar start: {self.progressBar.value()}")
        print(f"*** Progressbar total: {total}")

    def __enter__(self):
        self.progressBar.setValue(0)
        self.progressBar.setFormat("")
        self.progressBar.setVisible(True)
        return self

    def __exit__(self, type, value, traceback):
        self.total = 0
        self.progressBar.setFormat("")
        self.progressBar.setVisible(False)

    def update(self, i, task_description):
        if self.total == 0:
            print(
                "*** ERROR: Update request for non-existent task."
            )  # TODO: This scenario should have been prevented by the callers - why isn't it? Related to __exit__ setting it to 0?
            return
        percentage = int((i) * 100 / self.total)
        self.progressBar.setValue(percentage)
        self.progressBar.setFormat(
            f"{task_description} {i + 1} / {self.total}:   %p% complete"
        )


class ParseDataThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal()  # custom signal, decoupled from QThread.finished

    def __init__(self, df_p_to_update, dict_folders):
        super().__init__()
        self.df_p_to_update = df_p_to_update
        self.dict_folders = dict_folders
        self.rows = []
        self.total = len(df_p_to_update)

    def run(self):
        """Parse data from files, persist them as bw parquet:s, and update df_p"""
        try:
            for i, (_, df_proj_row) in enumerate(self.df_p_to_update.iterrows()):
                recording_name = df_proj_row["recording_name"]
                source_path = df_proj_row["path"]
                self.progress.emit(i)
                dict_dfs_raw = parse.source2dfs(source=source_path)
                if not dict_dfs_raw:
                    print(f"Failed to read source file at: {source_path}")
                    continue
                # convert dict - channel:df to recording_name:df
                dict_name_df = {
                    (
                        recording_name
                        if len(dict_dfs_raw) == 1
                        else f"{recording_name}_ch{channel}"
                    ): df
                    for channel, df in dict_dfs_raw.items()
                }
                for rec, df_raw in dict_name_df.items():
                    if config.verbose:
                        print(f"ParseDataThread: {rec}")
                    df_proj_new_row = uisub.create_recording(df_proj_row, rec, df_raw)
                    self.rows.append(df_proj_new_row)
        except Exception as e:
            import traceback

            print(f"ParseDataThread.run: EXCEPTION: {e}")
            print(traceback.format_exc())
        finally:
            self.finished.emit()


class graphPreloadThread(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int)

    def __init__(self, uistate, uiplot, uisub):
        super().__init__()
        self.rows = []
        self.uistate = uistate
        self.uiplot = uiplot
        self.uisub = uisub
        self.df_p = self.uisub.get_df_project()
        self.i = 0

    def run(self):
        print(
            f"graphPreloadThread.run: entered, {len(self.uistate.list_idx_recs2preload)} recordings"
        )
        df_p = self.df_p.loc[self.uistate.list_idx_recs2preload]
        self.uistate.list_idx_recs2preload = []
        self.i = 0
        for i, p_row in df_p.iterrows():
            print(f"graphPreloadThread.run: processing {p_row['recording_name']}")
            print(f"graphPreloadThread.run: calling get_dft")
            dft = self.uisub.get_dft(row=p_row)
            print(f"graphPreloadThread.run: get_dft returned {type(dft)}")
            print(f"graphPreloadThread.run: calling get_dfmean")
            dfmean = self.uisub.get_dfmean(row=p_row)
            print(f"graphPreloadThread.run: calling get_dffilter")
            _ = self.uisub.get_dffilter(row=p_row)
            print(f"graphPreloadThread.run: calling get_dfoutput")
            if self.uistate.checkBox["paired_stims"]:
                dfoutput = self.uisub.get_dfdiff(row=p_row)
            else:
                dfoutput = self.uisub.get_dfoutput(row=p_row)
            print(f"graphPreloadThread.run: get_dfoutput returned {type(dfoutput)}")
            if dfoutput is None:
                print(
                    "graphPreloadThread.run: dfoutput is None, returning early (finished will NOT emit)"
                )
                return
            print(
                f"graphPreloadThread, {p_row['recording_name']} calls uiplot.addRow() dfoutput columns: {dfoutput.columns}"
            )
            self.uiplot.addRow(
                p_row=p_row.to_dict(), dft=dft, dfmean=dfmean, dfoutput=dfoutput
            )
            self.progress.emit(i)
            self.i += 1
            print(f"Preloaded {p_row['recording_name']}")
        self.finished.emit()


#####################################################################
# section directly copied from pyuic output - do not alter!         #
# NB: 'object' must be 'QtCore.QObject' for pyqtSlot(list) to work  #
#####################################################################


class Ui_MainWindow(QtCore.QObject):
    def _cleanup_threads(self):
        # Stop and wait for all running threads
        for thread in getattr(self, "_threads", []):
            if isinstance(thread, QtCore.QThread) and thread.isRunning():
                thread.quit()
                thread.wait()
        self._threads = []

    def closeEvent(self, event):
        # Ensure all threads are stopped on window close
        self._cleanup_threads()
        super().closeEvent(event)

    def setupUi(self, mainWindow):
        mainWindow.setObjectName("mainWindow")
        mainWindow.resize(1270, 1050)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName(
            "horizontalLayoutCentralwidget"
        )
        self.verticalMasterLayout = QtWidgets.QVBoxLayout()
        self.verticalMasterLayout.setObjectName("verticalMasterLayout")
        self.h_splitterMaster = QtWidgets.QSplitter(self.centralwidget)
        self.h_splitterMaster.setOrientation(QtCore.Qt.Horizontal)
        self.h_splitterMaster.setObjectName("h_splitterMaster")
        self.layoutWidget = QtWidgets.QWidget(self.h_splitterMaster)
        self.layoutWidget.setObjectName("layoutWidget")
        self.verticalLayoutProj = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.verticalLayoutProj.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.verticalLayoutProj.setContentsMargins(0, 0, 0, 0)
        self.verticalLayoutProj.setObjectName("verticalLayoutProj")
        self.horizontalLayoutProjParse = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProjParse.setObjectName("horizontalLayoutProjParse")
        self.pushButtonParse = QtWidgets.QPushButton(self.layoutWidget)
        self.pushButtonParse.setObjectName("pushButtonParse")
        self.horizontalLayoutProjParse.addWidget(self.pushButtonParse)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutProjParse)
        self.horizontalLayoutProjStim = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProjStim.setObjectName("horizontalLayoutProjStim")
        self.checkBox_force1stim = QtWidgets.QCheckBox(self.layoutWidget)
        self.checkBox_force1stim.setObjectName("checkBox_force1stim")
        self.horizontalLayoutProjStim.addWidget(self.checkBox_force1stim)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutProjStim)
        self.verticalLayoutWidget = QtWidgets.QWidget(self.h_splitterMaster)
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayoutStim = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayoutStim.setContentsMargins(0, 0, 0, 0)
        self.verticalLayoutStim.setObjectName("verticalLayoutStim")
        self.tableStim = QtWidgets.QTableView(self.verticalLayoutWidget)
        self.tableStim.setEnabled(True)
        self.tableStim.setMinimumSize(QtCore.QSize(50, 0))
        self.tableStim.setObjectName("tableStim")
        self.verticalLayoutStim.addWidget(self.tableStim)
        self.verticalLayoutWidget_2 = QtWidgets.QWidget(self.h_splitterMaster)
        self.verticalLayoutWidget_2.setObjectName("verticalLayoutWidget_2")
        self.verticalLayoutGraphs = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_2)
        self.verticalLayoutGraphs.setContentsMargins(0, 0, 0, 0)
        self.verticalLayoutGraphs.setObjectName("verticalLayoutGraphs")
        self.v_splitterGraphs = QtWidgets.QSplitter(self.verticalLayoutWidget_2)
        self.v_splitterGraphs.setOrientation(QtCore.Qt.Vertical)
        self.v_splitterGraphs.setObjectName("v_splitterGraphs")
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.v_splitterGraphs)
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayoutMean = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayoutMean.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayoutMean.setObjectName("horizontalLayoutMean")
        self.graphMean = QtWidgets.QWidget(self.horizontalLayoutWidget)
        self.graphMean.setMinimumSize(QtCore.QSize(100, 100))
        self.graphMean.setObjectName("graphMean")
        self.horizontalLayoutMean.addWidget(self.graphMean)
        self.horizontalLayoutWidget_2 = QtWidgets.QWidget(self.v_splitterGraphs)
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayoutEvent = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_2
        )
        self.horizontalLayoutEvent.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayoutEvent.setObjectName("horizontalLayoutEvent")
        self.graphEvent = QtWidgets.QWidget(self.horizontalLayoutWidget_2)
        self.graphEvent.setMinimumSize(QtCore.QSize(100, 100))
        self.graphEvent.setObjectName("graphEvent")
        self.horizontalLayoutEvent.addWidget(self.graphEvent)
        self.horizontalLayoutWidget_3 = QtWidgets.QWidget(self.v_splitterGraphs)
        self.horizontalLayoutWidget_3.setObjectName("horizontalLayoutWidget_3")
        self.horizontalLayoutOutput = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_3
        )
        self.horizontalLayoutOutput.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayoutOutput.setObjectName("horizontalLayoutOutput")
        self.graphOutput = QtWidgets.QWidget(self.horizontalLayoutWidget_3)
        self.graphOutput.setMinimumSize(QtCore.QSize(100, 100))
        self.graphOutput.setObjectName("graphOutput")
        self.horizontalLayoutOutput.addWidget(self.graphOutput)
        self.verticalLayoutGraphs.addWidget(self.v_splitterGraphs)
        self.verticalLayoutWidget_3 = QtWidgets.QWidget(self.h_splitterMaster)
        self.verticalLayoutWidget_3.setObjectName("verticalLayoutWidget_3")
        self.verticalLayoutTools = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_3)
        self.verticalLayoutTools.setContentsMargins(0, 0, 0, 0)
        self.verticalLayoutTools.setObjectName("verticalLayoutTools")
        self.frameToolStim = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolStim.sizePolicy().hasHeightForWidth()
        )
        self.frameToolStim.setSizePolicy(sizePolicy)
        self.frameToolStim.setMinimumSize(QtCore.QSize(211, 201))
        self.frameToolStim.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolStim.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolStim.setObjectName("frameToolStim")
        self.checkBox_show_all_events = QtWidgets.QCheckBox(self.frameToolStim)
        self.checkBox_show_all_events.setGeometry(QtCore.QRect(10, 30, 151, 23))
        self.checkBox_show_all_events.setObjectName("checkBox_show_all_events")
        self.checkBox_timepoints_per_stim = QtWidgets.QCheckBox(self.frameToolStim)
        self.checkBox_timepoints_per_stim.setGeometry(QtCore.QRect(10, 50, 161, 23))
        self.checkBox_timepoints_per_stim.setObjectName("checkBox_timepoints_per_stim")
        self.label_stims = QtWidgets.QLabel(self.frameToolStim)
        self.label_stims.setGeometry(QtCore.QRect(10, 10, 62, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_stims.setFont(font)
        self.label_stims.setObjectName("label_stims")
        self.pushButton_stim_assign_threshold = QtWidgets.QPushButton(
            self.frameToolStim
        )
        self.pushButton_stim_assign_threshold.setGeometry(QtCore.QRect(20, 170, 61, 25))
        self.pushButton_stim_assign_threshold.setObjectName(
            "pushButton_stim_assign_threshold"
        )
        self.label_stim_detection_threshold = QtWidgets.QLabel(self.frameToolStim)
        self.label_stim_detection_threshold.setGeometry(QtCore.QRect(10, 150, 141, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(False)
        font.setWeight(50)
        self.label_stim_detection_threshold.setFont(font)
        self.label_stim_detection_threshold.setObjectName(
            "label_stim_detection_threshold"
        )
        self.label_mean_to = QtWidgets.QLabel(self.frameToolStim)
        self.label_mean_to.setGeometry(QtCore.QRect(90, 120, 21, 20))
        self.label_mean_to.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_mean_to.setObjectName("label_mean_to")
        self.lineEdit_mean_selection_end = QtWidgets.QLineEdit(self.frameToolStim)
        self.lineEdit_mean_selection_end.setGeometry(QtCore.QRect(100, 120, 61, 25))
        self.lineEdit_mean_selection_end.setObjectName("lineEdit_mean_selection_end")
        self.label_mean_selected_range = QtWidgets.QLabel(self.frameToolStim)
        self.label_mean_selected_range.setGeometry(QtCore.QRect(10, 100, 71, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(False)
        font.setWeight(50)
        self.label_mean_selected_range.setFont(font)
        self.label_mean_selected_range.setObjectName("label_mean_selected_range")
        self.lineEdit_mean_selection_start = QtWidgets.QLineEdit(self.frameToolStim)
        self.lineEdit_mean_selection_start.setGeometry(QtCore.QRect(20, 120, 61, 25))
        self.lineEdit_mean_selection_start.setObjectName(
            "lineEdit_mean_selection_start"
        )
        self.pushButton_stim_detect = QtWidgets.QPushButton(self.frameToolStim)
        self.pushButton_stim_detect.setGeometry(QtCore.QRect(90, 170, 61, 25))
        self.pushButton_stim_detect.setObjectName("pushButton_stim_detect")
        self.checkBox_output_per_stim = QtWidgets.QCheckBox(self.frameToolStim)
        self.checkBox_output_per_stim.setGeometry(QtCore.QRect(10, 70, 161, 23))
        self.checkBox_output_per_stim.setObjectName("checkBox_output_per_stim")
        self.checkBox_show_all_events.raise_()
        self.checkBox_timepoints_per_stim.raise_()
        self.label_stims.raise_()
        self.pushButton_stim_assign_threshold.raise_()
        self.label_stim_detection_threshold.raise_()
        self.label_mean_to.raise_()
        self.label_mean_selected_range.raise_()
        self.pushButton_stim_detect.raise_()
        self.checkBox_output_per_stim.raise_()
        self.lineEdit_mean_selection_start.raise_()
        self.lineEdit_mean_selection_end.raise_()
        self.verticalLayoutTools.addWidget(self.frameToolStim, 0, QtCore.Qt.AlignTop)
        self.frameToolSweeps = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolSweeps.sizePolicy().hasHeightForWidth()
        )
        self.frameToolSweeps.setSizePolicy(sizePolicy)
        self.frameToolSweeps.setMinimumSize(QtCore.QSize(211, 111))
        self.frameToolSweeps.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolSweeps.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolSweeps.setObjectName("frameToolSweeps")
        self.pushButton_sweeps_even = QtWidgets.QPushButton(self.frameToolSweeps)
        self.pushButton_sweeps_even.setGeometry(QtCore.QRect(60, 70, 41, 25))
        self.pushButton_sweeps_even.setObjectName("pushButton_sweeps_even")
        self.label_sweeps = QtWidgets.QLabel(self.frameToolSweeps)
        self.label_sweeps.setGeometry(QtCore.QRect(10, 10, 151, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_sweeps.setFont(font)
        self.label_sweeps.setObjectName("label_sweeps")
        self.pushButton_sweeps_odd = QtWidgets.QPushButton(self.frameToolSweeps)
        self.pushButton_sweeps_odd.setGeometry(QtCore.QRect(120, 70, 41, 25))
        self.pushButton_sweeps_odd.setObjectName("pushButton_sweeps_odd")
        self.lineEdit_sweeps_range_to = QtWidgets.QLineEdit(self.frameToolSweeps)
        self.lineEdit_sweeps_range_to.setGeometry(QtCore.QRect(120, 30, 41, 25))
        self.lineEdit_sweeps_range_to.setObjectName("lineEdit_sweeps_range_to")
        self.label_sweeps_dash = QtWidgets.QLabel(self.frameToolSweeps)
        self.label_sweeps_dash.setGeometry(QtCore.QRect(110, 30, 16, 20))
        self.label_sweeps_dash.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_sweeps_dash.setObjectName("label_sweeps_dash")
        self.label_sweeps_selection = QtWidgets.QLabel(self.frameToolSweeps)
        self.label_sweeps_selection.setGeometry(QtCore.QRect(10, 30, 41, 20))
        self.label_sweeps_selection.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_sweeps_selection.setObjectName("label_sweeps_selection")
        self.lineEdit_sweeps_range_from = QtWidgets.QLineEdit(self.frameToolSweeps)
        self.lineEdit_sweeps_range_from.setGeometry(QtCore.QRect(60, 30, 41, 25))
        self.lineEdit_sweeps_range_from.setObjectName("lineEdit_sweeps_range_from")
        self.label_sweeps_select_even_odd = QtWidgets.QLabel(self.frameToolSweeps)
        self.label_sweeps_select_even_odd.setGeometry(QtCore.QRect(10, 70, 41, 20))
        self.label_sweeps_select_even_odd.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_sweeps_select_even_odd.setObjectName("label_sweeps_select_even_odd")
        self.label_sweeps_dash.raise_()
        self.pushButton_sweeps_even.raise_()
        self.label_sweeps.raise_()
        self.pushButton_sweeps_odd.raise_()
        self.lineEdit_sweeps_range_to.raise_()
        self.label_sweeps_selection.raise_()
        self.lineEdit_sweeps_range_from.raise_()
        self.label_sweeps_select_even_odd.raise_()
        self.verticalLayoutTools.addWidget(self.frameToolSweeps, 0, QtCore.Qt.AlignTop)
        self.frameToolBin = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frameToolBin.sizePolicy().hasHeightForWidth())
        self.frameToolBin.setSizePolicy(sizePolicy)
        self.frameToolBin.setMinimumSize(QtCore.QSize(211, 111))
        self.frameToolBin.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolBin.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolBin.setObjectName("frameToolBin")
        self.checkBox_bin = QtWidgets.QCheckBox(self.frameToolBin)
        self.checkBox_bin.setGeometry(QtCore.QRect(10, 30, 151, 23))
        self.checkBox_bin.setObjectName("checkBox_bin")
        self.label_bins = QtWidgets.QLabel(self.frameToolBin)
        self.label_bins.setGeometry(QtCore.QRect(10, 10, 62, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_bins.setFont(font)
        self.label_bins.setObjectName("label_bins")
        self.pushButton_bin_size_set_all = QtWidgets.QPushButton(self.frameToolBin)
        self.pushButton_bin_size_set_all.setGeometry(QtCore.QRect(90, 80, 51, 25))
        self.pushButton_bin_size_set_all.setObjectName("pushButton_bin_size_set_all")
        self.label_bin_size = QtWidgets.QLabel(self.frameToolBin)
        self.label_bin_size.setGeometry(QtCore.QRect(10, 60, 71, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(False)
        font.setWeight(50)
        self.label_bin_size.setFont(font)
        self.label_bin_size.setObjectName("label_bin_size")
        self.lineEdit_bin_size = QtWidgets.QLineEdit(self.frameToolBin)
        self.lineEdit_bin_size.setGeometry(QtCore.QRect(20, 80, 61, 25))
        self.lineEdit_bin_size.setObjectName("lineEdit_bin_size")
        self.verticalLayoutTools.addWidget(self.frameToolBin, 0, QtCore.Qt.AlignTop)
        self.frameToolAspect = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolAspect.sizePolicy().hasHeightForWidth()
        )
        self.frameToolAspect.setSizePolicy(sizePolicy)
        self.frameToolAspect.setMinimumSize(QtCore.QSize(211, 171))
        self.frameToolAspect.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolAspect.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolAspect.setObjectName("frameToolAspect")
        self.checkBox_EPSP_slope = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_EPSP_slope.setGeometry(QtCore.QRect(10, 30, 101, 23))
        self.checkBox_EPSP_slope.setObjectName("checkBox_EPSP_slope")
        self.checkBox_volley_slope = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_volley_slope.setGeometry(QtCore.QRect(10, 70, 101, 23))
        self.checkBox_volley_slope.setObjectName("checkBox_volley_slope")
        self.checkBox_EPSP_amp = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_EPSP_amp.setGeometry(QtCore.QRect(10, 50, 101, 23))
        self.checkBox_EPSP_amp.setObjectName("checkBox_EPSP_amp")
        self.label_aspect = QtWidgets.QLabel(self.frameToolAspect)
        self.label_aspect.setGeometry(QtCore.QRect(10, 10, 62, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_aspect.setFont(font)
        self.label_aspect.setObjectName("label_aspect")
        self.checkBox_volley_amp = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_volley_amp.setGeometry(QtCore.QRect(10, 90, 101, 23))
        self.checkBox_volley_amp.setObjectName("checkBox_volley_amp")
        self.lineEdit_EPSP_amp_halfwidth = QtWidgets.QLineEdit(self.frameToolAspect)
        self.lineEdit_EPSP_amp_halfwidth.setGeometry(QtCore.QRect(60, 140, 31, 25))
        self.lineEdit_EPSP_amp_halfwidth.setObjectName("lineEdit_EPSP_amp_halfwidth")
        self.lineEdit_volley_amp_halfwidth = QtWidgets.QLineEdit(self.frameToolAspect)
        self.lineEdit_volley_amp_halfwidth.setGeometry(QtCore.QRect(140, 140, 31, 25))
        self.lineEdit_volley_amp_halfwidth.setObjectName(
            "lineEdit_volley_amp_halfwidth"
        )
        self.label_header_amp_halfwidth = QtWidgets.QLabel(self.frameToolAspect)
        self.label_header_amp_halfwidth.setGeometry(QtCore.QRect(10, 120, 201, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_header_amp_halfwidth.setFont(font)
        self.label_header_amp_halfwidth.setObjectName("label_header_amp_halfwidth")
        self.label_EPSP_amp_halfwidth = QtWidgets.QLabel(self.frameToolAspect)
        self.label_EPSP_amp_halfwidth.setGeometry(QtCore.QRect(20, 140, 51, 20))
        self.label_EPSP_amp_halfwidth.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_EPSP_amp_halfwidth.setObjectName("label_EPSP_amp_halfwidth")
        self.label_volley_amp_halfwidth = QtWidgets.QLabel(self.frameToolAspect)
        self.label_volley_amp_halfwidth.setGeometry(QtCore.QRect(100, 140, 51, 20))
        self.label_volley_amp_halfwidth.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_volley_amp_halfwidth.setObjectName("label_volley_amp_halfwidth")
        self.pushButton_EPSP_amp_width_set_all = QtWidgets.QPushButton(
            self.frameToolAspect
        )
        self.pushButton_EPSP_amp_width_set_all.setGeometry(
            QtCore.QRect(40, 170, 51, 25)
        )
        self.pushButton_EPSP_amp_width_set_all.setObjectName(
            "pushButton_EPSP_amp_width_set_all"
        )
        self.pushButton_volley_amp_width_set_all = QtWidgets.QPushButton(
            self.frameToolAspect
        )
        self.pushButton_volley_amp_width_set_all.setGeometry(
            QtCore.QRect(130, 170, 51, 25)
        )
        self.pushButton_volley_amp_width_set_all.setObjectName(
            "pushButton_volley_amp_width_set_all"
        )
        self.checkBox_volley_slope_mean = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_volley_slope_mean.setGeometry(QtCore.QRect(120, 70, 101, 23))
        self.checkBox_volley_slope_mean.setObjectName("checkBox_volley_slope_mean")
        self.checkBox_volley_amp_mean = QtWidgets.QCheckBox(self.frameToolAspect)
        self.checkBox_volley_amp_mean.setGeometry(QtCore.QRect(120, 90, 61, 23))
        self.checkBox_volley_amp_mean.setObjectName("checkBox_volley_amp_mean")
        self.checkBox_EPSP_slope.raise_()
        self.checkBox_volley_slope.raise_()
        self.checkBox_EPSP_amp.raise_()
        self.label_aspect.raise_()
        self.checkBox_volley_amp.raise_()
        self.label_header_amp_halfwidth.raise_()
        self.label_EPSP_amp_halfwidth.raise_()
        self.label_volley_amp_halfwidth.raise_()
        self.lineEdit_EPSP_amp_halfwidth.raise_()
        self.lineEdit_volley_amp_halfwidth.raise_()
        self.pushButton_EPSP_amp_width_set_all.raise_()
        self.pushButton_volley_amp_width_set_all.raise_()
        self.checkBox_volley_slope_mean.raise_()
        self.checkBox_volley_amp_mean.raise_()
        self.verticalLayoutTools.addWidget(self.frameToolAspect, 0, QtCore.Qt.AlignTop)
        self.frameToolScaling = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolScaling.sizePolicy().hasHeightForWidth()
        )
        self.frameToolScaling.setSizePolicy(sizePolicy)
        self.frameToolScaling.setMinimumSize(QtCore.QSize(211, 131))
        self.frameToolScaling.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolScaling.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolScaling.setObjectName("frameToolScaling")
        self.lineEdit_norm_EPSP_end = QtWidgets.QLineEdit(self.frameToolScaling)
        self.lineEdit_norm_EPSP_end.setGeometry(QtCore.QRect(80, 70, 41, 25))
        self.lineEdit_norm_EPSP_end.setObjectName("lineEdit_norm_EPSP_end")
        self.label_norm_on_sweep = QtWidgets.QLabel(self.frameToolScaling)
        self.label_norm_on_sweep.setGeometry(QtCore.QRect(10, 50, 131, 20))
        self.label_norm_on_sweep.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_norm_on_sweep.setObjectName("label_norm_on_sweep")
        self.checkBox_norm_EPSP = QtWidgets.QCheckBox(self.frameToolScaling)
        self.checkBox_norm_EPSP.setGeometry(QtCore.QRect(10, 30, 111, 23))
        self.checkBox_norm_EPSP.setObjectName("checkBox_norm_EPSP")
        self.label_relative_to = QtWidgets.QLabel(self.frameToolScaling)
        self.label_relative_to.setGeometry(QtCore.QRect(70, 70, 21, 20))
        self.label_relative_to.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft
        )
        self.label_relative_to.setObjectName("label_relative_to")
        self.label_scaling = QtWidgets.QLabel(self.frameToolScaling)
        self.label_scaling.setGeometry(QtCore.QRect(10, 10, 81, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_scaling.setFont(font)
        self.label_scaling.setObjectName("label_scaling")
        self.lineEdit_norm_EPSP_start = QtWidgets.QLineEdit(self.frameToolScaling)
        self.lineEdit_norm_EPSP_start.setGeometry(QtCore.QRect(20, 70, 41, 25))
        self.lineEdit_norm_EPSP_start.setObjectName("lineEdit_norm_EPSP_start")
        self.checkBox_output_ymin0 = QtWidgets.QCheckBox(self.frameToolScaling)
        self.checkBox_output_ymin0.setGeometry(QtCore.QRect(10, 100, 111, 23))
        self.checkBox_output_ymin0.setObjectName("checkBox_output_ymin0")
        self.pushButton_norm_range_set_all = QtWidgets.QPushButton(
            self.frameToolScaling
        )
        self.pushButton_norm_range_set_all.setGeometry(QtCore.QRect(130, 70, 51, 25))
        self.pushButton_norm_range_set_all.setObjectName(
            "pushButton_norm_range_set_all"
        )
        self.label_norm_on_sweep.raise_()
        self.checkBox_norm_EPSP.raise_()
        self.label_relative_to.raise_()
        self.label_scaling.raise_()
        self.checkBox_output_ymin0.raise_()
        self.lineEdit_norm_EPSP_end.raise_()
        self.lineEdit_norm_EPSP_start.raise_()
        self.pushButton_norm_range_set_all.raise_()
        self.verticalLayoutTools.addWidget(self.frameToolScaling, 0, QtCore.Qt.AlignTop)
        self.verticalLayoutGroups = QtWidgets.QVBoxLayout()
        self.verticalLayoutGroups.setObjectName("verticalLayoutGroups")
        self.verticalLayoutTools.addLayout(self.verticalLayoutGroups)
        self.frameToolPairedStim = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolPairedStim.sizePolicy().hasHeightForWidth()
        )
        self.frameToolPairedStim.setSizePolicy(sizePolicy)
        self.frameToolPairedStim.setMinimumSize(QtCore.QSize(211, 71))
        self.frameToolPairedStim.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolPairedStim.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolPairedStim.setObjectName("frameToolPairedStim")
        self.pushButton_paired_data_flip = QtWidgets.QPushButton(
            self.frameToolPairedStim
        )
        self.pushButton_paired_data_flip.setGeometry(QtCore.QRect(100, 30, 51, 25))
        self.pushButton_paired_data_flip.setObjectName("pushButton_paired_data_flip")
        self.label_paired_data = QtWidgets.QLabel(self.frameToolPairedStim)
        self.label_paired_data.setGeometry(QtCore.QRect(8, 10, 91, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_paired_data.setFont(font)
        self.label_paired_data.setObjectName("label_paired_data")
        self.checkBox_paired_stims = QtWidgets.QCheckBox(self.frameToolPairedStim)
        self.checkBox_paired_stims.setGeometry(QtCore.QRect(8, 30, 90, 23))
        self.checkBox_paired_stims.setObjectName("checkBox_paired_stims")
        self.verticalLayoutTools.addWidget(
            self.frameToolPairedStim, 0, QtCore.Qt.AlignTop
        )
        self.frameToolExport = QtWidgets.QFrame(self.verticalLayoutWidget_3)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.frameToolExport.sizePolicy().hasHeightForWidth()
        )
        self.frameToolExport.setSizePolicy(sizePolicy)
        self.frameToolExport.setMinimumSize(QtCore.QSize(211, 71))
        self.frameToolExport.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameToolExport.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameToolExport.setObjectName("frameToolExport")
        self.pushButton_export_selection = QtWidgets.QPushButton(self.frameToolExport)
        self.pushButton_export_selection.setGeometry(QtCore.QRect(10, 30, 81, 25))
        self.pushButton_export_selection.setObjectName("pushButton_export_selection")
        self.label_export = QtWidgets.QLabel(self.frameToolExport)
        self.label_export.setGeometry(QtCore.QRect(10, 10, 81, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_export.setFont(font)
        self.label_export.setObjectName("label_export")
        self.pushButton_export_groups = QtWidgets.QPushButton(self.frameToolExport)
        self.pushButton_export_groups.setGeometry(QtCore.QRect(100, 30, 81, 25))
        self.pushButton_export_groups.setObjectName("pushButton_export_groups")
        self.verticalLayoutTools.addWidget(self.frameToolExport, 0, QtCore.Qt.AlignTop)
        spacerItem = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.verticalLayoutTools.addItem(spacerItem)
        self.verticalMasterLayout.addWidget(self.h_splitterMaster)
        self.progressBar = QtWidgets.QProgressBar(self.centralwidget)
        self.progressBar.setProperty("value", 24)
        self.progressBar.setObjectName("progressBar")
        self.verticalMasterLayout.addWidget(self.progressBar)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalMasterLayout)
        mainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(mainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1270, 22))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuData = QtWidgets.QMenu(self.menubar)
        self.menuData.setObjectName("menuData")
        self.menuGroups = QtWidgets.QMenu(self.menubar)
        self.menuGroups.setObjectName("menuGroups")
        self.menuEdit = QtWidgets.QMenu(self.menubar)
        self.menuEdit.setObjectName("menuEdit")
        self.menuView = QtWidgets.QMenu(self.menubar)
        self.menuView.setObjectName("menuView")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuData.menuAction())
        self.menubar.addAction(self.menuGroups.menuAction())

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)

    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash"))
        self.pushButtonParse.setText(_translate("mainWindow", "Import"))
        self.checkBox_force1stim.setText(_translate("mainWindow", "Single stim"))
        self.checkBox_show_all_events.setText(
            _translate("mainWindow", "Show all events")
        )
        self.checkBox_timepoints_per_stim.setText(
            _translate("mainWindow", "Timepoints per stim")
        )
        self.label_stims.setText(_translate("mainWindow", "Stims"))
        self.pushButton_stim_assign_threshold.setText(
            _translate("mainWindow", "Assign")
        )
        self.label_stim_detection_threshold.setText(
            _translate("mainWindow", "Detection Threshold")
        )
        self.label_mean_to.setText(_translate("mainWindow", "-"))
        self.label_mean_selected_range.setText(_translate("mainWindow", "Selection"))
        self.pushButton_stim_detect.setText(_translate("mainWindow", "Detect"))
        self.checkBox_output_per_stim.setText(
            _translate("mainWindow", "Output per stim")
        )
        self.pushButton_sweeps_even.setText(_translate("mainWindow", "Even"))
        self.label_sweeps.setText(_translate("mainWindow", "Select sweeps"))
        self.pushButton_sweeps_odd.setText(_translate("mainWindow", "Odd"))
        self.label_sweeps_dash.setText(_translate("mainWindow", "-"))
        self.label_sweeps_selection.setText(_translate("mainWindow", "Range"))
        self.label_sweeps_select_even_odd.setText(_translate("mainWindow", "Select"))
        self.checkBox_bin.setText(_translate("mainWindow", "Bin sweeps"))
        self.label_bins.setText(_translate("mainWindow", "Bins"))
        self.pushButton_bin_size_set_all.setText(_translate("mainWindow", "Set All"))
        self.label_bin_size.setText(_translate("mainWindow", "Bin size"))
        self.checkBox_EPSP_slope.setText(_translate("mainWindow", "EPSP slope"))
        self.checkBox_volley_slope.setText(_translate("mainWindow", "volley slope"))
        self.checkBox_EPSP_amp.setText(_translate("mainWindow", "EPSP amp."))
        self.label_aspect.setText(_translate("mainWindow", "Aspect"))
        self.checkBox_volley_amp.setText(_translate("mainWindow", "volley amp."))
        self.label_header_amp_halfwidth.setText(
            _translate("mainWindow", "Amplitude width (as ± ms)")
        )
        self.label_EPSP_amp_halfwidth.setText(_translate("mainWindow", "EPSP"))
        self.label_volley_amp_halfwidth.setText(_translate("mainWindow", "volley"))
        self.pushButton_EPSP_amp_width_set_all.setText(
            _translate("mainWindow", "Set All")
        )
        self.pushButton_volley_amp_width_set_all.setText(
            _translate("mainWindow", "Set All")
        )
        self.checkBox_volley_slope_mean.setText(_translate("mainWindow", "mean"))
        self.checkBox_volley_amp_mean.setText(_translate("mainWindow", "mean"))
        self.label_norm_on_sweep.setText(_translate("mainWindow", "Norm on sweep(s)"))
        self.checkBox_norm_EPSP.setText(_translate("mainWindow", "Relative"))
        self.label_relative_to.setText(_translate("mainWindow", "-"))
        self.label_scaling.setText(_translate("mainWindow", "Scaling"))
        self.checkBox_output_ymin0.setText(_translate("mainWindow", "output Ymin 0"))
        self.pushButton_norm_range_set_all.setText(_translate("mainWindow", "Set All"))
        self.pushButton_paired_data_flip.setText(_translate("mainWindow", "Flip C/I"))
        self.label_paired_data.setText(_translate("mainWindow", "Paired data"))
        self.checkBox_paired_stims.setText(_translate("mainWindow", "stim / stim"))
        self.pushButton_export_selection.setText(_translate("mainWindow", "selection"))
        self.label_export.setText(_translate("mainWindow", "Export"))
        self.pushButton_export_groups.setText(_translate("mainWindow", "groups"))
        self.menuFile.setTitle(_translate("mainWindow", "File"))
        self.menuData.setTitle(_translate("mainWindow", "Data"))
        self.menuGroups.setTitle(_translate("mainWindow", "Groups"))
        self.menuEdit.setTitle(_translate("mainWindow", "Edit"))
        self.menuView.setTitle(_translate("mainWindow", "View"))

        ################################################################
        #       non-QtDesigner-generated instructions                  #
        ################################################################

        self.pushButtonParse.setVisible(False)
        self.checkBox_force1stim.setVisible(False)
        self.progressBar.setVisible(False)
        self.progressBar.setValue(0)

        if config.hide_experimental:
            self.checkBox_show_all_events.setVisible(False)
            self.checkBox_output_per_stim.setVisible(False)
            self.checkBox_paired_stims.setVisible(False)
            self.checkBox_timepoints_per_stim.setVisible(False)
            self.pushButton_stim_assign_threshold.setVisible(False)
            self.pushButton_stim_detect.setVisible(False)
            self.label_stim_detection_threshold.setVisible(False)
            self.frameToolBin.setVisible(False)
            #            self.checkBox_bin.setVisible(False)
            self.pushButton_norm_range_set_all.setVisible(False)
            self.frameToolExport.setVisible(False)
            self.lineEdit_EPSP_amp_halfwidth.setVisible(False)
            self.lineEdit_volley_amp_halfwidth.setVisible(False)
            self.label_header_amp_halfwidth.setVisible(False)
            self.label_EPSP_amp_halfwidth.setVisible(False)
            self.label_volley_amp_halfwidth.setVisible(False)


################################################################
#        Dialog and table classes                              #
################################################################


class Ui_Dialog(QtWidgets.QWidget):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(1105, 525)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setGeometry(QtCore.QRect(930, 480, 161, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.widget = FileTreeSelectorDialog(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 10, 451, 501))
        self.widget.setObjectName("widget")
        self.tableView = QtWidgets.QTableView(Dialog)
        self.tableView.setGeometry(QtCore.QRect(570, 10, 521, 461))
        self.tableView.setObjectName("tableView")

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))


class InputDialogPopup(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.input = QtWidgets.QLineEdit(self)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.buttonBox)

    def showInputDialog(self, title, query):
        self.setWindowTitle(title)
        self.input.setPlaceholderText(query)
        self.setFixedSize(300, 150)  # Set the fixed width and height of the dialog
        result = self.exec_()
        text = self.input.text()
        if result == QtWidgets.QDialog.Accepted:
            print(f"You entered: {text}")
            return text


class ConfirmDialog(QtWidgets.QDialog):
    """Confirmation dialog with OK and Cancel buttons.
    Usage:
        dlg = ConfirmDialog(title='Confirm', message='Are you sure?')
        ok = dlg.showConfirmDialog()
        # ok is True when user pressed OK, False otherwise
    """

    def __init__(self, title: str = "Confirm", message: str = "Are you sure?"):
        super().__init__()
        self.setWindowTitle(title)
        self.label = QtWidgets.QLabel(message, self)
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.buttonBox)

    def showConfirmDialog(
        self, title: str | None = None, message: str | None = None
    ) -> bool:
        """Show the dialog modally. Returns True for OK, False for Cancel."""
        if title is not None:
            self.setWindowTitle(title)
        if message is not None:
            self.label.setText(message)
        result = self.exec_()
        return result == QtWidgets.QDialog.Accepted


def confirm(title: str = "Confirm", message: str = "Are you sure?") -> bool:
    """Convenience function: show confirmation dialog and return bool result."""
    dlg = ConfirmDialog(title=title, message=message)
    return dlg.showConfirmDialog()


class TableProjSub(QtWidgets.QTableView):
    # TODO: This class does the weirdest things to events; shifting event numbers around in non-standard ways and refuses to notice drops - but drag-into works. Why?
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            file_urls = [url.toLocalFile() for url in event.mimeData().urls()]
            print("Files dropped:", file_urls)
            # Handle the dropped files here
            dfAdd = df_projectTemplate()
            dfAdd["path"] = (
                file_urls  # needs to be first, as it sets the number of rows
            )
            dfAdd["host"] = str(self.parent.fqdn)
            dfAdd["filter"] = "voltage"
            # NTH: more intelligent default naming; lowest level unique name?
            # For now, use name + lowest level folder
            names = []
            duplicates = []  # remove these from dfAdd
            for i in file_urls:
                # check if file is already in df_project
                if i in self.parent.df_project["path"].values:
                    print(f"File {i} already in df_project")
                    duplicates.append(i)
                else:
                    names.append(
                        os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i)
                    )
            if not names:
                print("No new files to add.")
                return
            dfAdd = dfAdd.drop(dfAdd[dfAdd["path"].isin(duplicates)].index)
            dfAdd["recording_name"] = names
            self.parent.addData(dfAdd)
            event.acceptProposedAction()
        else:
            event.ignore()


class Filetreesub(Ui_Dialog):
    def __init__(self, dialog, parent=None, folder="."):
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)
        self.parent = parent
        if config.verbose:
            print(" - Filetreesub init")

        self.ftree = self.widget
        # set root_path for file tree model
        self.ftree.delayedInitForRootPath(folder)
        # self.ftree.model.parent_index   = self.ftree.model.setRootPath(projects_folder)
        # self.ftree.model.root_index     = self.ftree.model.index(projects_folder)

        # Dataframe to add
        self.names = []
        self.dfAdd = df_projectTemplate()

        self.buttonBoxAddGroup = QtWidgets.QDialogButtonBox(dialog)
        self.buttonBoxAddGroup.setGeometry(QtCore.QRect(470, 20, 91, 491))
        self.buttonBoxAddGroup.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBoxAddGroup.setOrientation(QtCore.Qt.Vertical)
        self.buttonBoxAddGroup.setStandardButtons(QtWidgets.QDialogButtonBox.NoButton)
        self.buttonBoxAddGroup.setObjectName("buttonBoxAddGroup")

        self.ftree.view.clicked.connect(
            self.widget.on_treeView_fileTreeSelector_clicked
        )
        self.ftree.model.paths_selected.connect(self.pathsSelectedUpdateTable)
        self.buttonBox.accepted.connect(self.addDf)

        self.tablemodel = TableModel(self.dfAdd)
        self.tableView.setModel(self.tablemodel)

    def addDf(self):
        self.parent.slotAddDfData(self.dfAdd)

    def pathsSelectedUpdateTable(self, paths):
        # TODO: Extract host and group
        dfAdd = df_projectTemplate()
        dfAdd["path"] = paths
        dfAdd["host"] = str(self.parent.fqdn)
        dfAdd["filter"] = "voltage"
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(
                os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i)
            )
        dfAdd["recording_name"] = names
        self.dfAdd = dfAdd
        # TODO: Add a loop that prevents duplicate names by adding a number until it becomes unique
        # format tableView
        header = self.tableView.horizontalHeader()
        self.tableView.setColumnHidden(0, True)  # host
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # path
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # name
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # group
        self.tableView.update()


###########################
#       Main class        #
###########################


# subclassing Ui_MainWindow to be able to use the unaltered output file from pyuic and QT designer
class UIsub(Ui_MainWindow):
    def __init__(self, mainwindow):
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)  # as generated by QtDesigner - do not touch!
        if config.verbose:
            print(" - UIsub init, verbose mode")
        self.bootstrap(mainwindow)  # set up general UI
        self.loadProject()  # load project data

    # Debugging tools

    def checkFocus(self):
        focused_widget = QtWidgets.QApplication.focusWidget()
        if focused_widget is not None:
            print(f"Focused Widget: {focused_widget.objectName()}")
        else:
            print("No widget has focus.")

    def find_widgets_with_top_left_coordinates(self, widget):
        print(f"trying child geometry")
        for child in widget.findChildren(QtWidgets.QWidget):
            # print(f"attribs: {dir(child.geometry())}")
            print(
                f"child.geometry(): {child.objectName()}, {child.geometry().topLeft()},  {child.mapTo(self.centralwidget, child.geometry().topLeft())}, {child.geometry().size()}"
            )

    ######################################################################
    #                     Selection changers                             #
    ######################################################################

    def tableProjSelectionChanged(self):
        if self.updating_tableProj:
            return
        self.usage("tableProjSelectionChanged")
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            self.tableProj.clearSelection()
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        # build the list uistate.list_idx_select_recs with indices
        uistate.list_idx_select_recs = [index.row() for index in selected_indexes]
        # print(f" - rec_select: {uistate.list_idx_select_recs}")
        self.update_recs2plot()
        self.update_show()
        if uistate.df_recs2plot is None:
            print("No parsed recordings selected.")
            self.graphRefresh()
            return
        prow = self.get_prow()
        # if exactly one stim of one recording is selected, reference its data in uistate.df_rec_select_data, and timepoints in uistate.df_rec_select_time
        if (
            len(uistate.list_idx_select_recs) == 1
            and len(uistate.list_idx_select_stims) == 1
        ):
            uistate.df_rec_select_time = dft_for_format = self.get_dft(row=prow)
            uistate.df_rec_select_data = self.get_dffilter(prow)
            uistate.float_sweep_duration_max = prow["sweep_duration"]
            if config.verbose:
                print(
                    f"One recording selected: index {uistate.list_idx_select_recs[0]}"
                )
                print(f"One stim selected: index {uistate.list_idx_select_stims[0]}")
        else:
            uistate.df_rec_select_data = None
            uistate.df_rec_select_time = None
            # store the selected prow with the highest sweep duration for layout formatting, so that the full x-axis is visible
            longest_sweep_prow = uistate.df_recs2plot.loc[
                uistate.df_recs2plot["sweep_duration"].idxmax()
            ]
            uistate.float_sweep_duration_max = longest_sweep_prow["sweep_duration"]
            dft_for_format = self.get_dft(row=longest_sweep_prow)

        if uistate.dict_rec_show:
            selected_stims = (
                self.tableStim.selectionModel().selectedRows()
            )  # save selection
            self.tableStimModel.setData(dft_for_format)
            model = self.tableStim.model()
            selection = QtCore.QItemSelection()
            for index in selected_stims:
                row_idx = index.row()
                index_start = model.index(row_idx, 0)  # Start of the row (first column)
                index_end = model.index(
                    row_idx, model.columnCount(QtCore.QModelIndex()) - 1
                )  # End of the row (last column)
                selection.select(index_start, index_end)
            self.tableStim.selectionModel().select(
                selection, QtCore.QItemSelectionModel.Select
            )
            self.formatTableStimLayout(dft=dft_for_format)
        self.zoomAuto()

        t0 = time.time()
        self.mouseoverUpdate()
        print(f" - - mouseoverUpdate: {round((time.time() - t0) * 1000)} ms")

    def stimSelectionChanged(self):
        self.usage(f"stimSelectionChanged")
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            self.tableStim.clearSelection()
        if uistate.mean_mouseover_stim_select is None:  # clicked table
            selected_indexes = self.tableStim.selectionModel().selectedRows()
        else:  # clicked graph
            row = uistate.mean_mouseover_stim_select - 1
            selected_indexes = [self.tableStimModel.index(row, 0)]
        uistate.mean_mouseover_stim_select = None
        # build the list uistate.list_idx_select_stims with indices
        uistate.list_idx_select_stims = [index.row() for index in selected_indexes]
        self.update_show()
        self.zoomAuto()
        self.mouseoverUpdate()

    def update_show(self, reset=False):
        aspects = [
            "EPSP_amp",
            "EPSP_slope",
            "volley_amp",
            "volley_slope",
            "volley_amp_mean",
            "volley_slope_mean",
        ]
        old_selection = uistate.dict_rec_show
        if uistate.df_recs2plot is None:
            reset = True
            new_selection = {}
        else:
            selected_ids = set(uistate.df_recs2plot["ID"])
            selected_stims = [
                stim + 1 for stim in uistate.list_idx_select_stims
            ]  # stim_select is 0-based (indices) - convert to stims
            print(
                f"update_show, selected_ids: {selected_ids}, selected_stims: {selected_stims}, reset: {reset}"
            )
            # remove non-selected recs and stims
            new_selection = {
                k: v
                for k, v in uistate.dict_rec_labels.items()
                if v["rec_ID"] in selected_ids
                and (v["stim"] in selected_stims or v["stim"] is None)
                and all(
                    uistate.checkBox[aspect] or v.get("aspect", "") != aspect
                    for aspect in aspects
                )
            }
            if not uistate.checkBox["norm_EPSP"]:
                filters = [" norm"]
            else:
                filters = [
                    " EPSP amp",
                    " EPSP slope",
                ]
            new_selection = {
                k: v
                for k, v in new_selection.items()
                if not any(k.endswith(f) for f in filters)
            }
        if reset:  # Hide all lines
            obsolete_lines = uistate.dict_rec_labels
        else:
            obsolete_lines = {
                k: v for k, v in old_selection.items() if k not in new_selection
            }
        for line_dict in obsolete_lines.values():
            line_dict["line"].set_visible(False)
        # Show what's now selected
        added_lines = {k: v for k, v in new_selection.items() if k not in old_selection}
        for line_dict in added_lines.values():
            line_dict["line"].set_visible(True)
        uistate.dict_rec_show = new_selection

        # group view
        if self.dd_groups is not None:
            reset_groups = False
            if uistate.dict_group_show == {}:
                reset_groups = True
            old_group_selection = uistate.dict_group_show.copy()
            # if any recs are selected, show only groups that contain selected recs
            if uistate.df_recs2plot is not None:
                selected_groups = {
                    group
                    for rec_ID in selected_ids
                    for group in self.get_groupsOfRec(rec_ID)
                }
                new_group_selection = {
                    k: v
                    for k, v in uistate.dict_group_labels.items()
                    if v["group_ID"] in selected_groups
                }
            else:
                new_group_selection = uistate.dict_group_labels.copy()
            new_group_selection = {
                k: v
                for k, v in new_group_selection.items()
                if all(
                    uistate.checkBox[aspect] or v.get("aspect", "") != aspect
                    for aspect in aspects
                )
            }
            if uistate.checkBox["norm_EPSP"]:
                filters = [" norm"]
            else:
                filters = [" mean"]
            new_group_selection = {
                k: v
                for k, v in new_group_selection.items()
                if any(k.endswith(f) for f in filters)
                and self.dd_groups[v["group_ID"]]["show"]
            }
            if reset_groups:  # Hide all lines
                obsolete_group_lines = uistate.dict_group_labels
            else:
                obsolete_group_lines = {
                    k: v
                    for k, v in old_group_selection.items()
                    if k not in new_group_selection
                }
            print(f"obsolete_group_lines: {obsolete_group_lines.keys()}")
            for k, line_dict in obsolete_group_lines.items():
                print(f"Obsolete group line key: {k}")
                line_dict["line"].set_visible(False)
                line_dict["fill"].set_visible(False)
            # Show what's now selected
            added_group_lines = {
                k: v
                for k, v in new_group_selection.items()
                if k not in old_group_selection
            }
            print(f"added_group_lines: {added_group_lines.keys()}")
            for k, line_dict in added_group_lines.items():
                print(f"Added group line key: {k}")
                line_dict["line"].set_visible(True)
                line_dict["fill"].set_visible(True)
            uistate.dict_group_show = new_group_selection

        # return
        # DEBUG block - for inquiring visiblity of specific lines
        for key, value in self.dd_groups.items():
            print(f"update_show: {key}, show:{value['show']}")
        print(f"update_show: {len(uistate.dict_rec_show)}")
        for key, value in uistate.dict_rec_show.items():
            if key.endswith(" volley amp mean") or key.endswith(" volley slope mean"):
                print(f"update_show: {key}, show:{value['line'].get_visible()}")
                print(f" - ydata: {value['line'].get_ydata()}")

    ##################################################################
    #    WIP section: TODO: move to appropriate header               #
    ##################################################################

    def binSweeps(self):
        print(
            "binSweeps - later on, this is to bin only the selected recording: now it does nothing and should be hidden"
        )

    def graphRefresh(self):
        self.usage("graphRefresh")
        uiplot.graphRefresh(self.dd_groups)

    def deleteFolder(self, dir_path):
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # remove file or symlink
                elif os.path.isdir(file_path):
                    self.deleteFolder(file_path)  # recursively remove a subdirectory
            os.rmdir(dir_path)  # remove the directory itself

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
        # print(f"persistOutput: rec_name: {rec_name}")
        # print(f"{dfoutput}")
        self.dict_outputs[rec_name] = dfoutput
        self.df2file(df=dfoutput, rec=rec_name, key="output")

    def uiFreeze(self):  # Disable selection changes and checkboxes
        if uistate.frozen:
            return
        uistate.frozen = True
        self.tableProj.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.tableStim.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.connectUIstate(disconnect=True)
        for key, _ in uistate.checkBox.items():
            checkBox = getattr(self, f"checkBox_{key}")
            checkBox.setEnabled(False)

    def uiThaw(self):  # Enable selection changes and checkboxes
        if not uistate.frozen:
            return
        self.tableProj.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tableStim.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.connectUIstate()
        for key, _ in uistate.checkBox.items():
            checkBox = getattr(self, f"checkBox_{key}")
            checkBox.setEnabled(True)
        uistate.frozen = False

    def toggleHeatmap(self):
        uistate.showHeatmap = not uistate.showHeatmap
        print(f"Heatmap is {uistate.showHeatmap}")
        if not uistate.showHeatmap:
            uiplot.heatunmap()
            return
        t0 = time.time()
        d_group_ndf = {}
        list_l = []
        for key, sub_dict in self.dd_groups.items():
            if sub_dict["show"]:
                n = len(sub_dict["rec_IDs"])
                df = self.get_dfgroupmean(key)
                list_l.append(len(df))
                d_group_ndf[key] = [n, df]
        if len(d_group_ndf) == 2:
            if list_l[0] == list_l[1]:
                for key, ndf in d_group_ndf.items():
                    n = ndf[0]
                    df = ndf[1]
                    l = len(df)
                    list_l.append(l)
                    print(f"{key} - N: {n} - {l} sweeps")
                # perform test
                norm = uistate.checkBox["norm_EPSP"]
                amp = uistate.checkBox["EPSP_amp"]
                slope = uistate.checkBox["EPSP_slope"]
                df_ttest = analysis.ttest_df(
                    d_group_ndf, norm=norm, amp=amp, slope=slope
                )
                if not df_ttest.empty:
                    uiplot.heatmap(df_ttest)
                print(df_ttest)
            else:
                print("t-test requires number of sweeps to match")
        else:
            print("t-test currently only available between exactly 2 shown groups")
        print(f"Heatmap: {round((time.time() - t0) * 1000)} ms")

    def setTableStimVisibility(self, state):
        widget = self.h_splitterMaster.widget(
            1
        )  # Get the second widget in the splitter
        widget.setVisible(state)

    def onSplitterMoved(self, pos, index):
        splitter = self.sender()
        splitter_name = splitter.objectName()
        total_size = sum(splitter.sizes())
        proportions = [size / total_size for size in splitter.sizes()]
        # print(f"{splitter_name}, total_size: {total_size}, Proportions: {proportions}")
        uistate.splitter[splitter_name] = proportions
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def toggleViewTool(self, frame):
        self.usage(f"toggleViewTool {frame}")
        uistate.viewTools[frame][1] = not uistate.viewTools[frame][1]
        getattr(self, frame).setVisible(uistate.viewTools[frame][1])
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def talkback(self):
        prow = self.get_prow()
        trow = self.get_trow()
        dfmean = self.get_dfmean(prow)
        t_stim = trow["t_stim"]
        t_start = t_stim - 0.002
        t_end = t_stim + 0.018
        dfevent = dfmean[(dfmean["time"] >= t_start) & (dfmean["time"] < t_end)]
        dfevent = dfevent[["time", "voltage"]]
        path_talkback_df = Path(
            f"{self.projects_folder}/talkback/talkback_slice_{prow['ID']}_stim.csv"
        )
        if not path_talkback_df.parent.exists():
            path_talkback_df.parent.mkdir(parents=True, exist_ok=True)
        dfevent.to_csv(path_talkback_df, index=False)
        # save the event data as a dict
        keys = [
            #            't_EPSP_amp', 't_EPSP_amp_method', 't_EPSP_amp_params',
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",  #'t_EPSP_slope_method', 't_EPSP_slope_params',
            #'t_volley_amp', 't_volley_amp_method', 't_volley_amp_params',
            "t_volley_slope_start",
            "t_volley_slope_end",  # 't_volley_slope_method', 't_volley_slope_params'
        ]
        dict_event = {key: trow[key] for key in keys}
        print(f"talkback dict_event: {dict_event}")
        # store dict_event as .csv named after recording_name
        path_talkback = Path(
            f"{self.projects_folder}/talkback/talkback_meta_{prow['ID']}_stim.csv"
        )
        with open(path_talkback, "w") as f:
            json.dump(dict_event, f)

    def darkmode(self):
        if uistate.darkmode:
            self.mainwindow.setStyleSheet("background-color: #2A2A2A; color: #fff;")

            table_style = """
                QTableView::item:selected {
                    background-color: #555;
                    color: #FFF;
                }
                QHeaderView::section {
                    background-color: #333;
                    color: #FFF;
                }
                QTableCornerButton::section {
                    background-color: #333;
                    color: #FFF;
                }
            """
            self.tableProj.setStyleSheet(table_style)
            self.tableStim.setStyleSheet(table_style)
        else:
            self.mainwindow.setStyleSheet("")
            self.tableProj.setStyleSheet("")
            self.tableStim.setStyleSheet("")

        uiplot.styleUpdate()
        self.graphRefresh()

    def get_dfv(self):
        # returns a dfV filtered by recording selection. Builds one if there is none.
        # NB: assumes the dfV shares indices with df_project!
        # TODO: deprecate by setting and maintaining y-limits as df_project columns
        if uistate.dfv is not None:
            return uistate.dfv
        t0 = time.time()
        dfv = self.get_df_project().copy()
        # find voltage range of selected recordings
        for i, row in dfv.iterrows():
            dffilter = self.get_dffilter(row)
            # mean voltages
            dfv.loc[i, "vmin"] = dffilter["voltage"].min()
            dfv.loc[i, "vmax"] = dffilter["voltage"].max()
            # event voltages # TODO: Hardcoded components - make configurable
            trow = self.get_trow(dfp_idx=i)
            event_start = trow["t_stim"] + 0.002  # s after stim
            event_end = event_start + 0.040
            dfv.loc[i, "event_vmin"] = dffilter[
                (dffilter["time"] >= event_start) & (dffilter["time"] <= event_end)
            ]["voltage"].min()
            dfv.loc[i, "event_vmax"] = (
                0.0005  # dffilter[(dffilter['time'] >= event_start) & (dffilter['time'] <= event_end)]['voltage'].max()
            )
            # output measurements
            dfout = self.get_dfoutput(row)  # TODO: Norm handling
            dfv.loc[i, "amp_min"] = dfout["EPSP_amp"].min()
            dfv.loc[i, "amp_max"] = dfout["EPSP_amp"].max()
            dfv.loc[i, "slope_min"] = dfout["EPSP_slope"].min()
            dfv.loc[i, "slope_max"] = dfout["EPSP_slope"].max()
            print(f"* * * * \n{dfv}")
            uistate.dfv = dfv
        print(
            f" - get_dfv voltage range calc time: {round((time.time() - t0) * 1000)} ms"
        )
        return uistate.dfv

    def zoomAuto(self, reset=False):
        # set and apply Auto-zoom parameters for all axes
        self.usage("zoomAuto")
        prow = self.get_prow()
        dfmean = self.get_dfmean(prow)
        # axm:
        vmin = dfmean["voltage"].min()
        vmax = dfmean["voltage"].max()
        uistate.zoom["mean_xlim"] = (0, prow["sweep_duration"])
        uistate.zoom["mean_ylim"] = (vmin, vmax)
        # axe:
        uistate.zoom["event_ylim"] = (-0.0015, 0.0002)
        uistate.zoom["event_xlim"] = (-0.0012, 0.030)
        # ax1 and ax2
        uistate.zoom["output_ax1_ylim"] = (0, 1.5)
        uistate.zoom["output_ax2_ylim"] = (0, 1.5)
        uistate.zoom["output_xlim"] = (0, prow["sweeps"])
        self.zoomReset()
        return

        if reset:
            uistate.dfv = None
        dfv = self.get_dfv()
        # invalid df or invalid indices
        if dfv is None or len(dfv) == 0:
            return
        # intersect selected indices with df index
        valid_idx = [i for i in uistate.list_idx_select_recs if i in dfv.index]
        if not valid_idx:
            return
        dfv_select = dfv.loc[valid_idx]
        if dfv_select is None or dfv_select.empty:
            return
        # axm:
        vmin = dfv_select["vmin"].min()
        vmax = dfv_select["vmax"].max()
        uistate.zoom["mean_xlim"] = (0, dfv_select["sweep_duration"].max())
        uistate.zoom["mean_ylim"] = (vmin, vmax)
        # axe:
        event_vmin = dfv_select["event_vmin"].min()
        event_vmax = dfv_select["event_vmax"].max()
        margin = 0.05
        uistate.zoom["event_ylim"] = (
            event_vmin - abs(event_vmin * margin),
            event_vmax + abs(event_vmax * margin),
        )

        # ax1 and ax2
        if uistate.checkBox["bin"]:
            first, last = (
                0,
                max(
                    (dfv_select["sweeps"].max() - 1) / uistate.lineEdit["bin_size"] - 1,
                    1,
                ),
            )
        else:
            first, last = 0, max(dfv_select["sweeps"].max() - 1, 1)
        if uistate.checkBox["output_per_stim"]:
            first, last = 1, max(dfv_select["stims"].max(), 2)

        amp_min = 0 if uistate.checkBox["output_ymin0"] else dfv_select["amp_min"].min()
        amp_max = dfv_select["amp_max"].max()
        slope_min = (
            0 if uistate.checkBox["output_ymin0"] else dfv_select["slope_min"].min()
        )
        slope_max = dfv_select["slope_max"].max()

        uistate.zoom["output_ax1_ylim"] = amp_min, amp_max * (1 + margin)
        uistate.zoom["output_ax2_ylim"] = slope_min, slope_max * (1 + margin)
        uistate.zoom["output_xlim"] = first, last

        self.zoomReset()

    def zoomReset(self, axis=None):
        # self.usage("zoomReset")
        if axis is None:
            for axis in [
                uistate.axm,
                uistate.axe,
                uistate.ax1,
                uistate.ax2,
            ]:
                # print(f"zoomReset: all canvases: {axis}")
                self.zoomReset(axis)
            return
        if axis == uistate.axm:
            if config.verbose:
                print("zoomReset: axm")
            axis.axes.set_xlim(uistate.zoom["mean_xlim"])
            axis.axes.set_ylim(uistate.zoom["mean_ylim"])
        elif axis == uistate.axe:
            if config.verbose:
                print("zoomReset: axe")
            axis.axes.set_xlim(uistate.zoom["event_xlim"])
            axis.axes.set_ylim(uistate.zoom["event_ylim"])
        elif axis == uistate.ax1 or axis == uistate.ax2:
            if config.verbose:
                print("zoomReset: ax1/ax2")
            uistate.ax1.axes.set_xlim(uistate.zoom["output_xlim"])
            uistate.ax2.axes.set_xlim(uistate.zoom["output_xlim"])
            uistate.ax1.axes.set_ylim(uistate.zoom["output_ax1_ylim"])
            uistate.ax2.axes.set_ylim(uistate.zoom["output_ax2_ylim"])
        else:
            raise ValueError("zoomReset: unknown axis")
        axis.figure.canvas.draw_idle()

    def update_recs2plot(self):
        if uistate.list_idx_select_recs:
            df_project_selected = self.get_df_project().iloc[
                uistate.list_idx_select_recs
            ]
            uistate.df_recs2plot = df_project_selected[
                df_project_selected["sweeps"] != "..."
            ]
            if uistate.df_recs2plot.empty:
                uistate.df_recs2plot = None
        else:
            uistate.df_recs2plot = None

    def viewSettingsChanged(self, key, state):
        self.usage(f"viewSettingsChanged {key}, {state == 2}")
        if key in uistate.checkBox.keys():
            uistate.checkBox[key] = state == 2
            if key == "norm_EPSP":
                self.label_norm_on_sweep.setVisible(state == 2)
                self.label_relative_to.setVisible(state == 2)
                self.lineEdit_norm_EPSP_start.setVisible(state == 2)
                self.lineEdit_norm_EPSP_end.setVisible(state == 2)
            elif key == "force1stim":
                self.checkBox_force1stim_changed(state)
            elif key == "output_per_stim":
                self.checkBox_output_per_stim_changed(state)
            elif key == "timepoints_per_stim":
                self.checkBox_timepoints_per_stim_changed(state)
            elif key == "output_ymin0":
                self.zoomAuto()
            elif key == "bin":
                self.checkBox_bin_changed(state)
        self.update_show()
        self.mouseoverUpdate()
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def groupControlsRefresh(self):
        self.group_controls_remove()
        for group_ID in self.dd_groups.keys():
            self.group_controls_add(group_ID)

    def usage(self, ui_component):  # Talkback function
        if config.verbose:
            print()
            print(f"usage: {ui_component}")
        if not config.talkback:
            return
        if ui_component not in self.dict_usage.keys():
            self.dict_usage[ui_component] = 0
        self.dict_usage[ui_component] += 1
        self.write_usage()

    def write_usage(self):
        path_usage = Path(f"{self.projects_folder}/talkback/usage.yaml")
        if not path_usage.parent.exists():
            path_usage.parent.mkdir(parents=True, exist_ok=True)
        # make sure 'WARNING' and 'alias' are printed first
        top_keys = ["WARNING", "alias"]
        dict_bottom = self.dict_usage.copy()
        top_data = {key: dict_bottom.pop(key, None) for key in top_keys}
        with path_usage.open("w") as file:
            yaml.safe_dump(top_data, file, default_flow_style=False)
            yaml.safe_dump(dict_bottom, file, default_flow_style=False)

    def resetCacheDicts(self):
        self.dict_datas = {}  # all raw data
        self.dict_filters = {}  # all processed data, based on raw data
        self.dict_bins = {}  # all binned data, based on filters
        self.dict_means = {}  # all means
        self.dict_ts = {}  # all timepoints
        self.dict_outputs = {}  # all outputs, x per sweep
        self.dict_group_means = {}  # means of all group outputs
        self.dict_diffs = {}  # all diffs (for paired stim)

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

    # uisub init refactoring

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

    def setupTalkback(self):
        path_usage = Path(f"{self.projects_folder}/talkback/usage.yaml")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if path_usage.exists():
            with path_usage.open("r") as file:
                self.dict_usage = yaml.safe_load(file)
            self.dict_usage[f"last_used_{config.version}"] = now
        else:
            os_name = sys.platform
            self.dict_usage = {
                "WARNING": "Do NOT set your alias to anything that can be used to identify you!",
                "alias": "",
                "ID": str(uuid.uuid4()),
                "os": os_name,
                "ID_created": now,
                f"last_used_{config.version}": now,
            }
        self.write_usage()

    def setSplitterSizes(self, *splitter_names):
        for splitter_name in splitter_names:
            splitter = getattr(self, splitter_name)
            proportions = uistate.splitter[splitter_name]
            widgets = [splitter.widget(i) for i in range(splitter.count())]
            # Store the original size policies of the widgets, and set their size policy to QtWidgets.QSizePolicy.Ignored
            # Set width/height depending on splitter orientation
            sizes = []
            for widget in widgets:
                # original_size_policy = widget.sizePolicy()
                widget.setSizePolicy(
                    QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
                )
                if splitter.orientation() == QtCore.Qt.Horizontal:
                    sizes.append(
                        int(
                            proportions[widgets.index(widget)]
                            * splitter.sizeHint().width()
                        )
                    )
                else:
                    sizes.append(
                        int(
                            proportions[widgets.index(widget)]
                            * splitter.sizeHint().height()
                        )
                    )
                # widget.setSizePolicy(original_size_policy)
            splitter.setSizes(sizes)

    def setupCanvases(self):
        def setup_graph(graph):
            graph.setLayout(QtWidgets.QVBoxLayout())
            canvas = MplCanvas(parent=graph)
            graph.layout().addWidget(canvas)
            canvas.mpl_connect(
                "button_press_event", lambda event: self.graphClicked(event, canvas)
            )
            canvas.show()
            return canvas

        self.canvasMean = setup_graph(self.graphMean)
        self.canvasEvent = setup_graph(self.graphEvent)
        self.canvasOutput = setup_graph(self.graphOutput)

    def setupMenus(self):
        # File menu
        self.actionNew = QtWidgets.QAction("New project", self)
        self.actionNew.triggered.connect(self.triggerNewProject)
        self.actionNew.setShortcut("Ctrl+N")
        self.menuFile.addAction(self.actionNew)
        self.actionOpen = QtWidgets.QAction("Open project", self)
        self.actionOpen.triggered.connect(self.triggerOpenProject)
        self.actionOpen.setShortcut("Ctrl+O")
        self.menuFile.addAction(self.actionOpen)
        self.actionRenameProject = QtWidgets.QAction("Rename project", self)
        self.actionRenameProject.triggered.connect(self.renameProject)
        self.actionRenameProject.setShortcut("Ctrl+R")
        self.menuFile.addAction(self.actionRenameProject)
        self.actionExit = QtWidgets.QAction("Exit", self)
        self.actionExit.triggered.connect(QtWidgets.qApp.quit)
        # self.actionExit.setShortcut("Ctrl+Q")  # Set shortcut for Exit
        self.menuFile.addAction(self.actionExit)

        # Edit menu
        # self.actionUndo = QtWidgets.QAction("Undo", self) # TODO: Implement undo
        # self.actionUndo.triggered.connect(self.triggerUndo)
        # self.actionUndo.setShortcut("Ctrl+Z")
        # self.menuEdit.addAction(self.actionUndo)
        self.actionCopyTimepoints = QtWidgets.QAction("Copy timepoints", self)
        self.actionCopyTimepoints.triggered.connect(self.triggerCopyTimepoints)
        self.actionCopyTimepoints.setShortcut("Ctrl+T")
        self.menuEdit.addAction(self.actionCopyTimepoints)
        self.actionCopyOutput = QtWidgets.QAction("Copy output", self)
        self.actionCopyOutput.triggered.connect(self.triggerCopyOutput)
        self.actionCopyOutput.setShortcut("Ctrl+C")
        self.menuEdit.addAction(self.actionCopyOutput)

        self.menuEdit.addSeparator()
        self.actionForAllSelected = QtWidgets.QAction(
            "For ALL selected recordings...", self
        )  # not connected: submenu header
        self.menuEdit.addAction(self.actionForAllSelected)
        self.actionReAnalyzeRecordings = QtWidgets.QAction("   Reanalyze", self)
        self.actionReAnalyzeRecordings.triggered.connect(self.triggerReanalyze)
        self.actionReAnalyzeRecordings.setShortcut("A")
        self.menuEdit.addAction(self.actionReAnalyzeRecordings)

        self.actionKeepOnlySelectedSweeps = QtWidgets.QAction(
            "   Keep only selected sweeps", self
        )
        self.actionKeepOnlySelectedSweeps.triggered.connect(
            self.triggerKeepSelectedSweeps
        )
        self.menuEdit.addAction(self.actionKeepOnlySelectedSweeps)
        self.actionRemoveSelectedSweeps = QtWidgets.QAction(
            "   Discard selected sweeps", self
        )
        self.actionRemoveSelectedSweeps.triggered.connect(
            self.triggerRemoveSelectedSweeps
        )
        self.menuEdit.addAction(self.actionRemoveSelectedSweeps)
        self.actionSplitBySelectedSweeps = QtWidgets.QAction(
            "   Split recordings by selected sweeps", self
        )
        self.actionSplitBySelectedSweeps.triggered.connect(
            self.triggerSplitBySelectedSweeps
        )
        self.menuEdit.addAction(self.actionSplitBySelectedSweeps)

        # View menu
        self.actionRefresh = QtWidgets.QAction("Refresh Graphs", self)
        self.actionRefresh.triggered.connect(self.triggerRefresh)
        self.actionRefresh.setShortcut("F5")
        self.menuView.addAction(self.actionRefresh)

        self.actionHeatmap = QtWidgets.QAction("Toggle Heatmap", self)
        self.actionHeatmap.setCheckable(True)
        self.actionHeatmap.setChecked(uistate.showHeatmap)
        self.actionHeatmap.setShortcut("H")
        self.actionHeatmap.triggered.connect(self.triggerShowHeatmap)
        self.menuView.addAction(self.actionHeatmap)

        self.actionDarkmode = QtWidgets.QAction("Toggle Darkmode", self)
        self.actionDarkmode.triggered.connect(self.triggerDarkmode)
        self.actionDarkmode.setShortcut("Alt+D")
        self.menuView.addAction(self.actionDarkmode)

        actionTimetable = QtWidgets.QAction("Toggle Timetable", self)
        actionTimetable.setCheckable(True)
        actionTimetable.setChecked(uistate.showTimetable)
        actionTimetable.setShortcut("Alt+T")
        actionTimetable.triggered.connect(self.triggerShowTimetable)
        self.menuView.addAction(actionTimetable)

        for frame, (text, initial_state) in uistate.viewTools.items():
            action = QtWidgets.QAction(f"Toggle {text}", self)
            action.setCheckable(True)
            action.setChecked(initial_state)
            action.triggered.connect(
                lambda state, frame=frame: self.toggleViewTool(frame)
            )
            self.menuView.addAction(action)

        # Data menu
        self.actionAddData = QtWidgets.QAction("Add data files", self)
        self.actionAddData.triggered.connect(self.triggerAddData)
        self.menuData.addAction(self.actionAddData)
        self.actionParse = QtWidgets.QAction("Import all added datafiles", self)
        self.actionParse.triggered.connect(self.triggerParse)
        self.actionParse.setShortcut("Ctrl+I")
        self.menuData.addAction(self.actionParse)
        self.actionDelete = QtWidgets.QAction("Delete selected data", self)
        self.actionDelete.triggered.connect(self.triggerDelete)
        self.actionDelete.setShortcut("DEL")
        self.menuData.addAction(self.actionDelete)
        self.actionRenameRecording = QtWidgets.QAction("Rename recording", self)
        self.actionRenameRecording.triggered.connect(self.triggerRenameRecording)
        self.actionRenameRecording.setShortcut("F2")
        self.menuData.addAction(self.actionRenameRecording)

        # Group menu
        self.actionNewGroup = QtWidgets.QAction("Add a group", self)
        self.actionNewGroup.triggered.connect(self.triggerNewGroup)
        self.actionNewGroup.setShortcut("+")
        self.menuGroups.addAction(self.actionNewGroup)
        self.actionRemoveEmptyGroup = QtWidgets.QAction("Remove last empty group", self)
        self.actionRemoveEmptyGroup.triggered.connect(self.triggerRemoveLastEmptyGroup)
        self.actionRemoveEmptyGroup.setShortcut("-")
        self.menuGroups.addAction(self.actionRemoveEmptyGroup)
        self.actionRemoveGroup = QtWidgets.QAction("Force remove last group", self)
        self.actionRemoveGroup.triggered.connect(self.triggerRemoveLastGroup)
        self.actionRemoveGroup.setShortcut("Ctrl+-")
        self.menuGroups.addAction(self.actionRemoveGroup)
        self.actionClearGroups = QtWidgets.QAction("Clear group(s) in selection", self)
        self.actionClearGroups.triggered.connect(self.triggerClearGroups)
        self.menuGroups.addAction(self.actionClearGroups)
        self.actionResetGroups = QtWidgets.QAction("Remove all groups", self)
        self.actionResetGroups.triggered.connect(self.triggerEditGroups)
        self.menuGroups.addAction(self.actionResetGroups)

    def setupTableProj(self):
        try:
            # If tableProj already exists, remove it from the layout
            if hasattr(self, "tableProj"):
                self.verticalLayoutProj.removeWidget(self.tableProj)
                sip.delete(self.tableProj)

            # Creates an instance of custom QTableView to allow drag&drop
            self.tableProj = TableProjSub(parent=self)
            self.verticalLayoutProj.addWidget(self.tableProj)
            self.tableProj.setObjectName("tableProj")

            # Set up the table view
            if not hasattr(self, "df_project"):
                self.df_project = df_projectTemplate()
            self.tablemodel = TableModel(self.df_project)
            self.tableProj.setModel(self.tablemodel)

            # Enable sorting on the QTableView
            self.tableProj.setSortingEnabled(True)

            # Connect events
            self.pushButtonParse.pressed.connect(self.triggerParse)
            self.tableProj.setSelectionBehavior(TableProjSub.SelectRows)
            tableProj_selectionModel = self.tableProj.selectionModel()
            tableProj_selectionModel.selectionChanged.connect(
                self.tableProjSelectionChanged
            )
            self.formatTableLayout()
        except Exception as e:
            print(f"Error setting up tableProj: {e}")

    def setupTableStim(self):
        self.tableStimModel = TableModel(pd.DataFrame([uistate.default_dict_t]))
        self.tableStim.setModel(self.tableStimModel)
        self.tableStim.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableStim.verticalHeader().hide()
        tableStim_selectionModel = self.tableStim.selectionModel()
        tableStim_selectionModel.selectionChanged.connect(self.stimSelectionChanged)

    def formatTableLayout(self):
        if config.verbose:
            print("formatTableLayout")

        self.tableProj.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        self.tableProj.verticalHeader().hide()

        df_p = self.df_project
        header = self.tableProj.horizontalHeader()

        # ordered, visible columns
        column_order = [
            "status",
            "recording_name",
            "groups",
            "stims",
            "sweeps",
            "sweep_duration",
        ]
        if uistate.checkBox["paired_stims"]:
            column_order.append("Tx")

        col_indices = [df_p.columns.get_loc(name) for name in column_order]

        # Show/hide columns and set resize behavior
        num_columns = df_p.shape[1]
        for col in range(num_columns):
            if col in col_indices:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
                self.tableProj.setColumnHidden(col, False)
            else:
                self.tableProj.setColumnHidden(col, True)

        self.tableProj.resizeColumnsToContents()

        # Reorder visible columns
        for i, col_index in enumerate(col_indices):
            header.moveSection(header.visualIndex(col_index), i)

    def formatTableStimLayout(self, dft):
        header = self.tableStim.horizontalHeader()
        column_order = [
            "stim",
            "t_stim",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_EPSP_slope_method",
            "t_EPSP_amp",
            "t_EPSP_amp_method",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_volley_slope_method",
            "t_volley_amp",
            "t_volley_amp_method",
        ]
        col_indices = [
            dft.columns.get_loc(col) for col in column_order if col in dft.columns
        ]
        num_columns = dft.shape[1]
        for col in range(num_columns):
            if col in col_indices:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
                self.tableStim.setColumnHidden(col, False)
            else:
                self.tableStim.setColumnHidden(col, True)
        for i, col_index in enumerate(col_indices):
            header.moveSection(header.visualIndex(col_index), i)
        self.tableStim.resizeColumnsToContents()

    def setupFolders(self):
        self.dict_folders = self.build_dict_folders()
        # DEBUG: clear cache and timepoints folders
        if config.clear_cache:
            self.deleteFolder(self.dict_folders["cache"])
        if config.clear_timepoints:
            self.deleteFolder(self.dict_folders["timepoints"])
        if config.clear_project_folder:
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
        for frame, (text, state) in uistate.viewTools.items():
            getattr(self, frame).setVisible(state)
        # TODO:
        # connect paired stim checkbox and flip button to local functions
        # self.checkBox_paired_stims.setChecked(uistate.checkBox['paired_stims'])
        # self.checkBox_paired_stims.stateChanged.connect(lambda state: self.checkBox_paired_stims_changed(state))
        # self.pushButton_paired_data_flip.pressed.connect(self.pushButton_paired_data_flip_pressed)

    def build_dict_folders(self):
        dict_folders = {
            "project": self.projects_folder
            / self.projectname,  # path to project folder
            "data": self.projects_folder
            / self.projectname
            / "data",  # path to project data subfolder
            "timepoints": self.projects_folder
            / self.projectname
            / "timepoints",  # path to project timepoints subfolder
            "cache": self.projects_folder
            / f"cache {config.version}"
            / self.projectname,  # path to project cache subfolder
        }
        return dict_folders

    def connectUIstate(self, disconnect=False):  # ternary (dis)connect of UI elements
        # checkBoxes
        for key, value in uistate.checkBox.items():
            checkBox = getattr(self, f"checkBox_{key}")
            checkBox.stateChanged.disconnect() if disconnect else checkBox.stateChanged.connect(
                lambda state, key=key: self.viewSettingsChanged(key, state)
            )
        # lineEdits
        for lineEdit in [
            self.lineEdit_mean_selection_start,
            self.lineEdit_mean_selection_end,
        ]:
            lineEdit.editingFinished.disconnect() if disconnect else lineEdit.editingFinished.connect(
                lambda le=lineEdit: self.editMeanSelectRange(le)
            )
        for lineEdit in [
            self.lineEdit_sweeps_range_from,
            self.lineEdit_sweeps_range_to,
        ]:
            lineEdit.editingFinished.disconnect() if disconnect else lineEdit.editingFinished.connect(
                lambda le=lineEdit: self.editSweepSelectRange(le)
            )
        for lineEdit in [
            self.lineEdit_norm_EPSP_start,
            self.lineEdit_norm_EPSP_end,
        ]:
            lineEdit.editingFinished.disconnect() if disconnect else lineEdit.editingFinished.connect(
                lambda le=lineEdit: self.editNormRange(le)
            )
        for lineEdit in [
            self.lineEdit_EPSP_amp_halfwidth,
            self.lineEdit_volley_amp_halfwidth,
        ]:
            lineEdit.editingFinished.disconnect() if disconnect else lineEdit.editingFinished.connect(
                lambda le=lineEdit: self.editAmpHalfwidth(le)
            )
        for lineEdit in [
            self.lineEdit_bin_size,
        ]:
            lineEdit.editingFinished.disconnect() if disconnect else lineEdit.editingFinished.connect(
                lambda le=lineEdit: self.editBinSize(le)
            )

        # pushButtons
        for str_button, str_function in uistate.pushButtons.items():
            button, func = getattr(self, str_button), getattr(self, str_function)
            button.pressed.disconnect() if disconnect else button.pressed.connect(func)
        # SplitterMoved
        for splitter_name in ["h_splitterMaster", "v_splitterGraphs"]:
            splitter = getattr(self, splitter_name)
            splitter.splitterMoved.disconnect() if disconnect else splitter.splitterMoved.connect(
                self.onSplitterMoved
            )

    def applyConfigStates(self):
        # Disconnect signals to prevent editingFinished from triggering from .setText
        self.connectUIstate(disconnect=True)

        for key, value in uistate.checkBox.items():
            checkBox = getattr(self, f"checkBox_{key}")
            checkBox.setChecked(value)
        norm = uistate.checkBox["norm_EPSP"]
        self.label_norm_on_sweep.setVisible(norm)
        self.label_relative_to.setVisible(norm)
        self.lineEdit_norm_EPSP_start.setVisible(norm)
        self.lineEdit_norm_EPSP_end.setVisible(norm)
        self.lineEdit_norm_EPSP_start.setText(f"{uistate.lineEdit['norm_EPSP_from']}")
        self.lineEdit_norm_EPSP_end.setText(f"{uistate.lineEdit['norm_EPSP_to']}")
        self.lineEdit_EPSP_amp_halfwidth.setText(
            f"{uistate.lineEdit['EPSP_amp_halfwidth_ms']}"
        )
        self.lineEdit_volley_amp_halfwidth.setText(
            f"{uistate.lineEdit['volley_amp_halfwidth_ms']}"
        )

        # apply splitter proportions from project config
        self.setSplitterSizes("h_splitterMaster", "v_splitterGraphs")
        self.connectUIstate()

    # trigger functions TODO: break out the big ones to separate functions!

    def groupCheckboxChanged(self, state, group_ID):
        if config.verbose:
            print(f"groupCheckboxChanged: {str(group_ID)} = {state}")
        self.dd_groups[group_ID]["show"] = state == 2
        self.group_save_dd()
        self.update_show()
        self.mouseoverUpdate()

    def checkBox_paired_stims_changed(self, state):
        self.usage("checkBox_paired_stims_changed")
        uistate.checkBox["paired_stims"] = bool(state)
        print(f"checkBox_paired_stims_changed: {uistate.checkBox['paired_stims']}")
        # TODO: reconnect this

    def trigger_export_selection(self):
        self.usage("trigger_export_selection - DEPRECATED")
        # self.export_selection()

    def trigger_export_groups(self):
        self.usage("trigger_export_groups - DEPRECATED")
        # self.export_groups()

    def triggerGroupRename(self, group_ID):
        self.usage("triggerGroupRename")
        RenameDialog = InputDialogPopup()
        new_group_name = RenameDialog.showInputDialog(title="Rename group", query="")
        self.group_rename(group_ID, new_group_name)

    def triggerStimDetect(self):
        self.usage("triggerStimDetect")
        self.stimDetect()

    def trigger_set_sweeps_even(self):
        self.usage(f"trigger_set_sweeps_even")
        self.sweepsSelect(even=True)

    def trigger_set_sweeps_odd(self):
        self.usage(f"trigger_set_sweeps_odd")
        self.sweepsSelect(even=False)

    def trigger_set_EPSP_amp_width_all(self):
        self.usage(f"trigger_set_EPSP_amp_width_all")
        self.recalculate()

    def trigger_set_volley_amp_width_all(self):
        self.usage(f"trigger_set_volley_amp_width_all")
        self.recalculate()

    def trigger_set_norm_range_all(self):
        self.usage(f"trigger_set_norm_range_all")
        self.recalculate()

    def trigger_set_bin_size_all(self):
        self.usage(f"trigger_set_bin_size_all")
        uistate.checkBox["bin"] = True
        self.recalculate()

    def triggerRefresh(self):
        self.usage(f"refresh graphs")
        selection = uistate.list_idx_select_recs
        self.tableProj.clearSelection()
        self.recalculate()
        uistate.list_idx_select_recs = selection
        self.tableUpdate()
        self.tableProjSelectionChanged()

    def triggerDarkmode(self):
        uistate.darkmode = not uistate.darkmode
        self.usage(f"triggerDarkmode set to {uistate.darkmode}")
        self.write_bw_cfg()
        self.darkmode()

    def triggerShowHeatmap(self):
        self.usage("triggerShowHeatmap")
        self.toggleHeatmap()

    def triggerShowTimetable(self):
        self.usage("triggerShowTimetable")
        uistate.showTimetable = not uistate.showTimetable
        if uistate.dict_rec_show:
            self.tableProjSelectionChanged()
        self.write_bw_cfg()
        self.setTableStimVisibility(uistate.showTimetable)

    def triggerCopyTimepoints(self):
        self.usage("triggerCopyTimepoints")
        self.copy_dft()

    def triggerCopyOutput(self):
        self.usage("triggerCopyOutput")
        self.copy_output()

    def pushButton_paired_data_flip_pressed(self):
        self.usage("pushButton_paired_data_flip_pressed")
        self.flipCI()

    def triggerRenameRecording(self):
        self.usage("triggerRenameRecording")
        self.renameRecording()

    def triggerClearGroups(self):
        self.usage("triggerClearGroups")
        if uistate.list_idx_select_recs:
            self.clearGroupsByRow(uistate.list_idx_select_recs)
            self.tableUpdate()
            self.mouseoverUpdate()
        else:
            print("No files selected.")

    def triggerEditGroups(self):  # Open groups UI (not built)
        self.usage("triggerEditGroups")
        # Placeholder: For now, delete all buttons and groups
        self.group_controls_remove()
        self.group_remove()
        self.tableUpdate()
        self.mouseoverUpdate()

    def triggerNewGroup(self):
        self.usage("triggerNewGroup")
        self.group_new()

    def triggerRemoveLastGroup(self):
        self.usage("triggerRemoveLastGroup")
        self.group_remove_last()

    def triggerRemoveLastEmptyGroup(self):
        self.usage("triggerRemoveLastEmptyGroup")
        self.group_remove_last_empty()

    def triggerDelete(self):
        self.usage("triggerDelete")
        self.deleteSelectedRows()

    def triggerRenameProject(self):  # renameProject
        self.usage("triggerRenameProject")
        self.inputProjectName.setReadOnly(False)
        self.inputProjectName.selectAll()  # Select all text
        self.inputProjectName.setFocus()  # Set focus
        try:  # Only disconnect if connected
            self.inputProjectName.editingFinished.disconnect()
        except TypeError:
            pass  # Ignore the TypeError that is raised when the signal isn't connected to any slots
        finally:
            self.inputProjectName.editingFinished.connect(self.renameProject)

    def triggerNewProject(self):
        self.usage("triggerNewProject")
        self.newProject()

    def triggerOpenProject(self):  # open folder selector dialog
        self.usage("triggerOpenProject")
        self.dialog = QtWidgets.QDialog()
        print(f"self.projects_folder: {self.projects_folder}")
        str_projectfolder = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self.dialog,
                "Open Directory",
                str(self.projects_folder),
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks
                | QtWidgets.QFileDialog.DontUseNativeDialog,
            )
        )
        if config.verbose:
            print(f"Received projectfolder: {str_projectfolder}")
        projectpath = Path(str_projectfolder) / "project.brainwash"
        if projectpath.exists():
            if config.verbose:
                print(f"Found project {str_projectfolder}, loading...")
            self.openProject(str_projectfolder)
        else:
            print(f"No project found in {str_projectfolder}")

    def triggerAddData(self):  # creates file tree for file selection
        self.usage("triggerAddData")
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.show()

    def triggerParse(self):  # parse non-parsed files and folders in self.df_project
        self.usage("triggerParse")
        self.mouseoverDisconnect()
        self.parseData()
        self.setButtonParse()

    def triggerReanalyze(self):
        self.usage("triggerReanalyze")
        selection = uistate.list_idx_select_recs
        self.reanalyze_recordings()
        self.tableProj.clearSelection()
        uistate.list_idx_select_recs = selection
        self.tableUpdate()
        self.tableProjSelectionChanged()

    def triggerKeepSelectedSweeps(self):
        self.usage("triggerKeepSelectedSweeps")
        self.sweep_keep_selected()

    def triggerRemoveSelectedSweeps(self):
        self.usage("triggerRemoveSelectedSweeps")
        self.sweep_remove_selected()

    def triggerSplitBySelectedSweeps(self):
        self.usage("triggerSplitBySelectedSweeps")
        self.sweep_split_by_selected()

    # Data Editing functions
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

    def reanalyze_recordings(self):
        self.usage("reanalyze_recordings")
        n_recs = len(uistate.list_idx_select_recs)
        print(f"Reanalyzing {n_recs} selected recording{'s' if n_recs != 1 else ''}...")
        # purge df timepoints and cache for selected recordings
        for rec_idx in uistate.list_idx_select_recs:
            p_row = self.df_project.iloc[rec_idx]
            rec_name = p_row["recording_name"]
            # delete timepoints file
            timepoints_file = self.dict_folders["timepoints"] / (rec_name + ".parquet")
            if timepoints_file.exists():
                timepoints_file.unlink()
                if config.verbose:
                    print(f"Deleted timepoints file: {timepoints_file}")
            # delete cached output file
            cache_file = self.dict_folders["cache"] / (rec_name + "_output.parquet")
            if cache_file.exists():
                cache_file.unlink()
                if config.verbose:
                    print(f"Deleted cached output file: {cache_file}")
            self.set_rec_status(rec_name)
        self.resetCacheDicts()
        self.recalculate()  # outputs, binning, group handling

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

    def duplicate_recording(self, source_p_row, new_name=None):
        source_name = source_p_row["recording_name"]
        if new_name is None:
            new_name = f"{source_name}_copy"
        if new_name in self.df_project["recording_name"].values:
            print(
                f"duplicate_recording: recording name '{new_name}' already exists, choose a different name."
            )
            return
        df_proj_new_row = source_p_row.copy()
        df_proj_new_row["ID"] = str(uuid.uuid4())  # new unique ID
        df_proj_new_row["recording_name"] = new_name
        # Update data files: copy source data file to new data file
        df_project = self.get_df_project()
        self.df_project = pd.concat(
            [df_project, pd.DataFrame([df_proj_new_row])], ignore_index=True
        )
        self.save_df_project()
        df_data = self.get_dfdata(source_p_row)
        self.df2file(df_data, new_name, key="data")  # persist data file
        dfmean, i_stim = parse.build_dfmean(df_data)
        self.df2file(dfmean, new_name, key="mean")  # persist mean
        df = parse.zeroSweeps(df_data, i_stim=i_stim)
        self.df2file(df, new_name, key="filter")  # persist zeroed
        return

    def create_recording(self, df_proj_row, rec, df_raw):
        def create_row(df_proj_row, new_name, dict_meta):
            df_proj_new_row = df_proj_row.copy()
            df_proj_new_row["ID"] = str(uuid.uuid4())
            df_proj_new_row["status"] = "Read"
            df_proj_new_row["recording_name"] = new_name
            df_proj_new_row["sweeps"] = dict_meta.get("nsweeps", None)
            df_proj_new_row["channel"] = ""  # dict_meta.get('channel', None)
            df_proj_new_row["stim"] = ""  # dict_meta.get('stim', None)
            df_proj_new_row["sweep_duration"] = dict_meta.get("sweep_duration", None)
            df_proj_new_row["resets"] = ""  # dict_meta.get('resets', None)
            return df_proj_new_row

        self.df2file(df_raw, rec, key="data")  # persist raws
        dfmean, i_stim = parse.build_dfmean(df_raw)
        self.df2file(dfmean, rec, key="mean")  # persist mean
        df = parse.zeroSweeps(df_raw, i_stim=i_stim)
        self.df2file(df, rec, key="filter")  # persist zeroed
        dict_meta = parse.metadata(df)  # extract metadata
        # TODO: create unique recording names
        df_proj_new_row = create_row(
            df_proj_row=df_proj_row, new_name=rec, dict_meta=dict_meta
        )
        return df_proj_new_row

    def recalculate(self):
        # Placeholder function called when output must be recalculated: normalization changed, binning changed, amp halfwidth changed
        # For now, it recalculates ALL outputs, triggered by any "set All" button
        # TODO: make a (default) version that only affects selected recordings
        self.usage("recalculate")
        self.uiFreeze()

        norm_from = uistate.lineEdit["norm_EPSP_from"]
        norm_to = uistate.lineEdit["norm_EPSP_to"]
        EPSP_amp_halfwidth_ms = uistate.lineEdit["EPSP_amp_halfwidth_ms"]
        volley_amp_halfwidth_ms = uistate.lineEdit["volley_amp_halfwidth_ms"]
        dt = uistate.default_dict_t
        dt["t_EPSP_amp_halfwidth"] = EPSP_amp_halfwidth_ms / 1000  # convert to seconds
        dt["t_volley_amp_halfwidth"] = (
            volley_amp_halfwidth_ms / 1000
        )  # convert to seconds
        dt["norm_output_from"] = norm_from
        dt["norm_output_to"] = norm_to
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

        binSweeps = uistate.checkBox["bin"]
        bin_size = uistate.lineEdit["bin_size"]
        if binSweeps:
            print(f"binSweeps: {binSweeps}, bin_size: {bin_size}")
        uiplot.exterminate()
        df_p = self.get_df_project()
        for _, p_row in df_p.iterrows():
            rec = p_row["recording_name"]
            df_t = self.get_dft(p_row)
            df_t["t_EPSP_amp_halfwidth"] = dt["t_EPSP_amp_halfwidth"]
            df_t["t_volley_amp_halfwidth"] = dt["t_volley_amp_halfwidth"]
            df_t["norm_output_from"] = dt["norm_output_from"]
            df_t["norm_output_to"] = dt["norm_output_to"]
            self.set_dft(rec, df_t)
            if binSweeps:
                dfbin = self.get_dfbin(p_row)
                print(dfbin)
            dfoutput = self.get_dfoutput(p_row, reset=True)
            self.persistOutput(rec, dfoutput)
            uiplot.addRow(p_row, df_t, self.get_dfmean(p_row), dfoutput)
        self.tableFormat()

        # group handling
        self.group_cache_purge()
        # TODO: rest of group handling

        # uistate.dfv = None
        uiplot.hideAll()
        self.update_show(reset=True)
        self.mouseoverUpdate()
        self.uiThaw()

    def editAmpHalfwidth(self, lineEdit):
        lineEditName = lineEdit.objectName()
        self.usage(f"editAmpHalfwidth {lineEditName}")
        try:
            num = max(0, float(lineEdit.text()))
        except ValueError:
            num = 0
        lineEdit.setText(str(num))
        if lineEditName == "lineEdit_EPSP_amp_halfwidth":
            uistate.lineEdit["EPSP_amp_halfwidth_ms"] = num
        elif lineEditName == "lineEdit_volley_amp_halfwidth":
            uistate.lineEdit["volley_amp_halfwidth_ms"] = num

    def editSort(self, lineEdit, start, end, request="int"):
        def str2num(text):
            try:
                if request == "float":
                    return max(0, float(text))
                else:
                    return max(0, int(text))
            except ValueError:
                return 0

        def num2str(num):
            if request == "float":
                return str(max(0, float(num)))
            else:
                return str(max(0, int(num)))

        num = str2num(lineEdit.text())
        if lineEdit.objectName() == start.objectName():
            pair = str2num(end.text())
        else:
            pair = str2num(start.text())
        low, high = min(num, pair), max(num, pair)
        start.setText(num2str(low))
        end.setText(num2str(high))
        return low, high

    def editMeanSelectRange(self, lineEdit):
        self.usage("editMeanSelectRange")
        low, high = self.editSort(
            lineEdit,
            start=self.lineEdit_mean_selection_start,
            end=self.lineEdit_mean_selection_end,
            request="float",
        )
        uistate.x_select["mean_start"], uistate.x_select["mean_end"] = low, high
        uiplot.xSelect(uistate.axm.figure.canvas)

    def editSweepSelectRange(self, lineEdit):
        self.usage("editSweepSelectRange")
        low, high = self.editSort(
            lineEdit,
            start=self.lineEdit_sweeps_range_from,
            end=self.lineEdit_sweeps_range_to,
        )
        uistate.x_select["output_start"], uistate.x_select["output_end"] = low, high
        uistate.x_select["output"] = set(range(low, high + 1))
        uiplot.xSelect(uistate.ax1.figure.canvas)
        uiplot.update_axe_mean()

    def editNormRange(self, lineEdit):
        self.usage("editNormRange")
        _ = self.editSort(
            lineEdit,
            start=self.lineEdit_norm_EPSP_start,
            end=self.lineEdit_norm_EPSP_end,
        )
        # TODO: show selection on graph

    def editBinSize(self, lineEdit):
        self.usage("editBinSize")
        try:
            num = max(2, int(lineEdit.text()))
        except ValueError:
            num = 10
        lineEdit.setText(str(num))
        uistate.lineEdit["bin_size"] = num
        print(f"editBinSize: {num}")
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def copy_dft(self):
        # get selected dft(s) and copy to clipboard
        if len(uistate.list_idx_select_recs) < 1:
            print("copy_dft: nothing selected.")
            return
        selected_dfts = pd.DataFrame()
        for rec in uistate.list_idx_select_recs:
            p_row = self.get_df_project().loc[rec]
            dft = self.get_dft(p_row)
            dft.insert(0, "recording_name", p_row["recording_name"])
            selected_dfts = pd.concat([selected_dfts, dft], ignore_index=True)
        selected_dfts.to_clipboard(index=False)

    def copy_output(self):
        if len(uistate.list_idx_select_recs) < 1:
            print("copy_output: nothing selected.")
            return
        selected_outputs = pd.DataFrame()
        for rec in uistate.list_idx_select_recs:
            p_row = self.get_df_project().loc[rec]
            output = self.get_dfoutput(p_row)
            output.insert(0, "recording_name", p_row["recording_name"])
            selected_outputs = pd.concat([selected_outputs, output], ignore_index=True)
        selected_outputs.to_clipboard(index=False)

    def stimDetect(self):
        if not uistate.list_idx_select_recs:
            print("No files selected.")
            return
        df_p = self.get_df_project()
        for index in uistate.list_idx_select_recs:
            p_row = df_p.loc[index]
            old_df_t = self.get_dft(p_row)
            rec_name = p_row["recording_name"]
            rec_ID = p_row["ID"]
            stims = p_row["stims"]
            if p_row["sweeps"] == "...":
                print(f"{rec_name} not parsed yet.")
                continue
            print(f"Detecting stims for {rec_name}")
            if uistate.x_select["mean_start"] is not None:
                print(
                    f" - range: {uistate.x_select['mean_start']} to {uistate.x_select['mean_end']}"
                )
            dfmean = self.get_dfmean(p_row)
            if (
                uistate.x_select["mean_start"] is not None
                and uistate.x_select["mean_end"] is not None
            ):
                dfmean_range = dfmean[
                    (dfmean["time"] >= uistate.x_select["mean_start"])
                    & (dfmean["time"] <= uistate.x_select["mean_end"])
                ].reset_index(drop=True)
            else:
                dfmean_range = dfmean
            default_dict_t = uistate.default_dict_t.copy()  # Default sizes
            print(
                f"stimDetect: {rec_name} calling find_events within range:\n{uistate.x_select}"
            )
            new_df_t = analysis.find_events(
                dfmean=dfmean_range, default_dict_t=default_dict_t, verbose=False
            )
            if new_df_t is None:
                print(f"StimDetect: No stims found for {rec_name}.")
                continue
            if uistate.checkBox["timepoints_per_stim"] or stims == 1:
                self.set_dft(rec_name, new_df_t)
            else:
                dfoutput = self.get_dfoutput(p_row)
                print(
                    f"stimDetect: {rec_name} calling set_uniformTimepoints with df_t:\n{new_df_t}"
                )
                # list_obsolete_stim_idx: a list of idx of old_df_t rows, that have a t_stim that isn't in new_df_t
                list_obsolete_stim_idx = [
                    i
                    for i, row in old_df_t.iterrows()
                    if row["t_stim"] not in new_df_t["t_stim"].values
                ]
                if list_obsolete_stim_idx:
                    print(f"Obsolete stims: {list_obsolete_stim_idx}")
                    for idx in list_obsolete_stim_idx:
                        dfoutput = dfoutput.drop(idx)
                        print(f" - removed idx {idx} from dfoutput")
                    dfoutput = dfoutput.reset_index(drop=True)
                    dfoutput["stim"] = new_df_t["stim"]
                self.set_uniformTimepoints(p_row=p_row, dft=new_df_t, dfoutput=dfoutput)
            df_p.loc[p_row["ID"] == df_p["ID"], "stims"] = len(new_df_t)
            self.set_df_project(df_p)
            uiplot.unPlot(rec_ID)
            dfoutput = self.get_dfoutput(p_row)
            self.persistOutput(p_row["recording_name"], dfoutput)
            uiplot.addRow(p_row, new_df_t, dfmean, dfoutput)
        uistate.list_idx_select_stims = [0]
        p_row = df_p.loc[uistate.list_idx_select_recs[0]]
        df_t = self.get_dft(p_row)
        self.tableStimModel.setData(df_t)
        self.tableStim.selectRow(0)
        # unplot and replot all affected recordings
        self.update_show(reset=True)
        self.mouseoverUpdate()

    def addData(self, dfAdd):  # concatenate dataframes of old and new data
        # Check for unique names in dfAdd, vs df_p and dfAdd
        # Adds (<lowest integer that makes unique>) to the end of non-unique recording_names
        df_p = self.get_df_project()
        list_recording_names = set(df_p["recording_name"])
        for index, row in dfAdd.iterrows():
            check_recording_name = row["recording_name"]
            if check_recording_name.endswith("_mean.parquet"):
                print(
                    "recording_name must not end with _mean.parquet - appending _X"
                )  # must not collide with internal naming
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
        self.set_df_project(df_p)
        self.tableFormat()
        if config.verbose:
            print("addData:", self.get_df_project())

    def renameRecording(self):
        # renames all instances of selected recording_name in df_project, and their associated files
        if len(uistate.list_idx_select_recs) != 1:
            print("Rename: please select one row only for renaming.")
            return
        df_p = self.get_df_project()
        old_recording_name = df_p.at[uistate.list_idx_select_recs[0], "recording_name"]
        RenameDialog = InputDialogPopup()
        new_recording_name = RenameDialog.showInputDialog(
            title="Rename recording", query=old_recording_name
        )
        # check if the new name is a valid filename
        if (
            new_recording_name is not None
            and re.match(r"^[a-zA-Z0-9_ -]+$", str(new_recording_name)) is not None
        ):
            list_recording_names = set(df_p["recording_name"])
            if not new_recording_name in list_recording_names:  # prevent duplicates
                self.rename_files_by_rec_name(
                    old_name=old_recording_name, new_name=new_recording_name
                )
                df_p.at[uistate.list_idx_select_recs[0], "recording_name"] = (
                    new_recording_name
                )
                # For paired recordings: also rename any references to old_recording_name in df_p['paired_recording']
                df_p.loc[
                    df_p["paired_recording"] == old_recording_name, "paired_recording"
                ] = new_recording_name
                self.set_df_project(df_p)
                self.tableUpdate()
                self.update_recs2plot()
                old_recording_ID = df_p.at[uistate.list_idx_select_recs[0], "ID"]
                uiplot.unPlot(old_recording_ID)
                self.graphUpdate(row=df_p.loc[uistate.list_idx_select_recs[0]])
                self.update_show(reset=True)
            else:
                print(f"new_recording_name {new_recording_name} already exists")
        else:
            print(f"new_recording_name {new_recording_name} is not a valid filename")

    def rename_files_by_rec_name(self, old_name, new_name):
        for folder_name, file_suffix in [
            ("data", ".parquet"),
            ("timepoints", ".parquet"),
            ("cache", "_mean.parquet"),
            ("cache", "_filter.parquet"),
            ("cache", "_bin.parquet"),
            ("cache", "_output.parquet"),
        ]:
            old_file_path = Path(
                self.dict_folders[folder_name] / (old_name + file_suffix)
            )
            new_file_path = Path(
                self.dict_folders[folder_name] / (new_name + file_suffix)
            )
            if old_file_path.exists():
                old_file_path.rename(new_file_path)
            elif folder_name == "data":
                print(f"recording_rename_files: file not found: {old_file_path}")
                raise FileNotFoundError

    def deleteSelectedRows(self):
        if not uistate.list_idx_select_recs:
            print("No files selected.")
            return
        df_p = self.get_df_project()
        for index in uistate.list_idx_select_recs:
            rec_name = df_p.at[index, "recording_name"]
            rec_ID = df_p.at[index, "ID"]
            sweeps = df_p.at[index, "sweeps"]
            if sweeps != "...":  # if the file is parsed:
                print(f"Deleting {rec_name}...")
                self.purgeRecordingData(rec_ID, rec_name)
                # this also purges group cache and unplots the group
                uiplot.unPlot(rec_ID)  # remove plotted lines
        # store the ID of the line below the last selected row
        reselect_ID = None
        if uistate.list_idx_select_recs[-1] < (len(df_p) - 1):
            reselect_ID = df_p.at[uistate.list_idx_select_recs[-1] + 1, "ID"]
        df_p.drop(uistate.list_idx_select_recs, inplace=True)
        df_p.reset_index(inplace=True, drop=True)
        self.set_df_project(df_p)
        self.tableUpdate()
        # reselect the line below the last selected row
        if reselect_ID is not None:
            uistate.list_idx_select_recs = [df_p[df_p["ID"] == reselect_ID].index[0]]
        self.tableProjSelectionChanged()

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
        if (
            groups2purge
        ):  # if rec_ID is in groups, purge those group caches and update dd_groups
            # print(f"purgeRecordingData: {rec_name} in groups: {groups2purge}")
            for (
                group_ID
            ) in groups2purge:  # remove rec_ID from rec_IDs of all affected groups
                print(f"purgeRecordingData: pre  {self.dd_groups[group_ID]['rec_IDs']}")
                self.dd_groups[group_ID]["rec_IDs"].remove(rec_ID)
                print(f"purgeRecordingData: post {self.dd_groups[group_ID]['rec_IDs']}")
            self.group_save_dd()
            self.group_cache_purge(groups2purge)
        # clear recording caches
        for cache_name in [
            "dict_datas",
            "dict_means",
            "dict_filters",
            "dict_ts",
            "dict_bins",
            "dict_outputs",
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
        self.uiFreeze()  # Thawed at the end of graphPreload()
        # Clean up any existing thread before starting a new one
        self._cleanup_threads()
        df_p = self.get_df_project()
        df_p_to_update = df_p[df_p["sweeps"] == "..."].copy()
        if len(df_p_to_update) > 0:
            print(f"parseData: {len(df_p_to_update)} files to parse.")
            thread = ParseDataThread(df_p_to_update, self.dict_folders)
            self._current_parse_thread = thread  # Store reference for use in callbacks
            thread.progress.connect(self.updateProgressBar)
            thread.finished.connect(self.onParseDataFinished)
            thread.finished.connect(thread.deleteLater)  # Auto-cleanup when done
            thread.finished.connect(
                lambda: (
                    self._threads.remove(thread) if thread in self._threads else None
                )
            )
            thread.finished.connect(
                lambda: setattr(self, "_current_parse_thread", None)
            )
            self._threads.append(thread)
            thread.start()
            self.progressBarManager = ProgressBarManager(
                self.progressBar, len(df_p_to_update)
            )
            self.progressBarManager.__enter__()

    def updateProgressBar(self, i):
        self.progressBarManager.update(i, "Parsing file ")

    def onParseDataFinished(self):
        print("onParseDataFinished: entered")
        self.progressBarManager.__exit__(None, None, None)
        if (
            hasattr(self, "_current_parse_thread")
            and self._current_parse_thread is not None
        ):
            thread = self._current_parse_thread
            if thread.rows:
                rows2add = pd.concat(thread.rows, axis=1).transpose()
                df_p = self.get_df_project()
                df_p = pd.concat([df_p[df_p["sweeps"] != "..."], rows2add]).reset_index(
                    drop=True
                )
                self.set_df_project(df_p)
                # Get the indices of the new rows, as they are in df_p
                uistate.list_idx_recs2preload = df_p.index[
                    df_p.index >= len(df_p) - len(rows2add)
                ].tolist()
        self.progressBarManager.__exit__(None, None, None)
        print("onParseDataFinished: calling graphPreload")
        self.graphPreload()

    def flipCI(self):
        # Inverse Control/Intervention flags of currently selected and paired recordings
        if uistate.list_idx_select_recs:
            df_p = self.get_df_project()
            already_flipped = []
            for index in uistate.list_idx_select_recs:
                row = df_p.loc[index]
                name_rec = row["recording_name"]
                name_pair = row["paired_recording"]
                index_pair = df_p[df_p["recording_name"] == name_pair].index[0]
                if index in already_flipped:
                    print(f"Already flipped {index}")
                    continue
                # if row_pair doesn't exist:
                if pd.isna(name_pair):
                    print(f"{name_rec} has no paired recording.")
                    return
                print(f"Flipping C-I for {name_rec} and {name_pair}...")
                df_p.at[index, "Tx"] = not df_p.at[index, "Tx"]
                df_p.at[index_pair, "Tx"] = not df_p.at[index, "Tx"]
                # clear caches and diff files
                key_pair = name_rec[:-2]
                self.dict_diffs.pop(key_pair, None)
                path_diff = Path(
                    f"{self.dict_folders['cache']}/{key_pair}_diff.parquet"
                )
                if path_diff.exists():
                    path_diff.unlink()
                # TODO: clear group cache
                already_flipped.append(index_pair)
                self.set_df_project(df_p)
                self.tableUpdate()
            self.mouseoverUpdate()
        else:
            print("No files selected.")

    # Data Group handling functions

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

    def get_groupsOfRec(
        self, rec_ID
    ):  # returns a set of all 'group ID' that have rec_ID in their 'rec_IDs' list
        return list(
            [key for key, value in self.dd_groups.items() if rec_ID in value["rec_IDs"]]
        )

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
        elif (
            re.match(r"^[a-zA-Z0-9_ -]+$", str(new_group_name)) is not None
        ):  # True if valid filename
            self.dd_groups[group_ID]["group_name"] = new_group_name
            self.group_save_dd()
            self.groupControlsRefresh()
        else:
            print(f"Group name {new_group_name} is not a valid name.")

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
        selected_rec_IDs = dfp.loc[
            uistate.list_idx_select_recs, "ID"
        ].tolist()  # selected rec_IDs
        all_in_group = all(
            rec_ID in self.dd_groups[group_ID]["rec_IDs"] for rec_ID in selected_rec_IDs
        )
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

    def group_cache_purge(
        self, group_IDs=None
    ):  # clear cache so that a new group mean is calculated
        if not self.dict_group_means:
            print("No groups to purge.")
            return
        if not group_IDs:  # if no group IDs are passed purge all groups
            group_IDs = list(self.dict_group_means.keys())
        print(f"group_cache_purge: {group_IDs}, len(group): {len(group_IDs)}")
        for group_ID in group_IDs:
            if group_ID in self.dict_group_means:
                del self.dict_group_means[group_ID]
            path_group_mean_cache = Path(
                f"{self.dict_folders['cache']}/group_{group_ID}_mean.parquet"
            )
            if (
                path_group_mean_cache.exists
            ):  # TODO: Upon adding a group, both of these conditions trigger. How?
                print(f"{path_group_mean_cache} found when checking for existence...")
                try:
                    path_group_mean_cache.unlink()
                    print("...and was successfully unlinked.")
                except FileNotFoundError:
                    print("...but NOT when attempting to unlink.")
            uiplot.unPlotGroup(group_ID)
            if group_ID in self.dd_groups and self.dd_groups[group_ID]["rec_IDs"]:
                uiplot.addGroup(
                    group_ID, self.dd_groups[group_ID], self.get_dfgroupmean(group_ID)
                )

    def group_controls_add(
        self, group_ID
    ):  # Create menu for adding to group and checkbox for showing group
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
        self.new_group_menu_item.triggered.connect(
            lambda checked, add_group_ID=group_ID: self.group_selection(add_group_ID)
        )
        self.new_group_menu_item.setShortcut(f"{str_ID}")
        self.menuGroups.addAction(self.new_group_menu_item)
        self.new_checkbox = CustomCheckBox(group_ID)
        self.new_checkbox.rightClicked.connect(
            self.triggerGroupRename
        )  # str_ID is passed by CustomCheckBox
        self.new_checkbox.setObjectName(f"checkBox_group_{str_ID}")
        self.new_checkbox.setText(f"{str_ID}. {group_name}")
        self.new_checkbox.setStyleSheet(
            f"background-color: {color};"
        )  # Set the background color
        self.new_checkbox.setMaximumWidth(100)  # Set the maximum width
        self.new_checkbox.setChecked(bool(dict_group["show"]))
        self.new_checkbox.stateChanged.connect(
            lambda state, group_ID=group_ID: self.groupCheckboxChanged(state, group_ID)
        )
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
                df_p.loc[df_p["ID"] == rec_ID, "groups"] = (
                    ", ".join(sorted(list_rec_in_groups)) if list_rec_in_groups else " "
                )
            else:
                for i, row in df_p.iterrows():
                    rec_ID = row["ID"]
                    list_rec_in_groups = group_list(rec_ID)
                    df_p.at[i, "groups"] = (
                        ", ".join(sorted(list_rec_in_groups))
                        if list_rec_in_groups
                        else " "
                    )
        self.set_df_project(df_p)
        self.tableFormat()

    # Writer functions

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
            self.bw_cfg_yaml = None  # Make sure it’s defined for consistency

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

    # Project functions

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
        # self.dict_folders['project'].mkdir(exist_ok=True)
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

    # Project dataframe handling

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
                    if config.verbose:
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
        self.tableUpdate()

    # Timepoints dataframe handling

    def set_dft(self, rec_name, df):  # persists df and saves it as a file
        # print(f"type: {type(df)}")
        print(f"set_dft of {rec_name}: {df}")
        self.dict_ts[rec_name] = df
        self.df2file(df=df, rec=rec_name, key="timepoints")

    # Table handling

    def setButtonParse(self):
        if config.verbose:
            print("setButtonParse")
        unparsed = self.df_project["sweeps"].eq("...").any()
        self.pushButtonParse.setVisible(bool(unparsed))
        if config.hide_experimental:
            self.checkBox_force1stim.setVisible(False)
        else:
            self.checkBox_force1stim.setVisible(bool(unparsed))

    def checkBox_force1stim_changed(self, state):
        uistate.checkBox["force1stim"] = state == 2
        if config.verbose:
            print(f"checkBox_force1stim_changed: {state}")

    def checkBox_output_per_stim_changed(self, state):
        uistate.checkBox["output_per_stim"] = state == 2
        print(f"checkBox_output_per_stim_changed: {state}")
        self.uiFreeze()
        df_p = self.get_df_project()
        for i, p_row in df_p.iterrows():
            dfoutput = self.get_dfoutput(p_row, reset=True)
            self.persistOutput(p_row["recording_name"], dfoutput)
            uiplot.unPlot(p_row["ID"])
            df_t = self.get_dft(p_row)
            dfmean = self.get_dfmean(p_row)
            uiplot.addRow(p_row=p_row, dft=df_t, dfmean=dfmean, dfoutput=dfoutput)
            self.update_show(reset=True)
        self.uiThaw()
        self.zoomAuto()

    def checkBox_timepoints_per_stim_changed(self, state):
        uistate.checkBox["timepoints_per_stim"] = state == 2
        print(f"checkBox_timepoints_per_stim_changed: {state}")
        if state == 0:
            self.set_uniformTimepoints()

    def checkBox_bin_changed(self, state):
        uistate.checkBox["bin"] = state == 2
        print(f"checkBox_bin_changed: {state}")
        if state == 2:
            self.binSweeps()

    def tableFormat(self):
        if config.verbose:
            print("tableFormat")
        selected_rows = self.tableProj.selectionModel().selectedRows()
        # Update data
        self.tablemodel.setData(self.get_df_project())
        # Restore selection
        selection = QtCore.QItemSelection()
        for index in selected_rows:
            selection.select(index, index)
        self.tableProj.selectionModel().select(
            selection,
            QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
        )
        self.setButtonParse()

    def tableUpdate(self):
        self.updating_tableProj = True  # prevent tableProjSelectionChanged from firing
        # Update data
        df_project = self.get_df_project()
        self.tablemodel.setData(df_project)
        self.tableProj.resizeColumnsToContents()
        # Restore selection
        selection_model = self.tableProj.selectionModel()
        for idx in uistate.list_idx_select_recs:
            index = self.tablemodel.index(idx, 0)  # get the QModelIndex for the row
            selection_model.select(
                index,
                QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
            )
            # print(f"tableUpdate: reselecting {len(uistate.list_idx_select_recs)}: {idx}")
        self.updating_tableProj = False

    # Internal dataframe handling
    def get_prow(self, dfp_idx=None):
        # returns the selected row with the lowest index in df_project
        if dfp_idx is not None:
            dfp = self.get_df_project()
            row = dfp.loc[dfp_idx]
            return row
        if not uistate.list_idx_select_recs:
            print("get_prow: No recording selected.")
            return None
        dfp = self.get_df_project()
        row = dfp.loc[uistate.list_idx_select_recs[0]]
        return row

    def get_trow(self, dfp_idx=None):
        if dfp_idx is not None:
            dft = self.get_dft(self.get_prow(dfp_idx))
        else:
            if not uistate.list_idx_select_stims:
                print("get_trow: No stim selected.")
                return None
            dft = self.get_dft(self.get_prow())
        if dft is None or len(dft) == 0:
            print("get_trow: Empty dataframe.")
            return None
        # ensure index is valid
        idx = uistate.list_idx_select_stims[0] if uistate.list_idx_select_stims else 0
        if idx < 0 or idx >= len(dft):
            idx = 0
            uistate.list_idx_select_stims = [0]
        return dft.loc[idx]

    def get_dfmean(self, row):
        # returns an internal df mean for the selected file. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        if recording_name in self.dict_means:  # 1: Return cached
            return self.dict_means[recording_name]

        persist = False
        str_mean_path = f"{self.dict_folders['cache']}/{recording_name}_mean.parquet"
        if Path(str_mean_path).exists():  # 2: Read from file
            dfmean = pd.read_parquet(str_mean_path)
        else:  # 3: Create file
            dfmean, _ = parse.build_dfmean(self.get_dfdata(row=row))
            persist = True

        # if the filter is not a column in dfmean, create it
        if row["filter"] == "savgol":
            # TODO: extract parameters from df_p, use default for now
            if "savgol" not in dfmean.columns:
                dict_filter_params = json.loads(row["filter_params"])
                window_length = int(dict_filter_params["window_length"])
                poly_order = int(dict_filter_params["poly_order"])
                dfmean["savgol"] = analysis.addFilterSavgol(
                    df=dfmean, window_length=window_length, poly_order=poly_order
                )
                persist = True
        if persist:
            self.df2file(df=dfmean, rec=recording_name, key="mean")
        self.dict_means[recording_name] = dfmean
        return self.dict_means[recording_name]

    def get_dft(self, row, reset=False):
        # returns an internal df t for the selected file. If it does not exist, read it from file first.
        rec = row["recording_name"]
        if rec in self.dict_ts.keys() and not reset:
            # print("returning cached dft")
            return self.dict_ts[rec]
        str_t_path = f"{self.dict_folders['timepoints']}/{rec}.parquet"
        if Path(str_t_path).exists() and not reset:
            # print("reading dft from file")
            dft = pd.read_parquet(str_t_path)
            self.dict_ts[rec] = dft
            return dft
        else:
            print("creating dft")
            default_dict_t = uistate.default_dict_t.copy()  # Default sizes
            dfmean = self.get_dfmean(row)
            dft = analysis.find_events(
                dfmean=dfmean, default_dict_t=default_dict_t, verbose=False
            )
            # TODO: Error handling!
            if dft.empty:
                print("get_dft: No stims found.")
                return None
            dft["norm_EPSP_from"], dft["norm_EPSP_to"] = (
                uistate.lineEdit["norm_EPSP_from"],
                uistate.lineEdit["norm_EPSP_to"],
            )
            dft["t_EPSP_amp_halfwidth"] = (
                uistate.lineEdit["EPSP_amp_halfwidth_ms"] / 1000
            )
            dft["t_volley_amp_halfwidth"] = (
                uistate.lineEdit["volley_amp_halfwidth_ms"] / 1000
            )
            df_p = self.get_df_project()  # update (number of) 'stims' columns
            stims = len(dft)
            self.set_df_project(df_p)
            # If the UI checkbox for 'timepoints_per_stim' is checked OR there's only 1 stim,
            # we assume timepoints don't need adjustment, so we cache df_t as-is.
            if uistate.checkBox["timepoints_per_stim"] or stims == 1:
                self.dict_ts[rec] = dft  # update cache
            # Otherwise, compute a uniform timepoint structure based on the current row and df_t.
            else:
                dfoutput = self.get_dfoutput(row=row, dft=dft)
                self.set_uniformTimepoints(p_row=row, dft=dft, dfoutput=dfoutput)
                dft = self.dict_ts[rec]
            self.df2file(df=dft, rec=rec, key="timepoints")  # persist dft as parquet
            self.set_rec_status(rec)  # update status in df_project
            return dft

    def get_dfoutput(self, row, reset=False, dft=None):  # Requires df_t
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        rec = row["recording_name"]
        if rec in self.dict_outputs and not reset:  # 1: Return cached
            return self.dict_outputs[rec]
        str_output_path = f"{self.dict_folders['cache']}/{rec}_output.parquet"
        if Path(str_output_path).exists() and not reset:  # 2: Read from file
            dfoutput = pd.read_parquet(str_output_path)
        else:  # 3: Create file and cache
            print(f"creating output for {row['recording_name']}")
            dfmean = self.get_dfmean(row=row)
            if dft is None:
                dft = self.get_dft(row=row)
            # print(f"df_t: {df_t}")
            if uistate.checkBox["output_per_stim"]:
                dfoutput = analysis.build_dfstimoutput(df=dfmean, df_t=dft)
            else:
                dfoutput = pd.DataFrame()
                for i, t_row in dft.iterrows():
                    dict_t = t_row.to_dict()
                    if uistate.checkBox["bin"]:
                        dfinput = self.get_dfbin(row)
                    else:
                        dfinput = self.get_dffilter(row)
                    dfoutput_stim = analysis.build_dfoutput(df=dfinput, dict_t=dict_t)
                    dft.at[i, "volley_amp_mean"] = dfoutput_stim["volley_amp"].mean()
                    dft.at[i, "volley_slope_mean"] = dfoutput_stim[
                        "volley_slope"
                    ].mean()
                    dfoutput = pd.concat([dfoutput, dfoutput_stim])
                    # print(f"dfoutput_stim: {dfoutput_stim}")
                self.set_dft(rec, dft)
        dfoutput.reset_index(inplace=True)
        # print(f"dfoutput: {dfoutput}")
        return dfoutput

    def get_dfdata(self, row):
        # returns an internal df for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        if recording_name in self.dict_datas:  # 1: Return cached
            return self.dict_datas[recording_name]
        path_data = Path(f"{self.dict_folders['data']}/{recording_name}.parquet")
        try:  # 2: Read from file - datafile should always exist
            dfdata = pd.read_parquet(path_data)
            self.dict_datas[recording_name] = dfdata
            return self.dict_datas[recording_name]
        except FileNotFoundError:
            print(f"did not find {path_data}. Not imported?")

    def get_dffilter(self, row):
        # returns an internal df_filter for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        if recording_name in self.dict_filters:  # 1: Return cached
            return self.dict_filters[recording_name]
        path_filter = Path(
            f"{self.dict_folders['cache']}/{recording_name}_filter.parquet"
        )
        if Path(path_filter).exists():  # 2: Read from file
            dffilter = pd.read_parquet(path_filter)
        else:  # 3: Create file
            dffilter = parse.zeroSweeps(
                dfdata=self.get_dfdata(row=row), dfmean=self.get_dfmean(row=row)
            )
            self.df2file(df=dffilter, rec=recording_name, key="filter")
            if row["filter"] == "savgol":
                dict_filter_params = json.loads(row["filter_params"])
                window_length = int(dict_filter_params["window_length"])
                poly_order = int(dict_filter_params["poly_order"])
                dffilter["savgol"] = analysis.addFilterSavgol(
                    df=dffilter, window_length=window_length, poly_order=poly_order
                )
        # Cache and return
        self.dict_filters[recording_name] = dffilter
        return self.dict_filters[recording_name]

    def get_dfbin(self, p_row):
        # returns an internal df_bin for the selected recording_name. If it does not exist, read it from file first.
        rec = p_row["recording_name"]
        if rec in self.dict_bins:
            return self.dict_bins[rec]
        path_bin = Path(f"{self.dict_folders['cache']}/{rec}_bin.parquet")
        if path_bin.exists():
            df_bins = pd.read_parquet(path_bin)
        else:
            bin_size = int(uistate.lineEdit["bin_size"])
            df_filter = self.get_dffilter(p_row)
            max_sweep = df_filter["sweep"].max()
            num_bins = (max_sweep // bin_size) + 1
            binned_data = []
            for bin_num in range(num_bins):
                sweep_start = bin_num * bin_size
                sweep_end = sweep_start + bin_size
                df_bin = df_filter[
                    (df_filter["sweep"] >= sweep_start)
                    & (df_filter["sweep"] < sweep_end)
                ]
                if df_bin.empty:
                    continue
                agg_funcs = {
                    col: "mean"
                    for col in df_bin.columns
                    if col not in ["sweep", "time"]
                }
                agg_funcs["time"] = (
                    "first"  # Keep the first time value as representative
                )
                df_bin_grouped = df_bin.groupby("time", as_index=False).agg(agg_funcs)
                # Assign the bin number as the new sweep value
                df_bin_grouped["sweep"] = bin_num
                binned_data.append(df_bin_grouped)
            df_bins = pd.concat(binned_data, ignore_index=True)
            self.dict_bins[rec] = df_bins
            print(
                f"recalculate: {rec}, binned {df_filter['sweep'].nunique()} sweeps into {len(df_bins['sweep'].unique())} bins"
            )
            self.df2file(df=df_bins, rec=rec, key="bin")
        self.dict_bins[rec] = df_bins
        return df_bins

    def get_dfdiff(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        rec_select = row["recording_name"]
        # TODO: check if row has a paired recording
        # Otherwise, find the paired recording
        rec_paired = None
        key_pair = rec_select[
            :-2
        ]  # remove stim id ("_a" or "_b") from selected recording_name
        # 1: check for cached diff
        if key_pair in self.dict_diffs:
            return self.dict_diffs[key_pair]
        # 2: check for file
        if Path(f"{self.dict_folders['cache']}/{key_pair}_diff.parquet").exists():
            dfdiff = pd.read_parquet(
                f"{self.dict_folders['cache']}/{key_pair}_diff.parquet"
            )
            self.dict_diffs[key_pair] = dfdiff
            return dfdiff
        # 3: build a new diff
        dfp = self.get_df_project()
        # 3.1: does the row have a saved paired recording that exists in dfp?
        if pd.notna(row["paired_recording"]):
            if row["paired_recording"] in dfp["recording_name"].values:
                rec_paired = row["paired_recording"]
        # 3.2: if not, find a recording with a matching name
        if (
            rec_paired is None
        ):  # set rec_paired to the first recording_name that starts with rec_paired, but isn't rec_select
            for i, row_check in dfp.iterrows():
                if (
                    row_check["recording_name"].startswith(key_pair)
                    and row_check["recording_name"] != rec_select
                ):
                    rec_paired = row_check["recording_name"]
                    break
        if rec_paired is None:  # if still None, return
            print("Paired recording not found.")
            return
        # 3.3: get the dfoutputs for both recordings
        row_paired = dfp[dfp["recording_name"] == rec_paired].iloc[0]
        dfp.loc[row.name, "paired_recording"] = rec_paired
        dfp.loc[row_paired.name, "paired_recording"] = rec_select
        self.set_df_project(dfp)
        dfout_select = self.get_dfoutput(row=row)
        dfout_paired = self.get_dfoutput(row=row_paired)

        # 3.4: check which of the paired recordings is Tx (the other being control)
        if pd.isna(row["Tx"]):
            print("Tx is NaN - loop should trigger!")
            row["Tx"] = False
            # default: assume Tx has the highest max EPSP_amp, or EPSP_slope if there is no EPSP_amp
            if any(
                (
                    dfout_select[col].max() > dfout_paired[col].max()
                    for col in ["EPSP_amp", "EPSP_slope"]
                    if col in dfout_select.columns
                )
            ):
                row["Tx"] = True
                row_paired["Tx"] = False
                dfp.loc[row.name, "Tx"] = row["Tx"]
                dfp.loc[row_paired.name, "Tx"] = row_paired["Tx"]
                print(f"{rec_select} is Tx, {rec_paired} is control. Saving df_p...")
                self.set_df_project(dfp)
            elif not any(
                col in dfout_select.columns for col in ["EPSP_amp", "EPSP_slope"]
            ):
                print("Selected recording has no measurements.")
                return
        else:
            print("Tx is not NaN")
        # 3.5: set dfi and dfc
        if row["Tx"]:
            dfi = dfout_select  # Tx output
            dfc = dfout_paired  # control output
        else:
            dfi = dfout_paired
            dfc = dfout_select
        # 3.6: build dfdiff
        dfdiff = pd.DataFrame({"sweep": dfi.sweep})
        if "EPSP_amp" in dfi.columns:
            dfdiff["EPSP_amp"] = dfi.EPSP_amp / dfc.EPSP_amp
        if "EPSP_slope" in dfi.columns:
            dfdiff["EPSP_slope"] = dfi.EPSP_slope / dfc.EPSP_slope
        self.df2file(df=dfdiff, rec=key_pair, key="diff")
        self.dict_diffs[key_pair] = dfdiff
        return dfdiff

    def get_dfgroupmean(self, group_ID):
        # returns an internal df output average of <group>. If it does not exist, create it
        if group_ID in self.dict_group_means:  # 1: Return cached
            if config.verbose:
                print(f"Returning cached group mean for group {group_ID}")
            return self.dict_group_means[group_ID]
        group_path = Path(f"{self.dict_folders['cache']}/group_{group_ID}.parquet")
        if group_path.exists():  # 2: Read from file
            if config.verbose:
                print(f"Loading stored group mean for group {group_ID}")
            group_mean = pd.read_parquet(str(group_path))
        else:  # 3: Create file
            if config.verbose:
                print(f"Building new group mean for group {group_ID}")
            recs_in_group = self.dd_groups[group_ID]["rec_IDs"]
            # print(f"recs_in_group: {recs_in_group}")
            dfs = []
            df_p = self.get_df_project()
            for rec_ID in recs_in_group:
                matching_rows = df_p.loc[df_p["ID"] == rec_ID]
                if matching_rows.empty:
                    raise ValueError(f"rec_ID {rec_ID} not found in df_project.")
                else:
                    p_row = matching_rows.iloc[0]
                df = self.get_dfoutput(row=p_row)
                dfs.append(df)
            if uistate.checkBox["output_per_stim"]:
                group_mean = (
                    pd.concat(dfs)
                    .groupby("stim")
                    .agg(
                        {
                            "EPSP_amp_norm": ["mean", "sem"],
                            "EPSP_slope_norm": ["mean", "sem"],
                            "EPSP_amp": ["mean", "sem"],
                            "EPSP_slope": ["mean", "sem"],
                        }
                    )
                    .reset_index()
                )
                group_mean.columns = [
                    col[0]
                    if col[0] == "stim"
                    else "_".join(col).strip().replace("sem", "SEM")
                    for col in group_mean.columns.values
                ]
            else:
                if len(dfs) == 0:
                    group_mean = pd.DataFrame(
                        {
                            "sweep": [],
                            "EPSP_amp_norm_mean": [],
                            "EPSP_amp_norm_SEM": [],
                            "EPSP_slope_norm_mean": [],
                            "EPSP_slope_norm_SEM": [],
                            "EPSP_amp_mean": [],
                            "EPSP_amp_SEM": [],
                            "EPSP_slope_mean": [],
                            "EPSP_slope_SEM": [],
                        }
                    )
                else:
                    group_mean = (
                        pd.concat(dfs)
                        .groupby("sweep")
                        .agg(
                            {
                                "EPSP_amp_norm": ["mean", "sem"],
                                "EPSP_slope_norm": ["mean", "sem"],
                                "EPSP_amp": ["mean", "sem"],
                                "EPSP_slope": ["mean", "sem"],
                            }
                        )
                        .reset_index()
                    )
                group_mean.columns = [
                    col[0]
                    if col[0] == "sweep"
                    else "_".join(col).strip().replace("sem", "SEM")
                    for col in group_mean.columns.values
                ]
            print(f"Group mean columns: {group_mean.columns}")
            print(f"Group mean: {group_mean}")
            self.df2file(df=group_mean, rec=f"group_{group_ID}", key="mean")
        self.dict_group_means[group_ID] = group_mean
        return group_mean

    def set_uniformTimepoints(
        self, p_row=None, dft=None, dfoutput=None
    ):  # NB: requires both dfoutput and df_t to be present!
        variables = [
            "t_volley_amp",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_EPSP_amp",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
        ]
        methods = [
            "t_volley_amp_method",
            "t_volley_slope_method",
            "t_EPSP_amp_method",
            "t_EPSP_slope_method",
        ]
        params = [
            "t_volley_amp_params",
            "t_volley_slope_params",
            "t_EPSP_amp_params",
            "t_EPSP_slope_params",
        ]

        def use_t_from_stim_with_max(p_row, df_t, dfoutput, column):
            # find highest EPSP_slope in df_output and apply uniform timepoints to all stims
            print(f" - use_t_from_stim_with_max called with df_t:\n{df_t}")
            precision = uistate.settings["precision"]
            if column in dfoutput.columns:
                print(f"dfoutput:\n{dfoutput}")
                idx_max_EPSP = dfoutput[column].idxmax()
                print(f"idx_max_EPSP: {idx_max_EPSP}")
                stim_max = dfoutput.loc[idx_max_EPSP, "stim"]
                print(f"stim_max: {stim_max}")
                t_template_row = df_t[df_t["stim"] == stim_max].copy()
                print(f"t_template_row: {t_template_row}")
                t_stim = round(t_template_row["t_stim"].values[0], precision)
                for var in variables:
                    t_template_row[var] = round(
                        t_template_row[var].values[0] - t_stim, precision
                    )
                if "stim" not in df_t.columns:
                    df_t["stim"] = None
                for i, row_t in df_t.iterrows():
                    df_t.at[i, "stim"] = i + 1  # stims numbered from 1
                    for var in variables:
                        df_t.at[i, var] = round(
                            t_template_row[var].values[0] + row_t["t_stim"], precision
                        )
                    for method in methods:
                        df_t.at[i, method] = f"=stim_{stim_max}"
                    for param in params:
                        df_t.at[i, param] = f"=stim_{stim_max}"
                print(f"Uniform timepoints applied to {p_row['recording_name']}.")
                self.set_dft(p_row["recording_name"], df_t)
                dfoutput = self.get_dfoutput(p_row, reset=True)
                self.persistOutput(p_row["recording_name"], dfoutput)

        if p_row is None:  # apply to all recordings
            print(f"set_uniformTimepoints for all recordings")
            for _, p_row in self.get_df_project().iterrows():
                dft = self.get_dft(p_row)
                dfoutput = self.get_dfoutput(p_row)
                use_t_from_stim_with_max(p_row, dft, dfoutput, "EPSP_slope")
        else:
            print(f"set_uniformTimepoints for {p_row['recording_name']}")
            if dft is None or dfoutput is None:
                dft = self.get_dft(p_row)
                dfoutput = self.get_dfoutput(p_row)
            use_t_from_stim_with_max(p_row, dft, dfoutput, "EPSP_slope")

    # Graph interface

    def graphWipe(self):  # removes all plots from canvasEvent and canvasOutput
        uistate.dict_rec_labels = {}
        uistate.dict_rec_show = {}
        uistate.dict_group_labels = {}
        uistate.dict_group_show = {}
        if hasattr(self, "canvasMean"):
            self.canvasMean.figure.legends.clear()
            self.canvasMean.axes.cla()
            self.canvasMean.draw()
        if hasattr(self, "canvasEvent"):
            self.canvasEvent.figure.legends.clear()
            self.canvasEvent.axes.cla()
            self.canvasEvent.draw()
        if hasattr(self, "canvasOutput"):
            for ax in self.canvasOutput.figure.axes:
                ax.cla()
                ax.legend_ = None
            self.canvasOutput.draw()

    def graphAxes(self):  # plot selected row(s), or clear graph if empty
        print("graphAxes")
        uistate.axm = self.canvasMean.axes
        uistate.axe = self.canvasEvent.axes
        ax1 = self.canvasOutput.axes
        if uistate.ax2 is not None and hasattr(
            uistate, "ax2"
        ):  # remove ax2 if it exists
            uistate.ax2.remove()
        ax2 = ax1.twinx()
        uistate.ax2 = ax2  # Store the ax2 instance
        uistate.ax1 = ax1
        # connect scroll event if not already connected #TODO: when graphAxes is called only once, the check should be redundant
        if (
            not hasattr(self, "scroll_event_connected")
            or not self.scroll_event_connected
        ):
            self.canvasMean.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="mean"),
            )
            self.canvasEvent.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="event"),
            )
            self.canvasOutput.mpl_connect(
                "scroll_event",
                lambda event: self.zoomOnScroll(event=event, graph="output"),
            )
            self.scroll_event_connected = True
        df_p = self.get_df_project()
        if df_p.empty:
            return
        self.graphPreload()

    def graphPreload(self):  # plot and hide imported recordings
        print("graphPreload: entered")
        self.usage("graphPreload")
        self.uiFreeze()  # Freeze UI, thaw on graphPreloadFinished
        t0 = time.time()
        self.mouseoverDisconnect()
        # Clean up any existing thread before starting a new one
        self._cleanup_threads()
        if not uistate.list_idx_recs2preload:
            print(
                "graphPreload: list_idx_recs2preload empty, falling back to all parsed recordings"
            )
            df_p = self.get_df_project()
            uistate.list_idx_recs2preload = df_p[
                ~df_p["sweeps"].eq("...")
            ].index.tolist()
        if not uistate.list_idx_recs2preload:
            print("graphPreload: nothing to preload, returning early")
            self.uiThaw()
            return
        print(
            f"graphPreload: starting thread for {len(uistate.list_idx_recs2preload)} recordings: {uistate.list_idx_recs2preload}"
        )
        self.progressBar.setValue(0)
        thread = graphPreloadThread(uistate, uiplot, self)
        thread.finished.connect(lambda: self.ongraphPreloadFinished(t0))
        thread.finished.connect(thread.deleteLater)  # Auto-cleanup when done
        thread.finished.connect(
            lambda: self._threads.remove(thread) if thread in self._threads else None
        )
        self._threads.append(thread)

        # Create ProgressBarManager and connect progress signal
        if len(uistate.list_idx_recs2preload) > 0:
            self.progressBarManager = ProgressBarManager(
                self.progressBar, len(uistate.list_idx_recs2preload)
            )
            thread.progress.connect(
                lambda i: self.progressBarManager.update(i, "Preloading recording")
            )

            thread.start()
            self.progressBarManager.__enter__()  # Show progress bar
        else:
            print("No new recordings to preload.")

    def ongraphPreloadFinished(self, t0):
        self.graphGroups()
        print(f"Preloaded recordings and groups in {time.time() - t0:.2f} seconds.")
        self.graphRefresh()
        self.progressBarManager.__exit__(None, None, None)  # Hide progress bar
        self.tableFormat()
        self.uiThaw()
        self.tableProjSelectionChanged()

    def graphGroups(self):
        # Get all group IDs
        all_group_ids = self.dd_groups.keys()
        if not all_group_ids:
            return
        groups_with_records = {
            group_id: group_info
            for group_id, group_info in self.dd_groups.items()
            if group_info["rec_IDs"]
        }
        already_plotted_groups = set(uistate.get_groupSet())
        groups_to_plot = (
            all_group_ids & set(groups_with_records.keys()) - already_plotted_groups
        )
        if groups_to_plot:
            for group_ID in groups_to_plot:
                dict_group = self.dd_groups[group_ID]
                group_mean_data = self.get_dfgroupmean(group_ID)
                # print(f"graphGroups: Adding group {group_ID} to plot: {group_mean_data}")
                uiplot.addGroup(group_ID, dict_group, group_mean_data)

    def graphUpdate(self, df=None, row=None):
        def processRow(row):
            dfmean = self.get_dfmean(row=row)
            dft = self.get_dft(row=row)
            print(f"graphUpdate dft: {dft}")
            dfoutput = (
                self.get_dfdiff(row=row)
                if uistate.checkBox["paired_stims"]
                else self.get_dfoutput(row=row)
            )
            if dfoutput is not None:
                uiplot.addRow(p_row=row, dft=dft, dfmean=dfmean, dfoutput=dfoutput)

        def processDataFrame(df):
            list_to_plot = [
                rec
                for rec in df["recording_name"].tolist()
                if rec not in uistate.get_recSet()
            ]
            for rec in list_to_plot:
                row = df[df["recording_name"] == rec].iloc[0]
                processRow(row)

        self.graphGroups()
        if row is not None:
            processRow(row)
        else:
            df = df or uistate.df_recs2plot
            if df is not None and not df.empty:
                processDataFrame(df)
        self.zoomAuto()
        print("graphUpdate calls self.graphRefresh()")
        self.graphRefresh()

    #####################################################
    #          Mouseover, click and drag events         #
    #####################################################

    def graphClicked(self, event, canvas):  # graph click event
        if not uistate.list_idx_select_recs:  # no recording selected; do nothing
            return
        x = event.xdata
        if x is None:  # clicked outside graph; do nothing
            return
        self.usage("graphClicked")
        if event.button == 2:  # middle click, reset zoom
            # print(f"axis: {axis}, type {type(axis)}")
            self.zoomAuto()
            return
        if event.button == 3:  # right click, deselect
            if uistate.dragging:
                return
            self.mouse_drag = None
            self.mouse_release = None
            uistate.x_drag = None
            if canvas == self.canvasMean:
                uiplot.xDeselect(ax=uistate.axm, reset=True)
                self.lineEdit_mean_selection_start.setText("")
                self.lineEdit_mean_selection_end.setText("")
            else:
                uiplot.xDeselect(ax=uistate.ax1, reset=True)
                self.lineEdit_sweeps_range_from.setText("")
                self.lineEdit_sweeps_range_to.setText("")
            return

        # left clicked on a graph
        uistate.dragging = True
        prow = self.get_prow()

        if (
            (canvas == self.canvasEvent)
            and (len(uistate.list_idx_select_recs) == 1)
            and (len(uistate.list_idx_select_stims) == 1)
        ):  # Event canvas left-clicked with just one rec and stim selected, middle graph: editing detected events
            uistate.dft_temp = self.get_dft(prow).copy()
            trow = uistate.dft_temp.loc[uistate.list_idx_select_stims[0]]
            label = f"{prow['recording_name']} - stim {trow['stim']}"
            dict_event = uistate.dict_rec_labels[label]
            data_x = dict_event["line"].get_xdata()
            data_y = dict_event["line"].get_ydata()
            uistate.x_on_click = data_x[
                np.abs(data_x - x).argmin()
            ]  # time-value of the nearest index
            # print(f"uistate.x_on_click: {uistate.x_on_click}")
            if event.inaxes is not None:
                if (event.button == 1 or event.button == 3) and (
                    uistate.mouseover_action is not None
                ):
                    action = uistate.mouseover_action
                    # print(f"mouseover action: {action}")
                    if action.startswith("EPSP slope"):
                        start, end = (
                            trow["t_EPSP_slope_start"] - trow["t_stim"],
                            trow["t_EPSP_slope_end"] - trow["t_stim"],
                        )
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragSlope(
                                event, action, data_x, data_y, start, end
                            ),
                        )
                    elif action == "EPSP amp move":
                        start = trow["t_EPSP_amp"] - trow["t_stim"]
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragPoint(
                                event, data_x, data_y, start
                            ),
                        )
                    elif action.startswith("volley slope"):
                        start, end = (
                            trow["t_volley_slope_start"] - trow["t_stim"],
                            trow["t_volley_slope_end"] - trow["t_stim"],
                        )
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragSlope(
                                event, action, data_x, data_y, start, end
                            ),
                        )
                    elif action == "volley amp move":
                        start = trow["t_volley_amp"] - trow["t_stim"]
                        self.mouse_drag = self.canvasEvent.mpl_connect(
                            "motion_notify_event",
                            lambda event: self.eventDragPoint(
                                event, data_x, data_y, start
                            ),
                        )
                    self.mouse_release = self.canvasEvent.mpl_connect(
                        "button_release_event",
                        lambda event: self.eventDragReleased(event, data_x, data_y),
                    )

        elif (
            canvas == self.canvasMean
        ):  # Mean canvas (top graph) left-clicked: overview and selecting ranges for finding relevant stims
            if uistate.mean_mouseover_stim_select is not None:
                uistate.dragging = False
                self.stimSelectionChanged()
                return
            dfmean = self.get_dfmean(prow)  # Required for event dragging, x and y
            time_values = dfmean["time"].values
            uistate.x_on_click = time_values[np.abs(time_values - x).argmin()]
            uistate.x_select["mean_start"] = uistate.x_on_click
            self.lineEdit_mean_selection_start.setText(
                str(uistate.x_select["mean_start"])
            )
            self.connectDragRelease(
                x_range=time_values, rec_ID=prow["ID"], graph="mean"
            )
        elif (
            canvas == self.canvasOutput
        ):  # Output canvas (bottom graph) left-clicked: click and drag to select specific sweeps
            sweep_numbers = list(range(0, int(prow["sweeps"])))
            uistate.x_on_click = sweep_numbers[np.abs(sweep_numbers - x).argmin()]
            uistate.x_select["output_start"] = uistate.x_on_click
            self.lineEdit_sweeps_range_from.setText(str(uistate.x_on_click))
            self.connectDragRelease(
                x_range=sweep_numbers, rec_ID=prow["ID"], graph="output"
            )

    def meanMouseover(self, event):  # determine which event is being mouseovered
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        dft = uistate.df_rec_select_time
        if dft is None or dft.empty:
            # print("No single recording selected with timepoints to mouseover.")
            return
        n_stims = len(dft)
        if n_stims < 2:
            # print("Not enough stims to mouseover.")
            return
        # One recording selected, with 2 or more stims, define mouseover zones
        prow = self.get_prow()
        rec_name = f"{prow['recording_name']}"
        rec_filter = prow["filter"]  # the filter currently used for this recording
        if rec_filter != "voltage":
            label_core = f"{rec_name} ({rec_filter})"
        else:
            label_core = rec_name

        axm = uistate.axm
        uistate.mean_mouseover_stim_select = (
            None  # name of stim that will be selected if clicked
        )
        uistate.mean_stim_x_ranges = {}  # dict: stim_num: (x_start, x_end)
        # y_margin is 10% of y-axis range
        uistate.mean_y_margin = (axm.get_ylim()[1] - axm.get_ylim()[0]) * 0.1
        y_range = (
            -uistate.mean_y_margin,
            uistate.mean_y_margin,
        )  # stim markers should be at y~0
        # x_margin is 25% of the shortest distance between stims OR 1% of x-axis range, whichever is smaller
        t_stims = dft["t_stim"].values
        t_diffs = np.diff(t_stims)
        min_t_diff = np.min(t_diffs)
        x_axis_range = axm.get_xlim()[1] - axm.get_xlim()[0]
        uistate.mean_x_margin = min(x_axis_range * 0.01, min_t_diff * 0.25)

        # build detection zones for each stim
        for row in dft.itertuples(index=False):
            stim = row.stim
            t_stim = row.t_stim
            x_range = t_stim - uistate.mean_x_margin, t_stim + uistate.mean_x_margin
            uistate.mean_stim_x_ranges[stim] = x_range
        # check if mouse is within any of the stim zones
        for stim, x_range in uistate.mean_stim_x_ranges.items():
            if x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]:
                uistate.mean_mouseover_stim_select = stim
                # print(f"meanMouseover of {uistate.mean_mouseover_stim_select}: x={x}, y={y}")
                # find corresponding selection marker:
                stim_str = f"- stim {stim}"
                label = f"mean {label_core} {stim_str} marker"
                stim_marker = uistate.dict_rec_labels.get(label)
                # print(f"{label}: {stim_marker}")
                # zorder mouseovered marker to top, alpha 1
                if stim_marker is not None:
                    stim_marker_line = stim_marker.get("line")
                    stim_marker_line.set_zorder(10)
                    stim_marker_line.set_alpha(1.0)
                break
            else:
                # reset all stim markers to default zorder and alpha
                stim_str = f"- stim {stim}"
                label = f"mean {label_core} {stim_str} marker"
                stim_marker = uistate.dict_rec_labels.get(label)
                if stim_marker is not None:
                    stim_marker_line = stim_marker.get("line")
                    stim_marker_line.set_zorder(0)
                    stim_marker_line.set_alpha(0.4)

        axm.figure.canvas.draw()

    def eventMouseover(self, event):  # determine which event is being mouseovered
        if (
            uistate.df_rec_select_data is None
        ):  # no single recording/stim combo selected
            return
        axe = uistate.axe

        def plotMouseover(action, axe):
            alpha = 0.8
            linewidth = 3 if "resize" in action else 10
            if "slope" in action:
                if "EPSP" in action:
                    x_range = (
                        uistate.EPSP_slope_start_xy[0],
                        uistate.EPSP_slope_end_xy[0],
                    )
                    y_range = (
                        uistate.EPSP_slope_start_xy[1],
                        uistate.EPSP_slope_end_xy[1],
                    )
                    color = uistate.settings["rgb_EPSP_slope"]
                elif "volley" in action:
                    x_range = (
                        uistate.volley_slope_start_xy[0],
                        uistate.volley_slope_end_xy[0],
                    )
                    y_range = (
                        uistate.volley_slope_start_xy[1],
                        uistate.volley_slope_end_xy[1],
                    )
                    color = uistate.settings["rgb_volley_slope"]

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(
                        x_range[1], y_range[1], color=color, s=100, alpha=alpha
                    )
                else:
                    uistate.mouseover_blob.set_offsets([x_range[1], y_range[1]])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)

                if uistate.mouseover_plot is None:
                    uistate.mouseover_plot = axe.plot(
                        x_range,
                        y_range,
                        color=color,
                        linewidth=linewidth,
                        alpha=alpha,
                        label="mouseover",
                    )
                else:
                    uistate.mouseover_plot[0].set_data(x_range, y_range)
                    uistate.mouseover_plot[0].set_linewidth(linewidth)
                    uistate.mouseover_plot[0].set_alpha(alpha)
                    uistate.mouseover_plot[0].set_color(color)

            elif "amp" in action:
                if "EPSP" in action:
                    x, y = uistate.EPSP_amp_xy
                    color = uistate.settings["rgb_EPSP_amp"]
                elif "volley" in action:
                    x, y = uistate.volley_amp_xy
                    color = uistate.settings["rgb_volley_amp"]

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(
                        x, y, color=color, s=100, alpha=alpha
                    )
                else:
                    uistate.mouseover_blob.set_offsets([x, y])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)

        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        if event.inaxes == axe:
            zones = {}
            if uistate.checkBox["EPSP_amp"]:
                zones["EPSP amp move"] = uistate.EPSP_amp_move_zone
            if uistate.checkBox["EPSP_slope"]:
                zones["EPSP slope resize"] = uistate.EPSP_slope_resize_zone
                zones["EPSP slope move"] = uistate.EPSP_slope_move_zone
            if uistate.checkBox["volley_amp"]:
                zones["volley amp move"] = uistate.volley_amp_move_zone
            if uistate.checkBox["volley_slope"]:
                zones["volley slope resize"] = uistate.volley_slope_resize_zone
                zones["volley slope move"] = uistate.volley_slope_move_zone
            uistate.mouseover_action = None
            for action, zone in zones.items():
                if (
                    zone["x"][0] <= x <= zone["x"][1]
                    and zone["y"][0] <= y <= zone["y"][1]
                ):
                    uistate.mouseover_action = action
                    plotMouseover(action, axe)

                    # Debugging block
                    if False:
                        prow = self.get_prow()
                        rec_name = prow["recording_name"]
                        rec_ID = prow["ID"]
                        trow = self.get_trow()
                        # new_dict = {key: value for key, value in uistate.dict_rec_labels.items() if value.get('stim') == stim_num and value.get('rec_ID') == rec_ID and value.get('axis') == 'ax2'}
                        # EPSP_slope = new_dict.get(f"{rec_name} - stim {stim_num} EPSP slope")
                        EPSP_slope = uistate.dict_rec_labels.get(
                            f"{rec_name} - stim {trow['stim']} EPSP slope"
                        )
                        line = EPSP_slope.get("line")
                        line.set_linewidth(10)
                        print(f"{EPSP_slope} - {action}")
                    break

            if uistate.mouseover_action is None:
                if uistate.mouseover_blob is not None:
                    uistate.mouseover_blob.set_sizes([0])
                if uistate.mouseover_plot is not None:
                    uistate.mouseover_plot[0].set_linewidth(0)

            axe.figure.canvas.draw()

    def outputMouseover(self, event):  # determine which event is being mouseovered
        x, y = event.xdata, event.ydata
        str_ax = "ax2" if uistate.slopeView() else "ax1" if uistate.ampView() else None
        ax = getattr(uistate, str_ax)
        print(f"outputMouseover: x={x}, y={y}, str_ax={str_ax}")
        if (
            str_ax is None
            or x is None
            or y is None
            or not event.inaxes == ax
            or not (uistate.slopeView() or uistate.ampView())
        ):
            if (
                uistate.ghost_sweep is not None
            ):  # remove ghost sweep if outside output graph
                self.exorcise()
            return
        if len(uistate.list_idx_select_recs) != 1:
            self.exorcise()
            return
        x_axis = "stim" if uistate.checkBox["output_per_stim"] else "sweep"

        # find a visible line
        dict_out = {
            key: value
            for key, value in uistate.dict_rec_show.items()
            if value["axis"] == str_ax
            and (value["aspect"] in ["EPSP_amp", "EPSP_slope"])
        }
        if not dict_out:
            return
        dict_pop = dict_out.popitem()[1]  # TODO: ugly random; pick top in df_p?
        x_data = dict_pop["line"].get_xdata()
        # find closest x_index
        out_x_idx = (np.abs(x_data - x)).argmin()

        # print(f"* * * outputMouseover: out_x_idx={out_x_idx}, sweeps={sweeps}")

        if out_x_idx == uistate.last_out_x_idx:  # prevent update if same x
            return

        if x_axis == "stim":  # Not connected yet
            return
        else:  # sweep
            rec_ID = dict_pop["rec_ID"]
            df_p = self.get_df_project()
            p_row = df_p[df_p["ID"] == rec_ID].iloc[0]
            df_t = self.get_dft(p_row)
            stim = dict_pop["stim"]
            t_row = df_t[df_t["stim"] == stim].iloc[0]
            offset = t_row["t_stim"]

            if uistate.checkBox["bin"]:
                dfsource = self.get_dfbin(p_row)
            else:
                dfsource = self.get_dffilter(p_row)

            dfsweep = dfsource[
                dfsource["sweep"] == out_x_idx
            ]  # select only rows where sweep == out_x_idx
            sweep_x = dfsweep["time"] - offset
            sweep_y = dfsweep[
                p_row["filter"]
            ]  # get the value of the filter at the selected sweep

            if uistate.ghost_sweep is None:
                ghost_color = "white" if uistate.darkmode else "black"
                (uistate.ghost_sweep,) = uistate.axe.plot(
                    sweep_x, sweep_y, color=ghost_color, alpha=0.5, zorder=0
                )
                if uistate.ghost_label is None:
                    uistate.ghost_label = uistate.axe.text(
                        1,
                        1,
                        f"sweep {out_x_idx}",
                        transform=uistate.axe.transAxes,
                        ha="left",
                        va="bottom",
                    )
                else:
                    uistate.ghost_label.set_text(f"sweep {out_x_idx}")
            else:
                uistate.ghost_sweep.set_data(sweep_x, sweep_y)
                uistate.ghost_label.set_text(f"sweep {out_x_idx}")
            uistate.axe.figure.canvas.draw()
        uistate.last_out_x_idx = out_x_idx
        ax.figure.canvas.draw()

    def on_leave_output(self, event):
        self.exorcise()

    def exorcise(self):
        if uistate.ghost_sweep is not None:
            uistate.ghost_sweep.remove()
            uistate.ghost_sweep = None
        if uistate.ghost_label is not None:
            uistate.ghost_label.remove()
            uistate.ghost_label = None
        uistate.axe.figure.canvas.draw()

    def connectDragRelease(self, x_range, rec_ID, graph):
        self.usage("connectDragRelease")
        # function to set up x scales for dragging and releasing on mean- and output canvases
        if graph == "mean":  # uistate.axm
            canvas = self.canvasMean
            filtered_values = [
                value["line"]
                for value in uistate.dict_rec_labels.values()
                if value["rec_ID"] == rec_ID and value["axis"] == "axm"
            ]
        elif graph == "output":  # uistate.ax1+ax2
            canvas = self.canvasOutput
            filtered_values = [
                value["line"]
                for value in uistate.dict_rec_labels.values()
                if value["rec_ID"] == rec_ID
                and (value["axis"] == "ax1" or value["axis"] == "ax2")
            ]
        else:
            print("connectDragRelease: Incorrect graph reference.")
            return

        filtered_values = [
            line for line in filtered_values if len(line.get_xdata()) > 0
        ]
        max_x_line = max(
            filtered_values, key=lambda line: line.get_xdata()[-1], default=None
        )
        if max_x_line is None:
            print("No lines found. Cannot set up drag and release.")
            return
        x_data = max_x_line.get_xdata()
        self.mouse_drag = canvas.mpl_connect(
            "motion_notify_event",
            lambda event: self.xDrag(
                event, canvas=canvas, x_data=x_data, x_range=x_range
            ),
        )
        self.mouse_release = canvas.mpl_connect(
            "button_release_event",
            lambda event: self.drag_released(event, canvas=canvas),
        )

    def xDrag(self, event, canvas, x_data, x_range):
        # self.usage("xDrag")
        if not uistate.dragging:
            return
        if event.xdata is None:
            return
        x = event.xdata  # mouse x position
        x_drag = np.abs(x_data - x).argmin()  # index closest to x
        if (
            x_drag == uistate.x_drag_last
        ):  # return if the pointer hasn't moved a full idx since last update
            return
        if x_drag < 0:
            x_drag = 0
        elif x_drag >= len(x_data):
            x_drag = len(x_data) - 1
        uistate.x_drag = x_range[np.abs(x_range - x).argmin()]
        uistate.x_drag_last = uistate.x_drag
        if canvas == self.canvasMean:
            uistate.x_select["mean_end"] = uistate.x_drag
            self.lineEdit_mean_selection_end.setText(str(uistate.x_drag))
        else:
            uistate.x_select["output_end"] = uistate.x_drag
            uistate.x_select["output"] = set(
                range(
                    min(uistate.x_on_click, uistate.x_drag),
                    max(uistate.x_on_click, uistate.x_drag) + 1,
                )
            )
            # print(f"uistate.x_select['output']: {uistate.x_select['output']}")
        uiplot.xSelect(canvas=canvas)

    def drag_released(self, event, canvas):
        self.usage("drag_released")
        is_mean = canvas is self.canvasMean
        is_output = canvas is self.canvasOutput

        if uistate.x_drag is None:  # click only
            if is_mean:
                self.lineEdit_mean_selection_end.setText("")
                uistate.x_select["mean_end"] = None
            elif is_output:
                self.lineEdit_sweeps_range_to.setText("")
                uistate.x_select["output_end"] = None
                uistate.x_select["output"] = {uistate.x_on_click}  # ensure set type
                uiplot.update_axe_mean()
        else:  # click and drag
            start, end = sorted((uistate.x_on_click, uistate.x_drag))
            if is_mean:
                uistate.x_select["mean_start"] = start
                uistate.x_select["mean_end"] = end
                self.lineEdit_mean_selection_start.setText(str(start))
                self.lineEdit_mean_selection_end.setText(str(end))
            elif is_output:
                uistate.x_select["output_start"] = start
                uistate.x_select["output_end"] = end
                uistate.x_select["output"] = set(range(start, end + 1))
                self.lineEdit_sweeps_range_from.setText(str(start))
                self.lineEdit_sweeps_range_to.setText(str(end))
                uiplot.update_axe_mean()
        # cleanup
        canvas.mpl_disconnect(self.mouse_drag)
        canvas.mpl_disconnect(self.mouse_release)
        self.mouse_drag = None
        self.mouse_release = None
        uistate.x_drag = None
        uistate.dragging = False

        uiplot.xSelect(canvas=canvas)

    def mouseoverUpdate(self):
        self.usage("mouseoverUpdate")
        self.mouseoverDisconnect()
        # if only one item is selected, make a new mouseover event connection
        if uistate.list_idx_select_recs and uistate.list_idx_select_stims:
            self.mouseoverUpdateMarkers()

        if len(uistate.list_idx_select_recs) != 1:
            print("(multi-rec-selection) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return
        if len(uistate.list_idx_select_stims) != 1:
            print("(multi-stim-selection) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return
        # print(f"mouseoverUpdate: {uistate.list_idx_select_recs[0]}, {type(uistate.list_idx_select_recs[0])}")
        prow = self.get_prow()
        rec_ID = prow["ID"]
        trow = self.get_trow()
        stim_num = trow["stim"]
        uistate.setMargins(axe=uistate.axe)
        dict_labels = {
            key: value
            for key, value in uistate.dict_rec_labels.items()
            if key.endswith(" marker")
            and value["rec_ID"] == rec_ID
            and value["axis"] == "axe"
            and value["stim"] == stim_num
        }
        if not dict_labels:
            print("(no labels) mouseoverUpdate calls self.graphRefresh()")
            self.graphRefresh()
            return

        for label, value in dict_labels.items():
            line = value["line"]
            if label.endswith("EPSP amp marker"):
                uistate.updatePointDragZone(
                    aspect="EPSP amp move", x=line.get_xdata()[0], y=line.get_ydata()[0]
                )
            elif label.endswith("volley amp marker"):
                uistate.updatePointDragZone(
                    aspect="volley amp move",
                    x=line.get_xdata()[0],
                    y=line.get_ydata()[0],
                )
            elif label.endswith("EPSP slope marker"):
                uistate.updateDragZones(
                    aspect="EPSP slope", x=line.get_xdata(), y=line.get_ydata()
                )
            elif label.endswith("volley slope marker"):
                uistate.updateDragZones(
                    aspect="volley slope", x=line.get_xdata(), y=line.get_ydata()
                )

        self.mouseoverMean = self.canvasMean.mpl_connect(
            "motion_notify_event", self.meanMouseover
        )
        self.mouseoverEvent = self.canvasEvent.mpl_connect(
            "motion_notify_event", self.eventMouseover
        )
        self.mouseoverOutput = self.canvasOutput.mpl_connect(
            "motion_notify_event", self.outputMouseover
        )
        self.mouseLeaveOutput = self.canvasOutput.mpl_connect(
            "axes_leave_event", self.on_leave_output
        )
        # print("mouseoverUpdate calls self.graphRefresh()")
        self.graphRefresh()

    def mouseoverUpdateMarkers(self):
        self.usage("mouseoverUpdateMarkers")
        # update xy data of shown markers
        df_p = self.get_df_project()
        precision = uistate.settings["precision"]

        EPSP_slope_markers = {
            k: v
            for k, v in uistate.dict_rec_show.items()
            if k.endswith(" EPSP slope marker")
        }
        # print(f"mouseoverUpdateMarkers: {EPSP_slope_markers.keys()}")
        for marker in EPSP_slope_markers.values():
            p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
            dfmean = self.get_dfmean(row=p_row)
            df_t = self.get_dft(row=p_row)
            stim_num = marker["stim"]
            t_row = df_t.loc[df_t["stim"] == stim_num].squeeze()
            t_stim = round(t_row["t_stim"], precision)
            # x: location on dfmean['time'], for acquiring y-values
            x_start, x_end = (
                round(t_row["t_EPSP_slope_start"], precision),
                round(t_row["t_EPSP_slope_end"], precision),
            )
            # event_x: location on event graph, for drawing event markers
            if not analysis.valid(x_start, x_end):
                print(
                    "ERROR - EPSP_slope_markers: invalid x_start or x_end in mouseoverUpdateMarkers"
                )
                print(type(x_start), x_start)
                print(type(x_end), x_end)
                return
            event_x_start, event_x_end = (
                round(t_row["t_EPSP_slope_start"] - t_stim, precision),
                round(t_row["t_EPSP_slope_end"] - t_stim, precision),
            )
            y_start, y_end = (
                dfmean.loc[dfmean["time"] == x_start, "voltage"].values[0],
                dfmean.loc[dfmean["time"] == x_end, "voltage"].values[0],
            )
            marker["line"].set_data([event_x_start, event_x_end], [y_start, y_end])

        EPSP_amp_markers = {
            k: v
            for k, v in uistate.dict_rec_show.items()
            if k.endswith(" EPSP amp marker")
        }
        # print(f"mouseoverUpdateMarkers: {EPSP_amp_markers.keys()}")
        for marker in EPSP_amp_markers.values():
            p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
            dfmean = self.get_dfmean(row=p_row)
            df_t = self.get_dft(row=p_row)
            stim_num = marker["stim"]
            t_row = df_t.loc[df_t["stim"] == stim_num].squeeze()
            t_stim = round(t_row["t_stim"], precision)
            # x: location on dfmean['time'], for acquiring y-values
            x_start = round(t_row["t_EPSP_amp"], precision)
            # event_x: location on event graph, for drawing event markers
            if not analysis.valid(x_start):
                print(
                    "ERROR - EPSP_amp_markers: invalid x_start or x_end in mouseoverUpdateMarkers"
                )
                print(type(x_start), x_start)
                return
            event_x_start = round(t_row["t_EPSP_amp"] - t_stim, precision)
            y_start = dfmean.loc[dfmean["time"] == x_start, "voltage"].values[0]
            marker["line"].set_data([event_x_start, event_x_start], [y_start, y_start])

        volley_slope_markers = {
            k: v
            for k, v in uistate.dict_rec_show.items()
            if k.endswith(" volley slope marker")
        }
        # print(f"mouseoverUpdateMarkers: {volley_slope_markers.keys()}")
        for marker in volley_slope_markers.values():
            p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
            dfmean = self.get_dfmean(row=p_row)
            df_t = self.get_dft(row=p_row)
            stim_num = marker["stim"]
            t_row = df_t.loc[df_t["stim"] == stim_num].squeeze()
            t_stim = round(t_row["t_stim"], precision)
            # x: location on dfmean['time'], for acquiring y-values
            x_start, x_end = (
                round(t_row["t_volley_slope_start"], precision),
                round(t_row["t_volley_slope_end"], precision),
            )
            # event_x: location on event graph, for drawing event markers
            if not analysis.valid(x_start, x_end):
                print(
                    "ERROR - volley_slope_markers: invalid x_start or x_end in mouseoverUpdateMarkers"
                )
                print(type(x_start), x_start)
                print(type(x_end), x_end)
                return
            event_x_start, event_x_end = (
                round(t_row["t_volley_slope_start"] - t_stim, precision),
                round(t_row["t_volley_slope_end"] - t_stim, precision),
            )
            y_start, y_end = (
                dfmean.loc[dfmean["time"] == x_start, "voltage"].values[0],
                dfmean.loc[dfmean["time"] == x_end, "voltage"].values[0],
            )
            marker["line"].set_data([event_x_start, event_x_end], [y_start, y_end])

        volley_amp_markers = {
            k: v
            for k, v in uistate.dict_rec_show.items()
            if k.endswith(" volley amp marker")
        }
        # print(f"mouseoverUpdateMarkers: {volley_amp_markers.keys()}")
        for marker in volley_amp_markers.values():
            p_row = df_p.loc[df_p["ID"] == marker["rec_ID"]].squeeze()
            dfmean = self.get_dfmean(row=p_row)
            df_t = self.get_dft(row=p_row)
            stim_num = marker["stim"]
            t_row = df_t.loc[df_t["stim"] == stim_num].squeeze()
            t_stim = round(t_row["t_stim"], precision)
            # x: location on dfmean['time'], for acquiring y-values
            x_start = round(t_row["t_volley_amp"], precision)
            # event_x: location on event graph, for drawing event markers
            if not analysis.valid(x_start):
                print(
                    "ERROR - volley_amp_markers: invalid x_start or x_end in mouseoverUpdateMarkers"
                )
                print(type(x_start), x_start)
                return
            event_x_start = round(t_row["t_volley_amp"] - t_stim, precision)
            y_start = dfmean.loc[dfmean["time"] == x_start, "voltage"].values[0]
            marker["line"].set_data([event_x_start, event_x_start], [y_start, y_start])

    def mouseoverDisconnect(self):
        self.usage("mouseoverDisconnect")
        # drop any prior mouseover event connections and plots
        if hasattr(self, "mouseover"):
            self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
            self.canvasOutput.mpl_disconnect(self.mouseoverOutput)
        if uistate.mouseover_plot is not None:
            uistate.mouseover_plot[0].remove()
            uistate.mouseover_plot = None
        if uistate.mouseover_blob is not None:
            uistate.mouseover_blob.remove()
            uistate.mouseover_blob = None
        if uistate.mouseover_out is not None:
            uistate.mouseover_out[0].remove()
            uistate.mouseover_out = None
        uistate.mouseover_action = None

    def eventDragSlope(
        self, event, action, data_x, data_y, prior_slope_start, prior_slope_end
    ):  # graph dragging event
        # self.usage("eventDragSlope")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None or action is None:
            return
        x = event.xdata
        uistate.x_drag = data_x[
            np.abs(data_x - x).argmin()
        ]  # time-value of the nearest index
        if (
            uistate.x_drag == uistate.x_drag_last
        ):  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = uistate.settings["precision"]
        time_diff = uistate.x_drag - uistate.x_on_click
        # get the x values of the slope
        blob = True  # only moving amplitudes and resizing slopes have a blob
        if action.endswith("resize"):
            x_start = prior_slope_start
        elif action.endswith("move"):
            x_start = round(prior_slope_start + time_diff, precision)
            blob = False
        x_end = round(prior_slope_end + time_diff, precision)
        # prevent resizing below 1 index - TODO: make it flip instead
        if x_end <= x_start:
            x_start_index = np.where(data_x == x_start)[0][0]
            x_end = data_x[x_start_index + 1]
        # get y values
        x_indices = np.searchsorted(data_x, [x_start, x_end])
        y_start, y_end = data_y[x_indices]
        # remember the last x index
        uistate.x_drag_last = uistate.x_drag
        # update the mouseover plot
        uistate.mouseover_plot[0].set_data([x_start, x_end], [y_start, y_end])
        if blob:
            uistate.mouseover_blob.set_offsets([x_end, y_end])
        self.canvasEvent.draw()
        self.eventDragUpdate(x_start, x_end, precision)

    def eventDragPoint(
        self, event, data_x, data_y, prior_amp
    ):  # maingraph dragging event
        # self.usage("eventDragPoint")
        self.canvasEvent.mpl_disconnect(self.mouseoverEvent)
        if event.xdata is None:
            return
        x = event.xdata
        uistate.x_drag = data_x[
            np.abs(data_x - x).argmin()
        ]  # time-value of the nearest index
        if (
            uistate.x_drag == uistate.x_drag_last
        ):  # if the dragged event hasn't moved an index point, change nothing
            return
        precision = uistate.settings["precision"]
        time_diff = uistate.x_drag - uistate.x_on_click
        x_point = round(prior_amp + time_diff, precision)
        idx = (np.abs(data_x - x_point)).argmin()
        y_point = data_y[idx]
        # print (f"x_point: {x_point}, y_point: {y_point}")
        # remember the last x index
        uistate.x_drag_last = uistate.x_drag
        # update the mouseover plot
        uistate.mouseover_blob.set_offsets([x_point, y_point])
        self.canvasEvent.draw()
        self.eventDragUpdate(x_point, x_point, precision)

    def eventDragUpdate(self, x_start, x_end, precision):
        # TODO: Overhaul this whole magic-string-mess
        """
        Updates output graph uistate.mouseover_out while dragging event markers
        x_start: new start time of slope or amplitude
        x_end: new end time of slope (same as x_start for amplitude)
        precision: number of decimal places to round to
        * updates uistate.dft_temp in place: overwrites dft on release
        * builds a dict_t and feeds it to analysis.build_dfoutput
        * updates uistate.mouseover_out plot data
        TODO: fix for dfstimoutput
        """

        # self.usage("eventDragUpdate")
        def handle_slope(aspect, x_start, x_end, precision, stim_offset):
            slope_width = round(x_end - x_start, precision)
            slope_start_key = f"t_{aspect}_start"
            slope_end_key = f"t_{aspect}_end"
            slope_width_key = f"t_{aspect}_width"
            return {
                slope_start_key: round(x_start + stim_offset, precision),
                slope_end_key: round(x_end + stim_offset, precision),
                slope_width_key: round(slope_width, precision),
            }

        def handle_amp(aspect, x_start, stim_offset, precision):
            amp_key = f"t_{aspect}"
            return {
                "t_stim": stim_offset,
                amp_key: round(x_start + stim_offset, precision),
            }

        action = uistate.mouseover_action
        aspect = "_".join(action.split()[:2])
        stim_idx = uistate.list_idx_select_stims[0]
        prow = self.get_prow()
        n_stims = prow["stims"]
        dft_temp = uistate.dft_temp  # set when clicked
        stim_offset = dft_temp.at[stim_idx, "t_stim"]
        dffilter = None
        dict_t = None

        if uistate.checkBox["output_per_stim"]:
            x_axis = "stim"
            dfmean = self.get_dfmean(row=prow)
        else:
            x_axis = "sweep"
            dffilter = self.get_dffilter(row=prow)
            dfmean = None

        if aspect in ["EPSP_slope", "volley_slope"]:
            axis = uistate.ax2
            dict_t = handle_slope(aspect, x_start, x_end, precision, stim_offset)
        elif aspect in ["EPSP_amp", "volley_amp"]:
            axis = uistate.ax1
            dict_t = handle_amp(aspect, x_start, stim_offset, precision)

        for key, value in dict_t.items():
            dft_temp.at[stim_idx, key] = value
            if (
                not uistate.checkBox["timepoints_per_stim"] and n_stims > 1
            ):  # update all timepoints in df_t
                offset = dft_temp.at[stim_idx, "t_stim"] - dft_temp.at[stim_idx, key]
                for i, i_trow in dft_temp.iterrows():
                    dft_temp.at[i, key] = round(i_trow["t_stim"] - offset, precision)

        trow_temp = dft_temp.iloc[stim_idx]
        dict_t["t_EPSP_amp_halfwidth"] = trow_temp["t_EPSP_amp_halfwidth"]
        dict_t["t_volley_amp_halfwidth"] = trow_temp["t_volley_amp_halfwidth"]
        dict_t["norm_output_from"] = trow_temp["norm_output_from"]
        dict_t["norm_output_to"] = trow_temp["norm_output_to"]

        if x_axis == "stim":
            print("eventDragUpdate: dfstimoutput removed from last analysis.")
            # TODO: fix eventDragUpdate for dfstimoutput
            # out = analysis.build_dfstimoutput(dfmean=dfmean, dft=dft_temp)
        elif x_axis == "sweep":
            dict_t["stim"] = trow_temp["stim"]
            dict_t["amp_zero"] = trow_temp["amp_zero"]
            out = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)

        # norm handling for EPSP
        if aspect in ["EPSP_amp", "EPSP_slope"]:
            aspect_norm = f"{aspect}_norm"
            outkey = aspect_norm if uistate.checkBox["norm_EPSP"] else aspect
            # print(f"eventDragUpdate - outkey {outkey}, {aspect}: t({trow_temp[f"t_{aspect}"]}) {out[aspect].iloc[0]}, {aspect_norm}: {out[aspect_norm].iloc[0]}")
        else:
            outkey = aspect
            # print(f"eventDragUpdate - outkey {outkey}, {aspect}: {out[aspect].iloc[0]}")

        if uistate.mouseover_out is None:
            uistate.mouseover_out = axis.plot(
                out[x_axis],
                out[outkey],
                color=uistate.settings[f"rgb_{aspect}"],
                linewidth=3,
            )
        else:
            uistate.mouseover_out[0].set_data(out[x_axis], out[outkey])

        self.canvasOutput.draw()

    def eventDragReleased(self, event, data_x, data_y):  # graph release event
        # TODO: Overhaul this whole magic-string-mess
        self.usage("eventDragReleased")
        print(f" - uistate.mouseover_action: {uistate.mouseover_action}")
        self.canvasEvent.mpl_disconnect(self.mouse_drag)
        self.canvasEvent.mpl_disconnect(self.mouse_release)
        uistate.x_drag_last = None
        if uistate.x_drag == uistate.x_on_click:  # nothing to update
            print("x_drag == x_on_click")
            self.mouseoverUpdate()
            return

        dft_temp = uistate.dft_temp  # copied on clicked, updated while dragging
        stim_idx = uistate.list_idx_select_stims[0]
        trow_temp = dft_temp.iloc[stim_idx]

        # Map drag actions to (0:method value, 1:aspect name, 2:{new measuring points}, 3:plot update function)
        action_mapping = {
            "EPSP slope": (
                "t_EPSP_slope_method",
                "EPSP slope",
                {
                    "t_EPSP_slope_start": trow_temp["t_EPSP_slope_start"],
                    "t_EPSP_slope_end": trow_temp["t_EPSP_slope_end"],
                },
                uistate.updateDragZones,
            ),
            "EPSP amp move": (
                "t_EPSP_amp_method",
                "EPSP amp",
                {
                    "t_EPSP_amp": trow_temp["t_EPSP_amp"],
                    "t_EPSP_amp_halfwidth": trow_temp["t_EPSP_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                uistate.updatePointDragZone,
            ),
            "volley slope": (
                "t_volley_slope_method",
                "volley slope",
                {
                    "t_volley_slope_start": trow_temp["t_volley_slope_start"],
                    "t_volley_slope_end": trow_temp["t_volley_slope_end"],
                },
                uistate.updateDragZones,
            ),
            "volley amp move": (
                "t_volley_amp_method",
                "volley amp",
                {
                    "t_volley_amp": trow_temp["t_volley_amp"],
                    "t_volley_amp_halfwidth": trow_temp["t_volley_amp_halfwidth"],
                    "amp_zero": trow_temp["amp_zero"],
                },
                uistate.updatePointDragZone,
            ),
        }
        # Build a dict_t of new measuring points and update drag zones
        for action, values in action_mapping.items():
            if uistate.mouseover_action.startswith(action):
                method_field = values[0]
                aspect = values[1]
                dict_t_updates = values[2]
                update_function = values[3]
                dict_t_updates[method_field] = "manual"
                dict_t_updates.update(
                    {
                        "stim": trow_temp["stim"],
                        "t_stim": trow_temp["t_stim"],
                        "norm_output_from": trow_temp["norm_output_from"],
                        "norm_output_to": trow_temp["norm_output_to"],
                    }
                )
                update_function()
                break

        # update selected row of dft_temp with the values from dict_t
        for key, value in dict_t_updates.items():
            dft_temp.loc[dft_temp.index[stim_idx], key] = value
            # old_trow = self.get_trow()
            # print(f" - * - stim{old_trow['stim']} {key} was {old_trow[key]}, set to {dft_temp.loc[dft_temp.index[stim_idx], key]}.")

        prow = self.get_prow()
        rec_name = prow["recording_name"]
        dfmean = self.get_dfmean(row=prow)

        # update dfoutput; dict and file, with normalized columns if applicable
        if False:  # uistate.checkBox['output_per_stim']:
            dfoutput = analysis.build_dfstimoutput(df=dfmean, df_t=dft_temp)
        else:
            dfoutput = self.get_dfoutput(row=prow)
            dffilter = self.get_dffilter(row=prow)
            stim_num = trow_temp["stim"]
            new_dfoutput = analysis.build_dfoutput(df=dffilter, dict_t=dict_t_updates)
            # print(f"dfoutput: {dfoutput}")
            # update volley means
            if aspect == "volley amp":
                dft_temp.loc[dft_temp.index[stim_idx], "volley_amp_mean"] = (
                    new_dfoutput["volley_amp"].mean()
                )
            elif aspect == "volley slope":
                dft_temp.loc[dft_temp.index[stim_idx], "volley_slope_mean"] = (
                    new_dfoutput["volley_slope"].mean()
                )

            new_dfoutput["stim"] = int(stim_num)
            for col in new_dfoutput.columns:
                dfoutput.loc[dfoutput["stim"] == stim_num, col] = new_dfoutput.loc[
                    new_dfoutput["stim"] == stim_num, col
                ]

        self.persistOutput(rec_name=rec_name, dfoutput=dfoutput)

        self.set_dft(rec_name, dft_temp)
        self.tableStimModel.setData(self.get_dft(prow))
        self.set_rec_status(rec_name=rec_name)
        trow = self.get_trow()
        uiplot.update(prow=prow, trow=trow, aspect=aspect, data_x=data_x, data_y=data_y)

        def update_amp_marker(trow, aspect, prow, dfmean, dfoutput):
            labelbase = f"{rec_name} - stim {trow['stim']}"
            labelamp = f"{labelbase} {aspect}"
            column_name = aspect.replace(" ", "_")
            t_aspect = f"t_{column_name}"
            stim_offset = trow["t_stim"]
            x = trow[t_aspect] - stim_offset
            y = dfmean.loc[dfmean["time"] == trow[t_aspect], prow["filter"]].values[0]
            amp = (
                dfoutput.loc[dfoutput["stim"] == trow["stim"]][column_name].mean()
                / 1000
            )  # conversion: mV to V
            t_amp = trow[t_aspect] - stim_offset
            amp_x = (
                t_amp - trow[f"{t_aspect}_halfwidth"],
                t_amp + trow[f"{t_aspect}_halfwidth"],
            )
            uiplot.updateAmpMarker(labelamp, x, y, amp_x, trow["amp_zero"], amp=amp)

        if aspect in ["EPSP amp", "volley amp"]:
            # print(f" - {aspect} updated")
            if False:  # uistate.checkBox['timepoints_per_stim']:
                update_amp_marker(trow, aspect, prow, dfmean, dfoutput)
            else:
                dft = self.get_dft(prow)
                for i, i_trow in dft.iterrows():
                    update_amp_marker(i_trow, aspect, prow, dfmean, dfoutput)

        # update groups
        affected_groups = self.get_groupsOfRec(prow["ID"])
        self.group_cache_purge(affected_groups)
        for group_ID in affected_groups:
            df_groupmean = self.get_dfgroupmean(group_ID)
            uiplot.addGroup(group_ID, self.dd_groups[group_ID], df_groupmean)
        self.mouseoverUpdate()

        if config.talkback:
            self.talkback()

    def zoomOnScroll(self, event, graph):
        if graph == "mean":
            canvas = self.canvasMean
            ax = uistate.axm
        elif graph == "event":
            canvas = self.canvasEvent
            ax = uistate.axe
        elif graph == "output":
            canvas = self.canvasOutput
            slope_left = uistate.slopeOnly()
            ax = uistate.ax2
            ax1 = uistate.ax1

        if event.button == "up":
            zoom = 1.1
        else:
            zoom = 1 / 1.1

        if (
            event.xdata is None or event.ydata is None
        ):  # if the scroll event was outside the axes, extrapolate x and y
            x_display, y_display = ax.transAxes.inverted().transform((event.x, event.y))
            x = x_display * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
            y = y_display * (ax.get_ylim()[1] - ax.get_ylim()[0]) + ax.get_ylim()[0]
        else:
            x = event.xdata
            y = event.ydata

        left = 0.12 * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
        right = 0.88 * (ax.get_xlim()[1] - ax.get_xlim()[0]) + ax.get_xlim()[0]
        bottom = 0.08 * (ax.get_ylim()[1] - ax.get_ylim()[0]) + ax.get_ylim()[0]
        on_x = y <= bottom
        on_left = x <= left
        on_right = x >= right

        # Apply the zoom
        ymin0 = uistate.checkBox["output_ymin0"]
        if on_x:  # check this first; x takes precedence
            ax.set_xlim(
                x - (x - ax.get_xlim()[0]) / zoom, x + (ax.get_xlim()[1] - x) / zoom
            )
        elif "slope_left" in locals():  # on output
            if on_left:
                if slope_left:  # scroll left y zoom output slope y
                    ymin = (
                        0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom
                    )  # TODO: uistate.checkBox...
                    ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
                else:  # scroll left y to zoom output amp y
                    ymin = (
                        0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom
                    )  # TODO: uistate.checkBox...
                    ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
            elif on_right and not slope_left:  # scroll right y to zoom output slope y
                ymin = (
                    0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom
                )  # TODO: uistate.checkBox...
                ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
            else:  # default, scroll graph to zoom all
                ax1.set_xlim(
                    x - (x - ax1.get_xlim()[0]) / zoom,
                    x + (ax1.get_xlim()[1] - x) / zoom,
                )
                ymin = (
                    0 if ymin0 else y - (y - ax1.get_ylim()[0]) / zoom
                )  # TODO: uistate.checkBox...
                ax1.set_ylim(ymin, y + (ax1.get_ylim()[1] - y) / zoom)
                ymin = (
                    0 if ymin0 else y - (y - ax.get_ylim()[0]) / zoom
                )  # TODO: uistate.checkBox...
                ax.set_ylim(ymin, y + (ax.get_ylim()[1] - y) / zoom)
        else:  # on mean or event graphs
            if on_left:  # scroll left x to zoom mean or event x
                ax.set_ylim(
                    y - (y - ax.get_ylim()[0]) / zoom, y + (ax.get_ylim()[1] - y) / zoom
                )
            else:
                ax.set_xlim(
                    x - (x - ax.get_xlim()[0]) / zoom, x + (ax.get_xlim()[1] - x) / zoom
                )
                ax.set_ylim(
                    y - (y - ax.get_ylim()[0]) / zoom, y + (ax.get_ylim()[1] - y) / zoom
                )

        # TODO: this block is dev visualization for debugging
        if False:
            if hasattr(ax, "hline"):  # If the line exists, update it
                ax.hline.set_ydata(bottom)
            else:  # Otherwise, create a new line
                ax.hline = ax.axhline(y=bottom, color="r", linestyle="--")

        canvas.draw()

    # pyqtSlot decorators
    @QtCore.pyqtSlot()
    def slotAddDfData(self, df):
        self.addData(df)


# Root functions


def get_signals(source):
    cls = source if isinstance(source, type) else type(source)
    signal = type(QtCore.pyqtSignal())
    print("get_signals:")
    for subcls in cls.mro():
        clsname = f"{subcls.__module__}.{subcls.__name__}"
        for key, aspect in sorted(vars(subcls).items()):
            if isinstance(aspect, signal):
                print(f"{key} [{clsname}]")


def df_projectTemplate():
    return pd.DataFrame(
        columns=[
            "ID",  # str: unique identifier for recording
            "host",  # str: computer name
            "path",  # str: path of original source file
            "status",  # str: blank if ok, 'default' is default recordings. TODO: add more states
            "recording_name",  # str: name of recording
            "stims",  # int: number of stims in recording
            "sweeps",  # int: number of sweeps in recording
            "sweep_duration",  # float: duration of each sweep in seconds
            "resets",  # str: list of number of first sweep in source file, for breaking up tables of non-continuous recordings
            "filter",  # str: filter used for analysis
            "filter_params",  # str: filter parameters
            "groups",  # str: group name(s); maintained by uisub.dfgroups and its functions
            "parsetimestamp",  # str: timestamp of parsing of original source file
            "channel",  # str: this recording is only from this channel
            "stim",  # str: this recording is only from this stim (a/b)
            "paired_recording",  # str: unique ID of paired recording
            "Tx",  # Boolean: Treatment / Control, for paired recordings
            "exclude",  # Boolean: If True, exclude this recording from analysis
            "comment",  # str: user comment
        ]
    )


# Mainguard
if __name__ == "__main__":
    print(f"\n\n{config.program_name} {config.version}\n")
    app = QtWidgets.QApplication(
        sys.argv
    )  # "QtWidgets.QApplication(sys.argv) appears to cause Qt: Session management error: None of the authentication protocols specified are supported"
    main_window = QtWidgets.QMainWindow()
    uisub = UIsub(main_window)
    main_window.show()
    sys.exit(app.exec_())
