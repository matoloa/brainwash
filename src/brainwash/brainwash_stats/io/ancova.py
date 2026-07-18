"""Textbook-style IO ANCOVA: slope homogeneity then covariate-adjusted group test."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress, shapiro

from ..data import _aspect_measurement_columns
from .xy_pairs import _get_io_xy_pairs

ALPHA_SLOPES_DEFAULT = 0.05


def _finite_xy(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def _per_group_linregress(x, y, *, force0: bool) -> tuple[float, float]:
    x, y = _finite_xy(x, y)
    if len(x) < 2:
        return np.nan, np.nan
    if force0:
        ssx = float(np.sum(x * x))
        if ssx <= 0:
            return np.nan, np.nan
        slope = float(np.sum(x * y) / ssx)
        yhat = slope * x
        sst = float(np.sum(y * y))
        ssr = float(np.sum((y - yhat) ** 2))
        r2 = 1.0 - ssr / sst if sst > 0 else np.nan
        return slope, r2
    res = linregress(x, y)
    slope = float(res.slope) if np.isfinite(res.slope) else np.nan
    r2 = float(res.rvalue**2) if np.isfinite(res.rvalue) else np.nan
    return slope, r2


def _anova_type2(model) -> pd.DataFrame | None:
    try:
        from statsmodels.stats.anova import anova_lm

        return anova_lm(model, typ=2)
    except Exception:
        return None


def _term_fp(anova_table: pd.DataFrame | None, *name_substrings: str) -> tuple[float, float, object]:
    """Return (F, p, df) for first ANOVA row whose index matches any substring."""
    if anova_table is None or anova_table.empty:
        return np.nan, np.nan, None
    for idx in anova_table.index:
        s = str(idx)
        if any(sub in s for sub in name_substrings):
            row = anova_table.loc[idx]
            f = float(row.get("F", np.nan)) if "F" in anova_table.columns else np.nan
            p = float(row.get("PR(>F)", np.nan)) if "PR(>F)" in anova_table.columns else np.nan
            df = row.get("df", None)
            return f, p, df
    return np.nan, np.nan, None


def _assumption_checks(model, groups: pd.Series, *, do_sw: bool, do_levene: bool) -> dict:
    notes: list[str] = []
    out: dict = {"sw_p": None, "levene_p": None, "notes": notes}
    try:
        resid = np.asarray(model.resid, dtype=float)
        resid = resid[np.isfinite(resid)]
    except Exception:
        notes.append("residuals unavailable")
        return out

    if do_sw and 3 <= len(resid) <= 5000:
        try:
            _w, p = shapiro(resid)
            out["sw_p"] = float(p)
            if p < 0.05:
                notes.append(f"SW residual p={p:.3g}")
        except Exception:
            notes.append("SW failed")

    if do_levene and groups is not None and len(groups) == len(model.resid):
        try:
            from scipy.stats import levene

            gser = pd.Series(groups).astype(str)
            res_s = pd.Series(np.asarray(model.resid, dtype=float))
            samples = [res_s[gser == g].dropna().values for g in gser.unique()]
            samples = [s for s in samples if len(s) >= 2]
            if len(samples) >= 2:
                _stat, p = levene(*samples, center="median")
                out["levene_p"] = float(p)
                if p < 0.05:
                    notes.append(f"Levene residual p={p:.3g}")
        except Exception:
            notes.append("Levene failed")
    return out


def _chow_slope_interaction(pooled: pd.DataFrame, *, force0: bool) -> tuple[float, float, int, int]:
    """F-test: separate slopes vs common slope (+ group intercepts). Scipy fallback."""
    from scipy.stats import f as f_dist

    groups = list(pooled["group"].unique())
    if len(groups) < 2:
        return np.nan, np.nan, 0, 0

    # Unrestricted: per-group slope (and intercept unless force0)
    sep_rss = 0.0
    n_tot = 0
    k = 0
    pieces = []
    for g in groups:
        sub = pooled[pooled["group"] == g]
        x, y = _finite_xy(sub["x"], sub["y"])
        if len(x) < 2:
            continue
        if force0:
            ssx = float(np.sum(x * x))
            if ssx <= 0:
                continue
            slope = float(np.sum(x * y) / ssx)
            pred = slope * x
        else:
            res = linregress(x, y)
            pred = res.slope * x + res.intercept
        sep_rss += float(np.sum((y - pred) ** 2))
        n_tot += len(x)
        k += 1
        pieces.append((g, x, y))
    if k < 2 or n_tot < 4:
        return np.nan, np.nan, 0, 0

    # Restricted: common slope + group-specific intercepts (or common slope through 0)
    if force0:
        # y = b * x  within each group share b: stack design
        num = den = 0.0
        for _g, x, y in pieces:
            num += float(np.sum(x * y))
            den += float(np.sum(x * x))
        b = num / den if den > 0 else 0.0
        rest_rss = 0.0
        for _g, x, y in pieces:
            rest_rss += float(np.sum((y - b * x) ** 2))
        # unrestricted k slopes; restricted 1 slope
        df1 = k - 1
        df2 = n_tot - k
    else:
        # y = a_g + b * x : solve for common b and intercepts a_g
        # For each group: a_g = ybar_g - b * xbar_g; minimize sum (y - a_g - b x)^2
        # → b = sum_g sum (x - xbar_g)(y - ybar_g) / sum_g sum (x - xbar_g)^2
        num = den = 0.0
        stats = []
        for g, x, y in pieces:
            xb, yb = float(np.mean(x)), float(np.mean(y))
            xc, yc = x - xb, y - yb
            num += float(np.sum(xc * yc))
            den += float(np.sum(xc * xc))
            stats.append((g, x, y, xb, yb))
        b = num / den if den > 0 else 0.0
        rest_rss = 0.0
        for g, x, y, xb, yb in stats:
            a = yb - b * xb
            rest_rss += float(np.sum((y - (a + b * x)) ** 2))
        # unrestricted 2k params; restricted k intercepts + 1 slope
        df1 = k - 1
        df2 = n_tot - (k + 1)

    if df2 <= 0 or df1 <= 0:
        return np.nan, np.nan, df1, df2
    if sep_rss <= 1e-15:
        if rest_rss <= 1e-12:
            return 0.0, 1.0, df1, df2
        return 1e12, 0.0, df1, df2
    if rest_rss + 1e-15 < sep_rss:
        return np.nan, np.nan, df1, df2
    f_stat = ((rest_rss - sep_rss) / df1) / (sep_rss / df2)
    p = float(1.0 - f_dist.cdf(max(f_stat, 0.0), df1, df2))
    return float(f_stat), p, df1, df2


def _fit_io_ancova_pooled(
    pooled: pd.DataFrame,
    *,
    force0: bool,
    alpha_slopes: float,
    do_sw: bool,
    do_levene: bool,
) -> dict:
    """Fit interaction + additive models; return stats dict for one aspect."""
    empty = {
        "p_interaction": np.nan,
        "F_interaction": np.nan,
        "df_interaction": None,
        "p_group_ancova": np.nan,
        "F_group_ancova": np.nan,
        "df_group": None,
        "p_covariate": np.nan,
        "F_covariate": np.nan,
        "slopes_homogeneous": False,
        "primary_contrast": "slope_interaction",
        "adjusted_means": {},
        "assumptions": {"notes": ["model fit failed"]},
        "x_bar": np.nan,
    }
    if pooled.empty or pooled["group"].nunique() < 2:
        return empty

    m_int = m_add = None
    f_int = p_int = f_grp = p_grp = f_x = p_x = np.nan
    df_int = df_grp = None
    try:
        from statsmodels.formula.api import ols

        if force0:
            m_int = ols("y ~ x:C(group) - 1", data=pooled).fit()
            m_add = ols("y ~ x + C(group) - 1", data=pooled).fit()
        else:
            m_int = ols("y ~ x * C(group)", data=pooled).fit()
            m_add = ols("y ~ x + C(group)", data=pooled).fit()
        a_int = _anova_type2(m_int)
        a_add = _anova_type2(m_add)
        f_int, p_int, df_int = _term_fp(a_int, "x:C(group)")
        if not np.isfinite(p_int):
            f_int, p_int, df_int = _term_fp(a_int, ":")
        f_grp, p_grp, df_grp = _term_fp(a_add, "C(group)")
        f_x, p_x, _df_x = _term_fp(a_add, "x")
    except Exception:
        f_int, p_int, df1, df2 = _chow_slope_interaction(pooled, force0=force0)
        df_int = (df1, df2)
        # Crude group test at mean X: one-way ANOVA of residuals from common slope — skip if no sm
        p_grp = f_grp = np.nan

    slopes_ok = bool(np.isfinite(p_int) and p_int >= alpha_slopes)
    primary = "group_adjusted" if slopes_ok and np.isfinite(p_grp) else (
        "group_adjusted" if slopes_ok else "slope_interaction"
    )
    # Without group p from statsmodels, still mark slopes OK but primary stays interaction if no group p
    if slopes_ok and not np.isfinite(p_grp):
        # scipy path: use simple intercept contrast via predicted at mean x from per-group fits
        try:
            from scipy.stats import f_oneway

            x_bar = float(np.nanmean(pooled["x"].to_numpy(dtype=float)))
            samples = []
            for g in pooled["group"].unique():
                sub = pooled[pooled["group"] == g]
                x, y = _finite_xy(sub["x"], sub["y"])
                if len(x) < 2:
                    continue
                if force0:
                    ssx = float(np.sum(x * x))
                    slope = float(np.sum(x * y) / ssx) if ssx > 0 else 0.0
                    # residual around forced line; adjusted mean ≈ slope * x_bar
                    samples.append(np.array([slope * x_bar]))
                else:
                    res = linregress(x, y)
                    # pseudo-observations: intercept estimates — use residual SD scaled; better: y - slope*(x-xbar)
                    y_adj = y - res.slope * (x - x_bar)
                    samples.append(y_adj)
            if len(samples) >= 2 and all(len(s) >= 1 for s in samples):
                if all(len(s) >= 2 for s in samples):
                    _st, p_grp = f_oneway(*samples)
                    f_grp = float(_st)
                    p_grp = float(p_grp)
                primary = "group_adjusted" if slopes_ok else "slope_interaction"
        except Exception:
            pass

    if not slopes_ok:
        primary = "slope_interaction"

    adjusted_means: dict = {}
    x_bar = float(np.nanmean(pooled["x"].to_numpy(dtype=float)))
    if slopes_ok and np.isfinite(x_bar):
        if m_add is not None:
            try:
                for g in sorted(pooled["group"].unique()):
                    pred = m_add.predict(pd.DataFrame({"x": [x_bar], "group": [g]}))
                    adjusted_means[str(g)] = float(pred.iloc[0])
            except Exception:
                adjusted_means = {}
        else:
            for g in sorted(pooled["group"].unique()):
                sub = pooled[pooled["group"] == g]
                x, y = _finite_xy(sub["x"], sub["y"])
                if len(x) < 2:
                    continue
                if force0:
                    ssx = float(np.sum(x * x))
                    slope = float(np.sum(x * y) / ssx) if ssx > 0 else np.nan
                    adjusted_means[str(g)] = float(slope * x_bar) if np.isfinite(slope) else np.nan
                else:
                    res = linregress(x, y)
                    adjusted_means[str(g)] = float(res.slope * x_bar + res.intercept)

    assumptions = {"notes": [], "sw_p": None, "levene_p": None}
    if m_add is not None or m_int is not None:
        primary_model = m_add if (slopes_ok and m_add is not None) else m_int
        if primary_model is not None:
            assumptions = _assumption_checks(
                primary_model,
                pooled["group"],
                do_sw=do_sw,
                do_levene=do_levene,
            )
    elif do_sw or do_levene:
        assumptions["notes"].append("statsmodels unavailable; assumption tests skipped")

    return {
        "p_interaction": float(p_int) if np.isfinite(p_int) else np.nan,
        "F_interaction": float(f_int) if np.isfinite(f_int) else np.nan,
        "df_interaction": df_int,
        "p_group_ancova": float(p_grp) if np.isfinite(p_grp) else np.nan,
        "F_group_ancova": float(f_grp) if np.isfinite(f_grp) else np.nan,
        "df_group": df_grp,
        "p_covariate": float(p_x) if np.isfinite(p_x) else np.nan,
        "F_covariate": float(f_x) if np.isfinite(f_x) else np.nan,
        "slopes_homogeneous": slopes_ok,
        "primary_contrast": primary,
        "adjusted_means": adjusted_means,
        "assumptions": assumptions,
        "x_bar": x_bar,
    }


def compute_io_ancova(
    shown_groups,
    get_group_testset_means_fn,
    uistate=None,
    n_unit="subject",
    norm=False,
    amp=True,
    slope=True,
    dd_groups=None,
    *,
    force_through_zero: bool = False,
    alpha_slopes: float = ALPHA_SLOPES_DEFAULT,
    test_sw: bool = False,
    test_levene: bool = False,
) -> dict:
    """Publication-oriented IO ANCOVA for ≥2 groups.

    1) Homogeneity of slopes via Type-II ANOVA on y ~ x * C(group)
    2) If parallel: classical ANCOVA y ~ x + C(group) (group effect adjusted for X)
    3) Else: primary result is slope interaction; report per-group slopes
    """
    results = []
    group_ns: dict = {}
    aspects = _aspect_measurement_columns(amp, slope, norm)

    # n per group once
    for g in shown_groups:
        try:
            xy_df = _get_io_xy_pairs(
                g, get_group_testset_means_fn, uistate, n_unit=n_unit, aspect_col="EPSP_amp"
            )
            if not xy_df.empty and "n_unique" in xy_df.columns:
                n_unique = int(xy_df["n_unique"].iloc[0]) if not xy_df["n_unique"].empty else 0
            elif not xy_df.empty:
                if n_unit == "subject" and "subject" in xy_df.columns:
                    n_unique = int(xy_df["subject"].nunique(dropna=True))
                else:
                    n_unique = int(xy_df["rec_ID"].nunique()) if "rec_ID" in xy_df.columns else len(xy_df)
            else:
                n_unique = 0
            group_ns[g] = n_unique
        except Exception:
            group_ns[g] = 0

    last_fit: dict = {}
    for _short, col in aspects:
        frames = []
        r2_per_group: dict = {}
        slope_per_group: dict = {}
        for g in shown_groups:
            try:
                xy_df = _get_io_xy_pairs(
                    g, get_group_testset_means_fn, uistate, n_unit=n_unit, aspect_col=col
                )
                if xy_df.empty or group_ns.get(g, 0) == 0:
                    r2_per_group[g] = np.nan
                    slope_per_group[g] = np.nan
                    continue
                x = xy_df["x"].to_numpy(dtype=float)
                y = xy_df["y"].to_numpy(dtype=float)
                x, y = _finite_xy(x, y)
                if len(x) < 2:
                    r2_per_group[g] = np.nan
                    slope_per_group[g] = np.nan
                    continue
                sl, r2 = _per_group_linregress(x, y, force0=force_through_zero)
                slope_per_group[g] = sl
                r2_per_group[g] = r2
                gdf = pd.DataFrame({"y": y, "x": x, "group": str(g)})
                frames.append(gdf)
            except Exception:
                r2_per_group[g] = np.nan
                slope_per_group[g] = np.nan

        if len(frames) < 2:
            fit = {
                "p_interaction": np.nan,
                "F_interaction": np.nan,
                "p_group_ancova": np.nan,
                "F_group_ancova": np.nan,
                "p_covariate": np.nan,
                "slopes_homogeneous": False,
                "primary_contrast": "slope_interaction",
                "adjusted_means": {},
                "assumptions": {"notes": ["need ≥2 groups with ≥2 finite points each"]},
            }
        else:
            pooled = pd.concat(frames, ignore_index=True)
            fit = _fit_io_ancova_pooled(
                pooled,
                force0=force_through_zero,
                alpha_slopes=alpha_slopes,
                do_sw=test_sw,
                do_levene=test_levene,
            )
        last_fit = fit

        p_int = fit.get("p_interaction", np.nan)
        p_grp = fit.get("p_group_ancova", np.nan)
        res_row = {
            "set_id": "__io_ancova__",
            "set_name": None,
            "group1": list(shown_groups),
            "n1": sum(group_ns.values()) if group_ns else 0,
            "slope_p": p_int,
            "p_slope": p_int if np.isfinite(p_int) else None,
            "p_group": p_grp if np.isfinite(p_grp) else None,
            "group_ns": group_ns.copy(),
            "r2_per_group": r2_per_group.copy(),
            "slope_per_group": slope_per_group.copy(),
            "primary_contrast": fit.get("primary_contrast"),
            "slopes_homogeneous": fit.get("slopes_homogeneous"),
            "F_interaction": fit.get("F_interaction"),
            "df_interaction": fit.get("df_interaction"),
            "F_group_ancova": fit.get("F_group_ancova"),
            "df_group": fit.get("df_group"),
            "p_covariate": fit.get("p_covariate"),
            "F_covariate": fit.get("F_covariate"),
            "adjusted_means": fit.get("adjusted_means") or {},
            "assumptions": fit.get("assumptions") or {},
            "aspect": col,
        }
        for g, r2v in r2_per_group.items():
            res_row[f"r2_{g}"] = r2v
        results.append(res_row)

    x_col = "volley_amp"
    y_col = "EPSP_amp"
    io_input = "vamp"
    io_output = "EPSPamp"
    exp = getattr(uistate, "experiment", None) if uistate is not None else None
    if exp is None and uistate is not None:
        nested = getattr(uistate, "uistate", None)
        exp = getattr(nested, "experiment", None) if nested is not None else None
    if exp is not None:
        io_input = getattr(exp, "io_input", io_input)
        io_output = getattr(exp, "io_output", io_output)
        x_map = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}
        y_map = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}
        x_col = x_map.get(io_input, "volley_amp")
        y_col = y_map.get(io_output, "EPSP_amp")

    # Prefer aspect matching io_output for top-level config (p-values, slopes, r²)
    prefer_col = y_col if not norm else f"{y_col}_norm"
    primary_row = next((r for r in results if r.get("aspect") == prefer_col), results[0] if results else {})

    config = {
        "type": "IO ANCOVA",
        "io_input": io_input,
        "io_output": io_output,
        "x_col": x_col,
        "y_col": y_col,
        "n_unit": n_unit,
        "implicit_testset": True,
        "test_sets_ignored": True,
        "force_through_zero": bool(force_through_zero),
        "alpha_slopes": float(alpha_slopes),
        "amp": amp,
        "slope": slope,
        "norm": norm,
        "group_ns": group_ns,
        "r2_per_group": primary_row.get("r2_per_group") or {},
        "slope_per_group": primary_row.get("slope_per_group") or {},
        "p_interaction": primary_row.get("slope_p", last_fit.get("p_interaction")),
        "F_interaction": primary_row.get("F_interaction", last_fit.get("F_interaction")),
        "df_interaction": primary_row.get("df_interaction", last_fit.get("df_interaction")),
        "p_group_ancova": primary_row.get("p_group", last_fit.get("p_group_ancova")),
        "F_group_ancova": primary_row.get("F_group_ancova", last_fit.get("F_group_ancova")),
        "df_group": primary_row.get("df_group", last_fit.get("df_group")),
        "p_covariate": primary_row.get("p_covariate", last_fit.get("p_covariate")),
        "F_covariate": primary_row.get("F_covariate", last_fit.get("F_covariate")),
        "slopes_homogeneous": primary_row.get("slopes_homogeneous", last_fit.get("slopes_homogeneous")),
        "primary_contrast": primary_row.get("primary_contrast", last_fit.get("primary_contrast")),
        "adjusted_means": primary_row.get("adjusted_means") or last_fit.get("adjusted_means") or {},
        "assumptions": primary_row.get("assumptions") or last_fit.get("assumptions") or {},
        "slope_p": primary_row.get("slope_p", last_fit.get("p_interaction")),
    }

    # Attach config on first result for statusbar extractors
    if results:
        results[0] = {**results[0], "config": config}

    return {"results": results, "config": config}
