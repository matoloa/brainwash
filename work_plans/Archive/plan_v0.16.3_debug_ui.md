# Plan v0.16.3 — Debug UI: `frameToolTest` fails to reappear after IO → TimeCourse switch

## Root Cause (Identified)

`experiment_type_changed` (src/lib/ui.py:3048-3068) unconditionally hides `frameToolTest` (and all sub-frames) when `exp_type == "io"`, and also disables the corresponding View menu action.  
When switching **back** to `"time"` or `"PP"`, the only code path that runs is:

```python
else:
    self.update_show()   # does NOT touch frameToolTest visibility
```

Neither `setupToolBar` (which **does** enforce `frameToolTest.setVisible(not is_io)`) nor `applyConfigStates` (which restores sub-frame visibility based on `test_type`) is ever called on an **in-session** experiment-type change.  
`viewTools["frameToolTest"]` itself is never updated when IO hides the frame, so even if a later `setupToolBar` ran it would restore the stale `True` value while the frame is still hidden.

Result: once hidden for IO, `frameToolTest` stays hidden forever until the project is reloaded.

---

## Mission (Minimal Surgical Fix)

Restore `frameToolTest` visibility (and re-enable its View menu action) when the user switches **away** from IO.  
Do **not** touch `ui_designer.py`. Keep changes to ≤10 lines in `ui.py`. No new UI-state variables.

---

## Phase 1 — Add the missing "re-show" branch in `experiment_type_changed`

**File:** `src/lib/ui.py`, inside `experiment_type_changed`, replace the bare `else: self.update_show()` with a symmetric block that re-applies the non-IO rule for `frameToolTest`.

### Current (broken) code (L3069-3077)

```python
uistate.save_cfg(projectfolder=self.dict_folders["project"])
if exp_type in ["io", "PP"] or old_type in ["io", "PP"]:
    self.exorcise()
    self.triggerRefresh()
    self.zoomAuto()
    self.graphRefresh()
    self.apply_statistical_test_if_active()
else:
    self.update_show()
```

### Replacement (one new `elif`)

```python
uistate.save_cfg(projectfolder=self.dict_folders["project"])
if exp_type == "io":
    # ... existing IO-hide block unchanged ...
elif old_type == "io":
    # Re-show the Statistical test frame when leaving IO
    if hasattr(self, "frameToolTest"):
        self.frameToolTest.setVisible(True)
    if hasattr(self, "menuView"):
        for action in self.menuView.actions():
            if "test" in action.text().lower() or "statistical" in action.text().lower():
                action.setEnabled(True)
    self.update_show()
else:
    self.update_show()
```

- The `elif old_type == "io"` triggers exactly once on the transition out of IO.
- It mirrors the hide logic but only touches `frameToolTest` (and its menu action).
- `update_show()` is still called so existing refresh behavior is preserved.
- `frameToolTestOptions` stays visible (already handled by `setupToolBar` / initial state).

---

## Phase 2 — (Optional) One-line hardening in `setupToolBar`

If the above `elif` is applied, `setupToolBar` already contains the correct rule (L3596-3598):

```python
is_io = getattr(uistate, "experiment_type", "time") == "io"
if hasattr(self, "frameToolTest"):
    self.frameToolTest.setVisible(not is_io)
```

This line is **defensive** — it will now correctly restore the frame on any future call to `setupToolBar` (e.g., project reload). No edit required unless the reviewer wants an explicit comment.

---

## Non-Goals / Exclusions

- Do **not** modify `ui_designer.py`.
- Do **not** add `frameToolTest` to `viewTools` (it is intentionally managed by experiment-type, not by the View menu checkbox).
- Do **not** touch sub-frame visibility here (`frameToolTest_sub_*` remain driven exclusively by `test_type`).
- No new persistence, no new radio-button logic, no change to IO regression path.

---

## Acceptance Criteria

1. Select IO → `frameToolTest` hides and its View menu entry is disabled.
2. Switch back to TimeCourse (or PP) → `frameToolTest` immediately reappears and its View menu entry is re-enabled.
3. The fix is contained in ≤10 net new lines in `src/lib/ui.py`.
4. No other tool-frame visibility is affected.
5. `uv run python src/lib/ui.py` (or equivalent smoke test) runs without syntax/import errors.

---

## Implementation Notes for Build Server

- The change is a pure addition of one `elif` branch + symmetric re-enable logic.
- The existing `if exp_type == "io":` block is left **completely untouched**.
- The `elif` re-uses the exact same menu-action search pattern already present at L3066-3068, so no new string constants are introduced.
- This fix makes `experiment_type_changed` fully symmetrical for the `frameToolTest` lifecycle without introducing any new state machine.

---

## File Summary

| File              | Change                     | Lines | Risk |
|-------------------|----------------------------|-------|------|
| `src/lib/ui.py`   | Add `elif old_type == "io"` block inside `experiment_type_changed` | +8    | Low  |

---

*End of plan v0.16.3_debug_ui.md*
