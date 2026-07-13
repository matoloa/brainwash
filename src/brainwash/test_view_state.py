"""Characterization tests for brainwash_ui.view_state."""

from brainwash_ui import view_state
from test_statistics_fixtures import make_dd_groups, make_dd_testsets


def test_visible_group_ids_empty():
    assert view_state.visible_group_ids({}) == []
    assert view_state.visible_group_ids(None) == []


def test_visible_group_ids_show_flags():
    dd = {
        "G1": {"show": True, "rec_IDs": ["r1"]},
        "G2": {"show": False, "rec_IDs": ["r2"]},
        "G3": {"show": "True", "rec_IDs": ["r3"]},
        "G4": {"show": 1, "rec_IDs": ["r4"]},
    }
    assert view_state.visible_group_ids(dd) == ["G1", "G3", "G4"]


def test_visible_testset_ids():
    dd = make_dd_testsets("TS1", "TS2", "TS3")
    dd["TS2"]["show"] = False
    assert view_state.visible_testset_ids(dd) == ["TS1", "TS3"]
    assert view_state.visible_testset_ids(None) == []


def test_should_show_stat_test_frame_io_default_hidden():
    assert view_state.should_show_stat_test_frame("io", {}) is False


def test_should_show_stat_test_frame_respects_view_tools():
    tools = {"frameToolTest": ["Statistical Test", True]}
    assert view_state.should_show_stat_test_frame("io", tools) is True
    tools["frameToolTest"][1] = False
    assert view_state.should_show_stat_test_frame("time", tools) is False


def test_groups_with_recordings_filters_empty():
    dd = make_dd_groups("G1", "G2")
    dd["G2"]["rec_IDs"] = []
    shown = view_state.visible_group_ids(dd)
    assert view_state.groups_with_recordings(dd, shown) == ["G1"]