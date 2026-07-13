"""pytest-qt smoke tests (offscreen; no full UIsub)."""

from PyQt5 import QtWidgets

from brainwash_ui import app_context, statusbar, view_state
from ui_state_classes import UIstate


def _statusbar_for_uistate(u: UIstate, *, dd_groups: dict, dd_testsets: dict | None = None) -> statusbar.StatusbarResult:
    """Mirror StatTestMixin statusbar query path without Qt host."""
    return app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups=dd_groups,
        dd_testsets=dd_testsets or {},
    )

_TYPE_TO_EXPERIMENT = {
    "radioButton_type_time": "time",
    "radioButton_type_io": "io",
    "radioButton_type_pp": "PP",
}


def test_qt_application_and_label(qtbot):
    label = QtWidgets.QLabel("brainwash")
    qtbot.addWidget(label)
    assert label.text() == "brainwash"


def test_radio_group_updates_checked_button(qtbot):
    group = QtWidgets.QButtonGroup()
    box = QtWidgets.QWidget()
    qtbot.addWidget(box)
    r1 = QtWidgets.QRadioButton("time")
    r2 = QtWidgets.QRadioButton("io")
    group.addButton(r1)
    group.addButton(r2)
    r2.setChecked(True)
    qtbot.wait(10)
    assert group.checkedButton() is r2
    assert r2.isChecked()


def test_experiment_type_radio_updates_nested_uistate(qtbot):
    u = UIstate()
    u.experiment.experiment_type = "time"
    btn = QtWidgets.QRadioButton()
    btn.setObjectName("radioButton_type_io")
    qtbot.addWidget(btn)

    exp_type = _TYPE_TO_EXPERIMENT.get(btn.objectName())
    u.experiment.experiment_type = exp_type

    assert u.experiment.experiment_type == "io"
    assert u.x_axis == "io"


def test_stat_test_frame_visibility_follows_view_tools(qtbot):
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.project.viewTools["frameToolTest"] = ["Statistical Test", False]
    assert view_state.should_show_stat_test_frame("io", u.project.viewTools) is False

    u.project.viewTools["frameToolTest"][1] = True
    assert view_state.should_show_stat_test_frame("io", u.project.viewTools) is True


def test_stat_test_host_io_statusbar_text(qtbot):
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.formal_test_results = [
        {
            "config": {
                "type": "IO regression",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2, "G2": 3},
                "slope_p": 0.04,
                "r2_per_group": {},
                "n_unit": "subject",
            }
        }
    ]
    dd_groups = {"G1": {"group_name": "Ctl"}, "G2": {"group_name": "Tx"}}
    result = _statusbar_for_uistate(u, dd_groups=dd_groups)
    assert result.text is not None
    assert "IO ANCOVA" in result.text
    assert result.state == "info"


def test_stat_test_host_ttest_warning_single_group(qtbot):
    u = UIstate()
    u.experiment.experiment_type = "time"
    u.stat_test.test_type = "t-test"
    u.stat_test.test_t_variant = "unpaired"
    dd_groups = {"G1": {"show": True, "rec_IDs": ["r1"], "group_name": "Only"}}
    result = _statusbar_for_uistate(u, dd_groups=dd_groups)
    assert result.text is not None
    assert "t-test requires 2 group(s) with data" in result.text
    assert result.state == "warning"


def test_hidden_group_excluded_from_visible_ids(qtbot):
    dd = {
        "G1": {"show": True, "rec_IDs": ["r1"]},
        "G2": {"show": False, "rec_IDs": ["r2"]},
    }
    assert view_state.visible_group_ids(dd) == ["G1"]