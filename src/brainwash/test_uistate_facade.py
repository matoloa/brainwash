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
    u.project.project_table_sort = {"column": "recording_name", "order": 1}
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
        assert u2.project.project_table_sort == {"column": "recording_name", "order": 1}


def test_amp_slope_view_ignore_volley_under_relative():
    u = UIstate()
    u.project.checkBox["EPSP_amp"] = False
    u.project.checkBox["EPSP_slope"] = False
    u.project.checkBox["volley_amp"] = True
    u.project.checkBox["volley_amp_mean"] = True
    u.project.checkBox["volley_slope"] = True
    u.project.checkBox["volley_slope_mean"] = True
    u.project.checkBox["norm_EPSP"] = False
    assert u.ampView() is True
    assert u.slopeView() is True
    u.project.checkBox["norm_EPSP"] = True
    # Volley still checked, but ignored in relative mode
    assert u.project.checkBox["volley_amp"] is True
    assert u.project.checkBox["volley_slope_mean"] is True
    assert u.ampView() is False
    assert u.slopeView() is False
    u.project.checkBox["EPSP_amp"] = True
    assert u.ampView() is True
    assert u.slopeView() is False


def test_project_table_sort_normalize_and_legacy_cfg():
    from ui_state_parts import ProjectPersistedState

    assert ProjectPersistedState._normalize_project_table_sort(None) == {"column": None, "order": 0}
    assert ProjectPersistedState._normalize_project_table_sort({"column": " groups ", "order": "1"}) == {
        "column": "groups",
        "order": 1,
    }
    assert ProjectPersistedState._normalize_project_table_sort({"column": "", "order": 9}) == {
        "column": None,
        "order": 0,
    }
    # Old cfg.pkl without key loads as default
    p = ProjectPersistedState()
    p.reset()
    p.apply_state_dict({"version": "0.1"}, zoom_defaults=p.zoom.copy())
    assert p.project_table_sort == {"column": None, "order": 0}