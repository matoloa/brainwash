"""Pure tests for GraphCoordinatorMixin zoom limit helpers."""

import numpy as np

from ui_graph import GraphCoordinatorMixin


class _MockLine:
    def __init__(self, x, y, *, visible=True, label=""):
        self._x = np.asarray(x, dtype=float)
        self._y = np.asarray(y, dtype=float)
        self._visible = visible
        self._label = label
        self._transform = None

    def get_xdata(self):
        return self._x

    def get_ydata(self):
        return self._y

    def get_visible(self):
        return self._visible

    def get_transform(self):
        return self._transform

    def get_label(self):
        return self._label


class _MockAxis:
    def __init__(self, lines=()):
        self.transData = object()
        self._lines = []
        for line in lines:
            line._transform = self.transData
            self._lines.append(line)
        self.collections = []

    def get_lines(self):
        return self._lines


def test_xlim_from_artists_applies_padding():
    axis = _MockAxis([_MockLine([0.0, 10.0], [1.0, 2.0])])
    lo, hi = GraphCoordinatorMixin._xlim_from_artists(axis, pad=0.1)
    assert lo == -1.0
    assert hi == 11.0


def test_xlim_from_artists_returns_none_without_data():
    axis = _MockAxis([_MockLine([np.nan], [1.0], visible=False)])
    assert GraphCoordinatorMixin._xlim_from_artists(axis) is None


def test_ylim_from_artists_filters_x_window():
    axis = _MockAxis([_MockLine([0.0, 4.5, 5.5, 10.0], [1.0, 2.0, 4.0, 99.0])])
    lo, hi = GraphCoordinatorMixin._ylim_from_artists(axis, pad=0.0, x_min=4.0, x_max=6.0)
    assert lo == 2.0
    assert hi == 4.0


def test_ylim_from_artists_anchors_ymin():
    axis = _MockAxis([_MockLine([0.0, 10.0], [2.0, 8.0])])
    lo, hi = GraphCoordinatorMixin._ylim_from_artists(axis, pad=0.0, ymin=0.0)
    assert lo == 0.0
    assert hi == 8.0