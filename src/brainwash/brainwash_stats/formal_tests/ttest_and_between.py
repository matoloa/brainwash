import numpy as np
from scipy.stats import f_oneway, ttest_1samp, ttest_ind, ttest_rel

from ..assumptions import _apply_assumption_tests
from ..data import _aggregate_to_unit_level
from ..fdr import _bh_fdr


def _aspect_name(use_amp: bool, use_norm: bool) -> str | None:
    if use_amp:
        return "EPSP_amp_norm" if use_norm else "EPSP_amp"
    return "EPSP_slope_norm" if use_norm else "EPSP_slope"


def run_main_test_set_loop(
    *,
    shown_groups,
    shown_sets,
    g1,
    g2,
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
    use_implicit,
    test_sw: bool = False,
    test_levene: bool = False,
) -> dict:
    alt = {"two-sided": "two-sided", "greater": "greater", "less": "less"}.get(tails, "two-sided")

    raw_p_amp = []
    raw_p_slope = []
    out_results = []

    for sid, tset in shown_sets:
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
            set_result["group1"] = shown_groups

        for short, col in aspects:
            try:
                obs1_df = fetch_group_testset_observations(g1, tset, col)
                obs1_df = _aggregate_to_unit_level(obs1_df, n_unit)
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
                    v1 = obs1[np.isfinite(obs1)]
                    v2 = obs2[np.isfinite(obs2)]
                    eff_n1 = min(len(v1), len(v2))
                    eff_n2 = eff_n1
                    if eff_n1 >= 2:
                        v1 = v1[:eff_n1]
                        v2 = v2[:eff_n1]
                        res = ttest_rel(v1, v2, alternative=alt)
                        stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                        p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
                elif test_type == "ANOVA":
                    vals_list = []
                    eff_n = 0
                    for g in shown_groups:
                        obs_df = fetch_group_testset_observations(g, tset, col)
                        obs_df = _aggregate_to_unit_level(obs_df, n_unit)
                        obs = obs_df["value"].to_numpy(dtype=float) if not obs_df.empty else np.array([], dtype=float)
                        valid_obs = obs[np.isfinite(obs)]
                        vals_list.append(valid_obs)
                        eff_n = max(eff_n, int(valid_obs.size))
                    if len(vals_list) >= 2 and all(len(v) > 0 for v in vals_list):
                        try:
                            res = f_oneway(*vals_list)
                            stat = float(res.statistic) if hasattr(res, "statistic") else np.nan
                            p = float(res.pvalue) if hasattr(res, "pvalue") else np.nan
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
                        set_result["anova_note"] = "need >=2 groups for one-way; RM-ANOVA deferred"
                    eff_n1 = eff_n
                    eff_n2 = eff_n
                else:
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
            if "eta2" in set_result:
                set_result["eta2"] = set_result.get("eta2", np.nan)

            if test_sw or test_levene:
                _apply_assumption_tests(
                    set_result,
                    short=short,
                    obs1=obs1,
                    obs2=obs2,
                    g2=g2,
                    shown_groups=shown_groups,
                    test_type=test_type,
                    shown_sets=shown_sets,
                    sid=sid,
                    fetch_group_testset_observations=fetch_group_testset_observations,
                    n_unit=n_unit,
                    col=col,
                    do_sw=bool(test_sw),
                    do_levene=bool(test_levene),
                )

            if short == "amp":
                raw_p_amp.append((len(out_results), p_key))
            else:
                raw_p_slope.append((len(out_results), p_key))

            if eff_n1:
                set_result["n1"] = max(int(set_result.get("n1", 0)), eff_n1)
            if eff_n2:
                set_result["n2"] = max(int(set_result.get("n2", 0)), eff_n2)

            # Per-group unit counts for statusbar (after n_unit aggregation)
            gns = set_result.setdefault("group_ns", {})
            if g1 is not None and not isinstance(g1, (list, tuple)) and eff_n1:
                gns[g1] = max(int(gns.get(g1, 0)), eff_n1)
            if g2 is not None and not isinstance(g2, (list, tuple)) and eff_n2:
                gns[g2] = max(int(gns.get(g2, 0)), eff_n2)

        has_any_p = any(k.startswith("p_") for k in set_result.keys()) or any(
            k.startswith(("sw_", "levene_")) for k in set_result.keys()
        )
        if has_any_p:
            out_results.append(set_result)

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
    return {"results": out_results, "config": config}