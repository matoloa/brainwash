# ui_stat_test.py
# StatTestMixin — formal statistical tests, applicability checks, statusbar, n_unit, etc.
# extracted from UIsub (Phase 4 of ui mixin extraction plan).
#
# Module-level singletons are injected by ui.py (same pattern as other mixins):
#
#   import ui_stat_test
#   ui_stat_test.uistate = uistate
#   ui_stat_test.config  = config
#   ui_stat_test.uiplot  = uiplot

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from PyQt5 import QtCore, QtWidgets

# brainwash stats (local module shadows stdlib; ui.py does "import statistics as stats" equivalent via its context + from . )
from . import statistics as stats

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class StatTestMixin:
    """Mixin that provides formal statistical test coordination, applicability checks, statusbar logic, n_unit handling, etc.

    Host requirements:
        - self.dd_groups, self.dd_testsets
        - self.get_group_testset_means (from DataFrameMixin)
        - self._is_loading_active()
        - self.graphRefresh(), self.update_show(), self.mouseoverUpdate() (optional for n_unit)
        - self.usage()
        - self.dict_folders for save_cfg calls
        - uiplot: show_test_markers, clear_test_markers, unPlotGroup, addGroup
        - uistate: test_type, experiment_type, formal_test_results, statusbar_state, buttonGroup_test_n, test_*_*, checkBox, viewTools, ...
    """

    # --- Radio mappings (test-related) ---
    # Duplicated here (small data) so mixin is robust if used; ui.py also defines them for uiFreeze etc.
    _RADIO_TO_TEST = {
        "radioButton_test_none": "None",
        "radioButton_test_t": "t-test",
        "radioButton_test_anova": "ANOVA",
        "radioButton_test_ancova": "ANCOVA",
        "radioButton_test_wilcoxon": "Wilcoxon",
        "radioButton_test_friedman": "Friedman",
        "radioButton_test_cluster": "Cluster perm.",
    }
    _TEST_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST.items()}

    _RADIO_TO_TEST_T_VARIANT = {
        "radioButton_test_t_variant_one": "one-sample",
        "radioButton_test_t_variant_paired": "paired",
        "radioButton_test_t_variant_unpaired": "unpaired",
    }
    _TEST_T_VARIANT_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_T_VARIANT.items()}

    _RADIO_TO_TEST_T_TAILS = {
        "radioButton_test_t_tails_two": "two-sided",
        "radioButton_test_t_tails_greater": "greater",
        "radioButton_test_t_tails_less": "less",
    }
    _TEST_T_TAILS_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_T_TAILS.items()}

    _RADIO_TO_TEST_WILCOX_VARIANT = {
        "radioButton_wilcoxon_variant_paired": "paired",
        "radioButton_wilcoxon_variant_one": "one-sample",
    }
    _TEST_WILCOX_VARIANT_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_WILCOX_VARIANT.items()}

    _RADIO_TO_TEST_WILCOX_TAILS = {
        "radioButton_wilcoxon_tails_two": "two-sided",
        "radioButton_wilcoxon_tails_greater": "greater",
        "radioButton_wilcoxon_tails_less": "less",
    }
    _TEST_WILCOX_TAILS_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_WILCOX_TAILS.items()}

    _RADIO_TO_TEST_N = {
        "radioButton_test_n_subject": "subject",
        "radioButton_test_n_slice": "slice",
        "radioButton_test_n_rec": "recording",
    }
    _TEST_N_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_N.items()}

    # (TYPE map is experiment, lives in core with io_ maps)

    # -------------------------------------------------------------------------
    # Visibility / helpers (also used by ProjectMixin setup etc.)
    # -------------------------------------------------------------------------

    def _get_shown_group_ids(self):
        """Return list of group IDs that are currently shown (checkbox checked)."""
        if not hasattr(self, "dd_groups") or not self.dd_groups:
            return []
        return [gid for gid, g in self.dd_groups.items() if g.get("show") in (True, "True", "true", 1, "1")]

    def _get_shown_testsets(self):
        """Return list of shown test set IDs."""
        if not hasattr(self, "dd_testsets"):
            return []
        return [tid for tid, t in self.dd_testsets.items() if t.get("show", False)]

    def update_anova_label(self):
        """Update label_test_ANOVA and uistate.anova_label based on number of shown test sets."""
        if not hasattr(self, "label_test_ANOVA"):
            return
        n = len(self._get_shown_testsets())
        if n > 1:
            label_text = "ANOVA (repeated)"
        else:
            label_text = "ANOVA (one-way)"
        uistate.anova_label = label_text
        self.label_test_ANOVA.setText(label_text)
        if hasattr(self, "dict_folders") and "project" in getattr(self, "dict_folders", {}):
            uistate.save_cfg(projectfolder=self.dict_folders["project"])

    def clear_formal_test_results(self):
        """Clear any formal test markers and stored results. Independent of heatmap."""
        try:
            if uiplot is not None:
                uiplot.clear_test_markers(draw=True)
        except Exception:
            pass
        if hasattr(uistate, "formal_test_results"):
            uistate.formal_test_results = None
        uistate.statusbar_state = None  # reset non-persisted state on clear
        # leave printed console output as-is (user can scroll)

    # -------------------------------------------------------------------------
    # Core statusbar appearance (authoritative; richer version using statusbar_label)
    # -------------------------------------------------------------------------

    def _set_statusbar_appearance(
        self, bg_color: str = None, text_color: str = None, bold: bool = False, text: str | None = None, clear: bool = False
    ):
        """Set statusbar appearance.
        - If bg_color is provided (e.g. red #c0392b for errors/warnings), force that background.
        - Otherwise (non-error states or successful stat test reports), do not force a background color so the
          statusbar uses its default appearance (sensitive to darkmode()).
        Text on the internal statusbar_label is always centered.
        """
        # Only force a background for error/warning states. For everything else
        # (including successful statistical test p-value reports) leave the
        # statusbar's background as the theme default.
        if bg_color:
            style = f"QStatusBar {{ background-color: {bg_color}; }}"
        else:
            style = ""

        # Choose a sensible text color for non-error states if none supplied.
        if text_color is None and bg_color is None:
            text_color = "#ddd" if getattr(uistate, "darkmode", False) else "#333"

        lbl = "QStatusBar QLabel { qproperty-alignment: AlignCenter; background-color: transparent;"
        if text_color:
            lbl += f" color: {text_color};"
        if bold:
            lbl += " font-weight: bold;"
        lbl += " }"
        self.statusbar.setStyleSheet(style + lbl)

        # Our own controlled label (created in __init__ after setupUi).
        label = getattr(self, "statusbar_label", None)
        if label is not None:
            label.setAlignment(QtCore.Qt.AlignCenter)
            parts = ["background-color: transparent;"]
            if text_color:
                parts.append(f"color: {text_color};")
            if bold:
                parts.append("font-weight: bold;")
            label.setStyleSheet("; ".join(parts))
            if clear or text in (None, ""):
                label.setText("")
            elif text is not None:
                label.setText(text)
            else:
                current_text = label.text()
                if current_text:
                    label.setText(current_text)

        try:
            self.statusbar.clearMessage()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Mode / effective state helpers (pure)
    # -------------------------------------------------------------------------

    def _is_io_mode(self) -> bool:
        return getattr(uistate, "experiment_type", "time") == "io"

    def _effective_test_type(self) -> str:
        if self._is_io_mode():
            return "io_regression"
        return getattr(uistate, "test_type", "None")

    def _should_show_stat_test_frame(self) -> bool:
        """Central helper: return whether Statistical Test frame should be shown (respects viewTools/menu/hide button state; no auto-hide on IO)."""
        if "frameToolTest" in getattr(uistate, "viewTools", {}):
            return uistate.viewTools["frameToolTest"][1]
        return not self._is_io_mode()

    def _is_loading_active(self):
        """True while parsing or preloading is using the progressBar. (delegates or local)"""
        try:
            return bool(self.progressBar.isVisible())
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Statusbar single source of truth + formatters
    # -------------------------------------------------------------------------

    def _get_statusbar_for_current_state(self) -> str | None:
        """Single source of truth for statusbar per AGENTS.md and plan.md.
        Dispatches based on experiment_type/effective operation. IO prefers formal_test_results config.
        Pure query (state set only by caller update_test / set_statusbar).
        """
        eff = self._effective_test_type()
        if eff == "None":
            uistate.statusbar_state = None
            return None
        if self._is_io_mode():
            formal = getattr(uistate, "formal_test_results", None)
            return self._format_io_regression_statusbar(formal)
        # non-IO
        text = self._get_stat_test_warning()
        if text is not None:
            uistate.statusbar_state = "warning"
            return text
        formal = getattr(uistate, "formal_test_results", None)
        if formal:
            text = self._format_non_io_stat_test_statusbar(formal)
            if text:
                return text
        uistate.statusbar_state = None
        return None

    def _format_io_regression_statusbar(self, formal):
        """Single source of truth for IO regression statusbar."""
        if formal:
            if isinstance(formal, list) and formal:
                item = formal[0]
                if isinstance(item, dict):
                    cfg = item.get("config") or item
            elif isinstance(formal, dict):
                cfg = formal.get("config") or formal
            else:
                cfg = None
            if isinstance(cfg, dict) and cfg.get("type") == "IO regression":
                prefix = "IO ANCOVA"
                global_notes = []
                n_report = ""
                group_ns = cfg.get("group_ns") or (formal[0] if isinstance(formal, list) else formal).get("group_ns", {})
                n_unit = cfg.get("n_unit", getattr(uistate, "buttonGroup_test_n", "subject"))
                unit_label = "subjects" if n_unit == "subject" else f"{n_unit}s"
                if group_ns:
                    ns = []
                    for g, n in group_ns.items():
                        g_name = self.dd_groups.get(g, {}).get("group_name", f"Group {g}")
                        ns.append(f"{g_name}={n}")
                    n_report = f"({', '.join(ns)} {unit_label})"
                x_col = cfg.get("x_col", "volley_amp")
                y_col = cfg.get("y_col", "EPSP_amp")
                label_map = {
                    "EPSP_amp": "EPSP amp",
                    "EPSP_slope": "EPSP slope",
                    "volley_amp": "volley amp",
                    "volley_slope": "volley slope",
                    "stim": "stim",
                }
                y_label = label_map.get(y_col, y_col.replace("_", " "))
                x_label = label_map.get(x_col, x_col.replace("_", " "))
                xy_label = f"{y_label} / {x_label}"
                slope_p = cfg.get("slope_p") or (formal[0] if isinstance(formal, list) else formal).get("slope_p")
                if isinstance(slope_p, (int, float)) and np.isfinite(slope_p):
                    pstr = f"{slope_p:.3g}" if slope_p >= 0.001 else "<0.001"
                    stat_label = "slope" if str(cfg.get("io_output", "")).endswith(("slope", "Slope")) else "ratio"
                    global_notes.append(f"{stat_label} p={pstr}")
                for g, r2v in cfg.get("r2_per_group", {}).items():
                    if isinstance(r2v, (int, float)) and np.isfinite(r2v):
                        global_notes.append(f"r²({g})={r2v:.2f}")
                        break
                if global_notes:
                    notes_str = " ".join(global_notes)
                    prefix = f"{prefix} {n_report} {xy_label}: {notes_str}"
                else:
                    prefix = f"{prefix} {n_report} {xy_label}"
                uistate.statusbar_state = "info"
                return prefix
            uistate.statusbar_state = None
            return "IO regression: select ≥2 groups to compute slope comparison"
        uistate.statusbar_state = None
        return None

    def _format_non_io_stat_test_statusbar(self, formal):
        """Compact success statusbar text for non-IO formal tests."""
        if not formal:
            uistate.statusbar_state = None
            return None
        results = formal if isinstance(formal, list) else [formal]
        if not any(isinstance(r, dict) for r in results):
            uistate.statusbar_state = None
            return None

        eff = self._effective_test_type()
        if eff == "Wilcoxon":
            variant = getattr(uistate, "test_wilcox_variant", "paired")
        elif eff == "t-test":
            variant = getattr(uistate, "test_t_variant", "unpaired")
        else:
            variant = None

        test_label = f"{eff} ({variant})" if variant else eff

        n_report = ""
        primary = results[0] if results else {}
        try:
            if isinstance(primary, dict):
                n_unit = getattr(uistate, "buttonGroup_test_n", "subject")
                unit_label = "subjects" if n_unit == "subject" else f"{n_unit}s"
                ddg = getattr(self, "dd_groups", {}) or {}
                group_ns = primary.get("group_ns") or (primary.get("config") or {}).get("group_ns", {})
                if group_ns:
                    ns = []
                    for g, n in group_ns.items():
                        g_name = ddg.get(g, {}).get("group_name", f"Group {g}")
                        ns.append(f"{g_name}={n}")
                    if ns:
                        n_report = f"({', '.join(ns)} {unit_label})"
                else:
                    g1 = primary.get("group1")
                    g2 = primary.get("group2")
                    n1 = int(primary.get("n1", 0) or 0)
                    n2 = int(primary.get("n2", 0) or 0)
                    if isinstance(g1, (list, tuple)) and len(g1) == 1: g1 = g1[0]
                    if isinstance(g2, (list, tuple)) and len(g2) == 1: g2 = g2[0]
                    def _gname(g):
                        if g is None or isinstance(g, (list, tuple)): return None
                        return ddg.get(g, {}).get("group_name", f"Group {g}")
                    if g1 is not None and g2 is not None and g1 != g2 and not isinstance(g1, (list, tuple)):
                        p1 = f"{_gname(g1)}={n1}" if n1 else str(_gname(g1))
                        p2 = f"{_gname(g2)}={n2}" if n2 else str(_gname(g2))
                        n_report = f"({p1}, {p2} {unit_label})"
                    elif g1 is not None:
                        if isinstance(g1, (list, tuple)):
                            parts = []
                            val = n1 or n2
                            for gg in g1:
                                nm = _gname(gg)
                                parts.append(f"{nm}={val}" if val else str(nm))
                            if parts: n_report = f"({', '.join(parts)} {unit_label})"
                        else:
                            nm = _gname(g1)
                            val = n1 or n2
                            n_report = f"({nm}={val} {unit_label})" if val else f"({nm})"
        except Exception:
            n_report = ""

        if n_report:
            test_label = f"{test_label} {n_report}"

        fdr = bool(getattr(uistate, "test_fdr", False))
        sw = bool(getattr(uistate, "test_sw", False))
        lev = bool(getattr(uistate, "test_levene", False))

        is_multi = (eff == "Cluster perm.") or len(results) > 1
        reports = []
        for idx, r in enumerate(results):
            if not isinstance(r, dict): continue
            set_prefix = ""
            if is_multi:
                sname = r.get("set_name") or r.get("set_id") or f"set{idx+1}"
                set_prefix = f"{sname}: "
            for key in sorted(k for k in r.keys() if k.startswith("p_")):
                aspect = key[2:].replace("_norm", " (norm)")
                use_q = fdr and r.get("q_" + key[2:]) is not None
                val_key = "q_" + key[2:] if use_q else key
                val = r.get(val_key, r.get(key))
                if isinstance(val, (int, float)) and np.isfinite(val):
                    pstr = f"{val:.3g}" if val >= 0.001 else "<0.001"
                else:
                    pstr = "NA"
                label = "q" if use_q else "p"
                reports.append(f"{set_prefix}{aspect}: {label}={pstr}")

        diag = []
        diag_suffix = ""
        if sw:
            diag.append("SW")
        if lev:
            lev_strs = []
            for r in results:
                for asp in ("amp", "slope"):
                    p = r.get(f"levene_p_{asp}")
                    if isinstance(p, (int, float)) and np.isfinite(p):
                        pstr = f"{p:.3g}" if p >= 0.001 else "<0.001"
                        lev_strs.append(f"{asp} p={pstr}")
            if lev_strs:
                diag.append("Lev(" + " ".join(lev_strs) + ")")
            else:
                diag.append("Levene")
        if diag:
            diag_suffix = "    " + " ".join(diag)

        if not reports:
            uistate.statusbar_state = "info"
            return f"{test_label}: done (see console){diag_suffix}"
        text = f"{test_label}: {'  '.join(reports)}{diag_suffix}"
        uistate.statusbar_state = "info"
        return text

    # -------------------------------------------------------------------------
    # Applicability checks (pure; return warning str or None)
    # -------------------------------------------------------------------------

    def _check_ttest_applicability(self, variant: str) -> str | None:
        had_results = bool(getattr(uistate, "formal_test_results", None))
        if not hasattr(self, "dd_groups") or not isinstance(self.dd_groups, dict) or not self.dd_groups:
            if had_results:
                print("Statistical test: no groups defined.")
            return "No groups defined for t-test"
        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]
        min_groups = 1 if variant in ("one-sample", "paired") else 2
        if len(shown_groups) < min_groups:
            if had_results:
                print(f"Statistical test: need at least {min_groups} shown group(s) with data for {variant}.")
            return f"t-test requires {min_groups} group(s) with data"
        shown_ts = self._get_shown_testsets()
        if variant == "paired" and len(shown_ts) != 2:
            if had_results:
                print("Statistical test: paired requires exactly 2 shown test sets (with 1 group).")
            return "Paired t-test requires exactly 2 test sets"
        if variant == "paired":
            n1 = len(self.dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
            if n1 < 2:
                if had_results:
                    print("Statistical test: paired requires N ≥ 2 recordings.")
                return "Paired t-test requires N ≥ 2 recordings per group"
        if not shown_ts:
            if had_results:
                print(f"Statistical test: no shown test sets. Tag sweeps and show at least one test set. (shown_ts={len(shown_ts)})")
            return "No test sets shown for t-test"
        return None

    def _check_anova_applicability(self) -> str | None:
        had_results = bool(getattr(uistate, "formal_test_results", None))
        if not hasattr(self, "dd_groups") or not isinstance(self.dd_groups, dict) or not self.dd_groups:
            if had_results:
                print("Statistical test: no groups defined.")
            return "No groups defined for ANOVA"
        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]
        shown_ts = self._get_shown_testsets()
        if len(shown_groups) < 1 or (len(shown_groups) == 1 and len(shown_ts) < 2):
            if had_results:
                print(f"Statistical test: ANOVA requires either >=2 groups, or 1 group with >=2 test sets (repeated-measures).")
            return "ANOVA requires ≥2 groups or 1 group + ≥2 test sets"
        if not shown_ts and len(shown_groups) == 1:
            if had_results:
                print(f"Statistical test: no shown test sets for repeated-measures ANOVA.")
            return "Repeated-measures ANOVA requires ≥2 test sets"
        return None

    def _check_wilcoxon_applicability(self, variant: str) -> str | None:
        return self._check_ttest_applicability(variant)

    def _check_friedman_applicability(self) -> str | None:
        had_results = bool(getattr(uistate, "formal_test_results", None))
        shown_ts = self._get_shown_testsets()
        if len(shown_ts) < 3:
            if had_results or True:
                print(f"Statistical test: Friedman requires ≥3 test sets (shown_ts={len(shown_ts)})")
            return "Friedman requires ≥3 test sets for repeated-measures"
        return None

    def _check_cluster_applicability(self) -> str | None:
        had_results = bool(getattr(uistate, "formal_test_results", None))
        if not hasattr(self, "dd_groups") or not isinstance(self.dd_groups, dict) or not self.dd_groups:
            if had_results:
                print("Statistical test: no groups defined.")
            return "No groups defined for Cluster perm."
        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]
        shown_ts = self._get_shown_testsets()
        if len(shown_groups) >= 2:
            return None
        if len(shown_groups) == 1 and len(shown_ts) >= 2:
            return None
        if had_results:
            print("Statistical test: Cluster perm. requires ≥2 groups or 1 group + 2 test sets.")
        return "Cluster permutation test requires ≥2 groups or 1 group + ≥2 test sets"

    def _get_stat_test_warning(self):
        """Return warning string (for non-IO) or status text (for IO), else None. Pure."""
        eff = self._effective_test_type()
        if eff == "None":
            return None
        if eff not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
            return f"Statistical test '{eff}' is not implemented"

        if eff == "t-test":
            variant = getattr(uistate, "test_t_variant", "unpaired")
            warning = self._check_ttest_applicability(variant)
        elif eff == "ANOVA":
            warning = self._check_anova_applicability()
        elif eff == "Wilcoxon":
            variant = getattr(uistate, "test_wilcox_variant", "paired")
            warning = self._check_wilcoxon_applicability(variant)
        elif eff == "Friedman":
            warning = self._check_friedman_applicability()
        elif eff == "Cluster perm.":
            warning = self._check_cluster_applicability()
        else:
            warning = None
        return warning

    # -------------------------------------------------------------------------
    # Main entry point + dispatcher + workers
    # -------------------------------------------------------------------------

    def update_test(self):
        """Single high-level entrypoint for all changes that affect statistical tests or their statusbar.
        Always runs statistical analysis if a test is active, then calls set_statusbar with the resulting state/text.
        """
        if self._is_loading_active():
            return
        if getattr(self, "_updating_test", False):
            return
        self._updating_test = True
        try:
            self.apply_statistical_test_if_active()
        finally:
            self._updating_test = False

        text = self._get_statusbar_for_current_state()
        state = getattr(uistate, "statusbar_state", None)
        self.set_statusbar(state, text)

    def set_statusbar(self, state: str | None = None, text: str | None = None):
        """Low-level applicator: only does what it is given (debug print + appearance)."""
        print(f"STATUSBAR: {text} (state={state})")
        if state == "warning":
            self._set_statusbar_appearance("#c0392b", text_color="white", bold=True, text=text)
        elif state == "info" or text:
            self._set_statusbar_appearance(bg_color=None, bold=True, text=text or "")
        else:
            self._set_statusbar_appearance(clear=True)

    def _on_statusbar_message_cleared(self, text):
        """After a transient message clears, restore via set_statusbar (pure display refresh)."""
        if text:
            return
        if self._is_loading_active():
            return
        self.set_statusbar(None, None)

    def apply_statistical_test_if_active(self):
        """Core dispatcher: io_regression or non-IO or clear."""
        try:
            eff = self._effective_test_type()
            if self._is_io_mode():
                self._apply_io_regression()
                return
            if eff == "None":
                self.clear_formal_test_results()
                return
            self._apply_non_io_test(eff)
        except Exception as ex:
            print(f"Statistical test: aborted (not applicable or internal issue): {ex}")
            import traceback
            traceback.print_exc()
            try:
                self.clear_formal_test_results()
            except Exception:
                pass

    def _apply_io_regression(self) -> bool:
        """Helper for IO path."""
        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]
        experiment_type = "io"
        try:
            comp = stats.compute_statistical_comparison(
                groups=shown_groups,
                dd_groups=self.dd_groups,
                dd_testsets=self.dd_testsets,
                get_group_testset_means_fn=self.get_group_testset_means,
                test_type="ANOVA",
                variant="unpaired",
                tails="two-sided",
                fdr=False,
                norm=False,
                amp=True,
                slope=True,
                ref=0.0,
                n_unit=getattr(uistate, "buttonGroup_test_n", "subject"),
                experiment_type=experiment_type,
            )
            results = list(comp.get("results", [])) if not comp.get("error") and not comp.get("not_implemented") else []
            if comp.get("config"):
                if not isinstance(results, list) or len(results) == 0:
                    results = [comp["config"].copy()]
                else:
                    for r in results:
                        if isinstance(r, dict):
                            r.setdefault("config", comp["config"])
            if results and isinstance(results, list) and len(results) > 0 and "group_ns" in results[0]:
                if isinstance(results[0], dict) and "config" not in results[0]:
                    results[0]["config"] = results[0].copy()
            uistate.formal_test_results = results
            uiplot.show_test_markers(results)
            return True
        except Exception as ex:
            print(f"IO regression compute error: {ex}")
            self.clear_formal_test_results()
            return False

    def _apply_non_io_test(self, eff: str) -> None:
        """Isolated non-IO guard + compute logic."""
        test_type = eff
        if eff not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
            print(f"Statistical test '{eff}' is not yet implemented for v0.16 (t-test, ANOVA, Wilcoxon, Friedman, Cluster perm.).")
            self.clear_formal_test_results()
            return

        had_results = bool(getattr(uistate, "formal_test_results", None))

        if not hasattr(self, "dd_groups") or not isinstance(self.dd_groups, dict) or not self.dd_groups:
            if had_results:
                print("Statistical test: no groups defined.")
            self.clear_formal_test_results()
            return

        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]

        ref_attr = "label_test_t_one_sample_value"
        if test_type == "Wilcoxon":
            variant_for_check = getattr(uistate, "test_wilcox_variant", "paired")
            ref_attr = "label_test_wilcox_one_sample_value"
        else:
            variant_for_check = getattr(uistate, "test_t_variant", "unpaired")
        if test_type == "Cluster perm.":
            variant_for_check = "unpaired"
        shown_ts = self._get_shown_testsets()
        if test_type in ("ANOVA", "Friedman"):
            min_groups = 1
        elif test_type == "Cluster perm.":
            min_groups = 1
        else:
            min_groups = 1 if variant_for_check in ("one-sample", "paired") else 2
        if len(shown_groups) < min_groups and test_type != "Cluster perm.":
            if had_results or test_type == "Friedman":
                if test_type == "ANOVA":
                    print("Statistical test: ANOVA requires either >=2 groups, or 1 group with >=2 test sets (repeated-measures).")
                elif test_type == "Friedman":
                    print(f"Statistical test: Friedman min_groups guard: shown_groups={len(shown_groups)} (need >=1), min_groups={min_groups}, shown_ts={len(shown_ts)} (need >=3)")
                else:
                    print(f"Statistical test: need at least {min_groups} shown group(s) with data for {variant_for_check}.")
            self.clear_formal_test_results()
            return

        if variant_for_check == "paired" and test_type != "Friedman":
            if len(shown_ts) != 2:
                if had_results:
                    print("Statistical test: paired requires exactly 2 shown test sets (with 1 group).")
                self.clear_formal_test_results()
                return
            n1 = len(self.dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
            if n1 < 2:
                if had_results:
                    print("Statistical test: paired requires N ≥ 2 recordings.")
                self.clear_formal_test_results()
                return

        if not shown_ts and test_type not in ("Friedman", "Cluster perm."):
            if had_results or test_type == "Friedman":
                print(f"Statistical test: no shown test sets. Tag sweeps and show at least one test set. (shown_ts={len(shown_ts)})")
            self.clear_formal_test_results()
            return

        if test_type == "Wilcoxon":
            variant = getattr(uistate, "test_wilcox_variant", "paired")
            tails = getattr(uistate, "test_wilcox_tails", "two-sided")
        else:
            variant = getattr(uistate, "test_t_variant", "unpaired")
            tails = getattr(uistate, "test_t_tails", "two-sided")
        ref_value = getattr(uistate, ref_attr, 0.0)
        fdr = bool(getattr(uistate, "test_fdr", False))
        norm = bool(uistate.checkBox.get("norm_EPSP", False))
        amp = bool(uistate.checkBox.get("EPSP_amp", True))
        slope = bool(uistate.checkBox.get("EPSP_slope", True))
        g1 = shown_groups[0] if shown_groups else None
        g2 = shown_groups[1] if len(shown_groups) > 1 else None
        n1 = len(self.dd_groups.get(g1, {}).get("rec_IDs", [])) if g1 else 0
        n2 = len(self.dd_groups.get(g2, {}).get("rec_IDs", [])) if g2 else 0

        n_unit = getattr(uistate, "buttonGroup_test_n", "subject")
        experiment_type = getattr(uistate, "experiment_type", "time")

        try:
            comp = stats.compute_statistical_comparison(
                groups=shown_groups,
                dd_groups=self.dd_groups,
                dd_testsets=self.dd_testsets,
                get_group_testset_means_fn=self.get_group_testset_means,
                test_type=test_type,
                variant=variant,
                tails=tails,
                fdr=fdr,
                norm=norm,
                amp=amp,
                slope=slope,
                ref=ref_value,
                n_unit=n_unit,
                experiment_type=experiment_type,
            )
            results = list(comp.get("results", [])) if not comp.get("error") and not comp.get("not_implemented") else []
            if comp.get("config"):
                if not isinstance(results, list) or len(results) == 0:
                    results = [comp["config"].copy()]
                else:
                    for r in results:
                        if isinstance(r, dict):
                            r.setdefault("config", comp["config"])
        except Exception as ex:
            print(f"apply_statistical_test compute error: {ex}")
            results = []

        if not results and not (comp.get("config") and comp.get("config").get("implicit_testset")):
            self.clear_formal_test_results()
            return
        if comp.get("config") and comp.get("config").get("implicit_testset") and (not results or not isinstance(results, list) or len(results) == 0):
            results = [{"config": comp["config"]}]

        uistate.formal_test_results = results
        uiplot.show_test_markers(results)
        self._print_statistical_test_table(results, variant=variant, tails=tails, fdr=fdr, norm=norm, test_type=test_type)
        set_names = ", ".join(str(r.get("set_name") or r.get("set_id") or "?") for r in results)
        sw = bool(getattr(uistate, "test_sw", False))
        lev = bool(getattr(uistate, "test_levene", False))
        effective_variant = "unpaired" if test_type == "Cluster perm." else variant
        self.usage(f"stat_test applied: {test_type} {effective_variant} {tails} on {set_names} (fdr={fdr}, sw={sw}, levene={lev}, n_unit={n_unit})")

    def _print_statistical_test_table(self, results, variant, tails, fdr, norm, test_type=None):
        if not results:
            return
        print("\n=== Statistical test (v0.16) ===")
        effective_variant = "unpaired" if (test_type or variant) == "Cluster perm." else variant
        print(f"variant={effective_variant}  tails={tails}  fdr={fdr}  norm={norm}")
        print("Note: each n = mean of aspect over sweeps in the test set, per recording.")
        if test_type == "Cluster perm.":
            for r_idx, r in enumerate(results):
                n1 = r.get("n1", 0)
                n2 = r.get("n2", 0)
                set_name = r.get("set_name") or r.get("set_id") or "?"
                print(f"  {set_name}:")
                for key in sorted(k for k in r.keys() if k.startswith("p_")):
                    pval = r.get(key)
                    sval = r.get("stat_" + key[2:], np.nan)
                    qval = r.get("q_" + key[2:], None)
                    aspect = key[2:]
                    pstr = f"{pval:.4g}" if isinstance(pval, (int, float)) and np.isfinite(pval) else str(pval)
                    if isinstance(sval, (int, float)) and np.isfinite(sval):
                        line = f"    {aspect}: p={pstr}  stat={sval:.4g}  n1={n1} n2={n2}"
                    else:
                        line = f"    {aspect}: p={pstr}  n1={n1} n2={n2}"
                    if qval is not None and isinstance(qval, (int, float)) and np.isfinite(qval):
                        line += f"  q={qval:.4g}"
                    print(line)
        else:
            r = results[0]
            n1 = r.get("n1", 0)
            n2 = r.get("n2", 0)
            for key in sorted(k for k in r.keys() if k.startswith("p_")):
                pval = r.get(key)
                sval = r.get("stat_" + key[2:], np.nan)
                qval = r.get("q_" + key[2:], None)
                aspect = key[2:]
                pstr = f"{pval:.4g}" if isinstance(pval, (int, float)) and np.isfinite(pval) else str(pval)
                if isinstance(sval, (int, float)) and np.isfinite(sval):
                    line = f"  {aspect}: p={pstr}  stat={sval:.4g}  n1={n1} n2={n2}"
                else:
                    line = f"  {aspect}: p={pstr}  n1={n1} n2={n2}"
                if qval is not None and isinstance(qval, (int, float)) and np.isfinite(qval):
                    line += f"  q={qval:.4g}"
                print(line)
        print("=== end test ===\n")

    # -------------------------------------------------------------------------
    # Radio / edit handlers (thin state update + save + reeval via update_test)
    # -------------------------------------------------------------------------

    def test_type_changed(self, button):
        """Handler for buttonGroup_test.buttonClicked signal."""
        test_type = self._RADIO_TO_TEST.get(button.objectName(), button.text()) if hasattr(self, "_RADIO_TO_TEST") else button.text()
        old_type = getattr(uistate, "test_type", "None")
        if test_type is None or test_type == old_type:
            return
        self.usage(f"test_type_changed → {test_type}")
        print(f"Selected statistical test: {test_type}")
        uistate.test_type = test_type
        if hasattr(self, "frameToolTest_sub_t"):
            self.frameToolTest_sub_t.setVisible(test_type == "t-test")
            if hasattr(self, "lineEdit_test_t_one_sample_value"):
                val = getattr(uistate, "label_test_t_one_sample_value", 0.0)
                self.lineEdit_test_t_one_sample_value.setText(str(val))
        if hasattr(self, "frameToolTest_sub_ANOVA"):
            self.frameToolTest_sub_ANOVA.setVisible(test_type in ("ANOVA", "ANCOVA"))
            if test_type in ("ANOVA", "ANCOVA"):
                self.update_anova_label()
        if hasattr(self, "frameToolTest_sub_wilcoxon"):
            self.frameToolTest_sub_wilcoxon.setVisible(test_type == "Wilcoxon")
            if test_type == "Wilcoxon" and hasattr(self, "lineEdit_wilcoxon_one_sample_value"):
                val = getattr(uistate, "label_test_wilcox_one_sample_value", 0.0)
                self.lineEdit_wilcoxon_one_sample_value.setText(str(val))
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        uistate.formal_test_results = None
        self.update_test()

    def test_t_variant_changed(self, button):
        variant = self._RADIO_TO_TEST_T_VARIANT.get(button.objectName(), button.text()) if hasattr(self, "_RADIO_TO_TEST_T_VARIANT") else button.text()
        print(f"Selected t-test variant: {variant}")
        uistate.test_t_variant = variant
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def test_t_tails_changed(self, button):
        tails = self._RADIO_TO_TEST_T_TAILS.get(button.objectName(), button.text()) if hasattr(self, "_RADIO_TO_TEST_T_TAILS") else button.text()
        print(f"Selected t-test tails: {tails}")
        uistate.test_t_tails = tails
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def test_wilcox_variant_changed(self, button):
        variant = self._RADIO_TO_TEST_WILCOX_VARIANT.get(button.objectName(), button.text()) if hasattr(self, "_RADIO_TO_TEST_WILCOX_VARIANT") else button.text()
        print(f"Selected Wilcoxon variant: {variant}")
        uistate.test_wilcox_variant = variant
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def test_wilcox_tails_changed(self, button):
        tails = self._RADIO_TO_TEST_WILCOX_TAILS.get(button.objectName(), button.text()) if hasattr(self, "_RADIO_TO_TEST_WILCOX_TAILS") else button.text()
        print(f"Selected Wilcoxon tails: {tails}")
        uistate.test_wilcox_tails = tails
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def editTestTOneSampleValue(self, lineEdit):
        self.usage("editTestTOneSampleValue")
        try:
            val = float(lineEdit.text().replace(",", "."))
        except ValueError:
            lineEdit.setText(str(getattr(uistate, "label_test_t_one_sample_value", 0.0)))
            return
        uistate.label_test_t_one_sample_value = val
        print(f"editTestTOneSampleValue: uistate.label_test_t_one_sample_value set to {val}")
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def editTestWilcoxOneSampleValue(self, lineEdit):
        self.usage("editTestWilcoxOneSampleValue")
        try:
            val = float(lineEdit.text().replace(",", "."))
        except ValueError:
            lineEdit.setText(str(getattr(uistate, "label_test_wilcox_one_sample_value", 0.0)))
            return
        uistate.label_test_wilcox_one_sample_value = val
        print(f"editTestWilcoxOneSampleValue: uistate.label_test_wilcox_one_sample_value set to {val}")
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

    def n_unit_changed(self, button):
        """v0.16_n_stats n_unit handler."""
        if button is None:
            return
        n_unit = self._RADIO_TO_TEST_N.get(button.objectName(), "subject") if hasattr(self, "_RADIO_TO_TEST_N") else "subject"
        print(f"Selected n_unit: {n_unit}")
        uistate.buttonGroup_test_n = n_unit
        uistate.save_cfg(projectfolder=self.dict_folders.get("project", None))
        self.update_test()

        # force fresh group means at new n_unit level (clear any prior caches for these groups)
        if hasattr(self, "dict_group_means"):
            for gid in list(self.dd_groups.keys()):
                self.dict_group_means.pop(gid, None)
                for lev in getattr(self, "VALID_LEVELS", ["recording", "slice", "subject"]):
                    self.dict_group_means.pop((gid, lev), None)

        if hasattr(uiplot, "unPlotGroup"):
            uiplot.unPlotGroup()
        for group_ID in list(self.dd_groups.keys()):
            if self.dd_groups[group_ID].get("rec_IDs"):
                dict_group = self.dd_groups[group_ID]
                level = getattr(uistate, "buttonGroup_test_n", "recording")
                group_mean_data = self.get_dfgroupmean(group_ID, level=level)
                x_pos = 1 + list(self.dd_groups.keys()).index(group_ID)
                uiplot.addGroup(group_ID, dict_group, self.V2mV(group_mean_data), x_pos=x_pos)
        self.update_show()
        if hasattr(self, "graphRefresh"):
            self.graphRefresh(reeval_formal_test=False)
        if hasattr(self, "mouseoverUpdate"):
            self.mouseoverUpdate()

        # force canvas redraw so group mean lines / SEM shades update immediately
        for cname in ("canvasMean", "canvasEvent", "canvasOutput"):
            if hasattr(self, cname):
                try:
                    getattr(self, cname).draw_idle()
                except Exception:
                    pass

    def update_experiment_type_radio_buttons(self):
        """Select experiment type radio buttons for the current state."""
        if not hasattr(self, "buttonGroup_type"):
            return
        mode = getattr(uistate, "experiment_type", "time")
        radio_name = self._TYPE_TO_RADIO.get(mode, "radioButton_type_time") if hasattr(self, "_TYPE_TO_RADIO") else None
        if radio_name and hasattr(self, radio_name):
            getattr(self, radio_name).setChecked(True)
