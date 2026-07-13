"""UIstate sub-object facade and cfg.pkl round-trip."""

import pickle
import tempfile
from pathlib import Path

from ui_state_classes import UIstate


def test_substate_layout():
    u = UIstate()
    assert hasattr(u, "project")
    assert hasattr(u, "experiment")
    assert hasattr(u, "stat_test")
    assert hasattr(u, "plot")
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "t-test"
    u.plot.ax1 = "stub"
    assert u.experiment.experiment_type == "io"
    assert u.stat_test.test_type == "t-test"
    assert u.plot.ax1 == "stub"


def test_cfg_pickle_roundtrip():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.experiment.io_input = "vslope"
    u.stat_test.test_fdr = True
    u.project.checkBox["EPSP_slope"] = False
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        u.save_cfg(folder, bw_version="9.9.9")
        u2 = UIstate()
        u2.load_cfg(folder, "9.9.9")
        assert u2.experiment.experiment_type == "io"
        assert u2.experiment.io_input == "vslope"
        assert u2.stat_test.test_fdr is True
        assert u2.project.checkBox["EPSP_slope"] is False
        assert u2.project.version == "9.9.9"