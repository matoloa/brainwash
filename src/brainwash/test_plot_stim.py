"""Characterization tests for brainwash_ui.plot_stim."""

import numpy as np
import pandas as pd

from brainwash_ui import plot_stim


def _dfmean_with_stim(t_stim: float = 0.04, baseline: float = 0.0, step: float = 0.001) -> pd.DataFrame:
    times = np.linspace(0, 0.1, 101)
    voltage = np.where(times >= t_stim, baseline + step, baseline)
    return pd.DataFrame({"time": times, "prim": voltage})


def test_amp_zero_pre_window():
    dfmean = _dfmean_with_stim(t_stim=0.04, baseline=0.0, step=0.002)
    amp_zero, y_at = plot_stim.amp_zero_and_y_at_stim(dfmean, 0.04, "prim")
    assert amp_zero == 0.0
    assert y_at == 0.002


def test_event_window_shifts_time_to_stim_zero():
    dfmean = _dfmean_with_stim()
    df_event = plot_stim.event_window_df(dfmean, 0.04, -0.01, 0.02, "prim")
    assert not df_event.empty
    assert abs(df_event["time"].min() + 0.01) < 1e-9


def test_resolve_epsp_amp_from_output_row():
    out_stim = pd.DataFrame({"EPSP_amp": [5.0]})
    df_event = pd.DataFrame({"time": [0.0], "prim": [0.001]})
    t_row = pd.Series({"t_EPSP_amp_halfwidth": 0.0})
    val = plot_stim.resolve_epsp_amp_si(out_stim, df_event, 0.01, t_row, "prim", 0.0)
    assert abs(val - 0.005) < 1e-9


def test_volley_amp_hline_mv():
    assert plot_stim.volley_amp_hline_mv(0.001) == 1.0


def test_slope_segment_nan_returns_none():
    df_event = pd.DataFrame({"time": [0.0, 0.01], "prim": [0.0, 0.001]})
    assert plot_stim.slope_segment(df_event, np.nan, 0.01, "prim") is None


def test_stim_num_from_index():
    assert plot_stim.stim_num_from_index(0) == 1


def test_build_stim_event_plot_specs_minimal():
    dfmean = _dfmean_with_stim()
    dft = pd.DataFrame(
        [
            {
                "stim": 1,
                "t_stim": 0.04,
                "t_EPSP_amp": 0.01,
                "t_EPSP_amp_halfwidth": 0.001,
                "t_EPSP_slope_start": 0.005,
                "t_EPSP_slope_end": 0.015,
                "t_volley_amp": np.nan,
                "t_volley_amp_halfwidth": 0.0,
                "t_volley_slope_start": np.nan,
                "t_volley_slope_end": np.nan,
            }
        ]
    )
    dfoutput = pd.DataFrame(
        {
            "sweep": [0, 1, None],
            "stim": [1, 1, 1],
            "EPSP_amp": [5.0, 6.0, 5.5],
            "EPSP_amp_norm": [50.0, 60.0, 55.0],
            "EPSP_slope": [0.1, 0.2, 0.15],
            "EPSP_slope_norm": [10.0, 20.0, 15.0],
            "volley_amp": [1.0, 1.1, 1.05],
            "volley_slope": [0.01, 0.02, 0.015],
        }
    )
    settings = {
        "event_start": -0.01,
        "event_end": 0.02,
        "rgb_EPSP_amp": "blue",
        "rgb_EPSP_slope": "red",
        "rgb_volley_amp": "green",
        "rgb_volley_slope": "orange",
    }
    specs = plot_stim.build_stim_event_plot_specs(
        "rec1",
        dft,
        dfmean,
        dfoutput,
        "prim",
        settings,
        {0: "cyan"},
    )
    assert len(specs) >= 5
    labels = {s.label for s in specs}
    assert "mean rec1 - stim 1 marker" in labels
    assert "rec1 - stim 1 EPSP amp" in labels
    assert any(isinstance(s, plot_stim.StimAmpWidthPlotSpec) for s in specs)
    assert any(isinstance(s, plot_stim.StimLinePlotSpec) and s.axid == "axe" for s in specs)