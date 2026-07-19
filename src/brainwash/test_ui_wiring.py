"""pytest-qt smoke tests (offscreen; no full UIsub)."""

from PyQt5 import QtCore, QtWidgets

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


def test_entity_remove_button_double_click_and_hover(qtbot):
    from ui_widgets import EntityRemoveButton, GroupRemoveButton

    btn = EntityRemoveButton(2, "controls", object_prefix="group_remove")
    qtbot.addWidget(btn)
    removed = []
    hovered = []
    left = []
    btn.removeRequested.connect(lambda gid: removed.append(gid))
    btn.hoverEntered.connect(lambda gid, name: hovered.append((gid, name)))
    btn.hoverLeft.connect(lambda: left.append(True))

    qtbot.mouseMove(btn)
    btn.enterEvent(None)
    assert hovered == [(2, "controls")]

    # Single click does not remove
    qtbot.mouseClick(btn, QtCore.Qt.LeftButton)
    assert removed == []

    qtbot.mouseDClick(btn, QtCore.Qt.LeftButton)
    assert removed == [2]

    btn.leaveEvent(None)
    assert left == [True]

    # Alias still constructs
    alias = GroupRemoveButton(1, "set 1", object_prefix="testset_remove")
    qtbot.addWidget(alias)
    assert alias.objectName() == "testset_remove_1"


def test_tablemodel_blind_display_masks_name_and_path(qtbot):
    """DisplayRole blinds name/path; underlying DataFrame keeps real values."""
    import pandas as pd
    from PyQt5 import QtCore

    from ui_widgets import TableModel

    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "recording_name": ["slice_A", "slice_B"],
            "path": ["/secret/a.abf", "/secret/b.abf"],
        }
    )
    model = TableModel(df)
    # Real values when not blind
    assert model.data(model.index(0, 1), QtCore.Qt.DisplayRole) == "slice_A"
    assert model.data(model.index(0, 2), QtCore.Qt.DisplayRole) == "/secret/a.abf"
    # Underlying access (role=None) still real
    assert model.data(model.index(0, 1), None) == "slice_A"

    model.set_blind_display(blind=True, aliases={"1": "Rec 1", "2": "Rec 2"})
    assert model.data(model.index(0, 1), QtCore.Qt.DisplayRole) == "Rec 1"
    assert model.data(model.index(1, 1), QtCore.Qt.DisplayRole) == "Rec 2"
    assert model.data(model.index(0, 2), QtCore.Qt.DisplayRole) == "—"
    # DataFrame / non-Display access unchanged
    assert model._data.iloc[0]["recording_name"] == "slice_A"
    assert model._data.iloc[0]["path"] == "/secret/a.abf"
    assert model.data(model.index(0, 1), None) == "slice_A"


def test_tablemodel_sort_by_display_recording_name_when_blind(qtbot):
    """Blind sort uses Rec n order, not real recording_name lexicographic order."""
    import pandas as pd
    from PyQt5 import QtCore

    from ui_widgets import TableModel

    # Real names would sort: high_z, mid_m, low_a
    # Aliases intentionally reverse-ish: high_z→Rec 1, mid_m→Rec 3, low_a→Rec 2
    df = pd.DataFrame(
        {
            "ID": [10, 20, 30],
            "recording_name": ["high_z", "mid_m", "low_a"],
            "path": ["/z", "/m", "/a"],
        }
    )
    model = TableModel(df)
    model.set_blind_display(
        blind=True,
        aliases={"10": "Rec 1", "20": "Rec 3", "30": "Rec 2"},
    )
    name_col = list(df.columns).index("recording_name")
    model.sort(name_col, QtCore.Qt.AscendingOrder)
    # Display order Rec 1, Rec 2, Rec 3 → IDs 10, 30, 20
    assert list(model._data["ID"]) == [10, 30, 20]
    assert list(model._data["recording_name"]) == ["high_z", "low_a", "mid_m"]
    # Natural: Rec 10 after Rec 2
    df2 = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "recording_name": ["a", "b", "c"],
            "path": ["p1", "p2", "p3"],
        }
    )
    model2 = TableModel(df2)
    model2.set_blind_display(blind=True, aliases={"1": "Rec 10", "2": "Rec 2", "3": "Rec 1"})
    model2.sort(0 if df2.columns[0] == "recording_name" else list(df2.columns).index("recording_name"), QtCore.Qt.AscendingOrder)
    assert list(model2._data["ID"]) == [3, 2, 1]


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
    u.stat_test.test_type = "ANCOVA"
    u.stat_test.formal_test_results = [
        {
            "config": {
                "type": "IO ANCOVA",
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