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
    if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
        return {"not_implemented": test_type, "results": []}

    if not isinstance(dd_groups, dict):
        return {"error": "no groups defined", "results": []}
    if groups is None:
        groups = []

    shown_groups = [g for g in groups if dd_groups.get(g, {}).get("show") in (True, "True", 1, "1", True)]
    shown_groups = [g for g in shown_groups if len(dd_groups.get(g, {}).get("rec_IDs", [])) > 0]
    if not shown_groups:
        return {"error": "no shown groups", "results": []}

    if variant == "one-sample":
        pass
    elif test_type == "ANOVA" and len(shown_groups) == 1:
        pass
    elif test_type == "Friedman" and len(shown_groups) == 1:
        pass
    elif test_type == "Cluster perm.":
        pass
    elif variant == "paired":
        if len(shown_groups) != 1:
            return {"error": "paired t-test requires exactly 1 group", "results": []}
    else:
        if len(shown_groups) < 2:
            return {"error": "need at least two shown groups", "results": []}

    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    is_io = experiment_type == "io"
    if not shown_sets and not is_io:
        return {"error": "no shown test sets", "results": []}

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
    if variant == "one-sample":
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "ANOVA" and len(shown_groups) == 1:
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "Friedman" and len(shown_groups) == 1:
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "Cluster perm.":
        pass
    elif variant == "paired":
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