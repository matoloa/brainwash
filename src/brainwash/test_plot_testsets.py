from brainwash_ui import plot_testsets
from test_statistics_fixtures import make_dd_testsets


def test_testset_span_specs_visible_only():
    dd = make_dd_testsets("TS1", "TS2")
    dd["TS2"]["show"] = False
    dd["TS1"]["sweeps"] = [2, 3, 4]
    specs = plot_testsets.testset_span_specs(dd)
    assert len(specs) == 2
    assert specs[0].set_id == "TS1"
    assert specs[0].start == 2.0
    assert specs[0].end == 5.0


def test_sample_overlay_linestyle_and_trace_specs():
    import pandas as pd

    assert plot_testsets.sample_overlay_linestyle(0) == "-"
    assert plot_testsets.sample_overlay_linestyle(2) == ":"
    dd_groups = {"1": {"show": True, "color": "red"}}
    dd_testset = {"T1": {"show": True}}
    df = pd.DataFrame({"time": [0.0, 0.01, 0.02], "voltage": [1.0, 2.0, 3.0], "stim": [1, 1, 1]})
    specs = plot_testsets.build_sample_overlay_trace_specs(
        dd_groups,
        dd_testset,
        {1: {"T1": df}},
        filter_col="voltage",
    )
    assert len(specs) == 1
    assert specs[0].color == "red"
    ylim = plot_testsets.sample_overlay_ylim(specs)
    assert ylim is not None


def test_sample_overlay_should_show():
    assert plot_testsets.sample_overlay_should_show({}) is False
    assert plot_testsets.sample_overlay_should_show({"g1": [1]}) is True