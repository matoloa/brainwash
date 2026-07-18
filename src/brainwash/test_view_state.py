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


def test_suppress_volley_under_norm_output_only():
    assert view_state.suppress_volley_under_norm("volley_amp", norm_active=True, axis="ax1")
    assert view_state.suppress_volley_under_norm("volley_slope_mean", norm_active=True, axis="ax2")
    assert view_state.suppress_volley_under_norm("volley_amp_mean", norm_active=True, axis=None)
    # Event markers stay under Relative mode
    assert not view_state.suppress_volley_under_norm("volley_amp", norm_active=True, axis="axe")
    # Off when not relative
    assert not view_state.suppress_volley_under_norm("volley_amp", norm_active=False, axis="ax1")
    # EPSP not suppressed by this rule
    assert not view_state.suppress_volley_under_norm("EPSP_amp", norm_active=True, axis="ax1")


def test_aspect_counts_for_output_view_ignores_volley_when_relative():
    cb = {
        "EPSP_amp": False,
        "volley_amp": True,
        "volley_amp_mean": True,
        "norm_EPSP": False,
    }
    assert view_state.aspect_counts_for_output_view("volley_amp", cb)
    assert view_state.aspect_counts_for_output_view("volley_amp_mean", cb)
    cb["norm_EPSP"] = True
    assert not view_state.aspect_counts_for_output_view("volley_amp", cb)
    assert not view_state.aspect_counts_for_output_view("volley_amp_mean", cb)
    # EPSP still counts when checked
    cb["EPSP_amp"] = True
    assert view_state.aspect_counts_for_output_view("EPSP_amp", cb)
