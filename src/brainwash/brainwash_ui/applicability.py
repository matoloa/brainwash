"""Pure statistical test applicability checks. Return warning string or None."""

from __future__ import annotations

from .view_state import groups_with_recordings, visible_group_ids, visible_testset_ids


# PP often has one binned "sweep" per recording and no test sets.
_PP_PAIRED_NO_WINDOW_MSG = (
    "Paired tests need two within-unit condition windows (2 test sets). "
    "Single-window PP has one mean PPR per unit — use unpaired t-test between groups, "
    "or one-sample vs 1 (facilitation), not paired."
)


def check_ttest_applicability(
    variant: str,
    dd_groups: dict | None,
    dd_testsets: dict | None,
    *,
    experiment_type: str | None = None,
) -> str | None:
    if not dd_groups:
        return "No groups defined for t-test"
    shown_groups = groups_with_recordings(dd_groups, visible_group_ids(dd_groups))
    shown_ts = visible_testset_ids(dd_testsets)
    is_pp = experiment_type == "PP"
    if variant == "paired":
        # Exactly one shown group + exactly two test sets (within-unit before/after, etc.)
        if is_pp and len(shown_ts) != 2:
            return _PP_PAIRED_NO_WINDOW_MSG
        if len(shown_groups) != 1:
            return "Paired t-test requires exactly 1 group with data"
        if len(shown_ts) != 2:
            return "Paired t-test requires exactly 2 test sets"
        n1 = len(dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
        if n1 < 2:
            return "Paired t-test requires N ≥ 2 recordings per group"
        return None
    if variant == "one-sample":
        if len(shown_groups) != 1:
            return "One-sample t-test requires exactly 1 group with data"
        # PP: one binned sweep per rec — no test set required (implicit all sweeps).
        if not shown_ts and not is_pp:
            return "No test sets shown for t-test"
        return None
    if len(shown_groups) < 2:
        msg = "t-test requires 2 group(s) with data"
        if is_pp:
            return msg + " for between-group PPR comparison"
        return msg
    if not shown_ts and not is_pp:
        return "No test sets shown for t-test"
    return None


def check_anova_applicability(
    dd_groups: dict | None,
    dd_testsets: dict | None,
    *,
    experiment_type: str | None = None,
) -> str | None:
    if not dd_groups:
        return "No groups defined for ANOVA"
    shown_groups = groups_with_recordings(dd_groups, visible_group_ids(dd_groups))
    shown_ts = visible_testset_ids(dd_testsets)
    is_pp = experiment_type == "PP"
    if len(shown_groups) < 1 or (len(shown_groups) == 1 and len(shown_ts) < 2):
        msg = "ANOVA requires ≥2 groups or 1 group + ≥2 test sets"
        if is_pp and len(shown_groups) == 1:
            return msg + " (PP RM needs ≥2 condition test sets; or show ≥2 groups for between PPR)"
        return msg
    if not shown_ts and len(shown_groups) == 1:
        return "Repeated-measures ANOVA requires ≥2 test sets"
    return None


def check_wilcoxon_applicability(
    variant: str,
    dd_groups: dict | None,
    dd_testsets: dict | None,
    *,
    experiment_type: str | None = None,
) -> str | None:
    """Wilcoxon signed-rank only (paired or one-sample). No unpaired/rank-sum."""
    if not dd_groups:
        return "No groups defined for Wilcoxon"
    shown_groups = groups_with_recordings(dd_groups, visible_group_ids(dd_groups))
    shown_ts = visible_testset_ids(dd_testsets)
    is_pp = experiment_type == "PP"
    if variant == "one-sample":
        if len(shown_groups) != 1:
            return "One-sample Wilcoxon requires exactly 1 group with data"
        if not shown_ts and not is_pp:
            return "No test sets shown for Wilcoxon"
        return None
    # Default / paired signed-rank
    if is_pp and len(shown_ts) != 2:
        return _PP_PAIRED_NO_WINDOW_MSG.replace("Paired tests", "Paired Wilcoxon").replace(
            "not paired", "not paired Wilcoxon"
        )
    if len(shown_groups) != 1:
        return "Paired Wilcoxon requires exactly 1 group with data"
    if len(shown_ts) != 2:
        return "Paired Wilcoxon requires exactly 2 test sets"
    n1 = len(dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
    if n1 < 2:
        return "Paired Wilcoxon requires N ≥ 2 recordings per group"
    return None


def check_friedman_applicability(
    dd_groups: dict | None,
    dd_testsets: dict | None,
    *,
    experiment_type: str | None = None,
) -> str | None:
    if not dd_groups:
        return "No groups defined for Friedman"
    shown_groups = groups_with_recordings(dd_groups, visible_group_ids(dd_groups))
    shown_ts = visible_testset_ids(dd_testsets)
    is_pp = experiment_type == "PP"
    if len(shown_groups) != 1:
        return "Friedman requires exactly 1 group with data"
    if len(shown_ts) < 3:
        msg = "Friedman requires ≥3 test sets for repeated-measures"
        if is_pp:
            return msg + " (PP: one set per condition epoch; not needed for single-window between-group tests)"
        return msg
    n1 = len(dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
    if n1 < 2:
        return "Friedman requires N ≥ 2 recordings per group"
    return None


# Shared wording for statusbar / validation / engine (keep in sync).
CLUSTER_PERM_LAYOUT_HELP = (
    "Valid layouts: (A) exactly 2 groups and ≥1 test set → between (one cluster test per set); "
    "or (B) exactly 1 group and exactly 2 test sets → paired."
)
CLUSTER_PERM_PP_HINT = (
    " On PP, cluster uses per-sweep PPR series (needs multi-sweep windows); "
    "for single-bin PPR prefer unpaired t-test without test sets."
)


def check_cluster_applicability(
    dd_groups: dict | None,
    dd_testsets: dict | None,
    *,
    experiment_type: str | None = None,
) -> str | None:
    is_pp = experiment_type == "PP"
    pp_suffix = CLUSTER_PERM_PP_HINT if is_pp else ""
    if not dd_groups:
        return f"No groups defined for Cluster perm. {CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"
    shown_groups = groups_with_recordings(dd_groups, visible_group_ids(dd_groups))
    shown_ts = visible_testset_ids(dd_testsets)
    n_g = len(shown_groups)
    n_ts = len(shown_ts)
    if n_g == 2:
        if n_ts < 1:
            return (
                f"Between-groups Cluster perm. needs ≥1 shown test set (have {n_ts}). "
                f"{CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"
            )
        return None
    if n_g == 1:
        if n_ts != 2:
            return (
                f"Paired Cluster perm. needs exactly 2 test sets (have {n_ts}); "
                f"or use exactly 2 groups for between mode. {CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"
            )
        # Each set needs a multi-sweep window; absolute sweep indices may differ (baseline vs post).
        tids = shown_ts
        t0 = (dd_testsets or {}).get(tids[0], {}) if tids else {}
        t1 = (dd_testsets or {}).get(tids[1], {}) if len(tids) > 1 else {}
        s0 = list(t0.get("sweeps") or [])
        s1 = list(t1.get("sweeps") or [])
        if len(s0) < 2 or len(s1) < 2:
            return (
                "Paired Cluster perm. needs ≥2 sweeps in each of the two test sets. "
                f"{CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"
            )
        return None
    if n_g > 2:
        return (
            f"Cluster perm. does not support {n_g} groups (only exactly 2 for between). "
            f"{CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"
        )
    return f"No groups with data for Cluster perm. {CLUSTER_PERM_LAYOUT_HELP}{pp_suffix}"


def warning_for_test_type(
    test_type: str,
    *,
    dd_groups: dict | None,
    dd_testsets: dict | None,
    ttest_variant: str = "unpaired",
    wilcox_variant: str = "paired",
    experiment_type: str | None = None,
) -> str | None:
    if test_type == "t-test":
        return check_ttest_applicability(
            ttest_variant, dd_groups, dd_testsets, experiment_type=experiment_type
        )
    if test_type == "ANOVA":
        return check_anova_applicability(dd_groups, dd_testsets, experiment_type=experiment_type)
    if test_type == "Wilcoxon":
        return check_wilcoxon_applicability(
            wilcox_variant, dd_groups, dd_testsets, experiment_type=experiment_type
        )
    if test_type == "Friedman":
        return check_friedman_applicability(dd_groups, dd_testsets, experiment_type=experiment_type)
    if test_type == "Cluster perm.":
        return check_cluster_applicability(dd_groups, dd_testsets, experiment_type=experiment_type)
    return None
