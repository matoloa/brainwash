#!/usr/bin/env python3

import logging
import os
import sys
import tempfile

# import lib.method
from PyQt5 import QtWidgets

# from lib.parse import *

if __name__ == "__main__":
    debug = "--debug" in sys.argv
    if debug:
        os.environ['BRAINWASH_DEBUG'] = '1'
    # Determine log path for frozen app or dev
    if getattr(sys, "frozen", False):
        log_dir = tempfile.gettempdir()
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(log_dir, "brainwash_debug.log")

    print("FROZEN:", getattr(sys, "frozen", False))
    print("LOG_DIR:", repr(log_dir))
    print("LOG_PATH:", repr(log_path))
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)

    # Suppress Matplotlib font spam (noisy on frozen Windows first-run)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

    logger.info(
        f"Brainwash starting... platform={sys.platform}, frozen={getattr(sys, 'frozen', False)}, argv={sys.argv}, py={sys.version[:10]}"
    )
    # import intentionally late to make sure it inherits logging level
    from lib.ui import UIsub

    if debug:
        try:
            from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

            logger.debug(f"PyQt5 v{PYQT_VERSION_STR}, Qt v{QT_VERSION_STR}")
        except Exception:
            logger.debug("PyQt5/Qt versions unavailable")

    if debug and sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.AllocConsole()
            ctypes.windll.kernel32.SetConsoleTitleW("Brainwash Debug Console")
            logger.info("Allocated Windows debug console")
        except Exception as e:
            logger.warning(f"Failed to allocate console: {e}")

    try:
        app = QtWidgets.QApplication(sys.argv)
        logger.info(f"QApplication created, platformName='{app.platformName()}'")
        MainWindow = QtWidgets.QMainWindow()
        logger.info("QMainWindow created")
        logger.info("Instantiating UIsub...")
        ui = UIsub(MainWindow)
        logger.info("UIsub instantiated successfully")
        MainWindow.show()
        logger.info("MainWindow shown, entering event loop")
        sys.exit(app.exec_())
    except Exception:
        logger.exception("Startup failed with exception:")
        sys.exit(1)
