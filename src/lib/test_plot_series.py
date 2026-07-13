"""Characterization tests for brainwash_ui.plot_series."""

import numpy as np
import pandas as pd

from brainwash_ui import plot_series


def test_io_axis_columns_and_y_column():
    assert plot_series.io_axis_columns("vslope", "EPSPslope") == ("volley_slope", "EPSP_slope")
    assert plot_series.io_y_column("EPSP_amp", variant="norm") == "EPSP_amp_norm"


def test_compute_io_regression_force_zero():
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([2.0, 4.0, 6.0])
    reg = plot_series.compute_io_regression(x, y, force_through_zero=True)
    assert reg is not None
    assert abs(reg.slope - 2.0) < 1e-9
    assert reg.intercept == 0.0
    assert reg.x0 == 0.0


def test_compute_io_regression_ols():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 3.0, 5.0, 7.0])
    reg = plot_series.compute_io_regression(x, y, force_through_zero=False)
    assert reg is not None
    assert abs(reg.slope - 2.0) < 1e-9


def test_pp_overlay_x_map_all_enabled():
    m = plot_series.pp_overlay_x_map(
        {"EPSP_amp": True, "EPSP_slope": True, "volley_amp": True, "volley_slope": True}
    )
    assert m == {"EPSP_amp": 1, "EPSP_slope": 2, "volley_amp": 3, "volley_slope": 4}


def test_pp_overlay_x_map_partial():
    m = plot_series.pp_overlay_x_map({"EPSP_amp": True, "EPSP_slope": False, "volley_amp": True, "volley_slope": False})
    assert m == {"EPSP_amp": 1, "volley_amp": 2}


def test_pp_bar_layout_single_aspect():
    configs = plot_series.pp_bar_layout([("EPSP_amp", "ax1")])
    assert len(configs) == 1
    assert configs[0][0] == "EPSP_amp"
    assert configs[0][3] > 0


def test_extract_group_mean_series():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 2],
            "EPSP_amp_mean": [1.0, 2.0, 3.0],
            "EPSP_amp_SEM": [0.1, 0.2, 0.3],
            "EPSP_amp_norm_mean": [10.0, 20.0, 30.0],
            "EPSP_amp_norm_SEM": [1.0, 2.0, 3.0],
        }
    )
    s = plot_series.extract_group_mean_series(df, "EPSP_amp")
    assert len(s.x) == 3
    assert s.y_norm is not None
    assert len(s.y_norm_sem) == 3


def test_group_mean_plots_for_df():
    df = pd.DataFrame({"EPSP_slope_mean": [1.0, np.nan], "volley_amp_mean": [np.nan, np.nan]})
    plots = plot_series.group_mean_plots_for_df(df)
    assert plots == [("ax2", "EPSP_slope", "EPSP_slope_mean")]


def test_render_group_mean_series_agg():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.DataFrame(
        {
            "sweep": [0, 1],
            "EPSP_amp_mean": [1.0, 2.0],
            "EPSP_amp_SEM": [0.1, 0.1],
        }
    )
    series = plot_series.extract_group_mean_series(df, "EPSP_amp")
    fig, ax = plt.subplots()
    ax.plot(series.x, series.y_mean)
    ax.fill_between(series.x, series.y_mean - series.y_sem, series.y_mean + series.y_sem)
    plt.close(fig)