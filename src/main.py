#!/usr/bin/env python3

import sys
from pathlib import Path

# Ensure `src/` is on sys.path so `lib` is importable regardless of how
# main.py is invoked (e.g. `python src/main.py`, `python -m src.main`,
# or a frozen cx_Freeze executable).
_src_dir = str(Path(__file__).parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# import lib.method
import pandas as pd

# pandas 3.0 changed the default string dtype to Arrow-backed string[pyarrow],
# which rejects assignment of non-string values (int, float, etc.).
# The project DataFrame mixes strings, ints and floats in the same CSV-loaded
# DataFrame, so we opt back into the legacy object-dtype string behaviour.
pd.options.future.infer_string = False

from PyQt5 import QtWidgets

# from lib.parse import *
from lib.ui import UIsub


def force_focus(window):
    """Force window focus using Win32 API (Windows builds only)."""
    if sys.platform == "win32":
        import ctypes

        hwnd = int(window.winId())
        ctypes.windll.user32.AllowSetForegroundWindow(hwnd)
        ctypes.windll.user32.SetForegroundWindow(hwnd)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = UIsub(MainWindow)
    MainWindow.show()
    MainWindow.raise_()  # bring to top of Z-order
    MainWindow.activateWindow()  # request input focus
    force_focus(MainWindow)  # Win32 fallback for stubborn builds
    sys.exit(app.exec_())
