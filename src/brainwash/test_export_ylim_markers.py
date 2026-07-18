"""Export ylim headroom for significance markers."""

import matplotlib.pyplot as plt

from export_image import EXPORT_MARKER_TOP_PAD, _expand_export_ylim_for_markers


def test_expand_export_ylim_raises_top_by_pad_fraction():
    fig, ax = plt.subplots()
    ax.set_ylim(0, 1.0)
    _expand_export_ylim_for_markers(ax, top_pad=0.25)
    ymin, ymax = ax.get_ylim()
    assert ymin == 0
    assert abs(ymax - 1.25) < 1e-9
    plt.close(fig)


def test_expand_export_ylim_default_pad_constant():
    fig, ax = plt.subplots()
    ax.set_ylim(0, 2.0)
    _expand_export_ylim_for_markers(ax)
    ymin, ymax = ax.get_ylim()
    assert ymin == 0
    assert abs(ymax - 2.0 * (1.0 + EXPORT_MARKER_TOP_PAD)) < 1e-9
    plt.close(fig)


def test_expand_export_ylim_preserves_bottom():
    fig, ax = plt.subplots()
    ax.set_ylim(-0.5, 1.5)
    _expand_export_ylim_for_markers(ax, top_pad=0.2)
    ymin, ymax = ax.get_ylim()
    assert abs(ymin - (-0.5)) < 1e-9
    assert abs(ymax - (1.5 + 0.2 * 2.0)) < 1e-9
    plt.close(fig)
