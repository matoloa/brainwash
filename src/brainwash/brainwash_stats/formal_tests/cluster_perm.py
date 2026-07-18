import warnings

import numpy as np
import pandas as pd


_HIERARCHY_COLS = frozenset({"rec_ID", "subject", "slice", "ID"})


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


def _sweep_columns(df_wide: pd.DataFrame) -> list[str]:
    """Numeric/sortable sweep columns only (exclude rec_ID / hierarchy)."""
    if df_wide is None or df_wide.empty:
        return []
    cols = []
    for c in df_wide.columns:
        if c in _HIERARCHY_COLS:
            continue
        # Sweep labels are typically int or str(int)
        try:
            float(c) if not isinstance(c, str) else float(c)
            cols.append(c)
        except (TypeError, ValueError):
            # Non-numeric column name (e.g. leftover labels) — skip
            continue
    # Sort by numeric value of label
    def _key(c):
        try:
            return (0, float(c))
        except (TypeError, ValueError):
            return (1, str(c))

    return sorted(cols, key=_key)


def _to_matrix(df_wide: pd.DataFrame, sweep_cols: list[str] | None = None) -> np.ndarray:
    """Convert wide DataFrame to (n_recs, n_sweeps) using only sorted sweep columns."""
    if df_wide is None or df_wide.empty:
        return np.array([], dtype=float).reshape(0, 0)
    cols = sweep_cols if sweep_cols is not None else _sweep_columns(df_wide)
    if not cols:
        return np.array([], dtype=float).reshape(0, 0)
    missing = [c for c in cols if c not in df_wide.columns]
    if missing:
        return np.array([], dtype=float).reshape(0, 0)
    mat = df_wide[cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return mat


def _align_between_matrices(df1: pd.DataFrame, df2: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list]:
    """Align two group wide frames on common sorted sweep columns."""
    cols1 = _sweep_columns(df1)
    cols2 = _sweep_columns(df2)
    # Common by numeric identity of labels
    def _norm(c):
        try:
            return float(c)
        except (TypeError, ValueError):
            return str(c)

    map1 = {_norm(c): c for c in cols1}
    map2 = {_norm(c): c for c in cols2}
    common_keys = sorted(set(map1) & set(map2), key=lambda x: (0, x) if isinstance(x, (int, float)) else (1, str(x)))
    if len(common_keys) < 2:
        return (
            np.array([], dtype=float).reshape(0, 0),
            np.array([], dtype=float).reshape(0, 0),
            [],
        )
    c1 = [map1[k] for k in common_keys]
    c2 = [map2[k] for k in common_keys]
    # Prefer df1's column labels for metadata
    return _to_matrix(df1, c1), _to_matrix(df2, c2), c1


def _align_paired_rec_matrices(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> dict:
    """Align two within-group wide frames on common rec_ID.

    Time axis: each set uses its own sorted sweeps; columns are paired by
    **relative position** (not absolute sweep index) so baseline vs post windows
    with different absolute numbers still work. Uses min length ≥ 2.

    Returns X1, X2 (aligned), n_pairs, n_dropped, dropped[{unit, reason}], sweeps.
    """
    empty = {
        "X1": np.array([], dtype=float).reshape(0, 0),
        "X2": np.array([], dtype=float).reshape(0, 0),
        "n_pairs": 0,
        "n_dropped": 0,
        "dropped": [],
        "sweeps": [],
    }
    if df1 is None or df2 is None or df1.empty or df2.empty:
        return empty
    if "rec_ID" not in df1.columns or "rec_ID" not in df2.columns:
        return empty

    cols1 = _sweep_columns(df1)
    cols2 = _sweep_columns(df2)
    n_t = min(len(cols1), len(cols2))
    if n_t < 2:
        return empty
    c1 = cols1[:n_t]
    c2 = cols2[:n_t]

    a = df1[["rec_ID"] + c1].copy()
    b = df2[["rec_ID"] + c2].copy()
    a["rec_ID"] = a["rec_ID"].map(lambda v: str(v).strip() if pd.notna(v) else "")
    b["rec_ID"] = b["rec_ID"].map(lambda v: str(v).strip() if pd.notna(v) else "")
    a = a[a["rec_ID"] != ""].drop_duplicates(subset=["rec_ID"], keep="first")
    b = b[b["rec_ID"] != ""].drop_duplicates(subset=["rec_ID"], keep="first")

    # Position-aligned time columns a_0.. / b_0..
    a = a.rename(columns={c: f"a_{i}" for i, c in enumerate(c1)})
    b = b.rename(columns={c: f"b_{i}" for i, c in enumerate(c2)})
    merged = a.merge(b, on="rec_ID", how="outer", indicator=True)

    dropped = []
    complete_idx = []
    a_cols = [f"a_{i}" for i in range(n_t)]
    b_cols = [f"b_{i}" for i in range(n_t)]
    for idx, row in merged.iterrows():
        rid = row["rec_ID"]
        if row["_merge"] == "left_only":
            dropped.append({"unit": rid, "reason": "no finite series in test set 2 (present only in test set 1)"})
            continue
        if row["_merge"] == "right_only":
            dropped.append({"unit": rid, "reason": "no finite series in test set 1 (present only in test set 2)"})
            continue
        va = pd.to_numeric(row[a_cols], errors="coerce").to_numpy(dtype=float)
        vb = pd.to_numeric(row[b_cols], errors="coerce").to_numpy(dtype=float)
        if not (np.isfinite(va).all() and np.isfinite(vb).all()):
            dropped.append({"unit": rid, "reason": "non-finite sweep value in one or both test sets"})
            continue
        complete_idx.append(idx)

    if len(complete_idx) < 2:
        return {
            "X1": np.array([], dtype=float).reshape(0, 0),
            "X2": np.array([], dtype=float).reshape(0, 0),
            "n_pairs": 0,
            "n_dropped": len(dropped),
            "dropped": dropped,
            "sweeps": c1,
        }

    complete = merged.loc[complete_idx]
    X1 = complete[a_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    X2 = complete[b_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return {
        "X1": X1,
        "X2": X2,
        "n_pairs": int(X1.shape[0]),
        "n_dropped": len(dropped),
        "dropped": dropped,
        "sweeps": c1,
        "sweeps2": c2,
    }


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
    try:
        from mne.stats import permutation_cluster_1samp_test, permutation_cluster_test
    except ImportError:
        return {
            "error": "MNE-Python not installed; cluster permutation requires `pip install mne` (or `pip install .[neuroscience]`)",
            "results": [],
        }
    except Exception as e:
        warnings.warn(f"MNE import failed: {e}")
        return {
            "error": "MNE-Python not installed; cluster permutation requires `pip install mne` (or `pip install .[neuroscience]`)",
            "results": [],
        }

    _layout_help = (
        "Valid layouts: (A) exactly 2 groups and ≥1 test set → between (one cluster test per set); "
        "or (B) exactly 1 group and exactly 2 test sets → paired."
    )
    shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
    n_g = len(shown_groups or [])
    n_ts = len(shown_sets)
    if n_g == 0:
        return {"error": f"No groups with data for Cluster perm. {_layout_help}", "results": []}
    if n_g > 2:
        return {
            "error": f"Cluster perm. does not support {n_g} groups (only exactly 2 for between). {_layout_help}",
            "results": [],
        }
    if n_g == 1 and n_ts != 2:
        return {
            "error": (
                f"Paired Cluster perm. needs exactly 2 test sets (have {n_ts}); "
                f"or use exactly 2 groups for between mode. {_layout_help}"
            ),
            "results": [],
        }
    if n_g == 2 and n_ts < 1:
        return {
            "error": f"Between-groups Cluster perm. needs ≥1 shown test set (have {n_ts}). {_layout_help}",
            "results": [],
        }
    if not shown_sets:
        return {"error": f"No shown test sets for Cluster perm. {_layout_help}", "results": []}

    results = []
    # FDR: list of (result_index, aspect_key)
    fdr_amp = []
    fdr_slope = []
    aspects = []
    if amp:
        aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
    if slope:
        aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))
    if not aspects:
        return {"error": "no aspects selected", "results": []}

    mode = "between" if n_g == 2 else "paired"

    if mode == "between":
        g1, g2 = shown_groups[0], shown_groups[1]
        for sid, tset in shown_sets:
            sweeps = list(tset.get("sweeps", []))
            if len(sweeps) < 2:
                continue
            res_row = {
                "set_id": sid,
                "set_name": tset.get("set_name", f"set {sid}"),
                "sweeps": sweeps,
                "group1": g1,
                "group2": g2,
                "n1": 0,
                "n2": 0,
                "cluster_mode": "between",
            }
            for short, col in aspects:
                try:
                    df1 = fetch_group_testset_observations(g1, tset, col, per_sweep=True)
                    df2 = fetch_group_testset_observations(g2, tset, col, per_sweep=True)
                    X1, X2, common_sw = _align_between_matrices(df1, df2)
                    n1 = int(X1.shape[0]) if X1.ndim == 2 else 0
                    n2 = int(X2.shape[0]) if X2.ndim == 2 else 0
                    if n1 < 2 or n2 < 2 or len(common_sw) < 2:
                        res_row[f"p_{short}"] = np.nan
                        res_row[f"stat_{short}"] = np.nan
                        continue
                    # Drop rows that are all-NaN
                    ok1 = np.isfinite(X1).all(axis=1)
                    ok2 = np.isfinite(X2).all(axis=1)
                    X1 = X1[ok1]
                    X2 = X2[ok2]
                    n1, n2 = int(X1.shape[0]), int(X2.shape[0])
                    if n1 < 2 or n2 < 2:
                        res_row[f"p_{short}"] = np.nan
                        res_row[f"stat_{short}"] = np.nan
                        continue
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        res = permutation_cluster_test([X1, X2], n_permutations=1000, threshold=None, tail=0)
                    cluster_p = _extract_cluster_p(res)
                    cluster_stat = float(np.max(res[0])) if hasattr(res[0], "__len__") and len(res[0]) > 0 else np.nan
                    res_row[f"p_{short}"] = cluster_p
                    res_row[f"stat_{short}"] = cluster_stat
                    res_row["n1"] = max(int(res_row.get("n1", 0)), n1)
                    res_row["n2"] = max(int(res_row.get("n2", 0)), n2)
                    res_row["sweeps"] = list(common_sw)
                    if short == "amp":
                        fdr_amp.append((len(results), "amp"))
                    else:
                        fdr_slope.append((len(results), "slope"))
                except Exception as e:
                    print(f"Cluster between error on {short}: {e}")
                    res_row[f"p_{short}"] = np.nan
                    res_row[f"stat_{short}"] = np.nan
            if any(k.startswith("p_") for k in res_row):
                results.append(res_row)

    else:
        # Paired: 1 group, 2 test sets; each window ≥2 sweeps (absolute indices may differ).
        g = shown_groups[0]
        s1, tset1 = shown_sets[0]
        s2, tset2 = shown_sets[1]
        sweeps1 = list(tset1.get("sweeps", []))
        sweeps2 = list(tset2.get("sweeps", []))
        if len(sweeps1) < 2 or len(sweeps2) < 2:
            return {
                "error": (
                    "Paired Cluster perm. needs ≥2 sweeps in each of the two test sets. " + _layout_help
                ),
                "results": [],
            }
        name1 = tset1.get("set_name", f"set {s1}")
        name2 = tset2.get("set_name", f"set {s2}")
        res_row = {
            "set_id": f"{s1}_{s2}",
            "set_name": f"Cluster (paired {name1} vs {name2})",
            "sweeps": sweeps1,
            "sweeps2": sweeps2,
            "group1": g,
            "n1": 0,
            "n2": 0,
            "n_pairs": 0,
            "n_dropped": 0,
            "paired_dropped": [],
            "cluster_mode": "paired",
        }
        all_dropped: list[dict] = []
        seen: set[str] = set()
        for short, col in aspects:
            try:
                df1 = fetch_group_testset_observations(g, tset1, col, per_sweep=True)
                df2 = fetch_group_testset_observations(g, tset2, col, per_sweep=True)
                aligned = _align_paired_rec_matrices(df1, df2)
                n_pairs = int(aligned["n_pairs"])
                n_dropped = int(aligned["n_dropped"])
                for d in aligned.get("dropped") or []:
                    u = d.get("unit")
                    if u is not None and u not in seen:
                        seen.add(u)
                        all_dropped.append(d)
                if n_pairs < 2:
                    res_row[f"p_{short}"] = np.nan
                    res_row[f"stat_{short}"] = np.nan
                    res_row["n_dropped"] = max(int(res_row.get("n_dropped", 0)), n_dropped)
                    continue
                Xdiff = aligned["X2"] - aligned["X1"]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    res = permutation_cluster_1samp_test(Xdiff, n_permutations=1000, threshold=None, tail=0)
                cluster_p = _extract_cluster_p(res)
                cluster_stat = float(np.max(res[0])) if hasattr(res[0], "__len__") and len(res[0]) > 0 else np.nan
                res_row[f"p_{short}"] = cluster_p
                res_row[f"stat_{short}"] = cluster_stat
                res_row["n1"] = max(int(res_row.get("n1", 0)), n_pairs)
                res_row["n2"] = res_row["n1"]
                res_row["n_pairs"] = max(int(res_row.get("n_pairs", 0)), n_pairs)
                res_row["n_dropped"] = max(int(res_row.get("n_dropped", 0)), n_dropped)
                if aligned.get("sweeps"):
                    res_row["sweeps"] = aligned["sweeps"]
                if short == "amp":
                    fdr_amp.append((len(results), "amp"))
                else:
                    fdr_slope.append((len(results), "slope"))
            except Exception as e:
                print(f"Cluster paired error on {short}: {e}")
                res_row[f"p_{short}"] = np.nan
                res_row[f"stat_{short}"] = np.nan
        res_row["paired_dropped"] = all_dropped
        res_row["n_dropped"] = max(int(res_row.get("n_dropped", 0)), len(all_dropped))
        if any(k.startswith("p_") for k in res_row):
            results.append(res_row)

    if fdr:
        for family, aspect in ((fdr_amp, "amp"), (fdr_slope, "slope")):
            if not family:
                continue
            try:
                from statsmodels.stats.multitest import multipletests

                ps = []
                for res_idx, _asp in family:
                    if res_idx < len(results):
                        val = results[res_idx].get(f"p_{aspect}", np.nan)
                        ps.append(val if np.isfinite(val) else 1.0)
                    else:
                        ps.append(1.0)
                qs = multipletests(ps, alpha=0.05, method="fdr_bh")[1]
                for (res_idx, _asp), q in zip(family, qs):
                    if res_idx < len(results):
                        results[res_idx][f"q_{aspect}"] = float(q)
            except Exception:
                pass

    config = {
        "type": test_type,
        "test_type": test_type,
        "variant": mode,
        "fdr": fdr,
        "norm": norm,
        "n_unit": "recording",
        "note": "Cluster permutation uses recording-level n (subject/slice deferred)",
    }
    if use_implicit:
        config["implicit_testset"] = True
    return {"results": results, "config": config}
