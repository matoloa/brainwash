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
        "stim_intensity": "stim intensity",
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

    # Merge assumptions from config + all result rows (multi-aspect IO).
    assum: dict = {}
    if isinstance(cfg, dict) and isinstance(cfg.get("assumptions"), dict):
        assum.update(cfg["assumptions"])
    if isinstance(formal, list):
        for item in formal:
            if not isinstance(item, dict):
                continue
            for blob in (item.get("assumptions"), (item.get("config") or {}).get("assumptions")):
                if not isinstance(blob, dict):
                    continue
                for k, v in blob.items():
                    if k == "notes":
                        # keep union of notes
                        prev = list(assum.get("notes") or [])
                        for n in v or []:
                            if n not in prev:
                                prev.append(n)
                        assum["notes"] = prev
                    elif assum.get(k) is None and v is not None:
                        assum[k] = v
    global_notes.extend(_assumption_statusbar_tokens(assum))
    if global_notes:
        notes_str = " ".join(global_notes)
        prefix = f"{prefix} {n_report} {xy_label}: {notes_str}"
    else:
        prefix = f"{prefix} {n_report} {xy_label}"
    return StatusbarResult(prefix, "info")


def _finite_p(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def _assumption_statusbar_tokens(assumptions: dict | None) -> list[str]:
    """SW:ok / Lev:ok when p>=0.05; ' - Warning: …' for failures / notes. Never SW:on."""
    out: list[str] = []
    assum = assumptions or {}
    sw_p = _finite_p(assum.get("sw_p"))
    lev_p = _finite_p(assum.get("levene_p"))
    if sw_p is not None and sw_p >= 0.05:
        out.append("SW:ok")
    if lev_p is not None and lev_p >= 0.05:
        out.append("Lev:ok")
    for note in (assum.get("notes") or [])[:2]:
        out.append(f" - Warning: {note}")
    return out


def _collect_assumption_ps(results: list) -> tuple[list[float], list[float], list[str], list[str]]:
    """Gather SW/Levene p-values and skip reasons from formal result rows."""
    sw_ps: list[float] = []
    lev_ps: list[float] = []
    sw_skips: list[str] = []
    lev_skips: list[str] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        for k, v in r.items():
            if k.startswith("sw_p"):
                p = _finite_p(v)
                if p is not None:
                    sw_ps.append(p)
            if k.startswith("levene_p"):
                p = _finite_p(v)
                if p is not None:
                    lev_ps.append(p)
            if k.startswith("sw_skip_") and v:
                sw_skips.append(str(v))
            if k.startswith("levene_skip_") and v:
                lev_skips.append(str(v))
        for blob in (r.get("assumptions"), (r.get("config") or {}).get("assumptions")):
            if not isinstance(blob, dict):
                continue
            p = _finite_p(blob.get("sw_p"))
            if p is not None:
                sw_ps.append(p)
            p = _finite_p(blob.get("levene_p"))
            if p is not None:
                lev_ps.append(p)
    return sw_ps, lev_ps, sw_skips, lev_skips


def _non_io_assumption_diag(results: list, *, test_sw: bool, test_levene: bool) -> str:
    """SW:ok / Lev:ok, warnings, or skip stamps (e.g. SW:n<3). Never silent when checkbox on."""
    tokens: list[str] = []
    sw_ps, lev_ps, sw_skips, lev_skips = _collect_assumption_ps(results)
    if test_sw:
        if sw_ps:
            if any(p < 0.05 for p in sw_ps):
                pmin = min(sw_ps)
                pstr = f"{pmin:.3g}" if pmin >= 0.001 else "<0.001"
                tokens.append(f" - Warning: SW p={pstr}")
            else:
                tokens.append("SW:ok")
        elif sw_skips:
            # e.g. n=2<3 → SW:n<3
            sk = sw_skips[0]
            if "n=" in sk and "<3" in sk:
                tokens.append("SW:n<3")
            else:
                tokens.append(f"SW:skip({sk})")
        else:
            tokens.append("SW:skip")
    if test_levene:
        if lev_ps:
            if any(p < 0.05 for p in lev_ps):
                pmin = min(lev_ps)
                pstr = f"{pmin:.3g}" if pmin >= 0.001 else "<0.001"
                tokens.append(f" - Warning: Lev p={pstr}")
            else:
                tokens.append("Lev:ok")
        elif lev_skips:
            sk = lev_skips[0]
            if "n<2" in sk:
                tokens.append("Lev:n<2")
            else:
                tokens.append(f"Lev:skip({sk})")
        else:
            tokens.append("Lev:skip")
    if not tokens:
        return ""
    return "    " + " ".join(tokens)


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
        "stim_intensity": "stimulus intensity",
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


def _assumption_p_str(p) -> str:
    if not isinstance(p, (int, float)) or not np.isfinite(p):
        return "n.a."
    return f"{p:.3g}" if p >= 0.001 else "<0.001"


def format_io_ancova_assumption_prose(assumptions: dict | None) -> str:
    """Verbose methods-style text for SW/Levene residual checks (figure .md / methods)."""
    if not assumptions:
        return ""
    bits: list[str] = []
    sw_p = assumptions.get("sw_p")
    lev_p = assumptions.get("levene_p")
    notes = list(assumptions.get("notes") or [])

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
                f"(*p* = {_assumption_p_str(sw_p)}); linear-model *p*-values should be interpreted with caution "
                f"(consider robust methods, transforms, or nonparametric alternatives)."
            )
        else:
            bits.append(
                f"Shapiro–Wilk test on residuals did not indicate clear non-normality "
                f"(*p* = {_assumption_p_str(sw_p)})."
            )
    if isinstance(lev_p, (int, float)) and np.isfinite(lev_p):
        if lev_p < 0.05:
            bits.append(
                f"Levene’s test suggested heterogeneous residual variance across groups "
                f"(*p* = {_assumption_p_str(lev_p)}); ANCOVA *p*-values may be sensitive to this."
            )
        else:
            bits.append(
                f"Levene’s test did not indicate clear residual variance heterogeneity across groups "
                f"(*p* = {_assumption_p_str(lev_p)})."
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


def _group_label_for_sw(result: dict, which: str, dd_groups: dict | None = None) -> str:
    """Human label for SW group slot g1/g2."""
    dd_groups = dd_groups or {}
    g = result.get("group1") if which == "g1" else result.get("group2")
    if isinstance(g, (list, tuple)) and g:
        g = g[0]
    if g is None or isinstance(g, (list, tuple)):
        return "group 1" if which == "g1" else "group 2"
    entry = dd_groups.get(g, dd_groups.get(str(g)))
    if isinstance(entry, dict) and entry.get("group_name"):
        return str(entry["group_name"])
    if isinstance(entry, str) and entry:
        return entry
    return f"group {g}"


def format_formal_assumption_report(
    results: list | None,
    *,
    test_sw: bool = False,
    test_levene: bool = False,
    group_names: dict | None = None,
) -> str:
    """Full SW/Levene report for figure .md from non-IO formal test results.

    Self-contained: no references to statusbar or console. SW is reported **per group**
    when g1/g2 keys exist. Includes skip reasons (e.g. n&lt;3) when not computable.
    """
    if not test_sw and not test_levene:
        return ""
    results = results or []
    dd = {}
    for gid, val in (group_names or {}).items():
        if isinstance(val, dict):
            dd[gid] = val
            dd[str(gid)] = val
        else:
            dd[gid] = {"group_name": str(val)}
            dd[str(gid)] = {"group_name": str(val)}

    rows: list[str] = []
    any_sw_p = False
    any_lev_p = False
    for r in results:
        if not isinstance(r, dict):
            continue
        sname = r.get("set_name") or r.get("set_id") or "comparison"
        for asp in ("amp", "slope"):
            if test_sw:
                # Prefer per-group keys; fall back to legacy single sw_p_{asp}
                per_group_found = False
                for which in ("g1", "g2"):
                    pk = f"sw_p_{asp}_{which}"
                    sk = f"sw_skip_{asp}_{which}"
                    if pk not in r and sk not in r:
                        continue
                    per_group_found = True
                    glabel = _group_label_for_sw(r, which, dd)
                    p = r.get(pk)
                    if isinstance(p, (int, float)) and np.isfinite(p):
                        any_sw_p = True
                        verdict = "non-normal" if p < 0.05 else "no clear non-normality"
                        rows.append(
                            f"- **{sname}** / {asp} / **{glabel}**: Shapiro–Wilk on unit values "
                            f"*p* = {_assumption_p_str(p)} ({verdict})."
                        )
                    elif r.get(sk):
                        reason = str(r.get(sk))
                        rows.append(
                            f"- **{sname}** / {asp} / **{glabel}**: Shapiro–Wilk **not computed** "
                            f"(need ≥3 finite units; {reason})."
                        )
                if not per_group_found:
                    pk = f"sw_p_{asp}"
                    sk = f"sw_skip_{asp}"
                    if pk in r or sk in r:
                        p = r.get(pk)
                        if isinstance(p, (int, float)) and np.isfinite(p):
                            any_sw_p = True
                            verdict = "non-normal" if p < 0.05 else "no clear non-normality"
                            rows.append(
                                f"- **{sname}** / {asp}: Shapiro–Wilk on unit values "
                                f"*p* = {_assumption_p_str(p)} ({verdict})."
                            )
                        elif r.get(sk):
                            reason = str(r.get(sk))
                            rows.append(
                                f"- **{sname}** / {asp}: Shapiro–Wilk **not computed** "
                                f"(need ≥3 finite units; {reason})."
                            )
            if test_levene:
                pk = f"levene_p_{asp}"
                sk = f"levene_skip_{asp}"
                if pk in r or sk in r:
                    p = r.get(pk)
                    if isinstance(p, (int, float)) and np.isfinite(p):
                        any_lev_p = True
                        verdict = "heterogeneous variances" if p < 0.05 else "no clear variance heterogeneity"
                        rows.append(
                            f"- **{sname}** / {asp}: Levene’s test across groups "
                            f"*p* = {_assumption_p_str(p)} ({verdict})."
                        )
                    elif r.get(sk):
                        rows.append(
                            f"- **{sname}** / {asp}: Levene’s test **not computed** ({r.get(sk)})."
                        )
        ass = r.get("assumptions") or (r.get("config") or {}).get("assumptions") or {}
        if isinstance(ass, dict) and (ass.get("sw_p") is not None or ass.get("levene_p") is not None):
            prose = format_io_ancova_assumption_prose(ass)
            if prose and prose not in "\n".join(rows):
                rows.append(f"- **{sname}**: {prose}")

    if not rows:
        bits = []
        if test_sw:
            bits.append(
                "Shapiro–Wilk was requested but no SW statistic is stored for this export "
                "(insufficient *n* per group, or the test path did not record results)."
            )
        if test_levene:
            bits.append(
                "Levene’s test was requested but no Levene statistic is stored for this export "
                "(insufficient *n* per group, or the test path did not record results)."
            )
        return " ".join(bits)

    intro = []
    if test_sw:
        intro.append(
            "Shapiro–Wilk tests whether each group’s unit-level values are consistent with a normal "
            "distribution (α = 0.05; reported **per group** when two groups are compared)."
        )
    if test_levene:
        intro.append(
            "Levene’s test assesses equality of variance across groups (α = 0.05)."
        )
    if any_sw_p or any_lev_p:
        intro.append(
            "These checks are diagnostic; significant results caution interpretation of parametric *p*-values "
            "but do not by themselves invalidate the comparison."
        )
    return " ".join(intro) + ("\n\n" + "\n".join(rows) if rows else "")


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
    primary0 = results[0] if results and isinstance(results[0], dict) else {}
    # Engine/UI error payloads (e.g. cluster layout failure) — always surface as warning
    err_msg = primary0.get("error") or (primary0.get("config") or {}).get("error")
    if err_msg:
        return StatusbarResult(f"{eff}: {err_msg}", "warning")

    if eff == "Wilcoxon":
        variant = wilcox_variant
    elif eff == "t-test":
        variant = ttest_variant
    elif eff == "Cluster perm.":
        variant = primary0.get("cluster_mode") or (primary0.get("config") or {}).get("variant")
    else:
        variant = None

    # Strip engine "t-test (PPR)" type suffix if present; show quantity separately.
    eff_display = eff.replace(" (PPR)", "") if isinstance(eff, str) else eff
    test_label = f"{eff_display} ({variant})" if variant else str(eff_display)

    primary = results[0] if results else {}
    cfg0 = (primary0.get("config") or {}) if isinstance(primary0, dict) else {}
    quantity = cfg0.get("quantity") or (primary.get("config") or {}).get("quantity") if isinstance(primary, dict) else None
    is_ppr = isinstance(quantity, str) and "PPR" in quantity
    if is_ppr and "PPR" not in test_label:
        test_label = f"{test_label} · PPR"

    n_report = ""
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

    # Complete-case paired attrition (short glanceable warning)
    n_dropped_total = 0
    if isinstance(primary, dict):
        try:
            n_dropped_total = int(primary.get("n_dropped", 0) or 0)
        except (TypeError, ValueError):
            n_dropped_total = 0
    drop_suffix = f"  {n_dropped_total} n dropped" if n_dropped_total > 0 else ""

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
            if is_ppr and not str(aspect).upper().startswith("PPR"):
                aspect = f"PPR {aspect}"
            use_q = test_fdr and r.get("q_" + key[2:]) is not None
            val_key = "q_" + key[2:] if use_q else key
            val = r.get(val_key, r.get(key))
            if isinstance(val, (int, float)) and np.isfinite(val):
                pstr = f"{val:.3g}" if val >= 0.001 else "<0.001"
            else:
                pstr = "NA"
            label = "q" if use_q else "p"
            reports.append(f"{set_prefix}{aspect}: {label}={pstr}")

    diag_suffix = _non_io_assumption_diag(results, test_sw=test_sw, test_levene=test_levene)
    state: StatusbarState = "warning" if n_dropped_total > 0 else "info"

    if not reports:
        return StatusbarResult(f"{test_label}: done (see console){drop_suffix}{diag_suffix}", state)
    text = f"{test_label}: {'  '.join(reports)}{drop_suffix}{diag_suffix}"
    return StatusbarResult(text, state)
