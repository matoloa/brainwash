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

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.Hidden | QtCore.QDir.NoDot)
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
            return QtCore.Qt.Checked

    def setData(self, index, value, role):
        if (role == QtCore.Qt.CheckStateRole and index.column() == 0):
            self.checks[index] = value
            print('setData(): {}'.format(value))
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


#   def SelectionChanged(self):
#   self.
    
      # Change Text from other project
#    self.edit.textChanged.connect(self.changeText)
    

class FileTreeSelectorDialog(QtWidgets.QWidget):
    def __init__(self, root_path='/'):
        super().__init__()

        self.root_path      = root_path

        # Widget
        self.title          = "Not supposed to be a separate window!"
        self.left           = 50
        self.top            = 50
        self.width          = 1080
        self.height         = 640

        self.setWindowTitle(self.title)         #TODO:  Whilch title?
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Model
        self.model          = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # View
        self.view           = QtWidgets.QTreeView()

        self.view.setObjectName('treeView_fileTreeSelector')
        self.view.setWindowTitle("Dir View")    #TODO:  Which title?
        self.view.setAnimated(False)
        self.view.setIndentation(20)
        self.view.setSortingEnabled(True)
        self.view.setColumnWidth(0,150)
        self.view.resize(1080, 640)

        # Attach Model to View
        self.view.setModel(self.model)
        self.view.setRootIndex(self.model.parent_index)

        # Misc
        self.node_stack     = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(self.view)
        self.setLayout(windowlayout)

        QtCore.QMetaObject.connectSlotsByName(self)

        self.show()

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_treeView_fileTreeSelector_clicked(self, index):
        print('tree clicked: {}'.format(self.model.filePath(index)))
        self.model.traverseDirectory(index, callback=self.model.printIndex)


def FileTreeSelectorDialogStripped(widget, root_path='/'):        
        widget.root_path      = root_path
                
        # Model
        widget.model          = FileTreeSelectorModel(root_path=widget.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # View
        widget.view = QtWidgets.QTreeView()

        widget.view.setObjectName('treeView_fileTreeSelector')
        widget.view.setWindowTitle("Dir View")    #TODO:  Which title?
        widget.view.setAnimated(False)
        widget.view.setIndentation(20)
        widget.view.setSortingEnabled(True)
        widget.view.setColumnWidth(0,300)
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

        QtCore.QMetaObject.connectSlotsByName(widget)

        widget.show()

    #@QtCore.pyqtSlot(QtCore.QModelIndex)
    
def on_treeView_fileTreeSelector_clicked(self, index):
    print('tree clicked: {}'.format(self.model.filePath(index)))
    self.label.setText("Clicked")
    self.model.traverseDirectory(index, callback=self.model.printIndex)


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

        #print(self.children()[1].children()[3].metaObject())
        print(self.children()[1].children()[1].__dict__)
        print("0", self.children()[1].children()[0])
        print("1", self.children()[1].children()[1])
        print("2", self.children()[1].children()[2])
        print("3", self.children()[1].children()[3])


        # Clicked Filetree
        #self.widget.on_treeView_fileTreeSelector_clicked(self.)

        # Hit Enter
        self.edit.editingFinished.connect(self.hitEnter)

        # Change Text
        self.edit.textChanged.connect(self.changeText)

        # Placeholder update label instruction
        self.label.setText("The label text")
        
        self.widget.view.clicked.connect(self.ftree_clicked) # this worked to find the signal that finds if the ftree was clicked

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
        print("Dumdumdum")
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