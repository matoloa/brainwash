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