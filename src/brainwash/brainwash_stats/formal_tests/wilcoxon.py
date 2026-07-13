import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from ..data import _aggregate_to_unit_level, _aspect_measurement_columns


def _apply_wilcoxon_fdr(out_results, raw_p_amp, raw_p_slope, fdr):
    if not fdr or not out_results:
        return
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


def _wilcoxon_config(test_type, variant, tails, fdr, norm, amp, slope):
    return {
        "type": test_type,
        "variant": variant,
        "tails": tails,
        "fdr": fdr,
        "norm": norm,
        "amp": amp,
        "slope": slope,
    }


def run_wilcoxon_tests(
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
    variant,
    tails,
    ref,
) -> dict:
    """Wilcoxon signed-rank: paired (1 group, 2 test sets) or one-sample vs ref."""
    variant = variant if variant in ("paired", "one-sample") else "paired"
    alt = {"two-sided": "two-sided", "greater": "greater", "less": "less"}.get(tails, "two-sided")
    aspects = _aspect_measurement_columns(amp, slope, norm)
    if not aspects:
        return {"error": "no aspects selected", "results": []}

    raw_p_amp = []
    raw_p_slope = []
    out_results = []

    if variant == "paired":
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
                obs1_df = _aggregate_to_unit_level(obs1_df, n_unit)
                obs2_df = _aggregate_to_unit_level(obs2_df, n_unit)
            except Exception:
                obs1_df = obs2_df = pd.DataFrame({"value": []})
            vals1 = obs1_df["value"].to_numpy(dtype=float) if not obs1_df.empty else np.array([], dtype=float)
            vals2 = obs2_df["value"].to_numpy(dtype=float) if not obs2_df.empty else np.array([], dtype=float)
            v1 = vals1[np.isfinite(vals1)]
            v2 = vals2[np.isfinite(vals2)]
            eff_n = min(len(v1), len(v2))
            p = np.nan
            stat = np.nan
            if eff_n >= 2:
                try:
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
        if any(k.startswith("p_") for k in set_result.keys()):
            out_results.append(set_result)
        _apply_wilcoxon_fdr(out_results, raw_p_amp, raw_p_slope, fdr)
        return {"results": out_results, "config": _wilcoxon_config(test_type, variant, tails, fdr, norm, amp, slope)}

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
                obs_df = _aggregate_to_unit_level(obs_df, n_unit)
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
        if any(k.startswith("p_") for k in set_result.keys()):
            out_results.append(set_result)
    _apply_wilcoxon_fdr(out_results, raw_p_amp, raw_p_slope, fdr)
    return {"results": out_results, "config": _wilcoxon_config(test_type, variant, tails, fdr, norm, amp, slope)}
