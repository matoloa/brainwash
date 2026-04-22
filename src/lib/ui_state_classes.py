from __future__ import annotations

import pickle
from math import ceil, floor
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd
from matplotlib.ticker import AutoLocator, FixedLocator, FuncFormatter, Locator

if TYPE_CHECKING:
    import matplotlib.axes
    import matplotlib.collections
    import matplotlib.lines
    import matplotlib.text


class TimeModeLocator(Locator):
    """A matplotlib Locator that calculates ticks based on converted time units
    rather than raw sweep numbers, so that ticks fall on clean time intervals."""

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
    # --- Axes (not persisted) ---
    axm: Optional[matplotlib.axes.Axes]
    axe: Optional[matplotlib.axes.Axes]
    ax1: Optional[matplotlib.axes.Axes]
    ax2: Optional[matplotlib.axes.Axes]

    # --- Recording selection (not persisted) ---
    float_sweep_duration_max: Optional[float]
    df_rec_select_data: Optional[pd.DataFrame]
    df_rec_select_time: Optional[pd.DataFrame]
    df_recs2plot: Optional[pd.DataFrame]

    # --- Meangraph mouseover (not persisted) ---
    mean_mouseover_stim_select: Optional[str]
    mean_x_margin: Optional[float]
    mean_y_margin: Optional[float]

    # --- Eventgraph mouseover (not persisted) ---
    mouseover_action: Optional[str]
    mouseover_plot: Optional[list[matplotlib.lines.Line2D]]
    mouseover_blob: Optional[matplotlib.collections.PathCollection]
    mouseover_out: Optional[list[matplotlib.lines.Line2D]]
    x_margin: Optional[float]
    y_margin: Optional[float]
    x_on_click: Optional[float]
    x_drag_last: Optional[float]
    x_drag: Optional[float]
    dft_temp: Optional[pd.DataFrame]

    # --- Eventgraph mouseover coordinates (not persisted) ---
    EPSP_amp_xy: Optional[tuple[float, float]]
    EPSP_slope_start_xy: Optional[tuple[float, float]]
    EPSP_slope_end_xy: Optional[tuple[float, float]]
    volley_amp_xy: Optional[tuple[float, float]]
    volley_slope_start_xy: Optional[tuple[float, float]]
    volley_slope_end_xy: Optional[tuple[float, float]]

    # --- Outputgraph mouseover (not persisted) ---
    last_out_x_idx: Optional[int]
    ghost_sweep: Optional[matplotlib.lines.Line2D]
    ghost_label: Optional[matplotlib.text.Text]

    # --- Experiment type (persisted) ---
    experiment_type: str  # "time", "sweep", "timestamp", "train", "io", "PP"
    io_input: str
    io_output: str

    # --- Global bw_cfg (not persisted in project cfg.pkl) ---
    darkmode: bool

    def __init__(self):
        self.reset()

    def reset(self):  # (re)set all persisted states
        print("UIstate: reset")
        self.version = "0.0.0"
        self.colors = [
            "#808080",
            "#00BFFF",
            "#008000",
            "#FF8080",
            "#006666",
            "#9ACD32",
            "#D2691E",
            "#FFD700",
            "#0000FF",
        ]
        self.splitter = {
            "h_splitterMaster": [0.105, 0.04, 0.855, 200],
            "v_splitterGraphs": [0.2, 0.5, 0.3],
        }
        self.viewTools = {  # these are cycled by uisub.connectUIstate; framename: [title, visible]
            "frameToolStim": ["Stim detection", True],
            "frameToolSweeps": ["Sweep selection", True],
            "frameToolTag": ["Tag selection", True],
            "frameToolBin": ["Binning", True],
            "frameToolType": ["Experiment type", True],
            "frameToolFilter": ["Filter", True],
            "frameToolYscale": ["Y scaling", True],
            "frameToolAspect": ["Aspect toggles", True],
            "frameToolAspectSlope": ["Slope width", False],
            "frameToolAspectAmp": ["Amplitude width", False],
        }
        self.checkBox = {  # these are cycled by uisub.connectUIstate; maintain format!
            "EPSP_amp": True,
            "EPSP_slope": True,
            "volley_amp": False,
            "volley_amp_mean": True,  # display mean of volley_amp in output
            "volley_slope": False,
            "volley_slope_mean": True,  # display mean of volley_slope in output
            "splitOddEven": False,  # split parsed file into odd _1 and even _2 recordings
            "timepoints_per_stim": False,  # allow setting (non-uniform) timepoints per stim
            "output_ymin0": True,  # set output y-axis minimum to 0
            # break these out to separate mod-class?
            "norm_EPSP": False,  # show normalized EPSPs (they're always calculated)
            "paired_stims": False,  # Recs are paired: output per pair is Intervention / Control
            "io_trendline": False,
            "io_force0": False,
        }
        self.lineEdit = {  # storage of user input; used to update df_t
            "split_at_time": 0.0,  # in s (SI). User enters ms; converted at input in editImportOptions.
            "import_gain": 1.0,
            "norm_EPSP_from": 0,
            "norm_EPSP_to": 0,
            "EPSP_amp_halfwidth_ms": 0,  # in ms here (visible to user). NB: in s in df_t!
            "volley_amp_halfwidth_ms": 0,  # in ms here (visible to user). NB: in s in df_t!
            "EPSP_slope_width_ms": 0,  # in ms here (visible to user). NB: in s in df_t!
            "volley_slope_width_ms": 0,  # in ms here (visible to user). NB: in s in df_t!
            "savgol_window": 9,
            "savgol_poly": 3,
        }
        self.settings = {
            "event_start": -0.005,  # in relation to current t_stim
            "event_end": 0.05,
            "precision": 4,  # TODO: fix hardcoded precision
            "dft_width_proportion": 0.2,
            "filter": "voltage",  # filter to show in event graph; default 'voltage' column
            # colors and alpha
            "rgb_EPSP_amp": (0.2, 0.2, 1),
            "rgb_EPSP_slope": (0.5, 0.5, 1),
            "rgb_volley_amp": (1, 0.2, 1),
            "rgb_volley_slope": (1, 0.5, 1),
            "alpha_mark": 0.4,
            "alpha_line": 1,
            "journal_export": None,
        }
        self.zoom = {
            "mean_xlim": (0, 1),
            "mean_ylim": (-1, 1),
            "event_xlim": (-0.0012, 0.030),
            "event_ylim": (-0.001, 0.0002),
            "output_xlim": (0, None),
            "output_ax1_ylim": (0, 3.2),
            "output_ax2_ylim": (0, 1.2),
        }
        self.experiment_type = "time"  # "time", "sweep", "timestamp", "train", "io", "PP"
        self.io_input = "vamp"
        self.io_output = "EPSPamp"
        self._time_divisor = 1.0  # set by x_axis_xlim when mode == "time"
        self._time_unit_label = "s"  # set by x_axis_xlim when mode == "time"
        self._time_sweep_hz = 1.0  # set by x_axis_xlim when mode == "time"
        self._time_bin_size = 1.0  # set by x_axis_xlim when mode == "time"
        self._stim_tick_locs: list[int] = []  # set by x_axis_xlim when mode == "stim"
        self.showTimetable = False
        self.showHeatmap = False
        self.dict_heatmap = {}

        # default_dict_t is used to store timepoints and their parameters
        # only assign full width as we normally use odd length in discrete index for clarity
        t_volley_slope_width = 0.0003  # default width for volley slope, in seconds
        t_EPSP_slope_width = 0.0007  # default width for EPSP
        resolution = 0.0001  # resolution in seconds TODO: hardcoded for 10KHz
        t_volley_slope_halfwidth = self.floor_to_resolution(t_volley_slope_width / 2, resolution)
        t_EPSP_slope_halfwidth = self.floor_to_resolution(t_EPSP_slope_width / 2, resolution)
        # print(f"UIstate: t_volley_slope_halfwidth={t_volley_slope_halfwidth}, t_EPSP_slope_halfwidth={t_EPSP_slope_halfwidth}")
        self.default_dict_t = {  # default values for df_t(imepoints)
            # TODO: rework and harmonize parameters
            # suggested format: feature-[param, value]
            # example: dict_param = {volley_slope-width: 3}
            # example: dict_values = {volley_slope-value: -0.3254}
            "stim": 0,
            "t_stim": 0.0,
            "t_stim_method": "max prim",
            "t_stim_params": "NA",
            "amp_zero": 0.0,
            "t_volley_slope_width": t_volley_slope_width,
            "t_volley_slope_halfwidth": t_volley_slope_halfwidth,
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
            "t_VEB": 0.0,  # Deprecated
            "t_VEB_method": 0,  # Deprecated
            "t_VEB_params": 0,  # Deprecated
            "t_EPSP_slope_width": t_EPSP_slope_width,
            "t_EPSP_slope_halfwidth": t_EPSP_slope_halfwidth,
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

        # Do NOT persist these
        self.pushButtons = {  # these are cycled by uisub.connectUIstate; buttonname: methodname
            # stim detection
            "pushButton_stim_add": "triggerStimAdd",
            "pushButton_stim_remove": "triggerStimRemove",
            # sweep selection
            "pushButton_sweeps_even": "trigger_set_sweeps_even",
            "pushButton_sweeps_odd": "trigger_set_sweeps_odd",
            # sweep comparison
            "pushButton_compare": "triggerCompare",
            "pushButton_sample": "triggerSample",
        }
        self.x_select = {  # selected ranges on mean- and output graphs
            # start and end: current drag operation; None if not dragging
            "mean_start": None,
            "mean_end": None,
            "output": set(),  # set of x indices selected in output graph
            "output_start": None,
            "output_end": None,
        }

        # darkmode is owned by bw_cfg.yaml, not the project cfg.pkl; set by get_bw_cfg()
        self.axm = None  # axis of mean graph (top)
        self.axe = None  # axis of event graph (middle)
        self.ax1 = None  # axis of output for amplitudes (bottom graph)
        self.ax2 = None  # axis of output for slopes (bottom graph)
        self.frozen = False  # True if ui is frozen

        self.list_idx_recs2preload = []  # list of indices in uisub.df_project for freshly parsed recordings; used by uisub.graphPreload()
        self.list_idx_select_recs = []  # list of selected indices in uisub.tableProj
        self.list_idx_select_stims = [0]  # list of selected indices in uisub.tableStim; default to first
        self.float_sweep_duration_max = (
            None  # maximum sweep duration of all recordings in df_recs2plot; used to set x-limits of eventgraph. Updated on rec selection change.
        )

        # Liabilities: TODO: are these properly updated/cleared when selections change?
        self.df_rec_select_data = (
            None  # df_filtered of ONE selected recording (if more than one selected, None), used to plot means of selected sweeps in eventgraph
        )
        self.df_rec_select_time = None  # dft of ONE selected recording (if more than one selected, None), used to offset mean sweeps in eventgraph
        self.df_recs2plot = None  # df_project copy, filtered to selected AND parsed recordings (or all parsed, if none are selected)

        # Plotted lines and fills
        self.dict_rec_labels = {}  # dict of dicts of all plotted recordings. {key:label(str): {rec_ID: str, stim: int, aspect: str, variant: str ("raw"|"norm"|None), axis: str, line: 2DlineObject}}
        self.dict_rec_show = {}  # subset of dict_rec_labels containing only currently visible entries

        # Groups (mean of recs)
        self.dict_group_labels = {}  # dict of dicts of all plotted groups: {key:label(str): {group_ID: int, stim: int, aspect: str, variant: str ("raw"|"norm"), axis: str, line: 2DlineObject, fill: 2DfillObject}}
        self.dict_group_show = {}  # subset of dict_group_labels containing only currently visible entries

        # Mouseover variables
        # Meangraph Mouseover variables
        self.mean_mouseover_stim_select = None  # name of stim that will be selected if clicked
        self.mean_stim_x_ranges = {}  # dict: stim_num: (x_start, x_end)
        self.mean_x_margin = None  # for mouseover detection boundaries of clickable points
        self.mean_y_margin = None  # for mouseover detection boundaries of clickable points

        # Eventgraph Mouseover variables
        self.mouseover_action = None  # name of action to take if clicked at current mouseover: EPSP amp move, EPSP slope move/resize, volley amp move, volley slope move/resize
        self.mouseover_plot = None  # plot of tentative EPSP slope
        self.mouseover_blob = None  # scatterplot indicating mouseover of dragable point; move point or resize slope
        self.x_margin = None  # for mouseover detection boundaries of clickable points
        self.y_margin = None  # for mouseover detection boundaries of clickable points
        self.x_on_click = None  # x-value closest to mousebutton down
        self.x_drag_last = None  # last x-value within the same dragging event; prevents needless update when holding drag still
        self.x_drag = None  # x-value of current dragging
        self.dragging = False  # True if dragging; allows right-click to cancel drag
        self.mouseover_out = None  # output of dragged aspect
        self.dft_temp = None  # temporary dft, updated during dragging, replaces dft at release

        # Eventgraph Mouseover coordinates, for plotting. Set on row selection.
        self.EPSP_amp_xy = None  # x,y
        self.EPSP_slope_start_xy = None  # x,y
        self.EPSP_slope_end_xy = None  # x,y
        self.volley_amp_xy = None  # x,y
        self.volley_slope_start_xy = None  # x,y
        self.volley_slope_end_xy = None  # x,y

        # Eventgraph Mouseover clickzones: coordinates including margins. Set on row selection.
        self.EPSP_amp_move_zone = {}  # dict: key=x,y, value=start,end.
        self.EPSP_slope_move_zone = {}  # dict: key=x,y, value=start,end.
        self.EPSP_slope_resize_zone = {}  # dict: key=x,y, value=start,end.
        self.volley_amp_move_zone = {}  # dict: key=x,y, value=start,end.
        self.volley_slope_move_zone = {}  # dict: key=x,y, value=start,end.
        self.volley_slope_resize_zone = {}  # dict: key=x,y, value=start,end.

        # OutputGraph Mouseover variables
        self.last_out_x_idx = None
        self.ghost_sweep = None
        self.ghost_label = None

    def setMargins(self, axe, pixels=10):  # set margins for mouseover detection
        self.x_margin = axe.transData.inverted().transform((pixels, 0))[0] - axe.transData.inverted().transform((0, 0))[0]
        self.y_margin = axe.transData.inverted().transform((0, pixels))[1] - axe.transData.inverted().transform((0, 0))[1]

    def setMarginsAxm(self, axm, pixels=10):  # set pixel-based margins for axm mouseover detection
        self.mean_x_margin = axm.transData.inverted().transform((pixels, 0))[0] - axm.transData.inverted().transform((0, 0))[0]
        self.mean_y_margin = axm.transData.inverted().transform((0, pixels))[1] - axm.transData.inverted().transform((0, 0))[1]

    def updateDragZones(self, aspect=None, x=None, y=None):
        # print(f"*** updateDragZones: {aspect} {x} {y}")
        if aspect is None:
            # Fall back to stored state when called without arguments
            assert self.mouseover_action is not None, "updateDragZones: called with no aspect and mouseover_action is not set"
            assert self.mouseover_plot is not None, "updateDragZones: called with no x/y and mouseover_plot is not set"
            aspect = self.mouseover_action
            x = self.mouseover_plot[0].get_xdata()
            y = self.mouseover_plot[0].get_ydata()

        # Use the local `aspect` variable — self.mouseover_action may still be None
        # if the no-args path was taken and mouseover_action had not been set yet.
        if aspect.startswith("EPSP slope"):
            self.updateSlopeZone("EPSP", x, y)
        elif aspect.startswith("volley slope"):
            self.updateSlopeZone("volley", x, y)

    def updatePointDragZone(self, aspect=None, x=None, y=None):
        # print(f"*** updatePointDragZone: {aspect} {x} {y}")
        if aspect is None:
            # Fall back to stored state when called without arguments
            assert self.mouseover_action is not None, "updatePointDragZone: called with no aspect and mouseover_action is not set"
            assert self.mouseover_blob is not None, "updatePointDragZone: called with no x/y and mouseover_blob is not set"
            aspect = self.mouseover_action
            x, y = self.mouseover_blob.get_offsets()[0].tolist()  # type: ignore[index, union-attr]

        if aspect == "EPSP amp move":
            self.updateAmpZone("EPSP", x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone("volley", x, y)

    def updateSlopeZone(self, type, x, y):
        # print(f"*** - updateSlopeZone: {type} {x} {y}")
        slope_start = x[0], y[0]
        slope_end = x[-1], y[-1]
        x_window = min(x), max(x)
        y_window = min(y), max(y)

        setattr(self, f"{type}_slope_start_xy", slope_start)
        setattr(self, f"{type}_slope_end_xy", slope_end)
        getattr(self, f"{type}_slope_move_zone")["x"] = (
            x_window[0] - self.x_margin,
            x_window[-1] + self.x_margin,
        )
        getattr(self, f"{type}_slope_move_zone")["y"] = (
            y_window[0] - self.y_margin,
            y_window[-1] + self.y_margin,
        )
        getattr(self, f"{type}_slope_resize_zone")["x"] = (
            x[-1] - self.x_margin,
            x[-1] + self.x_margin,
        )
        getattr(self, f"{type}_slope_resize_zone")["y"] = (
            y[-1] - self.y_margin,
            y[-1] + self.y_margin,
        )

    def updateAmpZone(self, type, x, y):
        # print(f"*** - updateAmpZone: {type} {x} {y}")
        amp_xy = x, y
        amp_move_zone = (
            x - self.x_margin,
            x + self.x_margin,
            y - self.y_margin,
            y + self.y_margin,
        )

        setattr(self, f"{type}_amp_xy", amp_xy)
        getattr(self, f"{type}_amp_move_zone")["x"] = amp_move_zone[0], amp_move_zone[1]
        getattr(self, f"{type}_amp_move_zone")["y"] = amp_move_zone[2], amp_move_zone[3]

    def get_recSet(self):  # returns a set of all rec IDs that are currently plotted
        return set([value["rec_ID"] for value in self.dict_rec_labels.values()])

    def get_groupSet(self):  # returns a set of all group IDs that are currently plotted
        return set([value["group_ID"] for value in self.dict_group_labels.values()])

    # --- x-axis mode helpers (7.2–7.5) ---

    @property
    def x_axis(self) -> str:
        """Single call site for all plot-layer x-axis decisions.
        Maps the experiment type to the underlying plot mode."""
        if self.experiment_type in ["time", "timestamp"]:
            return "time"
        elif self.experiment_type == "sweep":
            return "sweep"
        elif self.experiment_type == "train":
            return "stim"
        elif self.experiment_type == "io":
            return "io"
        # PP modes will likely use stim or a custom mode later
        return "sweep"

    @staticmethod
    def time_axis_unit(max_seconds: float) -> tuple:
        """Choose the most readable time unit for the x-axis.

        Returns (divisor, suffix) where divisor converts raw seconds to
        display values and suffix is the unit string for the axis label.

        Thresholds:
        - < 120 s   → seconds  (divisor=1,    suffix="s")
        - < 120 min → minutes  (divisor=60,   suffix="min")
        - otherwise → hours    (divisor=3600, suffix="h")
        """
        if max_seconds < 120:
            return (1.0, "s")
        if max_seconds < 7200:
            return (60.0, "min")
        return (3600.0, "h")

    def x_axis_xlabel(self) -> str:
        """Human-readable axis label for the current x-axis mode.

        In time mode, uses the cached unit label set by x_axis_xlim.
        """
        mode = self.x_axis
        if mode == "time":
            return f"Time ({self._time_unit_label})"
        elif mode == "io":
            io_input = getattr(self, "io_input", "vamp")
            if io_input == "vamp":
                return "Volley Amplitude (mV)"
            elif io_input == "vslope":
                return "Volley Slope (mV/ms)"
            return "Stimulus"
        return {"sweep": "Sweep", "stim": "Stim"}.get(mode, "Sweep")

    def x_axis_xlim(self, prow, dft=None) -> tuple:
        """Return (xmin, xmax) for the output graph given the current mode.

        In time mode, also caches the auto-scaled unit (divisor and label)
        for use by x_axis_xlabel and x_axis_formatter.  The returned limits
        are always in sweep-space (same coordinates as the line x-data);
        the FuncFormatter converts tick labels to the chosen time unit.
        """
        if self.experiment_type == "PP":
            has_groups = False
            max_x = 1.5
            if hasattr(self, "dict_group_show"):
                x_positions = []
                for key, val in self.dict_group_show.items():
                    if "PPR" in key and hasattr(val["line"], "patches"):
                        has_groups = True
                        try:
                            x_positions.append(val["line"].patches[0].get_x() + val["line"].patches[0].get_width() / 2)
                        except:
                            pass
                if x_positions:
                    max_x = max(x_positions) + 0.5
            if has_groups:
                return (0.5, max_x)

            # Check if we have recordings
            has_recs = False
            rec_x_positions = []
            if hasattr(self, "dict_rec_show"):
                for key, val in self.dict_rec_show.items():
                    if "PPR" in key and "marker" not in key and val.get("line") and val["line"].get_visible():
                        has_recs = True
                        try:
                            x_data = val["line"].get_xdata()
                            if len(x_data) > 0:
                                rec_x_positions.extend(x_data)
                        except:
                            pass
            if has_recs:
                if rec_x_positions:
                    return (min(rec_x_positions) - 0.5, max(rec_x_positions) + 0.5)
                return (0.5, 4.5)  # Default 1 to 4 span

            return (0.5, 1.5)

        mode = self.x_axis
        if mode == "sweep":
            n = prow["sweeps"]
            if pd.notna(prow.get("bin_size")):
                n = ceil(n / prow["bin_size"])
            return (0, n)
        elif mode == "time":
            if pd.isna(prow["sweep_hz"]):
                raise ValueError("x_axis_xlim called in time mode but sweep_hz is NaN")
            n = prow["sweeps"]
            bin_size = prow.get("bin_size")
            if pd.notna(bin_size):
                n = ceil(n / bin_size)
            else:
                bin_size = 1.0
            self._time_sweep_hz = prow["sweep_hz"]
            self._time_bin_size = bin_size
            max_seconds = (n * bin_size) / self._time_sweep_hz
            self._time_divisor, self._time_unit_label = self.time_axis_unit(max_seconds)
            # Return sweep-space limits; tick labels are converted by x_axis_formatter.
            return (0, n)
        elif mode == "stim":
            if dft is not None and len(dft) > 0 and "stim" in dft.columns:
                stim_min = int(dft["stim"].min())
                stim_max = int(dft["stim"].max())
            else:
                stims = prow["stims"]
                if pd.isna(stims):
                    raise ValueError("x_axis_xlim called in stim mode but prow['stims'] is NaN and no dft was provided")
                n = int(stims)
                stim_min = 1
                if stim_min > stim_max:
                    stim_max = n
            self._stim_tick_locs = list(range(stim_min, stim_max + 1))
            return (stim_min - 0.5, stim_max + 0.5)
        elif mode == "io":
            x_min, x_max = float("inf"), float("-inf")
            lines_to_check = list(self.dict_rec_labels.values())
            if hasattr(self, "dict_group_labels"):
                lines_to_check.extend(self.dict_group_labels.values())

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
                            x_data = line.get_xdata()
                            if len(x_data) > 0:
                                x_min = min(x_min, np.nanmin(x_data))
                                x_max = max(x_max, np.nanmax(x_data))
                    except Exception:
                        pass
            if x_min != float("inf") and x_max != float("-inf"):
                pad = abs(x_max) * 0.1
                if pad == 0:
                    pad = 0.1
                return (0, x_max + pad)
            return (0, 1)
        raise ValueError(f"Unknown x_axis mode: {mode!r}")

    def x_axis_locator(self):
        """Return a Locator that places ticks at nice intervals in the current mode."""
        mode = self.x_axis
        if mode == "time":
            return TimeModeLocator(self._time_sweep_hz, self._time_divisor, self._time_bin_size)
        elif mode == "stim":
            return FixedLocator(self._stim_tick_locs)
        return AutoLocator()

    def x_axis_formatter(self):
        """Return a FuncFormatter that converts sweep-number ticks to time.

        Only meaningful when x_axis_mode == "time".  For other modes returns
        a passthrough formatter (tick value displayed as-is with no decimals).

        Must be called after x_axis_xlim (which caches _time_sweep_hz and
        _time_divisor).
        """
        if self.x_axis == "time":
            sweep_hz = self._time_sweep_hz
            divisor = self._time_divisor
            bin_size = self._time_bin_size

            def _fmt(val, _pos):
                # When data is binned, the x-axis value (val) is the bin index.
                # So bin index * bin size gives the effective sweep number.
                t = (val * bin_size) / sweep_hz / divisor
                # Drop trailing zeros: "2.5" not "2.500", "3" not "3.0"
                return f"{t:g}"

            return FuncFormatter(_fmt)
        # Sweep / stim: integer ticks, no decimals.
        return FuncFormatter(lambda val, _pos: f"{val:g}")

    def x_axis_values(self, dfoutput, prow):
        """Return the x-values Series to plot for the current mode.

        Time mode returns sweep numbers (same as sweep mode); the
        FuncFormatter on the axis handles display conversion.
        """
        mode = self.x_axis
        if mode == "sweep" or mode == "time":
            mask = dfoutput["sweep"].notna()
            return dfoutput.loc[mask, "sweep"]
        elif mode == "stim":
            mask = dfoutput["sweep"].isna()
            return dfoutput.loc[mask, "stim"]
        elif mode == "io":
            mask = dfoutput["sweep"].notna()
            io_input = getattr(self, "io_input", "vamp")
            col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(io_input, "volley_amp")
            if col in dfoutput.columns:
                return dfoutput.loc[mask, col]
            return pd.Series(dtype=float)
        raise ValueError(f"Unknown x_axis mode: {mode!r}")

    def get_state(self):
        try:
            return {
                "version": self.version,
                "colors": self.colors,
                "splitter": self.splitter,
                "viewTools": self.viewTools,
                "checkBox": self.checkBox,
                "lineEdit": self.lineEdit,
                "settings": self.settings,
                "zoom": self.zoom,
                "default_dict_t": self.default_dict_t,
                "experiment_type": getattr(self, "experiment_type", "time"),
                "io_input": getattr(self, "io_input", "vamp"),
                "io_output": getattr(self, "io_output", "EPSPamp"),
                "showTimetable": self.showTimetable,
                "detailedProjectTable": getattr(self, "detailedProjectTable", False),
                "detailedTimetable": getattr(self, "detailedTimetable", False),
            }
        except AttributeError:
            # One or more attributes are missing (e.g. loading a stale pickle).
            # Reset to defaults and return the fresh state.
            self.reset()
            return self.get_state()

    def set_state(self, state):
        self.version = state.get("version")
        self.colors = state.get("colors")

        valid_splitters = self.splitter.copy()
        loaded_splitters = state.get("splitter") or {}
        self.splitter = {}
        for k, v in valid_splitters.items():
            loaded_v = loaded_splitters.get(k)
            if isinstance(loaded_v, list) and len(loaded_v) == len(v):
                self.splitter[k] = loaded_v
            else:
                self.splitter[k] = v

        # Read experiment type. Fallback to old x_axis_mode if experiment_type is missing,
        # otherwise default to "time".
        self.experiment_type = state.get("experiment_type", state.get("x_axis_mode", "time"))
        self.io_input = state.get("io_input", "vamp")
        self.io_output = state.get("io_output", "EPSPamp")

        self.showTimetable = state.get("showTimetable", False)
        self.detailedProjectTable = state.get("detailedProjectTable", False)
        self.detailedTimetable = state.get("detailedTimetable", False)

        # Filter out any keys saved in old configs that no longer exist as widgets.
        # This lets us remove keys from these dicts without old cfg.pkl files
        # re-introducing stale keys on next load, while also preserving defaults
        # for newly added features that don't exist in the old cfg.pkl.
        def merge_dict(default_dict, loaded_dict):
            return {k: loaded_dict.get(k, default_dict[k]) for k in default_dict}

        self.viewTools = merge_dict(self.viewTools, state.get("viewTools") or {})
        self.checkBox = merge_dict(self.checkBox, state.get("checkBox") or {})
        self.lineEdit = merge_dict(self.lineEdit, state.get("lineEdit") or {})
        self.settings = merge_dict(self.settings, state.get("settings") or {})

        # Rebuild zoom defensively: start from known-good defaults, overlay any
        # persisted values that are type-compatible, and silently discard
        # stale/corrupt entries (e.g. strings stored by older versions).
        zoom_defaults = {
            "mean_xlim": (0, 1),
            "mean_ylim": (-1, 1),
            "event_xlim": (-0.0012, 0.030),
            "event_ylim": (-0.001, 0.0002),
            "output_xlim": (0, None),
            "output_ax1_ylim": (0, 1.2),
            "output_ax2_ylim": (0, 1.2),
        }
        loaded_zoom = state.get("zoom") or {}

        def _ok(v):
            return v is None or isinstance(v, (int, float))

        validated_zoom = {}
        for key, default_val in zoom_defaults.items():
            persisted = loaded_zoom.get(key)
            if persisted is None:
                validated_zoom[key] = default_val
                continue
            # Each zoom value must be a 2-tuple of numbers (or None for open bounds).
            if not isinstance(persisted, (tuple, list)) or len(persisted) != 2:
                print(f"set_state: discarding zoom[{key!r}] = {persisted!r} (expected 2-tuple, got {type(persisted).__name__})")
                validated_zoom[key] = default_val
                continue
            lo, hi = persisted
            if not (_ok(lo) and _ok(hi)):
                print(f"set_state: discarding zoom[{key!r}] = {persisted!r} (tuple elements must be numeric or None)")
                validated_zoom[key] = default_val
                continue
            validated_zoom[key] = tuple(persisted)
        self.zoom = validated_zoom
        self.default_dict_t = state.get("default_dict_t")

    def load_cfg(self, projectfolder, bw_version, force_reset=False):  # load state from project config file
        path_pkl = projectfolder / "cfg.pkl"
        if path_pkl.exists() and not force_reset:
            with open(path_pkl, "rb") as f:
                data = pickle.load(f)
            if data is not None:
                self.set_state(data)
                # check if version is compatible
                if bw_version != self.version:
                    print(f"Warning: cfg.pkl is from {self.version} - current version is {bw_version}")
                    cfg_v = self.version.split(".")
                    bw_v = bw_version.split(".")
                    if cfg_v[0] != bw_v[0]:
                        print("Major version mismatch: Project may not load correctly")
                    elif cfg_v[1] != bw_v[1]:
                        print("Minor version mismatch: Some settings may not load correctly")
                    elif cfg_v[2] != bw_v[2]:
                        print("Patch version mismatch: Minor changes may not load correctly")
            else:
                print("Warning: cfg.pkl is empty or corrupt, resetting to defaults")
                self.reset()
                self.save_cfg(projectfolder, bw_version)
        else:
            self.reset()
            self.save_cfg(projectfolder, bw_version)

    def save_cfg(self, projectfolder, bw_version=None):  # save state to project config file
        path_pkl = projectfolder / "cfg.pkl"
        data = self.get_state()
        if bw_version is not None:
            data["version"] = bw_version
        if not path_pkl.parent.exists():
            path_pkl.parent.mkdir(parents=True, exist_ok=True)
        with open(path_pkl, "wb") as f:
            pickle.dump(data, f)

    def ampView(self):
        if getattr(self, "experiment_type", "time") == "io":
            return True
        show = self.checkBox
        return show["EPSP_amp"]

    def slopeView(self):
        if getattr(self, "experiment_type", "time") == "io":
            return False
        show = self.checkBox
        return show["EPSP_slope"]

    def slopeOnly(self):
        if getattr(self, "experiment_type", "time") == "io":
            return False
        show = self.checkBox
        return show["EPSP_slope"] and not show["EPSP_amp"]

    def anyView(self):
        if getattr(self, "experiment_type", "time") == "io":
            return True
        show = self.checkBox
        return any(show.values())

    def floor_to_resolution(self, value, resolution):
        # Infer decimals from resolution, e.g., 0.0003 → 4 decimal places
        decimals = abs(len(str(resolution).split(".")[-1]))

        floored = floor(value / resolution) * resolution
        return round(max(floored, resolution), decimals)


if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == True
    uistate.checkBox["EPSP_slope"] = False
    assert uistate.anyView() == False
    print("test passed")
