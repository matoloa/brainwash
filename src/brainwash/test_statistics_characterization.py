"""Characterization smoke tests for statistics.py — lock behavior before refactor.

Start minimal (5 tests). Expand per work_plans/plan_statistics_refactor.md only when a phase needs it.
"""

import pandas as pd
import pytest

from brainwash_stats.data import (
    _aggregate_to_unit_level,
    _align_paired_unit_values,
    _normalize_hierarchy_key,
)
from load_brainwash_statistics import load_brainwash_statistics_module

brainwash_statistics = load_brainwash_statistics_module()
compute_statistical_comparison = brainwash_statistics.compute_statistical_comparison
from test_statistics_fixtures import (
    bind_accessor,
    make_dd_groups,
    make_dd_testsets,
    make_scalar_accessor,
    MinimalUistate,
)


def test_normalize_hierarchy_key_unifies_numeric_forms():
    assert _normalize_hierarchy_key(1) == "1"
    assert _normalize_hierarchy_key(1.0) == "1"
    assert _normalize_hierarchy_key("1") == "1"
    assert _normalize_hierarchy_key("1.0") == "1"
    assert _normalize_hierarchy_key(" 2 ") == "2"


def test_aggregate_to_unit_level_collapses_mixed_subject_types():
    """Two recs with subject 1 / '1' / '1.0' must count as one subject (n=1)."""
    obs = pd.DataFrame(
        {
            "rec_ID": ["r1", "r2", "r3"],
            "subject": [1, "1", "1.0"],
            "slice": ["1", "1", 1],
            "value": [1.0, 2.0, 3.0],
        }
    )
    agg = _aggregate_to_unit_level(obs, "subject")
    assert len(agg) == 1
    assert float(agg.iloc[0]["value"]) == pytest.approx(2.0)


def _ttest_fixture():
    g1_vals = [("r1", "s1", 1.0), ("r2", "s1", 1.2), ("r3", "s2", 1.1)]
    g2_vals = [("r4", "s3", 2.5), ("r5", "s3", 2.7), ("r6", "s4", 2.6)]
    return {
        "groups": ["G1", "G2"],
        "dd_groups": make_dd_groups("G1", "G2"),
        "dd_testsets": make_dd_testsets("TS1"),
        "accessor": make_scalar_accessor({"G1": g1_vals, "G2": g2_vals}),
    }


def test_error_no_shown_groups():
    out = compute_statistical_comparison(
        groups=[],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1"),
        get_group_testset_means_fn=make_scalar_accessor({}),
    )
    assert out.get("error") == "no shown groups"
    assert out.get("results") == []


def test_error_no_shown_test_sets_non_io():
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
        get_group_testset_means_fn=make_scalar_accessor({}),
        experiment_type="time",
    )
    assert out.get("error") == "no shown test sets"
    assert out.get("results") == []


def test_align_paired_unit_values_inner_join_and_drops():
    obs1 = pd.DataFrame(
        {
            "rec_ID": ["r1", "r2", "r3"],
            "subject": ["s1", "s2", "s3"],
            "slice": ["1", "1", "1"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    # s3 only in set1; s4 only in set2; s1/s2 complete
    obs2 = pd.DataFrame(
        {
            "rec_ID": ["r1", "r2", "r4"],
            "subject": ["s1", "s2", "s4"],
            "slice": ["1", "1", "1"],
            "value": [1.5, 2.5, 4.0],
        }
    )
    aligned = _align_paired_unit_values(obs1, obs2, n_unit="subject")
    assert aligned["n_pairs"] == 2
    assert aligned["n_dropped"] == 2
    assert list(aligned["v1"]) == pytest.approx([1.0, 2.0])
    assert list(aligned["v2"]) == pytest.approx([1.5, 2.5])
    units = {d["unit"] for d in aligned["dropped"]}
    assert units == {"s3", "s4"}


def test_align_paired_unit_values_recording_keys():
    obs1 = pd.DataFrame({"rec_ID": ["a", "b"], "subject": ["s1", "s1"], "value": [1.0, 2.0]})
    obs2 = pd.DataFrame({"rec_ID": ["b", "c"], "subject": ["s1", "s2"], "value": [3.0, 4.0]})
    aligned = _align_paired_unit_values(obs1, obs2, n_unit="recording")
    assert aligned["n_pairs"] == 1
    assert aligned["v1"][0] == pytest.approx(2.0)
    assert aligned["v2"][0] == pytest.approx(3.0)
    assert aligned["n_dropped"] == 2


def test_paired_ttest_returns_results_and_config():
    g1_vals = [("r1", "s1", 1.0), ("r2", "s1", 1.2), ("r3", "s2", 1.1)]
    accessor = make_scalar_accessor({"G1": g1_vals})
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        get_group_testset_means_fn=accessor,
        test_type="t-test",
        variant="paired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out
    assert out.get("results")
    assert len(out["results"]) == 1
    res = out["results"][0]
    assert out.get("config", {}).get("type") == "t-test"
    assert out.get("config", {}).get("variant") == "paired"
    assert res.get("n_pairs") == 2  # s1, s2 after subject aggregation
    assert res.get("n_dropped", 0) == 0
    assert "sweeps2" in res


def test_paired_ttest_drops_incomplete_units():
    """Units only in one test set are excluded; n_pairs reflects complete cases."""

    def accessor(g, sweeps, aspect="EPSP_amp", per_sweep=False):
        sweeps = list(sweeps or [])
        # TS1 default sweeps [1,2,3]; TS2 we override in dd with [10,11,12]
        if 10 in sweeps:
            rows = [
                ("r1", "s1", 2.0),
                ("r2", "s2", 2.2),
                # s3 only in set2
                ("r4", "s3", 9.0),
            ]
        else:
            rows = [
                ("r1", "s1", 1.0),
                ("r2", "s2", 1.1),
                # s4 only in set1
                ("r3", "s4", 0.5),
            ]
        return pd.DataFrame(
            [{"rec_ID": rid, "subject": sub, "slice": "1", "value": val} for rid, sub, val in rows]
        )

    dd_ts = {
        "TS1": {"show": True, "sweeps": [1, 2, 3], "set_name": "pre"},
        "TS2": {"show": True, "sweeps": [10, 11, 12], "set_name": "post"},
    }
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=dd_ts,
        get_group_testset_means_fn=accessor,
        test_type="t-test",
        variant="paired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out
    assert len(out["results"]) == 1
    res = out["results"][0]
    assert res["n_pairs"] == 2
    assert res["n1"] == 2 and res["n2"] == 2
    assert res["n_dropped"] == 2
    drop_units = {d["unit"] for d in res.get("paired_dropped") or []}
    assert drop_units == {"s3", "s4"}
    assert "vs" in (res.get("set_name") or "")


def test_unpaired_ttest_returns_results_and_config():
    fx = _ttest_fixture()
    out = compute_statistical_comparison(
        groups=fx["groups"],
        dd_groups=fx["dd_groups"],
        dd_testsets=fx["dd_testsets"],
        get_group_testset_means_fn=fx["accessor"],
        test_type="t-test",
        variant="unpaired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out
    assert out.get("results")
    assert out.get("config", {}).get("type") == "t-test"


def test_io_ancova_empty_testsets():
    g1 = [("rec_G1_1", "s1", 1.0), ("rec_G1_2", "s1", 1.5)]
    g2 = [("rec_G2_1", "s2", 2.0), ("rec_G2_2", "s2", 2.5)]
    accessor = bind_accessor(make_scalar_accessor({"G1": g1, "G2": g2}))
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
        get_group_testset_means_fn=accessor,
        test_type="ANCOVA",
        experiment_type="io",
        uistate=MinimalUistate(),
        amp=True,
        slope=True,
        n_unit="recording",
    )
    assert out.get("config", {}).get("type") == "IO ANCOVA"
    assert out.get("config", {}).get("test_sets_ignored") is True
    assert out.get("results")
    assert out["results"][0].get("set_id") == "__io_ancova__"


def test_io_ancova_ignores_shown_test_sets():
    """PR-B policy: shown test sets must not fall through to time ANOVA."""
    g1 = [("rec_G1_1", "s1", 1.0), ("rec_G1_2", "s1", 1.5)]
    g2 = [("rec_G2_1", "s2", 2.0), ("rec_G2_2", "s2", 2.5)]
    accessor = bind_accessor(make_scalar_accessor({"G1": g1, "G2": g2}))
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1", sweeps=[1, 2]),
        get_group_testset_means_fn=accessor,
        test_type="ANCOVA",
        experiment_type="io",
        uistate=MinimalUistate(),
        amp=True,
        slope=True,
        n_unit="recording",
    )
    assert "error" not in out
    assert out.get("config", {}).get("type") == "IO ANCOVA"
    assert out["results"][0].get("set_id") == "__io_ancova__"


def test_io_rejects_non_ancova_test_type():
    g1 = [("rec_G1_1", "s1", 1.0), ("rec_G1_2", "s1", 1.5)]
    g2 = [("rec_G2_1", "s2", 2.0), ("rec_G2_2", "s2", 2.5)]
    accessor = bind_accessor(make_scalar_accessor({"G1": g1, "G2": g2}))
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
        get_group_testset_means_fn=accessor,
        test_type="ANOVA",
        experiment_type="io",
        uistate=MinimalUistate(),
    )
    assert out.get("error") == "IO experiment requires ANCOVA"


def test_io_ancova_radio_required_in_validation():
    """Non-IO ANCOVA is not implemented; IO+ANCOVA is allowed (PR-A/B)."""
    g1 = [("rec_G1_1", "s1", 1.0), ("rec_G1_2", "s1", 1.5)]
    g2 = [("rec_G2_1", "s2", 2.0), ("rec_G2_2", "s2", 2.5)]
    accessor = bind_accessor(make_scalar_accessor({"G1": g1, "G2": g2}))
    out_non_io = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
        get_group_testset_means_fn=accessor,
        test_type="ANCOVA",
        experiment_type="time",
    )
    assert out_non_io.get("not_implemented") == "ANCOVA"


def test_not_implemented_test_type():
    fx = _ttest_fixture()
    out = compute_statistical_comparison(
        groups=fx["groups"],
        dd_groups=fx["dd_groups"],
        dd_testsets=fx["dd_testsets"],
        get_group_testset_means_fn=fx["accessor"],
        test_type="Kruskal-Wallis",
    )
    assert out.get("not_implemented") == "Kruskal-Wallis"
    assert out.get("results") == []


def test_cluster_perm_between_groups_smoke():
    pytest.importorskip("mne")
    g1_vals = [("r1", "s1", 1.0), ("r2", "s1", 1.2), ("r3", "s2", 1.1)]
    g2_vals = [("r4", "s3", 2.5), ("r5", "s3", 2.7), ("r6", "s4", 2.6)]
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1", sweeps=[1, 2, 3]),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1_vals, "G2": g2_vals}),
        test_type="Cluster perm.",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out
    assert out.get("config", {}).get("test_type") == "Cluster perm."
    assert out.get("results")