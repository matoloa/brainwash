# Plan v0.16_n: Subject / Slice hierarchy (statistical protocol compliance)

## Mission Statement

Implement the data model required by `statistical_protocol.md`: **Subject (animal)** is the sole experimental unit; **Slice** and **Recording** are nested repeated measurements. The project DataFrame must expose `subject` and `slice` columns so that downstream mixed-effects analyses (and any future hierarchical summaries) can correctly group data by biological sample size (n = number of unique subjects).

Two deprecated columns (`paired_recording`, `Tx`) must be explicitly marked as such. The UI already contains `frameToolHierarchy` (designer-built) with `lineEdit_hierarchy_subject`, `lineEdit_hierarchy_slice`, and `checkBox_hierarchy_dd_is_subject`. Phase 0 of this plan wires that frame so it participates in show/hide, focus, and state persistence exactly like other tool frames. No deeper editing or assignment logic is required yet.

The loader may continue to assume "one slice per unique animal" on import; the schema change is purely additive and forward-compatible.

**Core Constraint** (carried from v0.15): NEVER alter `ui_designer.py` or run `puic`. All button wiring must be performed via the dynamic `self.pushButtons` dictionary in `UIstate.reset()` (consumed by `UIsub.connectUIstate()`) or by connecting to existing Qt signals.

---

## What Exists Today

### `df_projectTemplate` in `src/lib/ui_project.py` (lines 47–76)

Defines the canonical column list for the project DataFrame:

```python
columns=[
    "ID",
    "host",
    "path",
    "status",
    "recording_name",
    "gain",
    ...
    "channel",
    "paired_recording",   # ← to be deprecated
    "Tx",                 # ← to be deprecated
    "exclude",
    "comment",
]
```

No `subject` or `slice` columns exist. `paired_recording` and `Tx` are used by the paired-stimulus workflow (`get_dfdiff` in `ui_data_frames.py`, `formatTableLayout` conditional in `ui.py`, rename logic in `renameRecording`).

### Table display (`formatTableLayout` in `src/lib/ui.py`, lines 3304–3345)

The compact view shows: `status | recording_name | groups | stims | sweeps | sweep_duration | [Tx if paired_stims]`.

The detailed view appends every remaining column from `df_project`. Column order is hardcoded; new columns (`subject`, `slice`) will appear only in detailed mode unless explicitly inserted into the compact `column_order` list.

### Loading paths that populate `df_project`

- `TableProjSub.dropEvent` (ui.py:643) — drag-and-drop of source files
- `Filetreesub.pathsSelectedUpdateTable` (ui.py:707) — file tree selection
- Both call `df_projectTemplate()`, assign `path`/`host`/`filter`, then synthesize `recording_name` from folder+filename.

No code path currently sets `subject` or `slice`. Existing projects loaded from parquet will simply lack those columns until migrated or until the loader synthesizes defaults.

### Persistence

`df_project` is saved via `df2file` / `loadProject` (ProjectMixin). Adding new nullable columns is safe: pandas will back-fill with `NaN` (or `pd.NA`) on read of older project files; writers will emit the new columns going forward.

### Existing `frameToolHierarchy` (ui_designer.py:159–198)

A designer-built `QFrame` already exists inside `scrollAreaWidgetContentsTools`:

- `frameToolHierarchy` — container (min-size 201×121)
- `label_hierarchy` — bold title label
- `label_hierarchy_subject` + `lineEdit_hierarchy_subject` — subject entry (geometry 90×30, width 41)
- `label_hierarchy_slice` + `lineEdit_hierarchy_slice` — slice entry (geometry 90×60, width 41)
- `checkBox_hierarchy_dd_is_subject` — "treat drag-and-drop item as subject" (spans bottom of frame)
- `pushButton_hide_hierarchy` — flat [×] button at top-right corner

No signals are connected yet; the frame is always visible unless its parent layout is collapsed. It is absent from `viewTools`, `pushButtons`, and `uistate` attribute tracking.

---

## Phase 0 — Wire `frameToolHierarchy` (show/hide, focus, persistence)

**Goal**: make the pre-existing hierarchy frame behave exactly like the other tool frames (`frameToolFilter*`, `frameToolTag`, etc.) so the user can discover and interact with it immediately after the schema lands. No assignment logic or two-way binding to `df_project` rows is required.

### 0.1 Add to `viewTools` (visibility toggle)

In `UIstate.reset()` (ui_state_classes.py) add:

```python
"frameToolHierarchy": True,
```

This entry will be consumed by `UIsub.viewSettingsChanged` and the generic frame show/hide machinery.

### 0.2 Add hide-button wiring

In the same `pushButtons` dict add:

```python
"pushButton_hide_hierarchy": "triggerHideHierarchy",
```

Implement `triggerHideHierarchy` in `UIsub` (or a lightweight mixin) to simply flip `uistate.viewTools["frameToolHierarchy"] = False` and call `viewSettingsChanged`. This matches the pattern used by all other `pushButton_hide_*` buttons.

### 0.3 Keyboard focus & tab order (optional but cheap)

If desired, call `setTabOrder` in `setupTableProj` (or a one-time `QTimer.singleShot`) so that `lineEdit_hierarchy_subject → lineEdit_hierarchy_slice` feels natural. Not required for v0.16_n correctness.

### 0.4 Persistence

`viewTools` is already round-tripped via `get_state`/`set_state`/`load_cfg`/`save_cfg`. Adding the key here automatically persists show/hide state with no extra code.

### 0.5 Non-goals for Phase 0

- No signal connection from the line-edits or checkbox to any data model.
- No population of the line-edits from the current selection.
- No enforcement or validation of the integer naming rule.
- The frame simply appears, can be hidden, and remembers its state.

After Phase 0 the hierarchy tool frame is a first-class citizen of the UI even though its deeper functionality remains future work.

---

## Phase 1 — Minimal two-way binding (selection → line-edit, line-edit → selection)

**Clarified behavior (2026-06-28)**: the `frameToolHierarchy` line-edits and checkbox must provide a live view + bulk-assign surface for the selected recordings.

### 1.1 Display rule (selection change → line-edit contents)

On `tableProjSelectionChanged` (or equivalent selection signal):

- If **exactly one** recording is selected, populate:
  - `lineEdit_hierarchy_subject` ← that row's `subject` value (or `""` if NaN/None)
  - `lineEdit_hierarchy_slice` ← that row's `slice` value
- If **multiple** recordings are selected:
  - If **all** share the identical non-null string in `subject`, write that string into the line-edit.
  - Otherwise (mixed or any NaN) write `""` (blank).
  - Same rule independently for `slice`.

Edge case: zero selections → both line-edits become `""` (or retain last single-selection value — decision can be "blank" for safety).

### 1.2 Apply rule (line-edit edit → selected rows)

When the user finishes editing either line-edit (e.g. `editingFinished` or explicit `returnPressed` signal; simplest is to connect both):

- If the line-edit text is non-empty, copy that value into the `subject` (or `slice`) column for **every** currently selected row in `df_project`.
- If the line-edit is cleared to blank while ≥1 rows are selected, the implementation may either (a) set those rows to `""`/`NaN` or (b) do nothing. Document the chosen behavior.

No per-recording commit button is required; the change is immediate on edit completion.

### 1.3 `checkBox_hierarchy_dd_is_subject` — persisted flag only

Wire the checkbox exactly like every other boolean in `checkBox`:

- In `UIstate.reset()` add the default entry:
  ```python
  self.checkBox["hierarchy_dd_is_subject"] = False
  ```
- Because the checkbox objectName is `checkBox_hierarchy_dd_is_subject`, the generic `connectUIstate`/`applyConfigStates` machinery (already scanning for `checkBox_*` widgets and routing through `checkBoxChanged`) will automatically keep the `uistate.checkBox` entry in sync and persist it via `cfg.pkl`.

**Remark**: at this time the flag has no behavior — it is stored and restored but never read by any drop handler or assignment routine. This satisfies the requirement to treat it "same as all other checkboxes" while making clear it is a placeholder for future drag-and-drop semantics.

### 1.4 Implementation notes (no designer change)

- Selection change hook: extend the existing `tableProjSelectionChanged` handler or add a lightweight helper `refreshHierarchyLineEdits()` called from it.
- Write back: connect `lineEdit_hierarchy_subject.editingFinished` (and likewise for slice) to `applyHierarchyToSelection()`.
- Both helpers read/write `self.get_df_project()` and finish with `tableUpdate()` (or the lighter `tableFormat` path) so the table reflects the new values.
- Because `df_project` may contain nullable string columns, guard against `pd.isna` / `pd.NA` when comparing.

### 1.5 Data-integrity corner cases

- Subject names must remain **strings**. The lowest-unique-integer rule is only applied at import time (see §2); subsequent edits in the line-edit are verbatim user input.
- No cross-validation against the integer namespace is performed here.
- Concurrent changes from elsewhere (e.g. future group-ops) simply re-trigger the display rule on the next selection change.

After Phase 1 the hierarchy frame is a functional inspector + bulk-assign tool while still respecting the "user owns deeper interaction" mandate.

---

## Detailed Requirements for v0.16_n

### 1. Schema change — add `subject` and `slice` columns (position-sensitive)

**Location**: `df_projectTemplate()` in `src/lib/ui_project.py`.

**New columns** (to be inserted immediately after `recording_name`):

| Column    | Dtype        | Purpose                                                  | Source on load                                                                          |
| --------- | ------------ | -------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `subject` | str          | Unique animal / biological sample identifier. Defines n. | Default: derive from `recording_name` or folder (policy TBD — see Options).             |
| `slice`   | str or Int64 | Slice identifier within subject.                         | Default: `"1"` (or `1`) — the program may assume one slice per unique animal on import. |

Column order in the template list must become:

```
...
"recording_name",
"subject",
"slice",
"gain",
...
```

Rationale: keeps logical grouping (`recording_name` + its hierarchical context) together; downstream code that iterates columns will encounter the new fields early.

**Deprecation markers** — modify the two comments:

```python
"paired_recording",  # DEPRECATED (paired-stimulus workflow). str: unique ID of paired recording
"Tx",                # DEPRECATED (paired-stimulus workflow). Boolean: Treatment / Control
```

No behavior change yet; the columns remain functional until a later cleanup removes the paired-stim logic.

### 2. Backward compatibility on load (explicit default policy)

When a project is loaded (or files are first imported) and `subject`/`slice` are absent or null:

- For every row, if `subject` is null/empty → set `subject = recording_name` (or a stable prefix derived from the source path).
- If `slice` is null/empty → set `slice = "1"` (string) or `1` (using the nullable `Int64` dtype consistent with `_INT_COLUMNS`).

This preserves the current "one-animal-one-slice" assumption without requiring any UI work in v0.16_n. The user will later provide an interface to re-assign these values; the schema already supports it.

**Option A (recommended for minimal diff)**: treat both columns as `object` (string) dtype; store `"1"` for the default slice. Keeps all columns homogeneous and simplifies editing/display.

**Option B**: add `"slice"` to `_INT_COLUMNS` and use `pd.Int64Dtype()` so that `1` renders as `1` not `1.0`. Requires a tiny dtype coercion after `df_projectTemplate()` returns.

Clarification needed: prefer A or B?

### 3. Table visibility (no designer change)

- **Compact view** (`formatTableLayout`): do **not** add `subject`/`slice` to the hardcoded `column_order` list unless the user explicitly requests them in the slim table. They will be hidden by default (existing behavior for undlisted columns).
- **Detailed view** (`detailedProjectTable == True`): the loop `for col_name in df_p.columns: if not in column_order: append` will automatically surface them. Their position in the DataFrame column order (right after `recording_name`) will determine where they appear among the "extra" columns.

If a friendlier compact layout is desired later, a follow-up plan can insert `"subject", "slice"` into `column_order` after the deprecation of the paired columns is complete.

### 4. No analysis or statistics changes required in v0.16_n

The statistical protocol (`statistical_protocol.md`) mandates:

> n = number of unique subjects (animals).  
> Slice and Recording improve measurement precision but do not increase sample size.

Mixed-effects models and hierarchical summaries are future work. The schema addition is a prerequisite; nothing in `statistics.py`, `analysis_v3.py`, or the test UI needs to read `subject`/`slice` yet. This plan deliberately stops at the data model.

### 5. Persistence & migration

- Existing `.parquet` project files that lack the two columns will be read with `NaN` in those positions.
- On first `set_df_project` or `tableUpdate` after load, the loader (or a small migration helper) can run the default synthesis described in §2.
- Subsequent saves will include the columns. No version bump of the project file format is required.

### 6. Documentation / comments

- Update the docstring of `df_projectTemplate` (or add a module-level comment) referencing `statistical_protocol.md`.
- Each new column should carry a comment:
  ```python
  "subject",  # str: biological subject / animal identifier (defines n per statistical_protocol.md)
  "slice",    # str: slice within subject; default "1" on import (nested repeated measure)
  ```

---

## Open Questions / Clarifications Needed

1. **Default synthesis policy** — when `subject` is missing on load (per clarification 2026-06-28):
   - Mark all unknown recordings as **unique subjects** by default.
   - Apply a **lowest-unique-integer naming convention**: scan existing subject values, assign the smallest positive integer not yet used (as a string, e.g. `"1"`, `"2"`, ...).
   - Example: if a freshly imported project has 3 recordings and no prior subjects, they become `"1"`, `"2"`, `"3"`. If a later import adds 2 more, they become `"4"`, `"5"`. If the user has already set some subjects manually, the algorithm respects those and fills gaps with the lowest available integers.

2. **Slice dtype** — string `"1"` (Option A) or nullable integer `1` (Option B)? The latter needs `"slice"` added to `_INT_COLUMNS`.

3. **Column ordering in compact table** — should `subject` and `slice` eventually appear in the slim view between `recording_name` and `groups`, or remain detail-only for now?

4. **Rename / edit scope** — the user stated: _"the interface to correct that (I'll do that bit)"_. Confirm that v0.16_n should **not** implement any editing UI, validators, or group-assignment helpers for `subject`/`slice`. The plan will only deliver the schema + safe defaults.

5. **Interaction with paired-stimulus deprecation** — is there any timeline or additional plan to actually remove the `paired_recording`/`Tx` code paths, or do we simply leave them marked deprecated indefinitely?

---

## Non-Goals (explicit)

- No changes to `ui_designer.py`.
- Phase 0 wiring is limited to show/hide + persistence.
- Phase 1 adds the **minimal** two-way binding described above; deeper drag-and-drop, validation, or integer-namespace enforcement is out of scope.
- No modifications to `statistics.py`, `analysis_v3.py`, or any mixed-model entry point.
- No automatic grouping or n-counting UI in the Groups or Test panels.
- The existing paired-stimulus workflow (`get_dfdiff`, `Tx` column, rename propagation) remains fully functional.

---

## Summary of Deliverables

| File                                 | Change                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/ui_state_classes.py`        | (1) Add `"frameToolHierarchy": True` entry inside `UIstate.reset()`. (2) Add `self.checkBox["hierarchy_dd_is_subject"] = False` default.                                                                                                                                                                                                 |
| `src/lib/ui.py`                      | (1) Add `"pushButton_hide_hierarchy": "triggerHideHierarchy"` and the two `editingFinished` handlers to `pushButtons`. (2) Implement `triggerHideHierarchy`, `refreshHierarchyLineEdits`, `applyHierarchyToSelection`. (3) Call the refresh helper from `tableProjSelectionChanged`. (4) Optional: minor comment in `formatTableLayout`. |
| `src/lib/ui_project.py`              | Add `"subject"` and `"slice"` to `df_projectTemplate()` column list (right after `recording_name`); mark `paired_recording` and `Tx` comments as DEPRECATED; optional dtype handling for `slice`.                                                                                                                                        |
| `work_plans/statistical_protocol.md` | (no change unless desired) — referenced for rationale.                                                                                                                                                                                                                                                                                   |

After Phases 0+1 + schema work the hierarchy frame is a live inspector + bulk-assign control with a persisted (but currently inert) checkbox flag, and the project DataFrame is compliant with the statistical protocol. Deeper subject/slice semantics (actual drag-and-drop behavior, integer namespace management) remain future work (user-supplied).
