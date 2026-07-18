"""Characterization tests for brainwash_ui.statusbar formatters."""

from brainwash_ui.statusbar import format_io_regression_statusbar, format_non_io_stat_test_statusbar


def test_io_regression_statusbar_with_slope_p_and_r2():
    formal = [
        {
            "config": {
                "type": "IO ANCOVA",
                "x_col": "volley_amp",
                "y_col": "EPSP_amp",
                "group_ns": {"G1": 3, "G2": 4},
                "slope_p": 0.042,
                "r2_per_group": {"G1": 0.87},
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
    assert "ratio p=" in result.text
    assert "r²(G1)=0.87" in result.text


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


def test_io_regression_statusbar_empty():
    result = format_io_regression_statusbar(None, dd_groups={})
    assert result.text is None
    assert result.state is None


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