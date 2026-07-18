# Plan v0.16_n: Subject / Slice hierarchy (statistical protocol compliance) [L1-320]

## Mission Statement

Implement data model from `statistical_protocol.md`: **Subject** (animal) is the sole experimental unit defining n (unique subjects). **Slice** and **Recording** are nested repeated measures. Add `subject` (str) and `slice` (str) columns to `df_project` for correct grouping in mixed-effects analyses.

- Explicitly deprecate `paired_recording`/`Tx`.
- Wire existing `frameToolHierarchy` (UI designer) for visibility, focus, persistence (Phase 0).
- Add minimal 2-way binding for selection <-> line-edits (Phase 1).
- Ensure **explicit backward compatibility** + **default synthesis** on load/import (lowest-unique-integer subjects; slice="1").
- **Core constraint**: NEVER edit `ui_designer.py` or run `puic`. Use dynamic `pushButtons`, `viewTools`, `checkBox` in `UIstate.reset()`, `connectUIstate()`, and existing signals.

Loader/import paths may assume "one slice per subject" initially; UI provides bulk-edit surface. No stats/analysis changes (deferred).

## What Exists Today

### `df_projectTemplate()` in `src/lib/ui_project.py` (lines 47–76)

Canonical schema (object dtype mostly; `_INT_COLUMNS` for nullable Int64). No `subject`/`slice`. `paired_recording`/`Tx` still active in `ui_data_frames.py:get_dfdiff`, `ui.py:formatTableLayout`, rename logic.

### Table display (`formatTableLayout` in `src/lib/ui.py:3310`)

- **Updated per user requirement**: `subject` and `slice` are **always shown** immediately after `recording_name` in `column_order` (both compact and detailed views). No longer "detail-only".
- Columns use string dtype (see migration).

### Loading/Import Paths Populating `df_project`

- `TableProjSub.dropEvent`, `Filetreesub.pathsSelectedUpdateTable`, `addData` (and other paths) → `df_projectTemplate()` then `set_df_project` (triggers `_migrate_hierarchy`).
- `load_df_project` (ui_project.py:397): reads CSV, backfills, restores dtypes, calls `_migrate_hierarchy`.

### Persistence

- `load_df_project`/`set_df_project`/`save_df_project` (CSV via `to_csv`/`read_csv`; parquet elsewhere).
- `uistate` (`viewTools`, `checkBox`) via `get_state`/`set_state` + `cfg.pkl`.
- Adding columns is safe (NaN backfill + migration); new saves include them. `set_df_project` now also calls `tableUpdate()` for immediate UI refresh.

### Existing `frameToolHierarchy` (ui_designer.py:159–198)

Pre-built QFrame with:

- `lineEdit_hierarchy_subject`, `lineEdit_hierarchy_slice`
- `checkBox_hierarchy_dd_is_subject` ("Each drag/drop is a Subject")
- `pushButton_hide_hierarchy` (× button)

Absent from `viewTools`/`pushButtons`/`uistate` initially. No signals connected. (Full grep results confirmed patterns in `tableProjSelectionChanged:935`, uniform selection in `update_*_lineEdits`, `connectUIstate`, `setViewToolVisible`.)

---

**Implementation note (post-completion)**: The table refresh bug ("type in 4, Subject still says 2 until I reload") required adding `if hasattr(self, "tableUpdate"): self.tableUpdate()` inside `set_df_project` (ui_project.py:386, guarded by `updating_tableProj` flag in `tableUpdate`). This ensures line-edit → DataFrame → visual table sync without reload. All other requirements matched the plan exactly.

## Phase 0 — Wire `frameToolHierarchy` (visibility, hide button, persistence)

**Goal**: Make frame first-class citizen like `frameToolFilter*` etc. No data binding yet.

### 0.1 Add to `viewTools` (in `UIstate.reset()`, src/lib/ui_state_classes.py:115)

```python
"frameToolHierarchy": ["Hierarchy", True],  # title + default visible
```

Consumed by `setupToolBar:3408`, `setViewToolVisible`, `applyConfigStates:3696`, menu, `connectUIstate` (hide button wiring).

### 0.2 Add hide-button wiring (in `uistate.pushButtons`, ui_state_classes.py:260)

```python
"pushButton_hide_hierarchy": "triggerHideHierarchy",
```

In `UIsub.connectUIstate` (ui.py:3665 loop) this auto-connects to `self.triggerHideHierarchy`.

Implement in `UIsub` (ui.py, near other triggers ~4019):

```python
def triggerHideHierarchy(self):
    self.usage("triggerHideHierarchy")
    self.setViewToolVisible("frameToolHierarchy", False)  # reuses existing; flips viewTools + saves cfg
```

(Matches pattern of other `pushButton_hide_*` via menuView actions.)

### 0.3 Keyboard focus/tab order (cheap, recommended)

In `setupTableProj` (ui.py:3285, after table setup):

```python
if hasattr(self, 'lineEdit_hierarchy_subject') and hasattr(self, 'lineEdit_hierarchy_slice'):
    self.setTabOrder(self.lineEdit_hierarchy_subject, self.lineEdit_hierarchy_slice)
```

(Or `QTimer.singleShot(0, ...)` post-load.)

### 0.4 Persistence

Automatic via `viewTools` in `ui_state_classes.py:746` (`merge_dict`) + `load_cfg`/`save_cfg`. Add default ensures old configs get `True`.

### 0.5 Menu entry (ui_menus.py)

Most tool frames appear in the **View** menu (e.g. `actionViewToolFilter`, `actionViewToolTag`, …). Add a matching action for Hierarchy:

- In `setupMenus` create/find `actionViewToolHierarchy` (or follow the existing naming).
- Connect it to `setViewToolVisible("frameToolHierarchy", checked)` (or the existing toggle lambda pattern used by other view actions).
- The generic menu/View machinery already keeps the check-mark in sync with `viewTools["frameToolHierarchy"]`.

If the action does not yet exist in the compiled UI, the menu addition itself is still safe (no designer change) — the handler can be a no-op or print a placeholder until the action is added later. For v0.16_n the intent is to document the wiring point.

### 0.6 Non-goals for Phase 0

- No line-edit/checkbox signals or data binding.
- No population from selection.
- Frame appears, hides via × or View menu, persists state.

After Phase 0: Hierarchy frame is discoverable/persistent (including via menu).

## Phase 1 — Minimal two-way binding (selection ↔ line-edits + checkbox)

**Behavior** (refined from 2026-06-28 clarification):

- **Display** (`refreshHierarchyLineEdits`, called from `tableProjSelectionChanged:933` **after** `connectUIstate(disconnect=True)` block ~1013):
  - 0 selections: `""` for both.
  - 1 selection: `subject`/`slice` value ("" if NaN/None).
  - > 1 selections: if **all** identical and non-null → that value; else `""`. (Use `pd.isna`, set comparison like bin_size logic.)
- **Apply** (`applyHierarchyToSelection`, on `editingFinished`):
  - Connect in `connectUIstate` (add to lineEdit list ~3554):
    ```python
    self.lineEdit_hierarchy_subject.editingFinished.connect(
        lambda: self.applyHierarchyToSelection("subject")
    )
    # same for slice
    ```
  - If text non-empty: set `df_project.loc[selected_rows, col] = text`; else optional NaN (choose set-to-NaN; document).
  - Call `self.set_df_project(df_p)` or lighter `self.tableUpdate()` (preserves selection).
- **Checkbox**: Pure persistence (no behavior). Add to `UIstate.reset:128`:
  ```python
  "hierarchy_dd_is_subject": False,
  ```
  Generic `connectUIstate` + `checkBox_hierarchy_dd_is_subject` (objectName match) + `viewSettingsChanged` handles it. Drop handlers remain unchanged (future work).

**Helpers** (add to UIsub in ui.py near `update_amp_lineEdits` ~4428):

```python
def refreshHierarchyLineEdits(self, df_p=None):
    if df_p is None:
        df_p = self.get_df_project()
    if not hasattr(self, 'lineEdit_hierarchy_subject'):
        return
    self.connectUIstate(disconnect=True)  # prevent feedback
    idxs = uistate.list_idx_select_recs
    if not idxs:
        self.lineEdit_hierarchy_subject.setText("")
        self.lineEdit_hierarchy_slice.setText("")
        self.connectUIstate()
        return
    subs = [df_p.at[i, 'subject'] for i in idxs if pd.notna(df_p.at[i, 'subject'])]
    slices = [df_p.at[i, 'slice'] for i in idxs if pd.notna(df_p.at[i, 'slice'])]
    subj_val = subs[0] if len(set(subs)) == 1 else ""
    slice_val = slices[0] if len(set(slices)) == 1 else ""
    self.lineEdit_hierarchy_subject.setText(str(subj_val) if subj_val else "")
    self.lineEdit_hierarchy_slice.setText(str(slice_val) if slice_val else "")
    self.connectUIstate()

def applyHierarchyToSelection(self, col: str):  # "subject" or "slice"
    self.usage(f"applyHierarchyToSelection({col})")
    text = getattr(self, f'lineEdit_hierarchy_{col}').text().strip()
    idxs = uistate.list_idx_select_recs
    if not idxs:
        return
    df_p = self.get_df_project().copy()
    if text:
        df_p.loc[idxs, col] = text
    else:
        df_p.loc[idxs, col] = pd.NA  # or "" ; chosen: explicit NA
    self.set_df_project(df_p)  # triggers save + tableUpdate
    self.refreshHierarchyLineEdits(df_p)  # refresh display
```

Call `self.refreshHierarchyLineEdits()` at end of `tableProjSelectionChanged` (after `update_slope_lineEdits` ~1038, before `graphUpdate`).

**Data integrity**: Strings only. Guard `pd.isna`/`pd.notna`. No validation here (future). Re-selection refreshes display.

---

## Detailed Requirements for v0.16_n

### 1. Schema change (position-sensitive) — `src/lib/ui_project.py:47`

Insert after `"recording_name",`:

```python
"subject",  # str: biological subject/animal ID (defines n per statistical_protocol.md)
"slice",    # str: slice within subject; default "1" (nested repeated measure)
```

Update deprecations:

```python
"paired_recording",  # DEPRECATED (paired-stimulus workflow). str: unique ID of paired recording
"Tx",                # DEPRECATED (paired-stimulus workflow). Boolean: Treatment / Control
```

Update `_INT_COLUMNS` comment if needed (no change; both new cols are `object`/`string` — Option A chosen for simplicity/uniformity. No nullable Int64 for slice).

Update module docstring + `df_projectTemplate` docstring referencing protocol.

### 2. Backward compatibility + default synthesis (explicit policy)

In `load_df_project` (ui_project.py:389, after existing backfill loop) **and** import paths (`addData` etc.):

- Add helper:

```python
def _migrate_hierarchy(self, df: pd.DataFrame) -> pd.DataFrame:
    """Apply statistical_protocol defaults. Called on load/import."""
    if 'subject' not in df.columns:
        df['subject'] = None
    if 'slice' not in df.columns:
        df['slice'] = None

    # Lowest-unique-integer subjects (respects existing; fills gaps)
    existing_subs = set(df['subject'].dropna().astype(str).unique())
    next_id = 1
    for i, row in df.iterrows():
        if pd.isna(row['subject']) or str(row['subject']).strip() == '':
            while str(next_id) in existing_subs:
                next_id += 1
            df.at[i, 'subject'] = str(next_id)
            existing_subs.add(str(next_id))
            next_id += 1
        if pd.isna(row['slice']) or str(row['slice']).strip() == '':
            df.at[i, 'slice'] = "1"
    return df
```

Call: `self.df_project = self._migrate_hierarchy(self.df_project)` (after dtype restoration, before `tableFormat`).

On new `df_projectTemplate()`: columns default to NaN → migration fills on first `set_df_project`/`loadProject`.

This enforces "one slice per unique animal" safely. Subjects start as "1","2",... (string).

### 3. Table visibility (no designer change)

- **Always visible** (per final requirement): `subject` and `slice` added to `column_order` right after `"recording_name"` in `formatTableLayout` (both compact + detailed views; see updated "What Exists Today" section above). Comment added.
- Position after `recording_name` preserved via explicit list.
- **Table refresh**: `set_df_project` now explicitly calls `tableUpdate()` (with `updating_tableProj` guard to prevent recursion). This fixed the visual staleness on line-edit edits (cells previously only updated on full reload). `applyHierarchyToSelection` + `refreshHierarchyLineEdits` complete the 2-way binding.

### 4. No analysis/statistics changes

Per protocol: n = unique(`subject`). Deferred to later (mixed models, UI n-reporting). Current code unaffected.

### 5. Persistence & migration

- Old projects: CSV read → backfill NaNs → `_migrate_hierarchy` fills defaults → saved with columns.
- New saves include columns. No format version bump.
- `uistate.viewTools["frameToolHierarchy"]` and checkbox auto-persisted.

### 6. Documentation / comments

- Reference `statistical_protocol.md` in `ui_project.py` docstring, new column comments, plan summary.
- Comment all new methods/helpers.
- Update `plan_v0.16_n.md` deliverables.

---

## Resolved Open Questions

1. **Default synthesis**: Lowest-unique-integer for `subject` (string); `"1"` for `slice`. Implemented in `_migrate_hierarchy` (respects manual edits, fills gaps).
2. **Slice dtype**: String (Option A). Uniform with `subject`; simplifies UI/table. No `_INT_COLUMNS` change. Users may later enter non-numeric labels ("a", "b", "left", "right"); any integer-sorting cleverness is deferred.
3. **Compact table**: `subject`/`slice` now always shown (updated from "detail-only" per user requirement during implementation). Added to `column_order` after `recording_name`.
4. **Table refresh**: Explicit `tableUpdate()` in `set_df_project` (with `updating_tableProj` guard) to ensure line-edits immediately update project table cells. Resolved the "Subject still says 2 until I reload" bug.
5. **Rename/edit scope**: Confirmed — only schema + inspector/bulk-assign (Phase 1). User supplies deeper UI later. No validators/namespace enforcement.
6. **Paired deprecation**: Leave functional (marked only). Future cleanup plan.

### Additional agent-confirmed decisions (final)

- **viewTools entry**: `["Hierarchy", True]` (title + default visible; matches other frames).
- **Disconnect guard**: `connectUIstate(disconnect=True)` in `refreshHierarchyLineEdits` (and reconnect); prevents feedback loops on `setText`.
- **Clear-to-NA**: `pd.NA` on empty text; displays as blank. `str()` sanitization in `applyHierarchyToSelection` + `object` dtype in migration prevents `LossySetitemError`.
- **Checkbox key**: Generic prefix-stripping works; no extra code.
- **Dtype**: `object` for both columns (Option A). Lowest-unique-integer subjects (string) + `slice="1"`. Full `_migrate_hierarchy` implemented with `pd.isna`, `iterrows`/`at`, and dtype coercion.

## Non-Goals (explicit)

- No `ui_designer.py` changes.
- No drag-and-drop semantics for checkbox (placeholder only).
- View menu action for Hierarchy is wired only if the corresponding `actionViewToolHierarchy` already exists in the compiled UI; otherwise the handler is a documented stub.
- No stats/UI n-counting, mixed models, or grouping changes.
- No compact-table inclusion or advanced validation.
- Paired-stim workflow untouched.

## Verification Steps (for agent/check-work) — All Passed

1. Load old project → `subject`/`slice` auto-filled (lowest-unique integers, slice="1"), no breakage. Migration works on CSV round-trip.
2. New import/addData → same defaults.
3. Hide/show hierarchy frame (× button + persistence via `viewTools` in cfg.pkl) works. `triggerHideHierarchy` + `setViewToolVisible`.
4. Select 1/multiple rows → `refreshHierarchyLineEdits` populates line-edits correctly (uniform value or blank for mixed).
5. **Edit line-edits** (`editingFinished` → `applyHierarchyToSelection`) → `df_project` updated (string values), **table cells refresh immediately** (via `set_df_project` → `tableUpdate`), saved to CSV. No more staleness.
6. Checkbox (`hierarchy_dd_is_subject`) persists.
7. Existing tests (`test_parse.py`, stats) + manual verification pass. No impact on analysis paths yet (n=unique subjects deferred).
8. `tableUpdate`/`formatTableLayout` (now includes hierarchy columns), `set_df_project`, no `ui_designer.py` edits. `LossySetitemError` fixed via string dtype + sanitization.

**Current status**: Fully implemented and verified. Table now always shows Subject/Slice after Recording name. Plan updated to reflect final state.

## Summary of Deliverables (Final — Updated Post-Implementation)

| File                                 | Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/ui_project.py`              | (1) `subject`/`slice` + protocol comments in `df_projectTemplate`. (2) Deprecation comments for `paired_recording`/`Tx`. (3) Full `_migrate_hierarchy` (lowest-unique-integer subjects as str, slice="1", `object` dtype coercion). (4) Calls in `load_df_project`, `set_df_project` (now also calls `tableUpdate()` for immediate refresh). (5) Updated docstrings + `loadProject` init guard.                                                                                                    |
| `src/lib/ui_state_classes.py`        | (1) `"frameToolHierarchy": ["Hierarchy", True]` in `viewTools`. (2) `"hierarchy_dd_is_subject": False` in `checkBox`.                                                                                                                                                                                                                                                                                                                                                                              |
| `src/lib/ui.py`                      | (1) `pushButton_hide_hierarchy` wiring + `triggerHideHierarchy`. (2) `refreshHierarchyLineEdits` (uniform selection logic, disconnect guard, `str()` conversion). (3) `applyHierarchyToSelection` (sanitized `str(text)`, `pd.NA`, `set_df_project` + refresh). (4) Wiring in `connectUIstate`, `tableProjSelectionChanged`, `setupTableProj` (tab order). (5) `formatTableLayout`: `subject`/`slice` always in `column_order` after `recording_name` (both views). (6) `tableUpdate` integration. |
| `work_plans/plan_v0.16_n.md`         | **This file**: Removed duplication, updated "What Exists Today", table visibility (always-show), refresh fix, resolved questions, verification (all passed), deliverables. Marked complete.                                                                                                                                                                                                                                                                                                        |
| `work_plans/statistical_protocol.md` | No change (reference only).                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

**Implementation complete** (v0.16_n on `science_test_v0.16` branch). All bugs fixed (dtype crash, table staleness on line-edit edit, column positioning). Verified via manual testing, migration round-trips, and console output. Feature delivers statistical protocol compliance with minimal disruption. Ready for Phase 2 (drag-drop, stats integration) or merging.

(End of plan — now fully current as of latest changes.)
