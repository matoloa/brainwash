import warnings

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import f_oneway, friedmanchisquare, levene, linregress, shapiro, ttest_1samp, ttest_ind, ttest_ind_from_stats, ttest_rel, wilcoxon


def _aspect_columns(amp: bool = True, slope: bool = True, norm: bool = False):
    aspects = []
    if amp:
        aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
    if slope:
        aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))
    if not aspects:
        aspects = [("amp", "EPSP_amp")]
    return aspects


def _make_get_obs(get_group_testset_means_fn, use_implicit: bool = False):
    def _get_obs(g, tset, col, per_sweep: bool = False):
        sweeps_arg = None if use_implicit else (list(tset.get("sweeps", [])) if tset else [])
        return get_group_testset_means_fn(g, sweeps_arg, aspect=col, per_sweep=per_sweep)

    return _get_obs


def _aggregate_to_unit_level(obs_df, n_unit="subject"):
    if obs_df.empty or n_unit == "recording" or "value" not in obs_df.columns:
        return obs_df.copy() if not obs_df.empty else obs_df

    if n_unit == "subject":
        group_keys = ["subject"]
    elif n_unit == "slice":
        group_keys = ["subject", "slice"]
    else:
        group_keys = ["subject"]

    if not all(k in obs_df.columns for k in group_keys):
        return obs_df.copy()

    valid = obs_df[group_keys + ["value"]].dropna()
    if valid.empty:
        empty_df = pd.DataFrame({k: pd.Series(dtype=obs_df[k].dtype if k in obs_df.columns else "object") for k in group_keys})
        empty_df["value"] = pd.Series(dtype=float)
        return empty_df

    agg = valid.groupby(group_keys, as_index=False)["value"].mean()
    return agg


def _apply_assumption_tests(set_result, obs1, obs2, short, shown_groups, shown_sets, test_type, n_unit, _get_obs):
    """Extracted Shapiro-Wilk + Levene block. Pure; populates sw_/levene_ keys in set_result."""
    # SW requires n>=3; Levene >=2 groups.
    valid_obs1 = obs1[np.isfinite(obs1)]
    n_obs1 = len(valid_obs1)
    if (short in ("amp", "slope")) and n_obs1 >= 3:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sw_stat, sw_p = shapiro(valid_obs1)
            set_result[f"sw_stat_{short}"] = float(sw_stat)
            set_result[f"sw_p_{short}"] = float(sw_p)
        except Exception:
            set_result[f"sw_stat_{short}"] = np.nan
            set_result[f"sw_p_{short}"] = np.nan

        if len(shown_groups) >= 2 or (test_type == "ANOVA" and len(shown_sets) >= 2):
            try:
                groups_for_lev = [valid_obs1]
                if obs2 is not None and len(obs2) > 0:
                    groups_for_lev.append(obs2[np.isfinite(obs2)])
                elif test_type == "ANOVA" and len(shown_groups) == 1:
                    for sid2, tset2 in shown_sets:
                        if sid2 == getattr(set_result, "sid", None):  # avoid self
                            continue
                        try:
                            o_df = _get_obs(shown_groups[0], tset2, short.replace("p_", "") if "p_" in short else "EPSP_amp")
                            o_df = _aggregate_to_unit_level(o_df, n_unit)
                            o_vals = o_df["value"].to_numpy(dtype=float) if not o_df.empty else np.array([])
                            if len(o_vals) > 0:
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
        else:
            set_result[f"levene_stat_{short}"] = np.nan
            set_result[f"levene_p_{short}"] = np.nan


def _get_io_xy_pairs(g, get_group_testset_means_fn, uistate=None, n_unit="recording", aspect_col="EPSP_amp"):
    """Private helper: Returns long DataFrame with ['rec_ID', 'subject', 'slice', 'x', 'y'] for all sweeps in group.
    Uses per_sweep=True, melts, joins real X from dfoutput via uistate.io_input. Falls back to sweep rank if X missing.
    Respects n_unit.
    """
    if uistate is None:
        # Fallback for testing
        io_input = "vamp"
        io_output = "EPSPamp"
    else:
        io_input = getattr(uistate, "io_input", "vamp")
        io_output = getattr(uistate, "io_output", "EPSPamp")

    x_map = {
        "vamp": "volley_amp",
        "fiber": "fiber_amp",
        "presyn": "presyn_amp",
        "ihold": "holding_current",
    }
    x_col = x_map.get(io_input, "volley_amp")
    y_col = aspect_col

    # Get wide per-sweep matrix (rec_ID + sweep cols) or fallback
    try:
        wide_df = get_group_testset_means_fn(g, sweeps=None, aspect=y_col, per_sweep=True)
    except Exception:
        wide_df = pd.DataFrame()

    if wide_df.empty or "rec_ID" not in wide_df.columns:
        return pd.DataFrame(columns=["rec_ID", "subject", "slice", "x", "y"])

    # Melt to long (sweep as int for matching)
    id_vars = ["rec_ID"]
    if "subject" in wide_df.columns:
        id_vars.append("subject")
    if "slice" in wide_df.columns:
        id_vars.append("slice")

    long = wide_df.melt(id_vars=id_vars, var_name="sweep", value_name="y")
    long = long[long["sweep"].astype(str).str.isdigit()].copy()  # only numeric sweeps
    long["sweep"] = pd.to_numeric(long["sweep"], errors="coerce").astype(int)

    # Join real X from full dfoutput (per group recs, using df_project access via accessor self)
    try:
        # Recover df_project / get_dfoutput from the mixin instance if possible
        if hasattr(get_group_testset_means_fn, "__self__"):
            mixin = get_group_testset_means_fn.__self__
            df_p = mixin.get_df_project()
            recs = df_p[df_p["ID"].isin(wide_df["rec_ID"].astype(str))]["recording_name"].tolist() if not df_p.empty else []
            if recs:
                dfs = []
                for rec_name in recs:
                    prow = df_p[df_p["recording_name"] == rec_name].iloc[0]
                    dfo = mixin.get_dfoutput(row=prow)
                    if dfo is not None and not dfo.empty:
                        dfs.append(dfo[["sweep", x_col]].copy() if x_col in dfo.columns else dfo[["sweep"]].copy())
                if dfs:
                    x_df = pd.concat(dfs, ignore_index=True)
                    long = long.merge(x_df, on="sweep", how="left")
                    long = long.rename(columns={x_col: "x"})
                else:
                    long["x"] = long["sweep"].rank(method="dense")  # fallback rank
            else:
                long["x"] = long["sweep"].rank(method="dense")
        else:
            long["x"] = long["sweep"].rank(method="dense")
    except Exception:
        long["x"] = long["sweep"].rank(method="dense")

    return long[["rec_ID", "subject", "slice", "x", "y"]].dropna().sort_values("x")


def _compute_io_regression_internal(
    shown_groups, get_group_testset_means_fn, uistate=None, n_unit="subject", norm=False, amp=True, slope=True, dd_groups=None
):
    """Core IO regression: X/Y pairs per group (_get_io_xy_pairs), linregress per group, OLS slope comparison.
    Returns dict compatible with statusbar (config with "type": "IO regression", r2_per_group, slope_p, group_ns).
    """
    results = []
    group_ns = {}
    r2_per_group = {}
    slope_per_group = {}
    aspects = _aspect_columns(amp=amp, slope=slope, norm=norm)

    for short, col in aspects:
        group_data = {}
        for g in shown_groups:
            try:
                xy_df = _get_io_xy_pairs(g, get_group_testset_means_fn, uistate, n_unit=n_unit, aspect_col=col)
                if xy_df.empty or len(xy_df) < 2:
                    group_data[g] = {"x": np.array([]), "y": np.array([]), "n": 0}
                    continue
                x = xy_df["x"].to_numpy(dtype=float)
                y = xy_df["y"].to_numpy(dtype=float)
                valid = np.isfinite(x) & np.isfinite(y)
                if valid.sum() < 2:
                    group_data[g] = {"x": np.array([]), "y": np.array([]), "n": 0}
                    continue
                # n = unique units per AGENTS.md (not XY pairs); nunique on full xy_df before valid mask (ensures n=4 subjects not 0)
                n = len(xy_df.drop_duplicates(subset=["subject", "slice"] if n_unit == "slice" else ["subject"])) if not xy_df.empty else 0
                group_data[g] = {"x": x[valid], "y": y[valid], "n": n}
                group_ns[g] = n
            except Exception:
                group_data[g] = {"x": np.array([]), "y": np.array([]), "n": 0}
                group_ns[g] = 0

        if not group_data:
            continue

        # linregress per group
        for g, data in group_data.items():
            if len(data["x"]) < 2:
                r2_per_group[g] = np.nan
                slope_per_group[g] = np.nan
                continue
            try:
                res = linregress(data["x"], data["y"])
                r2_per_group[g] = float(res.rvalue**2) if hasattr(res, "rvalue") else np.nan
                slope_per_group[g] = float(res.slope) if hasattr(res, "slope") else np.nan
            except Exception:
                r2_per_group[g] = np.nan
                slope_per_group[g] = np.nan

        # OLS slope comparison if >=2 groups (statsmodels)
        slope_p = np.nan
        if len(shown_groups) >= 2 and len([g for g in shown_groups if group_data.get(g, {}).get("n", 0) >= 2]) >= 2:
            try:
                # Lazy import statsmodels (as done for FDR/multipletests)
                import statsmodels.api as sm
                from statsmodels.formula.api import ols

                dfs = []
                for g in shown_groups:
                    d = group_data.get(g, {})
                    if len(d.get("x", [])) >= 2:
                        dfg = pd.DataFrame({"x": d["x"], "y": d["y"], "group": g})
                        dfs.append(dfg)
                if dfs:
                    df = pd.concat(dfs, ignore_index=True)
                    df["group"] = pd.Categorical(df["group"])
                    model = ols("y ~ x * C(group)", data=df).fit()
                    # ANOVA on interaction term for slope diff
                    anova_table = sm.stats.anova_lm(model, typ=2)
                    if "C(group):x" in anova_table.index:
                        slope_p = float(anova_table.loc["C(group):x", "PR(>F)"])
                    else:
                        slope_p = np.nan
            except Exception:
                slope_p = np.nan

        results.append(
            {
                "set_id": "__io_regression_implicit__",
                "set_name": None,
                "sweeps": [],
                "group1": shown_groups,
                "n1": sum(group_ns.values()),
                "slope_p": float(slope_p) if np.isfinite(slope_p) else np.nan,
                "r2_per_group": r2_per_group,
                "group_ns": group_ns,
            }
        )

    config = {
        "type": "IO regression",
        "norm": norm,
        "amp": amp,
        "slope": slope,
        "n_unit": n_unit,
        "r2_per_group": r2_per_group,
        "slope_p": float(slope_p) if "slope_p" in locals() and np.isfinite(slope_p) else np.nan,
    }
    if dd_groups:
        config["groups"] = list(dd_groups.keys())
    return {
        "results": results,
        "config": config,
    }


def _bh_fdr(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR correction. Returns q-values in [0,1]."""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    if n == 0:
        return np.array([], dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    q = np.empty(n, dtype=float)
    q[order[-1]] = ranked[-1]
    for i in range(n - 2, -1, -1):
        q[order[i]] = min(ranked[i] * n / (i + 1), q[order[i + 1]])
    q = np.minimum(q, 1.0)
    return q


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
    return pd.DataFrame()


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
):
    if experiment_type == "io" and not dd_testsets:
        return _compute_io_regression_internal(
            shown_groups=groups or [],
            get_group_testset_means_fn=get_group_testset_means_fn,
            uistate=uistate,
            n_unit=n_unit,
            norm=norm,
            amp=amp,
            slope=slope,
            dd_groups=dd_groups,
        )
    return {"results": [], "config": {"type": test_type}}
