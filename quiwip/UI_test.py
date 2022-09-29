#%%con
# file tree selector
import sys
import os
from pathlib import Path
from PyQt5 import QtWidgets, uic, QtCore, QtGui


dir_project_root = Path(os.getcwd().split("quiwip")[0])

class FileTreeSelectorModel(QtWidgets.QFileSystemModel): #Should be paired with a FileTreeSelectorView
    def __init__(self, parent=None, root_path='/'):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.root_path      = root_path
        self.checks         = {}
        self.nodestack      = []
        self.parent_index   = self.setRootPath(self.root_path)
        self.root_index     = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.Hidden | QtCore.QDir.NoDotAndDotDot)
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
        str_paths = []
        for k, v in self.checks.items():
            if (v == 2): # Checked
                str_paths.append(format(self.filePath(k)))
        print(str_paths)
        # Emit SIGNAL/event
        
        #self.textBrowser.setText(str_paths)

    def setData(self, index, value, role):
        if (role == QtCore.Qt.CheckStateRole and index.column() == 0):
            self.checks[index] = value
            # print('setData(): {}'.format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def traverseDirectory(self, parentindex, callback=None):
        print('traverseDirectory():')
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


def FileTreeSelectorDialogStripped(widget, root_path='/'):        
        widget.root_path      = root_path
                
        # Model
        widget.model          = FileTreeSelectorModel(root_path=widget.root_path)

        # View
        widget.view = QtWidgets.QTreeView()

        widget.view.setObjectName('treeView_fileTreeSelector')
        widget.view.setWindowTitle("Dir View")    #TODO:  Which title?
        widget.view.setAnimated(False)
        widget.view.setIndentation(20)
        widget.view.setSortingEnabled(True)
        widget.view.setColumnWidth(0, 150)
        widget.view.resize(1080, 600)

        # Attach Model to View
        widget.view.setModel(widget.model)
        widget.view.setRootIndex(widget.model.parent_index)

        # Misc
        widget.node_stack     = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(widget.view)
        widget.setLayout(windowlayout)

        #QtCore.QMetaObject.connectSlotsByName(widget)

        widget.show()

def on_treeView_fileTreeSelector_clicked(self, index):
    self.model.getCheckedPaths()


QtWidgets.QWidget.on_treeView_fileTreeSelector_clicked = on_treeView_fileTreeSelector_clicked

class UI(QtWidgets.QMainWindow):
    def __init__(self):
        super(UI, self).__init__()
        # Load interface and main window
        uic.loadUi(dir_project_root / "quiwip" / "textandtree.ui", self)

        # Define our widgets
        self.edit = self.findChild(QtWidgets.QLineEdit, "lineEdit")
        self.label = self.findChild(QtWidgets.QLabel, "label")
        self.widget = self.findChild(QtWidgets.QWidget, "widget")
        
        # create the file tree thingie
        self.ftree = FileTreeSelectorDialogStripped(widget=self.widget, 
                                                    root_path=str(dir_project_root / "dataSource")) # dir as str because QT seems to not support pathlib
        # create the file tree thingie
        self.widget.view.clicked.connect(self.widget.on_treeView_fileTreeSelector_clicked)

        # Hit Enter
        self.edit.editingFinished.connect(self.hitEnter)

        # Change Text
        self.edit.textChanged.connect(self.changeText)
        
        # SLOT - listen for SIGNAL from getCheckedPaths
        
        self.show()

    def ftree_clicked(self): # now working
        print("clicked")
        
    def hitEnter(self):
        get_signals(self.children()[1].children()[1].model)
        self.textBrowser.setText(self.edit.text())

    def changeText(self):
        self.label.setText(self.edit.text())


def get_signals(source):
        cls = source if isinstance(source, type) else type(source)
        signal = type(QtCore.pyqtSignal())
        print("get_signals:")
        for subcls in cls.mro():
            clsname = f'{subcls.__module__}.{subcls.__name__}'
            for key, value in sorted(vars(subcls).items()):
                if isinstance(value, signal):
                    print(f'{key} [{clsname}]')


# %%
app = QtWidgets.QApplication(sys.argv)

UIWindow = UI()
#app.allWidgets()


sys.exit(app.exec_())
# %%
print(os.getcwd())
# %%