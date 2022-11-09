
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
        print(paths)
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
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(783, 592)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.inputProjectName = QtWidgets.QLineEdit(self.centralwidget)
        self.inputProjectName.setGeometry(QtCore.QRect(10, 10, 191, 22))
        self.inputProjectName.setObjectName("inputProjectName")
        self.pushButtonAddData = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonAddData.setGeometry(QtCore.QRect(310, 10, 71, 24))
        self.pushButtonAddData.setObjectName("pushButtonAddData")
        self.pushButtonOpenProject = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonOpenProject.setEnabled(False)
        self.pushButtonOpenProject.setGeometry(QtCore.QRect(210, 10, 91, 24))
        self.pushButtonOpenProject.setObjectName("pushButtonOpenProject")
        self.tableMaster = QtWidgets.QTableView(self.centralwidget)
        self.tableMaster.setGeometry(QtCore.QRect(10, 40, 371, 511))
        self.tableMaster.setObjectName("tableMaster")
        self.labelMetadata = QtWidgets.QLabel(self.centralwidget)
        self.labelMetadata.setGeometry(QtCore.QRect(390, 470, 141, 16))
        self.labelMetadata.setObjectName("labelMetadata")
        self.pushButtonSelect = QtWidgets.QPushButton(self.centralwidget)
        self.pushButtonSelect.setGeometry(QtCore.QRect(720, 10, 51, 24))
        self.pushButtonSelect.setObjectName("pushButtonSelect")
        self.checkPreview = QtWidgets.QCheckBox(self.centralwidget)
        self.checkPreview.setGeometry(QtCore.QRect(630, 10, 77, 21))
        self.checkPreview.setObjectName("checkPreview")
        self.graphData = QtWidgets.QWidget(self.centralwidget)
        self.graphData.setGeometry(QtCore.QRect(390, 40, 381, 191))
        self.graphData.setObjectName("graphData")
        self.graphOutput = QtWidgets.QWidget(self.centralwidget)
        self.graphOutput.setGeometry(QtCore.QRect(390, 260, 381, 201))
        self.graphOutput.setObjectName("graphOutput")
        self.labelMeanGroups = QtWidgets.QLabel(self.centralwidget)
        self.labelMeanGroups.setGeometry(QtCore.QRect(390, 240, 141, 16))
        self.labelMeanGroups.setObjectName("labelMeanGroups")
        self.labelMeanSweep = QtWidgets.QLabel(self.centralwidget)
        self.labelMeanSweep.setGeometry(QtCore.QRect(390, 20, 141, 16))
        self.labelMeanSweep.setObjectName("labelMeanSweep")
        self.tableMetadata = QtWidgets.QTableView(self.centralwidget)
        self.tableMetadata.setGeometry(QtCore.QRect(390, 490, 381, 61))
        self.tableMetadata.setObjectName("tableMetadata")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 783, 21))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Brainwash 0.1"))
        self.inputProjectName.setText(_translate("MainWindow", "placeholder project name"))
        self.pushButtonAddData.setText(_translate("MainWindow", "Add data"))
        self.pushButtonOpenProject.setText(_translate("MainWindow", "Open project"))
        self.labelMetadata.setText(_translate("MainWindow", "Metadata:"))
        self.pushButtonSelect.setText(_translate("MainWindow", "select"))
        self.checkPreview.setText(_translate("MainWindow", "Preview"))
        self.labelMeanGroups.setText(_translate("MainWindow", "Mean Groups:"))
        self.labelMeanSweep.setText(_translate("MainWindow", "Mean Sweep:"))


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

        self.buttonBoxAddGroup = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBoxAddGroup.setGeometry(QtCore.QRect(470, 20, 91, 491))
        self.buttonBoxAddGroup.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.buttonBoxAddGroup.setOrientation(QtCore.Qt.Vertical)
        self.buttonBoxAddGroup.setStandardButtons(QtWidgets.QDialogButtonBox.NoButton)
        self.buttonBoxAddGroup.setObjectName("buttonBoxAddGroup")
        # Consider UI for easy renaming and removing
        # Manually added (unconnected) default group buttons
        # Eventually, these must be populated from masterTable group names
        self.buttonBoxAddGroup.groupcontrol = QtWidgets.QPushButton(self.tr("&Control"))
        self.buttonBoxAddGroup.groupintervention = QtWidgets.QPushButton(self.tr("&Intervention"))
        self.buttonBoxAddGroup.newGroup = QtWidgets.QPushButton(self.tr("&New group"))
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.groupcontrol, QtWidgets.QDialogButtonBox.ActionRole)
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.groupintervention, QtWidgets.QDialogButtonBox.ActionRole)
        self.buttonBoxAddGroup.addButton(self.buttonBoxAddGroup.newGroup, QtWidgets.QDialogButtonBox.ActionRole)

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
#        dftest = pd.DataFrame({'path': ['asdfasdf', 'asdfasdf'],
#                               'value': [5, 6]})
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)
        print('UIsub init')
       
        # rename for clarity
        
        # I'm guessing that all these signals and slots and connections can be defined in QT designer, and autocoded through pyuic
        # maybe learn more about that later?
        # however, I kinda like the control of putting each of them explicit here and use designer just to get the boxes right visually
        # connecting the same signals we had in original ui test
        self.inputProjectName.editingFinished.connect(self.setProjectname)
        self.pushButtonAddData.pressed.connect(self.pushedButtonAddData)
        self.pushButtonSelect.pressed.connect(self.addData)


    def pushedButtonAddData(self):
        # creates file tree for file selection
        self.dialog = QtWidgets.QDialog()
        self.ftree = Filetreesub(self.dialog)
        self.dialog.show()
        

    def addData(self): # TODO move contents to correct place, trigger from ftree buttonBox.accepted
        print('addData')
        # create placeholder dataframes
        dfMaster = pd.DataFrame({'rigID': ['computer 0'], 'path': ['C:/new folder(4)/braindamage/pre-test'], 'checksum': ['biggest number'], 'name': ['Zero test'], 'group': ['pilot'], 'groupRGB': ['255,0,0'], 'parsetimestamp': ['2022-04-05'], 'nSweeps': [720], 'measurements': ['(dict of coordinates)'], 'exclude': [False], 'comment': ['recorded sideways']})
        dfAdd = pd.DataFrame({'rigID': ['computer 1', 'computer 58'], 'path': ['C:/copy of new folder(4)/braindamage/second test', 'F:/404/braindamage/sillySubfolder/first test'], 'checksum': ['big number', 'arbitrary number'], 'name': ['first test', 'second test'], 'group': ['pilot', 'pilot']})
        # .append is deprecated; switching to pd.concat
        dfMaster = pd.concat([dfMaster, dfAdd])
        print(dfMaster)


    def setGraph(self):
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
        #self.textBrowser.setText(self.inputProjectName.text())
        print(f"setProjectName: {self}")


    def changeText(self):
        self.label.setText(self.inputProjectName.text())
    
    
    def setTableDf(self, data):
        self.tablemodel.setData(data)
        self.tableView.update()

    
    @QtCore.pyqtSlot(list)
    def print_paths(self, mypaths):
        print(f'mystr: {mypaths}')
        strmystr = "\n".join(sorted(['/'.join(i.split('/')[-2:]) for i in mypaths]))
        self.textBrowser.setText(strmystr)
        list_display_names = ['/'.join(i.split('/')[-2:]) for i in mypaths]
        dftable = pd.DataFrame({'path_source': mypaths, 'name': list_display_names})
        self.setTableDf(dftable)


class Filetreesub(Ui_Dialog):
    def __init__(self, dialog):
#        dftest = pd.DataFrame({'path': ['asdfasdf', 'asdfasdf'],
#                               'value': [5, 6]})
        super(Filetreesub, self).__init__()
        self.setupUi(dialog)

        print('Filetreesub init')
        self.ftree = self.widget
        self.ftree.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)
#       self.ftree.model.paths_selected.connect(self.print_paths)
        

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
 

