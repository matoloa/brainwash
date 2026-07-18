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