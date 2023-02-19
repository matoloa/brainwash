# %%
from csv import Dialect
import os
import sys
from pathlib import Path
from tkinter import dialog
import yaml

import matplotlib
import seaborn as sns

matplotlib.use('Qt5Agg')

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtGui, QtWidgets, uic

import parse

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
##### trying to make all the rest work with it                     #####
##### WARNING: I was forced to change the parent class from        #####
##### 'object' to 'QtCore.QObject' for the pyqtSlot(list) to work  #####
########################################################################


class Ui_MainWindow(QtCore.QObject):
    def setupUi(self, mainWindow):
        mainWindow.setObjectName("mainWindow")
        mainWindow.resize(923, 957)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName("horizontalLayoutCentralwidget")
        self.verticalLayoutProj = QtWidgets.QVBoxLayout()
        self.verticalLayoutProj.setObjectName("verticalLayoutProj")
        self.horizontalLayoutProj = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProj.setObjectName("horizontalLayoutProj")
        self.inputProjectName = QtWidgets.QLineEdit(self.centralwidget)
        self.inputProjectName.setMinimumSize(QtCore.QSize(150, 0))
        self.inputProjectName.setObjectName("inputProjectName")
        self.horizontalLayoutProj.addWidget(self.inputProjectName)
        self.pushButtonRenameProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonRenameProject.setObjectName("pushButtonRenameProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonRenameProject)
        self.pushButtonNewProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonNewProject.setObjectName("pushButtonNewProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonNewProject)
        self.pushButtonOpenProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonOpenProject.setEnabled(True)
        self.pushButtonOpenProject.setObjectName("pushButtonOpenProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonOpenProject)
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
        self.verticalLayoutProj.addLayout(self.horizontalLayoutData)
        self.tableProj = QtWidgets.QTableView(self.centralwidget)
        self.tableProj.setObjectName("tableProj")
        self.verticalLayoutProj.addWidget(self.tableProj)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalLayoutProj)
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
        self.menubar.setGeometry(QtCore.QRect(0, 0, 923, 21))
        self.menubar.setObjectName("menubar")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)

    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash 0.3"))
        self.inputProjectName.setText(_translate("mainWindow", "My Project"))
        self.pushButtonRenameProject.setText(_translate("mainWindow", "Rename"))
        self.pushButtonNewProject.setText(_translate("mainWindow", "New"))
        self.pushButtonOpenProject.setText(_translate("mainWindow", "Open"))
        self.pushButtonAddData.setText(_translate("mainWindow", "Add data"))
        self.pushButtonParse.setText(_translate("mainWindow", "Import"))
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


# subclassing Ui_MainWindow to be able to use the unaltered output file from pyuic and QT designer
class UIsub(Ui_MainWindow):
    def __init__(self, mainwindow):
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)
        if verbose: print(' - UIsub init, verbose mode') # rename for clarity

        # load cfg if present, create if not existing
        paths = [Path.cwd()] + list(Path.cwd().parents)
        self.repo_root = [i for i in paths if (-1 < str(i).find('brainwash')) & (str(i).find('src') == -1)][0] # path to brainwash directory
        self.cfg_yaml = self.repo_root / 'cfg.yaml'
        if self.cfg_yaml.exists():
            with self.cfg_yaml.open('r') as file:
                cfg = yaml.safe_load(file)
                self.user_documents = Path(cfg['user_documents']) # Where to look for raw data
                self.projects_folder = Path(cfg['projects_folder']) # Where to save and read parsed data
        else:
            self.user_documents = Path.home() / 'Documents' # Where to look for raw data
            self.projects_folder = self.user_documents / 'Brainwash Projects' # Where to save and read parsed data
            cfg = {
                'user_documents': str(self.user_documents),
                'projects_folder': str(self.projects_folder),
            }
            with self.cfg_yaml.open('w+') as file:
                yaml.safe_dump(cfg, file)
        
        if not os.path.exists(self.projects_folder):
            os.makedirs(self.projects_folder)
        
        self.projectdf = pd.DataFrame(columns=['host', 'path', 'checksum', 'save_file_name', 'group', 'groupRGB', 'parsetimestamp', 'nSweeps', 'measurements', 'exclude', 'comment'])
        # Placeholder project dataframe
        # self.projectdf = pd.DataFrame({'host': ['computer 0'], 'path': ['C:/new folder(4)/braindamage/pre-test'], 'checksum': ['biggest number'], 'save_file_name': ['Zero test'], 'group': ['pilot'], 'groupRGB': ['255,0,0'], 'parsetimestamp': ['2022-04-05'], 'nSweeps': [720], 'measurements': ['(dict of coordinates)'], 'exclude': [False], 'comment': ['recorded sideways']})

        self.projectname = "default" # a folder in project_root
        self.projectfolder = self.projects_folder / self.projectname

        # I'm guessing that all these signals and slots and connections can be defined in QT designer, and autocoded through pyuic
        # maybe learn more about that later?
        # however, I kinda like the control of putting each of them explicit here and use designer just to get the boxes right visually
        # connecting the same signals we had in original ui test

        self.inputProjectName.editingFinished.connect(self.setProjectname)
        self.pushButtonOpenProject.pressed.connect(self.pushedButtonOpenProject)
        self.pushButtonAddData.pressed.connect(self.pushedButtonAddData)
        self.pushButtonParse.pressed.connect(self.pushedButtonParse)
        self.pushButtonSelect.pressed.connect(self.pushedButtonSelect)

        # show dfProj in tableProj
        self.tablemodel = TableModel(self.projectdf)
        self.tableProj.setModel(self.tablemodel)
        self.setTableDf(self.projectdf)

        self.tableProj.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        #self.tableProj.setSelectionMode(QTableView.SingleSelection)

        selection_model = self.tableProj.selectionModel()
        #selection_model.selectionChanged.connect(lambda x: print(self.tablemodel.dataRow(x.indexes()[0])))
        selection_model.selectionChanged.connect(self.tableProjSelectionChanged)

        #self.tablemodel.setData(self.projectdf)
        #self.tableProj.update()

        # place current project as folder in project_root, lock project name for now
        # self.projectfolder = self.project_root / self.project


    def tableProjSelectionChanged(self, single_index_range):
        # TODO: handle list index out of range 
        print(f"single_index_range: {single_index_range.indexes()}")
        if 0 < len(single_index_range.indexes()):
            single_index = single_index_range.indexes()[0]
            print(single_index)
            table_row = self.tablemodel.dataRow(single_index)
            print(table_row)
            self.setGraph(table_row[3]) # Passing along save_file_name
    
    
    def pushedButtonOpenProject(self):
        # open folder selector dialog
        self.dialog = QtWidgets.QDialog()
        projectfolder = QtWidgets.QFileDialog.getExistingDirectory(self.dialog, "Open Directory", str(self.projects_folder), 
                                                            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks)
        self.projectfolder = Path(projectfolder)
        self.load_dfproj()


    def pushedButtonAddData(self):
        # creates file tree for file selection
        if verbose: print("pushedButtonAddData")
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self, folder=self.user_documents)
        self.dialog.show()


    def pushedButtonSelect(self):
        # Placeholder; this is later meant to open a dialog to specify what aspects of the data are to be displayed in the graphs        
        # if verbose:
        print("pushedButtonSelect")


    def pushedButtonParse(self):
        # parse non-parsed files and folders in self.projectdf
        if verbose: print("pushedButtonParse")
        parse.parseProjFiles(self.projectfolder, self.projectdf)
        

    def getdfProj(self):
        return self.projectdf


    def load_dfproj(self):
        self.projectdf = pd.read_csv(str(self.projectfolder / "project.brainwash"))
        self.setTableDf(self.projectdf)  # set dfproj to table
        self.inputProjectName.setText(self.projectfolder.stem)  # set foler name to proj name
        if verbose: print(f"loaded project df: {self.projectdf}")
        self.clear_graph()      


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
        # dipslay SELECTED from tableProj at graphMean

        if verbose: print('setGraph')
        dfmean_path = self.projectfolder / (save_file_name + "_mean.csv")
        print(dfmean_path)
        dfmean = pd.read_csv(dfmean_path) # import csv
        print(dfmean)
        # dfmean = pd.read_csv('/home/jonathan/code/brainwash/dataGenerated/metaData/2022_01_24_0020.csv') # import csv
        self.canvas_seaborn = MplCanvas(parent=self.graphMean)  # instantiate canvas
        dfmean.reset_index(inplace=True)
        dfmean['voltage'] = dfmean.voltage / dfmean.voltage.abs().max()
        dfmean['prim'] = dfmean.prim / dfmean.prim.abs().max()
        dfmean['bis'] = dfmean.bis / dfmean.bis.abs().max()
        g = sns.lineplot(data=dfmean, y="voltage", x="index", ax=self.canvas_seaborn.axes, color="black")
        h = sns.lineplot(data=dfmean, y="prim", x="index", ax=self.canvas_seaborn.axes, color="red")
        i = sns.lineplot(data=dfmean, y="bis", x="index", ax=self.canvas_seaborn.axes, color="green")
        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()

#        dfmean.set_index('t0', inplace=True)
#        dfmean['slope'] = dfmean.slope / dfmean.slope.abs().max()
#        dfmean['sweep'] = dfmean.sweep / dfmean.sweep.abs().max()
#        g = sns.lineplot(data=dfmean, y="slope", x="t0", ax=self.canvas_seaborn.axes, color="black")
#        h = sns.lineplot(data=dfmean, y="sweep", x="t0", ax=self.canvas_seaborn.axes, color="red")
#        self.canvas_seaborn.draw()
#        self.canvas_seaborn.show()

    
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
        self.tableProj.setColumnHidden(0, True) #host
        self.tableProj.setColumnHidden(1, True) #path
        self.tableProj.setColumnHidden(2, True) #checksum
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents) #name
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents) #group
        self.tableProj.setColumnHidden(5, True) #rgb
        self.tableProj.setColumnHidden(6, True) #timestamp (of parsing)
        self.tableProj.setColumnHidden(7, False) #nSweeps
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)
        self.tableProj.setColumnHidden(8, True) #measurements
        self.tableProj.setColumnHidden(9, True) #exclude
        self.tableProj.setColumnHidden(10, True) #comments


    def addData(self, dfAdd): # concatinate dataframes of old and new data
        dfProj = self.getdfProj()
        dfProj = pd.concat([dfProj, dfAdd]) # .append is deprecated; using pd.concat
        dfProj.reset_index(drop=True, inplace=True)
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
        self.dfAdd = pd.DataFrame()
        
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
        dfAdd = pd.DataFrame({"host": 'computer 1', "path": paths, 'checksum': 'big number', 'save_file_name': paths, 'group': None})
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