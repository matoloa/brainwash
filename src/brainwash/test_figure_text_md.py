"""Characterization: journal figure-text skeleton (.md companion)."""

from export_image import (
    JournalTemplate,
    build_figure_text_md,
    resolve_export_template_key,
    resolve_journal_export_key,
    _figure_text_force0_warning,
    _figure_text_paired_drop_warning,
    _figure_text_unit_warning,
)
from ui_state_classes import UIstate


def _template():
    return JournalTemplate(name="test", width_mm=85, height_mm=60)


def test_unit_warning_only_for_slice_and_recording():
    assert _figure_text_unit_warning("subject") is None
    w_slice = _figure_text_unit_warning("slice")
    assert w_slice is not None
    assert "slice" in w_slice
    assert "not subjects" in w_slice
    assert "animal" in w_slice  # example in parenthetical only
    assert "donor" in w_slice
    assert "culture line" in w_slice
    # Prefer subject language, not leading with Animal as unit name
    assert "**animal**" not in w_slice.lower()
    w_rec = _figure_text_unit_warning("recording")
    assert w_rec is not None and "recording" in w_rec


def test_paired_drop_warning_lists_units_and_rule():
    assert _figure_text_paired_drop_warning([]) is None
    assert _figure_text_paired_drop_warning([{"n_dropped": 0}]) is None
    w = _figure_text_paired_drop_warning(
        [
            {
                "n_dropped": 2,
                "n_pairs": 5,
                "paired_dropped": [
                    {"unit": "s3", "reason": "no finite value in test set 2 (present only in test set 1)"},
                    {"unit": "s4", "reason": "no finite value in test set 1 (present only in test set 2)"},
                ],
            }
        ]
    )
    assert w is not None
    assert "complete cases only" in w
    assert "2" in w and "5" in w
    assert "`s3`" in w and "`s4`" in w
    assert "test set 2" in w


def test_skeleton_paired_includes_incomplete_pair_note():
    u = UIstate()
    u.stat_test.test_type = "t-test"
    u.stat_test.test_t_variant = "paired"
    u.stat_test.buttonGroup_test_n = "subject"
    u.stat_test.formal_test_results = [
        {
            "set_name": "pre vs post",
            "sweeps": [1, 2],
            "sweeps2": [10, 11],
            "p_amp": 0.02,
            "n1": 5,
            "n2": 5,
            "n_pairs": 5,
            "n_dropped": 1,
            "paired_dropped": [
                {"unit": "s9", "reason": "no finite value in test set 2 (present only in test set 1)"},
            ],
            "group1": "G1",
        }
    ]
    md = build_figure_text_md(u, _template(), group_names={"G1": "Ctl"}, panel_hint="amplitude")
    assert "Note on incomplete pairs" in md
    assert "complete cases only" in md
    assert "`s9`" in md
    assert "statusbar" not in md.lower()


def test_skeleton_no_test_still_structured():
    u = UIstate()
    u.stat_test.test_type = "None"
    md = build_figure_text_md(u, _template(), group_names={"1": "Ctl"}, panel_hint="amplitude")
    assert md.startswith("# Figure text skeleton")
    assert "## Caption draft" in md
    assert "### Statistics" in md
    assert "No formal statistical comparison" in md
    assert "[EPSP amplitude" in md


def test_skeleton_ttest_includes_p_and_checklist():
    u = UIstate()
    u.experiment.experiment_type = "time"
    u.stat_test.test_type = "t-test"
    u.stat_test.test_t_variant = "unpaired"
    u.stat_test.test_t_tails = "two-sided"
    u.stat_test.buttonGroup_test_n = "subject"
    u.stat_test.test_sw = True
    u.stat_test.test_levene = True
    u.stat_test.formal_test_results = [
        {
            "set_name": "post",
            "sweeps": [45, 50, 60],
            "p_amp": 0.012,
            "p_slope": 0.04,
            "n1": 6,
            "n2": 7,
            "group_ns": {"G1": 6, "G2": 7},
            "group1": "G1",
            "group2": "G2",
            "sw_p_amp_g1": 0.4,
            "sw_p_amp_g2": 0.35,
            "levene_p_amp": 0.2,
            "sw_p_slope_g1": 0.01,
            "sw_skip_slope_g2": "n=2<3",
            "levene_skip_slope": "n<2 per group",
        }
    ]
    md = build_figure_text_md(
        u,
        _template(),
        group_names={"G1": "Control", "G2": "Drug"},
        panel_hint="amplitude",
    )
    assert "Student's *t*-test" in md or "t*-test" in md
    assert "subject" in md
    assert "Control" in md and "Drug" in md
    assert "0.012" in md
    assert "### Symbols" in md
    assert "### Checklist" in md
    assert "Set `post`" in md
    assert "### Assumption checks" in md
    assert "Shapiro–Wilk" in md
    assert "Levene" in md
    assert "per group" in md.lower() or "Control" in md
    assert "group-1" not in md  # no longer only g1 wording
    assert "statusbar" not in md.lower()
    assert "console" not in md.lower()
    # no aggressive truncation
    assert len(md) > 200
    assert _figure_text_unit_warning("subject") is None
    assert "Note on statistical units" not in md


def test_skeleton_ttest_sw_skip_reported_in_md():
    u = UIstate()
    u.stat_test.test_type = "t-test"
    u.stat_test.test_sw = True
    u.stat_test.test_levene = True
    u.stat_test.formal_test_results = [
        {
            "set_name": "set 2",
            "group1": "G1",
            "group2": "G2",
            "p_slope": 0.09,
            "n1": 2,
            "n2": 2,
            "sw_skip_slope_g1": "n=2<3",
            "sw_skip_slope_g2": "n=2<3",
            "levene_p_slope": 0.4,
        }
    ]
    md = build_figure_text_md(u, _template(), group_names={"G1": "A", "G2": "B"})
    assert "### Assumption checks" in md
    assert "not computed" in md.lower() or "n=2" in md
    assert "A" in md or "B" in md or "group" in md.lower()
    assert "statusbar" not in md.lower()


def test_skeleton_slice_n_unit_leads_with_warning():
    u = UIstate()
    u.stat_test.test_type = "t-test"
    u.stat_test.buttonGroup_test_n = "slice"
    u.stat_test.formal_test_results = [
        {"set_name": "T1", "p_amp": 0.03, "n1": 4, "n2": 4, "group_ns": {"1": 4, "2": 4}}
    ]
    md = build_figure_text_md(u, _template(), group_names={"1": "A", "2": "B"})
    assert md.index("Note on statistical units") < md.index("## Caption draft")
    assert "**slice**" in md
    assert "not subjects" in md


def test_force0_warning_helper():
    assert _figure_text_force0_warning(force0=False) is None
    assert _figure_text_force0_warning(force0=True, exp_type="time") is None
    w = _figure_text_force0_warning(force0=True, exp_type="io")
    assert w is not None
    assert "origin" in w.lower()
    assert "io_force0" in w


def test_skeleton_io_force0_under_unit_warning():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "ANCOVA"
    u.stat_test.buttonGroup_test_n = "recording"
    u.project.checkBox["io_force0"] = True
    u.stat_test.formal_test_results = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2, "G2": 2},
                "primary_contrast": "slope_interaction",
                "force_through_zero": True,
                "p_interaction": 0.01,
                "slope_per_group": {},
                "r2_per_group": {},
            }
        }
    ]
    md = build_figure_text_md(u, _template(), group_names={"G1": "A", "G2": "B"}, panel_hint="io")
    assert "Note on statistical units" in md
    assert "Note on forced-through-origin" in md
    assert md.index("Note on statistical units") < md.index("Note on forced-through-origin")
    assert md.index("Note on forced-through-origin") < md.index("## Caption draft")


def test_resolve_journal_export_none_key_defaults_jneurosci():
    assert resolve_journal_export_key(None) == "jneurosci"
    assert resolve_journal_export_key({"journal_export": None}) == "jneurosci"
    assert resolve_journal_export_key({"journal_export": "None"}) == "jneurosci"
    assert resolve_export_template_key({"journal_export": None}, "1col") == "jneurosci_1col"
    assert resolve_export_template_key(None, "2col") == "jneurosci_2col"
    assert resolve_journal_export_key("nature") == "nature"
    assert resolve_export_template_key("nature", "1col") == "nature_1col"


def test_skeleton_io_ancova_uses_methods_and_group_names():
    u = UIstate()
    u.experiment.experiment_type = "io"
    u.stat_test.test_type = "ANCOVA"
    u.stat_test.buttonGroup_test_n = "subject"
    u.stat_test.formal_test_results = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 3, "G2": 4},
                "primary_contrast": "group_adjusted",
                "slopes_homogeneous": True,
                "p_interaction": 0.4,
                "p_group_ancova": 0.01,
                "p_covariate": 0.001,
                "slope_per_group": {"G1": 1.0, "G2": 0.9},
                "r2_per_group": {"G1": 0.9, "G2": 0.85},
                "assumptions": {
                    "sw_p": 0.01,
                    "levene_p": 0.4,
                    "notes": ["SW residual p=0.01"],
                },
            }
        }
    ]
    md = build_figure_text_md(
        u,
        _template(),
        group_names={"G1": "Ctl", "G2": "Tx"},
        panel_hint="vamp-EPSPamp",
    )
    assert "ANCOVA" in md
    assert "Ctl" in md or "subject" in md
    assert "Per-group fits" in md or "slope" in md.lower()
    assert "### Checklist" in md
    assert "### Assumption checks" in md
    assert "Residuals are the vertical distances" in md
    assert "non-normal residual distribution" in md
    assert "statusbar" not in md.lower()
