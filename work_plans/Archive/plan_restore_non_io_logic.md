# Plan: Restore Non-IO Guard Logic with Modular Helpers

**File:** `src/lib/ui.py`  
**Goal:** Populate the non-IO placeholder logic in the current clean skeleton of `_get_stat_test_warning` with the original guard checks, organized into small, single-purpose helper functions to keep the master function short and readable.

**Prerequisite:** The current clean dispatch structure (`if eff == "None"`, `if eff == "ANCOVA"`, `if eff not in (...)`) must be in place.

---

## Strategy

Replace the long, monolithic chain of `if/elif` guards with a **dispatch + helper** pattern.

- The master function (`_get_stat_test_warning`) remains short (< 30 lines).
- Each test type (t-test, ANOVA, etc.) gets its own **small helper method** (< 15 lines).
- This eliminates the "monster" architecture while restoring the lost functionality.

---

## Implementation Steps

### Step 1: Create the Helper Methods

Add the following **private methods** to `UIsub` (place them near `_format_io_regression_statusbar`).

**1.1. `_check_ttest_applicability(self, variant: str) -> str | None`**
- Checks for 1 or 2 groups, N≥2 for paired, etc.
- Returns a warning string or `None` if valid.

**1.2. `_check_anova_applicability(self) -> str | None`**
- Checks for ≥2 groups or 1 group + ≥2 test sets.
- Returns a warning string or `None` if valid.

**1.3. `_check_wilcoxon_applicability(self, variant: str) -> str | None`**
- Checks for 1 or 2 groups, N≥2 for paired, etc.
- Returns a warning string or `None` if valid.

**1.4. `_check_friedman_applicability(self) -> str | None`**
- Checks for ≥3 test sets for repeated-measures.
- Returns a warning string or `None` if valid.

**1.5. `_check_cluster_applicability(self) -> str | None`**
- Checks for ≥2 groups or 1 group + 2 test sets.
- Returns a warning string or `None` if valid.

**Note:** These helpers should use the existing `self._get_shown_group_ids()` and `self._get_shown_testsets()` methods.

### Step 2: Update the Master Dispatch

Modify the placeholder section in `_get_stat_test_warning` (after the `if eff not in (...)` guard) to dispatch to the new helpers:

```python
        # --- Non-IO explicit test paths (modular) ---
        if eff == "t-test":
            variant = getattr(uistate, "test_t_variant", "unpaired")
            return self._check_ttest_applicability(variant)
        if eff == "ANOVA":
            return self._check_anova_applicability()
        if eff == "Wilcoxon":
            variant = getattr(uistate, "test_wilcox_variant", "paired")
            return self._check_wilcoxon_applicability(variant)
        if eff == "Friedman":
            return self._check_friedman_applicability()
        if eff == "Cluster perm.":
            return self._check_cluster_applicability()
        
        return None # Fallback
```

### Step 3: (Optional) Result Formatting

If the applicability checks pass (return `None`), the function should proceed to generate the success string (p-values, effect sizes). This logic can remain in the main function or be moved to a separate `_format_test_result` helper if it is also long.

---

## File Summary

| File              | Change                                           | LOC  | Risk |
|-------------------|--------------------------------------------------|------|------|
| `src/lib/ui.py`   | Add 5 small helper methods (`_check_*_applicability`) | ~50  | Low  |
| `src/lib/ui.py`   | Update dispatch logic in `_get_stat_test_warning`    | ~10  | Low  |

**Total:** ~60 LOC of new, clean, testable code. Replaces the 100+ line monster with a dispatch + 5 helpers.

---

*End of plan.*
