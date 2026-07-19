"""Bounded sub-state for UIstate (PR-06). No backwards-compat flat attributes."""

from __future__ import annotations


def _merge_dict(default_dict: dict, loaded_dict: dict | None) -> dict:
    loaded = loaded_dict or {}
    return {k: loaded.get(k, default_dict[k]) for k in default_dict}


def _rgb_near(a, b, *, tol: float = 0.05) -> bool:
    if not (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) >= 3 and len(b) >= 3):
        return False
    try:
        return all(abs(float(a[i]) - float(b[i])) <= tol for i in range(3))
    except (TypeError, ValueError):
        return False


# Pre-1.0.0 measure colors still present in many cfg.pkl settings blobs.
_LEGACY_MEASURE_RGB = {
    "rgb_volley_amp": (1.0, 0.2, 1.0),  # magenta
    "rgb_volley_slope": (1.0, 0.5, 1.0),  # light magenta
}
_DEFAULT_MEASURE_RGB = {
    "rgb_EPSP_amp": (0.2, 0.25, 0.85),
    "rgb_EPSP_slope": (0.45, 0.55, 0.95),
    "rgb_volley_amp": (0.1, 0.45, 0.15),
    "rgb_volley_slope": (0.35, 0.7, 0.35),
}


def migrate_legacy_measure_colors(settings: dict) -> dict:
    """Replace stock magenta volley RGBs with green family; leave custom colors alone."""
    out = dict(settings)
    for key, legacy in _LEGACY_MEASURE_RGB.items():
        if key in out and _rgb_near(out[key], legacy):
            out[key] = _DEFAULT_MEASURE_RGB[key]
    return out


def measure_rgb(settings: dict, aspect: str, default="black"):
    """Resolve rgb_* for an aspect, including *_mean / *_norm variants.

    Stock pre-1.0.0 magenta volley colors are remapped to the green family even if
    settings were not run through migrate_legacy_measure_colors (e.g. partial dicts).
    """
    if not aspect:
        return default
    base = str(aspect).replace("_mean", "").replace("_norm", "")
    key = f"rgb_{base}"
    if key in settings:
        color = settings[key]
        legacy = _LEGACY_MEASURE_RGB.get(key)
        if legacy is not None and _rgb_near(color, legacy):
            return _DEFAULT_MEASURE_RGB[key]
        return color
    # Fallback chain for partial settings
    if base.startswith("volley"):
        return settings.get("rgb_volley_amp", _DEFAULT_MEASURE_RGB.get("rgb_volley_amp", default))
    if base.startswith("EPSP"):
        return settings.get("rgb_EPSP_amp", _DEFAULT_MEASURE_RGB.get("rgb_EPSP_amp", default))
    return default


class ProjectPersistedState:
    """Persisted project UI preferences (cfg.pkl)."""

    def reset(self) -> None:
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
            "h_splitterMaster": [0.105, 0.04, 0.855, 300],
            "v_splitterGraphs": [0.2, 0.5, 0.3],
        }
        self.viewTools = {
            "frameToolStim": ["Stim detection", True],
            "frameToolSweeps": ["Sweep selection", True],
            "frameToolTag": ["Tag selection", True],
            "frameToolBin": ["Binning", True],
            "frameToolType": ["Experiment type", True],
            "frameToolFilter": ["Filter", True],
            "frameToolYscale": ["Y scaling", True],
            "frameToolDisplay": ["Results display", True],
            "frameToolAspect": ["Aspect toggles", True],
            "frameToolAspectSlope": ["Slope width", False],
            "frameToolAspectAmp": ["Amplitude width", False],
            "frameToolTest": ["Statistical test", True],
            "frameToolHierarchy": ["Hierarchy", True],
            "frameToolType_sub_io_stim": ["IO stim µA", True],
        }
        # Output ax1/ax2 series style: "dots" | "line" (default dots)
        self.output_line_style = "dots"
        self.checkBox = {
            "EPSP_amp": True,
            "EPSP_slope": True,
            "volley_amp": False,
            "volley_amp_mean": True,
            "volley_slope": False,
            "volley_slope_mean": True,
            "splitOddEven": False,
            "timepoints_per_stim": False,
            "output_ymin0": True,
            "norm_EPSP": False,
            "paired_stims": False,
            "io_trendline": False,
            "io_force0": False,
            "is_group_sample": False,
            "hierarchy_dd_is_subject": False,
        }
        self.lineEdit = {
            "split_at_time": 0.0,
            "import_gain": 1.0,
            "norm_EPSP_from": 0,
            "norm_EPSP_to": 0,
            "EPSP_amp_halfwidth_ms": 0,
            "volley_amp_halfwidth_ms": 0,
            "EPSP_slope_width_ms": 0,
            "volley_slope_width_ms": 0,
            "savgol_window": 9,
            "savgol_poly": 3,
        }
        self.settings = {
            "event_start": -0.005,
            "event_end": 0.05,
            "precision": 4,
            "dft_width_proportion": 0.2,
            "filter": "voltage",
            # Measure colors: EPSP blue family, volley green family (dark=amp, light=slope).
            # Same values for light/dark UI (black/white traces remain visible either way).
            **_DEFAULT_MEASURE_RGB,
            "alpha_mark": 0.4,
            "alpha_line": 1,
            "journal_export": "jneurosci",
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
        self.default_dict_t = {}
        self.showTimetable = False
        self.detailedProjectTable = False
        self.detailedTimetable = False
        # Project table header sort: column name (stable) + 0=asc / 1=desc. None = unsorted.
        self.project_table_sort = {"column": None, "order": 0}
        self.pushButtons = {
            "pushButton_stim_add": "triggerStimAdd",
            "pushButton_stim_remove": "triggerStimRemove",
            "pushButton_sweeps_even": "trigger_set_sweeps_even",
            "pushButton_sweeps_odd": "trigger_set_sweeps_odd",
            "pushButton_add_to_set": "triggerAddToSet",
            "pushButton_hide_hierarchy": "triggerHideHierarchy",
        }
        self.list_idx_recs2preload = []

    @staticmethod
    def _normalize_project_table_sort(raw) -> dict:
        default = {"column": None, "order": 0}
        if not isinstance(raw, dict):
            return default.copy()
        col = raw.get("column")
        if col is not None:
            col = str(col).strip() or None
        try:
            order = int(raw.get("order", 0))
        except (TypeError, ValueError):
            order = 0
        if order not in (0, 1):
            order = 0
        return {"column": col, "order": order}

    def to_state_dict(self) -> dict:
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
            "showTimetable": self.showTimetable,
            "detailedProjectTable": self.detailedProjectTable,
            "detailedTimetable": self.detailedTimetable,
            "project_table_sort": self._normalize_project_table_sort(self.project_table_sort),
            "output_line_style": self.output_line_style if self.output_line_style in ("dots", "line") else "dots",
        }

    def apply_state_dict(self, state: dict, *, zoom_defaults: dict) -> None:
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
        self.viewTools = _merge_dict(self.viewTools, state.get("viewTools"))
        self.checkBox = _merge_dict(self.checkBox, state.get("checkBox"))
        self.lineEdit = _merge_dict(self.lineEdit, state.get("lineEdit"))
        self.settings = migrate_legacy_measure_colors(_merge_dict(self.settings, state.get("settings")))
        loaded_zoom = state.get("zoom") or {}

        def _ok(v):
            return v is None or isinstance(v, (int, float))

        validated_zoom = {}
        for key, default_val in zoom_defaults.items():
            persisted = loaded_zoom.get(key)
            if persisted is None:
                validated_zoom[key] = default_val
                continue
            if not isinstance(persisted, (tuple, list)) or len(persisted) != 2:
                validated_zoom[key] = default_val
                continue
            lo, hi = persisted
            if not (_ok(lo) and _ok(hi)):
                validated_zoom[key] = default_val
                continue
            validated_zoom[key] = tuple(persisted)
        self.zoom = validated_zoom
        if state.get("default_dict_t") is not None:
            self.default_dict_t = state.get("default_dict_t")
        self.showTimetable = state.get("showTimetable", False)
        self.detailedProjectTable = state.get("detailedProjectTable", False)
        self.detailedTimetable = state.get("detailedTimetable", False)
        self.project_table_sort = self._normalize_project_table_sort(state.get("project_table_sort"))
        style = state.get("output_line_style", "dots")
        self.output_line_style = style if style in ("dots", "line") else "dots"


class ExperimentConfig:
    def reset(self) -> None:
        self.experiment_type = "time"
        self.io_input = "vamp"
        self.io_output = "EPSPamp"

    def to_state_dict(self) -> dict:
        return {
            "experiment_type": self.experiment_type,
            "io_input": self.io_input,
            "io_output": self.io_output,
        }

    def apply_state_dict(self, state: dict) -> None:
        self.experiment_type = state.get("experiment_type", "time")
        self.io_input = state.get("io_input", "vamp")
        self.io_output = state.get("io_output", "EPSPamp")


class StatTestState:
    def reset(self) -> None:
        self.test_type = "None"
        self.test_t_variant = "unpaired"
        self.test_t_tails = "two-sided"
        self.test_fdr = False
        self.test_sw = False
        self.test_levene = False
        self.label_test_t_one_sample_value = 0.0
        self.test_wilcox_variant = "paired"
        self.test_wilcox_tails = "two-sided"
        self.label_test_wilcox_one_sample_value = 0.0
        self.anova_label = "ANOVA (one-way)"
        self.buttonGroup_test_n = "subject"
        self.test_cluster = False
        self.formal_test_results = None
        self.statusbar_state = None
        # Session-only: restore non-IO test when leaving experiment_type io (not pickled).
        self.test_type_before_io = None

    def to_state_dict(self) -> dict:
        return {
            "test_type": self.test_type,
            "test_t_variant": self.test_t_variant,
            "test_t_tails": self.test_t_tails,
            "test_fdr": self.test_fdr,
            "test_sw": self.test_sw,
            "test_levene": self.test_levene,
            "label_test_t_one_sample_value": self.label_test_t_one_sample_value,
            "test_wilcox_variant": self.test_wilcox_variant,
            "test_wilcox_tails": self.test_wilcox_tails,
            "label_test_wilcox_one_sample_value": self.label_test_wilcox_one_sample_value,
            "anova_label": self.anova_label,
            "test_cluster": self.test_cluster,
            "buttonGroup_test_n": self.buttonGroup_test_n,
        }

    def apply_state_dict(self, state: dict) -> None:
        self.test_type = state.get("test_type", "None")
        self.test_t_variant = state.get("test_t_variant", "unpaired")
        self.test_t_tails = state.get("test_t_tails", "two-sided")
        self.test_fdr = state.get("test_fdr", False)
        self.test_sw = state.get("test_sw", False)
        self.test_levene = state.get("test_levene", False)
        self.label_test_t_one_sample_value = state.get("label_test_t_one_sample_value", 0.0)
        self.test_wilcox_variant = state.get("test_wilcox_variant", "paired")
        self.test_wilcox_tails = state.get("test_wilcox_tails", "two-sided")
        self.label_test_wilcox_one_sample_value = state.get("label_test_wilcox_one_sample_value", 0.0)
        self.anova_label = state.get("anova_label", "ANOVA (one-way)")
        self.buttonGroup_test_n = state.get("buttonGroup_test_n", "subject")
        if state.get("test_type") == "Cluster perm.":
            self.test_type = "Cluster perm."
        self.test_cluster = state.get("test_cluster", False)


class PlotSession:
    """Transient plot, selection, and interaction state (not pickled)."""

    def reset(self) -> None:
        self.showHeatmap = False
        self.dict_heatmap = {}
        self.dict_test_markers = {}
        self.testset_spans = {}
        # Output series on ax1/ax2: "line" (connected) or "dots" (markers only).
        self.output_line_style = "dots"
        # IO stim µA table: True until Apply (CSV may already be saved; plot not yet).
        self.stim_intensity_dirty = False
        self.axm = None
        self.axe = None
        self.ax1 = None
        self.ax2 = None
        self.frozen = False
        self.list_idx_select_recs = []
        self.list_idx_select_stims = [0]
        self.float_sweep_duration_max = None
        self.df_rec_select_data = None
        self.df_rec_select_time = None
        self.df_recs2plot = None
        self.dict_rec_labels = {}
        self.dict_rec_show = {}
        self.dict_group_labels = {}
        self.dict_group_show = {}
        self.x_select = {
            "mean_start": None,
            "mean_end": None,
            "output": set(),
            "output_start": None,
            "output_end": None,
        }
        self.mean_mouseover_stim_select = None
        self.mean_stim_x_ranges = {}
        self.mean_x_margin = None
        self.mean_y_margin = None
        self.mouseover_action = None
        self.mouseover_plot = None
        self.mouseover_blob = None
        self.mouseover_out = None
        self.mouseover_out_blob = None
        self.x_margin = None
        self.y_margin = None
        self.x_on_click = None
        self.x_drag_last = None
        self.x_drag = None
        self.dragging = False
        self.dft_temp = None
        self.EPSP_amp_xy = None
        self.EPSP_slope_start_xy = None
        self.EPSP_slope_end_xy = None
        self.volley_amp_xy = None
        self.volley_slope_start_xy = None
        self.volley_slope_end_xy = None
        self.EPSP_amp_move_zone = {}
        self.EPSP_slope_move_zone = {}
        self.EPSP_slope_resize_zone = {}
        self.volley_amp_move_zone = {}
        self.volley_slope_move_zone = {}
        self.volley_slope_resize_zone = {}
        self.last_out_x_idx = None
        self.ghost_sweep = None
        self.ghost_label = None
        self._time_divisor = 1.0
        self._time_unit_label = "s"
        self._time_sweep_hz = 1.0
        self._time_bin_size = 1.0
        self._stim_tick_locs: list[int] = []
        self.sample_artists = None
        self.sample_dirty = False
        self.sample_inset = None
        self.dd_group_samples = None