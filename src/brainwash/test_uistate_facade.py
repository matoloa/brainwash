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
    u.project.blind_recordings = True
    u.project.blind_aliases = {"1": "Rec 1", "7": "Rec 2"}
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
        assert u2.project.blind_recordings is True
        assert u2.project.blind_aliases == {"1": "Rec 1", "7": "Rec 2"}


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
    assert p.blind_recordings is False
    assert p.blind_aliases == {}


def test_migrate_legacy_volley_magenta_to_green():
    from ui_state_parts import (
        ProjectPersistedState,
        _DEFAULT_MEASURE_RGB,
        measure_rgb,
        migrate_legacy_measure_colors,
    )

    legacy = {
        "rgb_volley_amp": (1, 0.2, 1),
        "rgb_volley_slope": [1.0, 0.5, 1.0],
        "rgb_EPSP_amp": (0.2, 0.25, 0.85),
    }
    migrated = migrate_legacy_measure_colors(legacy)
    assert migrated["rgb_volley_amp"] == _DEFAULT_MEASURE_RGB["rgb_volley_amp"]
    assert migrated["rgb_volley_slope"] == _DEFAULT_MEASURE_RGB["rgb_volley_slope"]
    # Custom / already-new colors left alone
    custom = migrate_legacy_measure_colors({"rgb_volley_amp": (0.9, 0.1, 0.1)})
    assert custom["rgb_volley_amp"] == (0.9, 0.1, 0.1)

    # measure_rgb remaps legacy magenta and strips _mean / _norm
    assert measure_rgb(legacy, "volley_amp") == _DEFAULT_MEASURE_RGB["rgb_volley_amp"]
    assert measure_rgb(legacy, "volley_amp_mean") == _DEFAULT_MEASURE_RGB["rgb_volley_amp"]
    assert measure_rgb(legacy, "volley_slope_mean") == _DEFAULT_MEASURE_RGB["rgb_volley_slope"]

    p = ProjectPersistedState()
    p.reset()
    p.apply_state_dict(
        {
            "version": "0.16.3",
            "settings": {
                "rgb_volley_amp": (1.0, 0.2, 1.0),
                "rgb_volley_slope": (1.0, 0.5, 1.0),
            },
        },
        zoom_defaults=p.zoom.copy(),
    )
    assert p.settings["rgb_volley_amp"] == _DEFAULT_MEASURE_RGB["rgb_volley_amp"]
    assert p.settings["rgb_volley_slope"] == _DEFAULT_MEASURE_RGB["rgb_volley_slope"]
