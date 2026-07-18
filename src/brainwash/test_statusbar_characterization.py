"""Characterization tests for brainwash_ui.statusbar formatters."""

from brainwash_ui.statusbar import (
    format_io_ancova_assumption_prose,
    format_io_ancova_methods_text,
    format_io_regression_statusbar,
    format_non_io_stat_test_statusbar,
)


def test_io_regression_statusbar_with_slope_p_and_r2():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 3, "G2": 4},
                "slope_p": 0.042,
                "primary_contrast": "slope_interaction",
                "slope_per_group": {"G1": 1.02, "G2": 0.41},
                "r2_per_group": {"G1": 0.87, "G2": 0.74},
                "n_unit": "subject",
            }
        }
    ]
    dd_groups = {"G1": {"group_name": "Control"}, "G2": {"group_name": "Drug"}}
    result = format_io_regression_statusbar(formal, dd_groups=dd_groups, n_unit="subject")
    assert result.state == "info"
    assert result.text is not None
    assert "IO ANCOVA" in result.text
    assert "Control=3" in result.text
    assert "Drug=4" in result.text
    assert "slopes differ" in result.text
    assert "slope(Control)=1.02 r²=0.87" in result.text
    assert "slope(Drug)=0.41 r²=0.74" in result.text
    # r² immediately after its slope; no orphan r²(id)= form
    assert "r²(G1)" not in result.text
    assert result.text.index("slope(Control)") < result.text.index("r²=0.87")
    assert result.text.index("r²=0.87") < result.text.index("slope(Drug)")


def test_io_ancova_statusbar_group_adjusted_includes_slope_r2_pairs():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 3, "G2": 4},
                "primary_contrast": "group_adjusted",
                "p_group_ancova": 0.01,
                "p_interaction": 0.4,
                "slope_per_group": {"G1": 1.0, "G2": 0.98},
                "r2_per_group": {"G1": 0.91, "G2": 0.89},
            }
        }
    ]
    dd_groups = {"G1": {"group_name": "Ctl"}, "G2": {"group_name": "Tx"}}
    result = format_io_regression_statusbar(formal, dd_groups=dd_groups, n_unit="subject")
    assert "group p=" in (result.text or "")
    assert "slopes OK" in (result.text or "")
    assert "slope(Ctl)=1 r²=0.91" in (result.text or "")
    assert "slope(Tx)=0.98 r²=0.89" in (result.text or "")


def test_io_regression_statusbar_accepts_legacy_type():
    formal = [
        {
            "config": {
                "type": "IO regression",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {},
                "r2_per_group": {},
            }
        }
    ]
    result = format_io_regression_statusbar(formal, dd_groups={})
    assert result.state == "info"
    assert "IO ANCOVA" in (result.text or "")


def test_io_regression_statusbar_missing_config():
    result = format_io_regression_statusbar([{"config": {"type": "t-test"}}], dd_groups={})
    assert result.text == "IO ANCOVA: select ≥2 groups to compute slope comparison"
    assert result.state == "info"


def test_io_regression_statusbar_empty():
    # Never blank under IO+ANCOVA path — empty formal means "not enough data yet".
    result = format_io_regression_statusbar(None, dd_groups={})
    assert result.text == "IO ANCOVA: select ≥2 groups to compute slope comparison"
    assert result.state == "info"


def test_io_regression_statusbar_error_stub():
    result = format_io_regression_statusbar(
        [{"config": {"type": "IO ANCOVA", "error": "need at least two shown groups"}}],
        dd_groups={},
    )
    assert result.state == "warning"
    assert "need at least two shown groups" in (result.text or "")


def test_io_statusbar_spells_out_warning_for_assumption_notes():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2},
                "primary_contrast": "group_adjusted",
                "p_group_ancova": 0.01,
                "p_interaction": 0.5,
                "slope_per_group": {"G1": 1.0},
                "r2_per_group": {"G1": 0.9},
                "assumptions": {"notes": ["SW residual p=0.02"], "sw_p": 0.02},
            }
        }
    ]
    result = format_io_regression_statusbar(formal, dd_groups={"G1": {"group_name": "Ctl"}})
    assert " - Warning: SW residual p=0.02" in (result.text or "")
    assert "warn:" not in (result.text or "")
    assert "SW:ok" not in (result.text or "")


def test_io_statusbar_sw_lev_ok_stamps():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2, "G2": 2},
                "primary_contrast": "group_adjusted",
                "p_group_ancova": 0.01,
                "p_interaction": 0.5,
                "slope_per_group": {"G1": 1.0, "G2": 1.0},
                "r2_per_group": {"G1": 0.9, "G2": 0.9},
                "assumptions": {"notes": [], "sw_p": 0.4, "levene_p": 0.6},
            }
        }
    ]
    result = format_io_regression_statusbar(
        formal, dd_groups={"G1": {"group_name": "A"}, "G2": {"group_name": "B"}}
    )
    assert "SW:ok" in (result.text or "")
    assert "Lev:ok" in (result.text or "")
    assert " - Warning:" not in (result.text or "")


def test_non_io_statusbar_sw_lev_ok_not_bare_labels():
    formal = [
        {
            "set_name": "T1",
            "p_amp": 0.01,
            "n1": 5,
            "n2": 5,
            "sw_p_amp": 0.3,
            "levene_p_amp": 0.4,
        }
    ]
    result = format_non_io_stat_test_statusbar(
        formal,
        effective_test_type="t-test",
        dd_groups={"G1": {"group_name": "A"}, "G2": {"group_name": "B"}},
        test_sw=True,
        test_levene=True,
    )
    assert "SW:ok" in (result.text or "")
    assert "Lev:ok" in (result.text or "")
    assert "SW:on" not in (result.text or "")
    assert "Levene" not in (result.text or "")


def test_non_io_skip_stamps_when_n_too_small():
    """Checkbox on, skip reasons from compute → SW:n<3 / Lev:n<2 (not silent, not SW:on)."""
    formal = [
        {
            "set_name": "T1",
            "p_amp": 0.01,
            "n1": 2,
            "n2": 2,
            "sw_skip_amp": "n=2<3",
            "levene_skip_amp": "n<2 per group",
        }
    ]
    result = format_non_io_stat_test_statusbar(
        formal,
        effective_test_type="t-test",
        dd_groups={},
        test_sw=True,
        test_levene=True,
    )
    assert "SW:n<3" in (result.text or "")
    assert "Lev:n<2" in (result.text or "")
    assert "SW:on" not in (result.text or "")


def test_format_io_ancova_assumption_prose_nonnormal():
    text = format_io_ancova_assumption_prose(
        {"sw_p": 0.01, "levene_p": 0.4, "notes": ["SW residual p=0.01"]}
    )
    assert "vertical distances" in text
    assert "non-normal residual distribution" in text
    assert "0.01" in text or "<0.001" in text


def test_io_ancova_methods_text_group_adjusted():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 3, "G2": 4},
                "p_interaction": 0.4,
                "p_group_ancova": 0.01,
                "p_covariate": 0.001,
                "primary_contrast": "group_adjusted",
                "slopes_homogeneous": True,
                "force_through_zero": False,
                "alpha_slopes": 0.05,
                "assumptions": {"notes": []},
            }
        }
    ]
    text = format_io_ancova_methods_text(formal, dd_groups={"G1": {"group_name": "Ctl"}, "G2": {"group_name": "Tx"}})
    assert "ANCOVA" in text
    assert "Homogeneity of regression slopes" in text
    assert "group effect adjusted" in text
    assert "Ctl n=3" in text


def test_io_ancova_methods_text_heterogeneous():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 2, "G2": 2},
                "p_interaction": 0.001,
                "primary_contrast": "slope_interaction",
                "slopes_homogeneous": False,
                "slope_per_group": {"G1": 1.0, "G2": 2.0},
                "alpha_slopes": 0.05,
                "assumptions": {},
            }
        }
    ]
    text = format_io_ancova_methods_text(formal, dd_groups={})
    assert "differed across groups" in text
    assert "Per-group slopes" in text


def test_non_io_ttest_statusbar_p_values():
    formal = [
        {
            "group1": "G1",
            "group2": "G2",
            "n1": 5,
            "n2": 6,
            "p_amp": 0.03,
            "p_slope": 0.0005,
        }
    ]
    dd_groups = {"G1": {"group_name": "A"}, "G2": {"group_name": "B"}}
    result = format_non_io_stat_test_statusbar(
        formal,
        effective_test_type="t-test",
        dd_groups=dd_groups,
        ttest_variant="unpaired",
    )
    assert result.state == "info"
    assert "t-test (unpaired)" in result.text
    assert "A=5" in result.text
    assert "B=6" in result.text
    assert "amp: p=0.03" in result.text
    assert "slope: p=<0.001" in result.text


def test_non_io_empty_formal():
    result = format_non_io_stat_test_statusbar(None, effective_test_type="ANOVA", dd_groups={})
    assert result.text is None