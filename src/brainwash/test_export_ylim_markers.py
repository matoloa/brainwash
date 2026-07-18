"""Export ylim headroom and time x-axis tick conversion."""

import matplotlib.pyplot as plt

from export_image import (
    EXPORT_MARKER_TOP_PAD,
    _configure_export_xaxis,
    _expand_export_ylim_for_markers,
)
from ui_state_classes import UIstate


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


def test_export_time_x_scale_600_sweeps_at_0p25hz():
    """600 sweeps @ 0.25 Hz → display minutes scale so xmax plots at 40 min."""
    from export_image import _export_time_x_scale, _scale_export_x

    u = UIstate()
    u.experiment.experiment_type = "time"
    u.apply_time_axis_params(n_bins=600, sweep_hz=0.25, bin_size=1.0)
    scale = _export_time_x_scale(u)
    assert scale is not None
    # 600 / 0.25 / 60 = 40 min
    assert abs(float(_scale_export_x(600, scale)) - 40.0) < 1e-9
    assert abs(float(_scale_export_x(300, scale)) - 20.0) < 1e-9


def test_configure_export_xaxis_scaled_xlim_is_minutes():
    """After data-space conversion, xlim 600 sweeps becomes 40 min."""
    from export_image import _export_time_x_scale

    u = UIstate()
    u.experiment.experiment_type = "time"
    u.apply_time_axis_params(n_bins=600, sweep_hz=0.25, bin_size=1.0)
    u.project.zoom["output_xlim"] = (0, 600)
    scale = _export_time_x_scale(u)

    fig, ax = plt.subplots()
    # plot already-scaled x (as export does)
    ax.plot([0, 20, 40], [1, 1, 1])
    _configure_export_xaxis(ax, u, x_scale=scale)

    assert ax.get_xlabel() == "Time (min)"
    assert abs(ax.get_xlim()[1] - 40.0) < 1e-9
    fig.canvas.draw()
    labels = [t.get_text() for t in ax.get_xticklabels() if t.get_text()]
    # Should not show raw sweep count as a tick label
    assert "600" not in labels
    plt.close(fig)
