import numpy as np
from scipy.stats import f_oneway

from ..data import _aggregate_to_unit_level, _aspect_measurement_columns


def run_repeated_measures_anova(
    *,
    shown_groups,
    shown_sets,
    fetch_group_testset_observations,
    n_unit,
    norm,
    amp,
    slope,
    fdr,
    test_type,
) -> dict:
    """Omnibus one-way ANOVA across test sets within a single group (>=2 test sets)."""
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
