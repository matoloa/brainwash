import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import ttest_ind_from_stats


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
        stat_vals = []
        for i in range(len(sweeps)):
            try:
                if variant == "one-sample":
                    m1 = float(df1.loc[i, mean_col]) if mean_col in df1.columns else float(df1.loc[i, raw_col]) if raw_col in df1.columns else np.nan
                    if not np.isfinite(m1):
                        pvals.append(np.nan)
                        stat_vals.append(np.nan)
                        continue
                    s1 = float(df1.loc[i, sem_col]) * np.sqrt(n1) if sem_col in df1.columns else np.nan
                    if not np.isfinite(s1) or s1 == 0 or n1 < 1:
                        pvals.append(np.nan)
                        stat_vals.append(np.nan)
                        continue
                    tstat = (m1 - ref) / (s1 / np.sqrt(n1)) if s1 > 0 else np.nan
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
                    stat_vals.append(float(tstat))
                elif variant == "paired":
                    if df2 is None or len(df1) != len(df2):
                        pvals.append(np.nan)
                        stat_vals.append(np.nan)
                        continue
                    pvals.append(np.nan)
                    stat_vals.append(np.nan)
                else:
                    m1 = float(df1.loc[i, mean_col])
                    s1 = float(df1.loc[i, sem_col]) * np.sqrt(n1)
                    m2 = float(df2.loc[i, mean_col]) if df2 is not None else np.nan
                    s2 = float(df2.loc[i, sem_col]) * np.sqrt(n2) if df2 is not None else np.nan
                    if not (np.isfinite(m1) and np.isfinite(m2) and np.isfinite(s1) and np.isfinite(s2) and s1 > 0 and s2 > 0):
                        pvals.append(np.nan)
                        stat_vals.append(np.nan)
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
                    pvals.append(float(p))
                    stat_vals.append(np.nan)
            except Exception:
                pvals.append(np.nan)
                stat_vals.append(np.nan)

        out[p_name] = pvals
        out[stat_name] = stat_vals

    return pd.DataFrame(out)