"""Pure drag-zone geometry for event-plot amp/slope handles."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

SWEEP_OUTPUT_ASPECTS = frozenset({"EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"})


def amp_move_zone(x: float, y: float, *, x_margin: float, y_margin: float) -> dict[str, tuple[float, float]]:
    return {
        "x": (x - x_margin, x + x_margin),
        "y": (y - y_margin, y + y_margin),
    }


def slope_drag_state(
    x: Sequence[float],
    y: Sequence[float],
    *,
    x_margin: float,
    y_margin: float,
) -> tuple[tuple[float, float], tuple[float, float], dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    slope_start = (x[0], y[0])
    slope_end = (x[-1], y[-1])
    x_window = min(x), max(x)
    y_window = min(y), max(y)
    move_zone = {
        "x": (x_window[0] - x_margin, x_window[-1] + x_margin),
        "y": (y_window[0] - y_margin, y_window[-1] + y_margin),
    }
    resize_zone = {
        "x": (x[-1] - x_margin, x[-1] + x_margin),
        "y": (y[-1] - y_margin, y[-1] + y_margin),
    }
    return slope_start, slope_end, move_zone, resize_zone


def point_in_zone(x: float, y: float, zone: dict) -> bool:
    if not zone or "x" not in zone or "y" not in zone:
        return False
    x0, x1 = zone["x"]
    y0, y1 = zone["y"]
    return x0 <= x <= x1 and y0 <= y <= y1


def artist_xdata(line) -> np.ndarray:
    return np.asarray(line.get_xdata(), dtype=float).ravel()


def artist_ydata(line) -> np.ndarray:
    return np.asarray(line.get_ydata(), dtype=float).ravel()


def artist_xy_first(line) -> tuple[float, float]:
    xdata = artist_xdata(line)
    ydata = artist_ydata(line)
    return float(xdata[0]), float(ydata[0])


def nearest_point_index_display(
    mouse_disp_x: float,
    mouse_disp_y: float,
    x_data,
    y_data,
    transform,
) -> int | None:
    """Index of the point nearest the mouse in *display* (screen/pixel) space.

    Uses ``transform.transform`` (typically ``Axes.transData``) so X/Y are weighted
    by on-screen distance, not raw data units or axis data-range fractions.
    Returns None when no finite points exist.
    """
    x_arr = np.asarray(x_data, dtype=float).ravel()
    y_arr = np.asarray(y_data, dtype=float).ravel()
    if x_arr.size == 0 or x_arr.size != y_arr.size:
        return None
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    if not np.any(finite):
        return None
    pts = np.column_stack([x_arr, y_arr])
    try:
        disp = np.asarray(transform.transform(pts), dtype=float)
    except Exception:
        return None
    if disp.ndim != 2 or disp.shape[0] != x_arr.size or disp.shape[1] < 2:
        return None
    d2 = (disp[:, 0] - float(mouse_disp_x)) ** 2 + (disp[:, 1] - float(mouse_disp_y)) ** 2
    d2 = np.where(finite, d2, np.nan)
    if np.all(np.isnan(d2)):
        return None
    return int(np.nanargmin(d2))


def snap_to_nearest_x(x_range, x: float):
    """Return the nearest x in *x_range* to mouse *x* (may be numpy scalar)."""
    arr = np.asarray(x_range, dtype=float)
    return arr[np.abs(arr - x).argmin()]


def snap_sweep_index(x_range, x: float) -> int:
    """Snap mouse *x* to nearest sweep index (Python int for range()/set)."""
    return int(snap_to_nearest_x(x_range, x))


def output_sweep_range(start, end) -> set[int]:
    """Inclusive sweep index range from drag endpoints (coerces numpy scalars)."""
    lo = int(min(start, end))
    hi = int(max(start, end))
    return set(range(lo, hi + 1))


def drag_release_line_candidates(
    rec_ID,
    graph: str,
    *,
    dict_rec_show: dict,
    dict_rec_labels: dict,
) -> list[tuple[object, np.ndarray]]:
    if graph == "mean":
        axes = {"axm"}
        require_sweep_aspect = False
    elif graph == "output":
        axes = {"ax1", "ax2"}
        require_sweep_aspect = True
    else:
        return []

    candidates: list[tuple[object, np.ndarray]] = []
    for store in (dict_rec_show, dict_rec_labels):
        if not store:
            continue
        for value in store.values():
            if value.get("rec_ID") != rec_ID or value.get("axis") not in axes:
                continue
            if require_sweep_aspect and value.get("aspect") not in SWEEP_OUTPUT_ASPECTS:
                continue
            line = value.get("line")
            if line is None or not hasattr(line, "get_xdata"):
                continue
            xdata = artist_xdata(line)
            if xdata.size == 0:
                continue
            candidates.append((line, xdata))
        if candidates:
            break
    return candidates


def group_output_sweep_domain(
    dict_group_show: dict | None,
    dict_group_labels: dict | None = None,
) -> list[int]:
    """Inclusive sweep-index domain from visible group artists (groups-only output view).

    Uses max finite x among group mean lines on ax1/ax2 (prefer dict_group_show).
    Returns ``list(range(0, max_x + 1))`` or empty if no usable group series.
    """
    max_sweep = -1
    for store in (dict_group_show, dict_group_labels):
        if not store:
            continue
        for value in store.values():
            if value.get("group_ID") is None:
                continue
            if value.get("axis") not in ("ax1", "ax2"):
                continue
            # Prefer mean lines; skip pure errorbar containers without get_xdata
            line = value.get("line")
            if line is None or not hasattr(line, "get_xdata"):
                continue
            xdata = artist_xdata(line)
            if xdata.size == 0:
                continue
            finite = xdata[np.isfinite(xdata)]
            if finite.size == 0:
                continue
            # Sweep indices are non-negative; ignore negative/weird x (e.g. PP bars)
            finite = finite[finite >= 0]
            if finite.size == 0:
                continue
            max_sweep = max(max_sweep, int(np.floor(float(np.nanmax(finite)))))
        if max_sweep >= 0 and store is dict_group_show:
            break
    if max_sweep < 0:
        return []
    return list(range(0, max_sweep + 1))