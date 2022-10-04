#!/usr/bin/env python3

import sys
import lib.ui
import lib.parse
# import lib.method
from PyQt5 import QtCore, QtGui, QtWidgets



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
