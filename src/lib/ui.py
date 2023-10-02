import os  # TODO: replace use by pathlib?
import sys
from pathlib import Path
import yaml

import matplotlib

# import matplotlib.pyplot as plt # TODO: use instead of matplotlib for smaller import?
import seaborn as sns
import scipy.stats as stats

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

# from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets
from datetime import datetime
import re

import parse
import analysis

matplotlib.use("Qt5Agg")

verbose = True
track_widget_focus = False


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


class Ui_measure_window(QtCore.QObject):
    def setupUi(self, measure):
        measure.setObjectName("measure")
        measure.resize(502, 992)
        self.verticalLayout = QtWidgets.QVBoxLayout(measure)
        self.verticalLayout.setObjectName("verticalLayout")
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
        self.measure_info = QtWidgets.QTableView(measure)
        self.measure_info.setObjectName("measure_info")
        self.measure_verticalLayout.addWidget(self.measure_info)
        self.measure_graph_output = QtWidgets.QWidget(measure)
        self.measure_graph_output.setObjectName("measure_graph_output")
        self.measure_verticalLayout.addWidget(self.measure_graph_output)
        self.measure_verticalLayout.setStretch(0, 4)
        self.measure_verticalLayout.setStretch(1, 1)
        self.measure_verticalLayout.setStretch(2, 4)
        self.verticalLayout.addLayout(self.measure_verticalLayout)

        self.retranslateUi(measure)
        QtCore.QMetaObject.connectSlotsByName(measure)

    def retranslateUi(self, measure):
        _translate = QtCore.QCoreApplication.translate
        measure.setWindowTitle(_translate("measure", "Placeholder Window Title"))


################################################################
# section directly copied from output from pyuic, do not alter #
# trying to make all the rest work with it                     #
# WARNING: I was forced to change the parent class from        #
# 'object' to 'QtCore.QObject' for the pyqtSlot(list) to work  #
################################################################


class Ui_MainWindow(QtCore.QObject):
    def setupUi(self, mainWindow):
        mainWindow.setObjectName("mainWindow")
        mainWindow.resize(951, 816)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName("horizontalLayoutCentralwidget")
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
        self.tableProj.setAcceptDrops(True)
        self.tableProj.setObjectName("tableProj")
        self.verticalLayoutProj.addWidget(self.tableProj)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalLayoutProj)
        spacerItem = QtWidgets.QSpacerItem(10, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayoutCentralwidget.addItem(spacerItem)
        self.verticalLayoutGraph = QtWidgets.QVBoxLayout()
        self.verticalLayoutGraph.setObjectName("verticalLayoutGraph")
        self.labelMeanSweep = QtWidgets.QLabel(self.centralwidget)
        self.labelMeanSweep.setObjectName("labelMeanSweep")
        self.verticalLayoutGraph.addWidget(self.labelMeanSweep)
        self.graphMean = QtWidgets.QWidget(self.centralwidget)
        self.graphMean.setMinimumSize(QtCore.QSize(0, 100))
        self.graphMean.setObjectName("graphMean")
        self.verticalLayoutGraph.addWidget(self.graphMean)
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
        self.verticalLayoutGraph.setStretch(3, 5)
        self.verticalLayoutGraph.setStretch(5, 1)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalLayoutGraph)
        mainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(mainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 951, 22))
        self.menubar.setObjectName("menubar")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)

    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash 0.4"))
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
            "channel",
            "stim",
            "groups",
            "parsetimestamp",
            "sweeps",
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
        # load cfg if present
        paths = [Path.cwd()] + list(Path.cwd().parents)
        self.repo_root = [i for i in paths if (-1 < str(i).find("brainwash")) & (str(i).find("src") == -1)][0]  # path to brainwash directory
        self.cfg_yaml = self.repo_root / "cfg.yaml"
        self.projectname = None
        self.inputProjectName.setReadOnly(True)

        if self.cfg_yaml.exists():
            with self.cfg_yaml.open("r") as file:
                cfg = yaml.safe_load(file)
                self.user_documents = Path(cfg["user_documents"])  # Where to look for raw data
                self.projects_folder = Path(cfg["projects_folder"])  # Where to save and read parsed data
                self.projectname = cfg["projectname"]
        else:
            self.user_documents = Path.home() / "Documents"  # Where to look for raw data
            self.projects_folder = self.user_documents / "Brainwash Projects"  # Where to save and read parsed data
            self.projectname = "My Project"

        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)

        # replacing table proj with custom to allow changing of keypress event handling
        originalTableView = self.centralwidget.findChild(QtWidgets.QTableView, "tableProj")  # Find and replace the original QTableView in the layout
        tableProj = TableProjSub(self.centralwidget)  # Create an instance of your custom table view
        
        # Replace the original QTableView with TableProjSub in the layout
        layout = self.centralwidget.layout()
        layout.replaceWidget(originalTableView, tableProj)
        layout.removeWidget(originalTableView)

        # Update the layout
        layout.update()
        self.tableProj = tableProj
        tableProj.setAcceptDrops(True)
        tableProj.setObjectName("tableProj")

        self.df_project = df_projectTemplate()
        self.tablemodel = TableModel(self.df_project)
        self.tableProj.setModel(self.tablemodel)

        self.projectfolder = self.projects_folder / self.projectname
        # If projectfile exists, load it, otherwise create it
        if Path(self.projectfolder / "project.brainwash").exists():
            self.load_df_project()
        else:
            self.projectname = "My Project"
            self.projectfolder = self.projects_folder / self.projectname
            self.setTableDf(self.df_project)
        self.write_cfg()

        # Write local cfg, for storage of group colours, zoom levels etc.
        self.project_cfg_yaml = self.projectfolder / "project_cfg.yaml"
        self.delete_locked = True
        self.list_groups = []
        if self.project_cfg_yaml.exists():
            with self.project_cfg_yaml.open("r") as file:
                project_cfg = yaml.safe_load(file)
                self.delete_locked = project_cfg["delete_locked"] == "True"  # Delete lock engaged
                self.list_groups = project_cfg["list_groups"]
                # print(f"Found project_cfg['delete_locked']:{project_cfg['delete_locked']}")
                # print(f"Boolean project_cfg:{self.delete_locked}")
        else:
            project_cfg = {"delete_locked": str(self.delete_locked), "list_groups": self.list_groups}
            print("Creating project_cfg:", self.project_cfg_yaml)
            self.write_project_cfg()
        # Enforce local cfg
        self.checkBoxLockDelete.setChecked(self.delete_locked)
        self.pushButtonDelete.setEnabled(not self.delete_locked)
        for group in self.list_groups:  # Generate buttons based on groups in project:
            self.addGroupButton(group)

        if track_widget_focus: # debug mode; prints widget focus every 1000ms
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.checkFocus)
            self.timer.start(1000)  

        # Internal storage dicts
        self.dict_datas = {} # all data
        self.dict_means = {} # all means
        self.dict_outputs = {} # all outputs
        self.dict_group_means = {} # means of all group outputs

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

        # place current project as folder in project_root, lock project name for now
        # self.projectfolder = self.project_root / self.project

# Placeholder tuples (zoom for graphs)
    graph_xlim = (0.006, 0.020)
    graph_ylim = (-0.1, 0.02)


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
        # print(self.list_groups)
        # print(f"self.gridLayout: {self.gridLayout}")
        # print(f"range(self.gridLayout.count()): {range(self.gridLayout.count())}")
        for group in self.list_groups:
            for i in range(self.gridLayout.count()):
                widget = self.gridLayout.itemAt(i).widget()
                if widget and widget.text() == group:
                    widget.deleteLater()
                    if verbose:
                        print("Removed", group, f"(widget: {widget}")
        self.list_groups = []
        self.write_project_cfg()

    def pushedButtonAddGroup(self):
        if verbose:
            print("pushedButtonGroups")
        if len(self.list_groups) < 12: # TODO: hardcoded max nr of groups: move to cfg
            i = 0
            while True:
                new_group_name = "group_" + str(i)
                if new_group_name in self.list_groups:
                    if verbose:
                        print(new_group_name, " already exists")
                    i += 1
                else:
                    self.list_groups.append(new_group_name)
                    print("created", new_group_name)
                    break
            self.write_project_cfg()
            self.addGroup(new_group_name)
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
        self.projectfolder.mkdir(exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d")
        i = 0
        while True:
            new_project_name = "Project " + date
            if i > 0:
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
        projectfolder = QtWidgets.QFileDialog.getExistingDirectory(
            self.dialog, "Open Directory", str(self.projects_folder), QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
        )
        if verbose:
            print(f"Received projectfolder: {str(projectfolder)}")
        if (Path(projectfolder) / "project.brainwash").exists():
            self.projectfolder = Path(projectfolder)
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
        selected_rows = self.listSelectedRows()
        df_selection = self.df_project.loc[selected_rows]
        self.setGraph(df = df_selection)

    def tableProjDoubleClicked(self):
        self.launchMeasureWindow()

    def checkedBoxLockDelete(self, state):
        if state == 2:
            self.delete_locked = True
        else:
            self.delete_locked = False
        self.pushButtonDelete.setEnabled(not self.delete_locked)
        if verbose:
            print(f"checkedBoxLockDelete {state}, self.delete_locked:{self.delete_locked}")
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
        df_p["channel"] = df_p["channel"].fillna(" ")
        df_p["stim"] = df_p["stim"].fillna(" ")
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
            old_recording_name = df_p.at[row,'recording_name']
            old_data = self.projectfolder / (old_recording_name + ".csv")
            old_mean = self.projectfolder / (old_recording_name + "_mean.csv")
            RenameDialog = InputDialogPopup()
            new_recording_name = RenameDialog.showInputDialog(title='Rename recording', query='')
            if re.match(r'^[a-zA-Z0-9_-]+$', str(new_recording_name)) is not None: # check if valid filename
                list_recording_names = set(df_p['recording_name'])
                if not new_recording_name in list_recording_names: # prevent duplicates
                    new_data = self.projectfolder / (new_recording_name + ".csv")
                    new_mean = self.projectfolder / (new_recording_name + "_mean.csv")
                    if old_data.exists() & old_mean.exists():
                        if verbose:
                            print(f"rename_data: {old_data} to {new_data}")
                            print(f"rename_mean: {old_mean} to {new_mean}")
                            print(f"new recording_name set: {new_recording_name}")
                        os.rename(old_data, new_data)
                        os.rename(old_mean, new_mean)
                    else:
                        print(f"data file exists: {old_data.exists()} : {old_data}")
                        print(f"mean file exists: {old_mean.exists()} : {old_mean}")
                        raise FileNotFoundError
                    df_shared_recording_name = df_p[df_p['recording_name'] == old_recording_name]
                    for i, subrow in df_shared_recording_name.iterrows():
                        df_p.at[i,'recording_name'] = new_recording_name
                    self.set_df_project(df_p)
                    self.setTableDf(self.df_project)  # Force update
                else:
                    print(f"new_recording_name {new_recording_name} already exists")
            else:
                print(f"new_recording_name {new_recording_name} is not a valid filename")    
        else:
            print("Rename: please select one row only for renaming.")

    def deleteSelectedRows(self):
        df_p = self.df_project
        set_files_before_purge = set(df_p['recording_name'])
        selected_rows = self.listSelectedRows()
        if 0 < len(selected_rows):
            files_to_purge = False
            for row in selected_rows:
                sweeps = df_p.at[row, 'sweeps']
                if sweeps != "...": # if the file is parsed:
                    files_to_purge = True
                    recording_name = df_p.at[row, 'recording_name']
                    channel = df_p.at[row, 'channel']
                    stim = df_p.at[row, 'stim']
                    if verbose:
                        print("Delete:", recording_name, channel, stim)
                    data_path = Path(self.projectfolder / (recording_name + ".csv"))
                    try:
                        df = pd.read_csv(str(data_path))  # parse csv
                    except FileNotFoundError:
                        print("did not find data .csv to load. Not imported?")
                    dfmean_path = Path(self.projectfolder / (recording_name + "_mean.csv"))
                    try:
                        dfmean = pd.read_csv(str(dfmean_path))  # parse _mean.csv
                    except FileNotFoundError:
                        print("did not find _mean.csv to load. Not imported?")
                    purged_df = df[(df['channel'] != channel) | (df['stim'] != stim)]
                    purged_dfmean = dfmean[(dfmean['channel'] != channel) | (dfmean['stim'] != stim)]
                    parse.persistdf(recording_name=recording_name, proj_folder=self.projectfolder, dfdata=purged_df, dfmean=purged_dfmean)
            # Regardless of whether or not there was a file, purge the row from df_project
            self.clearGraph()
            df_p.drop(selected_rows, inplace=True)
            if files_to_purge: # unlink any files that are no longer in df_p
                set_files_after_purge = set(df_p['recording_name'])
                list_delete = [item for item in set_files_before_purge if item not in set_files_after_purge]
                for file in list_delete:
                    delete_data = self.projectfolder / (file + ".csv")
                    delete_mean = self.projectfolder / (file + "_mean.csv")
                    if delete_data.exists():
                        delete_data.unlink()
                        if verbose:
                            print(f"Deleted data: {delete_data}")
                    else:
                        print(f"File not found: {delete_data}")
                    if delete_mean.exists():
                        delete_mean.unlink()
                        if verbose:
                            print(f"Deleted mean: {delete_mean}")
                    else:
                        print(f"File not found: {delete_mean}")
            df_p.reset_index(inplace=True, drop=True)
            self.set_df_project(df_p)
            self.setTableDf(self.df_project)  # Force update
        else:
            print("No files selected.")

    def parse_data(self): # parse data files and modify self.df_project accordingly
        update_frame = self.df_project.copy()  # copy from which to remove rows without confusing index
        rows = []
        for i, df_proj_row in self.df_project.iterrows():
            recording_name = df_proj_row['recording_name']
            source_path = df_proj_row['path']
            if df_proj_row["sweeps"] == "...":  # indicates not read before TODO: Replace with selector!
                dictmeta = parse.parseProjFiles(self.projectfolder, recording_name=recording_name, source_path=source_path)  # result is a dict of <channel>:<channel ID>
                for channel in dictmeta['channel']:
                    for stim in dictmeta['stim']:
                        df_proj_new_row = df_proj_row.copy()
                        df_proj_new_row['channel'] = channel
                        df_proj_new_row['stim'] = stim
                        df_proj_new_row['sweeps'] = dictmeta['sweeps']
                        rows.append(df_proj_new_row)
                update_frame = update_frame[update_frame.recording_name != recording_name]
                print(f"update_frame: {update_frame}")
                rows2add = pd.concat(rows, axis=1).transpose()
                print("rows2add:", rows2add[["recording_name", "channel", "stim", "sweeps" ]])
                self.df_project = (pd.concat([update_frame, rows2add])).reset_index(drop=True)
                print(self.df_project[["recording_name", "channel", "stim", "sweeps" ]])
                self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
                self.save_df_project()


# Data Group functions

    def addGroup(self, new_group_name):
        if verbose:
            print("addGroupButton")
        self.addGroupButton(new_group_name)

    def addGroupButton(self, group):
        self.new_button = QtWidgets.QPushButton(group, self.centralwidget)
        self.new_button.setObjectName(group)
        self.new_button.clicked.connect(lambda _, button_name=group: self.pushedGroupButton(group))
        # Arrange in rows of 4. TODO: hardcoded number of columns: move to cfg
        column = self.list_groups.index(group)
        row = 0
        print(row, column)
        while column >= 4:
            column -= 4
            row += 1
        self.gridLayout.addWidget(self.new_button, row, column, 1, 1)
        # self.gridLayout.addWidget(self.new_button, self.gridLayout.rowCount(), 0, 1, 1)

    def addToGroup(self, add_group):
        # Assign all selected files to group "add_group" unless they already belong to that group
        selected_rows = self.listSelectedRows()
        if 0 < len(selected_rows):
            list_group = ""
            for i in selected_rows:
                if self.df_project.loc[i, "groups"] == " ":
                    self.df_project.loc[i, "groups"] = add_group
                else:
                    list_group = self.df_project.loc[i, "groups"]
                    list_group = list(list_group.split(","))
                    if add_group not in list_group:
                        list_group.append(add_group)
                        self.df_project.loc[i, "groups"] = ",".join(map(str, sorted(list_group)))
                    else:
                        print(f"{self.df_project.loc[i, 'recording_name']}, channel {self.df_project.loc[i, 'channel']}, stim {self.df_project.loc[i, 'stim']} is already in {add_group}")
                self.save_df_project()
                self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
        else:
            print("No files selected.")

    def clearGroupsByRow(self, rows):
        for i in rows:
            self.df_project.loc[i, "groups"] = " "
        self.save_df_project()
        self.setTableDf(self.df_project)  # Force update table (TODO: why is this required?)
        self.clearGraph()


# writer functions
    
    def write_cfg(self):  # config file for program, global stuff
        cfg = {"user_documents": str(self.user_documents), "projects_folder": str(self.projects_folder), "projectname": self.projectname}
        #        new_projectfolder = self.projects_folder / self.projectname
        #        new_projectfolder.mkdir(exist_ok=True)
        with self.cfg_yaml.open("w+") as file:
            yaml.safe_dump(cfg, file)

    def write_project_cfg(self):  # config file for project, local stuff
        project_cfg = {"delete_locked": str(self.delete_locked), "list_groups": self.list_groups}
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
            self.projectfolder = new_projectfolder
            self.projectname = new_project_name
            self.inputProjectName.setText(self.projectname)
            self.clearGraph()
            self.df_project = df_projectTemplate()
            self.setTableDf(self.df_project)
            self.save_df_project()
            self.write_cfg()

    def renameProject(self): # changes name of project folder and updates .cfg
        self.projectfolder.mkdir(exist_ok=True)
        new_project_name = self.inputProjectName.text()
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if verbose:
                print(f"Project name {new_project_name} already exists.")
            self.inputProjectName.setText(self.projectname)
        elif re.match(r'^[a-zA-Z0-9_-]+$', str(new_project_name)) is not None: # check if valid filename
            self.projectfolder = self.projectfolder.rename(self.projects_folder / new_project_name)
            self.projectname = new_project_name
            self.inputProjectName.setReadOnly(True)
            self.write_cfg()
            print(f"Project renamed to {new_project_name}.")
        else:
            print(f"Project name {new_project_name} is not a valid path.")

    def setProjectname(self):
        # get_signals(self.children()[1].children()[1].model)
        self.projectname = self.inputProjectName.text()
        self.projectfolder = self.projects_folder / self.projectname
        if self.projectfolder.exists():
            # look for project.brainwash and load it
            if (self.projectfolder / "project.brainwash").exists():
                self.load_df_project()
        else:
            self.projectfolder.mkdir()
        if verbose:
            print(f"setProjectname, folder: {self.projectfolder} exists: {self.projectfolder.exists()}")


# Project dataframe handling

    def get_df_project(self): # returns a copy of the persistent df_project TODO: make these functions the only way to get to it.
        return self.df_project

    def load_df_project(self): # reads fileversion of df_project to persisted self.df_project, clears graphs and saves cfg
        self.df_project = pd.read_csv(str(self.projectfolder / "project.brainwash"))
        self.setTableDf(self.df_project)  # display self.df_project to table
        self.inputProjectName.setText(self.projectfolder.stem)  # set folder name to proj name
        self.projectname = self.projectfolder.stem
        if verbose:
            print(f"loaded project df: {self.df_project}")
        self.clearGraph()
        self.write_cfg()

    def save_df_project(self): # writes df_project to .csv
        self.df_project.to_csv(str(self.projectfolder / "project.brainwash"), index=False)

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
                     df_p.columns.get_loc("sweeps"),
                     df_p.columns.get_loc("channel"),
                     df_p.columns.get_loc("stim")]
        num_columns = df_p.shape[1]
        for col in range(num_columns):
            if col in list_show:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
            else:
                self.tableProj.setColumnHidden(col, True)

# internal dataframe handling
    def row2key(self, row):
        return (row['recording_name'] + str(row['channel']) + str(row['stim']))

    def get_dfmean(self, row):
        # returns an internal df mean for the selected file. If it does not exist, read it from file first.
        key_mean = self.row2key(row=row) + "_mean"
        if key_mean in self.dict_means:
            return self.dict_means[key_mean]
        else:
            recording_name = row['recording_name']
            channel = row['channel']
            stim = row['stim']
            dfmean_path = self.projectfolder / (recording_name + "_mean.csv")
            try:
                dfmean = pd.read_csv(dfmean_path)
            except FileNotFoundError:
                print("did not find _mean.csv to load. Not imported?")
            dfcopy = dfmean[(dfmean['channel'] == channel) & (dfmean['stim'] == stim)].copy()
            dfcopy.reset_index(inplace=True)
            self.dict_means[key_mean] = dfcopy
            return self.dict_means[key_mean]

    def get_dfoutput(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        key_output = self.row2key(row=row) + "_output"
        if key_output in self.dict_outputs:
            return self.dict_outputs[key_output]
        else:
            df_data = self.get_dfdata(row)
            all_t = analysis.find_all_t(dfmean=self.get_dfmean(row=row), verbose=verbose)
            t_EPSP_amp = all_t["t_EPSP_amp"]
            df_result = analysis.build_df_result(df_data=df_data, t_EPSP_amp=t_EPSP_amp)
            df_result.reset_index(inplace=True)

            self.dict_outputs[key_output] = df_result
            return self.dict_outputs[key_output]
        
    def get_dfdata(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        key_data = self.row2key(row=row)
        if key_data in self.dict_datas:
            return self.dict_datas[key_data]
        else:
            recording_name = row['recording_name']
            channel = row['channel']
            stim = row['stim']
            # TODO: Placeholder functionality for loading analysis.buildResultFile()
            file_path = Path(self.projectfolder / (recording_name + ".csv"))
            if not file_path.exists():
                print(f"Error: {file_path} not found.")
                return
            df_datafile = pd.read_csv(file_path)
            df_data = df_datafile[(df_datafile['channel']==channel) & (df_datafile['stim']==stim)].copy()
            df_data.reset_index(inplace=True)

            self.dict_datas[key_data] = df_data
            return self.dict_datas[key_data]
        
    def get_df_groupmean(self, key_group):
        # returns an internal df output average of <group>. If it does not exist, create it
        if key_group in self.dict_group_means:
            return self.dict_group_means[key_group]
        else:
            df_p = self.df_project
            df_group = df_p[df_p['groups'].str.split(',').apply(lambda x: key_group in x)]
            dfs = []
            for i, row in df_group.iterrows():
                df = self.get_dfoutput(row=row)
                dfs.append(df)
            dfs = pd.concat(dfs)
            group_mean = dfs.groupby('sweep')['EPSP_amp'].agg(['mean', 'sem']).reset_index()
            group_mean.columns = ['sweep', 'EPSP_amp_mean', 'EPSP_amp_sem']
            print(f"group_mean: {group_mean}")
            self.dict_group_means[key_group] = group_mean
            return self.dict_group_means[key_group]        


# Graph handling

    def clearGraph(self): # removes all data from canvas_seaborn
        if hasattr(self, "canvas_seaborn_mean"):
            if verbose:
                print("clearGraph: self has attribue canvas_seaborn_mean")
            print(f"axes: {self.canvas_seaborn_mean.axes}")
            self.canvas_seaborn_mean.axes.cla()
            self.canvas_seaborn_mean.draw()
            self.canvas_seaborn_mean.show()

    def setGraph(self, df): # plot selected row(s), or clear graph if empty
        #print(f"df.shape[0]: {df.shape[0]}")
        self.canvas_seaborn_mean = MplCanvas(parent=self.graphMean)  # instantiate canvas for Mean
        self.canvas_seaborn_output = MplCanvas(parent=self.graphOutput)  # instantiate canvas for MeanGroups

        # add groups, regardless of selection:
        # print(f"Groups: {self.list_groups}")
        list_color = ["red", "green", "blue", "yellow"] # TODO: placeholder color range
        for color, group in enumerate(self.list_groups):
            df_group_mean = self.get_df_groupmean(key_group=group)
            # TODO: Errorbars: do I have
            sns.lineplot(data=df_group_mean, y="EPSP_amp_mean", x="sweep", ax=self.canvas_seaborn_output.axes, 
                         color=list_color[color])            

        if df.shape[0] == 0:
            self.canvas_seaborn_mean.axes.cla()
        else:
            df_filtered = df[df["sweeps"] != "..."]
            if df_filtered.empty:
                print("Selection not analyzed.")
            else:
                for i, row in df_filtered.iterrows(): # TODO: i to be used later for cycling colours?
                    dfmean = self.get_dfmean(row=row)
                    dfmean["voltage"] = dfmean.voltage / dfmean.voltage.abs().max()
                    sns.lineplot(data=dfmean, y="voltage", x="time", ax=self.canvas_seaborn_mean.axes, color="black")
                    # add results of selected row(s):
                    dfoutput = self.get_dfoutput(row=row)
                    sns.lineplot(data=dfoutput, y="EPSP_amp", x="sweep", ax=self.canvas_seaborn_output.axes, color="black")

        self.canvas_seaborn_mean.axes.set_xlim(self.graph_xlim)
        self.canvas_seaborn_mean.axes.set_ylim(self.graph_ylim)
        self.canvas_seaborn_output.axes.set_ylim(-0.0015, 0)

        self.canvas_seaborn_mean.draw()
        self.canvas_seaborn_mean.show()

        self.canvas_seaborn_output.draw()
        self.canvas_seaborn_output.show()


# MeasureWindow

    def launchMeasureWindow(self):  # , single_index_range):
        # TODO:find_all_ture_window (if it's already open, focus on it)
        #   How to check for existing windows?
        #   How to shift focus?
        # Display the appropriate recording on the new window's graphs: mean and output
        #   Construct a sensible interface: drag-drop on measurement middle, start and finish points
        #   UI for toggling displayed measurement methods. Drag-drop forces Manual.

        # table_row should already have t_ values; otherwise do not attempt to draw them

        qt_index = self.tableProj.selectionModel().selectedIndexes()[0]
        ser_table_row = self.tablemodel.dataRow(qt_index)
        row_index = ser_table_row.name
        recording_name = ser_table_row["recording_name"]
        channel = ser_table_row["channel"]
        stim = ser_table_row["stim"]
        sweeps = ser_table_row["sweeps"]
        if sweeps == "...":
            # TODO: Make it import the missing file
            print("Unknown number of sweeps - not imported?")
            return
        
        # Open window
        self.measure = QtWidgets.QDialog()
        self.measure_window_sub = Measure_window_sub(self.measure)
        window_name = (recording_name + ",_ch" + str(channel) + ", st" + stim)
        self.measure.setWindowTitle(window_name)
        self.measure.show()

        dfmean = self.get_dfmean(ser_table_row)
        # Analysis.py
        all_t = analysis.find_all_t(dfmean=dfmean, verbose=verbose)
        # Break out to variables
        t_VEB = all_t["t_VEB"]
        t_EPSP_amp = all_t["t_EPSP_amp"]
        t_EPSP_slope = all_t["t_EPSP_slope"]
        # Store variables in self.df_project
        self.df_project.loc[row_index, "t_VEB"] = t_VEB
        self.df_project.loc[row_index, "t_EPSP_amp"] = t_EPSP_amp
        self.df_project.loc[row_index, "t_EPSP_slope"] = t_EPSP_slope
        
        print(f"t_EPSP_amp: {t_EPSP_amp}")

        # zero Y
        dfmean["voltage"] = dfmean.voltage / dfmean.voltage.abs().max()
        dfmean["prim"] = dfmean.prim / dfmean.prim.abs().max()
        dfmean["bis"] = dfmean.bis / dfmean.bis.abs().max()

        self.measure_window_sub.setMeasureGraph(recording_name, dfmean, t_VEB=t_VEB, t_EPSP_amp=t_EPSP_amp, t_EPSP_slope=t_EPSP_slope)

        # TODO: Placeholder functionality for loading analysis.buildResultFile()
        file_path = Path(self.projectfolder / (recording_name + ".csv"))
        if not file_path.exists():
            print(f"Error: {file_path} not found.")
            return
        df_data = self.get_dfdata(row=ser_table_row)

        df_result = analysis.build_df_result(df_data=df_data, t_EPSP_amp=t_EPSP_amp)
        df_result.reset_index(inplace=True)
        print(recording_name, channel, stim)
        
        self.measure_window_sub.setOutputGraph(df_result=df_result)
        
            
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
            print(f'You entered: {text}')
            self.accept()  # Close the dialog when Enter is pressed
            return text


class TableProjSub(QtWidgets.QTableView):
    # subclassing to change behavior of keypress event
    def keyPressEvent(self, event):
        # print("a key pressed in CustomTableView")
        if event.key() == QtCore.Qt.Key.Key_F2:
            ui.renameRecording()
            # Forward the key press event to the base class
            super().keyPressEvent(event)
        else:
            # Handle other key events or pass them to the base class
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

        # Dataframe to add
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
    def __init__(self, measure_window, parent=None, folder="."):
        super(Measure_window_sub, self).__init__()
        self.setupUi(measure_window)
        self.parent = parent
        if verbose:
            print(" - measure_window init")

    def setMeasureGraph(self, recording_name, dfmean, t_VEB=None, t_EPSP_amp=None, t_EPSP_slope=None):
        # get dfmean from selected row in UIsub.
        # display SELECTED from tableProj at measurewindow
        if verbose:
            print("setMeasureGraph", dfmean)
        self.canvas_seaborn = MplCanvas(parent=self.measure_graph_mean)  # instantiate canvas

        # fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
        g = sns.lineplot(data=dfmean, y="prim", x="time", ax=self.canvas_seaborn.axes, color="red")
        g = sns.lineplot(data=dfmean, y="bis", x="time", ax=self.canvas_seaborn.axes, color="green")
        h = sns.lineplot(data=dfmean, y="voltage", x="time", ax=self.canvas_seaborn.axes, color="black")
        h.axvline(t_EPSP_amp, color="black", linestyle="--")

        # t_VEB
        print(f"t_VEB: {t_VEB}")
        g.axvline(t_VEB, color="grey", linestyle="--")

        # t_EPSP_slope
        g.axvline(t_EPSP_slope - 0.0004, color="green", linestyle=":")
        g.axvline(t_EPSP_slope, color="green", linestyle="--")
        g.axvline(t_EPSP_slope + 0.0004, color="green", linestyle=":")
        # plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0)

        # if not title is None:
        # ax1.set_title(title)
        self.canvas_seaborn.axes.set_xlim(ui.graph_xlim)
        self.canvas_seaborn.axes.set_ylim(ui.graph_ylim)

        # self.canvas_seaborn.axes.set_xmargin((100,500))
        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()

    def setOutputGraph(self, df_result):
        # get df_result from selected row in UIsub.
        # display SELECTED from tableProj at measurewindow
        if verbose:
            print("setOutputGraph", df_result)
        self.canvas_seaborn = MplCanvas(parent=self.measure_graph_output)  # instantiate canvas

        g = sns.lineplot(data=df_result, y="EPSP_amp", x="sweep", ax=self.canvas_seaborn.axes, color="black")
        self.canvas_seaborn.axes.set_ylim(-0.0015, 0)

        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()


def get_signals(source):
    cls = source if isinstance(source, type) else type(source)
    signal = type(QtCore.pyqtSignal())
    print("get_signals:")
    for subcls in cls.mro():
        clsname = f"{subcls.__module__}.{subcls.__name__}"
        for key, value in sorted(vars(subcls).items()):
            if isinstance(value, signal):
                print(f"{key} [{clsname}]")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UIsub(MainWindow)
    MainWindow.show()

    sys.exit(app.exec_())