import numpy as np
import pandas as pd

from ui_interactive import _artist_xdata, _drag_release_line_candidates


class _MockLine:
    def __init__(self, x):
        self._x = x

    def get_xdata(self):
        return self._x


def test_artist_xdata_accepts_pandas_series():
    line = _MockLine(pd.Series([0.0, 5.0, 10.0]))
    assert np.array_equal(_artist_xdata(line), np.array([0.0, 5.0, 10.0]))


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
    candidates = _drag_release_line_candidates(1, "output", dict_rec_show=rec_show, dict_rec_labels={})
    assert len(candidates) == 1
    assert candidates[0][1][-1] == 2.0