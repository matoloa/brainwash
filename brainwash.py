#!/usr/bin/env python3

import sys
from lib.ui import UIsub
import lib.parse
# import lib.method
from PyQt5 import QtCore, QtGui, QtWidgets



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UIsub(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
