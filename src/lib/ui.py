import os  # TODO: replace use by pathlib?
import sys
from pathlib import Path
import yaml

import matplotlib

# import matplotlib.pyplot as plt # TODO: use instead of matplotlib for smaller import?
import seaborn as sns
#import scipy.stats as stats

import numpy as np  # numeric calculations module
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

# from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets
from datetime import datetime
import re
import time

import parse
import analysis

matplotlib.use("Qt5Agg")

verbose = True
track_widget_focus = False
# expand as more aspects and filters are added
# TODO: make these redundant by looping through data columns
supported_aspects = [ "EPSP_amp", "EPSP_slope"]


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
        self.verbose = verbose
        self.checks = {}
        self.nodestack = []
        self.parent_index = self.setRootPath(self.root_path)
        self.root_index = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot)
        self.sort(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.directoryLoaded.connect(self._loaded)

    def _loaded(self, path):
        if self.verbose:
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
            if verbose:
                print("setData(): {}".format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def traverseDirectory(self, parentindex, callback=None):
        if verbose:
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


################################################################
# section directly copied from output from pyuic, do not alter #
# WARNING: changed parent class 'object' to 'QtCore.QObject'   #
################################################################


class QDialog_sub(QtWidgets.QDialog):
    # Sub-classed to make a custom closeEvent that disconnects all signals to it, while preserving those in main window
    def __init__(self):
        super(QDialog_sub, self).__init__()
        self.list_connections = []

    def closeEvent(self, event):
        error = None
        for signal, method in self.list_connections:
            try:
                signal.disconnect(method)
            except TypeError as e:
                error = e
                pass
        if error is None:
            print(f"Signals disconnected from subwindow {self.windowTitle()}")
        else:
            print(f"Warning! {self.windowTitle()}: {error} at closeEvent") # TODO: Shouldn't happen - why does it?
        super(QDialog_sub, self).closeEvent(event)

class Ui_measure_window(QtCore.QObject):
    def setupUi(self, measure):
        measure.setObjectName("measure")
        measure.resize(595, 812)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(measure.sizePolicy().hasHeightForWidth())
        measure.setSizePolicy(sizePolicy)
        measure.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.gridLayout = QtWidgets.QGridLayout(measure)
        self.gridLayout.setObjectName("gridLayout")
        self.measure_verticalLayout = QtWidgets.QVBoxLayout()
        self.measure_verticalLayout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.measure_verticalLayout.setObjectName("measure_verticalLayout")
        self.measure_graph_mean = QtWidgets.QWidget(measure)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.measure_graph_mean.sizePolicy().hasHeightForWidth())
        self.measure_graph_mean.setSizePolicy(sizePolicy)
        self.measure_graph_mean.setObjectName("measure_graph_mean")
        self.measure_verticalLayout.addWidget(self.measure_graph_mean)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.frame_measure_toolbox = QtWidgets.QFrame(measure)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_measure_toolbox.sizePolicy().hasHeightForWidth())
        self.frame_measure_toolbox.setSizePolicy(sizePolicy)
        self.frame_measure_toolbox.setMinimumSize(QtCore.QSize(320, 135))
        self.frame_measure_toolbox.setMaximumSize(QtCore.QSize(320, 135))
        self.frame_measure_toolbox.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_measure_toolbox.setFrameShadow(QtWidgets.QFrame.Plain)
        self.frame_measure_toolbox.setLineWidth(0)
        self.frame_measure_toolbox.setObjectName("frame_measure_toolbox")
        self.pushButton_EPSP_slope = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_EPSP_slope.setGeometry(QtCore.QRect(10, 40, 83, 25))
        self.pushButton_EPSP_slope.setObjectName("pushButton_EPSP_slope")
        self.pushButton_EPSP_amp = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_EPSP_amp.setGeometry(QtCore.QRect(10, 100, 83, 25))
        self.pushButton_EPSP_amp.setObjectName("pushButton_EPSP_amp")
        self.pushButton_EPSP_size = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_EPSP_size.setGeometry(QtCore.QRect(10, 70, 83, 25))
        self.pushButton_EPSP_size.setObjectName("pushButton_EPSP_size")
        self.pushButton_volley_size = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_volley_size.setGeometry(QtCore.QRect(170, 70, 83, 25))
        self.pushButton_volley_size.setObjectName("pushButton_volley_size")
        self.pushButton_volley_amp = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_volley_amp.setGeometry(QtCore.QRect(170, 100, 83, 25))
        self.pushButton_volley_amp.setObjectName("pushButton_volley_amp")
        self.pushButton_volley_slope = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_volley_slope.setGeometry(QtCore.QRect(170, 40, 83, 25))
        self.pushButton_volley_slope.setObjectName("pushButton_volley_slope")
        self.label_EPSP_ms = QtWidgets.QLabel(self.frame_measure_toolbox)
        self.label_EPSP_ms.setGeometry(QtCore.QRect(110, 20, 21, 17))
        self.label_EPSP_ms.setObjectName("label_EPSP_ms")
        self.label_volley_ms = QtWidgets.QLabel(self.frame_measure_toolbox)
        self.label_volley_ms.setGeometry(QtCore.QRect(270, 20, 21, 17))
        self.label_volley_ms.setObjectName("label_volley_ms")
        self.lineEdit_volley_slope = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_volley_slope.setGeometry(QtCore.QRect(260, 40, 51, 25))
        self.lineEdit_volley_slope.setObjectName("lineEdit_volley_slope")
        self.lineEdit_volley_size = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_volley_size.setGeometry(QtCore.QRect(260, 70, 51, 25))
        self.lineEdit_volley_size.setObjectName("lineEdit_volley_size")
        self.lineEdit_volley_amp = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_volley_amp.setGeometry(QtCore.QRect(260, 100, 51, 25))
        self.lineEdit_volley_amp.setObjectName("lineEdit_volley_amp")
        self.lineEdit_EPSP_size = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_EPSP_size.setGeometry(QtCore.QRect(100, 70, 51, 25))
        self.lineEdit_EPSP_size.setObjectName("lineEdit_EPSP_size")
        self.lineEdit_EPSP_amp = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_EPSP_amp.setGeometry(QtCore.QRect(100, 100, 51, 25))
        self.lineEdit_EPSP_amp.setObjectName("lineEdit_EPSP_amp")
        self.lineEdit_EPSP_slope = QtWidgets.QLineEdit(self.frame_measure_toolbox)
        self.lineEdit_EPSP_slope.setGeometry(QtCore.QRect(100, 40, 51, 25))
        self.lineEdit_EPSP_slope.setObjectName("lineEdit_EPSP_slope")
        self.pushButton_auto = QtWidgets.QPushButton(self.frame_measure_toolbox)
        self.pushButton_auto.setGeometry(QtCore.QRect(10, 10, 83, 25))
        self.pushButton_auto.setObjectName("pushButton_auto")
        self.horizontalLayout.addWidget(self.frame_measure_toolbox)
        self.frame_measure_view = QtWidgets.QFrame(measure)
        self.frame_measure_view.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_measure_view.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_measure_view.setObjectName("frame_measure_view")
        self.label_filter = QtWidgets.QLabel(self.frame_measure_view)
        self.label_filter.setGeometry(QtCore.QRect(10, 10, 62, 17))
        self.label_filter.setObjectName("label_filter")
        self.lineEdit_filter_param1 = QtWidgets.QLineEdit(self.frame_measure_view)
        self.lineEdit_filter_param1.setGeometry(QtCore.QRect(190, 30, 51, 25))
        self.lineEdit_filter_param1.setObjectName("lineEdit_filter_param1")
        self.radioButton_filter_placeholder = QtWidgets.QRadioButton(self.frame_measure_view)
        self.radioButton_filter_placeholder.setGeometry(QtCore.QRect(10, 70, 106, 23))
        self.radioButton_filter_placeholder.setObjectName("radioButton_filter_placeholder")
        self.label_filter_param2 = QtWidgets.QLabel(self.frame_measure_view)
        self.label_filter_param2.setGeometry(QtCore.QRect(110, 70, 71, 23))
        self.label_filter_param2.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.label_filter_param2.setObjectName("label_filter_param2")
        self.lineEdit_filter_param2 = QtWidgets.QLineEdit(self.frame_measure_view)
        self.lineEdit_filter_param2.setGeometry(QtCore.QRect(190, 70, 51, 25))
        self.lineEdit_filter_param2.setObjectName("lineEdit_filter_param2")
        self.label_filter_params = QtWidgets.QLabel(self.frame_measure_view)
        self.label_filter_params.setGeometry(QtCore.QRect(110, 10, 91, 17))
        self.label_filter_params.setObjectName("label_filter_params")
        self.radioButton_filter_savgol = QtWidgets.QRadioButton(self.frame_measure_view)
        self.radioButton_filter_savgol.setGeometry(QtCore.QRect(10, 50, 106, 23))
        self.radioButton_filter_savgol.setObjectName("radioButton_filter_savgol")
        self.radioButton_filter_none = QtWidgets.QRadioButton(self.frame_measure_view)
        self.radioButton_filter_none.setGeometry(QtCore.QRect(10, 30, 106, 23))
        self.radioButton_filter_none.setObjectName("radioButton_filter_none")
        self.label_filter_param1 = QtWidgets.QLabel(self.frame_measure_view)
        self.label_filter_param1.setGeometry(QtCore.QRect(110, 30, 71, 23))
        self.label_filter_param1.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.label_filter_param1.setObjectName("label_filter_param1")
        self.horizontalLayout.addWidget(self.frame_measure_view)
        self.measure_verticalLayout.addLayout(self.horizontalLayout)
        self.measure_graph_output = QtWidgets.QWidget(measure)
        self.measure_graph_output.setObjectName("measure_graph_output")
        self.measure_verticalLayout.addWidget(self.measure_graph_output)
        self.measure_info = QtWidgets.QTableView(measure)
        self.measure_info.setMinimumSize(QtCore.QSize(0, 50))
        self.measure_info.setObjectName("measure_info")
        self.measure_verticalLayout.addWidget(self.measure_info)
        self.buttonBox = QtWidgets.QDialogButtonBox(measure)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.measure_verticalLayout.addWidget(self.buttonBox)
        self.measure_verticalLayout.setStretch(0, 5)
        self.measure_verticalLayout.setStretch(1, 1)
        self.measure_verticalLayout.setStretch(2, 5)
        self.measure_verticalLayout.setStretch(3, 1)
        self.gridLayout.addLayout(self.measure_verticalLayout, 0, 0, 1, 1)

        self.retranslateUi(measure)
        self.buttonBox.accepted.connect(measure.accept) # type: ignore
        self.buttonBox.rejected.connect(measure.reject) # type: ignore
        QtCore.QMetaObject.connectSlotsByName(measure)

    def retranslateUi(self, measure):
        _translate = QtCore.QCoreApplication.translate
        measure.setWindowTitle(_translate("measure", "Placeholder Window Title"))
        self.pushButton_EPSP_slope.setText(_translate("measure", "EPSP slope"))
        self.pushButton_EPSP_amp.setText(_translate("measure", "EPSP amp."))
        self.pushButton_EPSP_size.setText(_translate("measure", "EPSP size"))
        self.pushButton_volley_size.setText(_translate("measure", "Volley size"))
        self.pushButton_volley_amp.setText(_translate("measure", "Volley amp."))
        self.pushButton_volley_slope.setText(_translate("measure", "Volley slope"))
        self.label_EPSP_ms.setText(_translate("measure", "ms"))
        self.label_volley_ms.setText(_translate("measure", "ms"))
        self.pushButton_auto.setText(_translate("measure", "Auto"))
        self.label_filter.setText(_translate("measure", "Filter"))
        self.radioButton_filter_placeholder.setText(_translate("measure", "...more"))
        self.label_filter_param2.setText(_translate("measure", "PolyOrder"))
        self.label_filter_params.setText(_translate("measure", "Parameters"))
        self.radioButton_filter_savgol.setText(_translate("measure", "SavGol"))
        self.radioButton_filter_none.setText(_translate("measure", "No filter"))
        self.label_filter_param1.setText(_translate("measure", "Window"))




################################################################
# section directly copied from output from pyuic, do not alter #
# trying to make all the rest work with it                     #
# WARNING: I was forced to change the parent class from        #
# 'object' to 'QtCore.QObject' for the pyqtSlot(list) to work  #
################################################################


class Ui_MainWindow(QtCore.QObject):
    def setupUi(self, mainWindow):
        mainWindow.setObjectName("mainWindow")
        mainWindow.resize(1066, 777)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName("horizontalLayoutCentralwidget")
        self.horizontalMasterLayout = QtWidgets.QHBoxLayout()
        self.horizontalMasterLayout.setObjectName("horizontalMasterLayout")
        self.verticalLayoutProj = QtWidgets.QVBoxLayout()
        self.verticalLayoutProj.setObjectName("verticalLayoutProj")
        self.horizontalLayoutProj = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProj.setObjectName("horizontalLayoutProj")
        self.pushButtonNewProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonNewProject.setMaximumSize(QtCore.QSize(50, 16777215))
        self.pushButtonNewProject.setObjectName("pushButtonNewProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonNewProject)
        self.pushButtonOpenProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonOpenProject.setEnabled(True)
        self.pushButtonOpenProject.setMaximumSize(QtCore.QSize(50, 16777215))
        self.pushButtonOpenProject.setObjectName("pushButtonOpenProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonOpenProject)
        self.inputProjectName = QtWidgets.QLineEdit(self.centralwidget)
        self.inputProjectName.setMinimumSize(QtCore.QSize(150, 0))
        self.inputProjectName.setReadOnly(True)
        self.inputProjectName.setObjectName("inputProjectName")
        self.horizontalLayoutProj.addWidget(self.inputProjectName)
        self.pushButtonRenameProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonRenameProject.setMaximumSize(QtCore.QSize(65, 16777215))
        self.pushButtonRenameProject.setObjectName("pushButtonRenameProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonRenameProject)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutProj)
        self.horizontalLayoutData = QtWidgets.QHBoxLayout()
        self.horizontalLayoutData.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        self.horizontalLayoutData.setObjectName("horizontalLayoutData")
        self.pushButtonAddData = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonAddData.setObjectName("pushButtonAddData")
        self.horizontalLayoutData.addWidget(self.pushButtonAddData)
        self.pushButtonParse = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonParse.setObjectName("pushButtonParse")
        self.horizontalLayoutData.addWidget(self.pushButtonParse)
        self.checkBoxLockDelete = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBoxLockDelete.setMaximumSize(QtCore.QSize(15, 16777215))
        self.checkBoxLockDelete.setText("")
        self.checkBoxLockDelete.setChecked(True)
        self.checkBoxLockDelete.setObjectName("checkBoxLockDelete")
        self.horizontalLayoutData.addWidget(self.checkBoxLockDelete)
        self.pushButtonDelete = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonDelete.setMaximumSize(QtCore.QSize(60, 16777215))
        self.pushButtonDelete.setObjectName("pushButtonDelete")
        self.horizontalLayoutData.addWidget(self.pushButtonDelete)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.horizontalLayoutData.addWidget(self.label)
        self.pushButtonAddGroup = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonAddGroup.setMaximumSize(QtCore.QSize(40, 16777215))
        self.pushButtonAddGroup.setObjectName("pushButtonAddGroup")
        self.horizontalLayoutData.addWidget(self.pushButtonAddGroup)
        self.pushButtonEditGroups = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonEditGroups.setMaximumSize(QtCore.QSize(40, 16777215))
        self.pushButtonEditGroups.setObjectName("pushButtonEditGroups")
        self.horizontalLayoutData.addWidget(self.pushButtonEditGroups)
        self.pushButtonClearGroups = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonClearGroups.setMaximumSize(QtCore.QSize(40, 16777215))
        self.pushButtonClearGroups.setObjectName("pushButtonClearGroups")
        self.horizontalLayoutData.addWidget(self.pushButtonClearGroups)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutData)
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayoutProj.addLayout(self.gridLayout)
        self.tableProj = QtWidgets.QTableView(self.centralwidget)
        self.tableProj.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.tableProj.setAcceptDrops(True)
        self.tableProj.setObjectName("tableProj")
        self.verticalLayoutProj.addWidget(self.tableProj)
        self.horizontalMasterLayout.addLayout(self.verticalLayoutProj)
        spacerItem = QtWidgets.QSpacerItem(10, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalMasterLayout.addItem(spacerItem)
        self.verticalLayoutGraph = QtWidgets.QVBoxLayout()
        self.verticalLayoutGraph.setObjectName("verticalLayoutGraph")
        self.labelMeanSweep = QtWidgets.QLabel(self.centralwidget)
        self.labelMeanSweep.setObjectName("labelMeanSweep")
        self.verticalLayoutGraph.addWidget(self.labelMeanSweep)
        self.graphMean = QtWidgets.QWidget(self.centralwidget)
        self.graphMean.setMinimumSize(QtCore.QSize(0, 100))
        self.graphMean.setObjectName("graphMean")
        self.verticalLayoutGraph.addWidget(self.graphMean)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.frame_main_view = QtWidgets.QFrame(self.centralwidget)
        self.frame_main_view.setMinimumSize(QtCore.QSize(0, 100))
        self.frame_main_view.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_main_view.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_main_view.setObjectName("frame_main_view")
        self.checkBox_aspect_EPSP_amp = QtWidgets.QCheckBox(self.frame_main_view)
        self.checkBox_aspect_EPSP_amp.setGeometry(QtCore.QRect(10, 50, 90, 23))
        self.checkBox_aspect_EPSP_amp.setObjectName("checkBox_aspect_EPSP_amp")
        self.checkBox_aspect_EPSP_slope = QtWidgets.QCheckBox(self.frame_main_view)
        self.checkBox_aspect_EPSP_slope.setGeometry(QtCore.QRect(10, 30, 90, 23))
        self.checkBox_aspect_EPSP_slope.setObjectName("checkBox_aspect_EPSP_slope")
        self.label_aspect = QtWidgets.QLabel(self.frame_main_view)
        self.label_aspect.setGeometry(QtCore.QRect(10, 10, 62, 17))
        self.label_aspect.setObjectName("label_aspect")
        self.horizontalLayout.addWidget(self.frame_main_view)
        self.verticalLayoutGraph.addLayout(self.horizontalLayout)
        self.labelMeanGroups = QtWidgets.QLabel(self.centralwidget)
        self.labelMeanGroups.setObjectName("labelMeanGroups")
        self.verticalLayoutGraph.addWidget(self.labelMeanGroups)
        self.graphOutput = QtWidgets.QWidget(self.centralwidget)
        self.graphOutput.setMinimumSize(QtCore.QSize(0, 100))
        self.graphOutput.setObjectName("graphOutput")
        self.verticalLayoutGraph.addWidget(self.graphOutput)
        self.labelMetadata = QtWidgets.QLabel(self.centralwidget)
        self.labelMetadata.setObjectName("labelMetadata")
        self.verticalLayoutGraph.addWidget(self.labelMetadata)
        self.tableMetadata = QtWidgets.QTableView(self.centralwidget)
        self.tableMetadata.setObjectName("tableMetadata")
        self.verticalLayoutGraph.addWidget(self.tableMetadata)
        self.verticalLayoutGraph.setStretch(1, 5)
        self.verticalLayoutGraph.setStretch(4, 5)
        self.verticalLayoutGraph.setStretch(6, 1)
        self.horizontalMasterLayout.addLayout(self.verticalLayoutGraph)
        self.horizontalMasterLayout.setStretch(2, 1)
        self.horizontalLayoutCentralwidget.addLayout(self.horizontalMasterLayout)
        mainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(mainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1066, 22))
        self.menubar.setObjectName("menubar")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)

    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash 0.5"))
        self.pushButtonNewProject.setText(_translate("mainWindow", "New"))
        self.pushButtonOpenProject.setText(_translate("mainWindow", "Open"))
        self.inputProjectName.setText(_translate("mainWindow", "My Project"))
        self.pushButtonRenameProject.setText(_translate("mainWindow", "Rename"))
        self.pushButtonAddData.setText(_translate("mainWindow", "Add Data"))
        self.pushButtonParse.setText(_translate("mainWindow", "Analyze"))
        self.pushButtonDelete.setText(_translate("mainWindow", "Delete"))
        self.label.setText(_translate("mainWindow", "Groups:"))
        self.pushButtonAddGroup.setText(_translate("mainWindow", "Add"))
        self.pushButtonEditGroups.setText(_translate("mainWindow", "Edit"))
        self.pushButtonClearGroups.setText(_translate("mainWindow", "Clear"))
        self.labelMeanSweep.setText(_translate("mainWindow", "Mean Sweep:"))
        self.checkBox_aspect_EPSP_amp.setText(_translate("mainWindow", "EPSP amp."))
        self.checkBox_aspect_EPSP_slope.setText(_translate("mainWindow", "EPSP slope"))
        self.label_aspect.setText(_translate("mainWindow", "Aspect"))
        self.labelMeanGroups.setText(_translate("mainWindow", "Mean Groups:"))
        self.labelMetadata.setText(_translate("mainWindow", "Metadata:"))


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


#######################################################################


def df_projectTemplate():
    return pd.DataFrame(
        columns=[
            "host",
            "path",
            "checksum",
            "recording_name",
            "groups",
            "parsetimestamp",
            "sweeps",
            "channel",
            "stim",
            "filter",
            "filter_params",
            "t_stim",
            "t_stim_method",
            "t_stim_params",
            "t_VEB",
            "t_VEB_method",
            "t_VEB_params",
            "t_volley_amp",
            "t_volley_amp_method",
            "t_volley_amp_params",
            "t_volley_slope",
            "t_volley_slope_method",
            "t_volley_slope_params",
            "t_EPSP_amp",
            "t_EPSP_amp_method",
            "t_EPSP_amp_params",
            "t_EPSP_slope",
            "t_EPSP_slope_method",
            "t_EPSP_slope_params",
            "exclude",
            "comment",
        ]
    )


# subclassing Ui_MainWindow to be able to use the unaltered output file from pyuic and QT designer
class UIsub(Ui_MainWindow):
    def __init__(self, mainwindow):
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)
        if verbose:
            print(" - UIsub init, verbose mode")  # rename for clarity
        # move mainwindow to default position (TODO: later to be stored in cfg)
        self.mainwindow = mainwindow
        self.mainwindow.setGeometry(0, 0, 1400, 1200)
        # load cfg if present
        paths = [Path.cwd()] + list(Path.cwd().parents)
        self.repo_root = [i for i in paths if (-1 < str(i).find("brainwash")) & (str(i).find("src") == -1)][0]  # path to brainwash directory

        self.cfg_yaml = self.repo_root / "cfg.yaml"
        self.projectname = None
        self.inputProjectName.setReadOnly(True)

        # Set default values for 
        self.user_documents = Path.home() / "Documents"  # Where to look for raw data
        self.projects_folder = self.user_documents / "Brainwash Projects"  # Where to save and read parsed data
        self.projectname = "My Project"
        # Override default if cfg.yaml exists
        if self.cfg_yaml.exists():
            with self.cfg_yaml.open("r") as file:
                cfg = yaml.safe_load(file)
                projectfolder = Path(cfg["projects_folder"]) / cfg["projectname"]
                if projectfolder.exists():  # if the folder stored in cfg.yaml exists, use it
                    self.user_documents = Path(cfg["user_documents"])  # Where to look for raw data
                    self.projects_folder = Path(cfg["projects_folder"])  # Where to save and read parsed data
                    self.projectname = cfg["projectname"]
        
        # Make sure the necessary folders exist
        self.dict_folders = self.build_dict_folders()
        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)
        if not os.path.exists(self.dict_folders['cache']):
            os.makedirs(self.dict_folders['cache'])

        # replacing table proj with custom to allow changing of keypress event handling
        originalTableView = self.centralwidget.findChild(QtWidgets.QTableView, "tableProj")  # Find and replace the original QTableView in the layout
        #tableProj = TableProjSub(self.centralwidget)  # Create an instance of your custom table view
        tableProj = TableProjSub(self)  # Create an instance of your custom table view
        
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
       
        # If projectfile exists, load it, otherwise create it
        if Path(self.dict_folders['project'] / "project.brainwash").exists():
            self.load_df_project()
        else:
            self.setTableDf(self.df_project)
            print(f"Project file {self.dict_folders['project'] / 'project.brainwash'} not found, creating new project file")
            self.write_cfg()

        # load or write local cfg, for storage of e.g. group colours, zoom levels etc.
        self.project_cfg_yaml = self.dict_folders['project'] / "project_cfg.yaml"
        if False:#self.project_cfg_yaml.exists():
            with self.project_cfg_yaml.open("r") as file:
                self.dict_cfg = yaml.safe_load(file)
        else:
            self.dict_cfg = {'list_groups': [], # group_X - how the program regognizes groups
                        'dict_group_name': {}, # group_X: name - how the program displays groups TODO: implement
                        'dict_group_show': {}, # group_X: True/False - whether to show group in graphs
                        'list_group_colors': ["red", "green", "blue", "yellow"], # TODO: build this list properly
                        'delete_locked': True, # whether to allow deleting of data
                        'aspect_EPSP_amp': True,
                        'aspect_EPSP_slope': True,
                        'mean_ylim': (-0.0015, None),
                        'mean_xlim': (0.006, 0.020),
                        'output_ax1_ylim': (0, None),
                        'output_ax1_xlim': (None, None),
                        'output_ax2_ylim': (0, None),
                        'output_ax2_xlim': (None, None),
                        }
            self.write_project_cfg()
        # Enforce local cfg
        self.checkBoxLockDelete.setChecked(self.dict_cfg['delete_locked'])
        self.pushButtonDelete.setEnabled(not self.dict_cfg['delete_locked'])
        for group in self.dict_cfg['list_groups']:  # Generate buttons based on groups in project:
            self.addGroupButton(group)

        if track_widget_focus: # debug mode; prints widget focus every 1000ms
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.checkFocus)
            self.timer.start(1000)  

        self.resetCacheDicts() # Internal storage dicts

        # Addon to make the graphs scaleable
        self.graphMean.setLayout(QtWidgets.QVBoxLayout())
        self.canvas_seaborn_mean = MplCanvas(parent=self.graphMean)  # instantiate canvas for Mean
        self.graphMean.layout().addWidget(self.canvas_seaborn_mean)
        self.graphOutput.setLayout(QtWidgets.QVBoxLayout())
        self.canvas_seaborn_output = MplCanvas(parent=self.graphOutput)  # instantiate canvas for Mean
        self.graphOutput.layout().addWidget(self.canvas_seaborn_output)
        self.canvas_seaborn_mean.show()
        self.canvas_seaborn_mean.mpl_connect('scroll_event', lambda event: zoomOnScroll(event=event, canvas=self.canvas_seaborn_mean))
        self.canvas_seaborn_mean.mpl_connect('button_press_event', self.meanClicked)
        self.canvas_seaborn_output.show()

        # I'm guessing that all these signals and slots and connections can be defined in QT designer, and autocoded through pyuic
        # maybe learn more about that later?
        # however, I kinda like the control of putting each of them explicit here and use designer just to get the boxes right visually
        # connecting the same signals we had in original ui test
        self.pushButtonNewProject.pressed.connect(self.pushedButtonNewProject)
        self.pushButtonOpenProject.pressed.connect(self.pushedButtonOpenProject)
        self.pushButtonAddData.pressed.connect(self.pushedButtonAddData)
        self.pushButtonParse.pressed.connect(self.pushedButtonParse)
        self.pushButtonRenameProject.pressed.connect(self.pushedButtonRenameProject)
        self.pushButtonAddGroup.pressed.connect(self.pushedButtonAddGroup)
        self.pushButtonEditGroups.pressed.connect(self.pushedButtonEditGroups)
        self.pushButtonClearGroups.pressed.connect(self.pushedButtonClearGroups)
        self.pushButtonDelete.pressed.connect(self.pushedButtonDelete)
        self.checkBoxLockDelete.stateChanged.connect(self.checkedBoxLockDelete)

        self.tableProj.setSelectionBehavior(TableProjSub.SelectRows)
        self.tableProj.doubleClicked.connect(self.tableProjDoubleClicked)
        selection_model = self.tableProj.selectionModel()
        selection_model.selectionChanged.connect(self.tableProjSelectionChanged)

        # connect checkboxes to local functions TODO: refactorize to merge with similar code in __init__(self, measure_frame...
        def loopConnectViews(view, key):
            str_view_key = f"{view}_{key}"
            key_checkBox = getattr(self, f"checkBox_{str_view_key}")
            key_checkBox.setChecked(self.dict_cfg[str_view_key])
            key_checkBox.stateChanged.connect(lambda state, str_view_key=str_view_key: self.viewSettingsChanged(state, str_view_key))
        for key in supported_aspects:
            loopConnectViews(view="aspect", key=key)

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

    def build_dict_folders(self):
        dict_folders = {
                    'project': self.projects_folder / self.projectname,
                    'data': self.projects_folder / self.projectname / 'data',
                    'cache': self.projects_folder / 'cache' / self.projectname
        }
        return dict_folders

    def resetCacheDicts(self):
        self.dict_datas = {} # all raw data
        self.dict_filters = {} # all processed data
        self.dict_means = {} # all means
        self.dict_outputs = {} # all outputs
        self.dict_group_means = {} # means of all group outputs


# pushedButton functions TODO: break out the big ones to separate functions!

    def pushedButtonClearGroups(self):
        selected_rows = self.listSelectedRows()
        if 0 < len(selected_rows):
            self.clearGroupsByRow(selected_rows)
        else:
            print("No files selected.")

    def pushedButtonEditGroups(self): # Open groups UI (not built)
        if verbose:
            print("pushedButtonEditGroups")
        # Placeholder: For now, delete all buttons and groups
        # print(f"self.gridLayout: {self.gridLayout}")
        # print(f"range(self.gridLayout.count()): {range(self.gridLayout.count())}")
        self.killGroupButtons()

    def pushedButtonAddGroup(self):
        if verbose:
            print("pushedButtonGroups")
        if len(self.dict_cfg['list_groups']) < 12: # TODO: hardcoded max nr of groups: move to cfg
            i = 0
            while True:
                new_group_internal = "group_" + str(i)
                if new_group_internal in self.dict_cfg['list_groups']:
                    if verbose:
                        print(new_group_internal, " already exists")
                    i += 1
                else:
                    self.dict_cfg['list_groups'].append(new_group_internal)
                    self.dict_cfg['dict_group_show'][new_group_internal] = True
                    print("created", new_group_internal)
                    break
            self.write_project_cfg()
            self.addGroupButton(new_group_internal)
        else:
            print("Maximum of 12 groups allowed for now.")

    def pushedGroupButton(self, button_name):
        if verbose:
            print("pushedGroupButton", button_name)
        self.addToGroup(button_name)

    def pushedButtonDelete(self):
        self.deleteSelectedRows()

    def pushedButtonRenameProject(self): # renameProject
        if verbose:
            print("pushedButtonRenameProject")
        self.inputProjectName.setReadOnly(False)
        self.inputProjectName.editingFinished.connect(self.renameProject)

    def pushedButtonNewProject(self):
        if verbose:
            print("pushedButtonNewProject")
        self.dict_folders['project'].mkdir(exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        i = 0
        while True:
            new_project_name = "Project " + date
            if 0 < i:
                new_project_name = new_project_name + "(" + str(i) + ")"
            if (self.projects_folder / new_project_name).exists():
                if verbose:
                    print(new_project_name, " already exists")
                i += 1
            else:
                self.newProject(new_project_name)
                break

    def pushedButtonOpenProject(self): # open folder selector dialog
        self.dialog = QtWidgets.QDialog()
        print(f"pushedButtonOpenProject: self.projects_folder: {self.projects_folder}")
        projectfolder = QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog, "Open Directory", str(self.projects_folder), QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        
        if verbose:
            print(f"Received projectfolder: {str(projectfolder)}")
        if (Path(projectfolder) / "project.brainwash").exists():
            self.dict_folders['project'] = Path(projectfolder)
            self.clearGraph()
            self.load_df_project()
            self.write_cfg()

    def pushedButtonAddData(self): # creates file tree for file selection
        if verbose:
            print("pushedButtonAddData")
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.show()

    def pushedButtonParse(self): # parse non-parsed files and folders in self.df_project
        self.parse_data()


# Non-button event functions

    def tableProjSelectionChanged(self):
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            self.tableProj.clearSelection()
            self.setGraph()
            return
        selected_rows = self.listSelectedRows()
        df_selection = self.df_project.loc[selected_rows]
        self.setGraph(df = df_selection)

    def tableProjDoubleClicked(self):
        self.launchMeasureWindow()
   
    def checkedBoxLockDelete(self, state):
        if state == 2:
            self.dict_cfg['delete_locked']= True
        else:
            self.dict_cfg['delete_locked']= False
        self.pushButtonDelete.setEnabled(not self.dict_cfg['delete_locked'])
        if verbose:
            print(f"checkedBoxLockDelete {state}, self.dict_cfg['delete_locked']: {self.dict_cfg['delete_locked']}")
        self.write_project_cfg()


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
        df_p["groups"] = df_p["groups"].fillna(" ")
        df_p["sweeps"] = df_p["sweeps"].fillna("...")
        self.set_df_project(df_p)
        if verbose:
            print("addData:", self.get_df_project())
        self.setTableDf(df_p)

    def renameRecording(self):
        # renames all instances of selected recording_name in df_project, and their associated files
        if verbose:
            print("F2 key pressed in CustomTableView")
        selected_rows = self.listSelectedRows()
        if len(selected_rows) == 1:
            row = selected_rows[0]
            df_p = self.df_project
            old_recording_name = df_p.at[row, 'recording_name']
            old_data = self.dict_folders['data'] / (old_recording_name + ".csv")
            old_mean = self.dict_folders['cache'] / (old_recording_name + "_mean.csv")
            old_filter = self.dict_folders['cache'] / (old_recording_name + "_filter.csv")
            old_output = self.dict_folders['cache'] / (old_recording_name + "_output.csv")
            RenameDialog = InputDialogPopup()
            new_recording_name = RenameDialog.showInputDialog(title='Rename recording', query='')
            if new_recording_name is not None and re.match(r'^[a-zA-Z0-9_ -]+$', str(new_recording_name)) is not None: # check if valid filename
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
                    df_p.at[row, 'recording_name'] = new_recording_name
                    self.set_df_project(df_p)
                    self.setTableDf(self.df_project)  # Force update
                else:
                    print(f"new_recording_name {new_recording_name} already exists")
            else:
                print(f"new_recording_name {new_recording_name} is not a valid filename")    
        else:
            print("Rename: please select one row only for renaming.")

    def deleteSelectedRows(self):
        df_p = self.get_df_project()
        selected_rows = self.listSelectedRows()
        list_affected_groups = []
        if 0 < len(selected_rows):
            for row in selected_rows:
                sweeps = df_p.at[row, 'sweeps']
                if sweeps != "...": # if the file is parsed:
                    recording_name = df_p.at[row, 'recording_name']
                    if verbose:
                        print(f"Deleting {recording_name}...")
                    data_path = Path(self.dict_folders['data'] / (recording_name + ".csv"))
                    if data_path.exists():
                        data_path.unlink()
                    mean_path = Path(self.dict_folders['cache'] / (recording_name + "_mean.csv"))
                    if mean_path.exists():
                        mean_path.unlink()
                    filter_path = Path(self.dict_folders['cache'] / (recording_name + "_filter.csv"))
                    if filter_path.exists():
                        filter_path.unlink()
                    output_path = Path(self.dict_folders['cache'] / (recording_name + "_output.csv"))
                    if output_path.exists():
                        output_path.unlink()
            # Regardless of whether or not there was a file, purge the row from df_project
            self.clearGroupsByRow(selected_rows) # clear cache so that a new group mean is calculated
            df_p.drop(selected_rows, inplace=True)
            df_p.reset_index(inplace=True, drop=True)
            self.set_df_project(df_p)
            print(f"Deleted {len(list_affected_groups)}, {list_affected_groups} rows.")
            self.setTableDf(df_p)  # Force update
            self.setGraph()
        else:
            print("No files selected.")

    def parse_data(self): # parse data files and modify self.df_project accordingly
        update_frame = self.df_project.copy()  # copy from which to remove rows without confusing index
        rows = []
        for i, df_proj_row in self.df_project.iterrows():
            recording_name = df_proj_row['recording_name']
            source_path = df_proj_row['path']
            if df_proj_row["sweeps"] == "...":  # indicates not read before TODO: Replace with selector!
                dict_data = parse.parseProjFiles(dict_folders = self.dict_folders, recording_name=recording_name, source_path=source_path)
                for new_name, dict_sub in dict_data.items(): # Access 'nsweeps' from the current dictionary
                    nsweeps = dict_sub.get('nsweeps', None)
                    if nsweeps is not None:
                        df_proj_new_row = df_proj_row.copy()
                        df_proj_new_row['recording_name'] = new_name
                        df_proj_new_row['sweeps'] = nsweeps
                        df_proj_new_row['channel'] = dict_sub.get('channel', None)
                        df_proj_new_row['stim'] = dict_sub.get('stim', None)
                        rows.append(df_proj_new_row)
                update_frame = update_frame[update_frame.recording_name != recording_name]
                print(f"update_frame: {update_frame}")
                rows2add = pd.concat(rows, axis=1).transpose()
                print("rows2add:", rows2add[["recording_name", "sweeps" ]])
                self.df_project = (pd.concat([update_frame, rows2add])).reset_index(drop=True)
                print(self.df_project[["recording_name", "sweeps" ]])
                self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
                self.save_df_project()


# Data Group functions

    def addGroupButton(self, group): # Create a new group button
        hbox = QtWidgets.QHBoxLayout() # hbox for button and checkbox

        self.new_button = QtWidgets.QPushButton(group, self.centralwidget)
        self.new_button.setObjectName(group)
        self.new_button.clicked.connect(lambda: self.pushedGroupButton(group))
        hbox.addWidget(self.new_button)

        self.new_checkbox = QtWidgets.QCheckBox(group, self.centralwidget)
        self.new_checkbox.setObjectName(group)
        self.new_checkbox.setText("")
        self.new_checkbox.setChecked(self.dict_cfg['dict_group_show'][group])
        self.new_checkbox.stateChanged.connect(lambda state, group=group: self.groupCheckboxChanged(state, group))
        hbox.addWidget(self.new_checkbox)

        # Create a QWidget and set hbox as its layout
        widget = QtWidgets.QWidget()
        widget.setLayout(hbox)

        # Arrange in rows of 4. TODO: hardcoded number of columns: move to cfg
        column = self.dict_cfg['list_groups'].index(group)
        row = 0
        while column >= 4:
            column -= 4
            row += 1
        self.gridLayout.addWidget(widget, row, column, 1, 1)

    def groupCheckboxChanged(self, state, group):
        if verbose:
            print(f"groupCheckboxChanged: {state}, {group}")
        if state == 2:
            self.dict_cfg['dict_group_show'][group] = True
        else:
            self.dict_cfg['dict_group_show'][group] = False
        self.write_project_cfg()
        self.setGraph()

    def killGroupButtons(self):
        for group in self.dict_cfg['list_groups']:
            for i in range(self.gridLayout.count()):
                widget = self.gridLayout.itemAt(i).widget()
                if widget and widget.text() == group:
                    widget.deleteLater()
                    if verbose:
                        print("Removed", group, f"(widget: {widget}")
        self.dict_cfg['list_groups'] = []
        self.write_project_cfg()

    def addToGroup(self, add_group):
        # Assign all selected files to group "add_group" unless they already belong to that group
        # Kill dict_group_means and csv
        selected_rows = self.listSelectedRows()
        if 0 < len(selected_rows):
            list_group = ""
            for i in selected_rows:
                if self.df_project.loc[i, 'groups'] == " ":
                    self.df_project.loc[i, 'groups'] = add_group
                else:
                    str_group = self.df_project.loc[i, 'groups']
                    list_group = list(str_group.split(","))
                    if add_group not in list_group:
                        list_group.append(add_group)
                        self.df_project.loc[i, 'groups'] = ",".join(map(str, sorted(list_group)))
                    else:
                        print(f"{self.df_project.loc[i, 'recording_name']} is already in {add_group}")
                self.save_df_project()
                self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
            self.purgeGroupCache(add_group)
            df_selection = self.df_project.loc[selected_rows]
            self.setGraph(df = df_selection)
        else:
            print("No files selected.")

    def purgeGroupCache(self, *groups): # clear cache so that a new group mean is calculated
        if verbose:
            print(f"purgeGroupCache: {groups}, len(group): {len(groups)}")
        for group in groups:
            if group in self.dict_group_means:
                del self.dict_group_means[group]
            path_group_cache = Path(f'{self.dict_folders["cache"]}/{group}.csv')
            if path_group_cache.exists: # TODO: Upon adding a group, both of these conditions trigger. How?
                print(f"{path_group_cache} found when checking for existence...")
                try:
                    path_group_cache.unlink()
                    print("...and was successfully unlinked.")
                except FileNotFoundError:
                    print("...but NOT when attempting to unlink.")

    def clearGroupsByRow(self, rows):
        list_affected_groups = ' '.join(self.df_project.iloc[rows]['groups'])
        affected_groups = set(re.findall(r'\b\w+\b', list_affected_groups))
        for i in rows:
            self.df_project.loc[i, "groups"] = " "
        for group in affected_groups:
            self.purgeGroupCache(group)
        self.save_df_project()
        self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
        self.setGraph()


# writer functions
    
    def write_cfg(self):  # config file for program, global settings
        cfg = {"user_documents": str(self.user_documents), "projects_folder": str(self.projects_folder), "projectname": self.projectname}
        with self.cfg_yaml.open("w+") as file:
            yaml.safe_dump(cfg, file)

    def write_project_cfg(self):  # config file for project, local settings
        project_cfg = self.dict_cfg
        print("Writing project_cfg:", self.project_cfg_yaml)
        new_projectfolder = self.projects_folder / self.projectname
        new_projectfolder.mkdir(exist_ok=True)
        with self.project_cfg_yaml.open("w+") as file:
            yaml.safe_dump(project_cfg, file)


# Project functions

    def newProject(self, new_project_name):
        new_projectfolder = self.projects_folder / new_project_name
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if verbose:
                print("The target project name already exists")
        else:
            new_projectfolder.mkdir()
            self.dict_folders['project'] = new_projectfolder
            self.projectname = new_project_name
            self.dict_folders = self.build_dict_folders()
            self.resetCacheDicts()
            self.killGroupButtons()
            self.inputProjectName.setText(self.projectname)
            self.df_project = df_projectTemplate()
            self.setTableDf(self.df_project)
            self.save_df_project()
            self.write_cfg()
            self.setGraph()

    def renameProject(self): # changes name of project folder and updates .cfg
        if verbose:
            print("renameProject")
        self.dict_folders['project'].mkdir(exist_ok=True)
        new_project_name = self.inputProjectName.text()
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if verbose:
                print(f"Project name {new_project_name} already exists")
            self.inputProjectName.setText(self.projectname)
        elif re.match(r'^[a-zA-Z0-9_ -]+$', str(new_project_name)) is not None: # check if valid filename
            self.dict_folders['project'] = self.dict_folders['project'].rename(self.projects_folder / new_project_name)
            self.dict_folders['data'] = self.projects_folder / new_project_name / 'data'
            self.dict_folders['cache'] = self.dict_folders['cache'].rename(self.projects_folder / 'cache' / new_project_name)
            self.projectname = new_project_name
            self.inputProjectName.setText(self.projectname)
            self.inputProjectName.setReadOnly(True)
            self.write_cfg()
            print(f"Project renamed to {new_project_name}.")
        else:
            print(f"Project name {new_project_name} is not a valid path.")

    def setProjectname(self):
        # get_signals(self.children()[1].children()[1].model)
        self.projectname = self.inputProjectName.text()
        self.dict_folders['project'] = self.projects_folder / self.projectname
        if self.dict_folders['project'].exists():
            # look for project.brainwash and load it
            if (self.dict_folders['project'] / "project.brainwash").exists():
                self.load_df_project()
        else:
            self.dict_folders['project'].mkdir()
        if verbose:
            print(f"setProjectname, folder: {self.dict_folders['project']} exists: {self.dict_folders['project'].exists()}")


# Project dataframe handling

    def get_df_project(self): # returns a copy of the persistent df_project TODO: make these functions the only way to get to it.
        return self.df_project

    def load_df_project(self): # reads fileversion of df_project to persisted self.df_project, clears graphs and saves cfg
        self.df_project = pd.read_csv(str(self.dict_folders['project'] / "project.brainwash"))
        self.setTableDf(self.df_project)  # display self.df_project to table
        self.projectname = self.dict_folders['project'].stem
        self.inputProjectName.setText(self.projectname)  # set folder name to proj name
        if verbose:
            print(f"loaded project df: {self.df_project}")
        self.clearGraph()
        self.write_cfg()

    def save_df_project(self): # writes df_project to .csv
        self.df_project.to_csv(str(self.dict_folders['project'] / "project.brainwash"), index=False)

    def set_df_project(self, df): # persists df and saves it to .csv
        self.df_project = df
        self.save_df_project()


# Table handling
    def listSelectedRows(self):
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        return [row.row() for row in selected_indexes]

    def setTableDf(self, data):
        if verbose:
            print("setTableDf")
        self.tablemodel.setData(data)
        self.formatTableProj() # hide/resize columns
        self.tableProj.update()

    def formatTableProj(self): # hide/resize columns
        if verbose:
            print("formatTableProj")
        header = self.tableProj.horizontalHeader()
        df_p = self.df_project
        # hide all columns except these:
        list_show = [df_p.columns.get_loc("recording_name"),
                     df_p.columns.get_loc("groups"),
                     df_p.columns.get_loc("sweeps")]
        num_columns = df_p.shape[1]
        for col in range(num_columns):
            if col in list_show:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
            else:
                self.tableProj.setColumnHidden(col, True)

# internal dataframe handling
    def get_dfmean(self, row):
        # returns an internal df mean for the selected file. If it does not exist, read it from file first.
        recording_name = row['recording_name']
        if recording_name in self.dict_means: #1: Return cached
            return self.dict_means[recording_name]

        persist = False
        str_mean_path = f'{self.dict_folders["cache"]}/{recording_name}_mean.csv'
        if Path(str_mean_path).exists(): #2: Read from file
            dfmean = pd.read_csv(str_mean_path)
        else: #3: Create file
            dfmean = parse.build_dfmean(self.get_dfdata(row=row))
            persist = True

        #if the filter is not a column in self.dfmean, create it
        if row['filter'] == 'savgol':
            # TODO: extract parameters from df_p, use default for now
            if 'savgol' not in dfmean.columns:
                # print number of rows in dfmean
                dfmean['savgol'] = analysis.addFilterSavgol(df = dfmean)
                persist = True

        if persist:
            self.df2csv(df=dfmean, rec=recording_name, key="mean")
        self.dict_means[recording_name] = dfmean
        return self.dict_means[recording_name]

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
            dfoutput.reset_index(inplace=True)
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
                dffilter['savgol'] = analysis.addFilterSavgol(df = dffilter)
        # Cache and return
        self.dict_filters[recording_name] = dffilter
        return self.dict_filters[recording_name]
        
        
    def get_dfgroupmean(self, key_group):
        # returns an internal df output average of <group>. If it does not exist, create it
        if key_group in self.dict_group_means: # 1: Return cached
            return self.dict_group_means[key_group]
        group_path = Path(f'{self.dict_folders["cache"]}/{key_group}.csv')
        if group_path.exists(): #2: Read from file
            if verbose:
                print("Loading stored", str(group_path))
            group_mean = pd.read_csv(str(group_path))
        else: #3: Create file
            if verbose:
                print("Building new", str(group_path))
            df_p = self.df_project
            dfgroup = df_p[df_p['groups'].str.split(',').apply(lambda x: key_group in x)]
            dfs = []
            for i, row in dfgroup.iterrows():
                df = self.get_dfoutput(row=row)
                dfs.append(df)
            dfs = pd.concat(dfs)
            group_mean = dfs.groupby('sweep').agg({'EPSP_amp': ['mean', 'sem'], 'EPSP_slope': ['mean', 'sem']}).reset_index()
            group_mean.columns = ['sweep', 'EPSP_amp_mean', 'EPSP_amp_SEM', 'EPSP_slope_mean', 'EPSP_slope_SEM']
            self.df2csv(df=group_mean, rec=key_group, key="mean")
        self.dict_group_means[key_group] = group_mean
        return self.dict_group_means[key_group]


    def df2csv(self, df, rec, key=None): # writes dict[rec] to rec_{dict}.csv
        self.dict_folders['cache'].mkdir(exist_ok=True)
        if key is None:
            filepath = f'{self.dict_folders["cache"]}/{rec}.csv'
        else:
            filepath = f'{self.dict_folders["cache"]}/{rec}_{key}.csv'
        print(f"saved cache filepath: {filepath}")
        df.to_csv(filepath, index=False)


# Default_output
    def defaultOutput(self, row):
        '''
        Generates default results for row (in self.df_project)
        Stores timepoints, methods and params in their designated columns in self.df_project
        Returns a df of the results: amplitudes and slopes
        '''
        dffilter = self.get_dffilter(row=row)
        dfmean = self.get_dfmean(row=row)
        df_p = self.get_df_project()
        dict_t = analysis.find_all_t(dfmean=dfmean, verbose=False)
        for aspect, value in dict_t.items():
            old_aspect_value = df_p.loc[row.name, aspect]
            if pd.notna(old_aspect_value):
                 # if old_aspect IS a valid float, use it: replace in dict_t
                dict_t[aspect] = old_aspect_value
                print(f"{aspect} was {old_aspect_value} in df_p, a valid float. Updated dict_t to {value}")
            else: # if old_aspect is NOT a valid float, replace df_p with dict_t
                df_p.loc[row.name, aspect] = value
                print(f"{aspect} was {old_aspect_value} in df_p, NOT a valid float. Updated df_p.")               
                self.set_df_project(df=df_p)
        df_output = analysis.build_dfoutput(df=dffilter, t_EPSP_amp=dict_t['t_EPSP_amp'], t_EPSP_slope=dict_t['t_EPSP_slope'])
        return df_output


# Graph handling

    def clearGraph(self): # removes all data from canvas_seaborn_mean - TODO: deprecated?
        if hasattr(self, "canvas_seaborn_mean"):
            self.canvas_seaborn_mean.axes.cla()
            self.canvas_seaborn_mean.draw()
        if hasattr(self, "canvas_seaborn_output"):
            self.canvas_seaborn_output.axes.cla()
            self.canvas_seaborn_output.draw()

    def setGraph(self, df=None): # plot selected row(s), or clear graph if empty
        amp = bool(self.dict_cfg['aspect_EPSP_amp'])
        slope = bool(self.dict_cfg['aspect_EPSP_slope'])
        self.clearGraph()
        ax1 = self.canvas_seaborn_output.axes
        if hasattr(self, "ax2"): # remove ax2 if it exists
            self.ax2.remove()
        ax2 = ax1.twinx()
        self.ax2 = ax2  # Store the ax2 instance
        self.ax1 = ax1
        # Plot group means
        if self.dict_cfg['list_groups']:
            self.setGraphGroups(ax1, ax2, self.dict_cfg['list_group_colors'])
        if df is not None: # plot selected rows
            self.setGraphSelected(df=df, ax1=ax1, ax2=ax2, amp=amp, slope=slope)
        
        # add appropriate ticks and axis labels
        self.canvas_seaborn_mean.axes.set_xlabel("Time (s)")
        self.canvas_seaborn_mean.axes.set_ylabel("Voltage (V)")
        self.ax1.set_ylabel("Amplitude (mV)")
        self.ax2.set_ylabel("Slope (mV/ms)")
        oneAxisLeft(self.ax1, self.ax2, amp, slope)
        # x and y limits
        self.canvas_seaborn_mean.axes.set_xlim(self.dict_cfg['mean_xlim'])
        self.canvas_seaborn_mean.axes.set_ylim(self.dict_cfg['mean_ylim'])
        ax1.set_ylim(self.dict_cfg['output_ax1_ylim'])
        self.canvas_seaborn_mean.draw()
        self.canvas_seaborn_output.draw()

    def setGraphSelected(self, df, ax1, ax2, amp, slope):
        df_analyzed = df[df["sweeps"] != "..."]
        if df_analyzed.empty:
            print("Nothing analyzed selected.")
        else:
            for i, row in df_analyzed.iterrows(): # TODO: i to be used later for cycling colours?
                dfmean = self.get_dfmean(row=row)
                dfoutput = self.get_dfoutput(row=row)
                # plot relevant filter of dfmean on canvas_seaborn_mean
                label = f"{row['recording_name']}"
                rec_filter = row['filter'] # the filter currently used for this recording
                _ = sns.lineplot(ax=self.canvas_seaborn_mean.axes, label=label, data=dfmean, y=rec_filter, x="time", color="black")

                # plot dfoutput on canvas_seaborn_output
                if amp & (not np.isnan(row["t_EPSP_amp"])):
                    _ = sns.lineplot(ax=ax1, label=f"{label}_EPSP_amp", data=dfoutput, y="EPSP_amp", x="sweep", color="black", linestyle='--')
                    # mean, amp indicator
                    y_position = dfmean[dfmean.time == row["t_EPSP_amp"]].voltage
                    self.canvas_seaborn_mean.axes.plot(row["t_EPSP_amp"], y_position, marker='v', markerfacecolor='blue', markeredgecolor='blue', markersize=10, alpha = 0.3)
                if slope & (not np.isnan(row["t_EPSP_slope"])):
                    _ = sns.lineplot(ax=ax2, label=f"{label}_EPSP_slope", data=dfoutput, y="EPSP_slope", x="sweep", color="black", alpha = 0.3)
                    # mean, slope indicator        
                    x_start = row["t_EPSP_slope"] - 0.0004
                    x_end = row["t_EPSP_slope"] + 0.0004
                    y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
                    y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
                    self.canvas_seaborn_mean.axes.plot([x_start, x_end], [y_start, y_end], color='blue', linewidth=10, alpha=0.3)

    def setGraphGroups(self, ax1, ax2, list_color):
        print(f"setGraphGroups: {self.dict_cfg['list_groups']}")
        df_p = self.get_df_project()
        for i_color, group in enumerate(self.dict_cfg['list_groups']):
            dfgroup = df_p[df_p['groups'].str.split(',').apply(lambda x: group in x)]
            if self.dict_cfg['dict_group_show'][group] == False:
                if verbose:
                    print(f"Checkbox for group {group} is not checked")
                continue
            if dfgroup.empty:
                if verbose:
                    print(f"No data in group {group}")
                continue

            # abort if any recording in group is an str
            if dfgroup['sweeps'].apply(lambda x: isinstance(x, str)).any():
                if verbose:
                    print(f"Analyse all recordings in {group} to show group output.")
                continue
            dfgroup_mean = self.get_dfgroupmean(key_group=group)
            # Errorbars, EPSP_amp_SEM and EPSP_slope_SEM are already a column in df
            # print(f'dfgroup_mean.columns: {dfgroup_mean.columns}')
            if dfgroup_mean['EPSP_amp_mean'].notna().any():
                _ = sns.lineplot(data=dfgroup_mean, y="EPSP_amp_mean", x="sweep", ax=ax1, color=list_color[i_color], linestyle='--')
                ax1.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_amp_mean + dfgroup_mean.EPSP_amp_SEM, dfgroup_mean.EPSP_amp_mean - dfgroup_mean.EPSP_amp_SEM, alpha=0.3, color=list_color[i_color])               
                ax1.axhline(y=0, linestyle='--', color='gray', alpha = 0.2)
            if dfgroup_mean['EPSP_slope_mean'].notna().any():
                _ = sns.scatterplot(data=dfgroup_mean, y="EPSP_slope_mean", x="sweep", ax=ax2, color=list_color[i_color], s=5)
                ax2.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_slope_mean + dfgroup_mean.EPSP_slope_SEM, dfgroup_mean.EPSP_slope_mean - dfgroup_mean.EPSP_slope_SEM, alpha=0.3, color=list_color[i_color])
                ax2.axhline(y=0, linestyle=':', color='gray', alpha = 0.2)

    def meanClicked(self, event): # maingraph click event
        if event.inaxes is not None:
            if event.button == 2:
                zoomReset(canvas=self.canvas_seaborn_mean, ui=self)

    def viewSettingsChanged(self, state, str_view_key):
        # checkboxes for views have changed; save settings and update
        self.dict_cfg[str_view_key] = (state == 2)
        self.write_project_cfg()
        self.tableProjSelectionChanged()


# MeasureWindow

    def launchMeasureWindow(self):  # , single_index_range):
        # Launches a new subwindow for the double-clicked row (if it's already open, focus on it)
        #   How to check for existing windows?
        #   How to shift focus?
        # Display the appropriate recording on the new window's graphs: mean and output
        #   Construct a sensible interface: drag-drop on measurement middle, start and finish points
        #   UI for toggling displayed measurement methods. Drag-drop forces Manual.

        # table_row should already have t_ values; otherwise do not attempt to draw them

        qt_index = self.tableProj.selectionModel().selectedIndexes()[0]
        ser_table_row = self.tablemodel.dataRow(qt_index)
        sweeps = ser_table_row["sweeps"]
        if sweeps == "...":
            # TODO: Make it import the missing file
            print("Unknown number of sweeps - not imported?")
            return
        # Close last window, for now. TODO: handle multiple windows (ew)
        if hasattr(self, "measure_frame"):
            print(f"Closing last window: {getattr(self, 'measure_frame')}")
            self.measure_frame.close()
        # Open window
        self.measure_frame = QDialog_sub()
        self.measure_window_sub = Measure_window_sub(self.measure_frame, row=ser_table_row, parent=self)
        self.measure_frame.setWindowTitle(ser_table_row['recording_name'])
        # move measurewindow to default position (TODO: later to be stored in cfg)
        self.measure_frame.setGeometry(1400, 0, 800, 1200)
        self.measure_frame.show()
        # Set graphs
        self.measure_window_sub.updatePlots()

            
    @QtCore.pyqtSlot(list)
    def slotPrintPaths(self, mypaths):
        if verbose:
            print(f"mystr: {mypaths}")
        strmystr = "\n".join(sorted(["/".join(i.split("/")[-2:]) for i in mypaths]))
        self.textBrowser.setText(strmystr)
        list_display_names = ["/".join(i.split("/")[-2:]) for i in mypaths]
        dftable = pd.DataFrame({"path_source": mypaths, "recording_name": list_display_names})
        self.setTableDf(dftable)

    @QtCore.pyqtSlot()
    def slotAddDfData(self, df):
        self.addData(df)

#####################################


class InputDialogPopup(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

    def showInputDialog(self, title, query):
        text, ok = QtWidgets.QInputDialog.getText(self, title, query)
        if ok:
            print(f"You entered: {text}")
            self.accept()  # Close the dialog when Enter is pressed
            return text


class TableProjSub(QtWidgets.QTableView):
    # TODO: This class does the weirdest things to events; shifting event numbers around in non-standard ways. Why?
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
            dfAdd['path'] = file_urls
            dfAdd['host'] = "Computer 1"
            dfAdd['checksum'] = "big number"
            dfAdd['filter'] = "voltage"
            # NTH: more intelligent default naming; lowest level unique name?
            # For now, use name + lowest level folder
            names = []
            for i in file_urls:
                names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
            dfAdd["recording_name"] = names
            self.parent.addData(dfAdd)
            event.acceptProposedAction()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_F2:
            ui.renameRecording()
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class Filetreesub(Ui_Dialog):
    def __init__(self, dialog, parent=None, folder="."):
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)
        self.parent = parent
        if verbose:
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
        # TODO: Extract host, checksum, group
        if verbose:
            print("pathsSelectedUpdateTable")
        dfAdd = df_projectTemplate()
        dfAdd["path"] = paths
        dfAdd["host"] = "Computer 1"
        dfAdd["checksum"] = "big number"
        dfAdd["filter"] = "voltage"
        # dfAdd['recording_name']=paths
        # dfAdd['groups']=' '
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(os.path.basename(os.path.dirname(i)) + "_" + os.path.basename(i))
        dfAdd["recording_name"] = names
        self.dfAdd = dfAdd
        # TODO: Add a loop that prevents duplicate names by adding a number until it becomes unique
        # TODO: names that have been set manually are stored a dict that persists while the addData window is open: this PATH should be replaced with this NAME (applied after default-naming, above)
        # format tableView
        header = self.tableView.horizontalHeader()
        self.tableView.setColumnHidden(0, True)  # host
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # path
        self.tableView.setColumnHidden(2, True)  # checksum
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # name
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # group
        self.tableView.update()


class Measure_window_sub(Ui_measure_window):
    def __init__(self, measure_frame, parent=None, row=None):
        super(Measure_window_sub, self).__init__()
        self.setupUi(measure_frame)
        self.parent = parent
        self.measure_frame = measure_frame
        self.row = row.copy() # creates a copy to be modified, then accepted to df_project, or rejected
        # create local copies of dfmean, dffilter and dfoutput
        # do NOT copy these dfs; add filter columns directly
        self.dfmean = self.parent.get_dfmean(row=self.row)
        self.dffilter = self.parent.get_dffilter(row=self.row)
        # copy this df; only replace if params change
        t0 = time.time()
        self.new_dfoutput = self.parent.get_dfoutput(row=self.row).copy()
        t1 = time.time()
        print(f"Measure_window_sub: {t1-t0} seconds to copy self.new_dfoutput")

        self.measure_graph_mean.setLayout(QtWidgets.QVBoxLayout())
        self.canvas_mean = MplCanvas(parent=self.measure_graph_mean)
        self.measure_graph_mean.layout().addWidget(self.canvas_mean)
        self.canvas_mean.show()
        self.canvas_mean.mpl_connect('button_press_event', self.meanClicked)
        self.canvas_mean.mpl_connect('scroll_event', lambda event: zoomOnScroll(event=event, canvas=self.canvas_mean))

        self.measure_graph_output.setLayout(QtWidgets.QVBoxLayout())
        self.canvas_output = MplCanvas(parent=self.measure_graph_output)  # instantiate canvas for Mean
        self.measure_graph_output.layout().addWidget(self.canvas_output)
        self.canvas_output.show()
        self.canvas_output.mpl_connect('button_press_event', self.outputClicked)
        self.canvas_output.mpl_connect('motion_notify_event', self.outputDragged)
        self.canvas_output.mpl_connect('button_release_event', self.outputReleased)

        # split axes
        self.ax1 = self.canvas_output.axes
        self.ax2 = self.ax1.twinx()

        # add appropriate ticks and axis labels
        self.canvas_mean.axes.set_xlabel("Time (s)")
        self.canvas_mean.axes.set_ylabel("Voltage (V)")
        self.ax1.set_ylabel("Amplitude (mV)")
        self.ax2.set_ylabel("Slope (mV/ms)")

        # Populate canvases - TODO: refactor such that components can be called individually when added later
        _ = sns.lineplot(ax=self.canvas_mean.axes, label='voltage', data=self.dfmean, y='voltage', x='time', color='black')
        if 'EPSP_amp' in self.new_dfoutput.columns and self.new_dfoutput['EPSP_amp'].notna().any():
            t_EPSP_amp = self.row['t_EPSP_amp']
            self.v_t_EPSP_amp =    sns.lineplot(ax=self.canvas_mean.axes).axvline(t_EPSP_amp, color="black", linestyle="--")
            _ = sns.lineplot(ax=self.ax1, label="old EPSP amp", data=self.new_dfoutput, y="EPSP_amp", x="sweep", color="gray")
        if 'EPSP_slope' in self.new_dfoutput.columns and self.new_dfoutput['EPSP_slope'].notna().any():
            t_EPSP_slope = self.row['t_EPSP_slope']
            x_start = t_EPSP_slope - 0.0004 # TODO: make this a variable
            x_end = t_EPSP_slope + 0.0004 # TODO: make this the same variable
            self.v_t_EPSP_slope =       sns.lineplot(ax=self.canvas_mean.axes).axvline(t_EPSP_slope, color="green", linestyle="--")
            self.v_t_EPSP_slope_start = sns.lineplot(ax=self.canvas_mean.axes).axvline(x_start, color="green", linestyle=":")
            self.v_t_EPSP_slope_end =   sns.lineplot(ax=self.canvas_mean.axes).axvline(x_end, color="green", linestyle=":")
            _ = sns.lineplot(ax=self.ax2, label="old EPSP slope", data=self.new_dfoutput, y="EPSP_slope", x="sweep", color="gray")

        self.canvas_mean.axes.set_xlim(parent.dict_cfg['mean_xlim'])
        self.canvas_mean.axes.set_ylim(parent.dict_cfg['mean_ylim'])
        self.ax1.set_ylim(parent.dict_cfg['output_ax1_ylim'])
        self.ax2.set_ylim(parent.dict_cfg['output_ax2_ylim'])

        # lines and drag state
        self.si_v = None # vertical line in canvas_output, indicating selected sweep
        self.si_sweep, = self.canvas_mean.axes.plot([], [], color="blue") # lineplot of the selected sweep on canvas_mean
        self.si_v_drag_from = None # vertical line in canvas_output, indicating start of drag
        self.si_v_drag_to = None # vertical line in canvas_output, indicating end of drag
        self.dragplot = None
        self.dragging = False
        self.last_x = None # remember last x position of mouse; None if no samples are selected

        # set button colors
        self.default_color = "background-color: rgb(239, 239, 239);"
        self.selected_color = "background-color: rgb(100, 100, 255);"

        # set default aspect
        self.toggle(self.pushButton_EPSP_slope, "EPSP_slope") # default for now TODO: Load/Save preference in local .cfg
        # Iterate through supported_aspects, connecting buttons and lineEdits
        def loopConnectAspects(aspect):
            aspect_button = getattr(self, f"pushButton_{aspect}")
            aspect_edit = getattr(self, f"lineEdit_{aspect}")
            aspect_button.setCheckable(True)
            aspect_button.pressed.connect(lambda: self.toggle(aspect_button, aspect))
            aspect_edit.setText(self.m(self.row[f"t_{aspect}"]))
            aspect_edit.editingFinished.connect(lambda: self.updateOnEdit(aspect_edit, aspect))
        for aspect in supported_aspects:
            loopConnectAspects(aspect=aspect)
        # connect checkboxes from mainwindow to updatePlots TODO: refactorize to merge with similar code in __init__(self, mainwindow)
        def loopConnectViews(view, key):
            str_view_key = f"{view}_{key}"
            key_checkBox = getattr(parent, f"checkBox_{str_view_key}")
            key_checkBox.setChecked(parent.dict_cfg[str_view_key])
            key_checkBox.stateChanged.connect(self.updatePlots)
            self.measure_frame.list_connections.append((key_checkBox.stateChanged, self.updatePlots))
        for key in supported_aspects:
            loopConnectViews(view="aspect", key=key)
        self.pushButton_auto.clicked.connect(self.autoCalculate)
        # check the radiobutton of the current filter, per row['filter']
        row_filter = self.row['filter']
        self.radioButton_filter_none.setChecked(row_filter=="voltage")
        self.radioButton_filter_none.clicked.connect(lambda: self.updateFilter("voltage"))
        self.radioButton_filter_savgol.setChecked(row_filter=="savgol")
        self.radioButton_filter_savgol.clicked.connect(lambda: self.updateFilter("savgol"))

        self.buttonBox.accepted.connect(self.accepted_handler)
        self.buttonBox.rejected.connect(self.measure_frame.close)
        self.updatePlots()


    def updateFilter(self, filter):
        self.row['filter'] = filter
        self.row['filter_params'] = "toyed with!"
        self.filter_params_changed = False
        if filter == "savgol":
            # TODO: create interface for filter params
            # make sure the updated filter exists
            if ('savgol' not in self.dfmean) | self.filter_params_changed:
                self.dfmean['savgol'] = analysis.addFilterSavgol(self.dfmean)
                parse.persistdf(file_base=self.row['recording_name'], dict_folders=self.parent.dict_folders, dfmean=self.dfmean)
            if ('savgol' not in self.dffilter) | self.filter_params_changed:
                self.dffilter['savgol'] = analysis.addFilterSavgol(self.dffilter)
                parse.persistdf(file_base=self.row['recording_name'], dict_folders=self.parent.dict_folders, dffilter=self.dffilter)

        # build new output
        self.new_dfoutput = analysis.build_dfoutput(df=self.dffilter,
                                    filter=filter,
                                    t_EPSP_amp=self.row["t_EPSP_amp"],
                                    t_EPSP_slope=self.row["t_EPSP_slope"])
        if self.last_x is not None:
            self.updateSample()
        self.updatePlots()


    def updatePlots(self):
        # Apply settings from self.parent.dict_cfg to canvas_mean and canvas_output
        amp = bool(self.parent.dict_cfg['aspect_EPSP_amp'])
        slope = bool(self.parent.dict_cfg['aspect_EPSP_slope'])
        rec_filter = self.row['filter'] # the filter currently used for this recording
        # Plot relevant filter of dfmean on canvas_mean, or show it if it's already plotted
        if label2idx(self.canvas_mean, rec_filter) is False:
            _ = sns.lineplot(ax=self.canvas_mean.axes, label=rec_filter, data=self.dfmean, y=rec_filter, x="time", color="black")
        
        self.canvas_mean.axes.lines[label2idx(self.canvas_mean, 'voltage')].set_visible(rec_filter=='voltage')
        if label2idx(self.canvas_mean, 'savgol') is not False:
            self.canvas_mean.axes.lines[label2idx(self.canvas_mean, 'savgol')].set_visible(rec_filter=='savgol')
        # hide mean legend
        if self.canvas_mean.axes.get_legend() is not None:
            self.canvas_mean.axes.get_legend().set_visible(False)

        # Plot dfoutput on canvas_output, or update and show if already plotted
        if label2idx(self.ax1, "EPSP_amp") is False:
            _ = sns.lineplot(ax=self.ax1, label='EPSP_amp', data=self.new_dfoutput, y='EPSP_amp', x='sweep', color="black", linestyle='--')
        else:
            self.ax1.lines[label2idx(self.ax1, "EPSP_amp")].set_data(self.new_dfoutput['sweep'], self.new_dfoutput['EPSP_amp'])
            self.ax1.lines[label2idx(self.ax1, "EPSP_amp")].set_visible(amp)

        if label2idx(self.ax2, "EPSP_slope") is False:
            _ = sns.lineplot(ax=self.ax2, label="EPSP_slope", data=self.new_dfoutput, y="EPSP_slope", x="sweep", color="black", alpha = 1)
        else:
            self.ax2.lines[label2idx(self.ax2, "EPSP_slope")].set_data(self.new_dfoutput['sweep'], self.new_dfoutput['EPSP_slope'])
            self.ax2.lines[label2idx(self.ax2, "EPSP_slope")].set_visible(slope)

        self.ax1.lines[label2idx(self.ax1, "old EPSP amp")].set_visible(amp)
        self.ax2.lines[label2idx(self.ax2, "old EPSP slope")].set_visible(slope)
            
            # Display aspect indicators:
        if 'EPSP_amp' in self.new_dfoutput.columns and self.new_dfoutput['EPSP_amp'].notna().any():
            self.v_t_EPSP_amp.set_visible(amp)
        if 'EPSP_slope' in self.new_dfoutput.columns and self.new_dfoutput['EPSP_slope'].notna().any():
            self.v_t_EPSP_slope.set_visible(slope)
            self.v_t_EPSP_slope_start.set_visible(slope)
            self.v_t_EPSP_slope_end.set_visible(slope)

        # TODO: Update y limits

        # Update axes visibility and position
        oneAxisLeft(self.ax1, self.ax2, amp, slope)

        self.canvas_mean.draw()
        self.canvas_output.draw()


    def accepted_handler(self):
        # Get the project dataframe
        df_p = self.parent.get_df_project()
        # Find the index of the row with the matching recording_name
        idx = df_p.index[df_p['recording_name'] == self.row['recording_name']]
        list_keep = ['recording_name', 'groups'] # Columns to keep
        # If there's exactly one matching row
        if len(idx) == 1:
            # Update the row in df_project
            for column, value in self.row.items():
                if column not in list_keep:
                    df_p.loc[idx, column] = value
            # Save the updated df_project
            self.parent.set_df_project(df_p)

            # Update dfs; dicts and files
            recording_name = self.parent.df_project.loc[int(idx.values[0]), 'recording_name']
            self.parent.dict_outputs[recording_name] = self.new_dfoutput
            self.parent.df2csv(df=self.new_dfoutput, rec=recording_name, key="output")

            # Delete affected group output; dicts and files
            str_groups = df_p.loc[int(idx.values[0]), 'groups']
            list_groups = list(str_groups.split(","))
            if (str_groups == " ") or (len(list_groups) == 0): # If the row is not in any group
                pass
            else: # Remove each group from internal dict and purge cache
                for group in list_groups:
                    if group in self.parent.dict_group_means.keys():
                        del self.parent.dict_group_means[group]
                        self.parent.purgeGroupCache(group)
                        # Delete the group file if it exists
                        group_path = Path(f'{self.parent.dict_folders["cache"]}/{group}.csv')
                        if group_path.exists():
                            group_path.unlink()
            self.parent.setGraph(df_p.iloc[idx]) # draw the updated row

        # Error handling        
        elif len(idx) < 1: # If no matching row is found
            raise ValueError(f"ERROR (accepted_handler): {self.row['recording_name']} not found in df_project.")
        else: # If multiple matching rows are found
            raise ValueError(f"ERROR (accepted_handler): multiple instances of {self.row['recording_name']} in project_df.")
        self.measure_frame.close()


    def autoCalculate(self):
        dffilter = self.parent.get_dffilter(row=self.row)
        dict_t = analysis.find_all_t(dfmean=self.dfmean, verbose=False)
        self.new_dfoutput = analysis.build_dfoutput(df=dffilter,
                                       t_EPSP_amp=dict_t["t_EPSP_amp"],
                                       t_EPSP_slope=dict_t["t_EPSP_slope"])
        self.new_dfoutput.reset_index(inplace=True)
        for aspect in supported_aspects:
            time = dict_t[f"t_{aspect}"]
            if isinstance(time, float) and not np.isnan(time) and time is not None:
                self.updateAspect(aspect=aspect, time=time, method="Auto")
        

    def m(self, SI): # convert seconds to milliseconds, or V to mV, returning a str for display purposes ONLY
        return str(round(SI * 1000, 1)) # TODO: single decimal assumes 10KHz sampling rate; make this more flexible


    def toggle(self, button, aspect): # updates aspect, sets "button" to active state, and all other buttons to inactive
        self.aspect = aspect
        for i_aspect in supported_aspects:
            un_button = getattr(self, f"pushButton_{i_aspect}")
            un_button.setStyleSheet(self.default_color)
        button.setStyleSheet(self.selected_color)


    def dfmeanDerivates(self, df): # plots prim and bis of df on canvas_mean
        # Prim and Bis: filter to display only the relevant part of the trace, and rescale to match voltage
        filtered_df = df.copy()
        min_V = filtered_df['voltage'].min()
        min_prim = filtered_df['prim'].min()
        min_bis = filtered_df['bis'].min()
        filtered_df['prim'] = filtered_df['prim'] * (min_V/min_prim)
        filtered_df['bis'] = filtered_df['bis'] * (min_V/min_bis)
        self.mean_prim = sns.lineplot(data=filtered_df, y="prim", x="time", ax=self.canvas_mean.axes, color="red", alpha=0.3)
        self.mean_bis = sns.lineplot(data=filtered_df, y="bis", x="time", ax=self.canvas_mean.axes, color="green", alpha=0.3)


    def meanClicked(self, event): # measure window click event
        if event.inaxes is not None:
            if event.button == 1:# Left mouse button clicked
                if self.aspect not in supported_aspects:
                    print(f"meanClicked: {self.aspect} not supported.")
                    return
                x = event.xdata
                # find time in self.dfmean closest to x
                time = self.dfmean.iloc[(self.dfmean['time'] - x).abs().argsort()[:1]]['time'].values[0]
                self.updateOnClick(time=time, aspect=self.aspect)
            elif event.button == 2:
                zoomReset(canvas=self.canvas_mean, ui=self.parent)


    def outputClicked(self, event): # measurewindow output click event
        x = event.xdata
        if event.button == 1 and x is not None: # Left mouse button clicked within xdata
            if event.button == 1: 
                self.drag_start = x
                self.dragging = True
                unPlot(self.canvas_output, self.si_v_drag_from)
                self.si_v_drag_from = sns.lineplot(ax=self.canvas_output.axes).axvline(x, color="blue")
                self.canvas_output.draw()
    

    def outputDragged(self, event): # measurewindow output drag event
        x = event.xdata
        if self.dragging:
            unPlot(self.canvas_output, self.si_v_drag_to, self.dragplot)
            if x is not None:
                self.si_v_drag_to = sns.lineplot(ax=self.canvas_output.axes).axvline(x, color="blue")
                self.dragplot = sns.lineplot(ax=self.canvas_output.axes).axvspan(self.drag_start, x, color='lightblue', alpha=0.3)
            self.canvas_output.draw()
    

    def outputReleased(self, event): # measurewindow output release event
        self.last_x = event.xdata
        if (self.dragging) and (event.button == 1) and (self.last_x is not None):
            self.dragging = False
            self.updateSample(event)
            self.canvas_mean.draw()
            self.canvas_output.draw()


    def updateSample(self, event=None):
        if event is not None:
            x = event.xdata
        else:
            x = self.last_x
        same = bool(int(self.drag_start) == int(x))
        print(f"meanDragged from: {self.drag_start} to {x}: {same}")
        df = self.dffilter
        rec_filter = self.row['filter'] # the filter currently used for this recording
        print(f"updateSample: event={event}, rec_filter={rec_filter}")
        if same: # click and release on same: get that specific sweep and superimpose it on canvas_mean
            unPlot(self.canvas_output, self.si_v_drag_to, self.dragplot)
            df = df[df['sweep'] == int(self.drag_start)]
            self.si_sweep.set_data(df["time"], df[rec_filter])
        else: # get all sweeps between drag_start and x (event.xdata) and superimpose the mean of them on canvas_mean
            if int(self.drag_start) > int(x):
                df = df[(df['sweep'] >= int(x)) & (df['sweep'] <= int(self.drag_start))]
            else:
                df = df[(df['sweep'] >= int(self.drag_start)) & (df['sweep'] <= int(x))]
            df = df.groupby('time').agg({rec_filter: ['mean']}).reset_index()
            df.columns = ['time', rec_filter]
            self.si_sweep.set_data(df["time"], df[rec_filter])

    
    def updateOnClick(self, time, aspect):
        if verbose:
            print(f"updateOnClick: time={time}, aspect={aspect}")
        self.updateAspect(time=time, aspect=aspect, method="Manual")


    def updateOnEdit(self, lineEdit, aspect):
        print(f"updateOnEdit: lineEdit={lineEdit}, aspect={aspect}")
        input_sanitized = lineEdit.text().replace(",", ".")
        try:
            time = float(input_sanitized)/1000 # convert to SI
        except:
            print("Invalid input: must be a number.")
            lineEdit.setText("")
            return
        # check if value is within dfmean time range
        if  time < self.dfmean['time'].min() or time > self.dfmean['time'].max():
            print(f"Time {time}s out of range")
            lineEdit.setText("")
            return
        self.updateAspect(time=time, aspect=aspect, method="Manual")
    

    def updateAspect(self, time, aspect, method):
        # changes the measuring points of an aspect and propagates the change to the appropriate columns in df_project
        t_aspect  = ("t_" + aspect)
        t_method = (t_aspect + "_method")
        t_params = (t_aspect + "_params")
        # update row
        self.row[t_aspect] = time
        self.row[t_method] = method
        self.row[t_params] = "-"
        if verbose:
            print(f" . self.parent.df_project.loc[self.row.name, t_aspect]: {self.parent.df_project.loc[self.row.name, t_aspect]}, row[{t_aspect}]: {self.row[t_aspect]}")
            print(f" . self.parent.df_project.loc[self.row.name, t_method: {self.parent.df_project.loc[self.row.name, t_method]}, row[{t_method}]: {self.row[t_method]}")
            print(f" . self.parent.df_project.loc[self.row.name, t_params]: {self.parent.df_project.loc[self.row.name, t_params]}, row[{t_params}]: {self.row[t_params]}")
        #recalculate aspect
        dffilter = self.parent.get_dffilter(row=self.row)
        if aspect == "EPSP_amp":
            axis = self.ax1
            df = analysis.build_dfoutput(df=dffilter, t_EPSP_amp=time)
            graph_color = "black"
            plot_on_mean = {'center': ("v_" + t_aspect)}
        else:# aspect == "EPSP_slope":
            axis = self.ax2
            df = analysis.build_dfoutput(df=dffilter, t_EPSP_slope=time)
            graph_color = "green"
            plot_on_mean = {'center': ("v_" + t_aspect),
                            'start':  ("v_" + t_aspect + "_start"),
                            'end':    ("v_" + t_aspect + "_end")}
        print(f"updateAspect, df: {df}")
        self.new_dfoutput[aspect] = df[aspect]
        #update appropriate lineEdit
        print(f"lineEdit_{aspect}: time{time} to ms: {self.m(time)}")
        line2update = getattr(self, "lineEdit_" + aspect)
        line2update.setText(self.m(time))

        #update mean graph
        for key, graph in plot_on_mean.items():
            getattr(self, graph).remove() # remove the one about to be replaced
            if key == "center":
                setattr(self, graph, sns.lineplot(ax=self.canvas_mean.axes).axvline(time, color=graph_color, linestyle="--"))
            elif key == "start":
                setattr(self, graph, sns.lineplot(ax=self.canvas_mean.axes).axvline(time - 0.0004, color=graph_color, linestyle=":"))
            elif key == "end":
                setattr(self, graph, sns.lineplot(ax=self.canvas_mean.axes).axvline(time + 0.0004, color=graph_color, linestyle=":"))
        self.canvas_mean.draw()
        #update output graph, voltage
        while label2idx(axis, aspect):
            axis.lines[label2idx(axis, aspect)].remove()
        if self.new_dfoutput[aspect].notna().any():
            _ = sns.lineplot(ax=axis, label=aspect, data=self.new_dfoutput, y=aspect, x='sweep', color='black')
        self.canvas_output.draw()


def get_signals(source):
    cls = source if isinstance(source, type) else type(source)
    signal = type(QtCore.pyqtSignal())
    print("get_signals:")
    for subcls in cls.mro():
        clsname = f"{subcls.__module__}.{subcls.__name__}"
        for key, aspect in sorted(vars(subcls).items()):
            if isinstance(aspect, signal):
                print(f"{key} [{clsname}]")


def zoomOnScroll(event, canvas):
    xdata, ydata = event.xdata, event.ydata
    scroll_factor = 0.9 # TODO: make this a setting
    def xzoom(xdata, factor):
        xlim = [xdata - (xdata - canvas.axes.get_xlim()[0]) * factor,
                xdata + (canvas.axes.get_xlim()[1] - xdata) * factor]
        return xlim
    def yzoom(ydata, factor):
        ylim = [ydata - (ydata - canvas.axes.get_ylim()[0]) * factor,
                ydata + (canvas.axes.get_ylim()[1] - ydata) * factor]
        return ylim
    if xdata is not None and ydata is not None:
        xlim = xzoom(xdata, scroll_factor if event.step > 0 else 1 / scroll_factor)
        ylim = yzoom(ydata, scroll_factor if event.step > 0 else 1 / scroll_factor)
        canvas.axes.set_xlim(xlim[0], xlim[1])
        canvas.axes.set_ylim(ylim[0], ylim[1])
        canvas.draw()


def zoomReset(canvas, ui):
    canvas.axes.set_xlim(ui.dict_cfg['mean_xlim'])
    canvas.axes.set_ylim(ui.dict_cfg['mean_ylim'])
    canvas.draw()


def oneAxisLeft(ax1, ax2, amp, slope):
    # sets ax1 and ax2 visibility and position
    ax1.set_visible(amp)
    ax2.set_visible(slope)
    if slope and not amp:
        ax2.yaxis.set_label_position("left")
        ax2.yaxis.set_ticks_position("left")
    else:
        ax2.yaxis.set_label_position("right")
        ax2.yaxis.set_ticks_position("right")


def unPlot(canvas, *artists): # remove line if it exists on canvas
    print(f"unPlot - canvas: {canvas}, artists: {artists}")
    for artist in artists:
        artists_on_canvas = canvas.axes.get_children()
        if artist in artists_on_canvas:
            print(f"unPlot - removed artist: {artist}")
            artist.remove()

def label2idx(canvas, aspect):
    dict_labels = {k.get_label(): v for (v, k) in enumerate(canvas.axes.lines)}
    return dict_labels.get(aspect, False)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    ui = UIsub(main_window)
    main_window.show()
    ui.setGraph()
    sys.exit(app.exec_())