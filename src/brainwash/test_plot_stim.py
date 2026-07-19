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


def test_axm_stim_markers_carry_stim_for_storage_key():
    """Each axm detection blob must include stim= so keys do not collapse to last stim."""
    dft = pd.DataFrame(
        {
            "stim": [1, 2],
            "t_stim": [0.1, 0.5],
            "t_EPSP_amp": [np.nan, np.nan],
            "t_EPSP_slope_start": [np.nan, np.nan],
            "t_EPSP_slope_end": [np.nan, np.nan],
            "t_volley_amp": [np.nan, np.nan],
            "t_volley_slope_start": [np.nan, np.nan],
            "t_volley_slope_end": [np.nan, np.nan],
        }
    )
    dfmean = pd.DataFrame({"time": np.linspace(0, 1, 20), "voltage": np.zeros(20)})
    dfoutput = pd.DataFrame({"stim": [1, 2], "sweep": [np.nan, np.nan]})
    specs = plot_stim.build_stim_event_plot_specs(
        "recA",
        dft,
        dfmean,
        dfoutput,
        "voltage",
        {"event_start": -0.005, "event_end": 0.05},
        {0: "r", 1: "b"},
    )
    axm_markers = [s for s in specs if isinstance(s, plot_stim.StimMarkerPlotSpec) and s.axid == "axm"]
    assert len(axm_markers) == 2
    assert {s.stim for s in axm_markers} == {1, 2}


def test_validate_drag_update_inputs():
    prow = pd.Series({"recording_name": "r1", "filter": "voltage"})
    trow = {"t_stim": 0.04, "stim": 1}
    x, y = plot_stim.validate_drag_update_inputs(
        prow, trow, "EPSP amp", np.array([0.0, 0.01]), np.array([0.0, 0.001]), None
    )
    assert len(x) == 2


def test_drag_update_label_core_and_output_label():
    assert plot_stim.drag_update_label_core("rec1", "voltage", 1, "EPSP amp") == "rec1 - stim 1 EPSP amp"
    assert (
        plot_stim.drag_update_label_core("rec1", "savgol", 2, "EPSP slope")
        == "rec1 (savgol) - stim 2 EPSP slope"
    )
    assert plot_stim.drag_output_label("rec1 - stim 1 EPSP amp", "EPSP amp", True) == "rec1 - stim 1 EPSP amp norm"
    assert plot_stim.amp_output_column("EPSP amp", True) == "EPSP_amp_norm"


def test_build_slope_drag_update_plan_from_df_when_dfoutput():
    """Non-PP EPSP slope release must not depend on mouseover_out (Preview off)."""
    trow = {"t_stim": 0.04, "stim": 1, "t_EPSP_slope_start": 0.045, "t_EPSP_slope_end": 0.055}
    data_x = np.linspace(0, 0.02, 5)
    data_y = data_x * 0.1
    for is_pp in (True, False):
        plan = plot_stim.build_slope_drag_update_plan(
            trow,
            "EPSP slope",
            0.04,
            data_x,
            data_y,
            "rec1 - stim 1 EPSP slope",
            norm_epsp=False,
            is_pp=is_pp,
            has_dfoutput=True,
        )
        assert plan.output_updates[0].method == "from_df"
        assert plan.output_updates[0].column == "EPSP_slope"
    plan_no_df = plot_stim.build_slope_drag_update_plan(
        trow,
        "EPSP slope",
        0.04,
        data_x,
        data_y,
        "rec1 - stim 1 EPSP slope",
        norm_epsp=False,
        is_pp=False,
        has_dfoutput=False,
    )
    assert plan_no_df.output_updates[0].method == "out_line"


def test_build_amp_drag_update_plan_volley_mean():
    trow = {
        "t_stim": 0.04,
        "stim": 1,
        "t_volley_amp": 0.05,
        "t_volley_amp_halfwidth": 0.001,
        "volley_amp_mean": 0.002,
    }
    data_x = np.array([-0.0015, 0.0, 0.01, 0.02])
    data_y = np.array([0.0, 0.001, 0.002, 0.003])
    plan = plot_stim.build_amp_drag_update_plan(
        trow,
        "volley amp",
        0.04,
        data_x,
        data_y,
        "rec1 - stim 1 volley amp",
        None,
        None,
        norm_epsp=False,
        is_pp=False,
        has_dfoutput=False,
    )
    methods = [u.method for u in plan.output_updates]
    assert methods == ["out_line", "out_mean"]


def test_mean_hline_ydata_matches_x_len_not_series():
    """Mean hlines must keep axhline length; never follow N-point series preview."""
    y = plot_stim.mean_hline_ydata(1.5, x_len=2)
    assert y is not None
    assert list(y) == [1.5, 1.5]
    y600 = plot_stim.mean_hline_ydata(0.25, x_len=600)
    assert y600 is not None and len(y600) == 600 and np.all(y600 == 0.25)
    assert plot_stim.mean_hline_ydata(None) is None
    assert plot_stim.mean_hline_ydata(float("nan")) is None


def test_amp_drag_geometry_and_resolve_drag_amp_si():
    trow = {
        "t_EPSP_amp": 0.05,
        "t_EPSP_amp_halfwidth": 0.001,
    }
    data_x = np.array([-0.0015, 0.0, 0.01, 0.02])
    data_y = np.array([0.0, 0.001, 0.002, 0.003])
    geom = plot_stim.amp_drag_geometry(trow, "EPSP amp", 0.04, data_x, data_y)
    assert abs(geom.t_amp - 0.01) < 1e-9
    assert geom.amp_zero == 0.0
    assert plot_stim.resolve_drag_amp_si(5000.0, geom.y_position, geom.amp_zero) == 5.0


def test_slope_marker_xy():
    trow = {"t_EPSP_slope_start": 0.045, "t_EPSP_slope_end": 0.055}
    data_x = np.linspace(0, 0.02, 5)
    data_y = data_x * 0.1
    x_data, y_data = plot_stim.slope_marker_xy(trow, "EPSP slope", 0.04, data_x, data_y)
    assert len(x_data) == 2
    assert abs(x_data[0] - 0.005) < 1e-6
    assert abs(x_data[1] - 0.015) < 1e-6


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


def test_volley_marker_and_mean_use_green_not_legacy_magenta():
    """Legacy magenta settings must not paint volley markers / mean hlines."""
    from ui_state_parts import _DEFAULT_MEASURE_RGB

    dfmean = _dfmean_with_stim()
    dft = pd.DataFrame(
        [
            {
                "stim": 1,
                "t_stim": 0.04,
                "t_EPSP_amp": np.nan,
                "t_EPSP_amp_halfwidth": 0.0,
                "t_EPSP_slope_start": np.nan,
                "t_EPSP_slope_end": np.nan,
                "t_volley_amp": 0.005,
                "t_volley_amp_halfwidth": 0.0005,
                "t_volley_slope_start": 0.002,
                "t_volley_slope_end": 0.004,
                "volley_amp_mean": 0.001,
                "volley_slope_mean": 0.5,
            }
        ]
    )
    dfoutput = pd.DataFrame(
        {
            "sweep": [0, 1, None],
            "stim": [1, 1, 1],
            "EPSP_amp": [np.nan, np.nan, np.nan],
            "EPSP_amp_norm": [np.nan, np.nan, np.nan],
            "EPSP_slope": [np.nan, np.nan, np.nan],
            "EPSP_slope_norm": [np.nan, np.nan, np.nan],
            "volley_amp": [1.0, 1.1, 1.05],
            "volley_slope": [0.01, 0.02, 0.015],
        }
    )
    settings = {
        "event_start": -0.01,
        "event_end": 0.02,
        "rgb_EPSP_amp": (0.2, 0.25, 0.85),
        "rgb_EPSP_slope": (0.45, 0.55, 0.95),
        # Stock pre-1.0.0 magenta — must remap to green family
        "rgb_volley_amp": (1.0, 0.2, 1.0),
        "rgb_volley_slope": (1.0, 0.5, 1.0),
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
    by_label = {s.label: s for s in specs}
    amp_green = _DEFAULT_MEASURE_RGB["rgb_volley_amp"]
    slope_green = _DEFAULT_MEASURE_RGB["rgb_volley_slope"]
    assert by_label["rec1 - stim 1 volley amp marker"].color == amp_green
    assert by_label["rec1 - stim 1 volley amp mean"].color == amp_green
    assert by_label["rec1 - stim 1 volley amp"].color == amp_green
    assert by_label["rec1 - stim 1 volley slope marker"].color == slope_green
    assert by_label["rec1 - stim 1 volley slope mean"].color == slope_green


def test_mean_of_selected_sweeps():
    df = pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1],
            "time": [0.0, 0.01, 0.0, 0.01],
            "prim": [1.0, 2.0, 3.0, 4.0],
        }
    )
    mean_df = plot_stim.mean_of_selected_sweeps(df, [0, 1], "prim")
    assert list(mean_df["prim"]) == [2.0, 3.0]


def test_amp_x_is_zero_width():
    assert plot_stim.amp_x_is_zero_width((0.01, 0.01)) is True
    assert plot_stim.amp_x_is_zero_width((0.01, 0.02)) is False


def test_build_axe_mean_plot_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1],
            "time": [0.03, 0.04, 0.05, 0.06],
            "prim": [0.0, 0.001, 0.0, 0.002],
        }
    )
    df_t = pd.DataFrame([{"t_stim": 0.04}, {"t_stim": 0.05}])
    settings = {"filter": "prim", "event_start": -0.01, "event_end": 0.02, "alpha_line": 0.8}
    specs = plot_stim.build_axe_mean_plot_specs("rec1", [0, 1], df, df_t, settings, {0: "red", 1: "blue"})
    assert len(specs) == 2
    assert specs[0].label == "axe mean selected sweeps - stim 1"
    assert specs[0].axid == "axe"
    assert specs[0].rec_id == "rec1"
    assert specs[0].stim == 1
    assert specs[0].alpha == 0.4
    assert specs[0].color == "red"