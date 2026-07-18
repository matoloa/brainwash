# plan_IO1.md — IO Regression Statusbar Fix

## Problem Statement

When the user switches `experiment_type` to `"io"`, the statusbar displays nothing (or a misleading hint) instead of the IO regression results (slope p-value, r² per group, n_report).

## Root Cause (Confirmed by Execution Trace)

**File:** `src/lib/statistics.py`, line 458

```python
if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
    return {"not_implemented": test_type, "results": []}
```

**Execution path from `experiment_type_changed` (ui.py:2972):**

1. Sets `uistate.experiment_type = "io"`, `uistate.test_type = "ANCOVA"`
2. Calls `apply_statistical_test_if_active()` → `_effective_test_type()` returns `"ANCOVA"`
3. Dispatcher routes to `_apply_io_regression()` (ui.py:1982)
4. `_apply_io_regression()` calls:
   ```python
   comp = stats.compute_statistical_comparison(
       ...,
       test_type="ANCOVA",        # ← sentinel for UI, not a real test type
       experiment_type="io",
   )
   ```
5. `compute_statistical_comparison` rejects `"ANCOVA"` at the entry guard (L458) **before** the IO regression guard at L512 can run.
6. Returns `{"not_implemented": "ANCOVA", "results": []}`
7. `_apply_io_regression` sets `formal_test_results = []`, `statusbar_state = "info"`
8. `_refresh_test_statusbar()` calls `_get_stat_test_warning()` → `_format_io_regression_statusbar([])`
9. Empty `formal` → sets `statusbar_state = None`, returns hint string
10. Statusbar shows hint or clears — never the regression report

## Why `test_type="ANCOVA"` Was Passed

- `uistate.test_type` is forced to `"ANCOVA"` in `experiment_type_changed` (ui.py:2985) when `exp_type == "io"`
- `_effective_test_type()` returns `"ANCOVA"` for IO (architectural invariant)
- `_apply_io_regression` reuses `test_type = "ANCOVA"` from `uistate.test_type`

The IO regression path in `compute_statistical_comparison` (L512) only checks `experiment_type == "io"` and `use_implicit`; it does **not** use `test_type`. The guard at L458 runs first and short-circuits.

## Design Constraints

- Keep `_get_stat_test_warning` pure (no side effects, no `_refresh_test_statusbar` calls)
- Keep `apply_statistical_test_if_active` as a thin dispatcher
- `_apply_io_regression` is the dedicated IO helper (already calls `compute_statistical_comparison(experiment_type="io")`)
- `uistate` recovery via `get_group_testset_means_fn.__self__` works for `df_project`/`get_dfoutput` access

## Implementation Plan

### Change 1: `src/lib/ui.py` — `_apply_io_regression` (L1775)

**Problem:** Passes `test_type="ANCOVA"` which is rejected by the guard.

**Fix:** Pass a valid `test_type` (e.g., `"ANOVA"`) since the IO regression branch (L512) ignores `test_type` and only branches on `experiment_type="io"`.

```python
def _apply_io_regression(self) -> bool:
    ...
    test_type = "ANOVA"  # Valid sentinel; IO path uses experiment_type="io", not test_type
    ...
    comp = stats.compute_statistical_comparison(
        ...,
        test_type=test_type,  # Now passes "ANOVA", not "ANCOVA"
        ...
        experiment_type=experiment_type,  # "io" triggers regression
    )
    ...
```

**Rationale:** The IO regression internal (`_compute_io_regression_internal`) computes linregress + OLS slope interaction; it does not dispatch on `test_type`. Using `"ANOVA"` (or any value from the allowed set) bypasses the guard while preserving the `experiment_type="io"` signal.

**Alternative (if preferred):** Pass `test_type=None` and adjust the guard to allow `None` when `experiment_type == "io"`. This is slightly more explicit but requires a statistics.py change.

### Change 2 (Optional Safety): `src/lib/statistics.py` — Guard at L458

If a more defensive fix is desired, reorder the IO check before the `test_type` guard:

```python
# Early exit for IO implicit regression (bypasses test_type validation)
is_io = experiment_type == "io"
shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]
use_implicit = not shown_sets and is_io
if is_io and use_implicit:
    if uistate is None:
        uistate = getattr(get_group_testset_means_fn, "__self__", None)
    return _compute_io_regression_internal(...)

# Existing guard (now only reached for non-IO paths)
if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
    return {"not_implemented": test_type, "results": []}
```

**Rationale:** Makes the IO path independent of `test_type` at the entry point. The current code already has `is_io`/`use_implicit` computed later (L499-503); hoisting the early return is minimal and explicit.

### No Changes Required

- `ui.py:experiment_type_changed` — already correctly sets `test_type="ANCOVA"`, calls `apply_statistical_test_if_active()`, then explicitly calls `_apply_io_regression()` as a safety net. The double-call is harmless (idempotent on same data).
- `ui.py:_get_stat_test_warning` — correctly dispatches ANCOVA to `_format_io_regression_statusbar`; remains pure.
- `ui.py:_refresh_test_statusbar` — correctly uses captured `state` + returned `warning` to decide display; no recursion risk.
- `ui.py:_format_io_regression_statusbar` — correctly handles `formal[0].get("config")` or `formal[0]` itself; sets `statusbar_state="info"` on success.

## Validation Steps

1. Launch the app, load a project with ≥2 groups having sweep data.
2. Switch experiment type radio to "IO".
3. Verify:
   - Statusbar shows: `"IO regression (slope p=... r²(G)=... (G=n, ...))"` (or similar)
   - No crash, no `not_implemented` path taken
   - `graphRefresh` and subsequent `_refresh_test_statusbar` calls preserve the report
4. Optional: toggle `io_input`/`io_output` radios; verify statusbar recomputes with new X/Y mapping.

## Notes for Implementer

- The `"ANCOVA"` sentinel is a UI-only convention (forced in `experiment_type_changed`) to signal "IO regression mode" through `_effective_test_type()`. It should not leak into `compute_statistical_comparison`.
- The recovery `uistate = getattr(get_group_testset_means_fn, "__self__", None)` in `compute_statistical_comparison` (L515) correctly obtains the UI instance for `df_project`/`get_dfoutput` access inside `_get_io_xy_pairs`.
- `io_input`/`io_output` attributes live on the global `uistate` object (ui_state_classes), not the UI instance. When the UI instance is passed as the `uistate` parameter, `getattr(uistate, "io_input", "vamp")` falls back to defaults. If preserving the user's radio selection is required, `_apply_io_regression` should pass the real `uistate` module-level object (import or closure capture). For v0.16 this is acceptable fallback behavior; a future refactor can thread the real `uistate` explicitly.
