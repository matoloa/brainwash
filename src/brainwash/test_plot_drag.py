import numpy as np
import pandas as pd

from brainwash_ui import plot_drag


class _MockLine:
    def __init__(self, x, y=None):
        self._x = x
        self._y = y if y is not None else x

    def get_xdata(self):
        return self._x

    def get_ydata(self):
        return self._y


def test_amp_move_zone():
    zone = plot_drag.amp_move_zone(1.0, 2.0, x_margin=0.1, y_margin=0.2)
    assert zone == {"x": (0.9, 1.1), "y": (1.8, 2.2)}


def test_slope_drag_state():
    start, end, move, resize = plot_drag.slope_drag_state(
        [0.0, 1.0, 2.0],
        [1.0, 3.0, 2.0],
        x_margin=0.1,
        y_margin=0.2,
    )
    assert start == (0.0, 1.0)
    assert end == (2.0, 2.0)
    assert move == {"x": (-0.1, 2.1), "y": (0.8, 3.2)}
    assert resize == {"x": (1.9, 2.1), "y": (1.8, 2.2)}


def test_point_in_zone():
    zone = {"x": (1.0, 2.0), "y": (3.0, 4.0)}
    assert plot_drag.point_in_zone(1.5, 3.5, zone)
    assert not plot_drag.point_in_zone(0.5, 3.5, zone)
    assert not plot_drag.point_in_zone(1.5, 3.5, {})


def test_artist_xdata_accepts_pandas_series():
    line = _MockLine(pd.Series([0.0, 5.0, 10.0]))
    assert np.array_equal(plot_drag.artist_xdata(line), np.array([0.0, 5.0, 10.0]))


def test_artist_xy_first():
    line = _MockLine(pd.Series([2.0]), pd.Series([4.0]))
    assert plot_drag.artist_xy_first(line) == (2.0, 4.0)


class _IdentityTransform:
    def transform(self, pts):
        return np.asarray(pts, dtype=float)


class _ScaleYTransform:
    """Maps data → display with Y stretched 10× (simulates tall aspect in data, short on screen)."""

    def transform(self, pts):
        p = np.asarray(pts, dtype=float).copy()
        p[:, 1] = p[:, 1] * 10.0
        return p


def test_nearest_point_index_display_identity():
    # Mouse at (1, 0); points at (0,0) and (2,0) → closer is (0,0) index 0? dist 1 vs 1 — first min
    idx = plot_drag.nearest_point_index_display(0.1, 0.0, [0.0, 2.0], [0.0, 0.0], _IdentityTransform())
    assert idx == 0
    idx = plot_drag.nearest_point_index_display(1.9, 0.0, [0.0, 2.0], [0.0, 0.0], _IdentityTransform())
    assert idx == 1


def test_nearest_point_index_display_uses_screen_not_data_range():
    # Two candidates from mouse at (0, 0) in *data*:
    # A: (1, 0) — far in X only
    # B: (0, 0.5) — far in Y only
    # Identity display: A is farther in data units (1 vs 0.5) → B wins.
    xs = [1.0, 0.0]
    ys = [0.0, 0.5]
    assert plot_drag.nearest_point_index_display(0.0, 0.0, xs, ys, _IdentityTransform()) == 1
    # After Y×10 display transform, B is 5 display units away, A is 1 → A wins (screen-space).
    assert plot_drag.nearest_point_index_display(0.0, 0.0, xs, ys, _ScaleYTransform()) == 0


def test_nearest_point_index_display_all_nan():
    assert plot_drag.nearest_point_index_display(0.0, 0.0, [np.nan], [np.nan], _IdentityTransform()) is None


def test_snap_sweep_index_returns_python_int():
    assert plot_drag.snap_sweep_index(list(range(10)), 3.7) == 4
    assert type(plot_drag.snap_sweep_index(list(range(10)), 3.7)) is int


def test_output_sweep_range_coerces_numpy_scalars():
    import numpy as np

    sel = plot_drag.output_sweep_range(np.float64(2.0), np.int64(5))
    assert sel == {2, 3, 4, 5}


def test_group_output_sweep_domain_from_show_store():
    show = {
        "g1 amp": {
            "group_ID": 1,
            "axis": "ax1",
            "aspect": "EPSP_amp",
            "line": _MockLine([0.0, 5.0, 10.0]),
        },
        "g2 slope": {
            "group_ID": 2,
            "axis": "ax2",
            "aspect": "EPSP_slope",
            "line": _MockLine([0.0, 3.0, 7.0]),
        },
    }
    domain = plot_drag.group_output_sweep_domain(show, None)
    assert domain == list(range(0, 11))


def test_group_output_sweep_domain_empty():
    assert plot_drag.group_output_sweep_domain({}, {}) == []
    assert plot_drag.group_output_sweep_domain(None, None) == []


def test_drag_release_line_candidates_prefers_sweep_aspects():
    rec_show = {
        "fill": {
            "rec_ID": 1,
            "axis": "ax1",
            "aspect": None,
            "line": _MockLine(pd.Series([0.0, 99.0])),
        },
        "amp": {
            "rec_ID": 1,
            "axis": "ax1",
            "aspect": "EPSP_amp",
            "line": _MockLine([0.0, 1.0, 2.0]),
        },
    }
    candidates = plot_drag.drag_release_line_candidates(1, "output", dict_rec_show=rec_show, dict_rec_labels={})
    assert len(candidates) == 1
    assert candidates[0][1][-1] == 2.0