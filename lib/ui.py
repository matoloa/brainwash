
from csv import Dialect
import os
import sys
from pathlib import Path
from tkinter import dialog

import matplotlib
import seaborn as sns

matplotlib.use('Qt5Agg')

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtGui, QtWidgets, uic

dir_project_root = Path(os.getcwd().split("quiwip")[0])

debug = False


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data=None):
        super(TableModel, self).__init__()
        self._data = data


    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)


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
        self.debug = debug
        self.checks         = {}
        self.nodestack      = []
        self.parent_index   = self.setRootPath(self.root_path)
        self.root_index     = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot)
        self.sort(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.directoryLoaded.connect(self._loaded)


    def _loaded(self, path):
        print('_loaded', self.root_path, self.rowCount(self.parent_index))


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
            # print('setData(): {}'.format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)


    def traverseDirectory(self, parentindex, callback=None):
        if debug: print('traverseDirectory():')
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
        self.root_path      = root_path

        # Model
        self.model          = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # View
        self.view           = QtWidgets.QTreeView()

        self.view.setObjectName('treeView_fileTreeSelector')
        self.view.setWindowTitle("Dir View")    #TODO:  Which title?


        self.view.setSortingEnabled(False)
        #self.view.resize(1080, 600)

        # Attach Model to View
        self.view.setModel(self.model)
        self.view.setRootIndex(self.model.parent_index)
        self.view.setAnimated(False)
        self.view.setIndentation(20)
        self.view.setColumnHidden(3, True)
        self.view.setColumnWidth(0, 250)
        self.view.setColumnWidth(1, 100)
        self.view.setColumnWidth(2, 50)

        
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
        mainWindow.resize(394, 432)
        self.centralwidget = QtWidgets.QWidget(mainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayoutCentralwidget = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayoutCentralwidget.setObjectName("horizontalLayoutCentralwidget")
        self.verticalLayoutProj = QtWidgets.QVBoxLayout()
        self.verticalLayoutProj.setObjectName("verticalLayoutProj")
        self.horizontalLayoutProj = QtWidgets.QHBoxLayout()
        self.horizontalLayoutProj.setObjectName("horizontalLayoutProj")
        self.inputProjectName = QtWidgets.QLineEdit(self.centralwidget)
        self.inputProjectName.setObjectName("inputProjectName")
        self.horizontalLayoutProj.addWidget(self.inputProjectName)
        self.pushButtonOpenProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonOpenProject.setEnabled(False)
        self.pushButtonOpenProject.setObjectName("pushButtonOpenProject")
        self.horizontalLayoutProj.addWidget(self.pushButtonOpenProject)
        self.pushButtonAddData = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonAddData.setObjectName("pushButtonAddData")
        self.horizontalLayoutProj.addWidget(self.pushButtonAddData)
        self.verticalLayoutProj.addLayout(self.horizontalLayoutProj)
        self.tableProj = QtWidgets.QTableView(self.centralwidget)
        self.tableProj.setObjectName("tableProj")
        self.verticalLayoutProj.addWidget(self.tableProj)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalLayoutProj)
        self.verticalLayoutGraph = QtWidgets.QVBoxLayout()
        self.verticalLayoutGraph.setObjectName("verticalLayoutGraph")
        self.horizontalLayoutGraph = QtWidgets.QHBoxLayout()
        self.horizontalLayoutGraph.setObjectName("horizontalLayoutGraph")
        self.pushButtonSelect = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonSelect.setObjectName("pushButtonSelect")
        self.horizontalLayoutGraph.addWidget(self.pushButtonSelect)
        self.checkPreview = QtWidgets.QCheckBox(self.centralwidget)
        self.checkPreview.setObjectName("checkPreview")
        self.horizontalLayoutGraph.addWidget(self.checkPreview)
        self.verticalLayoutGraph.addLayout(self.horizontalLayoutGraph)
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
        self.verticalLayoutGraph.setStretch(2, 5)
        self.verticalLayoutGraph.setStretch(4, 5)
        self.verticalLayoutGraph.setStretch(6, 1)
        self.horizontalLayoutCentralwidget.addLayout(self.verticalLayoutGraph)
        mainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(mainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 394, 21))
        self.menubar.setObjectName("menubar")
        mainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(mainWindow)
        self.statusbar.setObjectName("statusbar")
        mainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(mainWindow)
        QtCore.QMetaObject.connectSlotsByName(mainWindow)


    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash 0.2"))
        self.inputProjectName.setText(_translate("mainWindow", "placeholder project name"))
        self.pushButtonOpenProject.setText(_translate("mainWindow", "Open project"))
        self.pushButtonAddData.setText(_translate("mainWindow", "Add data"))
        self.pushButtonSelect.setText(_translate("mainWindow", "select"))
        self.checkPreview.setText(_translate("mainWindow", "Preview"))
        self.labelMeanSweep.setText(_translate("mainWindow", "Mean Sweep:"))
        self.labelMeanGroups.setText(_translate("mainWindow", "Mean Groups:"))
        self.labelMetadata.setText(_translate("mainWindow", "Metadata:"))


    def retranslateUi(self, mainWindow):
        _translate = QtCore.QCoreApplication.translate
        mainWindow.setWindowTitle(_translate("mainWindow", "Brainwash 0.2"))
        self.inputProjectName.setText(_translate("mainWindow", "placeholder project name"))
        self.pushButtonOpenProject.setText(_translate("mainWindow", "Open project"))
        self.pushButtonAddData.setText(_translate("mainWindow", "Add data"))
        self.pushButtonSelect.setText(_translate("mainWindow", "select"))
        self.checkPreview.setText(_translate("mainWindow", "Preview"))
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
        print('UIsub init') # rename for clarity

        # TODO: Placeholder project dataframe
        self.dfProj = pd.DataFrame(columns=['host', 'path', 'checksum', 'name', 'group', 'groupRGB', 'parsetimestamp', 'nSweeps', 'measurements', 'exclude', 'comment'])
        #self.dfProj = pd.DataFrame({'host': ['computer 0'], 'path': ['C:/new folder(4)/braindamage/pre-test'], 'checksum': ['biggest number'], 'name': ['Zero test'], 'group': ['pilot'], 'groupRGB': ['255,0,0'], 'parsetimestamp': ['2022-04-05'], 'nSweeps': [720], 'measurements': ['(dict of coordinates)'], 'exclude': [False], 'comment': ['recorded sideways']})

        self.project = "default" # a folder in project_root
        self.projectfolder = self.getProjectFolder() / self.project

        # I'm guessing that all these signals and slots and connections can be defined in QT designer, and autocoded through pyuic
        # maybe learn more about that later?
        # however, I kinda like the control of putting each of them explicit here and use designer just to get the boxes right visually
        # connecting the same signals we had in original ui test

        self.inputProjectName.editingFinished.connect(self.setProjectname)
        self.pushButtonAddData.pressed.connect(self.pushedButtonAddData)

        # show dfProj in tableProj - TODO: Doesn't work!
        self.tablemodel = TableModel(self.dfProj)
        self.tableProj.setModel(self.tablemodel)
        self.setTableDf(self.dfProj)

        #self.tablemodel.setData(self.dfProj)
        #self.tableProj.update()

        # place current project as folder in project_root, lock project name for now
        # self.projectfolder = self.project_root / self.project


    def getProjectFolder(self):
        # Find projectFolderLocation.txt in brainwash folder, or create a default one. Return Project Folder (Path).
        repo_root = Path(os.getcwd()) # path to brainwash directory
        self.projectLocationPath = repo_root / 'projectFolderLocation.txt'
        # open projectFolderLocation.txt; if it exists, use contents for self.projectLocation
        if os.path.exists(self.projectLocationPath):
            with open(self.projectLocationPath, 'r') as f:
                self.project_root = Path(f.readline())
        else: # file does not exist or is empty: assign default path to brainwash projects
            self.project_root = Path(os.path.expanduser('~/Documents/brainwash projects'))
            with open(self.projectLocationPath, 'w+') as f:
                f.writelines(str(self.project_root))
        return self.project_root


    def pushedButtonAddData(self):
        # creates file tree for file selection
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog, parent=self)
        self.dialog.show()
        

    def getdfProj(self):
        return self.dfProj


    def setdfProj(self, df):
        self.dfProj = df


    def setGraph(self):
        #defunct, except on Jonathan's laptop
        print('setGraph')
        dfmean = pd.read_csv('/home/jonathan/code/brainwash/dataGenerated/metaData/2022_01_24_0020.csv') # import csv
        self.canvas_seaborn = MplCanvas(parent=self.graphView)  # instantiate canvas
        dfmean.set_index('t0', inplace=True)
        dfmean['slope'] = dfmean.slope/dfmean.slope.abs().max()
        dfmean['sweep'] = dfmean.sweep/dfmean.sweep.abs().max()
        g = sns.lineplot(data=dfmean, y="slope", x="t0", ax=self.canvas_seaborn.axes, color="black")
        h = sns.lineplot(data=dfmean, y="sweep", x="t0", ax=self.canvas_seaborn.axes, color="red")
        self.canvas_seaborn.draw()
        self.canvas_seaborn.show()

    
    def setProjectname(self):
        #get_signals(self.children()[1].children()[1].model)
        self.project = self.inputProjectName.text()
        self.projectfolder = self.project_root / self.project
        if not os.path.exists(self.projectfolder):
            os.makedirs(self.projectfolder)
        print (os.path.exists(self.projectfolder))

    
    def setTableDf(self, data):
        self.tablemodel.setData(data)
        #format table TODO: Break out to separate function
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
        self.tableProj.update()


    def addData(self, dfAdd): # concatinate dataframes of old and new data
        #print('addData')
        dfProj = self.getdfProj()
        dfProj = pd.concat([dfProj, dfAdd]) # .append is deprecated; using pd.concat
        dfProj.reset_index(drop=True, inplace=True)
        self.setdfProj(dfProj)
        #print(self.getdfProj())
        self.setTableDf(dfProj)

    
    @QtCore.pyqtSlot(list)
    def slotPrintPaths(self, mypaths):
        print(f'mystr: {mypaths}')
        strmystr = "\n".join(sorted(['/'.join(i.split('/')[-2:]) for i in mypaths]))
        self.textBrowser.setText(strmystr)
        list_display_names = ['/'.join(i.split('/')[-2:]) for i in mypaths]
        dftable = pd.DataFrame({'path_source': mypaths, 'name': list_display_names})
        self.setTableDf(dftable)


    @QtCore.pyqtSlot(list, list, list, list, list)
    def slotAddData(self, host0, path1, checksum2, name3, group4):
        #Reconstructs dataframe after passing it through pyqt signaling as lists
        #print("slotAddData")
        dfAdd = pd.DataFrame({"host": host0, "path": path1, "checksum": checksum2, "name": name3, "group": group4})
        self.addData(dfAdd)

        
    @QtCore.pyqtSlot()
    def slotAddDfData(self, df):
        self.addData(df)


class Filetreesub(Ui_Dialog):
    signalAddData = QtCore.pyqtSignal(list, list, list, list, list)

    def __init__(self, dialog, parent=None):
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)
        self.parent = parent

        print('Filetreesub init')
    
        self.ftree = self.widget

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

        self.signalAddData.connect(parent.slotAddData)

        self.tablemodel = TableModel(self.dfAdd)
        self.tableView.setModel(self.tablemodel)


    def addDf(self):
        self.parent.slotAddDfData(self.dfAdd)
        
    
    def pathsSelectedUpdateTable(self, paths):
        # TODO: Extract host, checksum, group
        dfAdd = pd.DataFrame({"host": 'computer 1', "path": paths, 'checksum': 'big number', 'name': paths, 'group': None})
        self.tablemodel.setData(dfAdd)
        # NTH: more intelligent default naming; lowest level unique name?
        # For now, use name + lowest level folder
        names = []
        for i in paths:
            names.append(os.path.basename(os.path.dirname(i)) + '_' + os.path.basename(i))
        dfAdd["name"] = names
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