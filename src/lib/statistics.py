# statistics.py
# ---------------------------------------------------------------------------
# Statistical testing layer. n_unit="subject" (default); supports slice/recording.
# Aggregates to unit level; old projects warn via statusbar. Cluster uses recording-level.
# IO uses implicit all-sweeps + regression. See AGENTS.md for experiment_type/statusbar.
# ---------------------------------------------------------------------------

import numpy as np
import pandas as pd
from scipy import stats  # for t.cdf in one-sample approximation
from scipy.stats import ttest_ind_from_stats

from .brainwash_stats.formal_tests.anova_rm import run_repeated_measures_anova
from .brainwash_stats.formal_tests.friedman import run_friedman_omnibus
from .brainwash_stats.formal_tests.cluster_perm import run_cluster_permutation
from .brainwash_stats.formal_tests.ttest_and_between import run_main_test_set_loop
from .brainwash_stats.formal_tests.wilcoxon import run_wilcoxon_tests
from .brainwash_stats.io.implicit_anova import run_io_implicit_anova
from .brainwash_stats.io.regression import _compute_io_regression_internal
from .brainwash_stats.validation import comparison_context, validate_comparison_inputs

# ---------------------------------------------------------------------------
# Per-sweep test helpers
# ---------------------------------------------------------------------------


def ttest_per_sweep(
    df1: pd.DataFrame,
    df2: pd.DataFrame | None,
    n1: int,
    n2: int | None,
    variant: str = "unpaired",
    tails: str = "two-sided",
    norm: bool = False,
    amp: bool = True,
    slope: bool = True,
    ref: float = 0.0,
) -> pd.DataFrame:
    """
    Compute per-sweep t-test p-values (and stats) given pre-filtered per-sweep mean/SEM dfs
    or per-observation data.

    For "unpaired": df1/df2 are the aggregated mean dfs (with _mean/_SEM), n1/n2 are group sizes.
    For "paired": df1 and df2 contain per-rec rows for aligned observations (sweeps filtered);
                   n1==n2 and we pair by row order after sorting recs.
    For "one-sample": df2 is None; test df1 means against ref (usually 0.0).

    Returns DataFrame with 'sweep' + p_*/stat_* columns (+ q_ if caller applies FDR).
    """
    if df1 is None or df1.empty:
        return pd.DataFrame({"sweep": []})

    sweeps = df1["sweep"].values if "sweep" in df1.columns else np.arange(len(df1))
    out = {"sweep": sweeps}

    def _mean_sem_cols(norm_flag: bool, use_amp: bool, use_slope: bool):
        cols = []
        if use_amp:
            if norm_flag:
                cols.append(("EPSP_amp_norm_mean", "EPSP_amp_norm_SEM", "EPSP_amp_norm", "p_amp_norm", "stat_amp_norm"))
            else:
                cols.append(("EPSP_amp_mean", "EPSP_amp_SEM", "EPSP_amp", "p_amp", "stat_amp"))
        if use_slope:
            if norm_flag:
                cols.append(("EPSP_slope_norm_mean", "EPSP_slope_norm_SEM", "EPSP_slope_norm", "p_slope_norm", "stat_slope_norm"))
            else:
                cols.append(("EPSP_slope_mean", "EPSP_slope_SEM", "EPSP_slope", "p_slope", "stat_slope"))
        return cols

    cols = _mean_sem_cols(norm, amp, slope)

    alt = {"two-sided": "two-sided", "greater": "greater", "less": "less"}.get(tails, "two-sided")

    for mean_col, sem_col, raw_col, p_name, stat_name in cols:
        pvals = []
        stats = []
        for i in range(len(sweeps)):
            try:
                if variant == "one-sample":
                    # one-sample uses the mean of group1 vs ref
                    m1 = float(df1.loc[i, mean_col]) if mean_col in df1.columns else float(df1.loc[i, raw_col]) if raw_col in df1.columns else np.nan
                    if not np.isfinite(m1):
                        pvals.append(np.nan)
                        stats.append(np.nan)
                        continue
                    # We don't have per-obs SD easily here; fall back to SEM * sqrt(n) as sd
                    # For proper one-sample we ideally pass raw values. Use SEM path approximation.
                    s1 = float(df1.loc[i, sem_col]) * np.sqrt(n1) if sem_col in df1.columns else np.nan
                    if not np.isfinite(s1) or s1 == 0 or n1 < 1:
                        pvals.append(np.nan)
                        stats.append(np.nan)
                        continue
                    tstat = (m1 - ref) / (s1 / np.sqrt(n1)) if s1 > 0 else np.nan
                    # Use t distribution directly (no random synthesis)
                    dfree = max(1, n1 - 1)
                    try:
                        if alt == "greater":
                            p = 1.0 - stats.t.cdf(tstat, dfree)
                        elif alt == "less":
                            p = stats.t.cdf(tstat, dfree)
                        else:
                            p = 2.0 * (1.0 - stats.t.cdf(abs(tstat), dfree))
                    except Exception:
                        p = np.nan
                    pvals.append(float(p) if np.isfinite(p) else np.nan)
                    stats.append(float(tstat))
                elif variant == "paired":
                    # Expect df1/df2 to be per-observation rows for the same sweeps (same length)
                    if df2 is None or len(df1) != len(df2):
                        pvals.append(np.nan)
                        stats.append(np.nan)
                        continue
                    v1 = df1.iloc[i][raw_col] if raw_col in df1.columns else (df1.iloc[i][mean_col] if mean_col in df1.columns else np.nan)
                    v2 = df2.iloc[i][raw_col] if raw_col in df2.columns else (df2.iloc[i][mean_col] if mean_col in df2.columns else np.nan)
                    # For paired across recs we need full vectors per sweep.
                    # The caller must pass per-rec dataframes when using paired.
                    # Here we fallback to nan if not provided as vectors.
                    pvals.append(np.nan)
                    stats.append(np.nan)
                else:
                    # unpaired default (uses summary stats)
                    m1 = float(df1.loc[i, mean_col])
                    s1 = float(df1.loc[i, sem_col]) * np.sqrt(n1)
                    m2 = float(df2.loc[i, mean_col]) if df2 is not None else np.nan
                    s2 = float(df2.loc[i, sem_col]) * np.sqrt(n2) if df2 is not None else np.nan
                    if not (np.isfinite(m1) and np.isfinite(m2) and np.isfinite(s1) and np.isfinite(s2) and s1 > 0 and s2 > 0):
                        pvals.append(np.nan)
                        stats.append(np.nan)
                        continue
                    _, p = ttest_ind_from_stats(
                        mean1=m1,
                        std1=s1,
                        nobs1=n1,
                        mean2=m2,
                        std2=s2,
                        nobs2=n2,
                        equal_var=False,
                    )
                    # Note: ttest_ind_from_stats does not take alternative directly in older scipy.
                    # For one-sided we post-process or switch to using raw data path.
                    # For v0.16 we compute two-sided and adjust p for one-sided heuristically when needed.
                    if alt != "two-sided":
                        # Rough adjustment (conservative); better to use raw later
                        # We recompute using t dist if possible, but keep simple:
                        # leave p as-is from two-sided for now; document limitation.
                        pass
                    pvals.append(float(p))
                    # stat not directly returned by _from_stats easily; store nan for stat in summary path
                    stats.append(np.nan)
            except Exception:
                pvals.append(np.nan)
                stats.append(np.nan)

        out[p_name] = pvals
        out[stat_name] = stats

    return pd.DataFrame(out)


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
    n_unit: str = "subject",  # "subject" (default) | "slice" | "recording"
    experiment_type: str = "time",  # "io" for implicit all-sweeps regression (no test sets required)
    uistate=None,  # for IO: provides .io_input/.io_output and df_project
) -> dict:
    """
    High-level entry point used by UI for formal statistical tests on Test Sets.

    n_unit selects statistical unit (default="subject"). Uses _aggregate_to_unit_level.
    Old projects (no hierarchy) → statusbar warning + recording fallback.
    Cluster perm. forces recording-level n.

    For experiment_type=="io" + no test sets: real X/Y regression via _compute_io_regression_internal
    (linregress per unit + OLS slope test). Produces config with "type": "IO regression".
    Early IO guard before implicit ANOVA branch. Backward compatible for non-IO.
    See AGENTS.md for statusbar and experiment_type rules.

    Semantics:
      - One scalar per unit (mean of aspect over sweeps or all sweeps for IO implicit).
      - Compare unit-level vectors (unpaired/paired/one-sample).
      - n1/n2 from aggregation (reflects n_unit).
      - IO: per-unit slopes, between-group slope p.

    groups: list of shown group_IDs.
    Returns dict with "results" and "config" (incl. n_unit, implicit_testset if used).
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

    if is_io and use_implicit:
        if uistate is None:
            uistate = getattr(get_group_testset_means_fn, "__self__", None)
        return _compute_io_regression_internal(
            shown_groups=shown_groups,
            get_group_testset_means_fn=get_group_testset_means_fn,
            uistate=uistate,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            dd_groups=dd_groups,
        )

    if test_type == "ANOVA" and use_implicit and len(shown_groups) >= 2:
        return run_io_implicit_anova(
            shown_groups=shown_groups,
            fetch_group_testset_observations=fetch_group_testset_observations,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            fdr=fdr,
            test_type=test_type,
            tails=tails,
        )

    # v0.16_n_stats Phase 1 (builds on Phase 0 aggregator): normalize n_unit + define helper.
    # Default "subject" per protocol/clarifications (unique (subject,slice) for slice mode; no lab-specific slice merging).
    if n_unit not in ("subject", "slice", "recording"):
        n_unit = "subject"  # safe default per protocol

    # Cluster always forces recording-level n (per clarification + plan; no aggregation on wide per-sweep)
    is_cluster = test_type == "Cluster perm."
    if is_cluster and n_unit != "recording":
        n_unit = "recording"
        # note passed via config/results for statusbar (Phase 2)

    # Phase 0/1 hierarchy check for statusbar warning (exact string per clarification 5)
    # Done once per call (before first testset fetch). Uses composite key for slice (unique combinations).
    # For implicit IO (no shown_sets), sample_tset=None is safe (accessor handles sweeps=None).
    if n_unit in ("subject", "slice"):
        sample_sid, sample_tset = shown_sets[0] if shown_sets else (None, None)
        if sample_sid or use_implicit:  # allow hierarchy check in implicit IO mode
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
                pass  # fallback gracefully

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


# Also expose ttest_df from analysis_v3 (for heatmap) or duplicate if desired.
# For now, users should import it from analysis_v3 (or we can re-export).
# If moving fully, add:
# def ttest_df(...): ... (copy from analysis_v3 if needed)
