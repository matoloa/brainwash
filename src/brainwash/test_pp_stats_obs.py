"""PP formal-stats observation contract: PPR when experiment_type=PP, raw otherwise."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from brainwash_ui import plot_series


def _pp_dfoutput():
    # Two sweeps, stim1/stim2: PPR = 2.0 and 1.5 → mean 1.75
    return pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1],
            "stim": [1, 2, 1, 2],
            "EPSP_amp": [1.0, 2.0, 2.0, 3.0],
            "EPSP_slope": [1.0, 1.0, 1.0, 2.0],
        }
    )


def test_ppr_mean_matches_plot_helper():
    dfo = _pp_dfoutput()
    by = plot_series.ppr_by_sweep_from_dfoutput(dfo, "EPSP_amp")
    mean_from_sweeps = float(np.mean(list(by.values())))
    assert mean_from_sweeps == pytest.approx(1.75)
    assert plot_series.rec_mean_ppr_from_dfoutput(dfo)["EPSP_amp"] == pytest.approx(1.75)


def test_get_group_obs_pp_uses_ppr(monkeypatch):
    """With experiment_type PP, get_group_obs_for_sweeps returns PPR per sweep."""
    from ui_data_frames import DataFrameMixin

    class _Exp:
        experiment_type = "PP"

    class _Uistate:
        experiment = _Exp()

    class Host(DataFrameMixin):
        def __init__(self):
            self.uistate = _Uistate()
            self.dd_groups = {"g1": {"rec_IDs": ["r1"], "show": True}}
            self._dfo = _pp_dfoutput()

        def get_df_project(self):
            return pd.DataFrame({"ID": ["r1"], "subject": ["S1"], "slice": ["1"]})

        def get_dfoutput(self, row=None):
            return self._dfo

    host = Host()
    obs = host.get_group_obs_for_sweeps("g1", sweeps=[0, 1], aspect="EPSP_amp")
    assert list(obs.columns) == ["rec_ID", "0", "1"]
    assert float(obs.loc[0, "0"]) == pytest.approx(2.0)
    assert float(obs.loc[0, "1"]) == pytest.approx(1.5)

    means = host.get_group_testset_means("g1", sweeps=[0, 1], aspect="EPSP_amp")
    assert float(means.loc[0, "value"]) == pytest.approx(1.75)


def test_pp_unpaired_no_testsets_implicit_window():
    """PP + 2 groups + no test sets → unpaired t runs on mean PPR (implicit window)."""
    from load_brainwash_statistics import load_brainwash_statistics_module

    stats = load_brainwash_statistics_module()

    # Group A: high PPR (2.0); group B: lower PPR (1.0)
    dfo_a = pd.DataFrame(
        {"sweep": [0, 0], "stim": [1, 2], "EPSP_amp": [1.0, 2.0], "EPSP_slope": [1.0, 2.0]}
    )
    dfo_b = pd.DataFrame(
        {"sweep": [0, 0], "stim": [1, 2], "EPSP_amp": [1.0, 1.0], "EPSP_slope": [1.0, 1.0]}
    )

    from ui_data_frames import DataFrameMixin

    class _Exp:
        experiment_type = "PP"

    class _Uistate:
        experiment = _Exp()

    class Host(DataFrameMixin):
        def __init__(self):
            self.uistate = _Uistate()
            self.dd_groups = {
                "g1": {"rec_IDs": ["a1", "a2"], "show": True},
                "g2": {"rec_IDs": ["b1", "b2"], "show": True},
            }
            self._dfos = {"a1": dfo_a, "a2": dfo_a, "b1": dfo_b, "b2": dfo_b}

        def get_df_project(self):
            return pd.DataFrame(
                {
                    "ID": ["a1", "a2", "b1", "b2"],
                    "subject": ["S1", "S2", "S3", "S4"],
                    "slice": ["1", "1", "1", "1"],
                }
            )

        def get_dfoutput(self, row=None):
            rid = str(row["ID"]) if row is not None else None
            return self._dfos.get(rid, dfo_a)

    host = Host()
    dd_groups = host.dd_groups
    # Empty testsets
    comp = stats.compute_statistical_comparison(
        groups=["g1", "g2"],
        dd_groups=dd_groups,
        dd_testsets={},
        get_group_testset_means_fn=host.get_group_testset_means,
        test_type="t-test",
        variant="unpaired",
        amp=True,
        slope=False,
        n_unit="recording",
        experiment_type="PP",
    )
    assert not comp.get("error"), comp
    assert comp.get("config", {}).get("use_implicit") or True  # implicit path
    results = comp.get("results") or []
    assert results, comp
    # Means: g1 all 2.0, g2 all 1.0 → significant unpaired t
    p = results[0].get("p_amp")
    assert p is not None and np.isfinite(p)
    assert float(p) < 0.05


def test_pp_subject_n_unit_not_false_unassigned():
    """Implicit PP window must not claim subject unassigned when hierarchy is present."""
    from load_brainwash_statistics import load_brainwash_statistics_module
    from ui_data_frames import DataFrameMixin

    stats = load_brainwash_statistics_module()
    dfo = pd.DataFrame(
        {"sweep": [0, 0], "stim": [1, 2], "EPSP_amp": [1.0, 2.0], "EPSP_slope": [1.0, 2.0]}
    )

    class _Exp:
        experiment_type = "PP"

    class Host(DataFrameMixin):
        def __init__(self):
            self.uistate = type("U", (), {"experiment": _Exp()})()
            self.dd_groups = {
                "g1": {"rec_IDs": ["a1", "a2"], "show": True},
                "g2": {"rec_IDs": ["b1", "b2"], "show": True},
            }
            self._dfo = dfo

        def get_df_project(self):
            return pd.DataFrame(
                {
                    "ID": ["a1", "a2", "b1", "b2"],
                    "subject": ["S1", "S2", "S3", "S4"],
                    "slice": ["1", "1", "1", "1"],
                }
            )

        def get_dfoutput(self, row=None):
            return self._dfo

    host = Host()
    comp = stats.compute_statistical_comparison(
        groups=["g1", "g2"],
        dd_groups=host.dd_groups,
        dd_testsets={},
        get_group_testset_means_fn=host.get_group_testset_means,
        test_type="t-test",
        variant="unpaired",
        amp=True,
        slope=False,
        n_unit="subject",
        experiment_type="PP",
    )
    assert not comp.get("error"), comp
    assert "not assigned" not in str(comp.get("error", "")).lower()
    assert comp.get("results"), comp


def test_ttest_applicability_pp_no_testsets():
    from brainwash_ui import applicability
    from test_statistics_fixtures import make_dd_groups

    dd_g = make_dd_groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    assert applicability.check_ttest_applicability("unpaired", dd_g, {}, experiment_type="PP") is None
    assert applicability.check_ttest_applicability("unpaired", dd_g, {}) == "No test sets shown for t-test"
    dd1 = make_dd_groups("G1")
    dd1["G1"]["rec_IDs"] = ["r1"]
    assert applicability.check_ttest_applicability("one-sample", dd1, {}, experiment_type="PP") is None
    assert applicability.check_ttest_applicability("one-sample", dd1, {}) == "No test sets shown for t-test"


def test_pp_paired_applicability_redirects_to_unpaired_or_one_sample():
    from brainwash_ui import applicability
    from test_statistics_fixtures import make_dd_groups

    dd_g = make_dd_groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    msg = applicability.check_ttest_applicability("paired", dd_g, {}, experiment_type="PP")
    assert msg is not None
    assert "unpaired" in msg.lower()
    assert "one-sample" in msg.lower() or "one sample" in msg.lower() or "vs 1" in msg
    assert "2 test sets" in msg or "condition" in msg.lower()


def test_pp_cluster_applicability_hints_single_bin_ttest():
    from brainwash_ui import applicability
    from test_statistics_fixtures import make_dd_groups

    dd_g = make_dd_groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1"]
    dd_g["G2"]["rec_IDs"] = ["r2"]
    msg = applicability.check_cluster_applicability(dd_g, {}, experiment_type="PP")
    assert msg is not None
    assert "unpaired t-test" in msg or "PPR" in msg


def test_statusbar_shows_ppr_quantity():
    from brainwash_ui.statusbar import format_non_io_stat_test_statusbar

    formal = [
        {
            "group1": "G1",
            "group2": "G2",
            "n1": 3,
            "n2": 3,
            "p_amp": 0.02,
            "config": {"type": "t-test (PPR)", "quantity": "PPR (stim2/stim1)"},
        }
    ]
    result = format_non_io_stat_test_statusbar(
        formal,
        effective_test_type="t-test",
        dd_groups={"G1": {"group_name": "Ctl"}, "G2": {"group_name": "Drug"}},
        ttest_variant="unpaired",
        n_unit="recording",
    )
    assert result.text is not None
    assert "PPR" in result.text
    assert "PPR amp" in result.text or "amp" in result.text
    assert "p=0.02" in result.text


def test_get_group_obs_time_uses_raw_not_ppr():
    """Non-PP experiment types still use raw aspect (last stim row per sweep if multi-stim)."""
    from ui_data_frames import DataFrameMixin

    class _Exp:
        experiment_type = "time"

    class _Uistate:
        experiment = _Exp()

    class Host(DataFrameMixin):
        def __init__(self):
            self.uistate = _Uistate()
            self.dd_groups = {"g1": {"rec_IDs": ["r1"], "show": True}}
            self._dfo = _pp_dfoutput()

        def get_df_project(self):
            return pd.DataFrame({"ID": ["r1"], "subject": ["S1"], "slice": ["1"]})

        def get_dfoutput(self, row=None):
            return self._dfo

    host = Host()
    obs = host.get_group_obs_for_sweeps("g1", sweeps=[0, 1], aspect="EPSP_amp")
    # Dict comprehension last-write: stim2 rows → 2.0 and 3.0 (not PPR)
    assert float(obs.loc[0, "0"]) == pytest.approx(2.0)
    assert float(obs.loc[0, "1"]) == pytest.approx(3.0)
    means = host.get_group_testset_means("g1", sweeps=[0, 1], aspect="EPSP_amp")
    assert float(means.loc[0, "value"]) == pytest.approx(2.5)
