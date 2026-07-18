"""Pure statusbar text formatters. No Qt, no uistate mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

StatusbarState = Literal["info", "warning"] | None


@dataclass(frozen=True)
class StatusbarResult:
    text: str | None
    state: StatusbarState = None


def _group_display_name(dd_groups: dict, group_id) -> str:
    if group_id is None or isinstance(group_id, (list, tuple)):
        return ""
    return dd_groups.get(group_id, {}).get("group_name", f"Group {group_id}")


def _unit_label(n_unit: str) -> str:
    return "subjects" if n_unit == "subject" else f"{n_unit}s"


def format_io_regression_statusbar(
    formal,
    *,
    dd_groups: dict | None,
    n_unit: str = "subject",
) -> StatusbarResult:
    dd_groups = dd_groups or {}
    _hint = StatusbarResult("IO ANCOVA: select ≥2 groups to compute slope comparison", "info")
    if not formal:
        return _hint

    cfg = None
    if isinstance(formal, list) and formal:
        item = formal[0]
        if isinstance(item, dict):
            cfg = item.get("config") or item
    elif isinstance(formal, dict):
        cfg = formal.get("config") or formal

    # Canonical "IO ANCOVA"; accept legacy "IO regression" from pre-PR-B results.
    cfg_type = cfg.get("type") if isinstance(cfg, dict) else None
    if not isinstance(cfg, dict) or cfg_type not in ("IO ANCOVA", "IO regression"):
        return _hint

    # Compute/validation failure stored as stub config
    err = cfg.get("error")
    if err:
        return StatusbarResult(f"IO ANCOVA: {err}", "warning")

    prefix = "IO ANCOVA"
    global_notes = []
    n_report = ""
    group_ns = cfg.get("group_ns") or (formal[0] if isinstance(formal, list) else formal).get("group_ns", {})
    unit_label = _unit_label(n_unit)
    if group_ns:
        ns = []
        for g, n in group_ns.items():
            g_name = _group_display_name(dd_groups, g)
            ns.append(f"{g_name}={n}")
        n_report = f"({', '.join(ns)} {unit_label})"

    x_col = cfg.get("x_col", "volley_amp")
    y_col = cfg.get("y_col", "EPSP_amp")
    label_map = {
        "EPSP_amp": "EPSP amp",
        "EPSP_slope": "EPSP slope",
        "volley_amp": "volley amp",
        "volley_slope": "volley slope",
        "stim": "stim",
    }
    y_label = label_map.get(y_col, y_col.replace("_", " "))
    x_label = label_map.get(x_col, x_col.replace("_", " "))
    xy_label = f"{y_label} / {x_label}"

    def _pstr(p) -> str | None:
        if isinstance(p, (int, float)) and np.isfinite(p):
            return f"{p:.3g}" if p >= 0.001 else "<0.001"
        return None

    primary = cfg.get("primary_contrast")
    p_int = cfg.get("p_interaction", cfg.get("slope_p"))
    p_grp = cfg.get("p_group_ancova")
    if primary == "group_adjusted":
        ps = _pstr(p_grp)
        if ps:
            global_notes.append(f"group p={ps} (X-adj)")
        pi = _pstr(p_int)
        if pi:
            global_notes.append(f"slopes OK (p_int={pi})")
    else:
        # Heterogeneous slopes or legacy results: lead with interaction / slope comparison
        p_slope = p_int if p_int is not None else cfg.get("slope_p") or (formal[0] if isinstance(formal, list) else formal).get("slope_p")
        ps = _pstr(p_slope)
        if ps:
            if primary == "slope_interaction":
                global_notes.append(f"slopes differ (interaction p={ps})")
            else:
                stat_label = "slope" if str(cfg.get("io_output", "")).endswith(("slope", "Slope")) else "ratio"
                global_notes.append(f"{stat_label} p={ps}")

    # Per-group simple-regression slope + matching r² (same OLS fit); always when finite.
    slopes = cfg.get("slope_per_group") or {}
    r2s = cfg.get("r2_per_group") or {}
    group_order = list(slopes.keys()) or list(r2s.keys()) or list(group_ns.keys())
    for g in group_order[:2]:
        sl = slopes.get(g)
        r2v = r2s.get(g)
        if not (isinstance(sl, (int, float)) and np.isfinite(sl)):
            continue
        g_name = _group_display_name(dd_groups, g)
        bit = f"slope({g_name})={sl:.3g}"
        if isinstance(r2v, (int, float)) and np.isfinite(r2v):
            bit += f" r²={r2v:.2f}"
        global_notes.append(bit)

    assum = cfg.get("assumptions") or {}
    for note in (assum.get("notes") or [])[:2]:
        global_notes.append(f" - Warning: {note}")
    if global_notes:
        notes_str = " ".join(global_notes)
        prefix = f"{prefix} {n_report} {xy_label}: {notes_str}"
    else:
        prefix = f"{prefix} {n_report} {xy_label}"
    return StatusbarResult(prefix, "info")


def format_io_ancova_methods_text(
    formal,
    *,
    dd_groups: dict | None = None,
    n_unit: str = "subject",
) -> str:
    """Journal-ready methods / caption paragraph for IO ANCOVA (export .md companion)."""
    dd_groups = dd_groups or {}
    cfg = None
    if isinstance(formal, list) and formal:
        item = formal[0]
        if isinstance(item, dict):
            cfg = item.get("config") or item
    elif isinstance(formal, dict):
        cfg = formal.get("config") or formal
    if not isinstance(cfg, dict) or cfg.get("type") not in ("IO ANCOVA", "IO regression"):
        return "(IO ANCOVA results unavailable.)"

    label_map = {
        "EPSP_amp": "EPSP amplitude",
        "EPSP_slope": "EPSP slope",
        "volley_amp": "volley amplitude",
        "volley_slope": "volley slope",
        "stim": "stimulus intensity",
    }
    y_lab = label_map.get(cfg.get("y_col", ""), cfg.get("y_col", "Y").replace("_", " "))
    x_lab = label_map.get(cfg.get("x_col", ""), cfg.get("x_col", "X").replace("_", " "))
    unit = _unit_label(n_unit)
    group_ns = cfg.get("group_ns") or {}
    n_bits = []
    for g, n in group_ns.items():
        n_bits.append(f"{_group_display_name(dd_groups, g)} n={n}")
    n_str = "; ".join(n_bits) if n_bits else f"unit={unit}"

    def _p(p) -> str:
        if not isinstance(p, (int, float)) or not np.isfinite(p):
            return "n.a."
        return f"{p:.3g}" if p >= 0.001 else "<0.001"

    force0 = bool(cfg.get("force_through_zero"))
    force_note = " Regressions were constrained through the origin." if force0 else ""
    alpha = cfg.get("alpha_slopes", 0.05)
    p_int = cfg.get("p_interaction", cfg.get("slope_p"))
    p_grp = cfg.get("p_group_ancova")
    p_cov = cfg.get("p_covariate")
    primary = cfg.get("primary_contrast")
    slopes_ok = cfg.get("slopes_homogeneous")

    sentences = [
        f"Input–output relationships ({y_lab} vs {x_lab}) were compared across groups with ANCOVA "
        f"using statistical units at the {n_unit} level ({n_str}).{force_note}",
        f"Homogeneity of regression slopes was tested via the X×group interaction (α={alpha:g}; "
        f"interaction p={_p(p_int)}).",
    ]
    if primary == "group_adjusted" or slopes_ok:
        sentences.append(
            f"Slopes did not differ significantly; the primary test was the group effect adjusted for {x_lab} "
            f"(ANCOVA group p={_p(p_grp)}; covariate p={_p(p_cov)})."
        )
    else:
        sentences.append(
            "Regression slopes differed across groups; the interaction is reported as the primary contrast "
            "and group main effects from a common-slope ANCOVA are not interpreted."
        )
        slopes = cfg.get("slope_per_group") or {}
        if slopes:
            bits = []
            for g, sl in slopes.items():
                if isinstance(sl, (int, float)) and np.isfinite(sl):
                    bits.append(f"{_group_display_name(dd_groups, g)}={sl:.3g}")
            if bits:
                sentences.append("Per-group slopes: " + ", ".join(bits) + ".")
    assum = cfg.get("assumptions") or {}
    ass_prose = format_io_ancova_assumption_prose(assum)
    if ass_prose:
        sentences.append(ass_prose)
    return " ".join(sentences)


def format_io_ancova_assumption_prose(assumptions: dict | None) -> str:
    """Verbose methods-style text for SW/Levene residual checks (figure .md / methods)."""
    if not assumptions:
        return ""
    bits: list[str] = []
    sw_p = assumptions.get("sw_p")
    lev_p = assumptions.get("levene_p")
    notes = list(assumptions.get("notes") or [])

    def _p(p) -> str:
        if not isinstance(p, (int, float)) or not np.isfinite(p):
            return "n.a."
        return f"{p:.3g}" if p >= 0.001 else "<0.001"

    # Always explain residuals briefly when any assumption info is present
    if sw_p is not None or lev_p is not None or notes:
        bits.append(
            "Residuals are the vertical distances from each data point to the fitted IO regression "
            "line (observed Y minus predicted Y under the primary model)."
        )
    if isinstance(sw_p, (int, float)) and np.isfinite(sw_p):
        if sw_p < 0.05:
            bits.append(
                f"Shapiro–Wilk test on residuals suggested a non-normal residual distribution "
                f"(*p* = {_p(sw_p)}); linear-model *p*-values should be interpreted with caution "
                f"(consider robust methods, transforms, or nonparametric alternatives)."
            )
        else:
            bits.append(
                f"Shapiro–Wilk test on residuals did not indicate clear non-normality (*p* = {_p(sw_p)})."
            )
    if isinstance(lev_p, (int, float)) and np.isfinite(lev_p):
        if lev_p < 0.05:
            bits.append(
                f"Levene’s test suggested heterogeneous residual variance across groups "
                f"(*p* = {_p(lev_p)}); ANCOVA *p*-values may be sensitive to this."
            )
        else:
            bits.append(
                f"Levene’s test did not indicate clear residual variance heterogeneity across groups "
                f"(*p* = {_p(lev_p)})."
            )
    # Failure / skip notes not already covered by p-values
    for n in notes:
        s = str(n)
        if s.startswith("SW residual") or s.startswith("Levene residual"):
            continue  # already expanded via sw_p / levene_p
        if "unavailable" in s or "failed" in s or "skipped" in s:
            bits.append(f"Assumption-check note: {s}.")
        elif s not in " ".join(bits):
            bits.append(s if s.endswith(".") else s + ".")
    return " ".join(bits)


def format_non_io_stat_test_statusbar(
    formal,
    *,
    effective_test_type: str,
    dd_groups: dict | None,
    n_unit: str = "subject",
    ttest_variant: str = "unpaired",
    wilcox_variant: str = "paired",
    test_fdr: bool = False,
    test_sw: bool = False,
    test_levene: bool = False,
) -> StatusbarResult:
    dd_groups = dd_groups or {}
    if not formal:
        return StatusbarResult(None, None)
    results = formal if isinstance(formal, list) else [formal]
    if not any(isinstance(r, dict) for r in results):
        return StatusbarResult(None, None)

    eff = effective_test_type
    if eff == "Wilcoxon":
        variant = wilcox_variant
    elif eff == "t-test":
        variant = ttest_variant
    else:
        variant = None

    test_label = f"{eff} ({variant})" if variant else eff

    n_report = ""
    primary = results[0] if results else {}
    try:
        if isinstance(primary, dict):
            unit_label = _unit_label(n_unit)
            group_ns = primary.get("group_ns") or (primary.get("config") or {}).get("group_ns", {})
            if group_ns:
                ns = []
                for g, n in group_ns.items():
                    g_name = _group_display_name(dd_groups, g)
                    ns.append(f"{g_name}={n}")
                if ns:
                    n_report = f"({', '.join(ns)} {unit_label})"
            else:
                g1 = primary.get("group1")
                g2 = primary.get("group2")
                n1 = int(primary.get("n1", 0) or 0)
                n2 = int(primary.get("n2", 0) or 0)
                if isinstance(g1, (list, tuple)) and len(g1) == 1:
                    g1 = g1[0]
                if isinstance(g2, (list, tuple)) and len(g2) == 1:
                    g2 = g2[0]

                def _gname(g):
                    if g is None or isinstance(g, (list, tuple)):
                        return None
                    return _group_display_name(dd_groups, g)

                if g1 is not None and g2 is not None and g1 != g2 and not isinstance(g1, (list, tuple)):
                    p1 = f"{_gname(g1)}={n1}" if n1 else str(_gname(g1))
                    p2 = f"{_gname(g2)}={n2}" if n2 else str(_gname(g2))
                    n_report = f"({p1}, {p2} {unit_label})"
                elif g1 is not None:
                    if isinstance(g1, (list, tuple)):
                        parts = []
                        val = n1 or n2
                        for gg in g1:
                            nm = _gname(gg)
                            parts.append(f"{nm}={val}" if val else str(nm))
                        if parts:
                            n_report = f"({', '.join(parts)} {unit_label})"
                    else:
                        nm = _gname(g1)
                        val = n1 or n2
                        n_report = f"({nm}={val} {unit_label})" if val else f"({nm})"
    except Exception:
        n_report = ""

    if n_report:
        test_label = f"{test_label} {n_report}"

    is_multi = (eff == "Cluster perm.") or len(results) > 1
    reports = []
    for idx, r in enumerate(results):
        if not isinstance(r, dict):
            continue
        set_prefix = ""
        if is_multi:
            sname = r.get("set_name") or r.get("set_id") or f"set{idx+1}"
            set_prefix = f"{sname}: "
        for key in sorted(k for k in r.keys() if k.startswith("p_")):
            aspect = key[2:].replace("_norm", " (norm)")
            use_q = test_fdr and r.get("q_" + key[2:]) is not None
            val_key = "q_" + key[2:] if use_q else key
            val = r.get(val_key, r.get(key))
            if isinstance(val, (int, float)) and np.isfinite(val):
                pstr = f"{val:.3g}" if val >= 0.001 else "<0.001"
            else:
                pstr = "NA"
            label = "q" if use_q else "p"
            reports.append(f"{set_prefix}{aspect}: {label}={pstr}")

    diag = []
    diag_suffix = ""
    if test_sw:
        diag.append("SW")
    if test_levene:
        lev_strs = []
        for r in results:
            for asp in ("amp", "slope"):
                p = r.get(f"levene_p_{asp}")
                if isinstance(p, (int, float)) and np.isfinite(p):
                    pstr = f"{p:.3g}" if p >= 0.001 else "<0.001"
                    lev_strs.append(f"{asp} p={pstr}")
        if lev_strs:
            diag.append("Lev(" + " ".join(lev_strs) + ")")
        else:
            diag.append("Levene")
    if diag:
        diag_suffix = "    " + " ".join(diag)

    if not reports:
        return StatusbarResult(f"{test_label}: done (see console){diag_suffix}", "info")
    text = f"{test_label}: {'  '.join(reports)}{diag_suffix}"
    return StatusbarResult(text, "info")