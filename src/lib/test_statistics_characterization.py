"""Characterization smoke tests for statistics.py — lock behavior before refactor.

Start minimal (5 tests). Expand per work_plans/plan_statistics_refactor.md only when a phase needs it.
"""

import pytest

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
    assert out.get("config", {}).get("type") == "t-test"
    assert out.get("config", {}).get("variant") == "paired"


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


def test_io_empty_testsets_returns_io_regression_not_anova():
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
        amp=True,
        slope=True,
        n_unit="recording",
    )
    assert out.get("config", {}).get("type") == "IO regression"
    assert out.get("results")
    assert out["results"][0].get("set_id") == "__io_regression_implicit__"


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