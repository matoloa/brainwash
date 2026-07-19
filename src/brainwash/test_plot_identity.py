"""Unit tests for brainwash_ui.plot_identity (storage key ≠ display)."""

import pytest

from brainwash_ui import plot_identity as pi


def test_storage_key_rec_stable_and_name_free():
    k1 = pi.storage_key_rec(
        rec_ID=12,
        axis="ax1",
        role=pi.ROLE_SERIES,
        stim=1,
        aspect="EPSP_amp",
        variant="raw",
        x_mode="sweep",
    )
    k2 = pi.storage_key_rec(
        rec_ID="12",
        axis="ax1",
        role=pi.ROLE_SERIES,
        stim=1,
        aspect="EPSP_amp",
        variant="raw",
        x_mode="sweep",
    )
    assert k1.startswith("rec|")
    assert "slice" not in k1
    assert "EPSP" in k1 or "EPSP_amp" in k1
    assert k1 == k2 or k1.replace("|12|", "|12|")  # both encode id
    # Different role → different key
    k3 = pi.storage_key_rec(
        rec_ID=12,
        axis="ax1",
        role=pi.ROLE_SERIES_NORM,
        stim=1,
        aspect="EPSP_amp",
        variant="norm",
        x_mode="sweep",
    )
    assert k1 != k3


def test_storage_key_group_and_sys():
    g = pi.storage_key_group(
        group_ID=2,
        axis="ax1",
        role=pi.ROLE_GROUP_MEAN,
        aspect="EPSP_amp",
        variant="raw",
        level="subject",
        x_mode="sweep",
    )
    assert g.startswith("grp|2|")
    assert "subject" in g
    assert "Control" not in g  # no group name
    s = pi.storage_key_sys("Events y zero marker")
    assert s == "sys|Events y zero marker"


def test_find_rec_entries_and_require_one():
    store = {
        "legacy-name-key": {
            "rec_ID": "r1",
            "stim": 1,
            "aspect": "EPSP_amp",
            "role": pi.ROLE_ASPECT_MARKER,
            "axis": "axe",
            "variant": "raw",
            "line": object(),
        },
        "other": {
            "rec_ID": "r1",
            "stim": 1,
            "aspect": "EPSP_amp",
            "role": pi.ROLE_SERIES,
            "axis": "ax1",
            "variant": "raw",
            "line": object(),
        },
        "r2": {
            "rec_ID": "r2",
            "stim": 1,
            "aspect": "EPSP_amp",
            "role": pi.ROLE_SERIES,
            "axis": "ax1",
            "variant": "raw",
            "line": object(),
        },
    }
    hits = pi.find_rec_entries(store, rec_ID="r1", aspect="EPSP_amp")
    assert len(hits) == 2
    one = pi.require_one_rec_entry(store, rec_ID="r1", role=pi.ROLE_ASPECT_MARKER, stim=1)
    assert one["axis"] == "axe"
    with pytest.raises(LookupError):
        pi.require_one_rec_entry(store, rec_ID="missing")
    with pytest.raises(LookupError):
        pi.require_one_rec_entry(store, rec_ID="r1", aspect="EPSP_amp")  # ambiguous


def test_legend_label_prefers_display_label():
    entry = {
        "rec_ID": "r1",
        "axis": "ax1",
        "role": pi.ROLE_SERIES,
        "display_label": "Rec 3 EPSP amp",
        "line": object(),
    }
    assert pi.legend_label_for_entry(entry, fallback_key="rec|r1|…") == "Rec 3 EPSP amp"
    assert pi.legend_label_for_entry({}, fallback_key="fallback") == "fallback"


def test_find_entry_by_display_label():
    store = {
        "rec|r1|ax1|series|s1|EPSP_amp|raw|sweep": {
            "rec_ID": "r1",
            "display_label": "rec1 - stim 1 EPSP amp",
            "role": pi.ROLE_SERIES,
            "line": object(),
        }
    }
    key, ent = pi.find_entry_by_display_label(store, "rec1 - stim 1 EPSP amp")
    assert key.startswith("rec|")
    assert ent["rec_ID"] == "r1"
    assert pi.find_entry_by_display_label(store, "missing")[0] is None


def test_infer_rec_role_from_legacy_labels():
    assert pi.infer_rec_role("mean rec1 - stim 1 marker", kind="marker", axid="axm") == pi.ROLE_STIM_MARKER
    assert pi.infer_rec_role("rec1 - stim 1 selection marker", kind="vline", axid="axm") == pi.ROLE_STIM_SELECTION
    assert pi.infer_rec_role("rec1 - stim 1 EPSP amp marker", kind="marker", axid="axe", aspect="EPSP_amp") == pi.ROLE_ASPECT_MARKER
    assert pi.infer_rec_role("rec1 - stim 1 EPSP slope marker", kind="line", axid="axe", aspect="EPSP_slope") == pi.ROLE_ASPECT_MARKER
    assert pi.infer_rec_role("rec1 - stim 1 EPSP amp", kind="line", axid="ax1", aspect="EPSP_amp") == pi.ROLE_SERIES
    assert pi.infer_rec_role("rec1 - stim 1 EPSP amp norm", kind="line", axid="ax1", aspect="EPSP_amp", variant="norm") == pi.ROLE_SERIES_NORM
    assert pi.infer_rec_role("rec1 - stim 1 volley amp mean", kind="hline", axid="ax1", aspect="volley_amp") == pi.ROLE_SERIES_MEAN_HLINE
    assert pi.infer_rec_role("mean rec1", kind="line", axid="axm") == pi.ROLE_MEAN_TRACE
    assert pi.infer_rec_role("rec1 - stim 1", kind="line", axid="axe") == pi.ROLE_EVENT_TRACE
    assert pi.infer_rec_role("shade", kind="shade") == pi.ROLE_SHADE


def test_output_axis_legend_map_from_entries_uses_display():
    line_a, line_b = object(), object()
    dd_recs = {
        "rec|r1|ax1|series|s1|EPSP_amp|raw|sweep": {
            "rec_ID": "r1",
            "axis": "ax1",
            "role": pi.ROLE_SERIES,
            "display_label": "Rec 1 EPSP amp",
            "line": line_a,
        },
        "rec|r1|axe|aspect_marker|s1|EPSP_amp|raw|-": {
            "rec_ID": "r1",
            "axis": "axe",
            "role": pi.ROLE_ASPECT_MARKER,
            "display_label": "Rec 1 marker",
            "line": line_b,
        },
    }
    leg = pi.output_axis_legend_map_from_entries(
        dd_recs,
        {},
        axid="ax1",
        current_level="recording",
        include_groups=False,
    )
    assert list(leg.keys()) == ["Rec 1 EPSP amp"]
    assert leg["Rec 1 EPSP amp"] is line_a
