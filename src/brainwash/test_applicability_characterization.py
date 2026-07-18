"""Characterization tests for brainwash_ui.applicability — lock warning strings."""

from brainwash_ui import applicability
from test_statistics_fixtures import make_dd_groups, make_dd_testsets


def _groups(*ids: str):
    return make_dd_groups(*ids)


def test_ttest_unpaired_needs_two_groups():
    dd_g = _groups("G1")
    assert applicability.check_ttest_applicability("unpaired", dd_g, make_dd_testsets("TS1")) == (
        "t-test requires 2 group(s) with data"
    )


def test_ttest_paired_needs_two_testsets():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    assert applicability.check_ttest_applicability("paired", dd_g, make_dd_testsets("TS1")) == (
        "Paired t-test requires exactly 2 test sets"
    )


def test_ttest_paired_needs_exactly_one_group():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    dd_ts = make_dd_testsets("TS1", "TS2")
    assert applicability.check_ttest_applicability("paired", dd_g, dd_ts) == (
        "Paired t-test requires exactly 1 group with data"
    )


def test_ttest_paired_ok_one_group_two_sets():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_ts = make_dd_testsets("TS1", "TS2")
    assert applicability.check_ttest_applicability("paired", dd_g, dd_ts) is None


def test_ttest_paired_needs_two_recordings():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1"]
    dd_ts = make_dd_testsets("TS1", "TS2")
    assert applicability.check_ttest_applicability("paired", dd_g, dd_ts) == (
        "Paired t-test requires N ≥ 2 recordings per group"
    )


def test_ttest_no_groups():
    assert applicability.check_ttest_applicability("unpaired", None, {}) == "No groups defined for t-test"


def test_ttest_one_sample_needs_exactly_one_group():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    assert applicability.check_ttest_applicability("one-sample", dd_g, make_dd_testsets("TS1")) == (
        "One-sample t-test requires exactly 1 group with data"
    )


def test_wilcoxon_paired_messages_not_ttest():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    msg = applicability.check_wilcoxon_applicability("paired", dd_g, make_dd_testsets("TS1", "TS2"))
    assert msg == "Paired Wilcoxon requires exactly 1 group with data"
    assert "t-test" not in msg.lower()


def test_wilcoxon_paired_ok_one_group_two_sets():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    assert applicability.check_wilcoxon_applicability("paired", dd_g, make_dd_testsets("TS1", "TS2")) is None


def test_wilcoxon_one_sample_needs_exactly_one_group():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    msg = applicability.check_wilcoxon_applicability("one-sample", dd_g, make_dd_testsets("TS1"))
    assert msg == "One-sample Wilcoxon requires exactly 1 group with data"
    assert "t-test" not in msg.lower()


def test_wilcoxon_one_sample_ok():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    assert applicability.check_wilcoxon_applicability("one-sample", dd_g, make_dd_testsets("TS1")) is None


def test_warning_for_wilcoxon_uses_wilcox_variant():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    w = applicability.warning_for_test_type(
        "Wilcoxon",
        dd_groups=dd_g,
        dd_testsets=make_dd_testsets("TS1", "TS2"),
        wilcox_variant="paired",
    )
    assert w is not None and "Wilcoxon" in w and "t-test" not in w.lower()


def test_anova_one_group_two_testsets_ok():
    dd_g = _groups("G1")
    dd_ts = make_dd_testsets("TS1", "TS2")
    assert applicability.check_anova_applicability(dd_g, dd_ts) is None


def test_anova_insufficient():
    dd_g = _groups("G1")
    assert applicability.check_anova_applicability(dd_g, make_dd_testsets("TS1")) == (
        "ANOVA requires ≥2 groups or 1 group + ≥2 test sets"
    )


def test_friedman_needs_three_testsets():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    assert applicability.check_friedman_applicability(dd_g, make_dd_testsets("TS1", "TS2")) == (
        "Friedman requires ≥3 test sets for repeated-measures"
    )


def test_friedman_needs_exactly_one_group():
    dd_g = _groups("G1", "G2")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    dd_g["G2"]["rec_IDs"] = ["r3", "r4"]
    assert applicability.check_friedman_applicability(dd_g, make_dd_testsets("TS1", "TS2", "TS3")) == (
        "Friedman requires exactly 1 group with data"
    )


def test_friedman_ok_one_group_three_sets():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1", "r2"]
    assert applicability.check_friedman_applicability(dd_g, make_dd_testsets("TS1", "TS2", "TS3")) is None


def test_cluster_two_groups_needs_testset():
    dd_g = _groups("G1", "G2")
    msg = applicability.check_cluster_applicability(dd_g, {})
    assert msg is not None
    assert "Between-groups" in msg
    assert "≥1 shown test set" in msg or ">=1" in msg
    assert "Valid layouts" in msg
    assert "exactly 2 groups" in msg and "exactly 2 test sets" in msg


def test_cluster_two_groups_ok():
    dd_g = _groups("G1", "G2")
    assert applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1")) is None
    # 2 groups + 2 sets still between (valid)
    assert applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1", "TS2")) is None


def test_cluster_three_groups_refused():
    dd_g = _groups("G1", "G2", "G3")
    msg = applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1"))
    assert msg is not None
    assert "3 groups" in msg
    assert "Valid layouts" in msg


def test_cluster_paired_needs_two_sets():
    dd_g = _groups("G1")
    msg = applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1"))
    assert msg is not None
    assert "Paired" in msg
    assert "exactly 2 test sets" in msg
    assert "2 groups" in msg  # points at between alternative
    assert "Valid layouts" in msg


def test_cluster_paired_ok():
    dd_g = _groups("G1")
    assert applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1", "TS2")) is None


def test_cluster_paired_different_absolute_sweeps_ok():
    """Baseline vs post: different absolute indices, same layout class — allowed."""
    dd_g = _groups("G1")
    dd_ts = {
        "TS1": {"show": True, "sweeps": [1, 2, 3]},
        "TS2": {"show": True, "sweeps": [10, 11, 12]},
    }
    assert applicability.check_cluster_applicability(dd_g, dd_ts) is None


def test_cluster_paired_short_window_warns():
    dd_g = _groups("G1")
    dd_ts = {
        "TS1": {"show": True, "sweeps": [1]},
        "TS2": {"show": True, "sweeps": [10, 11, 12]},
    }
    msg = applicability.check_cluster_applicability(dd_g, dd_ts)
    assert msg is not None
    assert "≥2 sweeps" in msg
    assert "Valid layouts" in msg
    assert "[" not in msg


def test_cluster_insufficient():
    dd_g = _groups("G1")
    msg = applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1"))
    assert msg is not None and "Paired" in msg and "Valid layouts" in msg


def test_warning_for_test_type_not_implemented_type():
    assert applicability.warning_for_test_type("ANCOVA", dd_groups={}, dd_testsets={}) is None