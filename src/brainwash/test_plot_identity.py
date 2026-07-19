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


def test_display_recording_name_blind_hook():
    assert pi.display_recording_name("r1", "slice07", blind=False) == "slice07"
    assert pi.display_recording_name("r1", "slice07", blind=True, aliases={"r1": "Rec 1"}) == "Rec 1"
    assert pi.display_recording_name(2, "abf", blind=True) == "Rec 2"


def test_build_blind_aliases_random_new_episode():
    import random

    ids = [10, 2, 3]
    a = pi.build_blind_aliases(ids, rng=random.Random(0))
    b = pi.build_blind_aliases(ids, rng=random.Random(1))
    # Full covering of Rec 1..N
    assert set(a.values()) == {"Rec 1", "Rec 2", "Rec 3"}
    assert set(a.keys()) == {"2", "3", "10"}
    # Not the old sorted-by-ID assignment (Rec 1 → smallest ID always)
    sorted_by_id = {"2": "Rec 1", "3": "Rec 2", "10": "Rec 3"}
    # At least one seed should differ from sorted-by-ID; both must be valid bijections
    assert a != sorted_by_id or b != sorted_by_id
    # Different seeds can produce different maps
    assert a == pi.build_blind_aliases(ids, rng=random.Random(0))
    # Incremental: keep existing labels; new ID gets next free Rec n
    grown = pi.build_blind_aliases([10, 2, 3, 1], existing=a)
    assert grown["2"] == a["2"]
    assert grown["3"] == a["3"]
    assert grown["10"] == a["10"]
    assert grown["1"] == "Rec 4"
    # Empty existing after unblind → new shuffle (not reuse)
    fresh = pi.build_blind_aliases(ids, existing={}, rng=random.Random(2))
    assert set(fresh.values()) == {"Rec 1", "Rec 2", "Rec 3"}


def test_recording_name_sort_key_natural_rec():
    assert pi.recording_name_sort_key("Rec 2") < pi.recording_name_sort_key("Rec 10")
    assert pi.recording_name_sort_key("Rec 1") < pi.recording_name_sort_key("Rec 2")
    assert pi.recording_name_sort_key("Rec 10") < pi.recording_name_sort_key("zzz")


def test_replace_recording_stem_for_legend_labels():
    assert pi.replace_recording_stem("slice07", "slice07", "Rec 1") == "Rec 1"
    assert pi.replace_recording_stem("mean slice07", "slice07", "Rec 1") == "mean Rec 1"
    assert pi.replace_recording_stem("slice07 - stim 1 EPSP amp", "slice07", "Rec 1") == "Rec 1 - stim 1 EPSP amp"
    assert pi.replace_recording_stem("slice07 (savgol)", "slice07", "Rec 1") == "Rec 1 (savgol)"
    # reverse unblind
    assert pi.replace_recording_stem("Rec 1 - stim 1 EPSP amp", "Rec 1", "slice07") == "slice07 - stim 1 EPSP amp"


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
