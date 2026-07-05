import numpy as np
import pandas as pd
from scipy.stats import linregress

from ..data import _aspect_measurement_columns
from .xy_pairs import _get_io_xy_pairs


def _compute_io_regression_internal(
    shown_groups, get_group_testset_means_fn, uistate=None, n_unit="subject", norm=False, amp=True, slope=True, dd_groups=None
):
    """Core IO regression: linregress per group, OLS slope comparison between groups.
    Returns dict with config["type"] == "IO regression" for statusbar.
    """
    results = []
    group_ns = {}
    r2_per_group = {}
    slope_per_group = {}
    aspects = _aspect_measurement_columns(amp, slope, norm)

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
                if n_unit == "subject" and "subject" in xy_df.columns:
                    n_unique = xy_df["subject"].nunique()
                elif n_unit == "slice" and {"subject", "slice"}.issubset(xy_df.columns):
                    n_unique = xy_df[["subject", "slice"]].drop_duplicates().shape[0]
                else:
                    n_unique = len(xy_df["rec_ID"].unique()) if "rec_ID" in xy_df.columns else int(valid.sum())
                group_data[g] = {"x": x[valid], "y": y[valid], "n": int(n_unique)}
                group_ns[g] = group_data[g]["n"]
                res = linregress(group_data[g]["x"], group_data[g]["y"])
                r2_per_group[g] = float(res.rvalue**2) if hasattr(res, "rvalue") and np.isfinite(res.rvalue) else np.nan
                slope_per_group[g] = float(res.slope) if hasattr(res, "slope") and np.isfinite(res.slope) else np.nan
            except Exception:
                group_data[g] = {"x": np.array([]), "y": np.array([]), "n": 0}
                group_ns[g] = 0
                r2_per_group[g] = np.nan
                slope_per_group[g] = np.nan

        slope_p = np.nan
        if len(shown_groups) >= 2 and all(len(d["x"]) >= 2 for d in group_data.values()):
            try:
                from statsmodels.formula.api import ols

                dfs = []
                for g_idx, g in enumerate(shown_groups):
                    d = group_data.get(g, {})
                    if len(d.get("x", [])) > 0:
                        gdf = pd.DataFrame({"y": d["y"], "x": d["x"], "group": f"G{g_idx}"})
                        dfs.append(gdf)
                if dfs:
                    pooled = pd.concat(dfs, ignore_index=True)
                    model = ols("y ~ x * C(group)", data=pooled).fit()
                    pvals = model.pvalues
                    inter_p = pvals.filter(like="x:C(group)").iloc[0] if any("x:C" in str(k) for k in pvals.index) else np.nan
                    slope_p = float(inter_p) if np.isfinite(inter_p) else np.nan
            except Exception:
                try:
                    all_x = np.concatenate([d["x"] for d in group_data.values() if len(d["x"]) > 0])
                    all_y = np.concatenate([d["y"] for d in group_data.values() if len(d["y"]) > 0])
                    pooled_res = linregress(all_x, all_y)
                    pooled_rss = np.sum((all_y - (pooled_res.slope * all_x + pooled_res.intercept)) ** 2)
                    sep_rss = 0
                    for d in group_data.values():
                        if len(d["x"]) > 1:
                            res = linregress(d["x"], d["y"])
                            pred = res.slope * d["x"] + res.intercept
                            sep_rss += np.sum((d["y"] - pred) ** 2)
                    df1 = len(shown_groups) - 1
                    df2 = len(all_y) - 2 * len(shown_groups)
                    if df2 > 0 and pooled_rss > 0:
                        from scipy.stats import f

                        f_stat = ((pooled_rss - sep_rss) / df1) / (sep_rss / df2)
                        slope_p = 1.0 - f.cdf(f_stat, df1, df2)
                except Exception:
                    slope_p = np.nan

        res_row = {
            "set_id": "__io_regression_implicit__",
            "set_name": None,
            "group1": shown_groups,
            "n1": sum(group_ns.values()) if group_ns else 0,
            "slope_p": slope_p,
            "group_ns": group_ns.copy(),
            "r2_per_group": r2_per_group.copy(),
        }
        for g, r2v in r2_per_group.items():
            res_row[f"r2_{g}"] = r2v
        if np.isfinite(slope_p):
            res_row["p_slope"] = slope_p
        results.append(res_row)

    x_col = "volley_amp"
    y_col = "EPSP_amp"
    if uistate is not None:
        io_input = getattr(uistate, "io_input", "vamp")
        x_map = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}
        x_col = x_map.get(io_input, "volley_amp")
        io_output = getattr(uistate, "io_output", "EPSPamp")
        y_map = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}
        y_col = y_map.get(io_output, "EPSP_amp")

    config = {
        "type": "IO regression",
        "io_input": getattr(uistate, "io_input", "vamp") if uistate else "vamp",
        "io_output": getattr(uistate, "io_output", "EPSPamp") if uistate else "EPSPamp",
        "x_col": x_col,
        "y_col": y_col,
        "n_unit": n_unit,
        "implicit_testset": True,
        "amp": amp,
        "slope": slope,
        "norm": norm,
        "r2_per_group": r2_per_group,
    }
    if slope_per_group:
        config["slope_per_group"] = slope_per_group

    return {"results": results, "config": config}
