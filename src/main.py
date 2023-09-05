#!/usr/bin/env python3

import sys

# import lib.method
from PyQt5 import QtWidgets

# from lib.parse import *
from lib.ui import UIsub

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UIsub(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
