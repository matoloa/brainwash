"""Pure drag-zone geometry for event-plot amp/slope handles."""

from __future__ import annotations

from collections.abc import Sequence


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