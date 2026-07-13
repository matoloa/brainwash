"""pytest-qt smoke tests (offscreen; no full UIsub)."""

from PyQt5 import QtCore, QtWidgets

from brainwash_ui import view_state
from ui_state_classes import UIstate

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