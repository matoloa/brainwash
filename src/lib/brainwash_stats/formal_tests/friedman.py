import numpy as np
from scipy.stats import friedmanchisquare

from ..data import _aggregate_to_unit_level, _aspect_measurement_columns


def run_friedman_omnibus(
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
    """Repeated-measures Friedman omnibus (1 group, >=3 test sets)."""
    g = shown_groups[0]
    fm_res = {
        "set_id": "__friedman_rm_omnibus__",
        "set_name": "Friedman (repeated, omnibus)",
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
                vals_list.append(valid)
            except Exception:
                vals_list.append(np.array([], dtype=float))
        if len(vals_list) >= 3 and all(len(v) > 0 for v in vals_list):
            try:
                min_len = min(len(v) for v in vals_list)
                if min_len < 2:
                    continue
                aligned = [v[:min_len] for v in vals_list]
                res = friedmanchisquare(*aligned)
                p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                eff_n = min_len
                p_key = f"p_{short}"
                fm_res[p_key] = float(p) if np.isfinite(p) else np.nan
                fm_res[f"stat_{short}"] = float(stat) if np.isfinite(stat) else np.nan
                fm_res["n1"] = max(fm_res.get("n1", 0), eff_n)
                if short == "amp":
                    raw_p_amp.append(p_key)
                else:
                    raw_p_slope.append(p_key)
            except Exception:
                pass

    has_p = any(k.startswith("p_") for k in fm_res if isinstance(k, str))
    fm_results = [fm_res] if has_p else []

    if fdr and raw_p_amp:
        try:
            from statsmodels.stats.multitest import multipletests

            ps = [fm_res.get(k, np.nan) for k in raw_p_amp]
            qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
            for k, q in zip(raw_p_amp, qs):
                fm_res["q_" + k[2:]] = float(q)
        except Exception:
            pass
    if fdr and raw_p_slope:
        try:
            from statsmodels.stats.multitest import multipletests

            ps = [fm_res.get(k, np.nan) for k in raw_p_slope]
            qs = multipletests([p if np.isfinite(p) else 1.0 for p in ps], alpha=0.05, method="fdr_bh")[1]
            for k, q in zip(raw_p_slope, qs):
                fm_res["q_" + k[2:]] = float(q)
        except Exception:
            pass

    return {"results": fm_results, "config": {"test_type": test_type, "variant": "repeated", "fdr": fdr, "norm": norm}}
