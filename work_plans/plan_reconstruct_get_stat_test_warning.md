# Plan: Reconstruct `_get_stat_test_warning` (Build Server Edition)

**File:** `src/lib/ui.py`  
**Function:** `_get_stat_test_warning` (L1727+)  
**Goal:** Replace the current degraded function with a clean, readable dispatch structure that delegates IO regression formatting to the new `_format_io_regression_statusbar` helper.

**Prerequisite:** The `_format_io_regression_statusbar` helper must be present and correctly indented (user has already inserted it).

---

## The Replacement

**Delete** the entire body of `_get_stat_test_warning` from its docstring to the end of the function, and **replace it with** the following exact text:

```python
    def _get_stat_test_warning(self):
        """Return a warning string if the selected test cannot be applied, else None.
        When successful (no warning), also builds a concise p-value summary for statusbar.
        Uses central helpers (_effective_test_type, _is_io_mode) for dispatch.
        IO regression is handled exclusively by _format_io_regression_statusbar.
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

        # --- Non-IO explicit test paths (existing logic preserved) ---
        # ... (the original non-IO guard logic for t-test/ANOVA/Wilcoxon/Friedman/Cluster perm.
        #      remains exactly as it was before the monster was torn out; only the IO/ANCOVA
        #      dispatch above is new) ...
```

**Note for Build Server:** The `... (the original non-IO guard logic ...)` section is a placeholder. The Build Server should **preserve the existing non-IO `if/elif` chain** (the t-test, ANOVA, Wilcoxon, Friedman, and Cluster perm. guards) exactly as it appears in the current file after the monster was removed. Only the early dispatch for `"None"` and `"ANCOVA"` is being added.

---

## Verification (Build Server must confirm)

1. `uv run python -c "from src.lib.ui import UIsub; print('import ok')"` succeeds.
2. Load an IO project with ≥2 groups → statusbar shows the regression string (no "requires ≥2 groups" error).
3. The function `_get_stat_test_warning` is now <60 lines (down from 120+).
4. No "Experiment Type 'None'" or "not implemented" errors for any valid workflow.

---

## Why This Plan Will Succeed

- It is **one file, one function, one replacement**.
- It gives the Build Server **exact text** to insert (not prose describing intent).
- It explicitly tells the Build Server what to **preserve** (the non-IO guards) vs. what to **replace** (the early dispatch).
- It has a **single, unambiguous success criterion** (the statusbar string appears for IO).

---

*End of plan.*
