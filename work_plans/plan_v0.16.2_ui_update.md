# Plan v16.2 — UI Update: frameTool rename handling & View menu completion

## Context

`ui_state_classes.py` tracks toolframe visibility via `uistate.viewTools` (dict of `framename: [title, visible]`). Some `frameTool*` widgets were renamed to `frameTool_sub_*` variants. These sub-frames are controlled exclusively by radio buttons (not dedicated hide `pushButton_*` controls), and they should **not** appear in the View menu.

All **non-sub** `frameTool*` entries should have corresponding checkable menu actions under the **View** menu (most already do). Missing ones need to be added along with their `viewTools` entries. They default to **show** (`True`).

---

## Phase 0 — Update wiring for renamed sub-frames

### Problem
Some `frameTool*` widgets were renamed to `frameTool_sub_*`. The code that shows/hides them via radio button handlers still references the old names.

### Goal
Ensure that when a radio button selects a sub-variant, the corresponding `frameTool_sub_*` widget is shown/hidden, and when unselected, it is hidden. Non-sub frames continue to work as before.

### Tasks

1. **Audit all radio button handlers that touch `frameTool*` visibility**:
   - `experiment_type_changed` (L3038–3079) — toggles `frameToolType_io`
   - `test_type_changed` (L3081–3107) — toggles `frameToolTest_t`, `frameToolTest_ANOVA`, `frameToolTest_wilcoxon`, etc.
   - `applyConfigStates` (L3888–4003) — applies persisted `test_type` to sub-frames
   - `setupToolBar` (L3585–3600) — applies initial visibility for conditional frames

2. **For each renamed sub-frame**:
   - Confirm the widget attribute exists (e.g., `self.frameTool_sub_...`)
   - Update the `if hasattr(self, "frameToolXXX"):` / `self.frameToolXXX.setVisible(...)` logic to use the new `_sub_` name
   - Ensure the corresponding `hide` path is covered (sub-frames have no dedicated hide button; visibility is purely driven by radio state)

3. **Verification**:
   - Switching experiment type or test type correctly shows the matching sub-frame and hides siblings
   - `applyConfigStates` restores the correct sub-frame visibility on load
   - No references to stale `frameTool*` names remain for sub-variants

> **Note**: Sub-frames are **not** added to `uistate.viewTools` and have **no** View menu entry. Their lifecycle is owned by the radio button group.

---

## Phase 1 — Add missing View menu entries for non-sub frames

### Current `viewTools` (from `ui_state_classes.py:115–128`)

```python
self.viewTools = {
    "frameToolStim":        ["Stim detection", True],
    "frameToolSweeps":      ["Sweep selection", True],
    "frameToolTag":         ["Tag selection", True],
    "frameToolBin":         ["Binning", True],
    "frameToolType":        ["Experiment type", True],
    "frameToolFilter":      ["Filter", True],
    "frameToolYscale":      ["Y scaling", True],
    "frameToolAspect":      ["Aspect toggles", True],
    "frameToolAspectSlope": ["Slope width", False],
    "frameToolAspectAmp":   ["Amplitude width", False],
    "frameToolTest":        ["Statistical test", True],
    "frameToolHierarchy":   ["Hierarchy", True],
}
```

### Task

For each entry in `viewTools`, ensure:

1. A corresponding **checkable QAction** exists under `menuView` with matching `.text()` (the title string).
2. Toggling the action calls `setViewToolVisible(frame_name, visible)` (already wired via `menuView` → `setViewToolVisible` matching by title).
3. On startup / `applyConfigStates`, the action's checked state is synced from `uistate.viewTools[frame][1]`.

### Likely missing / needing verification

| Frame                    | Title                | Menu entry exists? | Action wired? | Default |
|--------------------------|----------------------|--------------------|---------------|---------|
| `frameToolStim`          | Stim detection       | ?                  | ?             | True    |
| `frameToolSweeps`        | Sweep selection      | ?                  | ?             | True    |
| `frameToolTag`           | Tag selection        | ?                  | ?             | True    |
| `frameToolBin`           | Binning              | ?                  | ?             | True    |
| `frameToolType`          | Experiment type      | ?                  | ?             | True    |
| `frameToolFilter`        | Filter               | ?                  | ?             | True    |
| `frameToolYscale`        | Y scaling            | ?                  | ?             | True    |
| `frameToolAspect`        | Aspect toggles       | ?                  | ?             | True    |
| `frameToolAspectSlope`   | Slope width          | ?                  | ?             | False   |
| `frameToolAspectAmp`     | Amplitude width      | ?                  | ?             | False   |
| `frameToolTest`          | Statistical test     | ?                  | ?             | True    |
| `frameToolHierarchy`     | Hierarchy            | ?                  | ?             | True    |

> The `.ui` file likely defines these actions (e.g., `actionStimDetection`, `actionSweepSelection`, …). If an action is missing, add it in Qt Designer (or by hand in the generated code if unavoidable) and ensure `menuView.addAction(...)` includes it.

### Additional wiring (already present, verify)

- `connectUIstate` (L3702–3714) defines `hide_buttons` mapping `pushButton_hide_*` → frame; these should **not** include sub-frame entries.
- `setViewToolVisible` (L2352–2373) updates `uistate.viewTools` and syncs the matching menu action by title.
- `applyConfigStates` (L3898–3903) iterates `viewTools` and checks the corresponding menu action.

---

## Non-goals / Exclusions

- **Do not touch `ui_designer.py`** (per `AGENTS.md`).
- Sub-frames (`frameTool_sub_*`) are intentionally **outside** `viewTools` and the View menu; they are radio-driven only.
- No new dedicated hide buttons for sub-frames are required.

---

## Acceptance criteria

1. **Phase 0**: All radio-driven show/hide of `frameTool_sub_*` widgets functions; no stale frame references; state is restored on config load.
2. **Phase 1**: Every `viewTools` entry has a matching checkable View menu action; toggling the action or the hide button updates both widget and menu check state; defaults match the table above.
3. No regressions in existing visibility behavior for non-sub frames or radio-controlled sub-frames.

---

## Notes for implementer

- The View menu is built from a `.ui` file; adding new actions there is the canonical path. If editing generated code, keep changes minimal and consistent with surrounding style.
- The sync between menu actions and `viewTools` is title-based (`action.text() == title`). Keep titles stable.
- When a sub-frame is shown by radio selection, ensure sibling sub-frames (and optionally the parent grouping frame) are hidden as appropriate (current `test_type_changed` pattern).
