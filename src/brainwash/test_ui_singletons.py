"""Phase 6a: uistate/uiplot/config are not created at import time."""

import os
import subprocess
import sys
from pathlib import Path


def test_brainwash_ui_aliases_none_before_uisub():
    src_root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(src_root)}
    code = (
        "from brainwash.ui import config, uiplot, uistate; "
        "assert uistate is None and uiplot is None and config is None"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(src_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout