# Plan: Reconstruct `_get_stat_test_warning` (Build Server Edition — Surgical, Clarified)

**File:** `src/lib/ui.py`  
**Target:** The body of `_get_stat_test_warning` only (NOT the rest of the file).  
**Goal:** Replace the current degraded function body with a clean, readable dispatch structure. This structure delegates IO regression formatting to the `_format_io_regression_statusbar` helper and leaves a clear, marked placeholder for the non-IO logic to be restored later.

**Prerequisite:** The `_format_io_regression_statusbar` helper must be present and correctly indented.

**Critical Safeguard:**

> **Do not delete any lines before `def _get_stat_test_warning(self):` or after the final `return` of that function. The replacement must be a 1:1 swap of the function body only. If you are unsure of the exact line range, stop and ask for clarification.**

---

## Exact `edit_file` Parameters

**old_text (the entire current body of the function, starting from the docstring):**

```python
    def _get_stat_test_warning(self):
        """Return a warning string if the selected test cannot be applied, else None.
        When successful (no warning), also builds a concise p-value summary for statusbar.
        Uses central helpers (_effective_test_type, _is_io_mode) for dispatch.
        IO regression is handled exclusively by _format_io_regression_statusbar.
        """
        eff = self._effective_test_type()
        print(f"DEBUG _get_stat_test_warning: eff={eff}, test_type={getattr(uistate, 'test_type', None)}, experiment_type={getattr(uistate, 'experiment_type', None)}")
        if eff == "None":
            uistate.statusbar_state = None
            return None

        if eff == "ANCOVA":
            # IO regression: always short-circuit here. Never reaches ANOVA/Friedman/Cluster guards.
            return self._format_io_regression_statusbar(getattr(uistate, "formal_test_results", None))
        print("DEBUG: Reached past ANCOVA block (should not happen)")
        if eff not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.", "ANCOVA"):
            uistate.statusbar_state = "warning"
            return f"Statistical test '{eff}' is not implemented"

        # --- Non-IO explicit test paths (existing logic preserved) ---
        # ... (the original non-IO guard logic for t-test/ANOVA/Wilcoxon/Friedman/Cluster perm.
        #      remains exactly as it was before the monster was torn out; only the IO/ANCOVA
        #      dispatch above is new) ...
```

**new_text (exact replacement — the clean, final structure):**

```python
    def _get_stat_test_warning(self):
        """Return a warning string if the selected test cannot be applied, else None.
        When successful (no warning), also builds a concise p-value summary for statusbar.
        Uses central helpers (_effective_test_type, _is_io_mode) for dispatch.
        IO regression is handled exclusively by _format_io_regression_statusbar.
        Non-IO logic is restored via helpers in a subsequent phase.
        """
        eff = self._effective_test_type()
        if eff == "None":
            uistate.statusbar_state = None
            return None

        if eff == "ANCOVA":
            # IO regression: always short-circuit here. Never reaches ANOVA/Friedman/Cluster guards.
            return self._format_io_regression_statusbar(
                getattr(uistate, "formal_test_results", None)
            )

        if eff not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.", "ANCOVA"):
            uistate.statusbar_state = "warning"
            return f"Statistical test '{eff}' is not implemented"

        # --- Non-IO explicit test paths ---
        # Placeholder: The original non-IO guard logic (t-test, ANOVA, etc.) will be
        # restored here in a subsequent phase using dedicated helper methods
        # (_check_ttest_applicability, etc.) to keep this function short.
        return None
```

---

## Verification (Build Server must confirm)

1.  `uv run python -c "from src.lib.ui import UIsub; print('import ok')"` succeeds.
2.  The function `_get_stat_test_warning` is now < 30 lines.
3.  Debug prints are removed.
4.  No "Experiment Type 'None'" or "not implemented" errors for any valid workflow.

---

_End of plan._
