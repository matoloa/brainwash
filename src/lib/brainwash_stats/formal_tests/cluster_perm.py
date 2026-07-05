import warnings

import numpy as np


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


def run_cluster_permutation(
    *,
    shown_groups,
    dd_testsets,
    fetch_group_testset_observations,
    n_unit,
    norm,
    amp,
    slope,
    fdr,
    test_type,
    use_implicit,
) -> dict:
    print(
        f"DEBUG compute_statistical_comparison: entered Cluster perm. branch with "
        f"{len(shown_groups) if shown_groups else 0} groups, test_type={test_type}"
    )
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

    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    print(f"DEBUG compute: shown_sets={len(shown_sets)}, shown_groups={len(shown_groups) if shown_groups else 'N/A'}")
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

    if len(shown_groups) >= 2:
        g1, g2 = shown_groups[0], shown_groups[1]
        for sid, tset in shown_sets:
            sweeps = list(tset.get("sweeps", []))
            if len(sweeps) < 2:
                continue
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
                    df1 = fetch_group_testset_observations(g1, tset, col, per_sweep=True)
                    df2 = fetch_group_testset_observations(g2, tset, col, per_sweep=True)
                    X1 = _to_matrix(df1)
                    X2 = _to_matrix(df2)
                    n1 = X1.shape[0]
                    n2 = X2.shape[0]
                    if n1 < 2 or n2 < 2:
                        continue
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        res = permutation_cluster_test([X1, X2], n_permutations=1000, threshold=None, tail=0)
                    cluster_p = _extract_cluster_p(res)
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
                recs1 = df1["rec_ID"].tolist() if not df1.empty and "rec_ID" in df1.columns else []
                recs2 = df2["rec_ID"].tolist() if not df2.empty and "rec_ID" in df2.columns else []
                common_recs = set(recs1) & set(recs2)
                if len(common_recs) < 2:
                    continue
                n_common = min(X1.shape[0], X2.shape[0], len(common_recs))
                if n_common < 2:
                    continue
                Xdiff = X2[:n_common] - X1[:n_common]
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