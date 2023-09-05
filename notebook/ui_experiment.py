```python
"""
Useful links:
    https://wiki.qt.io/New_Signal_Slot_Syntax
    https://doc.qt.io/qtforpython/overviews/qtwidgets-tutorials-widgets-windowlayout-example.html#widgets-tutorial-using-layouts
    https://realpython.com/qt-designer-python/#installing-and-running-qt-designer
    https://www.pythonfixing.com/2021/10/fixed-qfilesystemmodel-qtreeview.html
    https://www.youtube.com/watch?v=gg5TepTc2Jg
    https://youtu.be/t7JZo2xbb8I?t=29
"""
```

```python
import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets, uic

```

```python
"""app = QtWidgets.QApplication(sys.argv)

window = uic.loadUi("../quiwip/testtext.ui")
window.show()
app.exec()"""
```

```python
# Copy for toying
"""app = QtWidgets.QApplication(sys.argv)

window = uic.loadUi("../quiwip/testtext.ui")
window.show()
app.exec()"""
```

```python
"""from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QMainWindow,
    QMenuBar, QSizePolicy, QStatusBar, QTextBrowser,
    QWidget)
"""
class UI(QtWidgets.QMainWindow):
    def __init__(self):
        super(UI, self).__init__()
        
        # Load the ui file
        #uic.loadUi("../quiwip/testtext.ui", self)
        
        uic.loadUi("../quiwip/testqtd1.ui", self)
        self.setWindowTitle("Bind Text Typing")
        
        # Define our widgets
        self.edit = self.findChild(QtWidgets.QLineEdit, "lineEdit")
        self.label = self.findChild(QtWidgets.QLabel, "label")
        self.textBrowser = self.findChild(QtWidgets.QTextBrowser, "textBrowser")
        
        # Hit Enter
        self.edit.editingFinished.connect(self.hitEnter)
        
        # Change Text
        self.edit.textChanged.connect(self.changeText)
                       
        self.show()
        
    def hitEnter(self):
        self.textBrowser.setText(self.edit.text())
    
    def changeText(self):
        self.label.setText(self.edit.text())
```

```python
dir_project_root = Path(os.getcwd().split("notebook")[0])
app = QtWidgets.QApplication(sys.argv)
UIWindow = UI()
app.exec_()
#app.setupUi()
#ex = Ui_MainWindow()
#ex = FileTreeSelectorDialog(root_path=str(dir_project_root)) # dir as str because QT seems to not support pathlib
# class Ui_MainWindow(object):
#sys.exit(app.exec_())
```

```python
"""
# file tree selector
import sys
import os
from pathlib import Path
from PyQt5 import QtWidgets, uic, QtCore, QtGui

class FileTreeSelectorModel(QtWidgets.QFileSystemModel):
    def __init__(self, parent=None, root_path="/"):
        QtWidgets.QFileSystemModel.__init__(self, None)
        self.root_path = root_path
        self.checks = {}
        self.nodestack = []
        self.parent_index = self.setRootPath(self.root_path)
        self.root_index = self.index(self.root_path)

        self.setFilter(QtCore.QDir.AllEntries | QtCore.QDir.Hidden | QtCore.QDir.NoDot)
        self.directoryLoaded.connect(self._loaded)

    def _loaded(self, path):
        print("_loaded", self.root_path, self.rowCount(self.parent_index))

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.CheckStateRole:
            return QtWidgets.QFileSystemModel.data(self, index, role)
        else:
            if index.column() == 0:
                return self.checkState(index)

    def flags(self, index):
        return (
            QtWidgets.QFileSystemModel.flags(self, index)
            | QtCore.Qt.ItemIsUserCheckable
        )

    def checkState(self, index):
        if index in self.checks:
            return self.checks[index]
        else:
            return QtCore.Qt.Checked

    def setData(self, index, value, role):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            self.checks[index] = value
            print("setData(): {}".format(value))
            return True
        return QtWidgets.QFileSystemModel.setData(self, index, value, role)

    def traverseDirectory(self, parentindex, callback=None):
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
    def __init__(self, root_path="/"):
        super().__init__()

        self.root_path = root_path

        # Widget
        self.title = "Application Window"
        self.left = 10
        self.top = 10
        self.width = 1080
        self.height = 640

        self.setWindowTitle(self.title)  # TODO:  Whilch title?
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Model
        self.model = FileTreeSelectorModel(root_path=self.root_path)
        # self.model          = QtWidgets.QFileSystemModel()

        # View
        self.view = QtWidgets.QTreeView()

        self.view.setObjectName("treeView_fileTreeSelector")
        self.view.setWindowTitle("Dir View")  # TODO:  Which title?
        self.view.setAnimated(False)
        self.view.setIndentation(20)
        self.view.setSortingEnabled(True)
        self.view.setColumnWidth(0, 150)
        self.view.resize(1080, 640)

        # Attach Model to View
        self.view.setModel(self.model)
        self.view.setRootIndex(self.model.parent_index)

        # Misc
        self.node_stack = []

        # GUI
        windowlayout = QtWidgets.QVBoxLayout()
        windowlayout.addWidget(self.view)
        self.setLayout(windowlayout)

        QtCore.QMetaObject.connectSlotsByName(self)

        self.show()

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_treeView_fileTreeSelector_clicked(self, index):
        print("tree clicked: {}".format(self.model.filePath(index)))
        self.model.traverseDirectory(index, callback=self.model.printIndex)


dir_project_root = Path(os.getcwd().split("notebook")[0])
app = QtWidgets.QApplication(sys.argv)
ex = FileTreeSelectorDialog(
    root_path=str(dir_project_root)
)  # dir as str because QT seems to not support pathlib
sys.exit(app.exec_())
"""
```

```python

```
