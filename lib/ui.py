
import os
import sys
from pathlib import Path

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
        MainWindow.resize(1223, 942)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setGeometry(QtCore.QRect(10, 10, 1201, 861))
        self.tabWidget.setObjectName("tabWidget")
        self.tab = QtWidgets.QWidget()
        self.tab.setObjectName("tab")
        self.widget = FileTreeSelectorDialog(self.tab)
        self.widget.setGeometry(QtCore.QRect(10, 10, 811, 651))
        self.widget.setObjectName("widget")
        self.textBrowser = QtWidgets.QTextBrowser(self.tab)
        self.textBrowser.setGeometry(QtCore.QRect(830, 10, 311, 81))
        self.textBrowser.setObjectName("textBrowser")
        self.tableView = QtWidgets.QTableView(self.tab)
        self.tableView.setGeometry(QtCore.QRect(830, 100, 311, 731))
        self.tableView.setObjectName("tableView")
        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QtWidgets.QWidget()
        self.tab_2.setObjectName("tab_2")
        self.label = QtWidgets.QLabel(self.tab_2)
        self.label.setGeometry(QtCore.QRect(140, 70, 171, 51))
        self.label.setObjectName("label")
        self.tabWidget.addTab(self.tab_2, "")
        self.tab_3 = QtWidgets.QWidget()
        self.tab_3.setObjectName("tab_3")
        self.lineEdit = QtWidgets.QLineEdit(self.tab_3)
        self.lineEdit.setGeometry(QtCore.QRect(10, 10, 631, 371))
        self.lineEdit.setObjectName("lineEdit")
        self.tabWidget.addTab(self.tab_3, "")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1223, 21))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), _translate("MainWindow", "Source"))
        self.label.setText(_translate("MainWindow", "TextLabel"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), _translate("MainWindow", "Experiment"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), _translate("MainWindow", "Measure"))

#######################################################################


# subclassing Ui_MainWindow to be able to use the unaltered output file from pyuic and QT designer
class UIsub(Ui_MainWindow):
    def __init__(self, mainwindow):
        dftest = pd.DataFrame({'path': ['asdfasdf', 'asdfasdf'],
                               'value': [5, 6]})
        super(UIsub, self).__init__()
        self.setupUi(mainwindow)
        print('UIsub init')
        
        # rename for clarity
        self.ftree = self.widget
        
        # I'm guessing that all these signals and slots and connections can be defined in QT designer, and autocoded through pyuic
        # maybe learn more about that later?
        # however, I kinda like the control of putting each of them explicit here and use designer just to get the boxes right visually
        # connecting the same signals we had in original ui test
        self.lineEdit.editingFinished.connect(self.hitEnter)
        self.lineEdit.textChanged.connect(self.changeText)
        
        # this could probably be autonnected
        self.ftree.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)
        self.ftree.model.paths_selected.connect(self.print_paths)
        
        self.tablemodel = TableModel(dftest)
        self.tableView.setModel(self.tablemodel)
        self.tablemodel.dataChanged.connect(self.tableView.update)
        self.tablemodel.dataChanged.connect(self.hellohello) 
        
        # create graph window. This is meant to go in with designer later? and not create in this class
        self.canvas = MplCanvas(width=5, height=4, dpi=100)
        df = pd.DataFrame({'a': [0, 5, 10, 15, 20], 'b': np.random.random(5)})
        df.plot(ax=self.canvas.axes) # plot DataFrame, passing in the matplotlib Canvas axes.

        # Create toolbar, passing canvas as first param, parent (self, the MainWindow) as second.
        self.toolbar_graph = NavigationToolbar(self.canvas)
        self.layout_graph = QtWidgets.QVBoxLayout()
        self.layout_graph.addWidget(self.toolbar_graph)
        self.layout_graph.addWidget(self.canvas)

        # Create a placeholder widget to hold our toolbar and canvas.
        self.widget_graph = QtWidgets.QWidget()
        self.widget_graph.setLayout(self.layout_graph)
        self.widget_graph.show()
        
        # skeleton to update the plots, connect with signal and slot when ready
        # Setup a timer to trigger the redraw by calling update_plot.
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

        # SEABORN TEST
        # testing if our graph window can handle advanced seaborn stuff from the notebook prototypes
        self.canvas_seaborn = MplCanvas(width=5, height=4, dpi=100)
        dfmean = pd.read_csv('dataGenerated/Lactate_2022_abf_11WT_meandata.csv') # import csv
        # sns.lineplot(ax=self.canvas_seaborn.axes)
        dfmean.set_index('time', inplace=True)
        dfmean['voltage'] = dfmean.voltage/dfmean.voltage.abs().max()
        dfmean['prim'] = dfmean.prim/dfmean.prim.abs().max()
        g = sns.lineplot(data=dfmean, y="voltage", x="time", ax=self.canvas_seaborn.axes, color="black")
        h = sns.lineplot(data=dfmean, y="prim", x="time", ax=self.canvas_seaborn.axes, color="red")
        # and so on...
        
        # Create toolbar, passing canvas as first param, parent (self, the MainWindow) as second.
        self.toolbar_graph_seaborn = NavigationToolbar(self.canvas_seaborn)
        self.layout_graph_seaborn = QtWidgets.QVBoxLayout()
        self.layout_graph_seaborn.addWidget(self.toolbar_graph_seaborn)
        self.layout_graph_seaborn.addWidget(self.canvas_seaborn)

        # Create a placeholder widget to hold our toolbar and canvas.
        self.widget_graph_seaborn = QtWidgets.QWidget()
        self.widget_graph_seaborn.setLayout(self.layout_graph_seaborn)
        self.widget_graph_seaborn.show()
        
        
    def update_plot(self):
        # Drop off the first y element, append a new one.
        df = pd.DataFrame({'a': [0, 5, 10, 15, 20], 'b': np.random.random(5)})
        self.canvas.axes.cla()  # Clear the canvas.
        df.plot(ax=self.canvas.axes, x='a', y='b')
        # self.canvas.axes.plot(self.xdata, self.ydata, 'r')
        # Trigger the canvas to update and redraw.
        self.canvas.draw()

    
    def hellohello(self):
        print('hellohello')
        
    
    def hitEnter(self):
        #get_signals(self.children()[1].children()[1].model)
        self.textBrowser.setText(self.lineEdit.text())


    def changeText(self):
        self.label.setText(self.lineEdit.text())
    
    
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
 