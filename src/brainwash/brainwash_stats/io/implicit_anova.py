import numpy as np
from scipy.stats import f_oneway

from ..data import _aspect_measurement_columns


def run_io_implicit_anova(
    *,
    shown_groups,
    fetch_group_testset_observations,
    n_unit,
    norm,
    amp,
    slope,
    fdr,
    test_type,
    tails,
) -> dict:
    """Latent implicit IO ANOVA (dead path when experiment_type=='io' hits regression first)."""
    out_results = []
    aspects = _aspect_measurement_columns(amp, slope, norm)

    set_result = {
        "set_id": "__io_anova_implicit__",
        "set_name": None,
        "sweeps": [],
        "group1": shown_groups,
        "n1": 0,
        "n2": 0,
        "anova_note": "between-groups one-way on all sweeps (implicit IO)",
    }
    raw_p_amp = []
    raw_p_slope = []
    group_ns = {}

    for short, col in aspects:
        vals_list = []
        n_per_group = []
        for g in shown_groups:
            try:
                obs_df = fetch_group_testset_observations(g, None, col)
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
                set_result["n2"] = set_result["n1"]
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

    set_result["group_ns"] = group_ns
    if any(k.startswith("p_") for k in set_result if isinstance(k, str)):
        out_results.append(set_result)

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
    return {"results": out_results, "config": config}