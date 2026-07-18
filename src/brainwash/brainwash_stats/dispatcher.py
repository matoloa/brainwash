from .formal_tests.anova_rm import run_repeated_measures_anova
from .formal_tests.cluster_perm import run_cluster_permutation
from .formal_tests.friedman import run_friedman_omnibus
from .formal_tests.ttest_and_between import run_main_test_set_loop
from .formal_tests.wilcoxon import run_wilcoxon_tests
from .io.ancova import compute_io_ancova
from .validation import comparison_context, validate_comparison_inputs


def compute_statistical_comparison(
    groups: list,
    dd_groups: dict,
    dd_testsets: dict,
    get_group_testset_means_fn,
    test_type: str = "t-test",
    variant: str = "unpaired",
    tails: str = "two-sided",
    fdr: bool = False,
    norm: bool = False,
    amp: bool = True,
    slope: bool = True,
    ref: float = 0.0,
    n_unit: str = "subject",
    experiment_type: str = "time",
    uistate=None,
    force_through_zero: bool = False,
    test_sw: bool = False,
    test_levene: bool = False,
) -> dict:
    """
    High-level entry point used by UI for formal statistical tests on Test Sets.

    n_unit selects statistical unit (default="subject"). Uses _aggregate_to_unit_level.
    Old projects (no hierarchy) → statusbar warning + recording fallback.
    Cluster perm. forces recording-level n.

    IO formal analysis: experiment_type=="io" and test_type=="ANCOVA" only.
    Textbook ANCOVA (homogeneity of slopes then covariate-adjusted group test).
    Uses all sweeps/bins (test sets ignored for v1). Config type "IO ANCOVA".
    See work_plans/plan_io_ancova_publication.md.
    """
    validation_error = validate_comparison_inputs(
        groups=groups,
        dd_groups=dd_groups,
        dd_testsets=dd_testsets,
        get_group_testset_means_fn=get_group_testset_means_fn,
        test_type=test_type,
        variant=variant,
        experiment_type=experiment_type,
    )
    if validation_error is not None:
        return validation_error

    ctx = comparison_context(
        groups=groups,
        dd_groups=dd_groups,
        dd_testsets=dd_testsets,
        get_group_testset_means_fn=get_group_testset_means_fn,
        test_type=test_type,
        variant=variant,
        experiment_type=experiment_type,
    )
    shown_groups = ctx["shown_groups"]
    g1 = ctx["g1"]
    g2 = ctx["g2"]
    shown_sets = ctx["shown_sets"]
    use_implicit = ctx["use_implicit"]
    is_io = ctx["is_io"]
    fetch_group_testset_observations = ctx["fetch_group_testset_observations"]

    # PR-B/C: IO ANCOVA only — ignore test sets; no fall-through to time ANOVA.
    if is_io and test_type == "ANCOVA":
        if uistate is None:
            uistate = getattr(get_group_testset_means_fn, "__self__", None)
        return compute_io_ancova(
            shown_groups=shown_groups,
            get_group_testset_means_fn=get_group_testset_means_fn,
            uistate=uistate,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            dd_groups=dd_groups,
            force_through_zero=force_through_zero,
            test_sw=test_sw,
            test_levene=test_levene,
        )

    if n_unit not in ("subject", "slice", "recording"):
        n_unit = "subject"

    if test_type == "Cluster perm." and n_unit != "recording":
        n_unit = "recording"

    if n_unit in ("subject", "slice"):
        sample_sid, sample_tset = shown_sets[0] if shown_sets else (None, None)
        if sample_sid or use_implicit:
            try:
                sample_sweeps = sample_tset.get("sweeps", []) if sample_tset else None
                sample_obs = get_group_testset_means_fn(shown_groups[0], sample_sweeps, aspect="EPSP_amp")
                if not all(k in sample_obs.columns for k in ("subject", "slice")) or sample_obs["subject"].isna().all():
                    return {
                        "error": f"{n_unit} not assigned for included recording(s)",
                        "results": [],
                        "config": {"n_unit": n_unit},
                    }
            except Exception:
                pass

    if test_type == "ANOVA" and len(shown_groups) == 1 and len(shown_sets) >= 2:
        return run_repeated_measures_anova(
            shown_groups=shown_groups,
            shown_sets=shown_sets,
            fetch_group_testset_observations=fetch_group_testset_observations,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            fdr=fdr,
            test_type=test_type,
        )

    if test_type == "Friedman" and len(shown_groups) == 1 and len(shown_sets) >= 3:
        return run_friedman_omnibus(
            shown_groups=shown_groups,
            shown_sets=shown_sets,
            fetch_group_testset_observations=fetch_group_testset_observations,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            fdr=fdr,
            test_type=test_type,
        )

    if test_type == "Cluster perm.":
        return run_cluster_permutation(
            shown_groups=shown_groups,
            dd_testsets=dd_testsets,
            fetch_group_testset_observations=fetch_group_testset_observations,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            fdr=fdr,
            test_type=test_type,
            use_implicit=use_implicit,
        )

    if test_type == "Wilcoxon":
        return run_wilcoxon_tests(
            shown_groups=shown_groups,
            shown_sets=shown_sets,
            fetch_group_testset_observations=fetch_group_testset_observations,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            fdr=fdr,
            test_type=test_type,
            variant=variant,
            tails=tails,
            ref=ref,
        )

    return run_main_test_set_loop(
        shown_groups=shown_groups,
        shown_sets=shown_sets,
        g1=g1,
        g2=g2,
        fetch_group_testset_observations=fetch_group_testset_observations,
        n_unit=n_unit,
        norm=norm,
        amp=amp,
        slope=slope,
        fdr=fdr,
        test_type=test_type,
        variant=variant,
        tails=tails,
        ref=ref,
        use_implicit=use_implicit,
    )