"""Characterization tests for textbook IO ANCOVA (PR-C)."""

import numpy as np
import pandas as pd

from brainwash_stats.io.ancova import compute_io_ancova, _fit_io_ancova_pooled
from load_brainwash_statistics import load_brainwash_statistics_module
from test_statistics_fixtures import bind_accessor, make_dd_groups, make_scalar_accessor, MinimalUistate

brainwash_statistics = load_brainwash_statistics_module()
compute_statistical_comparison = brainwash_statistics.compute_statistical_comparison


def _make_parallel_accessor():
    """Two groups, same slope, different intercepts (classical ANCOVA setup)."""
    # x = 1,2,3 for two units each group; y = slope*x + intercept
    # G1 intercept 0, G2 intercept 2, slope 1
    rows = {
        "G1": [("r1", "s1", 1.0), ("r2", "s1", 2.0), ("r3", "s2", 1.0), ("r4", "s2", 2.0)],
        "G2": [("r5", "s3", 3.0), ("r6", "s3", 4.0), ("r7", "s4", 3.0), ("r8", "s4", 4.0)],
    }
    # make_scalar_accessor with per_sweep builds synthetic columns — use custom accessor for XY control
    def accessor(g, sweeps=None, aspect="EPSP_amp", per_sweep=False):
        if not per_sweep:
            return pd.DataFrame()
        # Wide: rec_ID, subject, 1, 2, 3 as y at x≈1,2,3
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


def test_fit_parallel_slopes_prefers_group_adjusted():
    # Same slope, different intercept
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


def test_fit_different_slopes_prefers_interaction():
    g1 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0], "group": "A"})
    g2 = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 3.0, 5.0, 7.0], "group": "B"})  # slope 2
    pooled = pd.concat([g1, g2], ignore_index=True)
    fit = _fit_io_ancova_pooled(pooled, force0=False, alpha_slopes=0.05, do_sw=False, do_levene=False)
    assert fit["slopes_homogeneous"] is False
    assert fit["primary_contrast"] == "slope_interaction"
    assert np.isfinite(fit["p_interaction"])
    assert fit["p_interaction"] < 0.05


def test_compute_io_ancova_config_type():
    acc = _make_parallel_accessor()
    # Monkey-patch: xy_pairs needs per_sweep wide with real x — use rank fallback from sweep
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
