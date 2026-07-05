"""Load src/lib/statistics.py without colliding with Python's stdlib ``statistics`` module."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_BRAINWASH_STATISTICS_MODULE_NAME = "brainwash_statistics"
_STATISTICS_FILE = Path(__file__).resolve().parent / "statistics.py"


def load_brainwash_statistics_module() -> ModuleType:
    """Return the Brainwash statistics module (not stdlib ``statistics``)."""
    spec = importlib.util.spec_from_file_location(_BRAINWASH_STATISTICS_MODULE_NAME, _STATISTICS_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Brainwash statistics from {_STATISTICS_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module