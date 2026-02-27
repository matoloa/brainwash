#!/usr/bin/env python3

import logging
import os
import sys
import tempfile
from pathlib import Path

# Ensure `src/` is on sys.path so `lib` is importable regardless of how
# main.py is invoked (e.g. `python src/main.py`, `python -m src.main`,
# or a frozen cx_Freeze executable).
_src_dir = str(Path(__file__).parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from PyQt5 import QtWidgets


def force_focus(window):
    """Force window focus using Win32 API (Windows builds only)."""
    if sys.platform == "win32":
        import ctypes

        hwnd = int(window.winId())
        ctypes.windll.user32.AllowSetForegroundWindow(hwnd)
        ctypes.windll.user32.SetForegroundWindow(hwnd)


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    if debug:
        os.environ["BRAINWASH_DEBUG"] = "1"

    # Determine log path: write to temp dir for frozen builds, else next to main.py
    if getattr(sys, "frozen", False):
        log_dir = tempfile.gettempdir()
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(log_dir, "brainwash_debug.log")

    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger(__name__)

    # Suppress noisy Matplotlib font-manager spam (especially on frozen first-run)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

    logger.info(
        f"Brainwash starting — platform={sys.platform}, "
        f"frozen={getattr(sys, 'frozen', False)}, "
        f"argv={sys.argv}, py={sys.version[:50]}"
    )

    # pandas 3.0 changed the default string dtype to Arrow-backed string[pyarrow],
    # which rejects assignment of non-string values (int, float, etc.).
    # The project DataFrame mixes strings, ints and floats in the same CSV-loaded
    # DataFrame, so we opt back into the legacy object-dtype string behaviour.
    # Imported late so any pandas logging is captured by the handler above.
    # import pandas as pd

    # pd.options.future.infer_string = False

    # Import intentionally late so the logging config is in place before any
    # module-level code in ui.py runs.
    #
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
        logger.info("QMainWindow created, instantiating UIsub...")

        ui = UIsub(MainWindow)
        logger.info("UIsub instantiated successfully")

        MainWindow.show()
        MainWindow.raise_()  # bring to top of Z-order
        MainWindow.activateWindow()  # request input focus
        force_focus(MainWindow)  # Win32 fallback for stubborn builds
        logger.info("MainWindow shown, entering event loop")

        sys.exit(app.exec_())
    except Exception:
        logger.exception("Startup failed with exception:")
        sys.exit(1)
