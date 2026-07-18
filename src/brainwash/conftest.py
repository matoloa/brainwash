"""pytest path setup: src/brainwash must precede stdlib so local statistics.py is importable."""

import sys
from pathlib import Path

_LIB = str(Path(__file__).resolve().parent)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)