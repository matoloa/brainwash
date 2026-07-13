"""Load Brainwash statistics module (not Python stdlib ``statistics``)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

_SRC = Path(__file__).resolve().parent.parent


def load_brainwash_statistics_module() -> ModuleType:
    """Return ``brainwash.statistics`` — same import path as ``ui.py`` and ``main.py``."""
    src = str(_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    import brainwash.statistics as module

    return module