"""Characterization tests for brainwash_ui.plot_model (no Qt/matplotlib display)."""

import numpy as np

from brainwash_ui import plot_model


def test_p_value_color_alpha_red_at_0001():
    color, alpha = plot_model.p_value_color_alpha(0.001)
    assert color == (1.0, 0.0, 0.0)
    assert alpha == 0.5


def test_p_value_color_alpha_yellow_at_05():
    color, alpha = plot_model.p_value_color_alpha(0.05)
    assert color[0] == 1.0
    assert color[1] == 1.0
    assert color[2] == 0.0


def test_significance_label_gradations():
    assert plot_model.significance_label(0.0005) == "***"
    assert plot_model.significance_label(0.005) == "**"
    assert plot_model.significance_label(0.03) == "*"
    assert plot_model.significance_label(0.2) == "ns"
    assert plot_model.significance_label(np.nan) == "ns"


def test_build_test_marker_specs_unpaired_two_aspects():
    results = [
        {
            "sweeps": [1, 2, 3],
            "p_amp": 0.005,
            "p_slope": 0.2,
        }
    ]
    specs = plot_model.build_test_marker_specs(
        results,
        test_type="t-test",
        t_variant="unpaired",
        wilcox_variant="paired",
        amp_view=True,
        slope_view=True,
        dark=False,
    )
    assert len(specs) == 2
    amp = next(s for s in specs if s.storage_pcol == "p_amp")
    slope = next(s for s in specs if s.storage_pcol == "p_slope")
    assert amp.axis == "ax1" and amp.label == "**"
    assert slope.axis == "ax2" and slope.label == "ns"
    assert amp.x == 2.0


def test_build_test_marker_specs_paired_single_marker():
    results = [
        {"sweeps": [1, 3], "p_amp": 0.0005},
        {"sweeps": [5, 7], "p_amp": 0.0005},
    ]
    specs = plot_model.build_test_marker_specs(
        results,
        test_type="t-test",
        t_variant="paired",
        wilcox_variant="paired",
        amp_view=True,
        slope_view=False,
        dark=True,
    )
    assert len(specs) == 1
    assert specs[0].x == 4.0
    assert specs[0].label == "***"
    assert specs[0].color == "white"


def test_build_group_line_specs_raw_only():
    specs = plot_model.build_group_line_specs("Group A", "EPSP_amp", "slice", include_norm=False)
    assert len(specs) == 1
    assert specs[0].display_label == "Group A EPSP amp mean"
    assert specs[0].storage_key == "Group A EPSP amp mean_slice"
    assert specs[0].variant == "raw"


def test_build_group_line_specs_with_norm():
    specs = plot_model.build_group_line_specs("G1", "EPSP_slope", "recording", include_norm=True)
    assert len(specs) == 2
    assert specs[0].variant == "raw"
    assert specs[1].display_label == "G1 EPSP slope norm"
    assert specs[1].storage_key == "G1 EPSP slope norm"
    assert specs[1].variant == "norm"


def test_io_rec_label_entry():
    entry = plot_model.io_rec_label_entry(rec_ID="r1", aspect="EPSP_amp", variant="raw")
    assert entry == {
        "rec_ID": "r1",
        "aspect": "EPSP_amp",
        "variant": "raw",
        "stim": None,
        "axis": "ax1",
        "x_mode": "io",
    }


def test_io_group_label_entry():
    entry = plot_model.io_group_label_entry(
        group_ID=2,
        aspect="EPSP_amp",
        variant="raw",
        axis="ax1",
        level="slice",
    )
    assert entry["x_mode"] == "io"
    assert entry["level"] == "slice"


def test_pp_group_bar_label_entry():
    entry = plot_model.pp_group_bar_label_entry(
        group_ID=1,
        aspect="EPSP_amp",
        level="recording",
        axis="ax1",
        rec_ID="r3",
        is_overlay=True,
    )
    assert entry["is_overlay"] is True
    assert entry["rec_ID"] == "r3"


def test_group_line_label_entry():
    entry = plot_model.group_line_label_entry(
        group_ID=3,
        aspect="EPSP_amp",
        variant="raw",
        axis="ax1",
        level="subject",
    )
    assert entry == {
        "group_ID": 3,
        "stim": None,
        "aspect": "EPSP_amp",
        "variant": "raw",
        "axis": "ax1",
        "x_mode": "sweep",
        "level": "subject",
    }


def test_level_storage_key_and_display_label():
    assert plot_model.level_storage_key("G1_amp", "subject") == "G1_amp_subject"
    assert plot_model.level_storage_key("G1_amp", "recording") == "G1_amp"
    assert plot_model.display_label_from_key("G1_amp_subject") == "G1_amp"


def test_output_axis_ylabels():
    labels = plot_model.output_axis_ylabels(experiment_type="io", io_output="EPSPamp", norm_epsP=False)
    assert labels.ax1_ylabel == "EPSP Amplitude (mV)"
    assert labels.ax2_ylabel == ""
    pp = plot_model.output_axis_ylabels(experiment_type="PP", io_output="", norm_epsP=False)
    assert pp.ax1_ylabel == "PPR Amp (%)"
    time_norm = plot_model.output_axis_ylabels(experiment_type="time", io_output="", norm_epsP=True)
    assert time_norm.ax2_ylabel == "Slope %"


def test_pp_reference_grid_y_values():
    assert plot_model.pp_reference_grid_y_values() == (1.0, 2.0, 3.0)


def test_output_axis_legend_map():
    dd_recs = {
        "rec1 EPSP amp": {"axis": "ax1", "line": "line1"},
        "rec1 marker": {"axis": "ax1", "line": "m1"},
    }
    dd_groups = {
        "G1 EPSP amp mean_subject": {"axis": "ax1", "line": "g1", "level": "subject"},
        "G2 EPSP amp mean_slice": {"axis": "ax1", "line": "g2", "level": "slice"},
    }
    legend = plot_model.output_axis_legend_map(
        dd_recs,
        dd_groups,
        axid="ax1",
        current_level="subject",
        include_groups=True,
    )
    assert "rec1 EPSP amp" in legend
    assert "rec1 marker" not in legend
    assert "G1 EPSP amp mean" in legend
    assert "G2 EPSP amp mean" not in legend


def test_output_legend_locations():
    assert plot_model.output_legend_locations(experiment_type="time", slope_only=False) == (
        "upper right",
        "lower right",
    )
    assert plot_model.output_legend_locations(experiment_type="io", slope_only=False) == (
        "lower right",
        "lower right",
    )
    assert plot_model.output_legend_locations(experiment_type="time", slope_only=True) == (
        "upper right",
        "upper right",
    )


def test_heatmap_helpers():
    assert plot_model.heatmap_axis_for_column("p_amp") == "ax1"
    assert plot_model.heatmap_axis_for_column("p_slope") == "ax2"
    assert plot_model.heatmap_axis_for_column("p_other") is None
    assert plot_model.heatmap_y_fraction("p_amp") == 0.92
    points = plot_model.significant_heatmap_points([1, 2, 3], [0.01, 0.2, np.nan])
    assert points == [(1.0, 0.01)]


def test_output_axis_visibility():
    assert plot_model.output_axis_y_visibility(amp_view=False, slope_view=False) == (False, False)
    assert plot_model.output_axis_y_visibility(amp_view=True, slope_view=False) == (True, False)
    assert plot_model.slope_yaxis_on_left(slope_only=True) is True