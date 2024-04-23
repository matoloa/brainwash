import os  # TODO: replace use by pathlib?
import sys
from pathlib import Path
import yaml
from PyQt5 import QtCore, QtWidgets, QtGui
import numpy as np
import pandas as pd

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import use as matplotlib_use
from matplotlib.figure import Figure

from datetime import datetime # used in project name defaults
import json # for saving and loading dicts as strings
import re # regular expressions
import time # counting time for functions
import uuid # generating unique talkback ID
import socket # getting computer name and localdomain for df_project['host'] (not reported in talkback)
import toml # for reading pyproject.toml
import importlib # for reloading modules

import parse
import analysis
import ui_state_classes
import ui_plot

matplotlib_use("Qt5Agg")


class Config:
    def __init__(self):
        self.dev_mode = True # Development mode
        #self.dev_mode = False # Deploy mode
        print("\n"*3)
        if self.dev_mode:
            print(f"Config set for development mode - {time.strftime('%H:%M:%S')}")
        self.verbose = self.dev_mode
        self.talkback = not self.dev_mode
        self.hide_experimental = not self.dev_mode
        self.track_widget_focus = False
        self.terminal_space = 372 if self.dev_mode else 0
        # get project_name and version number from pyproject.toml
        pathtoml = [i + "/pyproject.toml" for i in ["..", ".", "lib"] if Path(i + "/pyproject.toml").is_file()][0]
        pyproject = toml.load(pathtoml)
        self.program_name = pyproject['project']['name']
        self.version = pyproject['project']['version']

config = Config() 
uistate = ui_state_classes.UIstate() # global variable for storing state of UI
importlib.reload(ui_plot)
uiplot = ui_plot.UIplot(uistate)


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
        if not data is None and type(data) is pd.DataFrame:
            self.beginResetModel()
            self._data = data
            self.endResetModel()
            return True
        return False


class FileTreeSelectorModel(QtWidgets.QFileSystemModel):  # Should be paired with a FileTreeSelectorView
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
        return QtWidgets.QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

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
    rightClicked = QtCore.pyqtSignal(str)  # Define a new signal that carries a string
    def __init__(self, str_ID, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.str_ID = str_ID
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit(self.str_ID)
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
        percentage = int((i) * 100 / self.total)
        self.progressBar.setValue(percentage)
        self.progressBar.setFormat(f"{task_description} {i + 1} / {self.total}:   %p% complete")


class ParseDataThread(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)

    def __init__(self, df_p_to_update, dict_folders):
        super().__init__()
        self.df_p_to_update = df_p_to_update
        self.dict_folders = dict_folders
        self.rows = []
        self.total = len(df_p_to_update)

    def create_new_row(self, df_proj_row, new_name, dict_sub):
        df_proj_new_row = df_proj_row.copy()
        df_proj_new_row['ID'] = uuid.uuid4()
        df_proj_new_row['recording_name'] = new_name
        df_proj_new_row['sweeps'] = dict_sub.get('nsweeps', None)
        df_proj_new_row['channel'] = dict_sub.get('channel', None)
        df_proj_new_row['stim'] = dict_sub.get('stim', None)
        return df_proj_new_row

    def run(self):
        for i, (_, df_proj_row) in enumerate(self.df_p_to_update.iterrows()):
            self.progress.emit(i)
            recording_name = df_proj_row['recording_name']
            source_path = df_proj_row['path']
            dict_data = parse.parseProjFiles(dict_folders = self.dict_folders, recording_name=recording_name, source_path=source_path)
            for new_name, dict_sub in dict_data.items():
                nsweeps = dict_sub.get('nsweeps', None) 
                if nsweeps is not None:
                    df_proj_new_row = self.create_new_row(df_proj_row, new_name, dict_sub)
                    self.rows.append(df_proj_new_row)


class GraphMainPreloadThread(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int)

    def __init__(self, uistate, uiplot, uisub):
        super().__init__()
        self.uistate = uistate
        self.uiplot = uiplot
        self.uisub = uisub
        self.df_p = self.uisub.get_df_project()
        self.i = 0

    def run(self):
        df = self.df_p.loc[self.uistate.new_indices]
        self.uistate.new_indices = []
        self.i = 0
        for i, row in df.iterrows():
            dfmean = self.uisub.get_dfmean(row=row)
            _ = self.uisub.get_dffilter(row=row)
            if self.uistate.checkBox['paired_stims']:
                dfoutput = self.uisub.get_dfdiff(row=row)
            else:
                dfoutput = self.uisub.get_dfoutput(row=row)
            if dfoutput is None:
                return
            row = self.df_p.loc[i] # get_dfoutput updates df_project - update row!
            self.uiplot.addRow(dict_row=row.to_dict(), dfmean=dfmean, dfoutput=dfoutput)
            self.progress.emit(i)
            self.i += 1
            print(f"Preloaded {row['recording_name']}")
        self.finished.emit()



################################################################
# section directly copied from output from pyuic, do not alter #
# trying to make all the rest work with it                     #
# WARNING: I was forced to change the parent class from        #
# 'object' to 'QtCore.QObject' for the pyqtSlot(list) to work  #
################################################################

class Ui_MainWindow(QtCore.QObject):
    def setupUi(self, mainWindow):
        mainWindow.setObjectName("mainWindow")
        mainWindow.resize(1215, 717)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName("horizontalLayoutCentralwidget")
        self.verticalMasterLayout = QtWidgets.QVBoxLayout()
        self.verticalMasterLayout.setObjectName("verticalMasterLayout")
        self.horizontalMasterLayout = QtWidgets.QHBoxLayout()
        self.horizontalMasterLayout.setObjectName("horizontalMasterLayout")
        self.verticalLayoutProj = QtWidgets.QVBoxLayout()
        self.verticalLayoutProj.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.verticalLayoutProj.setObjectName("verticalLayoutProj")
        self.horizontalLayoutProj = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProj.setObjectName("horizontalLayoutProj")
        self.pushButtonParse = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonParse.setObjectName("pushButtonParse")
        self.horizontalLayoutProj.addWidget(self.pushButtonParse)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutProj)
        self.tableProj = QtWidgets.QTableView(self.centralwidget)
        self.tableProj.setMinimumSize(QtCore.QSize(420, 0))
        self.tableProj.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.tableProj.setAcceptDrops(True)
        self.tableProj.setObjectName("tableProj")
        self.verticalLayoutProj.addWidget(self.tableProj)
        self.horizontalMasterLayout.addLayout(self.verticalLayoutProj)
        spacerItem = QtWidgets.QSpacerItem(10, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalMasterLayout.addItem(spacerItem)
        self.verticalLayoutGraph = QtWidgets.QVBoxLayout()
        self.verticalLayoutGraph.setObjectName("verticalLayoutGraph")
        self.graphMean = QtWidgets.QWidget(self.centralwidget)
        self.graphMean.setMinimumSize(QtCore.QSize(100, 100))
        self.graphMean.setObjectName("graphMean")
        self.verticalLayoutGraph.addWidget(self.graphMean)
        self.horizontalLayoutControls = QtWidgets.QHBoxLayout()
        self.horizontalLayoutControls.setObjectName("horizontalLayoutControls")
        self.verticalLayoutGraph.addLayout(self.horizontalLayoutControls)
        self.horizontalLayoutGroups = QtWidgets.QHBoxLayout()
        self.horizontalLayoutGroups.setObjectName("horizontalLayoutGroups")
        self.verticalLayoutGraph.addLayout(self.horizontalLayoutGroups)
        self.graphOutput = QtWidgets.QWidget(self.centralwidget)
        self.graphOutput.setMinimumSize(QtCore.QSize(100, 100))
        self.graphOutput.setObjectName("graphOutput")
        self.verticalLayoutGraph.addWidget(self.graphOutput)
        self.verticalLayoutGraph.setStretch(0, 5)
        self.verticalLayoutGraph.setStretch(3, 5)
        self.horizontalMasterLayout.addLayout(self.verticalLayoutGraph)
        self.tableMetadata = QtWidgets.QTableView(self.centralwidget)
        self.tableMetadata.setObjectName("tableMetadata")
        self.horizontalMasterLayout.addWidget(self.tableMetadata)
        self.horizontalMasterLayout.setStretch(2, 1)
        self.verticalMasterLayout.addLayout(self.horizontalMasterLayout)
        self.addonFrame = QtWidgets.QFrame(self.centralwidget)
        self.addonFrame.setMinimumSize(QtCore.QSize(0, 120))
        self.addonFrame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.addonFrame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.addonFrame.setObjectName("addonFrame")
        self.checkBox_EPSP_amp = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_EPSP_amp.setGeometry(QtCore.QRect(10, 50, 101, 23))
        self.checkBox_EPSP_amp.setObjectName("checkBox_EPSP_amp")
        self.checkBox_EPSP_slope = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_EPSP_slope.setGeometry(QtCore.QRect(10, 30, 101, 23))
        self.checkBox_EPSP_slope.setObjectName("checkBox_EPSP_slope")
        self.label_aspect = QtWidgets.QLabel(self.addonFrame)
        self.label_aspect.setGeometry(QtCore.QRect(10, 10, 62, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_aspect.setFont(font)
        self.label_aspect.setObjectName("label_aspect")
        self.checkBox_paired_stims = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_paired_stims.setGeometry(QtCore.QRect(288, 30, 90, 23))
        self.checkBox_paired_stims.setObjectName("checkBox_paired_stims")
        self.label_paired_data = QtWidgets.QLabel(self.addonFrame)
        self.label_paired_data.setGeometry(QtCore.QRect(288, 10, 91, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_paired_data.setFont(font)
        self.label_paired_data.setObjectName("label_paired_data")
        self.pushButton_paired_data_flip = QtWidgets.QPushButton(self.addonFrame)
        self.pushButton_paired_data_flip.setGeometry(QtCore.QRect(290, 50, 81, 25))
        self.pushButton_paired_data_flip.setObjectName("pushButton_paired_data_flip")
        self.checkBox_volley_amp = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_volley_amp.setGeometry(QtCore.QRect(10, 90, 101, 23))
        self.checkBox_volley_amp.setObjectName("checkBox_volley_amp")
        self.checkBox_volley_slope = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_volley_slope.setGeometry(QtCore.QRect(10, 70, 101, 23))
        self.checkBox_volley_slope.setObjectName("checkBox_volley_slope")
        self.label_scaling = QtWidgets.QLabel(self.addonFrame)
        self.label_scaling.setGeometry(QtCore.QRect(140, 10, 81, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_scaling.setFont(font)
        self.label_scaling.setObjectName("label_scaling")
        self.checkBox_norm_EPSP = QtWidgets.QCheckBox(self.addonFrame)
        self.checkBox_norm_EPSP.setGeometry(QtCore.QRect(140, 30, 111, 23))
        self.checkBox_norm_EPSP.setObjectName("checkBox_norm_EPSP")
        self.lineEdit_norm_EPSP_start = QtWidgets.QLineEdit(self.addonFrame)
        self.lineEdit_norm_EPSP_start.setGeometry(QtCore.QRect(140, 70, 41, 25))
        self.lineEdit_norm_EPSP_start.setObjectName("lineEdit_norm_EPSP_start")
        self.label_norm_on_sweep = QtWidgets.QLabel(self.addonFrame)
        self.label_norm_on_sweep.setGeometry(QtCore.QRect(140, 50, 131, 20))
        self.label_norm_on_sweep.setAlignment(QtCore.Qt.AlignBottom|QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft)
        self.label_norm_on_sweep.setObjectName("label_norm_on_sweep")
        self.lineEdit_norm_EPSP_end = QtWidgets.QLineEdit(self.addonFrame)
        self.lineEdit_norm_EPSP_end.setGeometry(QtCore.QRect(200, 70, 41, 25))
        self.lineEdit_norm_EPSP_end.setObjectName("lineEdit_norm_EPSP_end")
        self.label_export = QtWidgets.QLabel(self.addonFrame)
        self.label_export.setGeometry(QtCore.QRect(410, 10, 81, 17))
        font = QtGui.QFont()
        font.setFamily("DejaVu Sans")
        font.setBold(True)
        font.setWeight(75)
        self.label_export.setFont(font)
        self.label_export.setObjectName("label_export")
        self.pushButton_export_jpeg = QtWidgets.QPushButton(self.addonFrame)
        self.pushButton_export_jpeg.setGeometry(QtCore.QRect(410, 30, 41, 25))
        self.pushButton_export_jpeg.setObjectName("pushButton_export_jpeg")
        self.label_relative_to = QtWidgets.QLabel(self.addonFrame)
        self.label_relative_to.setGeometry(QtCore.QRect(190, 70, 21, 20))
        self.label_relative_to.setAlignment(QtCore.Qt.AlignBottom|QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft)
        self.label_relative_to.setObjectName("label_relative_to")
        self.verticalMasterLayout.addWidget(self.addonFrame)
        self.progressBar = QtWidgets.QProgressBar(self.centralwidget)
        self.progressBar.setProperty("value", 24)
        self.progressBar.setObjectName("progressBar")
        self.verticalMasterLayout.addWidget(self.progressBar)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalMasterLayout)
        mainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(mainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1215, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuData = QtWidgets.QMenu(self.menubar)
        self.menuData.setObjectName("menuData")
        self.menuGroups = QtWidgets.QMenu(self.menubar)
        self.menuGroups.setObjectName("menuGroups")
        self.menuEdit = QtWidgets.QMenu(self.menubar)
        self.menuEdit.setObjectName("menuEdit")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuData.menuAction())
        self.menubar.addAction(self.menuGroups.menuAction())

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)

    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash"))
        self.pushButtonParse.setText(_translate("mainWindow", "Import"))
        self.checkBox_EPSP_amp.setText(_translate("mainWindow", "EPSP amp."))
        self.checkBox_EPSP_slope.setText(_translate("mainWindow", "EPSP slope"))
        self.label_aspect.setText(_translate("mainWindow", "Aspect"))
        self.checkBox_paired_stims.setText(_translate("mainWindow", "stim / stim"))
        self.label_paired_data.setText(_translate("mainWindow", "Paired data"))
        self.pushButton_paired_data_flip.setText(_translate("mainWindow", "Flip C-I"))
        self.checkBox_volley_amp.setText(_translate("mainWindow", "volley amp."))
        self.checkBox_volley_slope.setText(_translate("mainWindow", "volley slope"))
        self.label_scaling.setText(_translate("mainWindow", "Scaling"))
        self.checkBox_norm_EPSP.setText(_translate("mainWindow", "Relative"))
        self.label_norm_on_sweep.setText(_translate("mainWindow", "Norm on sweep(s)"))
        self.label_export.setText(_translate("mainWindow", "Export"))
        self.pushButton_export_jpeg.setText(_translate("mainWindow", "jpeg"))
        self.label_relative_to.setText(_translate("mainWindow", "-"))
        self.menuFile.setTitle(_translate("mainWindow", "File"))
        self.menuData.setTitle(_translate("mainWindow", "Data"))
        self.menuGroups.setTitle(_translate("mainWindow", "Groups"))
        self.menuEdit.setTitle(_translate("mainWindow", "Edit"))


################################################################
#        Hide elements that appear only on request             #
################################################################
        self.pushButtonParse.setVisible(False) # explicit hide command required for Windows, but not Linux (?)
        self.progressBar.setVisible(False)
        self.progressBar.setValue(0)
#       also hide experimental features (for deploy)
        if config.hide_experimental:
            self.label_paired_data.setVisible(False)
            self.pushButton_paired_data_flip.setVisible(False)
            self.checkBox_paired_stims.setVisible(False)



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
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
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
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal, self)
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
            dfAdd['path'] = file_urls # needs to be first, as it sets the number of rows
            dfAdd['host'] = str(self.parent.fqdn)
            dfAdd['filter'] = "voltage"
            # NTH: more intelligent default naming; lowest level unique name?
            # For now, use name + lowest level folder
            names = []
            duplicates = [] # remove these from dfAdd
            for i in file_urls:
                # check if file is already in df_project
                if i in self.parent.df_project['path'].values:
                    print(f"File {i} already in df_project")
                    duplicates.append(i)
                else:
                    names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
            if not names:
                print("No new files to add.")
                return
            dfAdd = dfAdd.drop(dfAdd[dfAdd['path'].isin(duplicates)].index)
            dfAdd['recording_name'] = names
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

        # Dataframe to addamp
        self.names = []
        self.dfAdd = df_projectTemplate()

        self.buttonBoxAddGroup = QtWidgets.QDialogButtonBox(dialog)
        self.buttonBoxAddGroup.setGeometry(QtCore.QRect(470, 20, 91, 491))
        self.buttonBoxAddGroup.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBoxAddGroup.setOrientation(QtCore.Qt.Vertical)
        self.buttonBoxAddGroup.setStandardButtons(QtWidgets.QDialogButtonBox.NoButton)
        self.buttonBoxAddGroup.setObjectName("buttonBoxAddGroup")

        self.ftree.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)
        self.ftree.model.paths_selected.connect(self.pathsSelectedUpdateTable)
        self.buttonBox.accepted.connect(self.addDf)

        self.tablemodel = TableModel(self.dfAdd)
        self.tableView.setModel(self.tablemodel)

    def addDf(self):
        self.parent.slotAddDfData(self.dfAdd)

    def pathsSelectedUpdateTable(self, paths):
        # TODO: Extract host and group
        dfAdd = df_projectTemplate()
        dfAdd['path'] = paths
        dfAdd['host'] = str(self.parent.fqdn)
        dfAdd['filter'] = "voltage"
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
        dfAdd['recording_name'] = names
        self.dfAdd = dfAdd
        # TODO: Add a loop that prevents duplicate names by adding a number until it becomes unique
        # TODO: names that have been set manually are stored a dict that persists while the addData window is open: this PATH should be replaced with this NAME (applied after default-naming, above)
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
        self.setupUi(mainwindow)
        if config.verbose:
            print(" - UIsub init, verbose mode")  # rename for clarity
        # move mainwindow to default position (TODO: later to be stored in cfg)
        self.mainwindow = mainwindow
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.mainwindow.setGeometry(0, 0, int(screen.width()*0.96), int(screen.height())-config.terminal_space)

        self.read_bw_cfg() # load bw global config file (not project specific)


        # set window title to projectname
        self.mainwindow.setWindowTitle(f"Brainwash {config.version} - {self.projectname}")

#       File menu
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

#       Edit menu
        self.actionUndo = QtWidgets.QAction("Undo (coming soon)", self)
        #self.actionUndo.triggered.connect(self.triggerUndo)
        self.actionUndo.setShortcut("Ctrl+Z")
        self.menuEdit.addAction(self.actionUndo)
        self.actionDarkmode = QtWidgets.QAction("Toggle Darkmode", self)
        self.actionDarkmode.triggered.connect(self.triggerDarkmode)
        self.actionDarkmode.setShortcut("Ctrl+D")
        self.menuEdit.addAction(self.actionDarkmode)

#       Data menu
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

#       Group menu
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
    
        # Make sure the necessary folders exist
        self.dict_folders = self.build_dict_folders()
        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)
        if not os.path.exists(self.dict_folders['cache']):
            os.makedirs(self.dict_folders['cache'])
        if not os.path.exists(self.dict_folders['timepoints']):
            os.makedirs(self.dict_folders['timepoints'])

        # replacing table proj with custom to allow custom drag and drop TODO: better way?
        originalTableView = self.centralwidget.findChild(QtWidgets.QTableView, "tableProj")  # Find and replace the original QTableView in the layout
        tableProj = TableProjSub(parent=self)  # Create an instance of your custom table view
        
        # Replace the original QTableView with TableProjSub in the layout
        layout = self.centralwidget.layout()
        layout.replaceWidget(originalTableView, tableProj)
        layout.removeWidget(originalTableView)

        # Update the layout
        layout.update()
        self.tableProj = tableProj
        tableProj.setObjectName("tableProj")

        self.df_project = df_projectTemplate()
        self.tablemodel = TableModel(self.df_project)
        self.tableProj.setModel(self.tablemodel)

        self.resetCacheDicts() # Clear internal storage dicts
       
        # If local project.brainwash exists, load it, otherwise create it
        if Path(self.dict_folders['project'] / "project.brainwash").exists():
            self.load_df_project()
        else:
            print(f"Project file {self.dict_folders['project'] / 'project.brainwash'} not found, creating new project file")
            self.write_bw_cfg()

        # If local project.cfg exists, load it, otherwise create it
        uistate.load_cfg(projectfolder=self.dict_folders['project'], bw_version=config.version)

        # make the graphs scaleable
        self.graphMean.setLayout(QtWidgets.QVBoxLayout())
        self.main_canvas_mean = MplCanvas(parent=self.graphMean)  # instantiate canvas for Mean
        self.graphMean.layout().addWidget(self.main_canvas_mean)
        self.graphOutput.setLayout(QtWidgets.QVBoxLayout())
        self.main_canvas_output = MplCanvas(parent=self.graphOutput)  # instantiate canvas for Output
        self.graphOutput.layout().addWidget(self.main_canvas_output)
        self.main_canvas_mean.mpl_connect('button_press_event', lambda event: self.mainClicked(event, self.main_canvas_mean))
        self.main_canvas_output.mpl_connect('button_press_event', lambda event: self.mainClicked(event, self.main_canvas_output, out=True))
        self.main_canvas_mean.show()
        self.main_canvas_output.show()

        # tableProj
        self.pushButtonParse.pressed.connect(self.triggerParse)
        self.tableProj.setSelectionBehavior(TableProjSub.SelectRows)
        selection_model = self.tableProj.selectionModel()
        selection_model.selectionChanged.connect(self.tableProjSelectionChanged)

        self.groupControlsRefresh() # add group controls to UI
        self.connectUIstate() # connect UI elements to uistate

        # connect paired stim checkbox and flip button to local functions
        #self.checkBox_paired_stims.setChecked(uistate.checkBox['paired_stims'])
        #self.checkBox_paired_stims.stateChanged.connect(lambda state: self.checkBox_paired_stims_changed(state))
        #self.pushButton_paired_data_flip.pressed.connect(self.pushButton_paired_data_flip_pressed)

        # connect Relative checkbox and lineedits to local functions
        norm = uistate.checkBox['norm_EPSP']
        self.label_norm_on_sweep.setVisible(norm)
        self.label_relative_to.setVisible(norm)
        self.lineEdit_norm_EPSP_start.setVisible(norm)
        self.lineEdit_norm_EPSP_end.setVisible(norm)
        self.lineEdit_norm_EPSP_start.setText(f"{uistate.lineEdit['norm_EPSP_on'][0]}")
        self.lineEdit_norm_EPSP_end.setText(f"{uistate.lineEdit['norm_EPSP_on'][1]}")
        self.lineEdit_norm_EPSP_start.editingFinished.connect(lambda: self.editNormRange(self.lineEdit_norm_EPSP_start))
        self.lineEdit_norm_EPSP_end.editingFinished.connect(lambda: self.editNormRange(self.lineEdit_norm_EPSP_end))

        self.fqdn = socket.getfqdn() # get computer name and local domain, for project file
        if config.talkback:
            path_usage = Path(f"{self.projects_folder}/talkback/usage.yaml")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if path_usage.exists():
                with path_usage.open("r") as file:
                    self.dict_usage = yaml.safe_load(file)
                self.dict_usage[f"last_used_{config.version}"] = now
            else:
                os_name = sys.platform
                self.dict_usage = {'WARNING': "Do NOT set your alias to anything that can be used to identify you!", 'alias': "", 'ID': str(uuid.uuid4()), 'os': os_name, 'ID_created': now, f"last_used_{config.version}": now}
            self.write_usage()

        # Set up the timepoints table, on metadata table for now
        # TODO: WIP timepoint table
        #self.df_times = df_timepointsTemplate()
        self.timesmodel = TableModel(df_timepointsTemplate())
        self.tableMetadata.setModel(self.timesmodel)
        self.tableMetadata.verticalHeader().hide()

        # Set up axes for the graphs
        self.graphMainAxes()
        self.darkmode() # set darkmode if set in bw_cfg

        # debug mode; prints widget focus every 1000ms
        if config.track_widget_focus:
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.checkFocus)
            self.timer.start(1000)


    # Debugging tools
            # self.find_widgets_with_top_left_coordinates(self.centralwidget)

    def find_widgets_with_top_left_coordinates(self, widget):
        print(f"trying child geometry")
        for child in widget.findChildren(QtWidgets.QWidget):
            #print(f"attribs: {dir(child.geometry())}")
            print(f"child.geometry(): {child.objectName()}, {child.geometry().topLeft()},  {child.mapTo(self.centralwidget, child.geometry().topLeft())}, {child.geometry().size()}")

    def checkFocus(self):
        focused_widget = QtWidgets.QApplication.focusWidget()
        if focused_widget is not None:
            print(f"Focused Widget: {focused_widget.objectName()}")
        else:
            print("No widget has focus.")



# WIP: TODO: move these to appropriate header in this file


    def talkback(self):
        row = uistate.row_copy
        dfmean = self.dfmean

        t_stim = row['t_stim']
        t_start = t_stim - 0.002
        t_end = t_stim + 0.018
        dfevent = dfmean[(dfmean['time'] >= t_start) & (dfmean['time'] < t_end)]
        dfevent = dfevent[['time', 'voltage']]
        path_talkback_df = Path(f"{self.projects_folder}/talkback/talkback_slice_{row['ID']}_stim.csv")
        if not path_talkback_df.parent.exists():
            path_talkback_df.parent.mkdir(parents=True, exist_ok=True)
        dfevent.to_csv(path_talkback_df, index=False)
        # save the event data as a dict
        keys = [
            't_EPSP_amp', 't_EPSP_amp_method', 't_EPSP_amp_params',
            't_EPSP_slope_start', 't_EPSP_slope_end', 't_EPSP_slope_method', 't_EPSP_slope_params',
            't_volley_amp', 't_volley_amp_method', 't_volley_amp_params',
            't_volley_slope_start', 't_volley_slope_end', 't_volley_slope_method', 't_volley_slope_params'
        ]
        dict_event = {key: row[key] for key in keys}
        print(f"talkback dict_event: {dict_event}")
        # store dict_event as .csv named after recording_name
        path_talkback = Path(f"{self.projects_folder}/talkback/talkback_meta_{row['ID']}_stim.csv")
        with open(path_talkback, 'w') as f:
            json.dump(dict_event, f)


    def darkmode(self):
        if uistate.darkmode:
            self.mainwindow.setStyleSheet("background-color: #333; color: #fff;")
            self.tableProj.setStyleSheet("""
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
            """)
        else:
            self.mainwindow.setStyleSheet("")
            self.tableProj.setStyleSheet("")
        uiplot.styleUpdate()
        uiplot.graphRefresh()


    def tableProjSelectionChanged(self):
        self.usage("tableProjSelectionChanged")
        t0 = time.time()
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            self.tableProj.clearSelection()
            print("Right click")
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        # build the list uistate.selected with indices
        uistate.selected = [index.row() for index in selected_indexes]
        self.zoomAuto()
        self.update_recs2plot()
        if len(uistate.selected) == 1:
            df_p = self.get_df_project()
            self.timesmodel.setData(self.get_dft(row=df_p.loc[uistate.selected[0]]))
        else:
            print("No single row selected, not updating timepoints")
            self.timesmodel.setData(None)
        self.updateMouseover()
        print(f" - - {round((time.time() - t0) * 1000, 2)}ms")
        report()


    def zoomAuto(self):
        # find the lowest t_stim and highest t_stim in selected rows
        if uistate.selected:
            df_p = self.get_df_project()
            t_stim_series = df_p.loc[uistate.selected, 't_stim']
            if not t_stim_series.empty:
                t_stim_min = t_stim_series.min() - 0.0005
                t_stim_max = t_stim_series.max() + 0.010
                if t_stim_min > 0:
                    uistate.zoom['mean_xlim'] = (t_stim_min, t_stim_max)
                    uistate.axm.set_xlim(uistate.zoom['mean_xlim'])

    def update_recs2plot(self):
        if uistate.selected:
            df_project_selected = self.get_df_project().iloc[uistate.selected]
            uistate.df_recs2plot = df_project_selected[df_project_selected['sweeps'] != "..."]
            if uistate.df_recs2plot.empty:
                uistate.df_recs2plot = None
        else:
            uistate.df_recs2plot = None


    def connectUIstate(self): # Connect UI elements to uistate
        # checkBoxes 
        for key, value in uistate.checkBox.items():
            #print(f" - connecting checkbox {key} to {value}")
            checkBox = getattr(self, f"checkBox_{key}")
            checkBox.setChecked(value)
            checkBox.stateChanged.connect(lambda state, key=key: self.viewSettingsChanged(key, state))
        # lineEdits
        # pushButtons
        # comboBoxes
        # mods?...

    def viewSettingsChanged(self, key, state):
        self.usage(f"viewSettingsChanged_{key}, {state == 2}")
        if key in uistate.checkBox.keys():
            uistate.checkBox[key] = (state == 2)
            if key == 'norm_EPSP':
                self.label_norm_on_sweep.setVisible(state == 2)
                self.label_relative_to.setVisible(state == 2)
                self.lineEdit_norm_EPSP_start.setVisible(state == 2)
                self.lineEdit_norm_EPSP_end.setVisible(state == 2)
                for idx in uistate.selected:
                    row = self.get_df_project().loc[idx]
                    rec_name = row['recording_name']
                    out = self.dict_outputs[rec_name]
                    uiplot.updateEPSPout(rec_name, out)
                self.purgeGroupCache()
                self.graphGroups()
        self.updateMouseover()
        uistate.save_cfg(projectfolder=self.dict_folders['project'])

    def groupControlsRefresh(self):
        self.removeGroupControls()
        #print (f"groupControlsRefresh: uistate.df_groups: {uistate.df_groups}")
        for str_ID in uistate.df_groups['group_ID'].tolist():
            #print(f" - adding group {str_ID}")
            self.addGroupControls(str_ID)

    def build_dict_folders(self):
        dict_folders = {
                    'project': self.projects_folder / self.projectname,
                    'data': self.projects_folder / self.projectname / 'data',
                    'timepoints': self.projects_folder / self.projectname / 'timepoints',
                    'cache': self.projects_folder / f'cache {config.version}' / self.projectname,
        }
        return dict_folders

    def resetCacheDicts(self):
        self.dict_datas = {} # all raw data
        self.dict_filters = {} # all processed data
        self.dict_means = {} # all means
        self.dict_ts = {} # all timepoints
        self.dict_outputs = {} # all outputs
        self.dict_group_means = {} # means of all group outputs
        self.dict_diffs = {} # all diffs (for paired stim)

    def usage(self, ui_component): # Talkback function
        if config.verbose:
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
        top_keys = ['WARNING', 'alias']
        dict_bottom = self.dict_usage.copy()
        top_data = {key: dict_bottom.pop(key, None) for key in top_keys}
        with path_usage.open("w") as file:
            yaml.safe_dump(top_data, file, default_flow_style=False)
            yaml.safe_dump(dict_bottom, file, default_flow_style=False)



# trigger functions TODO: break out the big ones to separate functions!

    def triggerDarkmode(self):
        uistate.darkmode = not uistate.darkmode
        self.usage(f"triggerDarkmode set to {uistate.darkmode}")
        self.write_bw_cfg()
        self.darkmode()

    def pushButton_paired_data_flip_pressed(self):
        self.usage("pushButton_paired_data_flip_pressed")
        self.flipCI()

    def triggerRenameRecording(self):
        self.usage("triggerRenameRecording")
        self.renameRecording()

    def triggerClearGroups(self):
        self.usage("triggerClearGroups")
        if uistate.selected:
            self.clearGroupsByRow(uistate.selected)
            self.tableUpdate()
            self.updateMouseover()
        else:
            print("No files selected.")

    def triggerEditGroups(self): # Open groups UI (not built)
        self.usage("triggerEditGroups")
        # Placeholder: For now, delete all buttons and groups
        # clearGroupsByRow on ALL rows of df_project
        self.removeGroupControls()
        self.groupsClear()
        self.tableUpdate()
        self.updateMouseover()

    def triggerNewGroup(self):
        self.usage("triggerNewGroup")
        df_groups = uistate.df_groups
        if len(df_groups) > 8: # TODO: hardcoded max nr of groups: move to bw cfg
            print("Maximum of 9 groups allowed for now.")
            return
        i = 1 # start at 1; no group_0
        while str(i) in df_groups['group_ID'].values:
            i += 1
        str_ID = str(i)
        new_group = pd.Series({'group_ID': str_ID, 'group_name': f"group {str_ID}", 'color': uistate.colors[i-1], 'show': "True"})
        uistate.df_groups = pd.concat([df_groups, new_group.to_frame().T]).reset_index(drop=True)
        print(f" - uistate.df_groups: {uistate.df_groups}")
        uistate.save_cfg(projectfolder=self.dict_folders['project'])
        self.addGroupControls(str_ID)

    def triggerRemoveLastGroup(self):
        self.usage("triggerRemoveLastGroup")
        if not uistate.df_groups.empty:  # Check if the DataFrame is not empty
            group__ID_to_remove = uistate.df_groups.iloc[-1]['group_ID']
            self.removeGroupControls(group__ID_to_remove)
            uistate.df_groups.drop(uistate.df_groups.index[-1], inplace=True)
            uistate.save_cfg(projectfolder=self.dict_folders['project'])
            self.removeFromGroup(group__ID_to_remove, self.get_df_project().index)

    def triggerRemoveLastEmptyGroup(self):
        self.usage("triggerRemoveLastEmptyGroup")
        if len(uistate.df_groups) < 1:  # Check if the DataFrame is not empty
            print("No groups to remove.")
            return
        df_p = self.get_df_project()
        group_to_remove = str(uistate.df_groups.iloc[-1]['group_ID'])
        print(f"Removing group {group_to_remove}...")
        if df_p['group_IDs'].str.contains(group_to_remove).any():
            print(f"{group_to_remove} is not empty.")
            return
        self.triggerRemoveLastGroup()
        print(f"{group_to_remove} removed.")

    def triggerDelete(self):
        self.usage("triggerDelete")
        self.deleteSelectedRows()

    def triggerRenameProject(self): # renameProject
        self.usage("triggerRenameProject")
        self.inputProjectName.setReadOnly(False)
        self.inputProjectName.selectAll()  # Select all text
        self.inputProjectName.setFocus()  # Set focus
        try: # Only disconnect if connected
            self.inputProjectName.editingFinished.disconnect()
        except TypeError:
            pass  # Ignore the TypeError that is raised when the signal isn't connected to any slots
        finally:
            self.inputProjectName.editingFinished.connect(self.renameProject)

    def triggerNewProject(self):
        self.usage("triggerNewProject")
        self.dict_folders['project'].mkdir(exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        i = 0
        while True:
            new_project_name = "Project " + date
            if 0 < i:
                new_project_name = new_project_name + "(" + str(i) + ")"
            if (self.projects_folder / new_project_name).exists():
                if config.verbose:
                    print(new_project_name, " already exists")
                i += 1
            else:
                self.newProject(new_project_name)
                break

    def triggerOpenProject(self): # open folder selector dialog
        self.usage("triggerOpenProject")
        self.dialog = QtWidgets.QDialog()
        print(f"triggerOpenProject: self.projects_folder: {self.projects_folder}")
        projectfolder = QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog, "Open Directory", str(self.projects_folder), QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        if config.verbose:
            print(f"Received projectfolder: {str(projectfolder)}")
        if (Path(projectfolder) / "project.brainwash").exists():
            if config.verbose:
                print(f"Projectfolder exists, loading project")
            self.dict_folders['project'] = Path(projectfolder)
            self.load_df_project()
            self.connectUIstate()
            self.groupControlsRefresh()
            self.mainwindow.setWindowTitle(f"Brainwash {config.version} - {self.projectname}")

    def triggerAddData(self): # creates file tree for file selection
        self.usage("triggerAddData")
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.show()

    def triggerParse(self): # parse non-parsed files and folders in self.df_project
        self.usage("triggerParse")
        self.mouseoverDisconnect()
        self.parseData()
        self.setButtonParse()

    def checkBox_paired_stims_changed(self, state):
        self.usage("checkBox_paired_stims_changed")
        uistate.checkBox['paired_stims'] = bool(state)
        print(f"checkBox_paired_stims_changed: {uistate.checkBox['paired_stims']}")
        self.pushButton_paired_data_flip.setEnabled(uistate.checkBox['paired_stims'])
        self.purgeGroupCache(*uistate.df_groups['group_ID'].tolist())
        uistate.save_cfg()
        self.tableFormat()
        self.updateMouseover()

    def editNormRange(self, lineEdit):
        self.usage("editNormRange")
        try:
            num = max(0, int(lineEdit.text()))
        except ValueError:
            num = 0
        if lineEdit.objectName() == "lineEdit_norm_EPSP_start": # start, cannot be higher than end
            if num == uistate.lineEdit['norm_EPSP_on'][0]:
                self.lineEdit_norm_EPSP_start.setText(str(num))
                return # no change
            uistate.lineEdit['norm_EPSP_on'][1] = max(num, int(self.lineEdit_norm_EPSP_end.text()))
            self.lineEdit_norm_EPSP_end.setText(str(uistate.lineEdit['norm_EPSP_on'][1]))
            uistate.lineEdit['norm_EPSP_on'][0] = num
        else: # end, cannot be lower than start
            if num == uistate.lineEdit['norm_EPSP_on'][1]:
                self.lineEdit_norm_EPSP_end.setText(str(num))
                return # no change
            uistate.lineEdit['norm_EPSP_on'][0] = min(num, int(self.lineEdit_norm_EPSP_start.text()))
            self.lineEdit_norm_EPSP_start.setText(str(uistate.lineEdit['norm_EPSP_on'][0]))
            uistate.lineEdit['norm_EPSP_on'][1] = num
        lineEdit.setText(str(num))
        uistate.save_cfg(projectfolder=self.dict_folders['project'])
        self.normOutputs() # ...of all recordings in df_p
        self.purgeGroupCache(*uistate.df_groups['group_ID'].tolist())
        self.tableFormat()
        # cycle through all selected recordings and update norm outputs
        for idx in uistate.selected:
            row = self.df_project.iloc[idx]
            rec_name = row['recording_name']
            out = self.get_dfoutput(row=row)
            uiplot.updateEPSPout(rec_name, out)
        print(f"editNormRange: {uistate.lineEdit['norm_EPSP_on']}")
    

    def normOutputs(self): # TODO: also norm diffs (paired stim) when applicable
        df_p = self.get_df_project()
        for index, row in df_p.iterrows():
            dfoutput = self.get_dfoutput(row=row)
            print(f"editNormRange: rebuilding norm columns for {row['recording_name']}")
            self.normOutput(row, dfoutput)


    def normOutput(self, row, dfoutput, aspect=None):
        normFrom = uistate.lineEdit['norm_EPSP_on'][0] # start
        normTo = uistate.lineEdit['norm_EPSP_on'][1] # end
        rec_name = row['recording_name']
        if aspect is None: # norm all existing columns and save file
            if 'EPSP_amp' in dfoutput.columns:
                selected_values = dfoutput.loc[normFrom:normTo, 'EPSP_amp']
                norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
                dfoutput['EPSP_amp_norm'] = dfoutput['EPSP_amp'] / norm_mean
            if 'EPSP_slope' in dfoutput.columns:
                selected_values = dfoutput.loc[normFrom:normTo, 'EPSP_slope']
                norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
                dfoutput['EPSP_slope_norm'] = dfoutput['EPSP_slope'] / norm_mean
            self.dict_outputs[rec_name] = dfoutput
            self.df2csv(df=dfoutput, rec=rec_name, key="output")
        else: # norm specific column and DO NOT SAVE file (dragged on-the-fly-graphs are saved only on mouse release)
            selected_values = dfoutput.loc[normFrom:normTo, aspect]
            norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
            dfoutput[f'{aspect}_norm'] = dfoutput[aspect] / norm_mean
            return dfoutput



# Data Editing functions

    def addData(self, dfAdd):  # concatenate dataframes of old and new data
        # Check for unique names in dfAdd, vs df_p and dfAdd
        # Adds (<lowest integer that makes unique>) to the end of non-unique recording_names
        df_p = self.get_df_project()
        list_recording_names = set(df_p['recording_name'])
        for index, row in dfAdd.iterrows():
            check_recording_name = row['recording_name']
            if check_recording_name.endswith('_mean.csv'):
                print("recording_name must not end with _mean.csv - appending _X") # must not collide with internal naming
                check_recording_name = check_recording_name + '_X'
                dfAdd.at[index,'recording_name'] = check_recording_name
            if check_recording_name in list_recording_names:
                # print(index, check_recording_name, "already exists!")
                i = 1
                new_recording_name = check_recording_name + "(" + str(i) + ")"
                while(new_recording_name in list_recording_names):
                    i += 1
                    new_recording_name = check_recording_name + "(" + str(i) + ")"
                print("New name:", new_recording_name)
                list_recording_names.add(new_recording_name)
                dfAdd.at[index,'recording_name'] = new_recording_name
            else:
                list_recording_names.add(check_recording_name)
        df_p = pd.concat([df_p, dfAdd])
        df_p.reset_index(drop=True, inplace=True)
        df_p['groups'] = df_p['groups'].fillna(" ")
        df_p['group_IDs'] = df_p['group_IDs'].fillna(" ")
        df_p['sweeps'] = df_p['sweeps'].fillna("...")
        self.set_df_project(df_p)
        self.tableFormat()
        if config.verbose:
            print("addData:", self.get_df_project())


    def renameRecording(self):
        # renames all instances of selected recording_name in df_project, and their associated files
        if len(uistate.selected) == 1:
            df_p = self.get_df_project()
            old_recording_name = df_p.at[uistate.selected[0], 'recording_name']
            old_data = self.dict_folders['data'] / (old_recording_name + ".csv")
            old_mean = self.dict_folders['cache'] / (old_recording_name + "_mean.csv")
            old_filter = self.dict_folders['cache'] / (old_recording_name + "_filter.csv")
            old_output = self.dict_folders['cache'] / (old_recording_name + "_output.csv")
            RenameDialog = InputDialogPopup()
            new_recording_name = RenameDialog.showInputDialog(title='Rename recording', query=old_recording_name)
            # check if the new name is a valid filename
            if new_recording_name is not None and re.match(r'^[a-zA-Z0-9_ -]+$', str(new_recording_name)) is not None:
                list_recording_names = set(df_p['recording_name'])
                if not new_recording_name in list_recording_names: # prevent duplicates
                    new_data = self.dict_folders['data'] / (new_recording_name + ".csv")
                    new_mean = self.dict_folders['cache'] / (new_recording_name + "_mean.csv")
                    new_filter = self.dict_folders['cache'] / (new_recording_name + "_filter.csv")
                    new_output = self.dict_folders['cache'] / (new_recording_name + "_output.csv")
                    if old_data.exists():
                        os.rename(old_data, new_data)
                    else: # data SHOULD exist
                        raise FileNotFoundError
                    if old_mean.exists():
                        os.rename(old_mean, new_mean)
                    if old_filter.exists():
                        os.rename(old_filter, new_filter)
                    if old_output.exists():
                        os.rename(old_output, new_output)
                    df_p.at[uistate.selected[0], 'recording_name'] = new_recording_name
                    # For paired recordings: also rename any references to old_recording_name in df_p['paired_recording']
                    df_p.loc[df_p['paired_recording'] == old_recording_name, 'paired_recording'] = new_recording_name
                    self.set_df_project(df_p)
                    self.tableUpdate()
                    uiplot.unPlot(old_recording_name)
                    self.graphUpdate(row = df_p.loc[uistate.selected[0]])
                else:
                    print(f"new_recording_name {new_recording_name} already exists")
            else:
                print(f"new_recording_name {new_recording_name} is not a valid filename")    
        else:
            print("Rename: please select one row only for renaming.")


    def deleteSelectedRows(self):
        if not uistate.selected:
            print("No files selected.")
            return
        df_p = self.get_df_project()
        for index in uistate.selected:
            recording_name = df_p.at[index, 'recording_name']
            sweeps = df_p.at[index, 'sweeps']
            if sweeps != "...": # if the file is parsed:
                print(f"Deleting {recording_name}...")
                self.purgeRecordingData(recording_name)
        # Regardless of whether or not there was a file, purge the row from df_project
        self.clearGroupsByRow(uistate.selected) # clear cache so that a new group mean is calculated
        # store the ID of the line below the last selected row
        reselect_ID = None
        if uistate.selected[-1] < len(df_p) - 1:
            reselect_ID = df_p.at[uistate.selected[-1] + 1, 'ID']
        df_p.drop(uistate.selected, inplace=True)
        df_p.reset_index(inplace=True, drop=True)
        self.set_df_project(df_p)
        self.tableUpdate()
        # reselect the line below the last selected row
        if reselect_ID:
            uistate.selected = df_p[df_p['ID'] == reselect_ID].index[0]
        self.tableProjSelectionChanged()


    def purgeRecordingData(self, recording_name):
        def removeFromCache(cache_name):
            cache = getattr(self, cache_name)
            if recording_name in cache.keys():
                cache.pop(recording_name, None)
        def removeFromDisk(folder_name, file_suffix):
            file_path = Path(self.dict_folders[folder_name] / (recording_name + file_suffix))
            if file_path.exists():
                file_path.unlink()
        for cache_name in ['dict_datas', 'dict_means', 'dict_filters', 'dict_ts', 'dict_outputs']:
            removeFromCache(cache_name)
        for folder_name, file_suffix in [('data', '.csv'), ('timepoints', '.csv'), ('cache', '_mean.csv'), ('cache', '_filter.csv'), ('cache', '_output.csv')]:
            removeFromDisk(folder_name, file_suffix)
        uiplot.unPlot(recording_name)


    def parseData(self): 
        df_p = self.get_df_project()
        df_p_to_update = df_p[df_p['sweeps'] == "..."].copy()

        self.thread = ParseDataThread(df_p_to_update, self.dict_folders)
        self.thread.progress.connect(self.updateProgressBar)
        self.thread.finished.connect(self.onParseDataFinished)
        self.thread.start()

        self.progressBarManager = ProgressBarManager(self.progressBar, len(df_p_to_update))
        self.progressBarManager.__enter__()


    def updateProgressBar(self, i):
        self.thread.progress.connect(lambda i: self.progressBarManager.update(i, "Parsing file "))


    def onParseDataFinished(self):
        self.progressBarManager.__exit__(None, None, None)
        if self.thread.rows:
            rows2add = pd.concat(self.thread.rows, axis=1).transpose()
            df_p = self.get_df_project()
            df_p = pd.concat([df_p[df_p['sweeps'] != "..."], rows2add]).reset_index(drop=True)
            self.set_df_project(df_p)
            # Get the indices of the new rows, as they are in df_p
            uistate.new_indices = df_p.index[df_p.index >= len(df_p) - len(rows2add)].tolist()
        self.tableFormat()
        self.progressBarManager.__exit__(None, None, None)
        self.graphMainPreload()
        

    def flipCI(self):
        if uistate.selected:
            df_p = self.get_df_project()
            already_flipped = []
            for index in uistate.selected:
                row = df_p.loc[index]
                name_rec = row['recording_name'] 
                name_pair = row['paired_recording']
                index_pair = df_p[df_p['recording_name'] == name_pair].index[0]
                if index in already_flipped:
                    print(f"Already flipped {index}")
                    continue
                # if row_pair doesn't exist:
                if pd.isna(name_pair):
                    print(f"{name_rec} has no paired recording.")
                    return
                print(f"Flipping C-I for {name_rec} and {name_pair}...")
                df_p.at[index, 'Tx'] = not df_p.at[index, 'Tx']
                df_p.at[index_pair, 'Tx'] = not df_p.at[index, 'Tx']
                # clear caches and diff files
                key_pair = name_rec[:-2]
                self.dict_diffs.pop(key_pair, None)
                path_diff = Path(f"{self.dict_folders['cache']}/{key_pair}_diff.csv")
                if path_diff.exists():
                    path_diff.unlink()
                # TODO: clear group cache
                already_flipped.append(index_pair)
                self.set_df_project(df_p)
                self.tableUpdate()
            self.updateMouseover()
        else:
            print("No files selected.")



# Data Group functions

    def groupsClear(self):
        # Generate a list of 9 colors for groups, hex format
        uistate.df_groups = pd.DataFrame(columns=['group_ID', 'group_name', 'color', 'show'])
        df_p = self.get_df_project()
        self.clearGroupsByRow(df_p.index) # clear all groups from all rows in df_project
        uistate.save_cfg(projectfolder=self.dict_folders['project'])

    def addGroupControls(self, str_ID): # Create menu for adding to group and checkbox for showing group
        group_ID = f"group_{str_ID}" # backend group name for object naming
        group_name = uistate.df_groups.loc[uistate.df_groups['group_ID'] == str_ID, 'group_name'].values[0]
        print(f"addGroupControls, str_ID: {str_ID}, type: {type(str_ID)} group_name: {group_name}")
        dict_row = uistate.df_groups.loc[uistate.df_groups['group_ID'] == str_ID].to_dict(orient='records')[0]
        if not dict_row:
            print(f"addGroupControls: {str_ID} not found in uistate.df_groups:")
            print(uistate.df_groups)
            return
        color = dict_row['color']
        # print(f"addGroupControls: {group_name}, {color}, type: {type(color)}")
        setattr(self, f"actionAddTo_{group_ID}", QtWidgets.QAction(f"Add selection to {group_name}", self))
        self.new_group_menu_item = getattr(self, f"actionAddTo_{group_ID}")
        self.new_group_menu_item.triggered.connect(lambda checked, add_group_ID=str_ID: self.addToGroup(add_group_ID))
        self.new_group_menu_item.setShortcut(f"{str_ID}")
        self.menuGroups.addAction(self.new_group_menu_item)                    
        self.new_checkbox = CustomCheckBox(str_ID)
        self.new_checkbox.rightClicked.connect(self.triggerGroupRename) # str_ID is passed by CustomCheckBox
        self.new_checkbox.setObjectName(group_ID)
        self.new_checkbox.setText(f"{str_ID}. {group_name}")
        self.new_checkbox.setStyleSheet(f"background-color: {color};")  # Set the background color
        self.new_checkbox.setMaximumWidth(100)  # Set the maximum width
        self.new_checkbox.setChecked(bool(dict_row['show']))
        self.new_checkbox.stateChanged.connect(lambda state, str_ID=str_ID: self.groupCheckboxChanged(state, str_ID))
        self.horizontalLayoutGroups.addWidget(self.new_checkbox)


    def triggerGroupRename(self, str_ID):
        print(f"triggerGroupRename: {str_ID}")
        RenameDialog = InputDialogPopup()
        new_group_name = RenameDialog.showInputDialog(title='Rename group', query='')
        # check if ok
        if new_group_name in uistate.df_groups['group_name'].values:
            print(f"Group name {new_group_name} already exists.")
        elif re.match(r'^[a-zA-Z0-9_ -]+$', str(new_group_name)) is not None: # True if valid filename
            uistate.df_groups.loc[uistate.df_groups['group_ID'] == str_ID, 'group_name'] = new_group_name
            uistate.save_cfg(projectfolder=self.dict_folders['project'])
            df_p = self.get_df_project()
            indexes_with_str_ID = [i for i in df_p.index if str_ID in df_p.loc[i, 'group_IDs'].split(",")]
            for i in indexes_with_str_ID:
                self.group_remove_from_row(i, str_ID)
                self.group_add_to_row(i, str_ID, new_group_name)
            self.save_df_project()
            self.groupControlsRefresh()
            self.tableFormat()
        else:
            print(f"Group name {new_group_name} is not a valid name.")


    def removeGroupControls(self, i=None):
        if i is None:  # if i is not provided, remove all group controls
            for i in range(1, 10):  # clear group controls 1-9
                self.removeGroupControls(i)
        else:
            group = f"group_{str(i)}"
            # get the widget named group and remove it
            widget = self.centralwidget.findChild(QtWidgets.QWidget, group)
            if widget:
                widget.deleteLater()
            # get the action named actionAddTo_{group} and remove it
            action = getattr(self, f"actionAddTo_{group}", None)
            if action:
                self.menuGroups.removeAction(action)
                delattr(self, f"actionAddTo_{group}")

    def groupCheckboxChanged(self, state, str_ID):
        if config.verbose:
            print(f"groupCheckboxChanged: {str_ID} = {state}")
        uistate.df_groups.loc[uistate.df_groups['group_ID'] == str_ID, 'show'] = str(state == 2)
        uistate.save_cfg(projectfolder=self.dict_folders['project'])
        self.updateMouseover()

    def group_remove_from_row(self, i, str_add_group_ID):
        str_group_IDs = self.df_project.loc[i, 'group_IDs']
        list_group_IDs = str_group_IDs.split(",")
        list_group_IDs.remove(str_add_group_ID)
        self.df_project.loc[i, 'group_IDs'] = ",".join(sorted(list_group_IDs)) if list_group_IDs else " "
        # Update 'groups' column
        if list_group_IDs:
            group_names = [uistate.df_groups.loc[uistate.df_groups['group_ID'] == group_id, 'group_name'].values[0] for group_id in list_group_IDs]
            self.df_project.loc[i, 'groups'] = ", ".join(sorted(group_names))
        else:
            self.df_project.loc[i, 'groups'] = " "

    def group_add_to_row(self, i, str_add_group_ID, groupname):
        if self.df_project.loc[i, 'group_IDs'] == " ":
            self.df_project.loc[i, 'group_IDs'] = str_add_group_ID
            self.df_project.loc[i, 'groups'] = groupname
        else:
            str_group_IDs = str(self.df_project.loc[i, 'group_IDs'])
            list_group_IDs = str_group_IDs.split(",")
            if str_add_group_ID not in list_group_IDs:
                list_group_IDs.append(str_add_group_ID)
                self.df_project.loc[i, 'group_IDs'] = ",".join(sorted(list_group_IDs))
                # Update 'groups' column
                group_names = [uistate.df_groups.loc[uistate.df_groups['group_ID'] == group_id, 'group_name'].values[0] for group_id in list_group_IDs]
                self.df_project.loc[i, 'groups'] = ", ".join(sorted(group_names))

    def addToGroup(self, add_group_ID):
        self.usage("addToGroup")
        str_add_group_ID = str(add_group_ID)
        print(f"addToGroup: {add_group_ID}")
        if not uistate.selected:
            print("No files selected.")
            return

        groupname = uistate.df_groups.loc[uistate.df_groups['group_ID'] == str_add_group_ID, 'group_name'].values[0]
        if all(self.df_project.loc[uistate.selected, 'group_IDs'].str.contains(str_add_group_ID)):
            for i in uistate.selected:
                self.group_remove_from_row(i, str_add_group_ID)
        else:
            for i in uistate.selected:
                self.group_add_to_row(i, str_add_group_ID, groupname)
        self.save_df_project()
        self.purgeGroupCache(add_group_ID)
        self.tableFormat()
        uiplot.unPlotGroup(add_group_ID)
        self.graphGroups()
        self.updateMouseover()

    
    def removeFromGroup(self, remove_group_ID, indices=uistate.selected):
        self.usage("removeFromGroup")
        str_remove_group_ID = str(remove_group_ID)
        print(f"removeFromGroup: {remove_group_ID}, indices: {indices}")
        # Remove all selected recordings from group "remove_group"
        if len(indices) > 0:
            for i in indices:
                if self.df_project.loc[i, 'group_IDs'] != " ":
                    str_group_IDs = self.df_project.loc[i, 'group_IDs']
                    list_groups = list(str_group_IDs.split(","))
                    if str_remove_group_ID in list_groups:
                        list_groups.remove(str_remove_group_ID)
                        self.df_project.loc[i, 'group_IDs'] = ",".join(map(str, sorted(list_groups)))
            self.save_df_project()
            self.purgeGroupCache(remove_group_ID)
            self.tableUpdate()
            self.updateMouseover()

    def purgeGroupCache(self, *groups): # clear cache so that a new group mean is calculated
        if not groups:  # if no groups are passed
            groups = list(self.dict_group_means.keys())  # purge all groups
        if config.verbose:
            print(f"purgeGroupCache: {groups}, len(group): {len(groups)}")
        for group in groups:
            if group in self.dict_group_means:
                del self.dict_group_means[group]
            path_group_cache = Path(f"{self.dict_folders['cache']}/{group}.csv")
            if path_group_cache.exists: # TODO: Upon adding a group, both of these conditions trigger. How?
                print(f"{path_group_cache} found when checking for existence...")
                try:
                    path_group_cache.unlink()
                    print("...and was successfully unlinked.")
                except FileNotFoundError:
                    print("...but NOT when attempting to unlink.")
            uiplot.unPlotGroup(group)

    def clearGroupsByRow(self, rows):
        list_affected_groups = ' '.join(self.df_project.iloc[rows]['group_IDs'])
        affected_groups = set(re.findall(r'\b\w+\b', list_affected_groups))
        for i in rows:
            self.df_project.loc[i, 'group_IDs'] = " "
            self.df_project.loc[i, 'groups'] = " "
        for group in affected_groups:
            self.purgeGroupCache(group)
        self.set_df_project(self.df_project)


# Writer functions
    
    def write_bw_cfg(self):  # config file for program, global settings
        cfg = {"user_documents": str(self.user_documents), "projects_folder": str(self.projects_folder), "projectname": self.projectname, "darkmode": uistate.darkmode}
        with self.bw_cfg_yaml.open("w+") as file:
            yaml.safe_dump(cfg, file)

    def read_bw_cfg(self):
        # load program bw_cfg if present
        paths = [Path.cwd()] + list(Path.cwd().parents)
        self.repo_root = [i for i in paths if (-1 < str(i).find("brainwash")) & (str(i).find("src") == -1)][0]  # path to brainwash directory
        self.bw_cfg_yaml = self.repo_root / "cfg.yaml"  # Path to cfg.yaml
        # Set default values for bw_cfg.yaml
        self.user_documents = Path.home() / "Documents"  # Where to look for raw data
        self.projects_folder = self.user_documents / "Brainwash Projects"  # Where to store projects
        self.projectname = "My Project"
        uistate.darkmode = False
        # Override default if cfg.yaml exists
        if self.bw_cfg_yaml.exists():
            with self.bw_cfg_yaml.open("r") as file:
                cfg = yaml.safe_load(file)
                projectfolder = Path(cfg['projects_folder']) / cfg['projectname']
                if projectfolder.exists():  # if the folder stored in cfg.yaml exists, use it
                    self.user_documents = Path(cfg['user_documents'])  # Where to look for raw data
                    self.projects_folder = Path(cfg['projects_folder'])  # Where to save and read parsed data
                    self.projectname = cfg['projectname']
                uistate.darkmode = cfg['darkmode']

    def df2csv(self, df, rec, key=None): # "writes dict[rec] to rec_{dict}.csv" TODO: Update, better description; replace "rec"
        self.dict_folders['cache'].mkdir(exist_ok=True)
        if key is None:
            filepath = f"{self.dict_folders['cache']}/{rec}.csv"
        elif key == "timepoints":
            filepath = f"{self.dict_folders['timepoints']}/t_{rec}.csv"
        else:
            filepath = f"{self.dict_folders['cache']}/{rec}_{key}.csv"
        print(f"saved cache filepath: {filepath}")
        df.to_csv(filepath, index=False)



# Project functions

    def newProject(self, new_project_name):
        new_projectfolder = self.projects_folder / new_project_name
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if config.verbose:
                print("The target project name already exists")
        else:
            new_projectfolder.mkdir()
            self.projectname = new_project_name
            self.mainwindow.setWindowTitle(f"Brainwash {config.version} - {self.projectname}")
            self.dict_folders = self.build_dict_folders()
            self.resetCacheDicts()
            self.set_df_project(df_projectTemplate())
            self.write_bw_cfg() # update project to open at boot
            uistate.reset()
            uistate.save_cfg(projectfolder=self.dict_folders['project'])
            self.tableFormat()
            uiplot.graphRefresh()

    def renameProject(self): # changes name of project folder and updates .cfg
        #self.dict_folders['project'].mkdir(exist_ok=True)
        RenameDialog = InputDialogPopup()
        new_project_name = RenameDialog.showInputDialog(title='Rename project', query='')
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if config.verbose:
                print(f"Project name {new_project_name} already exists")
        elif re.match(r'^[a-zA-Z0-9_ -]+$', str(new_project_name)) is not None: # True if valid filename
            dict_old = self.dict_folders
            self.projectname = new_project_name
            self.dict_folders = self.build_dict_folders()
            dict_old['project'].rename(self.dict_folders['project'])
            if Path(dict_old['cache']).exists():
                dict_old['cache'].rename(self.dict_folders['cache'])
            # self.project_cfg_yaml = self.dict_folders['project'] / "project_cfg.yaml"
            # self.write_bw_cfg() # update boot-up-path in bw_cfg.yaml to new project folder
            self.mainwindow.setWindowTitle(f"Brainwash {config.version} - {self.projectname}")
        else:
            print(f"Project name {new_project_name} is not a valid path.")



# Project dataframe handling

    def get_df_project(self): # returns a copy of the persistent df_project TODO: make these functions the only way to get to it.
        return self.df_project

    def set_df_project(self, df): # persists df and saves it to .csv
        print("set_df_project")
        self.df_project = df
        self.save_df_project()

    def load_df_project(self): # reads or builds project cfg and groups. Reads fileversion of df_project and saves bw_cfg
        self.graphMainWipe()
        self.resetCacheDicts() # clear internal caches
        self.projectname = self.dict_folders['project'].stem
        self.dict_folders = self.build_dict_folders()
        self.df_project = pd.read_csv(str(self.dict_folders['project'] / "project.brainwash"), dtype={'group_IDs': str})
        uistate.load_cfg(self.dict_folders['project'], config.version)
        self.tableFormat()
        self.write_bw_cfg()

    def save_df_project(self): # writes df_project to .csv
        self.df_project.to_csv(str(self.dict_folders['project'] / "project.brainwash"), index=False)



# Table handling

    def setButtonParse(self):
        if self.df_project['sweeps'].eq("...").any():
            self.pushButtonParse.setVisible(True)
        else:
            self.pushButtonParse.setVisible(False)

    def tableFormat(self):
        if config.verbose:
            print("tableFormat")
        selected_rows = self.tableProj.selectionModel().selectedRows()
        self.tableProj.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.tablemodel.setData(self.get_df_project())
        header = self.tableProj.horizontalHeader()
        self.tableProj.verticalHeader().hide()
        df_p = self.df_project
        # hide all columns except these:
        list_show = [   
                        df_p.columns.get_loc('recording_name'),
                        df_p.columns.get_loc('sweeps'),
                        df_p.columns.get_loc('groups'),
                        df_p.columns.get_loc('n_stims'),
#                        df_p.columns.get_loc('group_IDs'),
#                        df_p.columns.get_loc('t_EPSP_amp'),
#                        df_p.columns.get_loc('t_EPSP_amp_method'),
#                        df_p.columns.get_loc('t_EPSP_slope_start'),
#                        df_p.columns.get_loc('t_EPSP_slope_end'),
#                        df_p.columns.get_loc('t_EPSP_slope_width'),
#                        df_p.columns.get_loc('t_EPSP_slope_halfwidth'),
#                        df_p.columns.get_loc('t_EPSP_slope_method'),
#                        df_p.columns.get_loc('t_volley_amp'),
#                        df_p.columns.get_loc('volley_amp_mean'),
#                        df_p.columns.get_loc('t_volley_amp_method'),
#                        df_p.columns.get_loc('t_volley_slope_start'),
#                        df_p.columns.get_loc('t_volley_slope_end'),
#                        df_p.columns.get_loc('volley_slope_mean'),
#                        df_p.columns.get_loc('t_volley_slope_width'),
#                        df_p.columns.get_loc('t_volley_slope_halfwidth'),
#                        df_p.columns.get_loc('t_volley_slope_method'),
                    ]
        if uistate.checkBox['paired_stims']:
            list_show.append(df_p.columns.get_loc('Tx'))
        num_columns = df_p.shape[1]
        for col in range(num_columns):
            if col in list_show:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
                self.tableProj.setColumnHidden(col, False)
            else:
                self.tableProj.setColumnHidden(col, True)
        self.tableProj.resizeColumnsToContents()
        total_width = 13 + sum([self.tableProj.columnWidth(i) for i in range(self.tableProj.model().columnCount(QtCore.QModelIndex())) if not self.tableProj.isColumnHidden(i)])
        self.tableProj.setMinimumWidth(total_width)
        for index in selected_rows:
            self.tableProj.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
        self.setButtonParse()
    
    def tableUpdate(self):
        selected_rows = self.tableProj.selectionModel().selectedRows() # Save selection
        self.tablemodel.setData(self.get_df_project())
        self.tableProj.resizeColumnsToContents()
        for index in selected_rows: # Restore selection
            self.tableProj.selectionModel().select(index, QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)



# Internal dataframe handling

    def get_dfmean(self, row):
        # returns an internal df mean for the selected file. If it does not exist, read it from file first.
        recording_name = row['recording_name']
        if recording_name in self.dict_means: #1: Return cached
            return self.dict_means[recording_name]

        persist = False
        str_mean_path = f"{self.dict_folders['cache']}/{recording_name}_mean.csv"
        if Path(str_mean_path).exists(): #2: Read from file
            dfmean = pd.read_csv(str_mean_path)
        else: #3: Create file
            dfmean = parse.build_dfmean(self.get_dfdata(row=row))
            persist = True

        #if the filter is not a column in self.dfmean, create it
        if row['filter'] == 'savgol':
            # TODO: extract parameters from df_p, use default for now
            if 'savgol' not in dfmean.columns:
                dict_filter_params = json.loads(row['filter_params'])
                window_length = int(dict_filter_params['window_length'])
                poly_order = int(dict_filter_params['poly_order'])
                dfmean['savgol'] = analysis.addFilterSavgol(df = dfmean, window_length=window_length, poly_order=poly_order)
                persist = True

        if persist:
            self.df2csv(df=dfmean, rec=recording_name, key="mean")
        self.dict_means[recording_name] = dfmean
        return self.dict_means[recording_name]

    def get_dft(self, row):
        # returns an internal df t for the selected file. If it does not exist, read it from file first.
        print("*** get_dft")
        recording_name = row['recording_name']
        if recording_name in self.dict_ts.keys():
            print("returning cached t")
            return self.dict_ts[recording_name]
        str_t_path = f"{self.dict_folders['timepoints']}/t_{recording_name}.csv"
        if Path(str_t_path).exists():
            print("reading t from file")
            dft = pd.read_csv(str_t_path)
            self.dict_ts[recording_name] = dft
            return dft
        else:
            print("creating t")
            _ = self.defaultOutput(row=row) # also creates self.dict_ts[recording_name]
            dft = self.dict_ts[recording_name]
            self.df2csv(df=dft, rec=recording_name, key="timepoints")
            return dft

    def get_dfoutput(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        recording_name = row['recording_name']
        if recording_name in self.dict_outputs: #1: Return cached
            return self.dict_outputs[recording_name]
        str_output_path = f"{self.dict_folders['cache']}/{recording_name}_output.csv"
        if Path(str_output_path).exists(): #2: Read from file
            dfoutput = pd.read_csv(str_output_path)
        else: #3: Create file
            dfoutput = self.defaultOutput(row=row)
            self.df2csv(df=dfoutput, rec=recording_name, key="output")
        self.dict_outputs[recording_name] = dfoutput
        return self.dict_outputs[recording_name]
        
    def get_dfdata(self, row):
        # returns an internal df for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row['recording_name']
        if recording_name in self.dict_datas: #1: Return cached
            return self.dict_datas[recording_name]
        path_data = Path(f"{self.dict_folders['data']}/{recording_name}.csv")
        try: #2: Read from file - datafile should always exist
            dfdata = pd.read_csv(path_data)
            self.dict_datas[recording_name] = dfdata
            return self.dict_datas[recording_name]
        except FileNotFoundError:
            print("did not find _mean.csv to load. Not imported?")
            
    def get_dffilter(self, row):
        # returns an internal df_filter for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row['recording_name']
        if recording_name in self.dict_filters: #1: Return cached
            return self.dict_filters[recording_name]
        path_filter = Path(f"{self.dict_folders['cache']}/{recording_name}_filter.csv")
        if Path(path_filter).exists(): #2: Read from file
            dffilter = pd.read_csv(path_filter)
        else: #3: Create file
            dffilter = parse.zeroSweeps(self.get_dfdata(row=row), self.get_dfmean(row=row))
            self.df2csv(df=dffilter, rec=recording_name, key="filter")
            if row['filter'] == 'savgol':
                dict_filter_params = json.loads(row['filter_params'])
                window_length = int(dict_filter_params['window_length'])
                poly_order = int(dict_filter_params['poly_order'])
                dffilter['savgol'] = analysis.addFilterSavgol(df = dffilter, window_length=window_length, poly_order=poly_order)
        # Cache and return
        self.dict_filters[recording_name] = dffilter
        return self.dict_filters[recording_name]

    def get_dfdiff(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        rec_select = row['recording_name']
        # TODO: check if row has a paired recording
        # Otherwise, find the paired recording
        rec_paired = None
        key_pair = rec_select[:-2] # remove stim id ("_a" or "_b") from selected recording_name
        # 1: check for cached diff
        if key_pair in self.dict_diffs:
            return self.dict_diffs[key_pair]
        # 2: check for file
        if Path(f"{self.dict_folders['cache']}/{key_pair}_diff.csv").exists():
            dfdiff = pd.read_csv(f"{self.dict_folders['cache']}/{key_pair}_diff.csv")
            self.dict_diffs[key_pair] = dfdiff
            return dfdiff
        # 3: build a new diff
        df_p = self.get_df_project()
        # 3.1: does the row have a saved paired recording that exists in df_p?
        if pd.notna(row['paired_recording']):
            if row['paired_recording'] in df_p['recording_name'].values:
                rec_paired = row['paired_recording']
        # 3.2: if not, find a recording with a matching name
        if rec_paired is None: # set rec_paired to the first recording_name that starts with rec_paired, but isn't rec_select
            for i, row_check in df_p.iterrows():
                if row_check['recording_name'].startswith(key_pair) and row_check['recording_name'] != rec_select:
                    rec_paired = row_check['recording_name']
                    break
        if rec_paired is None: # if still None, return
            print("Paired recording not found.")
            return
        # 3.3: get the dfoutputs for both recordings
        row_paired = df_p[df_p['recording_name'] == rec_paired].iloc[0]
        df_p.loc[row.name, 'paired_recording'] = rec_paired
        df_p.loc[row_paired.name, 'paired_recording'] = rec_select
        self.set_df_project(df_p)
        dfout_select = self.get_dfoutput(row=row)
        dfout_paired = self.get_dfoutput(row=row_paired)

        # 3.4: check which of the paired recordings is Tx (the other being control)
        if pd.isna(row['Tx']):
            print("Tx is NaN - loop should trigger!")
            row['Tx'] = False
            # default: assume Tx has the highest max EPSP_amp, or EPSP_slope if there is no EPSP_amp
            if any((dfout_select[col].max() > dfout_paired[col].max() for col in ['EPSP_amp', 'EPSP_slope'] if col in dfout_select.columns)):
                row['Tx'] = True
                row_paired['Tx'] = False
                df_p.loc[row.name, 'Tx'] = row['Tx']
                df_p.loc[row_paired.name, 'Tx'] = row_paired['Tx']
                print(f"{rec_select} is Tx, {rec_paired} is control. Saving df_p...")
                self.set_df_project(df_p)
            elif not any(col in dfout_select.columns for col in ['EPSP_amp', 'EPSP_slope']):
                print("Selected recording has no measurements.")
                return
        else:
            print("Tx is not NaN")
        # 3.5: set dfi and dfc    
        if row['Tx']:
            dfi = dfout_select # Tx output
            dfc = dfout_paired # control output
        else:
            dfi = dfout_paired
            dfc = dfout_select
        # 3.6: build dfdiff
        dfdiff = pd.DataFrame({'sweep': dfi.sweep})
        if 'EPSP_amp' in dfi.columns:
            dfdiff['EPSP_amp'] = dfi.EPSP_amp / dfc.EPSP_amp
        if 'EPSP_slope' in dfi.columns:
            dfdiff['EPSP_slope'] = dfi.EPSP_slope / dfc.EPSP_slope
        self.df2csv(df=dfdiff, rec=key_pair, key="diff")
        self.dict_diffs[key_pair] = dfdiff
        return dfdiff        
        
    def get_dfgroupmean(self, str_ID):
        # returns an internal df output average of <group>. If it does not exist, create it
        if str_ID in self.dict_group_means: # 1: Return cached
            print(f"Returning cached group mean for {str_ID}")
            return self.dict_group_means[str_ID]
        group_path = Path(f"{self.dict_folders['cache']}/group_{str_ID}.csv")
        if group_path.exists(): #2: Read from file
            if config.verbose:
                print("Loading stored", str(group_path))
            group_mean = pd.read_csv(str(group_path))
        else: #3: Create file
            if config.verbose:
                print("Building new", str(group_path))
            df_p = self.df_project
            # create dfgroup_IDs. containing ONLY lines that have key group in their group_IDs
            dfgroup_IDs = df_p[df_p['group_IDs'].str.contains(str_ID, na=False)]
            # print(f"dfgroup_IDs: {dfgroup_IDs}")
            dfs = []
            list_pairs = [] # prevent diff duplicates
            for i, row in dfgroup_IDs.iterrows():
                if uistate.checkBox['paired_stims']:
                    name_rec = row['recording_name']
                    if name_rec in list_pairs:
                        continue
                    name_pair = row['paired_recording']
                    df = self.get_dfdiff(row=row)
                    list_pairs.append(name_pair)                    
                else:
                    df = self.get_dfoutput(row=row)
                    if uistate.checkBox['norm_EPSP']:
                        self.normOutput(row, df)
                dfs.append(df)
            if dfs:
                dfs = pd.concat(dfs)
            else:
                print(f"No recordings in group_ID {str_ID}.")
                return
            if uistate.checkBox['norm_EPSP']:
                group_mean = dfs.groupby('sweep').agg({'EPSP_amp_norm': ['mean', 'sem'], 'EPSP_slope_norm': ['mean', 'sem']}).reset_index()
            else:
                group_mean = dfs.groupby('sweep').agg({'EPSP_amp': ['mean', 'sem'], 'EPSP_slope': ['mean', 'sem']}).reset_index()
            group_mean.columns = ['sweep', 'EPSP_amp_mean', 'EPSP_amp_SEM', 'EPSP_slope_mean', 'EPSP_slope_SEM']
            self.df2csv(df=group_mean, rec=f"group_{str_ID}", key="mean")
        self.dict_group_means[str_ID] = group_mean
        return self.dict_group_means[str_ID]

    def defaultOutput(self, row):
        '''
        Generates default results for row (in self.df_project)
        Stores n_stims in self.df_project
        Stores timepoints, methods and params in dict_ts{<rec_ID>:<df_t>}
        Returns a dict{stim:output}, that is amplitudes and slopes for each stim
        '''
        print("defaultOutput")
        dffilter = self.get_dffilter(row=row)
        dfmean = self.get_dfmean(row=row)
        df_p = self.get_df_project()

        default_dict_t = uistate.default.copy()  # Default sizes
        dft = analysis.find_all_t(dfmean=dfmean, 
                                              volley_slope_halfwidth=default_dict_t['t_volley_slope_halfwidth'], 
                                              EPSP_slope_halfwidth=default_dict_t['t_EPSP_slope_halfwidth'], 
                                              verbose=False)
        dict_outputs = {}
        df_p['n_stims'] = len(dft)
        dft['stim'] = 0

        # Update each row in dft with the default values
        for i, row_t in dft.iterrows():
            updated_dict_t = default_dict_t.copy()  # Start with a copy of the default values
            updated_dict_t.update(row_t.to_dict())  # Update with the values from row_t
            dft.loc[i] = updated_dict_t
        
            # Update the original row in dft with the combined values
            row_id = row['ID']  # Get the row ID
            rec_name = row['recording_name']
            dfoutput = analysis.build_dfoutput(df=dffilter, dict_t=dft.loc[i].to_dict())
            dft.at[i, 'volley_amp_mean'] = dfoutput['volley_amp'].mean()
            dft.at[i, 'volley_slope_mean'] = dfoutput['volley_slope'].mean()
            dft.at[i, 'stim'] = i+1 # stims numbered from 1
            if i == 0: # TODO: for now, set the deprecated df_p values
                for key, value in dft.loc[i].items():
                    row_index = df_p[df_p['ID'] == row_id].index[0]
                    df_p.at[row_index, key] = value
            self.normOutput(row=row, dfoutput=dfoutput)
            if i == 0:
                dict_outputs[rec_name] = dfoutput

        self.set_df_project(df_p)
        column_order = ['stim',
                        't_EPSP_slope_start',
                        't_EPSP_slope_end',
                        't_EPSP_slope_width',
                        't_EPSP_slope_halfwidth',
                        't_EPSP_slope_method',
                        't_EPSP_slope_params',
                        't_EPSP_amp',
                        't_EPSP_amp_method',
                        't_EPSP_amp_params',
                        't_volley_slope_start',
                        't_volley_slope_end',
                        't_volley_slope_width',
                        't_volley_slope_halfwidth',
                        't_volley_slope_method',
                        't_volley_slope_params',
                        'volley_slope_mean',
                        't_volley_amp',
                        't_volley_amp_method',
                        't_volley_amp_params',
                        'volley_amp_mean',
        ]
                        
        dft = dft.reindex(columns=column_order)
        self.dict_ts[rec_name] = dft
        self.df2csv(df=dft, rec=rec_name, key="timepoints")
        return dict_outputs[rec_name]


# Graph interface

    def graphMainWipe(self): # removes all plots from main_canvas_mean and main_canvas_output
        if hasattr(self, "main_canvas_mean"):
            self.main_canvas_mean.axes.cla()
            self.main_canvas_mean.draw()
        if hasattr(self, "main_canvas_output"):
            self.main_canvas_output.axes.cla()
            self.main_canvas_output.draw()

    def graphMainAxes(self): # plot selected row(s), or clear graph if empty
        uistate.axm = self.main_canvas_mean.axes
        ax1 = self.main_canvas_output.axes
        if uistate.ax2 is not None and hasattr(uistate, "ax2"):  # remove ax2 if it exists
            uistate.ax2.remove()
        ax2 = ax1.twinx()
        uistate.ax2 = ax2  # Store the ax2 instance
        uistate.ax1 = ax1
        # connect scroll event if not already connected #TODO: when graphMainAxes is called only once, the check should be redundant
        if not hasattr(self, 'scroll_event_connected') or not self.scroll_event_connected:
            self.main_canvas_mean.mpl_connect('scroll_event', lambda event: self.zoomOnScroll(event=event, parent=self.graphMean, canvas=self.main_canvas_mean, ax1=self.main_canvas_mean.axes))
            self.main_canvas_output.mpl_connect('scroll_event', lambda event: self.zoomOnScroll(event=event, parent=self.graphOutput, canvas=self.main_canvas_output, ax1=uistate.ax1, ax2=uistate.ax1))
            self.scroll_event_connected = True
        df_p = self.get_df_project()
        if df_p.empty:
            return
        self.graphMainPreload()


    def graphMainPreload(self): # plot and hide imported recordings
        self.usage("graphMainPreload")
        t0 = time.time()
        self.mouseoverDisconnect()
        if not uistate.new_indices:
            df_p = self.get_df_project()
            uistate.new_indices = df_p[~df_p['sweeps'].eq("...")].index.tolist()
        if not uistate.new_indices:
            return
        print(f"Preloading {len(uistate.new_indices)} recordings.")
        self.progressBar.setValue(0)
        self.thread = GraphMainPreloadThread(uistate, uiplot, self)
        self.thread.finished.connect(lambda: self.onGraphMainPreloadFinished(t0))

        # Create ProgressBarManager and connect progress signal
        self.progressBarManager = ProgressBarManager(self.progressBar, len(uistate.new_indices))
        self.thread.progress.connect(lambda i: self.progressBarManager.update(i, "Preloading recording"))

        self.thread.start()
        self.progressBarManager.__enter__()  # Show progress bar

    def onGraphMainPreloadFinished(self, t0):
        self.graphGroups()
        print(f"Preloaded recordings and groups in {time.time()-t0:.2f} seconds.")
        uiplot.graphRefresh()
        self.progressBarManager.__exit__(None, None, None)  # Hide progress bar
        self.tableProjSelectionChanged()

    def graphGroups(self):
        group_ids = set(uistate.df_groups['group_ID'])
        print (f"group_ids: {group_ids}, {type(group_ids)}")
        print (f"df_project: {self.df_project['group_IDs'], type(self.df_project['group_IDs'])}")
        groups_with_recs = set(group_id for group_ids in self.df_project['group_IDs'] for group_id in group_ids.split(','))
        already_plotted = set(uistate.get_groupSet())
        print(f"groups already plotted: {already_plotted}")
        groups_to_plot = (group_ids & groups_with_recs) - already_plotted
        if groups_to_plot:
            df_groups_to_plot = uistate.df_groups[uistate.df_groups['group_ID'].isin(groups_to_plot)]
            print(f"groups to plot {df_groups_to_plot}")
            for _, df_group_row in df_groups_to_plot.iterrows():
                str_ID = df_group_row['group_ID']
                df_groupmean = self.get_dfgroupmean(str_ID=str_ID)
                uiplot.addGroup(df_group_row, df_groupmean)
                print(f"Loaded group {str_ID}, name: {df_group_row['group_name']}")


    def graphUpdate(self, df=None, row=None):
        def processRow(row):
            dfmean = self.get_dfmean(row=row)
            dfoutput = self.get_dfdiff(row=row) if uistate.checkBox['paired_stims'] else self.get_dfoutput(row=row)
            if dfoutput is not None:
                uiplot.addRow(dict_row=row.to_dict(), dfmean=dfmean, dfoutput=dfoutput)
        def processDataFrame(df):
            list_to_plot = [rec for rec in df['recording_name'].tolist() if rec not in uistate.get_recSet()]
            for rec in list_to_plot:
                row = df[df['recording_name'] == rec].iloc[0]
                processRow(row)
        def updateZoom(df):
            if uistate.zoom['output_xlim'][1] is None:
                uistate.zoom['output_xlim'] = [0, df['sweeps'].max()]
                uistate.save_cfg(projectfolder=self.dict_folders['project'])

        self.graphGroups()
        if row is not None:
            processRow(row)
            updateZoom(df)
        else:
            df = df or uistate.df_recs2plot
            if df is not None and not df.empty:
                processDataFrame(df)
                updateZoom(df)
        print("graphUpdate calls uiplot.graphRefresh()")
        uiplot.graphRefresh()


    def updateMouseover(self):
        self.mouseoverDisconnect()
        # if only one item is selected, make a new mouseover event connection
        if len(uistate.selected) == 1:
            df_p = self.get_df_project()
            uistate.row_copy = df_p.loc[uistate.selected[0]].copy()
            self.dfmean = self.get_dfmean(row=uistate.row_copy) # TODO: potential ISSUE: persisted dfmean overwritten only on selecting new single line
            uistate.setMargins(axm=uistate.axm)
            connect = False
            for line in uistate.axm.lines: # connects plotted lines
                label = line.get_label()
                rec_name = uistate.row_copy['recording_name']
                if label == f"{rec_name} EPSP slope marker":
                    uistate.updateDragZones(aspect="EPSP slope", x=line.get_xdata(), y=line.get_ydata())
                    connect = True
                elif label == f"{rec_name} EPSP amp marker":
                    uistate.updatePointDragZone(aspect="EPSP amp move", x=line.get_xdata()[0], y=line.get_ydata()[0])
                    connect = True
                elif label == f"{rec_name} volley slope marker":
                    uistate.updateDragZones(aspect="volley slope", x=line.get_xdata(), y=line.get_ydata())
                    connect = True
                elif label == f"{rec_name} volley amp marker":
                    uistate.updatePointDragZone(aspect="volley amp move", x=line.get_xdata()[0], y=line.get_ydata()[0])
                    connect = True
            if connect: # set new mouseover event connection
                self.mouseover = self.main_canvas_mean.mpl_connect('motion_notify_event', uiplot.graphMouseover)
        print("updateMouseover calls uiplot.graphRefresh()")
        uiplot.graphRefresh()

    def mouseoverDisconnect(self):
        # drop any prior mouseover event connections and plots
        if hasattr(self, 'mouseover'):
            self.main_canvas_mean.mpl_disconnect(self.mouseover)
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

    def mainClicked(self, event, canvas, out=False): # maingraph click event
        x = event.xdata
        time_values = self.dfmean['time'].values
        uistate.prior_x_idx = np.abs(time_values - x).argmin() # nearest x-index to click
        if event.inaxes is not None:
            if (event.button == 1 or event.button == 3) and (uistate.mouseover_action is not None):
                # mouseover what?
                action = uistate.mouseover_action
                print(f"action: {action}")
                if action.startswith("EPSP slope"):
                    start, end = uistate.row_copy['t_EPSP_slope_start'], uistate.row_copy['t_EPSP_slope_end']
                    self.mouse_drag = self.main_canvas_mean.mpl_connect('motion_notify_event', lambda event: self.mainDragSlope(event, time_values, action, start, end))
                elif action == 'EPSP amp move':
                    self.mouse_drag = self.main_canvas_mean.mpl_connect('motion_notify_event', lambda event: self.mainDragPoint(event, time_values))
                elif action.startswith("volley slope"):
                    start, end = uistate.row_copy['t_volley_slope_start'], uistate.row_copy['t_volley_slope_end']
                    self.mouse_drag = self.main_canvas_mean.mpl_connect('motion_notify_event', lambda event: self.mainDragSlope(event, time_values, action, start, end))
                elif action == 'volley amp move':
                    self.mouse_drag = self.main_canvas_mean.mpl_connect('motion_notify_event', lambda event: self.mainDragPoint(event, time_values))
                self.mouse_release = self.main_canvas_mean.mpl_connect('button_release_event', self.mainReleased)
            elif event.button == 2:
                self.zoomReset(canvas=canvas, out=out)


    def mainDragSlope(self, event, time_values, action, prior_slope_start, prior_slope_end): # maingraph dragging event
        self.main_canvas_mean.mpl_disconnect(self.mouseover)
        if event.xdata is None:
            return
        uistate.x_idx = np.abs(time_values - event.xdata).argmin()  # update x to the nearest x-value on the plot
        if uistate.x_idx == uistate.last_x_idx: # if the dragged event hasn't moved an index point, change nothing
            return
        precision = len(str(time_values[1] - time_values[0]).split('.')[1])
        time_diff = time_values[uistate.x_idx] - time_values[uistate.prior_x_idx]

        # get the x values of the slope
        blob = True # only moving amplitudes and resizing slopes have a blob
        if action.endswith('resize'):
            x_start = prior_slope_start
        elif action.endswith('move'):
            x_start = round(prior_slope_start + time_diff, precision)
            blob = False
        x_end = round(prior_slope_end + time_diff, precision)
        # prevent resizing below 1 index - TODO: make it flip instead
        if x_end <= x_start: # TODO: 
            x_start_index = np.where(time_values == x_start)[0][0]
            x_end = time_values[x_start_index + 1] 
        x_indices = self.dfmean['time'].searchsorted([x_start, x_end])

        # get y values from the appropriate filter of persisted dfmean
        rec_filter = uistate.row_copy['filter']
        y_start, y_end = self.dfmean[rec_filter].iloc[x_indices]

        # remember the last x index
        uistate.last_x_idx = uistate.x_idx

        # update the mouseover plot
        uistate.mouseover_plot[0].set_data([x_start, x_end], [y_start, y_end])

        if blob:
            uistate.mouseover_blob.set_offsets([x_end, y_end])
        self.main_canvas_mean.draw()
        self.mainDragUpdate(x_start, x_end, precision)


    def mainDragPoint(self, event, time_values): # maingraph dragging event
        self.main_canvas_mean.mpl_disconnect(self.mouseover)
        if event.xdata is None:
            return
        uistate.x_idx = np.abs(time_values - event.xdata).argmin()  # update x to the nearest x-value on the plot
        if uistate.x_idx == uistate.last_x_idx: # if the dragged event hasn't moved an index point, change nothing
            return
        precision = len(str(time_values[1] - time_values[0]).split('.')[1])
        
        x_point = time_values[uistate.x_idx]
        x_idx = self.dfmean['time'].searchsorted(x_point)

        # get y values from the appropriate filter of persisted dfmean
        rec_filter = uistate.row_copy['filter']
        y_point = self.dfmean[rec_filter].iloc[x_idx]

        # remember the last x index
        uistate.last_x_idx = uistate.x_idx
        # update the mouseover plot
        uistate.mouseover_blob.set_offsets([x_point, y_point])

        self.main_canvas_mean.draw()
        self.mainDragUpdate(x_point, x_point, precision)
  

    def mainDragUpdate(self, x_start, x_end, precision): # update output; this is a separate function to allow the user to make it happen live (current) or on release (for low compute per data)
        dffilter = self.get_dffilter(row=uistate.row_copy)
        action = uistate.mouseover_action
        
        if action.startswith("EPSP slope"):
            dict_t = { # only pass these values to build_dfoutput, so it won't rebuild unchanged values
                't_EPSP_slope_start': x_start,
                't_EPSP_slope_end': x_end,
                't_EPSP_slope_width': round(x_end - x_start, precision),
            }
            color = 'green'
            out = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
            if uistate.mouseover_out is None:
                if uistate.checkBox['norm_EPSP']:
                    out = self.normOutput(row=uistate.row_copy, dfoutput=out, aspect='EPSP_slope')
                    uistate.mouseover_out = uistate.ax2.plot(out['sweep'], out['EPSP_slope_norm'], color=color)
                else:
                    uistate.mouseover_out = uistate.ax2.plot(out['sweep'], out['EPSP_slope'], color=color)
            else:
                if uistate.checkBox['norm_EPSP']:
                    out = self.normOutput(row=uistate.row_copy, dfoutput=out, aspect='EPSP_slope')
                    uistate.mouseover_out[0].set_data(out['sweep'], out['EPSP_slope_norm'])
                else:
                    uistate.mouseover_out[0].set_data(out['sweep'], out['EPSP_slope'])
        elif action == "EPSP amp move":
            dict_t = {'t_EPSP_amp': x_start}
            color = 'green'
            out = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
            if uistate.mouseover_out is None:
                if uistate.checkBox['norm_EPSP']:
                    out = self.normOutput(row=uistate.row_copy, dfoutput=out, aspect='EPSP_amp')
                    uistate.mouseover_out = uistate.ax1.plot(out['sweep'], out['EPSP_amp_norm'], color=color)
                else:
                    uistate.mouseover_out = uistate.ax1.plot(out['sweep'], out['EPSP_amp'], color=color)
            else:
                if uistate.checkBox['norm_EPSP']:
                    out = self.normOutput(row=uistate.row_copy, dfoutput=out, aspect='EPSP_amp')
                    uistate.mouseover_out[0].set_data(out['sweep'], out['EPSP_amp_norm'])
                else:
                    uistate.mouseover_out[0].set_data(out['sweep'], out['EPSP_amp'])
        elif action.startswith("volley slope"):
            dict_t = {
                't_volley_slope_start': x_start,
                't_volley_slope_end': x_end,
                't_volley_slope_width': round(x_end - x_start, precision),
            }
            color = 'blue'
            out = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
            if uistate.mouseover_out is None:
                uistate.mouseover_out = uistate.ax2.plot(out['sweep'], out['volley_slope'], color=color)
            else:
                uistate.mouseover_out[0].set_data(out['sweep'], out['volley_slope'])
            dict_t['volley_slope_mean'] = out['volley_slope'].mean()

        elif action == "volley amp move":
            dict_t = {'t_volley_amp': x_start}
            color = 'blue'
            out = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
            if uistate.mouseover_out is None:
                uistate.mouseover_out = uistate.ax1.plot(out['sweep'], out['volley_amp'], color=color,  linestyle='--')
            else:
                uistate.mouseover_out[0].set_data(out['sweep'], out['volley_amp'])
            dict_t['volley_amp_mean'] = out['volley_amp'].mean()

        if dict_t:
            uistate.row_copy.update(dict_t)
        self.main_canvas_output.draw()


    def mainReleased(self, event): # maingraph release event
        self.usage("mainReleased")
        print(f" - uistate.mouseover_action: {uistate.mouseover_action}")
        self.main_canvas_mean.mpl_disconnect(self.mouse_drag)
        self.main_canvas_mean.mpl_disconnect(self.mouse_release)
        uistate.last_x_idx = None
        if uistate.x_idx == uistate.prior_x_idx: # nothing to update
            print("x_idx == prior_x_idx")
            self.updateMouseover()
            return
        
        if uistate.mouseover_action.startswith("EPSP slope"):
            uistate.row_copy['t_EPSP_slope_method'] = "manual"
            uiplot.plotUpdate(row=uistate.row_copy, aspect='EPSP slope', dfmean=self.dfmean)
            uistate.updateDragZones()
            dict_t = {'t_EPSP_slope_start': uistate.row_copy['t_EPSP_slope_start'], 't_EPSP_slope_end': uistate.row_copy['t_EPSP_slope_end']}
        elif uistate.mouseover_action == 'EPSP amp move':
            uistate.row_copy['t_EPSP_amp_method'] = "manual"
            uiplot.plotUpdate(row=uistate.row_copy, aspect='EPSP amp', dfmean=self.dfmean)
            uistate.updatePointDragZone()
            dict_t = {'t_EPSP_amp': uistate.row_copy['t_EPSP_amp']}
        elif uistate.mouseover_action.startswith("volley slope"):
            uistate.row_copy['t_volley_slope_method'] = "manual"
            uiplot.plotUpdate(row=uistate.row_copy, aspect='volley slope', dfmean=self.dfmean)
            uistate.updateDragZones()
            dict_t = {'t_volley_slope_start': uistate.row_copy['t_volley_slope_start'], 't_volley_slope_end': uistate.row_copy['t_volley_slope_end']}
        elif uistate.mouseover_action == 'volley amp move':
            uistate.row_copy['t_volley_amp_method'] = "manual"
            uiplot.plotUpdate(row=uistate.row_copy, aspect='volley amp', dfmean=self.dfmean)
            uistate.updatePointDragZone()
            dict_t = {'t_volley_amp': uistate.row_copy['t_volley_amp']}

        # update df_p with uistate.row_copy, allocated by unique ID
        df_p = self.get_df_project()
        df_update = pd.DataFrame(uistate.row_copy).T.set_index('ID')
        df_p.set_index('ID', inplace=True)
        df_p.update(df_update)
        df_p.reset_index(inplace=True)
        self.set_df_project(df_p)

        # update dfoutput; dict and file, with normalized columns if applicable
        row = uistate.row_copy
        dfoutput = self.get_dfoutput(row=row)
        dffilter = self.get_dffilter(row=uistate.row_copy)
        new_dfoutput_columns = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
        for col in new_dfoutput_columns.columns:
            dfoutput[col] = new_dfoutput_columns[col]
        self.tableUpdate()
        if uistate.mouseover_action.startswith("EPSP"): # add normalized EPSP columns
            self.normOutput(row=row, dfoutput=dfoutput)
        self.updateMouseover()
        if config.talkback:
            self.talkback()


    def zoomOnScroll(self, event, parent, canvas, ax1=None, ax2=None):
        x = event.xdata
        y = event.ydata
        y2 = event.ydata
        if x is None or y is None: # if the click was outside the canvas, extrapolate x and y
            x_display, y_display = ax1.transAxes.inverted().transform((event.x, event.y))
            x = x_display * (ax1.get_xlim()[1] - ax1.get_xlim()[0]) + ax1.get_xlim()[0]
            y = y_display * (ax1.get_ylim()[1] - ax1.get_ylim()[0]) + ax1.get_ylim()[0]
            if ax2 is not None:
                y2 = y_display * (ax2.get_ylim()[1] - ax2.get_ylim()[0]) + ax2.get_ylim()[0]
        if event.button == 'up':
            zoom = 1.05
        elif event.button == 'down':
            zoom = 1 / 1.05
        else:
            return
        # Define the boundaries of the invisible rectangles
        left = 0.12 * parent.width()
        right = 0.88 * parent.width()
        bottom = 0.12 * parent.height() # NB: counts from bottom up!
        x_rect = [0, 0, parent.width(), bottom]
        slope_left = uistate.slopeOnly()
        if slope_left:
            ax2_rect = [0, 0, left, parent.height()]
        else:
            ax1_rect = [0, 0, left, parent.height()]
            ax2_rect = [right, 0, parent.width()-right, parent.height()]

        # Check if the event is within each rectangle
        in_x = x_rect[0] <= event.x <= x_rect[0] + x_rect[2] and x_rect[1] <= event.y <= x_rect[1] + x_rect[3]
        if slope_left:
            in_ax1 = False
        else:
            in_ax1 = ax1_rect[0] <= event.x <= ax1_rect[0] + ax1_rect[2] and ax1_rect[1] <= event.y <= ax1_rect[1] + ax1_rect[3]
        if ax2 is not None:
            in_ax2 = ax2_rect[0] <= event.x <= ax2_rect[0] + ax2_rect[2] and ax2_rect[1] <= event.y <= ax2_rect[1] + ax2_rect[3]
        else:
            in_ax2 = False
        
        if in_x:
            ax1.set_xlim(x - (x - ax1.get_xlim()[0]) / zoom, x + (ax1.get_xlim()[1] - x) / zoom)
        if in_ax1:
            ax1.set_ylim(y - (y - ax1.get_ylim()[0]) / zoom, y + (ax1.get_ylim()[1] - y) / zoom)
        if ax2 is not None:
            if in_ax2:
                ax2.set_ylim(y2 - (y2 - ax2.get_ylim()[0]) / zoom, y2 + (ax2.get_ylim()[1] - y2) / zoom)
        # if all in_s are false, zoom all axes
        if not in_x and not in_ax1 and not in_ax2:
            ax1.set_xlim(x - (x - ax1.get_xlim()[0]) / zoom, x + (ax1.get_xlim()[1] - x) / zoom)
            ax1.set_ylim(y - (y - ax1.get_ylim()[0]) / zoom, y + (ax1.get_ylim()[1] - y) / zoom)
            if ax2 is not None:
                ax2.set_ylim(y2 - (y2 - ax2.get_ylim()[0]) / zoom, y2 + (ax2.get_ylim()[1] - y2) / zoom)
        canvas.draw()


    def zoomReset(self, canvas, out=False):
        if out:
            axes_in_figure = canvas.figure.get_axes()
            for ax in axes_in_figure:
                if ax.get_ylabel() == "Amplitude (mV)":
                    ax.set_ylim(uistate.zoom['output_ax1_ylim'])
                elif ax.get_ylabel() == "Slope (mV/ms)":
                    ax.set_ylim(uistate.zoom['output_ax2_ylim'])
                df_p = self.get_df_project()
                uistate.zoom['output_xlim'] = [0, df_p['sweeps'].max()]
                ax.set_xlim(uistate.zoom['output_xlim'])
        else:
            canvas.axes.set_xlim(uistate.zoom['mean_xlim'])
            canvas.axes.set_ylim(uistate.zoom['mean_ylim'])
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
            "ID",
            "host",
            "path",
            "recording_name",
            "group_IDs",
            "groups",
            "parsetimestamp",
            "sweeps",
            "channel",
            "stim",
            "paired_recording",
            "Tx",
            "filter",
            "filter_params",
            "n_stims",
            # TODO: deprecate timepoints
            "t_stim",
            "t_stim_method",
            "t_stim_params",
            "t_volley_amp",
            "t_volley_amp_method",
            "t_volley_amp_params",
            "t_volley_slope_width",
            "t_volley_slope_halfwidth",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_volley_slope_method",
            "t_volley_slope_params",
            "volley_amp_mean",
            "volley_slope_mean",
            "t_VEB",
            "t_VEB_method",
            "t_VEB_params",
            "t_EPSP_amp",
            "t_EPSP_amp_method",
            "t_EPSP_amp_params",
            "t_EPSP_slope_width",
            "t_EPSP_slope_halfwidth",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_EPSP_slope_method",
            "t_EPSP_slope_params",

            "exclude",
            "comment",
        ]
    )

def df_timepointsTemplate():
    return pd.DataFrame(
        columns=[
            "stim", # stim number in sequence
            "t_stim",
            "t_stim_method",
            "t_stim_params",
            "t_volley_amp",
            "t_volley_amp_method",
            "t_volley_amp_params",
            "t_volley_slope_width",
            "t_volley_slope_halfwidth",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_volley_slope_method",
            "t_volley_slope_params",
            "volley_amp_mean",
            "volley_slope_mean",
            "t_VEB",
            "t_VEB_method",
            "t_VEB_params",
            "t_EPSP_amp",
            "t_EPSP_amp_method",
            "t_EPSP_amp_params",
            "t_EPSP_slope_width",
            "t_EPSP_slope_halfwidth",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_EPSP_slope_method",
            "t_EPSP_slope_params",
        ]
    )


def report(): # debug function to report custom aspects of the current state of the program
    if False:
        print ("\n REPORT:")
    



if __name__ == "__main__":
    print(f"\n\n{config.program_name} {config.version}\n")
    app = QtWidgets.QApplication(sys.argv) # "QtWidgets.QApplication(sys.argv) appears to cause Qt: Session management error: None of the authentication protocols specified are supported"
    main_window = QtWidgets.QMainWindow()
    uisub = UIsub(main_window)
    main_window.show()
    sys.exit(app.exec_())