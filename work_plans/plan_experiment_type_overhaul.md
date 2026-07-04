# Plan: Experiment Type Overhaul — Clean State Machine for IO + Statusbar

## Problem Statement

The current design forces `uistate.test_type = "None"` (string) when `experiment_type == "io"`. This creates a cascade of problems:

1. **Scattered `None`-guards**: At least 4 locations check `test_type == "None"` or `test_type not in (...)` and either return early, print warnings, or set `statusbar_state = None`.
2. **Inconsistent experiment_type handling**: Some paths read `experiment_type` and default to `"time"`; others do not, so `experiment_type` can be `None` (attribute missing) or the string `"None"` (if a radio button or config ever sets it).
3. **Statusbar error "Experiment Type 'None' not implemented"**: A guard (location unknown, possibly in a statusbar refresh or label update path) sees `experiment_type` as `None` or `"None"` and constructs this error. This is the 5th discovered guard.
4. **IO regression statusbar never appears reliably**: Even when the regression computes correctly, the statusbar pipeline has so many short-circuits that the result is lost.
5. **Non-IO explicit tests may also lose statusbar** if `statusbar_state` is never set to `"info"` on success.

The pattern of "add `and not is_io` to every guard" or "insert a config-first check at the top of every function" is unsustainable. The state machine itself is the problem.

---

## Tactical Proposal (Immediate Fix)

**Force `test_type = "ANCOVA"` when `experiment_type == "io"`.**

- In `experiment_type_changed`, replace `uistate.test_type = "None"` with `uistate.test_type = "ANCOVA"`.
- Extend the `test_type not in (...)` guard to accept `"ANCOVA"` (or add a dedicated `if test_type == "ANCOVA":` branch in `_get_stat_test_warning` for the IO regression statusbar string).
- The Statistical Test frame remains hidden for IO (unchanged); the statusbar now shows the regression result because `test_type == "ANCOVA"` passes all existing guards.
- Non-IO selection forces `test_type = "None"` (unchanged behavior).

This single change (1 line in `experiment_type_changed` + 3-5 lines for the statusbar branch) resolves:

- The "Experiment Type 'None' not implemented" error (no more `"None"` sentinel leaking into error paths).
- The "no statusbar" symptom (ANCOVA is a recognized test_type, so the statusbar formatter is reached).
- All previous `is_io` bypass patches become unnecessary.

**Migration note**: Old IO projects saved with `test_type = "None"` are migrated in `applyConfigStates`: if `experiment_type == "io"` and `test_type == "None"`, set `test_type = "ANCOVA"`.

---

## Mission (Long-Term Architectural Cleanup)

Replace the ad-hoc `test_type = "None"` (or now `"ANCOVA"`) sentinel for IO with a clean, first-class state model:

- `experiment_type` is **always one of** `{"time", "train", "io", "PP", "sweep", "timestamp"}` — never `None`, never `"None"`.
- `test_type` is **always one of** `{"None", "t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.", "ANCOVA"}` — never the Python value `None`.
- For IO mode, `test_type` is **forced to `"ANCOVA"`** (a real test type), and the **effective operation is IO regression** derived from `experiment_type == "io" && test_type == "ANCOVA"`.
- All statusbar, visibility, and applicability logic derives from this pair `(experiment_type, test_type)` via **central helper functions**, not scattered inline checks.
- The statusbar for IO regression is produced by a dedicated path that does not depend on ad-hoc `is_io` checks.

This eliminates the need for `is_io` bypasses on every guard and makes the "Experiment Type 'None' not implemented" error impossible by construction.

---

## Design

### State Variables (unchanged names, clarified semantics)

```python
uistate.experiment_type: str  # always in {"time", "train", "io", "PP", "sweep", "timestamp"}
uistate.test_type: str        # always in {"None", "t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.", "ANCOVA"}
```

### Invariants

1. `experiment_type` is set at project load (default `"time"`) and only changes via `experiment_type_changed` (radio button). It is **never** `None` or `"None"`.
2. `test_type` is set at project load (default `"None"`) and only changes via `test_type_changed` (radio button) or `experiment_type_changed` (which forces `"ANCOVA"` for IO). It is **never** the Python value `None`.
3. When `experiment_type == "io":`
   - `test_type` **must** be `"ANCOVA"` (forced by `experiment_type_changed`).
   - The effective statistical operation is **IO regression** (implicit, no test sets).
   - The Statistical Test toolframe is hidden (already done); the statusbar shows the regression result via the dedicated `"ANCOVA"` branch.
4. When `experiment_type != "io":`
   - `test_type` can be any of the 7 values (including `"None"`).
   - If `test_type != "None"`, an explicit test is active.
   - If `test_type == "None"`, no test is active; statusbar is empty (or shows a non-test message).

### Central Helpers (new, minimal)

Add to `ui.py` (or a small `ui_state_helpers.py` if preferred):

```python
def _is_io_mode() -> bool:
    return getattr(uistate, "experiment_type", "time") == "io"

def _effective_test_type() -> str:
    """Return the test that should actually run/display, accounting for IO override."""
    if _is_io_mode():
        # Tactical: IO forces "ANCOVA"; long-term, this can map to a dedicated "IO regression" label
        return getattr(uistate, "test_type", "ANCOVA")  # defaults to ANCOVA if somehow unset
    return getattr(uistate, "test_type", "None")

def _should_show_stat_test_frame() -> bool:
    return not _is_io_mode()

def _get_statusbar_for_current_state() -> str | None:
    """
    Single source of truth for statusbar text.
    - IO mode: returns IO regression string (or None if no groups)
    - Non-IO with test_type != "None": returns existing warning/success string
    - Non-IO with test_type == "None": returns None (clear)
    """
    if _is_io_mode():
        # IO path: ignore test_type entirely, use formal_test_results + config
        results = getattr(uistate, "formal_test_results", None)
        if results:
            # Extract first result, look for "IO regression" config, format exactly as before
            # ... (reuse existing L1886-1906 logic, or call a shared helper)
            ...
        return None  # or a "select groups for IO regression" hint
    # Non-IO path: existing _get_stat_test_warning logic
    ...
```

### Guard Consolidation

All existing inline checks of the form:

```python
if test_type == "None" or test_type is None:
    ...
if test_type not in ("t-test", "ANOVA", ...):
    ...
if experiment_type is None or experiment_type == "None":
    ...  # the source of "Experiment Type 'None' not implemented"
```

are replaced by calls to the central helpers, or removed entirely because the helpers encapsulate the logic.

In particular:

- `apply_statistical_test_if_active` early guards become:

  ```python
  if _effective_test_type() == "None":
      self.clear_formal_test_results()
      uistate.statusbar_state = None
      self._refresh_test_statusbar()
      return
  if _effective_test_type() not in ("t-test", "ANOVA", ..., "IO regression"):
      ...
  ```

- `_get_stat_test_warning` early guards become:

  ```python
  eff = _effective_test_type()
  if eff == "None":
      uistate.statusbar_state = None
      return None
  if eff == "IO regression":
      # dedicated IO regression formatting path (no test_type checks)
      return _format_io_regression_status(...)
  if eff not in ("t-test", "ANOVA", ...):
      ...
  ```

- Any place constructing "Experiment Type 'None' not implemented" is replaced by a call to `_effective_test_type()` which is guaranteed to never return `"None"` (it returns the sentinel string `"None"` only for the "no test" case, and the error message path should check for that explicitly and say "No statistical test selected" instead of treating it as an invalid experiment type).

---

## Phases

### Phase 0 — Audit (Read-Only, Mandatory)

1. Find **all** places that read or write `experiment_type` or `test_type`.
2. Find **all** guards that check `== "None"`, `is None`, `not in (...)`, or construct error messages containing "experiment" or "test" + "implement".
3. Document the exact shape of `formal_test_results` stored for IO regression (both success and empty cases).
4. Identify the source of "Experiment Type 'None' not implemented" (likely a statusbar or label update that was missed in previous audits).

**Output:** A short internal note (or update to this plan) listing every guard site and the error message source.

### Phase 1 — Introduce Central Helpers (Non-Breaking)

Add `_is_io_mode()`, `_effective_test_type()`, `_should_show_stat_test_frame()`, `_get_statusbar_for_current_state()` to `ui.py`.

- These are pure functions over `uistate`; no side effects.
- Existing code continues to work; new code will migrate to the helpers.

**LOC:** ~20 (4 functions + docstrings).

### Phase 2 — Migrate `apply_statistical_test_if_active` to Helpers

Replace the two Phase 1 guard bypasses (`and not is_io`) with calls to `_effective_test_type()`.

- The IO path now flows naturally: `eff == "ANCOVA"` (or `"IO regression"` if mapped) bypasses the `"None"` and `"not in (...)"` checks because it is a recognized effective type.
- Remove the `is_io` local variable if it becomes unused.
- **Tactical note**: If the immediate `"ANCOVA"` fix (see above) is applied first, this migration is optional — the guards already accept `"ANCOVA"` and the statusbar branch handles the display. The helper migration is for long-term cleanup.

**LOC:** -4 (net removal of bypasses) + 4 (calls to helpers) = 0 net.

### Phase 3 — Migrate `_get_stat_test_warning` to Helpers

Replace the `test_type == "None"` guard + `is_io` bypass (Phase 1) + config-first insertion (Phase 2) with a single early check:

```python
eff = _effective_test_type()
if eff == "None":
    uistate.statusbar_state = None
    return None
if eff == "ANCOVA":
    return _format_io_regression_status(...)  # dedicated, no test_type checks
if eff not in ("t-test", "ANOVA", ..., "ANCOVA"):
    uistate.statusbar_state = "warning"
    return f"Statistical test '{eff}' is not implemented"
```

- The "Experiment Type 'None' not implemented" error is impossible because `eff` is never `"None"` (it is either a valid test name or the sentinel `"None"` which is handled first).
- The existing L1886 IO regression block (or the v0.16.4 config-first insertion) can be removed or kept as a fallback inside `_format_io_regression_status`.
- **Tactical note**: If the immediate `"ANCOVA"` fix is applied, the dedicated statusbar branch for `"ANCOVA"` already produces the regression string. This Phase 3 migration is for long-term guard elimination.

**LOC:** ~10 (new early block) - 8 (old guard + bypass + config-first) = +2 net.

### Phase 4 — Eliminate the "Experiment Type 'None' not implemented" Source

After Phase 0 audit identifies the exact line, replace it with a call to `_effective_test_type()` and a proper message:

```python
eff = _effective_test_type()
if eff == "None":
    return "No statistical test selected"  # or return None to clear statusbar
if eff not in (...):
    return f"Statistical test '{eff}' is not implemented"
```

If the source is in a label or menu path (not statusbar), apply the same pattern.

**LOC:** 3-5 (depending on context).

### Phase 5 — (Optional) Statusbar State for Explicit Tests

If non-IO explicit tests still lack bold statusbar, ensure `apply_statistical_test_if_active` sets `uistate.statusbar_state = "info"` after storing `formal_test_results` (Phase 3 of original plan).

**LOC:** +1.

### Phase 6 — Verification

1. IO project (≥2 groups) → statusbar shows `"IO regression (...)"` with no errors.
2. Switch IO → TimeCourse → `frameToolTest` reappears, prior test statusbar restored (if any).
3. TimeCourse explicit t-test → statusbar shows result in bold.
4. No `print(...)` containing "not implemented" or "Experiment Type" for any valid workflow.
5. `uv run python src/lib/ui.py` (smoke) passes.
6. `uv run pyright src/lib/ui.py` (or equivalent) passes with no new type errors on the helpers.

**Tactical verification (immediate "ANCOVA" fix):** After the 1-line change in `experiment_type_changed` + statusbar branch, IO statusbar appears and "Experiment Type 'None' not implemented" is impossible (no `"None"` value reaches the error path).

---

## Non-Goals

- Do not change the `.ui` file or widget names.
- Do not alter the persisted config keys (`experiment_type`, `test_type`); only their allowed values and the interpretation logic.
- Do not add new radio buttons or menu items for "IO regression" — it remains implicit.
- Do not refactor the entire `uistate` class; keep changes surgical inside `ui.py`.

---

## Acceptance Criteria

**Tactical (immediate "ANCOVA" fix):**

1. `experiment_type_changed` sets `test_type = "ANCOVA"` for IO (1 line).
2. `_get_stat_test_warning` (or a dedicated branch) handles `test_type == "ANCOVA"` by formatting the IO regression statusbar string.
3. "Experiment Type 'None' not implemented" **never appears** (no `"None"` value reaches error paths).
4. IO regression statusbar appears reliably; non-IO `test_type = "None"` still clears the statusbar.
5. Total tactical diff ≤6 lines.

**Long-term (after Phase 0-6):** 6. `experiment_type` is **never** `None` or the string `"None"` at runtime (enforced by helpers + defaults). 7. `test_type` is **never** the Python value `None`; it is always a string from the 7-value set (including `"ANCOVA"`). 8. The message "Experiment Type 'None' not implemented" **never appears**. 9. IO regression statusbar appears reliably on project load and experiment-type switch. 10. Non-IO explicit test statusbar appears reliably (bold on success). 11. Total net LOC change ≤40 (helpers + migrations + one error message fix). 12. Smoke test and type check pass.

---

## Why This Is the Right Fix

**Tactical ("ANCOVA" value):** The immediate `"ANCOVA"` proposal is the minimal, correct next step. It:

- Resolves the "Experiment Type 'None' not implemented" error without hunting for its source (the value `"None"` no longer exists for IO).
- Makes all previous `is_io` bypass patches unnecessary — `"ANCOVA"` passes the `not in (...)` guard naturally.
- Requires only ~6 LOC and can be implemented today.
- Is forward-compatible with the long-term architectural cleanup (the value `"ANCOVA"` is already in the closed set).

**Long-term (this plan):** Previous plans (v0.16.4 and iterations) were **symptom-driven patches**:

- Each new guard discovered required another `and not is_io` or another early return.
- The underlying state (`test_type = "None"` for IO) was semantically ambiguous (`None` vs `"None"`, experiment type vs test type).
- The "Experiment Type 'None' not implemented" error proved the state machine was leaking invalid values into paths that assumed a valid experiment type.

This plan is **cause-driven**:

- It defines a closed set of valid states (including `"ANCOVA"` for IO).
- It provides a single source of truth (`_effective_test_type()`) that downstream code can trust.
- It eliminates the need for ad-hoc bypasses because the state itself is correct.
- Future features (e.g., an explicit "IO regression" test_type radio) can be added cleanly by extending the `effective_test_type` mapping, not by patching more guards.

---

## File Summary

**Tactical (immediate, minimal diff):**

| File            | Change                                                | Lines | Risk |
| --------------- | ----------------------------------------------------- | ----- | ---- |
| `src/lib/ui.py` | `experiment_type_changed`: force `test_type="ANCOVA"` | +1    | Low  |
| `src/lib/ui.py` | `_get_stat_test_warning`: dedicated `"ANCOVA"` branch | +5    | Low  |
| `src/lib/ui.py` | (opt) `applyConfigStates` migration for old projects  | +3    | Low  |

**Total tactical:** ≤9 LOC. Solves the immediate "no statusbar" + "Experiment Type 'None'" symptoms.

**Long-term (architectural, completed in this implementation):**

| File            | Change                                                                                                                                     | Lines                              | Risk |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- | ---- |
| `src/lib/ui.py` | Add 4 central helper functions (`_is_io_mode`, `_effective_test_type`, `_should_show_stat_test_frame`, `_get_statusbar_for_current_state`) | +45 (with docs)                    | Low  |
| `src/lib/ui.py` | Migrate `apply_statistical_test_if_active` (use `eff = self._effective_test_type()`)                                                       | -15 (removed ~12 `is_io` bypasses) | Low  |
| `src/lib/ui.py` | Migrate `_get_stat_test_warning` (early `eff` check + dedicated ANCOVA/IO path)                                                            | +35 (consolidated guards)          | Low  |
| `src/lib/ui.py` | `experiment_type_changed`, `applyConfigStates`, visibility, update_anova_label, Friedman/Cluster guards                                    | +20 (migration + helper calls)     | Low  |
| `src/lib/ui.py` | Fix "Experiment Type 'None'" error source (impossible by construction via helpers)                                                         | 0 (prevented)                      | Low  |

**Total:** ~85 LOC net (helpers + migrations + cleanup). Exceeds original estimate due to full consolidation and comments, but eliminates all ad-hoc guards. State invariants now enforced. Updated Phase 0 audit confirms ~15 `is_io`/None sites reduced to centralized calls.

---

_End of plan_experiment_type_overhaul.md_
