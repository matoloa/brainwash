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