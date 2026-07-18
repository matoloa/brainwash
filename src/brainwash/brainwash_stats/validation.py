from .data import _make_group_testset_observation_accessor


def validate_comparison_inputs(
    *,
    groups,
    dd_groups,
    dd_testsets,
    get_group_testset_means_fn,
    test_type,
    variant,
    experiment_type,
) -> dict | None:
    """Return error/not_implemented dict, or None when inputs are valid.

    When None, call ``comparison_context`` with the same kwargs for shown_groups, g1, g2, etc.
    """
    is_io = experiment_type == "io"
    # IO formal analysis is ANCOVA-only (PR-A/B). Other test types must not run under experiment_type io.
    if is_io and test_type != "ANCOVA":
        return {
            "error": "IO experiment requires ANCOVA",
            "results": [],
            "config": {"type": "IO ANCOVA"},
        }
    if test_type == "ANCOVA" and not is_io:
        return {"not_implemented": "ANCOVA", "results": []}

    allowed = ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.", "ANCOVA")
    if test_type not in allowed:
        return {"not_implemented": test_type, "results": []}

    if not isinstance(dd_groups, dict):
        return {"error": "no groups defined", "results": []}
    if groups is None:
        groups = []

    shown_groups = [g for g in groups if dd_groups.get(g, {}).get("show") in (True, "True", 1, "1", True)]
    shown_groups = [g for g in shown_groups if len(dd_groups.get(g, {}).get("rec_IDs", [])) > 0]
    if not shown_groups:
        err = {"error": "no shown groups", "results": []}
        if is_io or test_type == "ANCOVA":
            err["config"] = {"type": "IO ANCOVA"}
        return err

    # t-test / Wilcoxon variant radios must not constrain ANOVA / Friedman / Cluster.
    paired_variant = test_type in ("t-test", "Wilcoxon") and variant == "paired"
    one_sample_variant = test_type in ("t-test", "Wilcoxon") and variant == "one-sample"
    _paired_label = "paired Wilcoxon" if test_type == "Wilcoxon" else "paired t-test"
    _one_label = "one-sample Wilcoxon" if test_type == "Wilcoxon" else "one-sample t-test"

    if one_sample_variant:
        if len(shown_groups) != 1:
            return {"error": f"{_one_label} requires exactly 1 group", "results": []}
    elif test_type == "ANOVA" and len(shown_groups) == 1:
        pass
    elif test_type == "Friedman":
        if len(shown_groups) != 1:
            return {"error": "Friedman requires exactly 1 group", "results": []}
    elif test_type == "Cluster perm.":
        # Layout checked with test sets below (needs both counts).
        pass
    elif test_type == "ANCOVA":
        # Test sets ignored for IO ANCOVA v1 (all sweeps/bins).
        if len(shown_groups) < 2:
            return {
                "error": "need at least two shown groups",
                "results": [],
                "config": {"type": "IO ANCOVA"},
            }
    elif paired_variant:
        if len(shown_groups) != 1:
            return {"error": f"{_paired_label} requires exactly 1 group", "results": []}
    else:
        if len(shown_groups) < 2:
            return {"error": "need at least two shown groups", "results": []}

    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    # IO ANCOVA does not require test sets (and ignores them for data selection in v1).
    if not shown_sets and not is_io and test_type != "Cluster perm.":
        return {"error": "no shown test sets", "results": []}
    if paired_variant and len(shown_sets) != 2:
        return {"error": f"{_paired_label} requires exactly 2 shown test sets", "results": []}
    if test_type == "Friedman" and len(shown_sets) < 3:
        return {"error": "Friedman requires at least 3 shown test sets", "results": []}
    if test_type == "Cluster perm.":
        # Keep wording aligned with brainwash_ui.applicability.CLUSTER_PERM_LAYOUT_HELP
        _cluster_help = (
            "Valid layouts: (A) exactly 2 groups and ≥1 test set → between (one cluster test per set); "
            "or (B) exactly 1 group and exactly 2 test sets → paired."
        )
        n_g = len(shown_groups)
        n_ts = len(shown_sets)
        if n_g == 0:
            return {"error": f"No groups with data for Cluster perm. {_cluster_help}", "results": []}
        if n_g > 2:
            return {
                "error": f"Cluster perm. does not support {n_g} groups (only exactly 2 for between). {_cluster_help}",
                "results": [],
            }
        if n_g == 1 and n_ts != 2:
            return {
                "error": (
                    f"Paired Cluster perm. needs exactly 2 test sets (have {n_ts}); "
                    f"or use exactly 2 groups for between mode. {_cluster_help}"
                ),
                "results": [],
            }
        if n_g == 2 and n_ts < 1:
            return {
                "error": (
                    f"Between-groups Cluster perm. needs ≥1 shown test set (have {n_ts}). {_cluster_help}"
                ),
                "results": [],
            }
        if not shown_sets and not is_io:
            return {"error": f"no shown test sets. {_cluster_help}", "results": []}

    if get_group_testset_means_fn is None:
        return {"error": "no data accessor for testset means", "results": []}

    return None


def comparison_context(
    *,
    groups,
    dd_groups,
    dd_testsets,
    get_group_testset_means_fn,
    test_type,
    variant,
    experiment_type,
) -> dict:
    if groups is None:
        groups = []

    shown_groups = [g for g in groups if dd_groups.get(g, {}).get("show") in (True, "True", 1, "1", True)]
    shown_groups = [g for g in shown_groups if len(dd_groups.get(g, {}).get("rec_IDs", [])) > 0]

    g1 = None
    g2 = None
    paired_variant = test_type in ("t-test", "Wilcoxon") and variant == "paired"
    one_sample_variant = test_type in ("t-test", "Wilcoxon") and variant == "one-sample"
    if one_sample_variant:
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "ANOVA":
        g1 = shown_groups[0]
        g2 = shown_groups[1] if len(shown_groups) > 1 else None
    elif test_type == "Friedman":
        g1 = shown_groups[0] if shown_groups else None
        g2 = None
    elif test_type == "Cluster perm.":
        pass
    elif paired_variant:
        g1 = shown_groups[0]
        g2 = None
    else:
        g1, g2 = shown_groups[0], shown_groups[1]

    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    is_io = experiment_type == "io"
    use_implicit = False
    if not shown_sets:
        if is_io:
            use_implicit = True

    fetch_group_testset_observations = _make_group_testset_observation_accessor(
        get_group_testset_means_fn, use_implicit
    )

    return {
        "shown_groups": shown_groups,
        "g1": g1,
        "g2": g2,
        "shown_sets": shown_sets,
        "use_implicit": use_implicit,
        "is_io": is_io,
        "fetch_group_testset_observations": fetch_group_testset_observations,
    }