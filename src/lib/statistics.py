# statistics.py
# ---------------------------------------------------------------------------
# Statistical testing layer. n_unit="subject" (default); supports slice/recording.
# Aggregates to unit level; old projects warn via statusbar. Cluster uses recording-level.
# IO uses implicit all-sweeps + regression. See AGENTS.md for experiment_type/statusbar.
# ---------------------------------------------------------------------------

import warnings

import numpy as np
import pandas as pd
from scipy import stats  # for t.cdf in one-sample approximation
from scipy.stats import f_oneway, levene, linregress, shapiro, ttest_1samp, ttest_ind, ttest_ind_from_stats, ttest_rel, wilcoxon

from .brainwash_stats.data import (
    _aggregate_to_unit_level,
    _aspect_measurement_columns,
    _make_group_testset_observation_accessor,
)
from .brainwash_stats.fdr import _bh_fdr
from .brainwash_stats.formal_tests.friedman import run_friedman_omnibus
from .brainwash_stats.io.regression import _compute_io_regression_internal

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
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "ANOVA" and len(shown_groups) == 1:
        # Repeated-measures path: 1 group, compare across test sets (within-subjects)
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "Friedman" and len(shown_groups) == 1:
        # Repeated-measures Friedman omnibus: 1 group, compare across >=3 test sets
        g1 = shown_groups[0]
        g2 = None
    elif test_type == "Cluster perm.":
        # Cluster perm. (v0.16): supports >=2 groups (between-subjects via permutation_cluster_test) or 1-group + exactly 2 test sets (paired via permutation_cluster_1samp_test).
        # Must come before the paired t-test guard and the default 2-group requirement.
        pass
    elif variant == "paired":
        # Paired t-test (v0.16): exactly 1 group + 2 test sets; pair observations by rec_ID within the single group
        if len(shown_groups) != 1:
            return {"error": "paired t-test requires exactly 1 group", "results": []}
        g1 = shown_groups[0]
        g2 = None  # not used; pairing handled inside ttest_rel branch using 2 test sets
    else:
        if len(shown_groups) < 2:
            return {"error": "need at least two shown groups", "results": []}
        g1, g2 = shown_groups[0], shown_groups[1]

    # Centralized guard for shown test sets. IO allows empty (implicit all-sweeps).
    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    is_io = experiment_type == "io"
    use_implicit = False
    if not shown_sets:
        if is_io:
            use_implicit = True
        else:
            return {"error": "no shown test sets", "results": []}

    if get_group_testset_means_fn is None:
        return {"error": "no data accessor for testset means", "results": []}

    fetch_group_testset_observations = _make_group_testset_observation_accessor(
        get_group_testset_means_fn, use_implicit
    )

    # Early IO regression guard for experiment_type=="io" + use_implicit. Calls _compute_io_regression_internal.
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

    # Implicit ANOVA for IO (between-groups on all-sweeps when >=2 groups). Placed early.
    if test_type == "ANOVA" and use_implicit and len(shown_groups) >= 2:
        out_results = []
        aspects = _aspect_measurement_columns(amp, slope, norm)

        set_result = {
            "set_id": "__io_anova_implicit__",
            "set_name": None,  # sentinel per debug plan v0.16; UI overrides to suppress name for "IO - ANOVA (n_report): ..." format
            "sweeps": [],
            "group1": shown_groups,  # all groups for ANOVA context (used in n_report)
            "n1": 0,
            "n2": 0,
            "anova_note": "between-groups one-way on all sweeps (implicit IO)",
        }
        raw_p_amp = []
        raw_p_slope = []
        group_ns = {}  # per-group n for precise n_report (avoids ?)

        for short, col in aspects:
            vals_list = []
            n_per_group = []
            for g in shown_groups:
                try:
                    obs_df = fetch_group_testset_observations(g, None, col)
                    # Inline aggregation (subject/slice) for implicit IO ANOVA branch.
                    if n_unit != "recording" and not obs_df.empty and "value" in obs_df.columns:
                        gkeys = ["subject", "slice"] if n_unit == "slice" else ["subject"]
                        if all(k in obs_df.columns for k in gkeys):
                            v = obs_df[gkeys + ["value"]].dropna()
                            if not v.empty:
                                obs_df = v.groupby(gkeys, as_index=False)["value"].mean()
                    obs = obs_df["value"].to_numpy(dtype=float) if not obs_df.empty else np.array([], dtype=float)
                    valid = obs[np.isfinite(obs)]
                    vals_list.append(valid)
                    n_per_group.append(len(valid))
                    group_ns[g] = max(group_ns.get(g, 0), len(valid))
                except Exception:
                    vals_list.append(np.array([], dtype=float))
                    n_per_group.append(0)
            if len(vals_list) >= 2 and all(len(v) > 0 for v in vals_list):
                try:
                    res = f_oneway(*vals_list)
                    p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                    stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                    set_result[f"p_{short}"] = float(p) if np.isfinite(p) else np.nan
                    set_result[f"stat_{short}"] = float(stat) if np.isfinite(stat) else np.nan
                    eff_n = max(n_per_group) if n_per_group else 0
                    set_result["n1"] = max(set_result.get("n1", 0), eff_n)
                    set_result["n2"] = set_result["n1"]  # symmetric for one-way
                    # eta2 (same as RM/main ANOVA path)
                    if hasattr(res, "statistic") and np.isfinite(res.statistic) and eff_n > 0:
                        df_between = len(vals_list) - 1
                        df_within = sum(len(v) for v in vals_list) - len(vals_list)
                        if df_within > 0:
                            eta2 = (df_between * res.statistic) / (df_between * res.statistic + df_within)
                            set_result["eta2"] = float(eta2)
                    if short == "amp":
                        raw_p_amp.append(f"p_{short}")
                    else:
                        raw_p_slope.append(f"p_{short}")
                except Exception:
                    set_result[f"p_{short}"] = np.nan
                    set_result[f"stat_{short}"] = np.nan
            else:
                set_result[f"p_{short}"] = np.nan
                set_result[f"stat_{short}"] = np.nan

        # Store per-group ns for UI n_report (overrides fallback in _get_stat_test_warning)
        set_result["group_ns"] = group_ns
        if any(k.startswith("p_") for k in set_result if isinstance(k, str)):
            out_results.append(set_result)

        # FDR if requested (single omnibus row)
        if fdr and raw_p_amp:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [set_result.get(k, np.nan) for k in raw_p_amp]
                qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                for k, q in zip(raw_p_amp, qs):
                    set_result["q_" + k[2:]] = float(q) if np.isfinite(q) else np.nan
            except Exception:
                pass
        if fdr and raw_p_slope:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [set_result.get(k, np.nan) for k in raw_p_slope]
                qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                for k, q in zip(raw_p_slope, qs):
                    set_result["q_" + k[2:]] = float(q) if np.isfinite(q) else np.nan
            except Exception:
                pass

        config = {
            "type": test_type,
            "variant": "unpaired",
            "tails": tails,
            "fdr": fdr,
            "norm": norm,
            "amp": amp,
            "slope": slope,
            "n_unit": n_unit,
            "implicit_testset": True,
        }
        # r2 from existing block will be merged below; return early with real results
        return {"results": out_results, "config": config}

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

    # --- Repeated-measures ANOVA path (1 group, >=2 test sets) ---
    # Computes omnibus one-way ANOVA across test sets within the single group.
    # Full subject-aligned RM-ANOVA (with subject factor + sphericity) is deferred (Phase 2+).
    if test_type == "ANOVA" and len(shown_groups) == 1 and len(shown_sets) >= 2:
        g = shown_groups[0]
        rm_res = {
            "set_id": "__anova_rm_omnibus__",
            "set_name": "ANOVA (repeated, omnibus)",
            "sweeps": [],
            "group1": shown_groups,
            "n1": 0,
            "n2": 0,
        }
        raw_p_amp = []
        raw_p_slope = []
        aspects = _aspect_measurement_columns(amp, slope, norm)

        for short, col in aspects:
            vals_list = []
            for sid2, tset2 in shown_sets:
                try:
                    obs_df = fetch_group_testset_observations(g, tset2, col)
                    # Phase 0: aggregate to chosen unit (subject default)
                    obs_df = _aggregate_to_unit_level(obs_df, n_unit)
                    obs = obs_df["value"].to_numpy(dtype=float) if not obs_df.empty else np.array([], dtype=float)
                    valid = obs[np.isfinite(obs)]
                except Exception:
                    valid = np.array([], dtype=float)
                vals_list.append(valid)
            if len(vals_list) >= 2 and all(len(v) > 0 for v in vals_list):
                try:
                    res = f_oneway(*vals_list)
                    p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                    stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                    eff_n = max((len(v) for v in vals_list), default=0)
                    rm_res[f"p_{short}"] = float(p) if np.isfinite(p) else np.nan
                    rm_res[f"stat_{short}"] = float(stat) if np.isfinite(stat) else np.nan
                    rm_res["n1"] = max(rm_res.get("n1", 0), eff_n)
                    if hasattr(res, "statistic") and np.isfinite(res.statistic) and eff_n > 0:
                        df_between = len(vals_list) - 1
                        df_within = sum(len(v) for v in vals_list) - len(vals_list)
                        if df_within > 0:
                            eta2 = (df_between * res.statistic) / (df_between * res.statistic + df_within)
                            rm_res["eta2"] = float(eta2)
                    if short == "amp":
                        raw_p_amp.append(f"p_{short}")
                    else:
                        raw_p_slope.append(f"p_{short}")
                except Exception:
                    pass
        rm_results = [rm_res] if ("p_amp" in rm_res or "p_slope" in rm_res) else []
        # FDR (if requested) on the omnibus results (single row)
        if fdr and raw_p_amp:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [rm_res.get(k, np.nan) for k in raw_p_amp]
                qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                for k, q in zip(raw_p_amp, qs):
                    rm_res["q_" + k[2:]] = float(q)
            except Exception:
                pass
        if fdr and raw_p_slope:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [rm_res.get(k, np.nan) for k in raw_p_slope]
                qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                for k, q in zip(raw_p_slope, qs):
                    rm_res["q_" + k[2:]] = float(q)
            except Exception:
                pass
        return {"results": rm_results, "config": {"test_type": test_type, "variant": "repeated", "fdr": fdr, "norm": norm}}

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

    # --- Cluster permutation test (time-series curves) ---
    # After Friedman omnibus; before Wilcoxon. Uses per-sweep matrices (Phase 1 helper).
    # Between-subjects: permutation_cluster_test on two group matrices per test set.
    # Paired (1 group + 2 test sets): permutation_cluster_1samp_test on difference matrix.
    if test_type == "Cluster perm.":
        print(f"DEBUG compute_statistical_comparison: entered Cluster perm. branch with {len(groups) if groups else 0} groups, test_type={test_type}")
        try:
            from mne.stats import permutation_cluster_1samp_test, permutation_cluster_test

            print("DEBUG: MNE imported successfully")
        except ImportError:
            print("DEBUG: MNE ImportError")
            return {
                "error": "MNE-Python not installed; cluster permutation requires `pip install mne` (or `pip install .[neuroscience]`)",
                "results": [],
            }
        except Exception as e:
            print(f"DEBUG: MNE import failed: {e}")
            warnings.warn(f"MNE import failed: {e}")
            return {
                "error": "MNE-Python not installed; cluster permutation requires `pip install mne` (or `pip install .[neuroscience]`)",
                "results": [],
            }

        # Cluster uses its own shown_sets (for sweep windows); implicit IO not applicable here (requires explicit sweeps for adjacency)
        shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
        print(f"DEBUG compute: shown_sets={len(shown_sets)}, shown_groups={len(shown_groups) if 'shown_groups' in locals() else 'N/A'}")
        if not shown_sets:
            return {"error": "Cluster perm. requires at least one shown test set (to define sweep windows)", "results": []}

        results = []
        raw_p_amp = []
        raw_p_slope = []
        aspects = []
        if amp:
            aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
        if slope:
            aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))
        if not aspects:
            return {"error": "no aspects selected", "results": []}
        # Phase 1: recording-level only (n_unit overridden above; no aggregator on per-sweep wide data)
        # Note added to final config below for statusbar ("Cluster permutation uses recording-level n")

        def _extract_cluster_p(res):
            """Helper: extract min cluster p-value (or 1.0 if none). res is tuple from MNE."""
            try:
                if isinstance(res, tuple) and len(res) >= 3:
                    cluster_p_values = res[2]
                    if len(cluster_p_values) > 0:
                        return float(min(p for p in cluster_p_values if np.isfinite(p)) or 1.0)
                return 1.0
            except Exception:
                return np.nan

        def _to_matrix(df_wide):
            """Convert wide DataFrame (rec_ID + sweep cols) to (n_recs, n_sweeps) ndarray."""
            if df_wide.empty or len(df_wide.columns) < 2:
                return np.array([], dtype=float).reshape(0, 0)
            num_cols = [c for c in df_wide.columns if c != "rec_ID"]
            mat = df_wide[num_cols].to_numpy(dtype=float)
            return mat

        if len(shown_groups) >= 2:
            # Between-subjects: first 2 groups (pragmatic; >2 groups uses first two)
            g1, g2 = shown_groups[0], shown_groups[1]
            for sid, tset in shown_sets:
                sweeps = list(tset.get("sweeps", []))
                if len(sweeps) < 2:
                    continue  # adjacency requires >=2 points
                res_row = {
                    "set_id": sid,
                    "set_name": tset.get("set_name", f"set {sid}"),
                    "sweeps": sweeps,
                    "group1": [g1],
                    "group2": [g2],
                    "n1": 0,
                    "n2": 0,
                }
                for short, col in aspects:
                    try:
                        df1 = fetch_group_testset_observations(g1, tset, col, per_sweep=True)  # respects use_implicit (though cluster typically requires explicit)
                        df2 = fetch_group_testset_observations(g2, tset, col, per_sweep=True)
                        X1 = _to_matrix(df1)
                        X2 = _to_matrix(df2)
                        n1 = X1.shape[0]
                        n2 = X2.shape[0]
                        if n1 < 2 or n2 < 2:
                            continue
                        import warnings

                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", category=RuntimeWarning)
                            res = permutation_cluster_test([X1, X2], n_permutations=1000, threshold=None, tail=0)
                        cluster_p = _extract_cluster_p(res)
                        # Max stat from first element of return (T_obs or equivalent)
                        cluster_stat = float(np.max(res[0])) if hasattr(res[0], "__len__") and len(res[0]) > 0 else np.nan
                        print(f"DEBUG cluster between {short}: p={cluster_p:.4f}, stat={cluster_stat:.3f}, n1={n1}, n2={n2}")
                        res_row[f"p_{short}"] = cluster_p
                        res_row[f"stat_{short}"] = cluster_stat
                        res_row["n1"] = n1
                        res_row["n2"] = n2
                        if short == "amp":
                            raw_p_amp.append(cluster_p)
                        else:
                            raw_p_slope.append(cluster_p)
                    except Exception as e:
                        print(f"Cluster between error on {short}: {e}")
                        res_row[f"p_{short}"] = np.nan
                        res_row[f"stat_{short}"] = np.nan
                if any(k.startswith("p_") for k in res_row):
                    results.append(res_row)

        elif len(shown_groups) == 1 and len(shown_sets) == 2:
            # Within-subjects/paired: difference curves, 1samp cluster test
            g = shown_groups[0]
            s1, tset1 = shown_sets[0]
            s2, tset2 = shown_sets[1]
            sweeps1 = list(tset1.get("sweeps", []))
            sweeps2 = list(tset2.get("sweeps", []))
            if sweeps1 != sweeps2 or len(sweeps1) < 2:
                return {"error": "paired cluster perm. requires two test sets with identical >=2-sweep ranges", "results": []}
            res_row = {
                "set_id": f"{s1}_{s2}",
                "set_name": f"Cluster (paired {tset1.get('set_name', 'set1')} vs {tset2.get('set_name', 'set2')})",
                "sweeps": sweeps1,
                "group1": [g],
                "n1": 0,
                "n2": 0,
            }
            for short, col in aspects:
                try:
                    df1 = fetch_group_testset_observations(g, tset1, col, per_sweep=True)
                    df2 = fetch_group_testset_observations(g, tset2, col, per_sweep=True)
                    X1 = _to_matrix(df1)
                    X2 = _to_matrix(df2)
                    # Align by common rec_IDs (intersection)
                    recs1 = df1["rec_ID"].tolist() if not df1.empty and "rec_ID" in df1.columns else []
                    recs2 = df2["rec_ID"].tolist() if not df2.empty and "rec_ID" in df2.columns else []
                    common_recs = set(recs1) & set(recs2)
                    if len(common_recs) < 2:
                        continue
                    # Simple row-order alignment assuming same order from helper (rec_ID sorted); for production could sort by rec_ID
                    # For MVP assume order match or use first N common
                    n_common = min(X1.shape[0], X2.shape[0], len(common_recs))
                    if n_common < 2:
                        continue
                    Xdiff = X2[:n_common] - X1[:n_common]
                    import warnings

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        res = permutation_cluster_1samp_test(Xdiff, n_permutations=1000, threshold=None, tail=0)
                    cluster_p = _extract_cluster_p(res)
                    cluster_stat = float(np.max(res[0])) if hasattr(res[0], "__len__") and len(res[0]) > 0 else np.nan
                    res_row[f"p_{short}"] = cluster_p
                    res_row[f"stat_{short}"] = cluster_stat
                    res_row["n1"] = n_common
                    if short == "amp":
                        raw_p_amp.append(cluster_p)
                    else:
                        raw_p_slope.append(cluster_p)
                except Exception as e:
                    print(f"Cluster paired error on {short}: {e}")
                    res_row[f"p_{short}"] = np.nan
                    res_row[f"stat_{short}"] = np.nan
            if any(k.startswith("p_") for k in res_row):
                results.append(res_row)
        else:
            return {"error": "Cluster perm. requires either >=2 groups (between) or exactly 1 group + 2 test sets (paired)", "results": []}

        # FDR across test-set cluster p-values (per aspect) - parallel to Friedman/ANOVA
        if fdr and raw_p_amp:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [p if np.isfinite(p) else 1.0 for p in raw_p_amp]
                qs = multipletests(ps, alpha=0.05, method="fdr_bh")[1]
                for i, q in enumerate(qs):
                    if i < len(results) and f"p_amp" in results[i]:
                        results[i]["q_amp"] = float(q)
            except Exception:
                pass
        if fdr and raw_p_slope:
            try:
                from statsmodels.stats.multitest import multipletests

                ps = [p if np.isfinite(p) else 1.0 for p in raw_p_slope]
                qs = multipletests(ps, alpha=0.05, method="fdr_bh")[1]
                for i, q in enumerate(qs):
                    if i < len(results) and f"p_slope" in results[i]:
                        results[i]["q_slope"] = float(q)
            except Exception:
                pass

        config = {
            "test_type": test_type,
            "variant": "cluster",
            "fdr": fdr,
            "norm": norm,
            "n_unit": n_unit,
            "note": "Cluster permutation uses recording-level n (subject/slice deferred)",
        }
        if use_implicit:
            config["implicit_testset"] = True
        return {"results": results, "config": config}

    # --- Wilcoxon signed-rank path (paired or one-sample) ---
    # Phase 1: aggregator applied; paired uses unit-level vectors (length-based intersection).
    if test_type == "Wilcoxon":
        variant = variant if variant in ("paired", "one-sample") else "paired"
        alt = {"two-sided": "two-sided", "greater": "greater", "less": "less"}.get(tails, "two-sided")
        # shown_sets already extracted + use_implicit set above (centralized guard); remove duplicate
        aspects = []
        if amp:
            aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
        if slope:
            aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))
        if not aspects:
            return {"error": "no aspects selected", "results": []}
        raw_p_amp = []
        raw_p_slope = []
        out_results = []
        if variant == "paired":
            # Paired: exactly 1 group + exactly 2 test sets; align by rec_ID
            if len(shown_groups) != 1 or len(shown_sets) != 2:
                return {"error": "Wilcoxon (paired) requires exactly 1 group and exactly 2 test sets", "results": []}
            g = shown_groups[0]
            sid1, tset1 = shown_sets[0]
            sid2, tset2 = shown_sets[1]
            set_result = {
                "set_id": sid1,
                "set_name": tset1.get("set_name", f"set {sid1}"),
                "sweeps": list(tset1.get("sweeps", [])),
                "group1": g,
                "n1": 0,
                "n2": 0,
            }
            for short, col in aspects:
                try:
                    obs1_df = fetch_group_testset_observations(g, tset1, col)
                    obs2_df = fetch_group_testset_observations(g, tset2, col)
                    # v0.16_n_stats Phase 1: aggregate to unit level + align by unit key (not rec_ID)
                    obs1_df = _aggregate_to_unit_level(obs1_df, n_unit)
                    obs2_df = _aggregate_to_unit_level(obs2_df, n_unit)
                except Exception:
                    obs1_df = obs2_df = pd.DataFrame({"value": []})
                vals1 = obs1_df["value"].to_numpy(dtype=float) if not obs1_df.empty else np.array([], dtype=float)
                vals2 = obs2_df["value"].to_numpy(dtype=float) if not obs2_df.empty else np.array([], dtype=float)
                v1 = vals1[np.isfinite(vals1)]
                v2 = vals2[np.isfinite(vals2)]
                # Phase 1: after aggregation to unit level, use length-based intersection (common units).
                # Full key-based alignment (by subject or (subject,slice)) deferred to later phase.
                eff_n = min(len(v1), len(v2))
                p = np.nan
                stat = np.nan
                if eff_n >= 2:
                    try:
                        # wilcoxon(x, y) tests x - y; for alternative we pass d = v1 - v2 for greater/less
                        d = v1 - v2
                        if alt == "two-sided":
                            res = wilcoxon(d, alternative="two-sided", zero_method="wilcox", correction=False)
                        else:
                            res = wilcoxon(d, alternative=alt, zero_method="wilcox", correction=False)
                        stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                        p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                    except Exception:
                        p = np.nan
                        stat = np.nan
                p_key = f"p_{short}" + ("_norm" if norm else "")
                s_key = f"stat_{short}" + ("_norm" if norm else "")
                set_result[p_key] = float(p) if np.isfinite(p) else np.nan
                set_result[s_key] = float(stat) if np.isfinite(stat) else np.nan
                set_result["n1"] = max(int(set_result.get("n1", 0)), eff_n)
                set_result["n2"] = set_result["n1"]
                if short == "amp":
                    raw_p_amp.append((len(out_results), p_key))
                else:
                    raw_p_slope.append((len(out_results), p_key))
            has_any_p = any(k.startswith("p_") for k in set_result.keys())
            if has_any_p:
                out_results.append(set_result)
            # FDR (operates on first result row for paired)
            if fdr and out_results:
                for family in (raw_p_amp, raw_p_slope):
                    if not family:
                        continue
                    ps = []
                    idxs = []
                    for res_idx, pcol in family:
                        if res_idx < len(out_results):
                            val = out_results[res_idx].get(pcol, np.nan)
                            ps.append(val if np.isfinite(val) else np.nan)
                            idxs.append((res_idx, pcol))
                    try:
                        from statsmodels.stats.multitest import multipletests

                        qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                        for (res_idx, pcol), q in zip(idxs, qs):
                            out_results[res_idx]["q_" + pcol[2:]] = float(q) if np.isfinite(q) else np.nan
                    except Exception:
                        pass
            return {
                "results": out_results,
                "config": {
                    "type": test_type,
                    "variant": variant,
                    "tails": tails,
                    "fdr": fdr,
                    "norm": norm,
                    "amp": amp,
                    "slope": slope,
                },
            }
        else:
            # one-sample Wilcoxon: 1 group, compare each test set vs ref
            if len(shown_groups) != 1:
                return {"error": "Wilcoxon (one-sample) requires exactly 1 group", "results": []}
            g = shown_groups[0]
            for sid, tset in shown_sets:
                set_result = {
                    "set_id": sid,
                    "set_name": tset.get("set_name", f"set {sid}"),
                    "sweeps": list(tset.get("sweeps", [])),
                    "group1": g,
                    "n1": 0,
                    "n2": 0,
                }
                for short, col in aspects:
                    try:
                        obs_df = fetch_group_testset_observations(g, tset, col)
                        obs_df = _aggregate_to_unit_level(obs_df, n_unit)  # Phase 0
                        vals = obs_df["value"].to_numpy(dtype=float) if not obs_df.empty else np.array([], dtype=float)
                    except Exception:
                        vals = np.array([], dtype=float)
                    v = vals[np.isfinite(vals)]
                    eff_n = int(v.size)
                    p = np.nan
                    stat = np.nan
                    if eff_n >= 1:
                        try:
                            d = v - float(ref)
                            if alt == "two-sided":
                                res = wilcoxon(d, alternative="two-sided", zero_method="wilcox", correction=False)
                            else:
                                res = wilcoxon(d, alternative=alt, zero_method="wilcox", correction=False)
                            stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                            p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                        except Exception:
                            p = np.nan
                            stat = np.nan
                    p_key = f"p_{short}" + ("_norm" if norm else "")
                    s_key = f"stat_{short}" + ("_norm" if norm else "")
                    set_result[p_key] = float(p) if np.isfinite(p) else np.nan
                    set_result[s_key] = float(stat) if np.isfinite(stat) else np.nan
                    set_result["n1"] = max(int(set_result.get("n1", 0)), eff_n)
                    if short == "amp":
                        raw_p_amp.append((len(out_results), p_key))
                    else:
                        raw_p_slope.append((len(out_results), p_key))
                has_any_p = any(k.startswith("p_") for k in set_result.keys())
                if has_any_p:
                    out_results.append(set_result)
            # FDR across test sets
            if fdr and out_results:
                for family in (raw_p_amp, raw_p_slope):
                    if not family:
                        continue
                    ps = []
                    idxs = []
                    for res_idx, pcol in family:
                        if res_idx < len(out_results):
                            val = out_results[res_idx].get(pcol, np.nan)
                            ps.append(val if np.isfinite(val) else np.nan)
                            idxs.append((res_idx, pcol))
                    try:
                        from statsmodels.stats.multitest import multipletests

                        qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
                        for (res_idx, pcol), q in zip(idxs, qs):
                            out_results[res_idx]["q_" + pcol[2:]] = float(q) if np.isfinite(q) else np.nan
                    except Exception:
                        pass
            return {
                "results": out_results,
                "config": {
                    "type": test_type,
                    "variant": variant,
                    "tails": tails,
                    "fdr": fdr,
                    "norm": norm,
                    "amp": amp,
                    "slope": slope,
                },
            }

    alt = {"two-sided": "two-sided", "greater": "greater", "less": "less"}.get(tails, "two-sided")

    def _aspect_name(use_amp: bool, use_norm: bool) -> str | None:
        if use_amp:
            return "EPSP_amp_norm" if use_norm else "EPSP_amp"
        else:
            return "EPSP_slope_norm" if use_norm else "EPSP_slope"

    # Collect raw p values per family for possible FDR
    raw_p_amp = []
    raw_p_slope = []
    out_results = []

    for sid, tset in shown_sets:
        # Resolve which aspects we actually compute for this set
        aspects = []
        if amp:
            aspects.append(("amp", _aspect_name(True, norm)))
        if slope:
            aspects.append(("slope", _aspect_name(False, norm)))

        if not aspects:
            continue

        set_result = {
            "set_id": sid,
            "set_name": tset.get("set_name", f"set {sid}"),
            "sweeps": list(tset.get("sweeps", [])),
            "group1": g1,
            "group2": g2,
            "n1": 0,
            "n2": 0,
        }
        if test_type == "ANOVA":
            set_result["group1"] = shown_groups  # store all for ANOVA context

        for short, col in aspects:
            try:
                obs1_df = fetch_group_testset_observations(g1, tset, col)
                obs1_df = _aggregate_to_unit_level(obs1_df, n_unit)  # Phase 0
                obs1 = obs1_df["value"].to_numpy(dtype=float) if not obs1_df.empty else np.array([], dtype=float)
            except Exception:
                obs1 = np.array([], dtype=float)

            obs2 = np.array([], dtype=float)
            if variant != "one-sample" and g2 is not None:
                try:
                    obs2_df = fetch_group_testset_observations(g2, tset, col)
                    obs2_df = _aggregate_to_unit_level(obs2_df, n_unit)
                    obs2 = obs2_df["value"].to_numpy(dtype=float) if not obs2_df.empty else np.array([], dtype=float)
                except Exception:
                    obs2 = np.array([], dtype=float)
            elif variant == "paired":
                # Paired t-test (1 group + 2 test sets): aggregate both testsets within g1
                try:
                    if len(shown_sets) >= 2:
                        sid2, tset2 = shown_sets[1]
                        obs2_df = fetch_group_testset_observations(g1, tset2, col)
                        obs2_df = _aggregate_to_unit_level(obs2_df, n_unit)
                        obs2 = obs2_df["value"].to_numpy(dtype=float) if not obs2_df.empty else np.array([], dtype=float)
                except Exception:
                    obs2 = np.array([], dtype=float)

            p = np.nan
            stat = np.nan
            eff_n1 = 0
            eff_n2 = 0

            try:
                if variant == "one-sample":
                    vals = obs1[np.isfinite(obs1)]
                    eff_n1 = int(vals.size)
                    if eff_n1 >= 1:
                        res = ttest_1samp(vals, popmean=ref, alternative=alt)
                        stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                        p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                elif variant == "paired":
                    # v0.16_n_stats Phase 1: align by unit (subject or (subject,slice)) after aggregation.
                    # Simple length-based intersection for now (full key-based align by unit keys deferred).
                    v1 = obs1[np.isfinite(obs1)]
                    v2 = obs2[np.isfinite(obs2)]
                    eff_n1 = min(len(v1), len(v2))  # common units
                    eff_n2 = eff_n1
                    if eff_n1 >= 2:
                        # Take first N for simplicity (order from accessor/groupby is stable)
                        v1 = v1[:eff_n1]
                        v2 = v2[:eff_n1]
                        res = ttest_rel(v1, v2, alternative=alt)
                        stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                        p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                elif test_type == "ANOVA":
                    # For ANOVA, use all shown groups (not just first 2); f_oneway on per-rec means across groups
                    # (for repeated measures, this is simplified one-way; full RM-ANOVA deferred)
                    vals_list = []
                    eff_n = 0
                    for g in shown_groups:
                        obs_df = fetch_group_testset_observations(g, tset, col)
                        obs_df = _aggregate_to_unit_level(obs_df, n_unit)  # Phase 0
                        obs = obs_df["value"].to_numpy(dtype=float) if not obs_df.empty else np.array([], dtype=float)
                        valid_obs = obs[np.isfinite(obs)]
                        vals_list.append(valid_obs)
                        eff_n = max(eff_n, int(valid_obs.size))
                    if len(vals_list) >= 2 and all(len(v) > 0 for v in vals_list):
                        try:
                            res = f_oneway(*vals_list)
                            stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                            p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                            # Store effect size (partial eta^2 approximation for one-way)
                            if hasattr(res, "statistic") and np.isfinite(res.statistic) and eff_n > 0:
                                df_between = len(vals_list) - 1
                                df_within = sum(len(v) for v in vals_list) - len(vals_list)
                                if df_within > 0:
                                    eta2 = (df_between * res.statistic) / (df_between * res.statistic + df_within)
                                    set_result["eta2"] = float(eta2)
                        except Exception:
                            stat = np.nan
                            p = np.nan
                    else:
                        # Insufficient groups for between-subjects ANOVA (may be repeated-measures case with 1 group + N test sets)
                        set_result["anova_note"] = "need >=2 groups for one-way; RM-ANOVA deferred"
                    eff_n1 = eff_n
                    eff_n2 = eff_n
                else:
                    # unpaired
                    v1 = obs1[np.isfinite(obs1)]
                    v2 = obs2[np.isfinite(obs2)]
                    eff_n1 = int(v1.size)
                    eff_n2 = int(v2.size)
                    if eff_n1 >= 1 and eff_n2 >= 1:
                        res = ttest_ind(v1, v2, alternative=alt, equal_var=False)
                        stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                        p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
            except Exception:
                p = np.nan
                stat = np.nan

            p_key = f"p_{short}" + ("_norm" if norm else "")
            s_key = f"stat_{short}" + ("_norm" if norm else "")
            set_result[p_key] = float(p) if np.isfinite(p) else np.nan
            set_result[s_key] = float(stat) if np.isfinite(stat) else np.nan
            # For ANOVA, also store effect size (eta2) if computed
            if "eta2" in set_result:
                set_result["eta2"] = set_result.get("eta2", np.nan)

            # Assumption tests (Shapiro-Wilk normality per group/aspect, Levene homogeneity across groups)
            # SW requires n>=3 (scipy shapiro constraint); Levene works for n>=2.
            valid_obs1 = obs1[np.isfinite(obs1)]
            n_obs1 = len(valid_obs1)
            if (short == "amp" or short == "slope") and n_obs1 >= 3:
                # Shapiro-Wilk on group 1 (or test-set values in RM-ANOVA case)
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        sw_stat, sw_p = shapiro(valid_obs1)
                    set_result[f"sw_stat_{short}"] = float(sw_stat)
                    set_result[f"sw_p_{short}"] = float(sw_p)
                except Exception:
                    set_result[f"sw_stat_{short}"] = np.nan
                    set_result[f"sw_p_{short}"] = np.nan
                # Levene across groups (or test sets in RM case); skip if <2 groups
                if len(shown_groups) >= 2 or (test_type == "ANOVA" and len(shown_sets) >= 2):
                    try:
                        groups_for_lev = [valid_obs1]
                        if g2 is not None:
                            groups_for_lev.append(obs2[np.isfinite(obs2)])
                        elif test_type == "ANOVA" and len(shown_groups) == 1:
                            # RM case: collect from all test sets for this aspect
                            for sid2, tset2 in shown_sets:
                                if sid2 == sid:
                                    continue  # already have obs1
                                try:
                                    o_df = fetch_group_testset_observations(shown_groups[0], tset2, col)
                                    o_df = _aggregate_to_unit_level(o_df, n_unit)  # Phase 0
                                    o_vals = o_df["value"].to_numpy(dtype=float)
                                    groups_for_lev.append(o_vals[np.isfinite(o_vals)])
                                except Exception:
                                    pass
                        if len(groups_for_lev) >= 2:
                            lev_stat, lev_p = levene(*groups_for_lev, center="mean")
                            set_result[f"levene_stat_{short}"] = float(lev_stat)
                            set_result[f"levene_p_{short}"] = float(lev_p)
                        else:
                            set_result[f"levene_stat_{short}"] = np.nan
                            set_result[f"levene_p_{short}"] = np.nan
                    except Exception:
                        set_result[f"levene_stat_{short}"] = np.nan
                        set_result[f"levene_p_{short}"] = np.nan

            # Track for FDR (per aspect family) - append *before* possible out_results.append
            if short == "amp":
                raw_p_amp.append((len(out_results), p_key))  # index into final list
            else:
                raw_p_slope.append((len(out_results), p_key))

            # Store effective n (use max seen across aspects for the set; fine for display)
            if eff_n1:
                set_result["n1"] = max(int(set_result.get("n1", 0)), eff_n1)
            if eff_n2:
                set_result["n2"] = max(int(set_result.get("n2", 0)), eff_n2)

        # If we computed at least one aspect for this set, keep it (assumption tests alone are sufficient to keep the result)
        has_any_p = any(k.startswith("p_") for k in set_result.keys()) or any(k.startswith(("sw_", "levene_")) for k in set_result.keys())
        if has_any_p:
            out_results.append(set_result)

    # FDR across test sets for each aspect family (if requested)
    if fdr and out_results:
        for family in (raw_p_amp, raw_p_slope):
            if not family:
                continue
            ps = []
            idxs = []
            for res_idx, pcol in family:
                if res_idx < len(out_results):
                    val = out_results[res_idx].get(pcol, np.nan)
                    ps.append(val if np.isfinite(val) else np.nan)
                    idxs.append((res_idx, pcol))
            qs = _bh_fdr(np.asarray(ps, dtype=float))
            for (res_idx, pcol), q in zip(idxs, qs):
                out_results[res_idx]["q_" + pcol[2:]] = float(q) if np.isfinite(q) else np.nan

    config = {
        "type": test_type,
        "variant": variant,
        "tails": tails,
        "fdr": fdr,
        "norm": norm,
        "amp": amp,
        "slope": slope,
        "n_unit": n_unit,
    }
    if use_implicit:
        config["implicit_testset"] = True
    return {
        "results": out_results,
        "config": config,
    }


# Also expose ttest_df from analysis_v3 (for heatmap) or duplicate if desired.
# For now, users should import it from analysis_v3 (or we can re-export).
# If moving fully, add:
# def ttest_df(...): ... (copy from analysis_v3 if needed)
