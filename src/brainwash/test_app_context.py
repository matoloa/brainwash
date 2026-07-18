"""Tests for brainwash_ui.app_context snapshots and statusbar dispatch."""

from brainwash_ui import app_context, statusbar
from test_statistics_fixtures import make_dd_groups, make_dd_testsets
from ui_state_classes import UIstate


def test_compute_statusbar_io_none_hints_select_ancova():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "None"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={},
        dd_testsets={},
    )
    assert result.state == "info"
    assert result.text == "Select ANCOVA to run Input-Output analysis"


def test_compute_statusbar_io_warns_on_non_ancova_test():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "t-test"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={},
        dd_testsets={},
    )
    assert result.state == "warning"
    assert result.text == "Use ANCOVA for Input-Output experiment analysis"


def test_compute_statusbar_io_ancova_allows_regression_path():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "ANCOVA"
    u.stat_test.formal_test_results = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2},
                "slope_p": 0.01,
                "r2_per_group": {},
            }
        }
    ]
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={"G1": {"group_name": "Ctl"}},
        dd_testsets={},
    )
    assert result.state == "info"
    assert result.text is not None
    assert "IO ANCOVA" in result.text


def test_compute_statusbar_ttest_warning():
    u = UIstate()
    u.stat_test.test_type = "t-test"
    u.stat_test.test_t_variant = "unpaired"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1"),
    )
    assert result.state == "warning"
    assert "t-test requires 2 group(s)" in (result.text or "")


def test_compute_statusbar_non_io_ancova_explains_io_only():
    u = UIstate()
    u.experiment.experiment_type = "time"
    u.stat_test.test_type = "ANCOVA"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
    )
    assert result.state == "warning"
    assert result.text is not None
    assert "not implemented" not in result.text.lower()
    assert "Input-Output" in result.text or "I-O" in result.text


def test_compute_statusbar_none_clears():
    u = UIstate()
    u.stat_test.test_type = "None"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1"),
    )
    assert result == statusbar.StatusbarResult(None, None)