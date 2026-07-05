"""stats/ package facade for statistical comparison (Phase 1b).
Re-exports public API from .core so existing imports (ui.py: from . import statistics as stats; stats.compute_statistical_comparison) continue to work unchanged.
No behavior change. See AGENTS.md for thin dispatcher, IO precedence, result contract.
"""

from .core import (
    _aggregate_to_unit_level,
    _apply_assumption_tests,
    # private helpers re-exported for analysis_v3/comments/tests if needed
    _aspect_columns,
    _bh_fdr,
    _compute_io_regression_internal,
    _get_io_xy_pairs,
    _make_get_obs,
    compute_statistical_comparison,
    ttest_per_sweep,
)

__all__ = [
    "compute_statistical_comparison",
    "ttest_per_sweep",
]
