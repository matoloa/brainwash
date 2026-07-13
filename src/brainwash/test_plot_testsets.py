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


def test_sample_overlay_should_show():
    assert plot_testsets.sample_overlay_should_show({}) is False
    assert plot_testsets.sample_overlay_should_show({"g1": [1]}) is True