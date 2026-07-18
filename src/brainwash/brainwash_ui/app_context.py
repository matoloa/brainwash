"""Snapshot types and pure statusbar dispatch from bounded UI state (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass

from . import applicability, statusbar

_IMPLEMENTED_TEST_TYPES = frozenset({"t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."})
# IO regression is driven by experiment_type; only ANCOVA (or no test) is appropriate.
_IO_ALLOWED_TEST_TYPES = frozenset({"ANCOVA", "None"})


@dataclass(frozen=True)
class ExperimentSnapshot:
    experiment_type: str


@dataclass(frozen=True)
class StatTestSnapshot:
    test_type: str
    formal_test_results: object
    buttonGroup_test_n: str
    test_t_variant: str
    test_wilcox_variant: str
    test_fdr: bool
    test_sw: bool
    test_levene: bool


def experiment_snapshot_from(uistate) -> ExperimentSnapshot:
    return ExperimentSnapshot(experiment_type=uistate.experiment.experiment_type)


def stat_test_snapshot_from(uistate) -> StatTestSnapshot:
    st = uistate.stat_test
    return StatTestSnapshot(
        test_type=st.test_type,
        formal_test_results=st.formal_test_results,
        buttonGroup_test_n=st.buttonGroup_test_n,
        test_t_variant=st.test_t_variant,
        test_wilcox_variant=st.test_wilcox_variant,
        test_fdr=bool(st.test_fdr),
        test_sw=bool(st.test_sw),
        test_levene=bool(st.test_levene),
    )


def compute_statusbar_result(
    *,
    experiment: ExperimentSnapshot,
    stat_test: StatTestSnapshot,
    dd_groups: dict | None,
    dd_testsets: dict | None,
) -> statusbar.StatusbarResult:
    if stat_test.test_type == "None" and experiment.experiment_type != "io":
        return statusbar.StatusbarResult(None, None)
    if experiment.experiment_type == "io":
        if stat_test.test_type not in _IO_ALLOWED_TEST_TYPES:
            return statusbar.StatusbarResult(
                "Use ANCOVA for Input-Output experiment analysis",
                "warning",
            )
        return statusbar.format_io_regression_statusbar(
            stat_test.formal_test_results,
            dd_groups=dd_groups or {},
            n_unit=stat_test.buttonGroup_test_n,
        )
    test_type = stat_test.test_type
    if test_type == "None":
        return statusbar.StatusbarResult(None, None)
    if test_type not in _IMPLEMENTED_TEST_TYPES:
        return statusbar.StatusbarResult(f"Statistical test '{test_type}' is not implemented", "warning")
    warning = applicability.warning_for_test_type(
        test_type,
        dd_groups=dd_groups,
        dd_testsets=dd_testsets,
        ttest_variant=stat_test.test_t_variant,
        wilcox_variant=stat_test.test_wilcox_variant,
    )
    if warning is not None:
        return statusbar.StatusbarResult(warning, "warning")
    if stat_test.formal_test_results:
        result = statusbar.format_non_io_stat_test_statusbar(
            stat_test.formal_test_results,
            effective_test_type=test_type,
            dd_groups=dd_groups or {},
            n_unit=stat_test.buttonGroup_test_n,
            ttest_variant=stat_test.test_t_variant,
            wilcox_variant=stat_test.test_wilcox_variant,
            test_fdr=stat_test.test_fdr,
            test_sw=stat_test.test_sw,
            test_levene=stat_test.test_levene,
        )
        if result.text:
            return result
    return statusbar.StatusbarResult(None, None)