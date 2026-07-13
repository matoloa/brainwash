"""Pure plot descriptors (no matplotlib/Qt). UIplot view layer renders these."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestMarkerSpec:
    x: float
    y_frac: float
    va: str
    label: str
    color: str
    axis: str
    storage_pcol: str


def p_value_color_alpha(p: float) -> tuple[tuple[float, float, float], float]:
    """RGB color and alpha for heatmap significance dots (p <= 0.05 only)."""
    alpha = 0.5
    if p < 0.005:
        color = (1.0, 0.0, 0.0)
    else:
        t = (0.05 - p) / 0.045
        g = 1.0 - t
        color = (1.0, g, 0.0)
    return color, alpha


def significance_label(val) -> str:
    if isinstance(val, (int, float)) and val == val and val < 0.001:
        return "***"
    if isinstance(val, (int, float)) and val == val and val < 0.01:
        return "**"
    if isinstance(val, (int, float)) and val == val and val < 0.05:
        return "*"
    return "ns"


def marker_text_color(is_sig: bool, *, dark: bool) -> str:
    if is_sig:
        return "white" if dark else "black"
    return "#aaaaaa" if dark else "#555555"


def effective_test_pvalue(res: dict, pcol: str):
    qcol = "q_" + pcol[2:]
    pval = res.get(pcol)
    qval = res.get(qcol)
    if isinstance(qval, (int, float)) and qval == qval:
        return qval
    return pval


def marker_x_for_results(results: list, *, variant: str) -> float | None:
    if not results:
        return None
    res0 = results[0]
    sweeps = res0.get("sweeps", []) or []
    if not sweeps:
        return None
    try:
        x = float(sum(sweeps) / len(sweeps))
    except Exception:
        return None
    if variant in ("paired", "one-sample") and len(results) >= 2:
        sweeps2 = results[1].get("sweeps", []) or []
        if sweeps2:
            try:
                x2 = float(sum(sweeps2) / len(sweeps2))
                x = (x + x2) / 2.0
            except Exception:
                pass
    return x


def aspect_placements(res: dict, *, amp_view: bool, slope_view: bool) -> list[tuple[str, str, float, str]]:
    """Return (pcol, axis_id, y_frac, va) for one result row."""
    amp_pcols = [k for k in res.keys() if k.startswith("p_") and "amp" in k]
    slope_pcols = [k for k in res.keys() if k.startswith("p_") and "slope" in k]
    placements: list[tuple[str, str, float, str]] = []
    if amp_view and slope_view:
        for pcol in amp_pcols:
            placements.append((pcol, "ax1", 0.94, "top"))
        for pcol in slope_pcols:
            placements.append((pcol, "ax2", 0.06, "bottom"))
    elif amp_view:
        for pcol in amp_pcols:
            placements.append((pcol, "ax1", 0.94, "top"))
    elif slope_view:
        for pcol in slope_pcols:
            placements.append((pcol, "ax2", 0.94, "top"))
    return placements


def build_test_marker_specs(
    results: list | None,
    *,
    test_type: str,
    t_variant: str,
    wilcox_variant: str,
    amp_view: bool,
    slope_view: bool,
    dark: bool,
) -> list[TestMarkerSpec]:
    if not results:
        return []
    variant = wilcox_variant if test_type == "Wilcoxon" else t_variant
    is_single = variant in ("paired", "one-sample") and len(results) >= 2
    specs: list[TestMarkerSpec] = []

    for idx, res in enumerate(results):
        if is_single and idx != 0:
            continue
        x = marker_x_for_results(results if is_single else [res], variant=variant if is_single else "unpaired")
        if x is None:
            continue
        for pcol, axis, y_frac, va in aspect_placements(res, amp_view=amp_view, slope_view=slope_view):
            val = effective_test_pvalue(res, pcol)
            label = significance_label(val)
            color = marker_text_color(label != "ns", dark=dark)
            specs.append(
                TestMarkerSpec(
                    x=x,
                    y_frac=y_frac,
                    va=va,
                    label=label,
                    color=color,
                    axis=axis,
                    storage_pcol=pcol,
                )
            )
    return specs


def level_storage_key(base_label: str, level: str | None) -> str:
    if not level or level == "recording":
        return base_label
    return f"{base_label}_{level}"


def display_label_from_key(key: str) -> str:
    for suf in ("_subject", "_slice", "_recording"):
        if key.endswith(suf):
            return key[: -len(suf)]
    return key


def output_legend_locations(*, experiment_type: str, slope_only: bool) -> tuple[str, str]:
    """Legend anchor per output axis (ax1, ax2)."""
    if experiment_type == "io":
        return "lower right", "lower right"
    if slope_only:
        return "upper right", "upper right"
    return "upper right", "lower right"


def heatmap_axis_for_column(col: str) -> str | None:
    if "amp" in col:
        return "ax1"
    if "slope" in col:
        return "ax2"
    return None


def heatmap_y_fraction(col: str) -> float:
    return 0.92 if "amp" in col else 0.08


def significant_heatmap_points(sweeps, ps) -> list[tuple[float, float]]:
    """Sweep index and p-value pairs with finite p <= 0.05."""
    out: list[tuple[float, float]] = []
    for x, p in zip(sweeps, ps):
        if isinstance(p, (int, float)) and p == p and p <= 0.05:
            out.append((float(x), float(p)))
    return out


def output_axis_y_visibility(*, amp_view: bool, slope_view: bool) -> tuple[bool, bool]:
    if not amp_view and not slope_view:
        return False, False
    return amp_view, slope_view


def slope_yaxis_on_left(*, slope_only: bool) -> bool:
    return slope_only