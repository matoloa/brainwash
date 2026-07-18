"""Characterization: journal figure-text skeleton (.md companion)."""

from export_image import (
    JournalTemplate,
    build_figure_text_md,
    resolve_export_template_key,
    resolve_journal_export_key,
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
    u.stat_test.formal_test_results = [
        {
            "set_name": "post",
            "sweeps": [45, 50, 60],
            "p_amp": 0.012,
            "p_slope": 0.04,
            "n1": 6,
            "n2": 7,
            "group_ns": {"G1": 6, "G2": 7},
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
    # no aggressive truncation
    assert len(md) > 200
    assert _figure_text_unit_warning("subject") is None
    assert "Note on statistical units" not in md


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
