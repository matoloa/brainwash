"""Tests for brainwash_ui.app_context snapshots and statusbar dispatch."""

from brainwash_ui import app_context, statusbar
from test_statistics_fixtures import make_dd_groups, make_dd_testsets
from ui_state_classes import UIstate


def test_compute_statusbar_io_empty():
    u = UIstate()
    u.experiment.experiment_type = "io"
    result = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={},
        dd_testsets={},
    )
    assert result.text is None


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