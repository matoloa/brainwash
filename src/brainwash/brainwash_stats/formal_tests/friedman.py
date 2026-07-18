import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare

from ..data import _aggregate_to_unit_level, _align_multi_condition_unit_values, _aspect_measurement_columns


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
    """Repeated-measures Friedman omnibus: exactly 1 group, ≥3 test sets, unit-key complete cases."""
    if len(shown_groups) != 1:
        return {"error": "Friedman requires exactly 1 group", "results": []}
    if len(shown_sets) < 3:
        return {"error": "Friedman requires at least 3 shown test sets", "results": []}

    g = shown_groups[0]
    all_sweeps: list = []
    set_labels: list[str] = []
    for sid, tset in shown_sets:
        all_sweeps.extend(list(tset.get("sweeps") or []))
        set_labels.append(tset.get("set_name", f"set {sid}"))

    fm_res = {
        "set_id": "__friedman_rm_omnibus__",
        "set_name": "Friedman (repeated, omnibus)",
        "sweeps": all_sweeps,
        "group1": shown_groups,
        "n1": 0,
        "n2": 0,
        "n_pairs": 0,
        "n_dropped": 0,
        "paired_dropped": [],
    }
    raw_p_amp = []
    raw_p_slope = []
    aspects = _aspect_measurement_columns(amp, slope, norm)
    all_dropped: list[dict] = []
    seen_drop_units: set[str] = set()

    for short, col in aspects:
        obs_dfs = []
        for _sid, tset in shown_sets:
            try:
                obs_df = fetch_group_testset_observations(g, tset, col)
                obs_df = _aggregate_to_unit_level(obs_df, n_unit)
            except Exception:
                obs_df = pd.DataFrame({"value": []})
            obs_dfs.append(obs_df)

        aligned = _align_multi_condition_unit_values(obs_dfs, n_unit=n_unit, condition_labels=set_labels)
        values = aligned["values"]
        n_pairs = int(aligned["n_pairs"])
        n_dropped = int(aligned["n_dropped"])
        for d in aligned.get("dropped") or []:
            u = d.get("unit")
            if u is not None and u not in seen_drop_units:
                seen_drop_units.add(u)
                all_dropped.append(d)

        p = np.nan
        stat = np.nan
        if n_pairs >= 2 and len(values) >= 3:
            try:
                res = friedmanchisquare(*values)
                p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
            except Exception:
                p = np.nan
                stat = np.nan

        p_key = f"p_{short}"
        fm_res[p_key] = float(p) if np.isfinite(p) else np.nan
        fm_res[f"stat_{short}"] = float(stat) if np.isfinite(stat) else np.nan
        fm_res[f"n_pairs_{short}"] = n_pairs
        fm_res[f"n_dropped_{short}"] = n_dropped
        fm_res["n1"] = max(int(fm_res.get("n1", 0)), n_pairs)
        fm_res["n_pairs"] = max(int(fm_res.get("n_pairs", 0)), n_pairs)
        fm_res["n_dropped"] = max(int(fm_res.get("n_dropped", 0)), n_dropped)
        if short == "amp":
            raw_p_amp.append(p_key)
        else:
            raw_p_slope.append(p_key)

    fm_res["paired_dropped"] = all_dropped
    fm_res["n_dropped"] = max(int(fm_res.get("n_dropped", 0)), len(all_dropped))
    gns = fm_res.setdefault("group_ns", {})
    n_complete = int(fm_res.get("n_pairs", 0) or 0)
    if n_complete:
        gns[g] = n_complete

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

    return {
        "results": fm_results,
        "config": {
            "type": test_type,
            "test_type": test_type,
            "variant": "repeated",
            "fdr": fdr,
            "norm": norm,
            "n_unit": n_unit,
        },
    }
