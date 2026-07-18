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


def test_friedman_happy_path_and_sweeps():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.2), ("r3", "s3", 1.1)]
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1", "TS2", "TS3"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1}),
        test_type="Friedman",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out, out
    assert out.get("results")
    res = out["results"][0]
    assert res.get("set_id") == "__friedman_rm_omnibus__"
    assert res.get("sweeps")
    assert res.get("n_pairs") == 3
    assert "p_amp" in res


def test_friedman_rejects_two_groups():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.1)]
    g2 = [("r3", "s3", 2.0), ("r4", "s4", 2.1)]
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1", "TS2", "TS3"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1, "G2": g2}),
        test_type="Friedman",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert out.get("error") == "Friedman requires exactly 1 group"
    assert not out.get("results")


def test_friedman_rejects_two_testsets():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.1), ("r3", "s3", 1.2)]
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1}),
        test_type="Friedman",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert out.get("error") == "Friedman requires at least 3 shown test sets"
    assert not out.get("results")


def test_friedman_drops_incomplete_units():
    def accessor(g, sweeps, aspect="EPSP_amp", per_sweep=False):
        sw = list(sweeps or [])
        if 10 in sw:
            rows = [("r1", "s1", 2.0), ("r2", "s2", 2.1)]  # s3 missing
        elif 20 in sw:
            rows = [("r1", "s1", 3.0), ("r2", "s2", 3.1), ("r3", "s3", 3.2)]
        else:
            rows = [("r1", "s1", 1.0), ("r2", "s2", 1.1), ("r3", "s3", 1.2)]
        return pd.DataFrame(
            [{"rec_ID": rid, "subject": sub, "slice": "1", "value": val} for rid, sub, val in rows]
        )

    dd_ts = {
        "A": {"show": True, "sweeps": [1, 2, 3], "set_name": "pre"},
        "B": {"show": True, "sweeps": [10, 11, 12], "set_name": "mid"},
        "C": {"show": True, "sweeps": [20, 21, 22], "set_name": "post"},
    }
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=dd_ts,
        get_group_testset_means_fn=accessor,
        test_type="Friedman",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out, out
    res = out["results"][0]
    assert res["n_pairs"] == 2
    assert res["n_dropped"] >= 1
    drop_units = {d["unit"] for d in res.get("paired_dropped") or []}
    assert "s3" in drop_units


def test_align_multi_condition_unit_values():
    from brainwash_stats.data import _align_multi_condition_unit_values

    a = pd.DataFrame({"subject": ["s1", "s2", "s3"], "value": [1.0, 2.0, 3.0]})
    b = pd.DataFrame({"subject": ["s1", "s2"], "value": [1.5, 2.5]})
    c = pd.DataFrame({"subject": ["s1", "s2", "s4"], "value": [2.0, 3.0, 9.0]})
    aligned = _align_multi_condition_unit_values([a, b, c], n_unit="subject")
    assert aligned["n_pairs"] == 2
    assert aligned["n_dropped"] >= 2
    assert len(aligned["values"]) == 3
    assert list(aligned["values"][0]) == pytest.approx([1.0, 2.0])


def test_wilcoxon_paired_returns_results_and_n_pairs():
    g1_vals = [("r1", "s1", 1.0), ("r2", "s2", 1.2), ("r3", "s3", 1.1)]
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1_vals}),
        test_type="Wilcoxon",
        variant="paired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out, out
    assert len(out.get("results") or []) == 1
    res = out["results"][0]
    assert res.get("n_pairs") == 3
    assert res.get("n_dropped", 0) == 0
    assert "p_amp" in res
    assert "sweeps2" in res
    assert out.get("config", {}).get("variant") == "paired"


def test_wilcoxon_one_sample_rejects_two_groups():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.2)]
    g2 = [("r3", "s3", 2.0), ("r4", "s4", 2.1)]
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1, "G2": g2}),
        test_type="Wilcoxon",
        variant="one-sample",
        amp=True,
        slope=False,
        n_unit="subject",
        ref=0.0,
    )
    assert "error" in out
    assert "one-sample Wilcoxon" in out["error"]
    assert "t-test" not in out["error"]


def test_wilcoxon_one_sample_ok_one_group():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.2), ("r3", "s3", 1.1)]
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1}),
        test_type="Wilcoxon",
        variant="one-sample",
        amp=True,
        slope=False,
        n_unit="subject",
        ref=0.0,
    )
    assert "error" not in out, out
    assert out.get("results")
    assert "p_amp" in out["results"][0]


def test_wilcoxon_paired_multi_group_error_says_wilcoxon():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.1)]
    g2 = [("r3", "s3", 2.0), ("r4", "s4", 2.1)]
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1, "G2": g2}),
        test_type="Wilcoxon",
        variant="paired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert out.get("error") == "paired Wilcoxon requires exactly 1 group"


def test_anova_multi_group_ignores_leftover_paired_variant():
    """t-test 'paired' radio must not blank multi-group one-way ANOVA."""
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.1), ("r3", "s3", 1.05)]
    g2 = [("r4", "s4", 2.5), ("r5", "s5", 2.6), ("r6", "s6", 2.55)]
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets=make_dd_testsets("TS1"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1, "G2": g2}),
        test_type="ANOVA",
        variant="paired",  # leftover UI radio
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out, out
    assert out.get("results")
    res = out["results"][0]
    assert "p_amp" in res
    assert isinstance(res["p_amp"], float)
    assert res.get("sweeps")  # markers need x position


def test_anova_rm_emits_sweeps_for_markers():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.2), ("r3", "s3", 1.1)]
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1}),
        test_type="ANOVA",
        variant="paired",
        amp=True,
        slope=False,
        n_unit="subject",
    )
    assert "error" not in out, out
    assert out.get("results")
    res = out["results"][0]
    assert res.get("set_id") == "__anova_rm_omnibus__"
    assert res.get("sweeps")
    assert "p_amp" in res


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


def test_cluster_to_matrix_ignores_hierarchy_and_sorts_sweeps():
    from brainwash_stats.formal_tests.cluster_perm import _sweep_columns, _to_matrix

    df = pd.DataFrame(
        {
            "rec_ID": ["a", "b"],
            "subject": ["s1", "s2"],
            "slice": ["1", "1"],
            "3": [3.0, 3.0],
            "1": [1.0, 1.0],
            "2": [2.0, 2.0],
        }
    )
    cols = _sweep_columns(df)
    assert cols == ["1", "2", "3"]
    mat = _to_matrix(df)
    assert mat.shape == (2, 3)
    assert list(mat[0]) == pytest.approx([1.0, 2.0, 3.0])


def test_cluster_align_paired_rec_order():
    from brainwash_stats.formal_tests.cluster_perm import _align_paired_rec_matrices

    df1 = pd.DataFrame(
        {
            "rec_ID": ["r1", "r2", "r3"],
            "subject": ["s1", "s2", "s3"],
            "1": [1.0, 2.0, 3.0],
            "2": [1.1, 2.1, 3.1],
        }
    )
    # Different absolute sweeps; reverse rec order; r3 only in set1, r4 only in set2
    df2 = pd.DataFrame(
        {
            "rec_ID": ["r2", "r1", "r4"],
            "subject": ["s2", "s1", "s4"],
            "10": [20.0, 10.0, 40.0],
            "11": [21.0, 11.0, 41.0],
        }
    )
    aligned = _align_paired_rec_matrices(df1, df2)
    assert aligned["n_pairs"] == 2
    assert aligned["n_dropped"] >= 2
    assert aligned["X1"].shape == (2, 2)
    rows = {tuple(aligned["X1"][i]): tuple(aligned["X2"][i]) for i in range(2)}
    assert rows[(1.0, 1.1)] == pytest.approx((10.0, 11.0))
    assert rows[(2.0, 2.1)] == pytest.approx((20.0, 21.0))


def test_cluster_perm_between_groups_smoke():
    import math

    pytest.importorskip("mne")
    g1_vals = [("r1", "s1", 1.0), ("r2", "s2", 1.2), ("r3", "s3", 1.1)]
    g2_vals = [("r4", "s4", 2.5), ("r5", "s5", 2.7), ("r6", "s6", 2.6)]
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
    assert "error" not in out, out
    assert out.get("config", {}).get("test_type") == "Cluster perm."
    assert out.get("config", {}).get("variant") == "between"
    assert out.get("results")
    res = out["results"][0]
    assert res.get("cluster_mode") == "between"
    p = res.get("p_amp")
    assert isinstance(p, (int, float)) and (math.isfinite(p) or math.isnan(p))


def test_cluster_rejects_three_groups():
    g1 = [("r1", "s1", 1.0), ("r2", "s2", 1.1)]
    g2 = [("r3", "s3", 2.0), ("r4", "s4", 2.1)]
    g3 = [("r5", "s5", 3.0), ("r6", "s6", 3.1)]
    out = compute_statistical_comparison(
        groups=["G1", "G2", "G3"],
        dd_groups=make_dd_groups("G1", "G2", "G3"),
        dd_testsets=make_dd_testsets("TS1", sweeps=[1, 2, 3]),
        get_group_testset_means_fn=make_scalar_accessor({"G1": g1, "G2": g2, "G3": g3}),
        test_type="Cluster perm.",
        amp=True,
        slope=False,
    )
    assert "error" in out
    assert "3 groups" in out["error"] or "does not support 3" in out["error"]
    assert "Valid layouts" in out["error"]
    assert not out.get("results")


def test_cluster_paired_align_and_drops():
    pytest.importorskip("mne")

    def accessor_same(g, sweeps, aspect="EPSP_amp", per_sweep=False):
        n = getattr(accessor_same, "_n", 0)
        accessor_same._n = n + 1
        if n % 2 == 0:
            rows = [
                {"rec_ID": "r1", "subject": "s1", "slice": "1", "1": 0.5, "2": 0.6, "3": 0.7},
                {"rec_ID": "r2", "subject": "s2", "slice": "1", "1": 1.5, "2": 1.6, "3": 1.7},
                {"rec_ID": "r4", "subject": "s4", "slice": "1", "1": 8.0, "2": 8.1, "3": 8.2},
            ]
        else:
            rows = [
                {"rec_ID": "r2", "subject": "s2", "slice": "1", "1": 2.5, "2": 2.6, "3": 2.7},
                {"rec_ID": "r1", "subject": "s1", "slice": "1", "1": 1.0, "2": 1.1, "3": 1.2},
                {"rec_ID": "r3", "subject": "s3", "slice": "1", "1": 9.0, "2": 9.1, "3": 9.2},
            ]
        return pd.DataFrame(rows)

    dd = {
        "A": {"show": True, "sweeps": [1, 2, 3], "set_name": "pre"},
        "B": {"show": True, "sweeps": [1, 2, 3], "set_name": "post"},
    }
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets=dd,
        get_group_testset_means_fn=accessor_same,
        test_type="Cluster perm.",
        amp=True,
        slope=False,
        n_unit="recording",
    )
    assert "error" not in out, out
    res = out["results"][0]
    assert res.get("cluster_mode") == "paired"
    assert res.get("n_pairs") == 2
    assert res.get("n_dropped") >= 2
    units = {d["unit"] for d in res.get("paired_dropped") or []}
    assert "r3" in units or "r4" in units
    assert isinstance(res.get("p_amp"), (int, float))

