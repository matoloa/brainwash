"""Time-axis unit conversion when no recording is selected (groups-only)."""

import numpy as np
import pandas as pd

from ui_state_classes import TimeModeLocator, UIstate


def test_apply_time_axis_params_600_sweeps_at_0p2hz_is_50_min():
    u = UIstate()
    # 600 sweeps @ 0.2 Hz = 3000 s = 50 min → unit should be "min"
    max_s = u.apply_time_axis_params(n_bins=600, sweep_hz=0.2, bin_size=1.0)
    assert abs(max_s - 3000.0) < 1e-9
    assert u.plot._time_unit_label == "min"
    assert u.plot._time_divisor == 60.0
    assert u.x_axis_xlabel() == "Time (min)"
    # Tick conversion: sweep index 600 → 50 min
    loc = TimeModeLocator(u.plot._time_sweep_hz, u.plot._time_divisor, u.plot._time_bin_size)
    # formatter path: (val * bin) / hz / divisor
    t_display = (600.0 * u.plot._time_bin_size) / u.plot._time_sweep_hz / u.plot._time_divisor
    assert abs(t_display - 50.0) < 1e-9


def test_default_hz_one_mislabels_as_seconds():
    """Characterization of the bug: default plot session uses hz=1 → 600 's'."""
    u = UIstate()
    assert u.plot._time_sweep_hz == 1.0
    assert u.plot._time_unit_label == "s"
    t_wrong = (600.0 * u.plot._time_bin_size) / u.plot._time_sweep_hz / u.plot._time_divisor
    assert abs(t_wrong - 600.0) < 1e-9


def test_time_axis_unit_thresholds():
    assert UIstate.time_axis_unit(60) == (1.0, "s")
    assert UIstate.time_axis_unit(119) == (1.0, "s")
    assert UIstate.time_axis_unit(120) == (60.0, "min")
    assert UIstate.time_axis_unit(7199) == (60.0, "min")
    assert UIstate.time_axis_unit(7200) == (3600.0, "h")


def test_infer_meta_from_groups_helper_via_fake_host():
    """Lightweight stand-in for GraphCoordinatorMixin._infer_time_axis_meta_from_groups."""

    class Host:
        def __init__(self):
            self.dd_groups = {
                1: {"show": True, "rec_IDs": ["r1", "r2"]},
                2: {"show": False, "rec_IDs": ["r3"]},
            }
            self._df = pd.DataFrame(
                {
                    "ID": ["r1", "r2", "r3"],
                    "sweep_hz": [0.2, 0.2, 1.0],
                    "bin_size": [np.nan, np.nan, 5],
                }
            )

        def get_df_project(self):
            return self._df

    # Bind the real method for the test without Qt graph mixin init
    from ui_graph import GraphCoordinatorMixin

    host = Host()
    hz, bs = GraphCoordinatorMixin._infer_time_axis_meta_from_groups(host)
    assert abs(hz - 0.2) < 1e-9
    assert bs == 1.0  # no finite bin_size on shown recs
