from __future__ import annotations

import pickle
from math import floor
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd
from matplotlib.ticker import AutoLocator, FixedLocator, FuncFormatter, Locator

from brainwash_ui import plot_drag

from ui_state_parts import ExperimentConfig, PlotSession, ProjectPersistedState, StatTestState

if TYPE_CHECKING:
    import matplotlib.axes
    import matplotlib.collections
    import matplotlib.lines
    import matplotlib.text


class TimeModeLocator(Locator):
    """A matplotlib Locator that calculates ticks based on converted time units."""

    def __init__(self, sweep_hz: float, divisor: float, bin_size: float = 1.0):
        self.sweep_hz = sweep_hz
        self.divisor = divisor
        self.bin_size = bin_size
        self._auto = AutoLocator()

    def set_axis(self, axis):
        self._auto.set_axis(axis)
        super().set_axis(axis)

    def tick_values(self, vmin, vmax):
        tmin = (vmin * self.bin_size) / self.sweep_hz / self.divisor
        tmax = (vmax * self.bin_size) / self.sweep_hz / self.divisor
        time_ticks = self._auto.tick_values(tmin, tmax)
        return [(t * self.divisor * self.sweep_hz) / self.bin_size for t in time_ticks]

    def __call__(self):
        vmin, vmax = self.axis.get_view_interval()
        return self.tick_values(vmin, vmax)


class UIstate:
    """Application state: project (persisted), experiment, stat_test, plot (session), darkmode (bw_cfg)."""

    project: ProjectPersistedState
    experiment: ExperimentConfig
    stat_test: StatTestState
    plot: PlotSession
    darkmode: bool

    def __init__(self):
        self.project = ProjectPersistedState()
        self.experiment = ExperimentConfig()
        self.stat_test = StatTestState()
        self.plot = PlotSession()
        self.darkmode = False
        self.reset()

    def reset(self):
        print("UIstate: reset")
        self.project.reset()
        self.experiment.reset()
        self.stat_test.reset()
        self.plot.reset()
        self._init_default_dict_t()

    def _init_default_dict_t(self):
        t_volley_slope_width = 0.0003
        t_epsp_slope_width = 0.0007
        resolution = 0.0001
        self.project.default_dict_t = {
            "stim": 0,
            "t_stim": 0.0,
            "t_stim_method": "max prim",
            "t_stim_params": "NA",
            "amp_zero": 0.0,
            "t_volley_slope_width": t_volley_slope_width,
            "t_volley_slope_halfwidth": self.floor_to_resolution(t_volley_slope_width / 2, resolution),
            "t_volley_slope_start": 0.0,
            "t_volley_slope_end": 0.0,
            "t_volley_slope_method": "default",
            "t_volley_slope_params": "NA",
            "volley_slope_mean": 0.0,
            "t_volley_amp": 0.0,
            "t_volley_amp_halfwidth": 0.0,
            "t_volley_amp_method": "default",
            "t_volley_amp_params": "NA",
            "volley_amp_mean": 0.0,
            "t_VEB": 0.0,
            "t_VEB_method": 0,
            "t_VEB_params": 0,
            "t_EPSP_slope_width": t_epsp_slope_width,
            "t_EPSP_slope_halfwidth": self.floor_to_resolution(t_epsp_slope_width / 2, resolution),
            "t_EPSP_slope_start": 0.0,
            "t_EPSP_slope_end": 0.0,
            "t_EPSP_slope_method": "default",
            "t_EPSP_slope_params": "NA",
            "t_EPSP_amp": 0.0,
            "t_EPSP_amp_halfwidth": 0.0,
            "t_EPSP_amp_method": "default",
            "t_EPSP_amp_params": "NA",
            "norm_output_from": 0,
            "norm_output_to": 0,
        }

    def setMargins(self, axe, pixels=10):
        p = self.plot
        p.x_margin = axe.transData.inverted().transform((pixels, 0))[0] - axe.transData.inverted().transform((0, 0))[0]
        p.y_margin = axe.transData.inverted().transform((0, pixels))[1] - axe.transData.inverted().transform((0, 0))[1]

    def setMarginsAxm(self, axm, pixels=10):
        p = self.plot
        p.mean_x_margin = axm.transData.inverted().transform((pixels, 0))[0] - axm.transData.inverted().transform((0, 0))[0]
        p.mean_y_margin = axm.transData.inverted().transform((0, pixels))[1] - axm.transData.inverted().transform((0, 0))[1]

    def updateDragZones(self, aspect=None, x=None, y=None):
        p = self.plot
        if aspect is None:
            assert p.mouseover_action is not None
            assert p.mouseover_plot is not None
            aspect = p.mouseover_action
            x = plot_drag.artist_xdata(p.mouseover_plot[0])
            y = plot_drag.artist_ydata(p.mouseover_plot[0])
        if aspect.startswith("EPSP slope"):
            self.updateSlopeZone("EPSP", x, y)
        elif aspect.startswith("volley slope"):
            self.updateSlopeZone("volley", x, y)

    def updatePointDragZone(self, aspect=None, x=None, y=None):
        p = self.plot
        if aspect is None:
            assert p.mouseover_action is not None
            assert p.mouseover_blob is not None
            aspect = p.mouseover_action
            x, y = p.mouseover_blob.get_offsets()[0].tolist()  # type: ignore[index, union-attr]
        if aspect == "EPSP amp move":
            self.updateAmpZone("EPSP", x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone("volley", x, y)

    def updateSlopeZone(self, type, x, y):
        p = self.plot
        slope_start, slope_end, move_zone, resize_zone = plot_drag.slope_drag_state(
            x,
            y,
            x_margin=p.x_margin,
            y_margin=p.y_margin,
        )
        setattr(p, f"{type}_slope_start_xy", slope_start)
        setattr(p, f"{type}_slope_end_xy", slope_end)
        zone_move = getattr(p, f"{type}_slope_move_zone")
        zone_move.clear()
        zone_move.update(move_zone)
        zone_resize = getattr(p, f"{type}_slope_resize_zone")
        zone_resize.clear()
        zone_resize.update(resize_zone)

    def updateAmpZone(self, type, x, y):
        p = self.plot
        setattr(p, f"{type}_amp_xy", (x, y))
        zone = getattr(p, f"{type}_amp_move_zone")
        zone.clear()
        zone.update(plot_drag.amp_move_zone(x, y, x_margin=p.x_margin, y_margin=p.y_margin))

    def get_recSet(self):
        return set(value["rec_ID"] for value in self.plot.dict_rec_labels.values())

    def get_groupSet(self, level=None):
        if level is None:
            return set(value["group_ID"] for value in self.plot.dict_group_labels.values())
        return set(
            value["group_ID"]
            for value in self.plot.dict_group_labels.values()
            if value.get("level") == level or value.get("level") is None
        )

    @property
    def x_axis(self) -> str:
        exp = self.experiment.experiment_type
        if exp in ("time", "timestamp"):
            return "time"
        if exp == "sweep":
            return "sweep"
        if exp == "train":
            return "stim"
        if exp == "io":
            return "io"
        return "sweep"

    @staticmethod
    def time_axis_unit(max_seconds: float) -> tuple:
        if max_seconds < 120:
            return (1.0, "s")
        if max_seconds < 7200:
            return (60.0, "min")
        return (3600.0, "h")

    def apply_time_axis_params(self, *, n_bins: float, sweep_hz: float, bin_size: float = 1.0) -> float:
        """Set time-mode conversion (Hz, bin size, unit label) from bin count and sweep rate.

        x-data stay in sweep/bin index; locators convert to Time (s|min|h).
        Returns max duration in seconds (for tests / callers).
        """
        hz = float(sweep_hz)
        if not np.isfinite(hz) or hz <= 0:
            raise ValueError(f"apply_time_axis_params: sweep_hz must be positive finite, got {sweep_hz!r}")
        bs = float(bin_size) if np.isfinite(bin_size) and float(bin_size) > 0 else 1.0
        n = max(float(n_bins), 1.0)
        self.plot._time_sweep_hz = hz
        self.plot._time_bin_size = bs
        max_seconds = (n * bs) / hz
        self.plot._time_divisor, self.plot._time_unit_label = self.time_axis_unit(max_seconds)
        return max_seconds

    def x_axis_xlabel(self) -> str:
        mode = self.x_axis
        if mode == "time":
            return f"Time ({self.plot._time_unit_label})"
        if mode == "io":
            io_input = self.experiment.io_input
            if io_input == "vamp":
                return "Volley Amplitude (mV)"
            if io_input == "vslope":
                return "Volley Slope (mV/ms)"
            return "Stimulus"
        return {"sweep": "Sweep", "stim": "Stim"}.get(mode, "Sweep")

    def x_axis_xlim(self, prow, dft=None) -> tuple:
        if self.experiment.experiment_type == "PP":
            has_groups = False
            max_x = 1.5
            for key, val in self.plot.dict_group_show.items():
                if "PPR" in key and hasattr(val["line"], "patches"):
                    has_groups = True
                    try:
                        max_x = max(max_x, val["line"].patches[0].get_x() + val["line"].patches[0].get_width() / 2)
                    except Exception:
                        pass
            if has_groups:
                return (0.5, max_x)
            has_recs = False
            rec_x_positions = []
            for key, val in self.plot.dict_rec_show.items():
                if "PPR" in key and "marker" not in key and val.get("line") and val["line"].get_visible():
                    has_recs = True
                    try:
                        rec_x_positions.extend(plot_drag.artist_xdata(val["line"]).tolist())
                    except Exception:
                        pass
            if has_recs:
                if rec_x_positions:
                    return (min(rec_x_positions) - 0.5, max(rec_x_positions) + 0.5)
                return (0.5, 4.5)
            return (0.5, 1.5)

        mode = self.x_axis
        if mode == "sweep":
            from math import ceil

            n = prow["sweeps"]
            if pd.notna(prow.get("bin_size")):
                n = ceil(n / prow["bin_size"])
            return (0, n)
        if mode == "time":
            from math import ceil

            if pd.isna(prow["sweep_hz"]):
                raise ValueError("x_axis_xlim called in time mode but sweep_hz is NaN")
            n = prow["sweeps"]
            bin_size = prow.get("bin_size")
            if pd.notna(bin_size):
                n = ceil(n / bin_size)
            else:
                bin_size = 1.0
            self.apply_time_axis_params(n_bins=n, sweep_hz=prow["sweep_hz"], bin_size=bin_size)
            return (0, n)
        if mode == "stim":
            if dft is not None and len(dft) > 0 and "stim" in dft.columns:
                stim_min = int(dft["stim"].min())
                stim_max = int(dft["stim"].max())
            else:
                stims = prow["stims"]
                if pd.isna(stims):
                    raise ValueError("x_axis_xlim called in stim mode but prow['stims'] is NaN and no dft was provided")
                stim_min = 1
                stim_max = int(stims)
                if stim_min > stim_max:
                    stim_max = int(stims)
            self.plot._stim_tick_locs = list(range(stim_min, stim_max + 1))
            return (stim_min - 0.5, stim_max + 0.5)
        if mode == "io":
            x_min, x_max = float("inf"), float("-inf")
            lines_to_check = list(self.plot.dict_rec_labels.values())
            lines_to_check.extend(self.plot.dict_group_labels.values())
            for info in lines_to_check:
                if info.get("x_mode") == "io" and info.get("line") is not None:
                    try:
                        line = info["line"]
                        if not line.get_visible():
                            continue
                        if hasattr(line, "get_offsets"):
                            offsets = line.get_offsets()
                            if len(offsets) > 0:
                                x_data = offsets[:, 0]
                                x_min = min(x_min, np.nanmin(x_data))
                                x_max = max(x_max, np.nanmax(x_data))
                        elif hasattr(line, "get_xdata"):
                            x_data = plot_drag.artist_xdata(line)
                            if x_data.size > 0:
                                x_min = min(x_min, np.nanmin(x_data))
                                x_max = max(x_max, np.nanmax(x_data))
                    except Exception:
                        pass
            if x_min != float("inf") and x_max != float("-inf"):
                pad = abs(x_max) * 0.1 or 0.1
                return (0, x_max + pad)
            return (0, 1)
        raise ValueError(f"Unknown x_axis mode: {mode!r}")

    def x_axis_locator(self):
        mode = self.x_axis
        p = self.plot
        if mode == "time":
            return TimeModeLocator(p._time_sweep_hz, p._time_divisor, p._time_bin_size)
        if mode == "stim":
            return FixedLocator(p._stim_tick_locs)
        return AutoLocator()

    def x_axis_formatter(self):
        if self.x_axis == "time":
            p = self.plot

            def _fmt(val, _pos):
                t = (val * p._time_bin_size) / p._time_sweep_hz / p._time_divisor
                return f"{t:g}"

            return FuncFormatter(_fmt)
        return FuncFormatter(lambda val, _pos: f"{val:g}")

    def x_axis_values(self, dfoutput, prow):
        mode = self.x_axis
        if mode in ("sweep", "time"):
            mask = dfoutput["sweep"].notna()
            return dfoutput.loc[mask, "sweep"]
        if mode == "stim":
            mask = dfoutput["sweep"].isna()
            return dfoutput.loc[mask, "stim"]
        if mode == "io":
            mask = dfoutput["sweep"].notna()
            col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(
                self.experiment.io_input, "volley_amp"
            )
            if col in dfoutput.columns:
                return dfoutput.loc[mask, col]
            return pd.Series(dtype=float)
        raise ValueError(f"Unknown x_axis mode: {mode!r}")

    def get_state(self):
        try:
            state = {}
            state.update(self.project.to_state_dict())
            state.update(self.experiment.to_state_dict())
            state.update(self.stat_test.to_state_dict())
            return state
        except AttributeError:
            self.reset()
            return self.get_state()

    def set_state(self, state):
        zoom_defaults = self.project.zoom.copy()
        self.experiment.apply_state_dict(state)
        self.stat_test.apply_state_dict(state)
        self.project.apply_state_dict(state, zoom_defaults=zoom_defaults)

    def load_cfg(self, projectfolder, bw_version, force_reset=False):
        path_pkl = projectfolder / "cfg.pkl"
        if path_pkl.exists() and not force_reset:
            with open(path_pkl, "rb") as f:
                data = pickle.load(f)
            if data is not None:
                self.set_state(data)
                if bw_version != self.project.version:
                    print(f"Warning: cfg.pkl is from {self.project.version} - current version is {bw_version}")
            else:
                print("Warning: cfg.pkl is empty or corrupt, resetting to defaults")
                self.reset()
                self.save_cfg(projectfolder, bw_version)
        else:
            self.reset()
            self.save_cfg(projectfolder, bw_version)

    def save_cfg(self, projectfolder, bw_version=None):
        path_pkl = projectfolder / "cfg.pkl"
        data = self.get_state()
        if bw_version is not None:
            data["version"] = bw_version
        if not path_pkl.parent.exists():
            path_pkl.parent.mkdir(parents=True, exist_ok=True)
        with open(path_pkl, "wb") as f:
            pickle.dump(data, f)

    def ampView(self):
        if self.experiment.experiment_type == "io":
            return True
        show = self.project.checkBox
        return show.get("EPSP_amp", False) or show.get("volley_amp", False) or show.get("volley_amp_mean", False)

    def slopeView(self):
        if self.experiment.experiment_type == "io":
            return False
        show = self.project.checkBox
        return show.get("EPSP_slope", False) or show.get("volley_slope", False) or show.get("volley_slope_mean", False)

    def slopeOnly(self):
        if self.experiment.experiment_type == "io":
            return False
        show = self.project.checkBox
        has_slope = show.get("EPSP_slope", False) or show.get("volley_slope", False) or show.get("volley_slope_mean", False)
        has_amp = show.get("EPSP_amp", False) or show.get("volley_amp", False) or show.get("volley_amp_mean", False)
        return has_slope and not has_amp

    def anyView(self):
        if self.experiment.experiment_type == "io":
            return True
        return any(self.project.checkBox.values())

    def floor_to_resolution(self, value, resolution):
        decimals = abs(len(str(resolution).split(".")[-1]))
        floored = floor(value / resolution) * resolution
        return round(max(floored, resolution), decimals)


if __name__ == "__main__":
    uistate = UIstate()
    assert uistate.anyView() is True
    uistate.project.checkBox["EPSP_slope"] = False
    assert uistate.anyView() is False
    print("test passed")