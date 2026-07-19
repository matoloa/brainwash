"""Characterization tests for brainwash_ui.plot_series."""

import numpy as np
import pandas as pd
import pytest

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


def test_pp_group_tick_label_map():
    # One tick per box center; labels kept per box (not collapsed).
    ticks, labels = plot_series.pp_group_tick_label_map(
        [(0.6, 0.8, "G1 amp (n=3)"), (1.6, 0.8, "G2 amp (n=4)")]
    )
    assert ticks == [1.0, 2.0]
    assert labels == ["G1 amp (n=3)", "G2 amp (n=4)"]


def test_pp_group_x_position_skips_empty_groups():
    dd = {
        "g0": {"rec_IDs": []},
        "g1": {"rec_IDs": ["r1"]},
        "g2": {"rec_IDs": ["r2"]},
    }
    assert plot_series.pp_group_x_position(dd, "g1") == 1
    assert plot_series.pp_group_x_position(dd, "g2") == 2


def test_pp_group_xlim_from_ticks():
    assert plot_series.pp_group_xlim_from_ticks([1.0, 2.0, 3.0], pad=0.6) == (0.4, 3.6)


def test_pp_active_aspects_omits_volley_under_relative():
    cb = {
        "EPSP_amp": True,
        "EPSP_slope": True,
        "volley_amp": True,
        "volley_slope": True,
        "norm_EPSP": False,
    }
    active = plot_series.pp_active_aspects(cb)
    assert ("volley_amp", "ax1") in active
    assert ("volley_slope", "ax2") in active
    cb["norm_EPSP"] = True
    active_rel = plot_series.pp_active_aspects(cb)
    assert ("volley_amp", "ax1") not in active_rel
    assert ("volley_slope", "ax2") not in active_rel
    assert ("EPSP_amp", "ax1") in active_rel
    # Checkboxes preserved
    assert cb["volley_amp"] is True
    assert cb["volley_slope"] is True


def test_pp_overlay_x_map_all_enabled():
    m = plot_series.pp_overlay_x_map(
        {"EPSP_amp": True, "EPSP_slope": True, "volley_amp": True, "volley_slope": True}
    )
    assert m == {"EPSP_amp": 1, "EPSP_slope": 2, "volley_amp": 3, "volley_slope": 4}


def test_pp_overlay_x_map_partial():
    # Fixed slots: volley amp stays at 3 (never collapses onto EPSP amp at 1)
    m = plot_series.pp_overlay_x_map({"EPSP_amp": True, "EPSP_slope": False, "volley_amp": True, "volley_slope": False})
    assert m == {"EPSP_amp": 1, "volley_amp": 3}


def test_pp_recording_view_ticks_match_overlay_slots():
    checkbox = {"EPSP_amp": True, "EPSP_slope": False, "volley_amp": True, "volley_slope": False}
    ticks, labels = plot_series.pp_recording_view_ticks(checkbox)
    assert ticks == [1, 3]
    assert labels == ["EPSP Amp", "Volley Amp"]
    # Data x for each aspect must equal its tick (never volley→amp)
    o1 = __import__("pandas").DataFrame({"EPSP_amp": [1.0], "volley_amp": [1.0]})
    o2 = __import__("pandas").DataFrame({"EPSP_amp": [2.0], "volley_amp": [2.0]})
    specs = plot_series.pp_recording_ppr_specs(o1, o2, checkbox, {"rgb_EPSP_amp": "b", "rgb_volley_amp": "g"})
    by_asp = {s.aspect: s.x_val for s in specs}
    assert by_asp["EPSP_amp"] == 1
    assert by_asp["volley_amp"] == 3


def test_aggregate_ppr_at_level_recording():
    rec_ppr = {"r1": {"EPSP_amp": 2.0}, "r2": {"EPSP_amp": 4.0}}
    agg = plot_series.aggregate_ppr_at_level(rec_ppr, "recording", None)
    assert agg.ppr_data["EPSP_amp"] == [2.0, 4.0]
    assert agg.rec_id_order["EPSP_amp"] == ["r1", "r2"]


def test_aggregate_ppr_at_level_subject_collapses_recs():
    """Two recs of the same subject → one unit mean; different subject stays separate."""
    rec_ppr = {
        "r1": {"EPSP_amp": 2.0},
        "r2": {"EPSP_amp": 4.0},  # same subject as r1
        "r3": {"EPSP_amp": 6.0},  # other subject
    }
    df_p = pd.DataFrame(
        {
            "ID": ["r1", "r2", "r3"],
            "subject": ["S1", "S1", "S2"],
            "slice": ["1", "2", "1"],
        }
    )
    agg = plot_series.aggregate_ppr_at_level(rec_ppr, "subject", df_p)
    vals = sorted(agg.ppr_data["EPSP_amp"])
    assert vals == [3.0, 6.0]  # mean(2,4)=3 for S1; 6 for S2
    assert len(agg.rec_id_order["EPSP_amp"]) == 2  # unit labels for dots


def test_rec_mean_ppr_from_dfoutput():
    df = pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1],
            "stim": [1, 2, 1, 2],
            "EPSP_amp": [1.0, 2.0, 2.0, 4.0],
        }
    )
    means = plot_series.rec_mean_ppr_from_dfoutput(df)
    assert means["EPSP_amp"] == pytest.approx(2.0)  # mean of 2/1 and 4/2


def test_ppr_by_sweep_from_dfoutput():
    df = pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1, 2, 2],
            "stim": [1, 2, 1, 2, 1, 2],
            "EPSP_amp": [1.0, 2.0, 2.0, 3.0, 1.0, 1.5],
        }
    )
    by = plot_series.ppr_by_sweep_from_dfoutput(df, "EPSP_amp")
    assert by[0] == pytest.approx(2.0)
    assert by[1] == pytest.approx(1.5)
    assert by[2] == pytest.approx(1.5)
    # Filter to one sweep
    by1 = plot_series.ppr_by_sweep_from_dfoutput(df, "EPSP_amp", sweeps=[1])
    assert list(by1.keys()) == [1]
    assert by1[1] == pytest.approx(1.5)
    # Mean of all sweeps matches rec_mean_ppr
    assert float(np.mean(list(by.values()))) == pytest.approx(plot_series.rec_mean_ppr_from_dfoutput(df)["EPSP_amp"])


def test_aggregate_ppr_at_level_slice_keeps_slices_separate():
    rec_ppr = {
        "r1": {"EPSP_amp": 2.0},
        "r2": {"EPSP_amp": 4.0},
    }
    df_p = pd.DataFrame(
        {
            "ID": ["r1", "r2"],
            "subject": ["S1", "S1"],
            "slice": ["1", "2"],
        }
    )
    agg = plot_series.aggregate_ppr_at_level(rec_ppr, "slice", df_p)
    assert sorted(agg.ppr_data["EPSP_amp"]) == [2.0, 4.0]


def test_aggregate_ppr_at_level_without_df_falls_back_to_rec():
    """Missing hierarchy must not invent subject units (silent rec-level fallback)."""
    rec_ppr = {"r1": {"EPSP_amp": 2.0}, "r2": {"EPSP_amp": 4.0}}
    agg = plot_series.aggregate_ppr_at_level(rec_ppr, "subject", None)
    assert sorted(agg.ppr_data["EPSP_amp"]) == [2.0, 4.0]


def test_pp_group_bar_store_items():
    spec = plot_series.PpGroupBarPlotSpec(
        aspect="EPSP_amp",
        axid="ax1",
        bar_x=1.0,
        bar_width=0.8,
        mean_val=1.5,
        sem_val=0.1,
        overlay_x=1,
        scatter_points=(plot_series.PpGroupScatterPointSpec(1.1, 2.0, "r1"),),
        scatter_color="white",
    )
    items = plot_series.pp_group_bar_store_items(spec)
    assert len(items) == 3  # bar + err + point (no overlays)
    assert items[-1].suffix == "r1 point"


def test_build_pp_group_box_plot_specs():
    agg = plot_series.PprLevelAggregate(
        ppr_data={"EPSP_amp": [1.0, 2.0, 3.0], "EPSP_slope": [], "volley_amp": [], "volley_slope": []},
        rec_id_order={"EPSP_amp": ["r1", "r2", "r3"], "EPSP_slope": [], "volley_amp": [], "volley_slope": []},
    )
    rng = np.random.default_rng(0)
    specs = plot_series.build_pp_group_box_plot_specs(
        aggregate=agg,
        x_pos=1.0,
        group_name="Ctl",
        checkbox={"EPSP_amp": True, "EPSP_slope": False, "volley_amp": False, "volley_slope": False},
        settings={"rgb_EPSP_amp": "blue"},
        rng=rng,
    )
    assert len(specs) == 1
    assert specs[0].n == 3
    assert specs[0].tick_label == "Ctl amp (n=3)"
    assert specs[0].values == (1.0, 2.0, 3.0)
    assert len(specs[0].scatter_points) == 3


def test_build_pp_group_bar_plot_specs():
    agg = plot_series.PprLevelAggregate(
        ppr_data={"EPSP_amp": [2.0, 4.0], "EPSP_slope": [], "volley_amp": [], "volley_slope": []},
        rec_id_order={"EPSP_amp": ["r1", "r2"], "EPSP_slope": [], "volley_amp": [], "volley_slope": []},
    )
    rng = np.random.default_rng(0)
    specs = plot_series.build_pp_group_bar_plot_specs(
        aggregate=agg,
        x_pos=1.0,
        level="recording",
        checkbox={"EPSP_amp": True, "EPSP_slope": False, "volley_amp": False, "volley_slope": False},
        settings={"rgb_EPSP_amp": "blue", "rgb_EPSP_slope": "red", "rgb_volley_amp": "g", "rgb_volley_slope": "o"},
        rng=rng,
    )
    assert len(specs) == 1
    assert specs[0].mean_val == 3.0
    assert len(specs[0].scatter_points) == 2


def test_build_io_group_plot_specs():
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([2.0, 4.0, 6.0])
    specs = plot_series.build_io_group_plot_specs(
        "G1",
        x,
        y,
        y_col_base="EPSP_amp",
        variant="raw",
        level="recording",
        force_through_zero=True,
        group_ID=1,
    )
    assert len(specs) == 2
    assert isinstance(specs[0], plot_series.IoGroupScatterPlotSpec)
    assert isinstance(specs[1], plot_series.IoGroupTrendlinePlotSpec)
    assert specs[0].storage_key.startswith("grp|1|")
    assert specs[0].label == "G1 raw IO scatter"
    legacy = plot_series.build_io_group_plot_specs(
        "G1", x, y, y_col_base="EPSP_amp", variant="raw", level="recording", force_through_zero=True
    )
    assert legacy[0].storage_key == "G1 raw IO scatter"


def test_build_pp_graph_refresh_xaxis_plan_group_bars():
    # left=0.6, width=0.8 → center 1.0 (box at integer group slot)
    specs = [(0.6, 0.8, "G1 amp (n=3)")]
    plan = plot_series.build_pp_graph_refresh_xaxis_plan(specs, {"EPSP_amp": True}, pp_has_recs=False)
    assert plan.ticks == (1.0,)
    assert plan.ticklabels == ("G1 amp (n=3)",)
    assert plan.labels_only is True
    assert plan.ax1_xlabel == ""


def test_build_pp_graph_refresh_xaxis_plan_recording_view():
    checkbox = {
        "EPSP_amp": True,
        "EPSP_slope": False,
        "volley_amp": False,
        "volley_slope": False,
    }
    plan = plot_series.build_pp_graph_refresh_xaxis_plan([], checkbox, pp_has_recs=True)
    assert plan.ticks == (1,)
    assert plan.labels_only is True


def test_build_pp_graph_refresh_xaxis_plan_no_aspects():
    checkbox = {
        "EPSP_amp": False,
        "EPSP_slope": False,
        "volley_amp": False,
        "volley_slope": False,
    }
    plan = plot_series.build_pp_graph_refresh_xaxis_plan([], checkbox, pp_has_recs=True)
    assert plan.ax1_xlabel == "No aspect selected"
    assert plan.hide_all is True


def test_pp_has_visible_rec_ppr():
    assert plot_series.pp_has_visible_rec_ppr({"rec PPR EPSP_amp": {}}) is True
    assert plot_series.pp_has_visible_rec_ppr({"rec PPR EPSP_amp marker": {}}) is False
    assert plot_series.pp_has_visible_rec_ppr({}) is False


def test_collect_pp_group_bar_patch_specs():
    class _Patch:
        def __init__(self, x, width):
            self._x = x
            self._width = width

        def get_x(self):
            return self._x

        def get_width(self):
            return self._width

    class _Bar:
        patches = [_Patch(0.6, 0.3)]

    show = {
        "Group A PPR EPSP_amp bar_subject": {
            "line": _Bar(),
            "is_overlay": False,
            "level": "subject",
        },
        "Group A PPR EPSP_amp overlay_bar_subject": {
            "line": _Bar(),
            "is_overlay": True,
            "level": "subject",
        },
    }
    specs = plot_series.collect_pp_group_bar_patch_specs(show, "subject", lambda base: base)
    assert len(specs) == 1
    assert specs[0][2] == "Group A"


def test_pp_bar_layout_single_aspect():
    configs = plot_series.pp_bar_layout([("EPSP_amp", "ax1")])
    assert len(configs) == 1
    assert configs[0][0] == "EPSP_amp"
    assert configs[0][3] > 0
    # Single aspect → centered on group slot
    assert abs(configs[0][2]) < 1e-9


def test_pp_bar_layout_amp_slope_side_by_side():
    """Amp (ax1) and slope (ax2) share twinx x-space → different offsets, not stacked."""
    configs = plot_series.pp_bar_layout([("EPSP_amp", "ax1"), ("EPSP_slope", "ax2")])
    assert len(configs) == 2
    assert configs[0][0] == "EPSP_amp"
    assert configs[1][0] == "EPSP_slope"
    assert configs[0][2] < 0  # amp left of group center
    assert configs[1][2] > 0  # slope right of group center
    assert abs(configs[0][2] - configs[1][2]) > 0.2


def test_pp_bar_layout_volley_not_on_epsp_amp_slot():
    """EPSP amp and volley amp get distinct offsets (volley is not drawn on amp's tick)."""
    configs = plot_series.pp_bar_layout([("EPSP_amp", "ax1"), ("volley_amp", "ax1")])
    assert [c[0] for c in configs] == ["EPSP_amp", "volley_amp"]
    assert configs[0][2] != configs[1][2]
    assert configs[0][2] < configs[1][2]


def test_build_pp_group_box_amp_and_volley_distinct_x():
    agg = plot_series.PprLevelAggregate(
        ppr_data={
            "EPSP_amp": [1.0, 2.0],
            "EPSP_slope": [],
            "volley_amp": [1.5, 2.5],
            "volley_slope": [],
        },
        rec_id_order={
            "EPSP_amp": ["r1", "r2"],
            "EPSP_slope": [],
            "volley_amp": ["r1", "r2"],
            "volley_slope": [],
        },
    )
    specs = plot_series.build_pp_group_box_plot_specs(
        aggregate=agg,
        x_pos=1.0,
        group_name="G1",
        checkbox={"EPSP_amp": True, "EPSP_slope": False, "volley_amp": True, "volley_slope": False},
        settings={"rgb_EPSP_amp": "blue", "rgb_volley_amp": "green"},
        rng=__import__("numpy").random.default_rng(0),
    )
    assert len(specs) == 2
    by_asp = {s.aspect: s for s in specs}
    assert by_asp["EPSP_amp"].box_x != by_asp["volley_amp"].box_x
    assert by_asp["EPSP_amp"].tick_label.startswith("G1 amp")
    assert "volley" in by_asp["volley_amp"].tick_label
    # Tick centers match box centers
    lefts = [(s.box_x - s.box_width / 2, s.box_width, s.tick_label) for s in specs]
    ticks, labels = plot_series.pp_group_tick_label_map(lefts)
    assert ticks == sorted([by_asp["EPSP_amp"].box_x, by_asp["volley_amp"].box_x])


def test_collect_pp_group_bar_patch_specs_from_box_meta():
    # Side-by-side: amp left of center, slope right (twinx shared x)
    show = {
        "Ctl PPR EPSP_amp box_recording": {
            "pp_box_x": 0.8,
            "pp_box_width": 0.36,
            "pp_tick_label": "Ctl amp (n=3)",
            "axis": "ax1",
            "level": "recording",
            "is_overlay": False,
        },
        "Ctl PPR EPSP_slope box_recording": {
            "pp_box_x": 1.2,
            "pp_box_width": 0.36,
            "pp_tick_label": "Ctl slope (n=3)",
            "axis": "ax2",
            "level": "recording",
            "is_overlay": False,
        },
        "Drug PPR EPSP_amp box_recording": {
            "pp_box_x": 1.8,
            "pp_box_width": 0.36,
            "pp_tick_label": "Drug amp (n=4)",
            "axis": "ax1",
            "level": "recording",
            "is_overlay": False,
        },
        "Drug PPR EPSP_slope box_recording": {
            "pp_box_x": 2.2,
            "pp_box_width": 0.36,
            "pp_tick_label": "Drug slope (n=4)",
            "axis": "ax2",
            "level": "recording",
            "is_overlay": False,
        },
    }
    # Combined (no axis filter): labels for every box on the shared x-axis
    all_specs = plot_series.collect_pp_group_bar_patch_specs(show, "recording", lambda base: base)
    assert len(all_specs) == 4
    ticks, labels = plot_series.pp_group_tick_label_map(all_specs)
    assert ticks == [0.8, 1.2, 1.8, 2.2]
    assert labels == ["Ctl amp (n=3)", "Ctl slope (n=3)", "Drug amp (n=4)", "Drug slope (n=4)"]
    xlim = plot_series.pp_group_xlim_from_ticks(ticks, pad=0.6)
    assert xlim[0] == pytest.approx(0.2)
    assert xlim[1] == pytest.approx(2.8)


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


def test_compute_ppr_percent():
    ppr = plot_series.compute_ppr_percent(np.array([1.0, 2.0]), np.array([2.0, 1.0]))
    assert ppr[0] == 200.0
    assert ppr[1] == 50.0


def test_compute_ppr_non_finite_to_nan():
    v1 = np.array([1.0, 0.0, 2.0])
    v2 = np.array([2.0, 1.0, 4.0])
    ppr = plot_series.compute_ppr(v1, v2)
    assert ppr[0] == 2.0
    assert np.isnan(ppr[1])


def test_pp_recording_ppr_specs():
    o1 = pd.DataFrame({"EPSP_amp": [1.0, 2.0]}, index=[0, 1])
    o2 = pd.DataFrame({"EPSP_amp": [2.0, 4.0]}, index=[0, 1])
    specs = plot_series.pp_recording_ppr_specs(o1, o2, {"EPSP_amp": True}, {"rgb_EPSP_amp": "blue"})
    assert len(specs) == 1
    assert specs[0].x_val == 1
    assert len(specs[0].ppr) == 2


def test_stim_aggregate_sem_reindex():
    df_sem = pd.DataFrame({"EPSP_amp": [0.1, 0.2]}, index=[1, 2])
    out_stim = pd.DataFrame({"stim": [1, 2], "EPSP_amp": [1.0, 2.0]})
    sem = plot_series.stim_aggregate_sem(df_sem, out_stim, "EPSP_amp")
    assert len(sem) == 2


def test_build_io_refresh_specs_for_rec():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 2],
            "stim": [1, 1, 1],
            "volley_amp": [1.0, 2.0, 3.0],
            "EPSP_amp": [2.0, 4.0, 6.0],
            "EPSP_amp_norm": [50.0, 100.0, 150.0],
        }
    )
    dict_rec_labels = {
        "rec1 raw IO scatter": {"x_mode": "io", "variant": "raw"},
        "rec1 raw IO trendline": {"x_mode": "io", "variant": "raw"},
        "rec2 raw IO scatter": {"x_mode": "io", "variant": "raw"},
    }
    specs = plot_series.build_io_refresh_specs_for_rec(
        "rec1",
        dict_rec_labels,
        df,
        "vamp",
        "EPSPamp",
        force_through_zero=True,
    )
    assert len(specs) == 2
    assert specs[0].label == "rec1 raw IO scatter"
    assert isinstance(specs[0], plot_series.IoScatterRefreshSpec)
    assert isinstance(specs[1], plot_series.IoTrendlineRefreshSpec)


def test_out_line_xy_from_df():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 0, 1],
            "stim": [1, 1, 2, 2],
            "EPSP_amp": [1.0, 2.0, 3.0, 4.0],
        }
    )
    xy = plot_series.out_line_xy_from_df(df, 2, "EPSP_amp")
    assert xy is not None
    assert list(xy[0]) == [0, 1]
    assert list(xy[1]) == [3.0, 4.0]
    assert plot_series.out_line_xy_from_df(df, 9, "EPSP_amp") is None


def test_build_ppr_overlay_refresh_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 0, 1],
            "stim": [1, 1, 2, 2],
            "EPSP_amp": [1.0, 2.0, 2.0, 4.0],
        }
    )
    existing = frozenset({"rec1 PPR EPSP_amp raw", "rec1 PPR EPSP_amp norm"})
    specs = plot_series.build_ppr_overlay_refresh_specs(
        "rec1",
        df,
        "EPSP_amp",
        {"EPSP_amp": True},
        {"rgb_EPSP_amp": "blue"},
        existing,
    )
    assert len(specs) == 2
    assert specs[0].y[0] == 2.0


def test_build_stim_aggregate_refresh_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, None, None],
            "stim": [1, 1, 1, 2],
            "EPSP_amp": [1.0, 1.1, 1.05, 2.0],
            "EPSP_amp_norm": [50.0, 55.0, 52.5, 100.0],
        }
    )
    settings = {
        "rgb_EPSP_amp": "blue",
        "rgb_EPSP_slope": "red",
        "rgb_volley_amp": "green",
        "rgb_volley_slope": "orange",
    }
    existing = frozenset({"rec1 EPSP amp", "rec1 EPSP amp shade"})
    specs = plot_series.build_stim_aggregate_refresh_specs("rec1", df, settings, existing)
    assert len(specs) == 1
    assert specs[0].line_label == "rec1 EPSP amp"
    assert specs[0].shade_label == "rec1 EPSP amp shade"
    assert len(specs[0].x) == 2
    assert specs[0].sem is not None


def test_build_pp_recording_plot_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 0, 1],
            "stim": [1, 1, 2, 2],
            "EPSP_amp": [1.0, 2.0, 2.0, 4.0],
        }
    )
    specs = plot_series.build_pp_recording_plot_specs(
        df,
        "rec1",
        {"EPSP_amp": True},
        {"rgb_EPSP_amp": "blue", "rgb_EPSP_slope": "red", "rgb_volley_amp": "g", "rgb_volley_slope": "o"},
    )
    assert len(specs) == 2
    assert all(isinstance(s, plot_series.PpRecordingPlotSpec) for s in specs)
    assert {s.variant for s in specs} == {"raw", "norm"}
    assert specs[0].aspect == "EPSP_amp"
    assert len(specs[0].y) == 2


def test_build_stim_aggregate_plot_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, None, None],
            "stim": [1, 1, 1, 2],
            "EPSP_amp": [1.0, 1.1, 1.05, 2.0],
            "EPSP_amp_norm": [50.0, 55.0, 52.5, 100.0],
        }
    )
    settings = {
        "rgb_EPSP_amp": "blue",
        "rgb_EPSP_slope": "red",
        "rgb_volley_amp": "green",
        "rgb_volley_slope": "orange",
    }
    specs = plot_series.build_stim_aggregate_plot_specs(df, "rec1", settings)
    line_specs = [s for s in specs if s.line_label.endswith("EPSP amp")]
    assert len(line_specs) == 1
    assert line_specs[0].shade_label == "rec1 EPSP amp shade"
    assert line_specs[0].sem is not None
    assert len(line_specs[0].x) == 2


def test_build_io_recording_plot_specs():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 2],
            "stim": [1, 1, 1],
            "volley_amp": [1.0, 2.0, 3.0],
            "EPSP_amp": [2.0, 4.0, 6.0],
            "EPSP_amp_norm": [50.0, 100.0, 150.0],
        }
    )
    specs = plot_series.build_io_recording_plot_specs(
        df,
        "rec1",
        "vamp",
        "EPSPamp",
        force_through_zero=True,
    )
    assert len(specs) == 4
    scatter_raw = next(s for s in specs if s.label == "rec1 raw IO scatter")
    trend_raw = next(s for s in specs if s.label == "rec1 raw IO trendline")
    assert isinstance(scatter_raw, plot_series.IoScatterPlotSpec)
    assert isinstance(trend_raw, plot_series.IoTrendlinePlotSpec)
    assert len(scatter_raw.x) == 3
    assert len(trend_raw.x) == 2


def test_build_io_recording_plot_specs_skips_missing_norm():
    df = pd.DataFrame(
        {
            "sweep": [0, 1],
            "stim": [1, 1],
            "volley_amp": [1.0, 2.0],
            "EPSP_amp": [2.0, 4.0],
        }
    )
    specs = plot_series.build_io_recording_plot_specs(
        df,
        "rec1",
        "vamp",
        "EPSPamp",
        force_through_zero=False,
    )
    assert len(specs) == 2
    assert all("raw" in s.label for s in specs)


def test_io_scatter_xy_and_trendline():
    df = pd.DataFrame(
        {
            "sweep": [0, 1, 2],
            "stim": [1, 1, 1],
            "volley_amp": [1.0, 2.0, 3.0],
            "EPSP_amp": [2.0, 4.0, 6.0],
        }
    )
    xy = plot_series.io_scatter_xy(df, "vamp", "EPSPamp", variant="raw")
    assert xy is not None
    assert len(xy[0]) == 3
    line = plot_series.io_trendline_xy(df, "vamp", "EPSPamp", variant="raw", force_through_zero=True)
    assert line is not None
    assert len(line[0]) == 2


def test_stim_mode_suffix_to_col_keys():
    assert plot_series.STIM_MODE_SUFFIX_TO_COL["EPSP amp"] == "EPSP_amp"


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