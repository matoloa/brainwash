"""Unit tests for color_events pure helpers (#6)."""

from brainwash_ui import color_events as ce


def test_normalize_and_effective_mode_matrix():
    assert ce.normalize_color_events_by(None) == "rec"
    assert ce.normalize_color_events_by("stim_nr") == "stim"
    assert ce.effective_color_events_mode("group", 5, 5) == "group"
    assert ce.effective_color_events_mode("rec", 1, 4) == "stim"
    assert ce.effective_color_events_mode("stim", 3, 1) == "rec"
    assert ce.effective_color_events_mode("rec", 3, 4) == "rec"
    assert ce.effective_color_events_mode("stim", 3, 4) == "stim"
    # 1×1 (or thinner) keeps build-time defaults — even if radio is group/rec/stim
    assert ce.effective_color_events_mode("rec", 1, 1) == "default"
    assert ce.effective_color_events_mode("stim", 1, 1) == "default"
    assert ce.effective_color_events_mode("group", 1, 1) == "default"
    assert ce.effective_color_events_mode("rec", 0, 0) == "default"
    assert ce.event_mouseover_enabled(1, 1) is True
    assert ce.event_mouseover_enabled(1, 2) is False
    assert ce.event_mouseover_enabled(2, 1) is False
    assert ce.event_mouseover_enabled(1, 0) is False


def test_display_order_and_rec_index_map():
    display = [10, 20, 30, 40]
    selected = [40, 20]
    ordered = ce.selected_rec_ids_in_display_order(display, selected)
    assert ordered == [20, 40]
    # Full display domain keeps stable ranks when selection shrinks
    idx = ce.rec_gradient_index_map(display)
    assert idx == {"10": 0, "20": 1, "30": 2, "40": 3}
    assert idx["40"] == 3  # not rebased to 1 when only 20,40 selected


def test_stim_domain_full_range_not_selection():
    """Stim 3 of {1,2,3} keeps rank 2 even if only stim 3 is 'selected' for analysis."""
    store = {
        "a": {"rec_ID": 1, "stim": 1, "role": "stim_marker", "axis": "axm"},
        "b": {"rec_ID": 1, "stim": 2, "role": "stim_marker", "axis": "axm"},
        "c": {"rec_ID": 1, "stim": 3, "role": "event_trace", "axis": "axe"},
    }
    domain = ce.collect_stim_domain_for_recs(store, [1])
    assert domain == [1, 2, 3]
    smap = ce.stim_gradient_index_map(domain)
    assert smap == {1: 0, 2: 1, 3: 2}
    grad = {0: "c0", 1: "c1", 2: "c2"}
    # Only stim 3 "selected" for events — color still c2
    assert (
        ce.resolve_event_artist_color(
            mode="stim",
            rec_ID=1,
            stim=3,
            stim_index_map=smap,
            rec_index_map={},
            gradient=grad,
            dd_groups={},
        )
        == "c2"
    )


def test_group_color_shown_only_and_ambiguous():
    dd = {
        1: {"show": True, "color": "#00ff00", "rec_IDs": [1, 2]},
        2: {"show": False, "color": "#ff0000", "rec_IDs": [2, 3]},
        3: {"show": True, "color": "#0000ff", "rec_IDs": [3]},
    }
    assert ce.group_color_for_rec(1, dd_groups=dd) == "#00ff00"
    # rec 2 in group1 shown + group2 hidden → only group1 counts
    assert ce.group_color_for_rec(2, dd_groups=dd) == "#00ff00"
    # rec 3 only in hidden group2 and shown group3 → one shown → blue
    assert ce.group_color_for_rec(3, dd_groups=dd) == "#0000ff"
    # multi shown
    dd2 = {
        1: {"show": True, "color": "a", "rec_IDs": [9]},
        2: {"show": True, "color": "b", "rec_IDs": [9]},
    }
    assert ce.group_color_for_rec(9, dd_groups=dd2) == "black"
    assert ce.group_color_for_rec(99, dd_groups=dd) == "black"


def test_resolve_event_artist_color_modes():
    grad = {0: "c0", 1: "c1", 2: "c2"}
    rec_map = {"1": 0, "2": 1}
    stim_map = {1: 0, 2: 1, 3: 2}
    dd = {1: {"show": True, "color": "g1", "rec_IDs": [1]}}

    assert (
        ce.resolve_event_artist_color(
            mode="rec",
            rec_ID=2,
            stim=1,
            stim_index_map=stim_map,
            rec_index_map=rec_map,
            gradient=grad,
            dd_groups=dd,
        )
        == "c1"
    )
    assert (
        ce.resolve_event_artist_color(
            mode="stim",
            rec_ID=1,
            stim=3,
            stim_index_map=stim_map,
            rec_index_map=rec_map,
            gradient=grad,
            dd_groups=dd,
        )
        == "c2"
    )
    assert (
        ce.resolve_event_artist_color(
            mode="group",
            rec_ID=1,
            stim=3,
            stim_index_map=stim_map,
            rec_index_map=rec_map,
            gradient=grad,
            dd_groups=dd,
        )
        == "g1"
    )


def test_artist_should_receive_event_color():
    assert ce.artist_should_receive_event_color({"axis": "axe", "role": "event_trace", "stim": 1})
    assert ce.artist_should_receive_event_color({"axis": "axm", "role": "stim_marker", "stim": 1})
    assert not ce.artist_should_receive_event_color({"axis": "axm", "role": "mean_trace"})
    assert not ce.artist_should_receive_event_color({"axis": "ax1", "role": "series", "stim": 1})
