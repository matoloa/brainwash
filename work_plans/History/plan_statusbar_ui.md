# Plan: Clean Experiment Type + Test Statusbar Architecture

> **CANCELLED (2026-07-05)** — Not in scope. Active work is `work_plans/plan_statistics_refactor.md` only (`statistics.py` modular split). Do not edit `ui.py` for statusbar architecture per this plan.

---

## Current Problems (from exploration of ui.py:1700-2000, statistics.py:419-560, and call sites)

- **Sentinel leakage**: "ANCOVA" is used as UI signal in `_effective_test_type()`, forced in `experiment_type_changed()`, passed to `compute_statistical_comparison()` (recently fixed to "ANOVA" in _apply_io_regression), and still appears in guards/comments.
- **Duplicate logic**: `shown_sets` / `use_implicit` / `is_io` computed in multiple places (dispatcher, _get_stat_test_warning, statistics.py). IO implicit ANOVA and regression have overlapping but fragile paths.
- **Side effects in "pure" functions**: `_get_stat_test_warning` sets `uistate.statusbar_state`. `_refresh_test_statusbar` calls it and has debug print. `_get_statusbar_for_current_state` is a stub.
- **Redundant calls**: `experiment_type_changed` does clear + refresh + `apply_statistical_test_if_active()` + explicit `_apply_io_regression()`.
- **Legacy bloat**: Many "Phase 3", "v0.17_io_statusbar_fix", "Debug section fix" comments. `_get_statusbar_for_current_state` is placeholder "until Phase 3".
- **Coverage gaps**: Some combinations (IO with 0 groups, implicit ANOVA without results, test_type=None in non-IO, edge cases in _check_*_applicability) produce no message, wrong warning, or stale statusbar.

Result: Not all experiment_type + test_type combinations produce valid statusbar or appropriate warning. Architecture is fragile for future extensions (PP, new test types).

## Proposed Clean Architecture (Minimal, Incremental, Aligned with AGENTS.md)

**Core Principle**: One source of truth for "what should the statusbar show?" based on `(experiment_type, effective_test_type, formal_test_results, groups/testsets state)`. No sentinels in stats layer. Pure functions. Thin dispatcher. Remove redundancy.

### 1. Central Helpers (Enhance Existing)

- `_is_io_mode()` — keep (already good).
- `_effective_operation()` — new or rename from `_effective_test_type()`: returns "io_regression", "t-test", "ANOVA", "None", etc. (no "ANCOVA" leak).
- `_get_statusbar_for_current_state()` — **make this the true single source**. It:
  - Checks `uistate.formal_test_results` first (for IO regression config).
  - Dispatches to `_format_io_regression_statusbar` or non-IO warning helpers.
  - Sets `uistate.statusbar_state` only as side effect if needed (or return tuple `(state, text)`).
  - Handles all combinations explicitly (IO+no_groups → "select ≥2 groups...", IO+results → full report, non-IO+None → None, etc.).
- Keep `_format_io_regression_statusbar` (already robust for config shapes).

### 2. Stats Layer (statistics.py)

- Keep the recent early IO regression guard (now that sentinel is "ANOVA" it works).
- Remove duplicate `shown_sets`/`use_implicit` calculation lower in function (the hoisted version already covers it).
- Update docstring to remove plan references; point to AGENTS.md.
- Implicit ANOVA branch stays but is now clearly "non-IO fallback or explicit".

### 3. Dispatcher & Event Handlers (ui.py)

- `apply_statistical_test_if_active()`: Pure dispatcher — if "io_regression" (or eff=="ANCOVA"), call `_apply_io_regression()` once. For "None" clear + refresh. Else `_apply_non_io_test()`.
- `experiment_type_changed()` and `test_type_changed()`: Set state, clear `formal_test_results` + `statusbar_state`, call `triggerRefresh()` / `graphRefresh()` / **single** `apply_statistical_test_if_active()`. Remove second explicit call and "redundant but harmless" comment.
- `_refresh_test_statusbar()`: Call `_get_statusbar_for_current_state()` (or keep calling `_get_stat_test_warning` if we merge them). Use returned state/text to set appearance. Remove debug print.

### 4. Statusbar Logic

- Make `_get_stat_test_warning` (or merged `_get_statusbar_for_current_state`) **pure**: return string or None, set state only in caller (`_refresh_test_statusbar`).
- Ensure every path sets one of:
  - `statusbar_state = "info"` + report text (bold)
  - `statusbar_state = "warning"` + specific message (red)
  - `statusbar_state = None` + clear
- IO regression always prefers config from `formal_test_results` (even if results list is empty).

### Trade-offs Considered

- **Minimal sentinel fix (already done)** vs full refactor: We have the tactical win. Now do the cleanup to prevent regression.
- Big bang vs incremental: Incremental (helpers first, then dispatcher, then remove duplicates). Use `check-work` after each.
- New `effective_operation` enum vs string: Keep strings for simplicity (no new types).
- Remove `_apply_io_regression` entirely? Deferred — it encapsulates IO-specific params (amp=True, slope=True, n_unit); keep for now.

### Implementation Strategy (Small Edits)

1. Enhance `_get_statusbar_for_current_state` to be the real dispatcher (use existing `_format_io_regression_statusbar` and non-IO helpers).
2. Update `_get_stat_test_warning` to delegate to it or merge (remove duplication).
3. Clean `apply_statistical_test_if_active`, event handlers, and statistics.py docstrings/comments (remove Phase/DEBUG/plan references).
4. Verify all combinations with test project (IO with/without groups, non-IO None/explicit tests, implicit ANOVA).
5. Use `check-work` skill after major sections.

This will make all combinations predictable, reduce context bloat, eliminate legacy comments, and make future test types easy to add. Total change ~60-80 LOC, but in small verifiable steps.