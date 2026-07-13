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


def test_ttest_paired_needs_two_recordings():
    dd_g = _groups("G1")
    dd_g["G1"]["rec_IDs"] = ["r1"]
    dd_ts = make_dd_testsets("TS1", "TS2")
    assert applicability.check_ttest_applicability("paired", dd_g, dd_ts) == (
        "Paired t-test requires N ≥ 2 recordings per group"
    )


def test_ttest_no_groups():
    assert applicability.check_ttest_applicability("unpaired", None, {}) == "No groups defined for t-test"


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
    assert applicability.check_friedman_applicability(make_dd_testsets("TS1", "TS2")) == (
        "Friedman requires ≥3 test sets for repeated-measures"
    )


def test_cluster_two_groups_ok():
    dd_g = _groups("G1", "G2")
    assert applicability.check_cluster_applicability(dd_g, {}) is None


def test_cluster_insufficient():
    dd_g = _groups("G1")
    assert applicability.check_cluster_applicability(dd_g, make_dd_testsets("TS1")) == (
        "Cluster permutation test requires ≥2 groups or 1 group + ≥2 test sets"
    )


def test_warning_for_test_type_not_implemented_type():
    assert applicability.warning_for_test_type("ANCOVA", dd_groups={}, dd_testsets={}) is None