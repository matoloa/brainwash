import os  # TODO: replace use by pathlib?
import sys
import tempfile
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets, sip
import numpy as np
import pandas as pd

# pandas 3.0 changed the default string dtype to Arrow-backed string[pyarrow],
# which rejects assignment of non-string values (int, float, etc.).
# The project DataFrame mixes strings, ints and floats in the same CSV-loaded
# DataFrame, so we opt back into the legacy object-dtype string behaviour.
pd.options.future.infer_string = False

# Matplotlib slowdown fix for frozen Windows builds: redirect config dir to temp
# Must be set before matplotlib is imported
if getattr(sys, "frozen", False):
    os.environ.setdefault(
        "MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "matplotlib")
    )

# TODO: kick these out to ui_plot.py
from matplotlib import use as matplotlib_use
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

matplotlib_use("Qt5Agg")

import importlib  # for reloading modules
import json  # for saving and loading dicts as strings
import logging
import pickle  # for saving and loading dicts
import re  # regular expressions
import socket  # getting computer name and localdomain for df_project['host'] (not reported in talkback)
import time  # counting time for functions

# used by talkback
import uuid  # generating unique talkback ID
from datetime import datetime  # used in project name defaults

import analysis_v2 as analysis

# brainwash files
import parse

# read and write
import toml  # for reading pyproject.toml
import ui_data_frames
import ui_designer  # Import the Designer-generated UI code
import ui_groups
import ui_plot
import ui_project
import ui_state_classes
import ui_sweep_ops
import yaml  # used by talkback
from ui_project import df_projectTemplate
```

**Only the first 8 lines change** — `from PyQt5 import ...` moves up above `import numpy as np`. Everything from line 9 onward stays identical to what's already in the file. Please apply just that reorder to the top of `ui.py`.

The reason this matters: on a frozen Windows cx_Freeze build, PyQt5's DLL directory isn't on the system `PATH`. When PyQt5 is imported, it calls `os.add_dll_directory()` (Python 3.8+ Windows API) to register its own `bin/` folder, which contains `Qt5Core.dll` and other Qt DLLs. NumPy's compiled `.pyd` extensions link against some of those same VC++ runtime DLLs. If numpy is imported first — before PyQt5 has had a chance to register its DLL directory — numpy's extension loader can fail to find the DLLs it needs, producing the silent hang you're seeing (the process dies during DLL loading, before Python's exception machinery can even run, so nothing reaches the logger).
