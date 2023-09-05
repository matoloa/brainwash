from csv import Dialect
import os #TODO: replace use by pathlib?
import sys
from pathlib import Path
import yaml

import matplotlib
#import matplotlib.pyplot as plt #TODO: use instead of matplotlib for smaller import?
import seaborn as sns

matplotlib.use('Qt5Agg')

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets, QtGui, uic
from datetime import datetime

import parse
import analysis

verbose = True

class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data=None):
        super(TableModel, self).__init__()
        self._data = data


    def data(self, index, role=None): # dataCell
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

    
    def setData(self, data: pd.DataFrame=None):
        if not data is None and type(data) is pd.DataFrame:
            self.beginResetModel()
            self._data = data
            self.endResetModel()
            return True
        
        return False


class FileTreeSelectorModel(QtWidgets.QFileSystemModel): #Should be paired with a FileTreeSelectorView
    paths_selected = QtCore.pyqtSignal(list)
    def __init__(self, parent=None, root_path='.'):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.root_path      = root_path
        self.verbose = verbose
        self.checks         = {}
        self.nodestack      = []
        self.parent_index   = self.setRootPath(self.root_path)
        self.root_index     = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot)
        self.sort(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.directoryLoaded.connect(self._loaded)


    def _loaded(self, path):
        if self.verbose: print('_loaded', self.root_path, self.rowCount(self.parent_index))


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
            if (v == 2): # Checked
                paths.append(format(self.filePath(k)))
        self.paths_selected.emit(paths)    

    
    def setData(self, index, value, role):
        if (role == QtCore.Qt.CheckStateRole and index.column() == 0):
            self.checks[index] = value
            if verbose: print('setData(): {}'.format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)


    def traverseDirectory(self, parentindex, callback=None):
        if verbose: print('traverseDirectory():')
        callback(parentindex)
        if self.hasChildren(parentindex):
            path = self.filePath(parentindex)
            it = QtCore.QDirIterator(path, self.filter()  | QtCore.QDir.NoDotAndDotDot)
            while it.hasNext():
                childIndex =  self.index(it.next())
                self.traverseDirectory(childIndex, callback=callback)
        else:
            print('no children')


    def printIndex(self, index):
        print('model printIndex(): {}'.format(self.filePath(index)))


class FileTreeSelectorDialog(QtWidgets.QWidget):
    def __init__(self, parent=None, root_path='.'):
        super().__init__(parent)


    def delayedInitForRootPath(self, root_path):
        self.root_path      = str(root_path)

        # Model
        self.model          = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # view
        self.view           = QtWidgets.QTreeView()

        self.view.setObjectName('treeView_fileTreeSelector')
        self.view.setWindowTitle("Dir View")    #TODO:  Which title?
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
        self.node_stack     = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(self.view)
        self.setLayout(windowlayout)

        #QtCore.QMetaObject.connectSlotsByName(self)


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


########################################################################
##### section directly copied from output from pyuic, do not alter #####
##### WARNING: changed parent class 'object' to 'QtCore.QObject'   #####
########################################################################

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
    

########################################################################
##### section directly copied from output from pyuic, do not alter #####
##### trying to make all the rest work with it                     #####
##### WARNING: I was forced to change the parent class from        #####
##### 'object' to 'QtCore.QObject' for the pyqtSlot(list) to work  #####
########################################################################


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
        self.pushButtonAddGroup = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonAddGroup.setObjectName("pushButtonAddGroup")
        self.horizontalLayoutData.addWidget(self.pushButtonAddGroup)
        self.pushButtonEditGroups = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonEditGroups.setObjectName("pushButtonEditGroups")
        self.horizontalLayoutData.addWidget(self.pushButtonEditGroups)
        self.pushButtonDelete = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonDelete.setMaximumSize(QtCore.QSize(60, 16777215))
        self.pushButtonDelete.setObjectName("pushButtonDelete")
        self.horizontalLayoutData.addWidget(self.pushButtonDelete)
        self.checkBoxLockDelete = QtWidgets.QCheckBox(self.centralwidget)
        self.checkBoxLockDelete.setMaximumSize(QtCore.QSize(15, 16777215))
        self.checkBoxLockDelete.setText("")
        self.checkBoxLockDelete.setChecked(True)
        self.checkBoxLockDelete.setObjectName("checkBoxLockDelete")
        self.horizontalLayoutData.addWidget(self.checkBoxLockDelete)
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
        self.pushButtonAddGroup.setText(_translate("mainWindow", "Add Group"))
        self.pushButtonEditGroups.setText(_translate("mainWindow", "Edit Groups"))
        self.pushButtonDelete.setText(_translate("mainWindow", "Delete"))
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
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
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


def buildTemplate():
    return pd.DataFrame(columns=['host', 'path', 'checksum', 'save_file_name', 'groups', 'parsetimestamp', 'nSweeps', #0-6
                                't_stim', 't_stim_method', 't_stim_params', #7-9
                                't_VEB', 't_VEB_method', 't_VEB_params', #10-12
                                't_volley_amp', 't_volley_amp_method', 't_volley_amp_params', #13-15
                                't_volley_slope', 't_volley_slope_method', 't_volley_slope_params', #16-18
                                't_EPSP_amp', 't_EPSP_amp_method', 't_EPSP_amp_params', #19-21
                                't_EPSP_slope', 't_EPSP_slope_method', 't_EPSP_slope_params', #22-24
                                'exclude', 'comment']) #25-26


# subclassing Ui_MainWindow to be able to use the unaltered output file from pyuic and QT designer
class UIsub(Ui_MainWindow):
    def __init__(self, mainwindow):
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)
        if verbose: print(' - UIsub init, verbose mode') # rename for clarity

        # load cfg if present
        paths = [Path.cwd()] + list(Path.cwd().parents)
        self.repo_root = [i for i in paths if (-1 < str(i).find('brainwash')) & (str(i).find('src') == -1)][0] # path to brainwash directory
        self.cfg_yaml = self.repo_root / 'cfg.yaml'
        self.projectname = None
        self.inputProjectName.setReadOnly(True)

        if self.cfg_yaml.exists():
            with self.cfg_yaml.open('r') as file:
                cfg = yaml.safe_load(file)
                self.user_documents = Path(cfg['user_documents']) # Where to look for raw data
                self.projects_folder = Path(cfg['projects_folder']) # Where to save and read parsed data
                self.projectname = cfg['projectname']
        else:
            self.user_documents = Path.home() / 'Documents' # Where to look for raw data
            self.projects_folder = self.user_documents / 'Brainwash Projects' # Where to save and read parsed data
            self.projectname = 'My Project'

        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)

        self.projectdf = buildTemplate()
        self.tablemodel = TableModel(self.projectdf)
        self.tableProj.setModel(self.tablemodel)

        self.projectfolder = self.projects_folder / self.projectname
        # If projectfile exists, load it, otherwise create it
        if Path(self.projectfolder / "project.brainwash").exists():
            self.load_dfproj()
        else:
            self.projectname = "My Project"
            self.projectfolder = self.projects_folder / self.projectname
            self.setTableDf(self.projectdf)
        self.write_cfg()

        # Write local cfg, for storage of group colours, zoom levels etc.
        self.project_cfg_yaml = self.projectfolder / 'project_cfg.yaml'
        self.delete_locked = True
        self.list_groups = []
        self.dict_groups = {'button_name':'group_name'}
        if self.project_cfg_yaml.exists():
            with self.project_cfg_yaml.open('r') as file:
                project_cfg = yaml.safe_load(file)
                self.delete_locked = project_cfg['delete_locked'] == 'True' # Delete lock engaged
                self.list_groups = project_cfg['list_groups']
                #print(f"Found project_cfg['delete_locked']:{project_cfg['delete_locked']}")
                #print(f"Boolean project_cfg:{self.delete_locked}")
        else:
            project_cfg = {
                'delete_locked': str(self.delete_locked),
                'list_groups': self.list_groups
            }
            print("Creating project_cfg:", self.project_cfg_yaml)
            self.write_project_cfg()
        # Enforce local cfg
        self.checkBoxLockDelete.setChecked(self.delete_locked)
        self.pushButtonDelete.setEnabled(not self.delete_locked)
        for group in self.list_groups: # Generate buttons based on groups in project:
            self.addGroupButton(group)

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
        self.pushButtonDelete.pressed.connect(self.pushedButtonDelete)
        self.checkBoxLockDelete.stateChanged.connect(self.checkedBoxLockDelete)

        self.tableProj.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.tableProj.doubleClicked.connect(self.tableProjDoubleClicked)
        

        selection_model = self.tableProj.selectionModel()
        #selection_model.selectionChanged.connect(lambda x: print(self.tablemodel.dataRow(x.indexes()[0])))
        selection_model.selectionChanged.connect(self.tableProjSelectionChanged)
        #self.tablemodel.setData(self.projectdf)
        #self.tableProj.update()

        # place current project as folder in project_root, lock project name for now
        # self.projectfolder = self.project_root / self.project


    def pushedButtonEditGroups(self):
        # Open groups UI (not built)
        if verbose: print("pushedButtonEditGroups")


    def pushedButtonAddGroup(self):
        if verbose: print("pushedButtonGroups")
        print(f"self.list_groups before {self.list_groups}")
        i = 0
        while True:
            new_group_name = "group_" + str(i)
            if new_group_name in self.list_groups:
                if verbose: print(new_group_name, " already exists")
                i += 1
            else:
                self.list_groups.append(new_group_name)
                print("created", new_group_name)
                break
        print(f"self.list_groups after {self.list_groups}")
        self.write_project_cfg()
        self.addGroup(new_group_name)
    

    def addGroup(self, new_group_name):
        if verbose: print("addGroupButton")
        self.addGroupButton(new_group_name)
      

    def addGroupButton(self, group):
        self.new_button = QtWidgets.QPushButton(group, self.centralwidget)
        self.new_button.setObjectName(group)
        self.new_button.clicked.connect(lambda _, button_name=group: self.pushedGroupButton(group))
        #TODO: arrange in rows of 4
        self.gridLayout.addWidget(self.new_button, 0, self.gridLayout.columnCount(), 1, 1)
        #self.gridLayout.addWidget(self.new_button, self.gridLayout.rowCount(), 0, 1, 1)


    def pushedGroupButton(self, button_name):
        if verbose: print("pushedGroupButton", button_name)
        self.addToGroup(button_name)


    def addToGroup(self, add_group):
    # Placeholder function: Assign all selected files to add_group unless they already belong to that group
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        selected_rows = [row.row() for row in selected_indexes]
        n_rows = len(selected_rows)
        if 0 < n_rows:
            list_group = ""
            for i in selected_rows:
                if self.projectdf.loc[i, 'groups'] == ' ':
                    self.projectdf.loc[i, 'groups'] = add_group
                else:
                    list_group = self.projectdf.loc[i, 'groups']
                    list_group = list(list_group.split(","))
                    if add_group not in list_group:
                        list_group.append(add_group)
                        self.projectdf.loc[i, 'groups'] = ','.join(map(str,sorted(list_group)))
                    else:
                        print(self.projectdf.loc[i, 'save_file_name'], "is already in", add_group)
                self.save_dfproj()
                self.setTableDf(self.projectdf)  # Force update table (TODO: why is this required?)
        else:
            print("No files selected.")


    def pushedButtonDelete(self):
        # TODO: Delete files for selected rows
        if verbose: print("pushedButtonDelete")
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        selected_rows = [row.row() for row in selected_indexes]
        n_rows = len(selected_rows)
        if 0 < n_rows:
            dfProj = self.projectdf
            dfSelection = dfProj.loc[selected_rows]
            list_delete = dfSelection['save_file_name'].tolist()
            #print(f"list_delete: {list_delete}")
            self.clear_graph()
            for file in list_delete:
                delete_data = self.projectfolder / (file + ".csv")
                delete_mean = self.projectfolder / (file + "_mean.csv")
                if delete_data.exists():
                    delete_data.unlink()
                    print(f"Deleted data: {delete_data}")
                else:
                    print(f"File not found: {delete_data}")
                if delete_mean.exists():
                    delete_mean.unlink()
                    print(f"Deleted mean: {delete_mean}")
                else:
                    print(f"File not found: {delete_mean}")
            # remove selected rows from projectdf
            self.projectdf = dfProj.drop(selected_rows)
            self.projectdf.reset_index(inplace=True, drop=True)
            self.save_dfproj()
            self.setTableDf(self.projectdf) # Force update
        else:
            print("No files selected.")
            

    def checkedBoxLockDelete(self, state):
        if verbose: print("checkedBoxLockDelete", state)
        if state == 2:
            self.delete_locked = True
        else:
            self.delete_locked = False
        self.pushButtonDelete.setEnabled(not self.delete_locked)
        print(f"self.delete_locked:{self.delete_locked}")
        self.write_project_cfg()


    def write_cfg(self): # config file for program, global stuff
        cfg = {
            'user_documents': str(self.user_documents),
            'projects_folder': str(self.projects_folder),
            'projectname': self.projectname
            }
#        new_projectfolder = self.projects_folder / self.projectname
#        new_projectfolder.mkdir(exist_ok=True)
        with self.cfg_yaml.open('w+') as file:
            yaml.safe_dump(cfg, file)
    

    def write_project_cfg(self): # config file for project, local stuff
        project_cfg = {
            'delete_locked': str(self.delete_locked),
            'list_groups': self.list_groups
            }
        new_projectfolder = self.projects_folder / self.projectname
        new_projectfolder.mkdir(exist_ok=True)
        with self.project_cfg_yaml.open('w+') as file:
            yaml.safe_dump(project_cfg, file)
    
    
    def tableProjDoubleClicked(self):
        self.launchMeasureWindow()


    def launchMeasureWindow(self):#, single_index_range):
        # TODO:find_all_ture_window (if it's already open, focus on it)
        #   How to check for existing windows?
        #   How to shift focus?
        # Display the appropriate recording on the new window's graphs: mean and output
        #   Construct a sensible interface: drag-drop on measurement middle, start and finish points
        #   UI for toggling displayed measurement methods. Drag-drop forces Manual.

        """
        table_row should already have t_ values; otherwise do not attempt to draw them
        """

        qt_index = self.tableProj.selectionModel().selectedIndexes()[0]
        ser_table_row = self.tablemodel.dataRow(qt_index)
        nSweeps = ser_table_row['nSweeps']
        if nSweeps == '...':
            #TODO: Make it import the missing file
            print('did not find _mean.csv to load. Not imported?')
            return
        file_name = ser_table_row['save_file_name']
        row_index = ser_table_row.name
        if verbose: print("launchMeasureWindow", file_name)

        # Analysis.py
        all_t = analysis.find_all_t(self.dfmean, verbose=verbose)
        # Break out to variables
        t_VEB = all_t['t_VEB']
        t_EPSP_amp = all_t['t_EPSP_amp']
        t_EPSP_slope = all_t['t_EPSP_slope']

        # Store variables in self.projectdf
        self.projectdf.loc[row_index, 't_VEB'] = t_VEB
        self.projectdf.loc[row_index, 't_EPSP_amp'] = t_EPSP_amp
        self.projectdf.loc[row_index, 't_EPSP_slope'] = t_EPSP_slope

        if verbose: print(f"projectdf: {self.projectdf}")

        # Open window
        self.measure = QtWidgets.QDialog()
        self.measure_window_sub = Measure_window_sub(self.measure)
        self.measure.setWindowTitle(file_name)
        self.measure.show()

        self.measure_window_sub.setMeasureGraph(file_name, self.dfmean, t_VEB=t_VEB, t_EPSP_amp=t_EPSP_amp, t_EPSP_slope=t_EPSP_slope)


    def tableProjSelectionChanged(self):
        if verbose: print("tableProjSelectionChanged")
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        selected_rows = [row.row() for row in selected_indexes]
        n_rows = len(selected_rows)

        if 0 < n_rows:
            dfProj = self.projectdf
            dfSelection = dfProj.loc[selected_rows]
            dfFiltered = dfSelection[dfSelection['nSweeps'] != '...']
            list_files_filtered = dfFiltered['save_file_name'].tolist()
            if not dfFiltered.empty:
                if len(list_files_filtered) == 1: # exactly one file selected
                    self.setGraph(list_files_filtered[-1])
                else: # several files selected
                    self.setGraphs(list_files_filtered)
            else:
                print("Selection not analyzed.")
            return
        else:
            if verbose: print("No rows selected.")
        # if the file isn't imported, or no file selected, clear the mean graph
        self.clear_graph()


    def pushedButtonRenameProject(self):
        # renameProject
        if verbose: print("pushedButtonRenameProject")
        self.inputProjectName.setReadOnly(False)
        self.inputProjectName.editingFinished.connect(self.renameProject)


    def renameProject(self):
        #TODO: sanitize path
        # make if not existing
        self.projectfolder.mkdir(exist_ok=True)
        new_project_name = self.inputProjectName.text()
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if verbose: print("The target project name already exists")
            self.inputProjectName.setText(self.projectname)
        else:
            self.projectfolder = self.projectfolder.rename(self.projects_folder / new_project_name)
            self.projectname = new_project_name
            self.inputProjectName.setReadOnly(True)
            self.write_cfg()
        
 
    def pushedButtonNewProject(self):
        if verbose: print("pushedButtonNewProject")
        self.projectfolder.mkdir(exist_ok=True)
        date = datetime.now().strftime('%Y-%m-%d')
        i = 0
        while True:
            new_project_name = "Project " + date
            if i>0: new_project_name = new_project_name + "(" + str(i) + ")"
            if (self.projects_folder / new_project_name).exists():
                if verbose: print(new_project_name, " already exists")
                i += 1
            else:
                self.newProject(new_project_name)
                break

        
    def newProject(self, new_project_name):
        new_projectfolder = self.projects_folder / new_project_name
        # check if ok
        if (self.projects_folder / new_project_name).exists():
            if verbose: print("The target project name already exists")
        else:
            new_projectfolder.mkdir()
            self.projectfolder = new_projectfolder
            self.projectname = new_project_name
            self.inputProjectName.setText(self.projectname)
            self.clear_graph()
            self.projectdf = buildTemplate()
            self.setTableDf(self.projectdf)
            self.save_dfproj()
            self.write_cfg()
        
    
    def pushedButtonOpenProject(self):
        # open folder selector dialog
        self.dialog = QtWidgets.QDialog()
        projectfolder = QtWidgets.QFileDialog.getExistingDirectory(self.dialog, "Open Directory", str(self.projects_folder), 
                                                            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        if verbose: print(f"Received projectfolder: {str(projectfolder)}")
        if (Path(projectfolder) / "project.brainwash").exists():
            self.projectfolder = Path(projectfolder)
            self.clear_graph()
            self.load_dfproj()
            self.write_cfg()


    def pushedButtonAddData(self):
        # creates file tree for file selection
        if verbose: print("pushedButtonAddData")
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.show()


    def pushedButtonParse(self):
        # parse non-parsed files and folders in self.projectdf
        if verbose: print("pushedButtonParse")
        update_frame = self.projectdf.copy() # copy from which to remove rows without confusing index
        frame2add = self.projectdf.iloc[0:0].copy() # new, empty df for adding rows for multi-channel readings, without messing with index
        for i, row in self.projectdf.iterrows():
            if row['nSweeps'] == '...': # indicates not read before
                # check number of channels. If more than one, create new row for each new channel. Re-sort df after loop.
                result = parse.parseProjFiles(self.projectfolder, row=row) # result is a dict of <channel>:<channel ID>
                if len(result) > 1: # more than one channel; rename
                    print(len(result), "channels found")
                    for j in result:
                        row2add = self.projectdf[self.projectdf.index==i].copy()
                        row2add['save_file_name'] = row2add['save_file_name'] + "_ch_" + str(j)
                        row2add['nSweeps'] = result[j]
                        frame2add = pd.concat([frame2add, row2add]) # add new, separate channel rows
                        update_frame = update_frame[update_frame.index!=i] # destroy original row in update_frame
                    if verbose: print (f"frame2add:{frame2add}")
                else: # just one channel - update nSweeps
                    print (f"result:{result}")
                    print (f"i:{i}")
                    update_frame.loc[i, 'nSweeps'] = str(list(result.values())[0])
                # TODO: NTH - new visual progress report (old one dysfunctional with index-preserving update_frame appraoch)
            else:
                print(i, "already exists: no action")

        self.projectdf = pd.concat([update_frame, frame2add])
        if verbose: print(f"update_frame: {update_frame}")
        self.projectdf.reset_index(inplace=True, drop=True) # Required for split abf files
        self.save_dfproj()
        self.setTableDf(self.projectdf)  # Force update table (TODO: why is this required?)


    def getdfProj(self):
        return self.projectdf


    def load_dfproj(self):
        self.projectdf = pd.read_csv(str(self.projectfolder / "project.brainwash"))
        self.setTableDf(self.projectdf)  # set dfproj to table
        self.inputProjectName.setText(self.projectfolder.stem)  # set foler name to proj name
        self.projectname = self.projectfolder.stem
        if verbose: print(f"loaded project df: {self.projectdf}")
        self.clear_graph()
        self.write_cfg()


    def save_dfproj(self):
        self.projectdf.to_csv(str(self.projectfolder / "project.brainwash"), index=False)        


    def set_dfproj(self, df):
        self.projectdf = df
        self.save_dfproj()


    def clear_graph(self):
        if verbose: print('clear_graph')
        if hasattr(self, 'canvas_seaborn'):
            if verbose: print('self has attribue canvas_seaborn')
            print(f"axes: {self.canvas_seaborn.axes}")
            self.canvas_seaborn.axes.cla()
            self.canvas_seaborn.draw()
            self.canvas_seaborn.show()


    def setGraph(self, save_file_name):
        #get dfmean from selected row in UIsub.
        # display SELECTED from tableProj at graphMean

        if verbose: print('setGraph')
        dfmean_path = self.projectfolder / (save_file_name + "_mean.csv")
        print(dfmean_path)
        try:
            dfmean = pd.read_csv(dfmean_path) # import csv
        except FileNotFoundError:
            print('did not find _mean.csv to load. Not imported?')
        #print("*** *** *** dfmean PRE reset_index:", dfmean)
        # dfmean = pd.read_csv('/home/jonathan/code/brainwash/dataGenerated/metaData/2022_01_24_0020.csv') # import csv
        self.canvas_seaborn = MplCanvas(parent=self.graphMean) # instantiate canvas
        dfmean.reset_index(inplace=True, drop=True)
        #print("*** *** *** dfmean POST reset_index:", dfmean)
        dfmean['voltage'] = dfmean.voltage / dfmean.voltage.abs().max()
        dfmean['prim'] = dfmean.prim / dfmean.prim.abs().max()
        dfmean['bis'] = dfmean.bis / dfmean.bis.abs().max()
        
        g = sns.lineplot(data=dfmean, y="voltage", x="time", ax=self.canvas_seaborn.axes, color="black")
        h = sns.lineplot(data=dfmean, y="prim", x="time", ax=self.canvas_seaborn.axes, color="red")
        i = sns.lineplot(data=dfmean, y="bis", x="time", ax=self.canvas_seaborn.axes, color="green")
        
        # TODO: replace hard-coding, overview but not the whole stim-artefact.
        self.canvas_seaborn.axes.set_ylim(-0.05, 0.01)
        self.canvas_seaborn.axes.set_xlim(0.006, 0.015)

        self.dfmean = dfmean # assign to self to make available for launchMeasureWindow()

        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()

#        dfmean.set_index('t0', inplace=True)
#        dfmean['slope'] = dfmean.slope / dfmean.slope.abs().max()
#        dfmean['sweep'] = dfmean.sweep / dfmean.sweep.abs().max()
#        g = sns.lineplot(data=dfmean, y="slope", x="t0", ax=self.canvas_seaborn.axes, color="black")
#        h = sns.lineplot(data=dfmean, y="sweep", x="t0", ax=self.canvas_seaborn.axes, color="red")
#        self.canvas_seaborn.draw()
#        self.canvas_seaborn.show()


    def setGraphs(self, list_files_filtered):
        # plot the mean voltages of several selected files
        #print(f"list_files_filtered: {list_files_filtered}")

        if verbose: print('setGraphs')

        dfmeans = []
        for file in list_files_filtered:
            dfmean_path = self.projectfolder / (file + "_mean.csv")
            #print(f"df_mean_path: {dfmean_path}")
            try:
                df = pd.read_csv(dfmean_path)
            except FileNotFoundError:
                print('did not find _mean.csv to load. Not imported?')
            dfmeans.append(df)
            #dfmeans = pd.concat([dfmeans, df], ignore_index=True, axis=0) #TODO: make functional

        self.canvas_seaborn = MplCanvas(parent=self.graphMean) # instantiate canvas
        for dfmeanfile in dfmeans:
            #sns.lineplot(data=dfmeanfile, x='time', y='voltage')
            dfmeanfile['voltage'] = dfmeanfile.voltage / dfmeanfile.voltage.abs().max()
            g = sns.lineplot(data=dfmeanfile, y="voltage", x="time", ax=self.canvas_seaborn.axes, color="black")

        self.canvas_seaborn.axes.set_ylim(-0.05, 0.01)
        self.canvas_seaborn.axes.set_xlim(0.006, 0.015)

        #self.dfmean = dfmean # assign to self to make available for launchMeasureWindow()

        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()
 

    def setProjectname(self):
        if verbose: print('setProjectname')
        #get_signals(self.children()[1].children()[1].model)
        self.projectname = self.inputProjectName.text()
        self.projectfolder = self.projects_folder / self.projectname
        if self.projectfolder.exists():
            # look for project.brainwash and load it
            if (self.projectfolder / "project.brainwash").exists():
                self.load_dfproj()
        else:
            self.projectfolder.mkdir()

        if verbose: print(f"folder: {self.projectfolder} exists: {self.projectfolder.exists()}")

           
    def setTableDf(self, data):
        if verbose: print('setTableDf')
        self.tablemodel.setData(data)
        self.formatTableProj() #hide/resize columns
        self.tableProj.update()


    def formatTableProj(self):
        if verbose: print('formatTableProj')
        header = self.tableProj.horizontalHeader()
        dfProj = self.projectdf
        #hide all columns except these:
        list_show = [dfProj.columns.get_loc('save_file_name'),
                     dfProj.columns.get_loc('groups'),
                     dfProj.columns.get_loc('nSweeps')]
        num_columns = dfProj.shape[1]
        for col in range(num_columns):
            if col in list_show:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
            else:
                self.tableProj.setColumnHidden(col, True)
        

    def addData(self, dfAdd): # concatenate dataframes of old and new data
        dfProj = self.getdfProj()
        dfProj = pd.concat([dfProj, dfAdd])
        dfProj.reset_index(drop=True, inplace=True)
        dfProj['groups'] = dfProj['groups'].fillna(' ')
        dfProj['nSweeps'] = dfProj['nSweeps'].fillna('...')
        self.set_dfproj(dfProj)
        if verbose: print('addData:', self.getdfProj())
        self.setTableDf(dfProj)
        
    
    @QtCore.pyqtSlot(list)
    def slotPrintPaths(self, mypaths):
        if verbose: print(f'mystr: {mypaths}')
        strmystr = "\n".join(sorted(['/'.join(i.split('/')[-2:]) for i in mypaths]))
        self.textBrowser.setText(strmystr)
        list_display_names = ['/'.join(i.split('/')[-2:]) for i in mypaths]
        dftable = pd.DataFrame({'path_source': mypaths, 'save_file_name': list_display_names})
        self.setTableDf(dftable)

        
    @QtCore.pyqtSlot()
    def slotAddDfData(self, df):
        self.addData(df)


class Filetreesub(Ui_Dialog):
    def __init__(self, dialog, parent=None, folder='.'):
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)
        self.parent = parent
        if verbose: print(' - Filetreesub init')
    
        self.ftree = self.widget
        # set root_path for file tree model
        self.ftree.delayedInitForRootPath(folder)
        #self.ftree.model.parent_index   = self.ftree.model.setRootPath(projects_folder)
        #self.ftree.model.root_index     = self.ftree.model.index(projects_folder)

        # Dataframe to add
        self.names = []
        self.dfAdd = buildTemplate()
        
        self.buttonBoxAddGroup = QtWidgets.QDialogButtonBox(dialog)
        self.buttonBoxAddGroup.setGeometry(QtCore.QRect(470, 20, 91, 491))
        self.buttonBoxAddGroup.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBoxAddGroup.setOrientation(QtCore.Qt.Vertical)
        self.buttonBoxAddGroup.setStandardButtons(QtWidgets.QDialogButtonBox.NoButton)
        self.buttonBoxAddGroup.setObjectName("buttonBoxAddGroup")
        
        # Manually added (unconnected) default group buttons - eventually, these must be populated from project.brainwash group names
        self.buttonBoxAddGroup.groupcontrol = QtWidgets.QPushButton(self.tr("&Control"))
        self.buttonBoxAddGroup.groupintervention = QtWidgets.QPushButton(self.tr("&Intervention"))
        self.buttonBoxAddGroup.newGroup = QtWidgets.QPushButton(self.tr("&New group"))
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.groupcontrol, QtWidgets.QDialogButtonBox.ActionRole)
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.groupintervention, QtWidgets.QDialogButtonBox.ActionRole)
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.newGroup, QtWidgets.QDialogButtonBox.ActionRole)

        self.ftree.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)
        self.ftree.model.paths_selected.connect(self.pathsSelectedUpdateTable)
        self.buttonBox.accepted.connect(self.addDf)

        self.tablemodel = TableModel(self.dfAdd)
        self.tableView.setModel(self.tablemodel)


    def addDf(self):
        self.parent.slotAddDfData(self.dfAdd)


    def pathsSelectedUpdateTable(self, paths):
        # TODO: Extract host, checksum, group
        if verbose: print('pathsSelectedUpdateTable')
        dfAdd = buildTemplate()
        dfAdd['path']=paths
        dfAdd['host']='Computer 1'
        dfAdd['checksum']='big number'
        #dfAdd['save_file_name']=paths
        #dfAdd['groups']=' '
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(os.path.basename(os.path.dirname(i)) + '_' + os.path.basename(i))
        dfAdd['save_file_name'] = names
        self.dfAdd = dfAdd
        # TODO: Add a loop that prevents duplicate names by adding a number until it becomes unique
        # TODO: names that have been set manually are stored a dict that persists while the addData window is open: this PATH should be replaced with this NAME (applied after default-naming, above)
        # format tableView
        header = self.tableView.horizontalHeader()
        self.tableView.setColumnHidden(0, True) #host
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents) #path
        self.tableView.setColumnHidden(2, True) #checksum
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents) #name
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents) #group
        self.tableView.update()


class Measure_window_sub(Ui_measure_window):
    def __init__(self, measure_window, parent=None, folder='.'):
        super(Measure_window_sub, self).__init__()
        self.setupUi(measure_window)
        self.parent = parent
        if verbose: print(' - measure_window init')


    def setMeasureGraph(self, save_file_name, dfmean, t_VEB=None, t_EPSP_amp=None, t_EPSP_slope=None):
        # get dfmean from selected row in UIsub.
        # display SELECTED from tableProj at measurewindow
        if verbose: print('setMeasureGraph', dfmean)
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
        #plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0)
        
#        if not title is None:
#            ax1.set_title(title)
        self.canvas_seaborn.axes.set_ylim(-0.05, 0.01)
        self.canvas_seaborn.axes.set_xlim(0.006, 0.015)
        
        #self.canvas_seaborn.axes.set_xmargin((100,500))
        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()


def get_signals(source):
        cls = source if isinstance(source, type) else type(source)
        signal = type(QtCore.pyqtSignal())
        print("get_signals:")
        for subcls in cls.mro():
            clsname = f'{subcls.__module__}.{subcls.__name__}'
            for key, value in sorted(vars(subcls).items()):
                if isinstance(value, signal):
                    print(f'{key} [{clsname}]')


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UIsub(MainWindow)
    MainWindow.show()
    
    sys.exit(app.exec_())