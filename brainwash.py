#!/usr/bin/env python3

import sys
import lib.ui
import lib.parse
# import lib.method




if __name__ == '__main__':
    app = lib.ui.QtWidgets.QApplication(sys.argv)
    UIWindow = lib.ui.UI()
    sys.exit(app.exec_())
