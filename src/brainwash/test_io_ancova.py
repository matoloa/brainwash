"""Characterization tests for textbook IO ANCOVA (PR-C/E goldens)."""

import numpy as np
import pandas as pd

from brainwash_stats.io.ancova import (
    _fit_io_ancova_pooled,
    _per_group_linregress,
    compute_io_ancova,
)
from brainwash_ui import app_context, statusbar
from load_brainwash_statistics import load_brainwash_statistics_module
from test_statistics_fixtures import bind_accessor, make_dd_groups, MinimalUistate
from ui_state_classes import UIstate

brainwash_statistics = load_brainwash_statistics_module()
compute_statistical_comparison = brainwash_statistics.compute_statistical_comparison


def _make_parallel_accessor():
    """Two groups, same slope (~1), different intercepts (classical ANCOVA setup)."""

    def accessor(g, sweeps=None, aspect="EPSP_amp", per_sweep=False):
        if not per_sweep:
            return pd.DataFrame()
        if g == "G1":
            data = {
                "rec_ID": ["r1", "r2"],
                "subject": ["s1", "s2"],
                "slice": ["1", "1"],
                1: [1.0, 1.1],
                2: [2.0, 2.1],
                3: [3.0, 3.1],
            }
        else:
            data = {
                "rec_ID": ["r3", "r4"],
                "subject": ["s3", "s4"],
                "slice": ["1", "1"],
                1: [3.0, 3.1],
                2: [4.0, 4.1],
                3: [5.0, 5.1],
            }
        return pd.DataFrame(data)

    return bind_accessor(accessor)


def _make_subject_agg_accessor():
    """Two subjects per group; two recs share a subject → n_unit=subject should be 2/group."""

    def accessor(g, sweeps=None, aspect="EPSP_amp", per_sweep=False):
        if not per_sweep:
            return pd.DataFrame()
        if g == "G1":
            # s1: two recs identical trend; s2: one rec
            return pd.DataFrame(
                {
                    "rec_ID": ["r1a", "r1b", "r2"],
                    "subject": ["s1", "s1", "s2"],
                    "slice": ["1", "1", "1"],
                    1: [1.0, 1.0, 1.2],
                    2: [2.0, 2.0, 2.2],
                    3: [3.0, 3.0, 3.2],
                }
            )
        return pd.DataFrame(
            {
                "rec_ID": ["r3a", "r3b", "r4"],
                "subject": ["s3", "s3", "s4"],
                "slice": ["1", "1", "1"],
                1: [2.0, 2.0, 2.2],
                2: [3.0, 3.0, 3.2],
                3: [4.0, 4.0, 4.2],
            }
        )

    return bind_accessor(accessor)


# --- Synthetic model goldens (pooled frame; no statsmodels required) ---


def test_fit_parallel_slopes_prefers_group_adjusted():
    g1 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0], "group": "A"})
    g2 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [3.0, 4.0, 5.0, 6.0], "group": "B"})
    pooled = pd.concat([g1, g2], ignore_index=True)
    fit = _fit_io_ancova_pooled(pooled, force0=False, alpha_slopes=0.05, do_sw=False, do_levene=False)
    assert fit["slopes_homogeneous"] is True
    assert fit["primary_contrast"] == "group_adjusted"
    assert np.isfinite(fit["p_group_ancova"])
    assert fit["p_group_ancova"] < 0.05
    assert np.isfinite(fit["p_interaction"])
    assert fit["p_interaction"] >= 0.05
    # Adjusted means at x_bar=2.5: A→2.5, B→4.5
    assert abs(fit["adjusted_means"]["A"] - 2.5) < 1e-9
    assert abs(fit["adjusted_means"]["B"] - 4.5) < 1e-9


def test_fit_different_slopes_prefers_interaction():
    g1 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0], "group": "A"})
    g2 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 3.0, 5.0, 7.0], "group": "B"})
    pooled = pd.concat([g1, g2], ignore_index=True)
    fit = _fit_io_ancova_pooled(pooled, force0=False, alpha_slopes=0.05, do_sw=False, do_levene=False)
    assert fit["slopes_homogeneous"] is False
    assert fit["primary_contrast"] == "slope_interaction"
    assert np.isfinite(fit["p_interaction"])
    assert fit["p_interaction"] < 0.05


def test_force0_linregress_matches_known_slopes():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y1 = 2.0 * x
    y2 = 0.5 * x
    s1, r1 = _per_group_linregress(x, y1, force0=True)
    s2, r2 = _per_group_linregress(x, y2, force0=True)
    assert abs(s1 - 2.0) < 1e-12
    assert abs(s2 - 0.5) < 1e-12
    assert abs(r1 - 1.0) < 1e-12
    assert abs(r2 - 1.0) < 1e-12
    # Unconstrained with intercept should also recover slope on through-origin data
    s1b, _ = _per_group_linregress(x, y1, force0=False)
    assert abs(s1b - 2.0) < 1e-12


def test_force0_interaction_detects_slope_difference():
    g1 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0], "group": "A"})
    g2 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0], "group": "B"})
    pooled = pd.concat([g1, g2], ignore_index=True)
    fit = _fit_io_ancova_pooled(pooled, force0=True, alpha_slopes=0.05, do_sw=False, do_levene=False)
    assert fit["slopes_homogeneous"] is False
    assert fit["p_interaction"] < 0.05


def test_force0_parallel_slopes_homogeneous():
    g1 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0], "group": "A"})
    g2 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0], "group": "B"})
    pooled = pd.concat([g1, g2], ignore_index=True)
    fit = _fit_io_ancova_pooled(pooled, force0=True, alpha_slopes=0.05, do_sw=False, do_levene=False)
    assert fit["slopes_homogeneous"] is True
    assert fit["p_interaction"] >= 0.05


# --- End-to-end / dispatcher / n_unit ---


def test_compute_io_ancova_config_type():
    acc = _make_parallel_accessor()
    out = compute_io_ancova(
        ["G1", "G2"],
        acc,
        uistate=MinimalUistate(),
        n_unit="recording",
        amp=True,
        slope=False,
        norm=False,
    )
    assert out["config"]["type"] == "IO ANCOVA"
    assert out["config"]["primary_contrast"] in ("group_adjusted", "slope_interaction")
    assert out["results"]
    assert out["results"][0]["set_id"] == "__io_ancova__"
    assert out["config"].get("test_sets_ignored") is True


def test_dispatcher_io_ancova_end_to_end():
    acc = _make_parallel_accessor()
    out = compute_statistical_comparison(
        groups=["G1", "G2"],
        dd_groups=make_dd_groups("G1", "G2"),
        dd_testsets={},
        get_group_testset_means_fn=acc,
        test_type="ANCOVA",
        experiment_type="io",
        uistate=MinimalUistate(),
        amp=True,
        slope=False,
        n_unit="recording",
    )
    assert out.get("config", {}).get("type") == "IO ANCOVA"
    assert "primary_contrast" in out["config"]


def test_one_group_returns_validation_error():
    acc = _make_parallel_accessor()
    out = compute_statistical_comparison(
        groups=["G1"],
        dd_groups=make_dd_groups("G1"),
        dd_testsets={},
        get_group_testset_means_fn=acc,
        test_type="ANCOVA",
        experiment_type="io",
        uistate=MinimalUistate(),
    )
    assert out.get("error") == "need at least two shown groups"
    assert out.get("results") == []


def test_n_unit_subject_counts_unique_subjects():
    acc = _make_subject_agg_accessor()
    out = compute_io_ancova(
        ["G1", "G2"],
        acc,
        uistate=MinimalUistate(),
        n_unit="subject",
        amp=True,
        slope=False,
    )
    # 2 unique subjects per group (s1,s2 and s3,s4) despite 3 recs
    assert out["config"]["group_ns"]["G1"] == 2
    assert out["config"]["group_ns"]["G2"] == 2


def test_force0_flag_propagates_to_config():
    acc = _make_parallel_accessor()
    out = compute_io_ancova(
        ["G1", "G2"],
        acc,
        uistate=MinimalUistate(),
        n_unit="recording",
        amp=True,
        slope=False,
        force_through_zero=True,
    )
    assert out["config"]["force_through_zero"] is True


# --- Statusbar / app_context dispatch (UI contract) ---


def test_app_context_only_ancova_shows_results():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2, "G2": 2},
                "primary_contrast": "group_adjusted",
                "slopes_homogeneous": True,
                "p_interaction": 0.5,
                "p_group_ancova": 0.01,
                "r2_per_group": {},
            }
        }
    ]
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.formal_test_results = formal

    u.stat_test.test_type = "ANCOVA"
    ok = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={"G1": {"group_name": "A"}, "G2": {"group_name": "B"}},
        dd_testsets={},
    )
    assert ok.state == "info"
    assert "IO ANCOVA" in (ok.text or "")

    u.stat_test.test_type = "t-test"
    bad = app_context.compute_statusbar_result(
        experiment=app_context.experiment_snapshot_from(u),
        stat_test=app_context.stat_test_snapshot_from(u),
        dd_groups={},
        dd_testsets={},
    )
    assert bad.state == "warning"
    assert "Use ANCOVA" in (bad.text or "")


def test_legacy_io_regression_statusbar_still_readable():
    formal = [
        {
            "config": {
                "type": "IO regression",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2},
                "slope_p": 0.02,
                "r2_per_group": {"G1": 0.9},
            }
        }
    ]
    result = statusbar.format_io_regression_statusbar(formal, dd_groups={"G1": {"group_name": "Ctl"}})
    assert result.state == "info"
    assert "IO ANCOVA" in (result.text or "")
