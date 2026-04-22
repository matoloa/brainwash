# Plan v0.15: Group, Sample, and Test Sets

## Mission Statement

The primary goal of version 0.15 is to introduce functionality that allows users to select, highlight, and categorize specific sweeps and recordings for enhanced statistical analysis and data presentation.

Users can highlight important sweeps (for example, two bins of 10 sweeps—one immediately before and one after a stimulus train) by click-and-drag on the output graph or by typing values into the sweep range `lineEdit` widgets. This selection is stored in `uistate.x_select["output"]` (a set of 0-based sweep indices) via `ui_interactive.py:drag_released` and related methods.

This version focuses on three pillars:

1. **Statistical Grouping** — Assign recordings to named, colored groups; persist via `groups.pkl`.
2. **Test Sets** — `add_to_set` button tags the currently selected sweeps as a named, reusable Test Set (integer `set_ID` with default name "set 1", "set 2", …) for use in group-based t-tests (e.g. "use mean of sweeps 110-119 when comparing groups"). Users can rename sets to descriptive labels.
3. **Sample Designation for Visual Overlay** — Mark specific recordings/sweeps as "samples" so that representative raw traces can be overlaid on exported mean graphs.

All features integrate with the existing `GroupMixin` (in `ui_groups.py`), `DataFrameMixin.get_dfgroupmean()`, plotting system (`uiplot.addGroup()` / `unPlotGroup()`), the new `verticalLayoutTestSet`, and `verticalLayoutComparison` panel.

**Core Constraint**: NEVER alter `ui_designer.py` or run `puic`. All button wiring must be performed via the dynamic `self.pushButtons` dictionary in `UIstate.reset()` (consumed by `UIsub.connectUIstate()`). The button formerly known as `pushButton_compare` is now wired to `add_to_set`.

## Detailed Features

### 1. Sweep Selection & Highlighting

- **UI**: Drag on `canvasOutput` (or use `lineEdit_sweeps_range_from` / `to` + "Even"/"Odd" buttons).
- **Storage**: `uistate.x_select["output"]` (set of int sweep indices). Updated in `InteractivePlotMixin.drag_released()` and `xDrag()`.
- **Highlighting**: `uiplot.xSelect()` draws vertical spans or markers on the mean and output axes.
- **Use in v0.15**: Selected sweeps are captured by the `add_to_set` button to create named Test Sets (using current `set_ID`). These sets are later used to subset group-mean DataFrames before running statistics.
- **Future**: Allow saving/loading named sweep selections per project.

### 2. Statistical Grouping Mechanics (`ui_groups.py` + `ui_data_frames.py`)

- **Data model** (`dd_groups`):
  ```python
  {
    1: {
      "group_name": "pre-stim",
      "color": "#FF0000",
      "show": True,
      "rec_IDs": ["rec_001.abf", "rec_002.abf", ...]
    },
    ...
  }
  ```
- **Persistence**:
  - `group_get_dd()` / `group_save_dd()` use `project/groups.pkl`.
  - Group means cached as `cache/group_{ID}_mean.parquet` (built by `get_dfgroupmean()`).
- **Core methods** (already in `GroupMixin`):
  - `group_new()`, `group_remove()`, `group_rename()`
  - `group_rec_assign(rec_ID, group_ID)`, `group_rec_ungroup(...)`
  - `group_selection(group_ID)` — toggles selected recordings into/out of a group (bound to dynamic menu actions `actionAddTo_N`).
  - `get_groupsOfRec(rec_ID)` — returns list of group IDs a recording belongs to.
  - `group_cache_purge(group_IDs)` — clears cache + replots updated means via `uiplot.addGroup(...)` using `self.V2mV(self.get_dfgroupmean(group_ID))`.
- **Mean computation** (`DataFrameMixin.get_dfgroupmean`):
  - Concatenates `get_dfoutput()` from all recordings in the group.
  - Aggregates per-sweep `mean` / `SEM` for `EPSP_amp*`, `EPSP_slope*`, and normalized variants.
  - Updated automatically on group membership changes.

### 3. Test Set Mechanics (Sweep Sets / Data Sets for Comparison)

Modeled **exactly** on the Group controls pattern in `ui_groups.py:214-261` (`group_controls_add` / `group_controls_remove`), but using integer `set_ID` keys (starting at 1) with default names "set 1", "set 2", … . The user can rename them to descriptive strings.

- **UI**: New `verticalLayoutTestSet` (added in UI designer after the Tag frame). Dynamic widgets will be added here, mirroring `verticalLayoutGroups`.
- **Data model** (`dd_testsets` — lives alongside `dd_groups` in `GroupMixin`):
  ```python
  {
    1: {
      "set_name": "set 1",                    # default; user can rename via right-click
      "show": True,
      "sweeps": [0, 1, ..., 19],              # sorted list of 0-based indices
    },
    2: {
      "set_name": "set 2",
      "show": True,
      "sweeps": [110, 111, ..., 119],
    },
    ...
  }
  ```
- **Persistence**:
  - New helpers `testset_get_dd()` / `testset_save_dd()` will write `project/test_sets.pkl` (underscore, parallel to `groups.pkl`).
  - Call `testset_save_dd()` after changes; integrate with existing `group_update_dfp()` for optional table summary column (`testsets`).
- **Core methods** (to be added to `GroupMixin`, aligned closely with group methods):
  - `testset_new()` — creates next integer `set_ID`, default name `"set {ID}"`, stores current `uistate.x_select["output"]` (sorted), calls `testset_controls_add(set_ID)`.
  - `testset_remove(set_ID=None)`, `testset_rename(set_ID, new_name)`.
  - `add_to_set()` (renamed from `add_compare` and the primary entry point):
    - Reads currently selected sweeps from `uistate.x_select.get("output", set())`.
    - If no selection, warn. Otherwise create new set via `testset_new()` or add to an active set.
    - Updates `dd_testsets`, saves to `test_sets.pkl`, refreshes `verticalLayoutTestSet`.
  - Dynamic control creation (`testset_controls_add(set_ID)`):
    - Mirrors `group_controls_add` exactly: creates `CustomCheckBox` (or lightweight subclass), sets `objectName` (`checkBox_testset_{set_ID}` or similar), right-click connects to rename, adds to `verticalLayoutTestSet`, sets color/style, connects state change.
    - Menu integration under `menuGroups` or new `menuTestSets` (dynamic actions).
    - `testset_controls_remove(set_ID=None)` mirrors `group_controls_remove` using `findChild`, `deleteLater()`, and attribute cleanup.
  - `get_testset(set_ID)` — returns the sweep list (or full dict) for use in comparisons.
  - `get_testsetsOfRec` / cache helpers as needed to keep symmetry with groups.
- **Comparison flow** (updated):
  - User creates Test Sets via `add_to_set` button (auto-assigns incremental `set_ID` with default "set N" name; rename freely).
  - A future "Compare groups using Test Set" action (or button in comparison panel) will:
    1. Let user pick a `set_ID`.
    2. For each active group: `dfm = self.get_dfgroupmean(gid).loc[self.dd_testsets[set_ID]["sweeps"]]`.
    3. Build `d_group_ndf` and call `analysis_v3.ttest_df(...)`.
    4. Display results in `verticalLayoutComparison`.
- **Edge cases**:
  - Clamp sweep indices to actual data length per recording.
  - Warn on empty selection, duplicate names after rename, or <2 groups.
  - Default names generated like groups (`set 1`, `set 2`, …); `set_ID` starts at 1 and grows like `group_ID`.
  - Persist across project reload via `test_sets.pkl`.

### 4. Sample Designation for Visual Overlay

- **UI**: `checkBox_is_group_sample` (replaces previous pushButton_sample) in the `frameToolTag`.
- **Wiring**: Handled inside `tableProjSelectionChanged()` (lines ~822-992); updates checkbox state and connects toggles to `sample_selected()`.
- **Storage**: Sample pointer lives _only_ inside `dd_groups[group_ID]["sample"] = (rec_ID: str, sweep: int) | None` (no `df_project` flag/column, no `is_sample`, no `samples.pkl`). A group has no or one sample; that sample is shared across all Test Sets.
- **Behaviour**:
  - Checkbox enabled only on exactly one recording that belongs to at least one group (groups listed in `df_project["groups"]` column); otherwise disabled.
  - Checked only if the single selected recording _is_ the sample for **all** groups it belongs to.
  - Clicking toggles: sets/clears the sample pointer (using current `x_select["output"]` sweep) in relevant group dicts only.
  - `sample_selected()` updates the group dict(s), calls `group_save_dd()`, then triggers `sample_overlay()` (no full cache purge).
  - New `sample_overlay()` (preferred name; in `ui_plot.py`) reuses the plotted line from `axe`, overlays it (group color, y-axis only, thin) in the upper-left corner of the output graph (ax1/ax2); supports multiple samples. Clearing updates only the overlay and the sample key in `dd_groups`.
- **Export integration**: When exporting mean graphs (`menuExport`), overlay the sample trace(s) with a legend entry "Example sweep".
- **Future** (v0.16): Allow multiple samples per group or per Test Set; auto-pick "most representative" sweep by correlation to group mean; unit tests.

### 5. UI Integration Points

- **Tag frame** (`frameToolTag`): contains renamed `pushButton_compare` (now triggers `add_to_set`), `checkBox_is_group_sample`, `pushButton_hide_tag`.
- **Test Set panel**: `verticalLayoutTestSet` — will host dynamic widgets mirroring the Group checkbox pattern (integer `set_ID`, default "set N" label, right-click rename, objectName-based cleanup, self-expanding list).
- **Comparison panel**: `verticalLayoutComparison` — remains the home for statistical result tables (populated after selecting a Test Set + groups).
- **Groups panel**: `verticalLayoutGroups` with colored `CustomCheckBox` widgets (already fully functional).
- **Menu**: `menuGroups` (extend with Test Set actions using `set_ID`); shortcuts preserved where possible.
- **Graph**: Group means + future Test Set indicators; samples overlaid (via `sample_overlay()`) on output graph (upper-left, y-axis only, group color).
- **Project table**: Show `groups` and (optionally) `testsets` columns — updated via `group_update_dfp()` style helpers (no sample column; sample state lives _only_ in `dd_groups`).

### 6. Storage & Cache

- `project/groups.pkl` — pickled `dd_groups` (now includes optional `"sample": (rec_ID, sweep) | None` per group; at most one sample per group, shared by all Test Sets).
- `project/test_sets.pkl` — pickled `dd_testsets` using integer `set_ID` keys (exactly like groups).
- `cache/group_{N}_mean.parquet` — per-group aggregated DataFrame (invalidated by `group_cache_purge`).
- `df_project["groups"]` (and future `testsets`) column for quick lookup (no `is_sample`, no `sample_sweeps` column, no `samples.pkl`; groups column used for checkbox enable/disable checks).
- All changes call appropriate save methods (`testset_save_dd()`, `group_save_dd()`) and refresh signals. Clearing/setting a sample updates only the sample key in `dd_groups` and calls `sample_overlay()`.

### 7. Phased Implementation Steps

**Phase 0 – Foundation (done)**

- Wiring of `pushButton_compare` (now `add_to_set`) and `pushButton_sample` via `pushButtons` dict.
- Existing group creation, assignment, caching, plotting, and `verticalLayoutTestSet` placeholder in UI.
- Stub `add_compare()` renamed to `add_to_set()`.

**Phase 1 – Test Set UI & Persistence (completed)**

- Added `dd_testsets`, `testset_get_dd()`, `testset_save_dd()` to `GroupMixin` (modeled on group equivalents; persists in `test_sets.pkl` with integer `set_ID` keys).
- Implemented `testset_new()` (auto-assigns next `set_ID`, default name `"set {ID}"`, captures current `uistate.x_select["output"]` as sorted "sweeps" list, calls controls refresh and save).
- Updated `add_to_data_set()` (renamed entrypoint) to validate selection then call `testset_new()`.
- Added `testset_controls_add(set_ID)`, `testset_controls_remove(set_ID)`, `testsetControlsRefresh()` (mirrors `group_controls_*` pattern exactly using `verticalLayoutTestSet`, `CustomCheckBox(set_ID)`, right-click rename via `triggerTestSetRename`, objectName cleanup with `checkBox_testset_{ID}`).
- Added `testsetCheckboxChanged()` and `triggerTestSetRename()` in `ui.py` (mirrors group versions, calls `testset_save_dd()`, `testsetControlsRefresh()`, usage logging).
- Initialized `self.dd_testsets = self.testset_get_dd()` in `loadProject()` (after groups) and `self.dd_testsets = {}` in `resetCacheDicts()`.
- `testset_rename()` is implemented (valid name check, save, refresh). Full menu integration, `group_update_dfp()` extension for testsets column, visualization (new Phase 2), and comparison logic remain for next phases.

**Phase 2 – Visualizing Test Sets (completed)**

- Implemented `clear_testset_spans()` and `visualize_test_sets(dd_testsets)` in `UIplot` (after `xSelect`/`xDeselect`).
- Gray per-set colored `axvspan` (using each set's own `dd_testsets[...]["color"]`, alpha=0.08, zorder=1, label=`"testset_span_{ID}"`) on output graph **only** (ax1 + ax2 twinx; no mean graph).
- Uses min/max of stored `"sweeps"` list (assumes continuous/sorted for now; overlaps stack alpha).
- Hooks: `graphRefresh(self.dd_groups, self.dd_testsets)` (calls visualize after drag maintenance), `testsetCheckboxChanged` now calls `graphRefresh()`, CRUD in `GroupMixin` (`testset_new`/`rename`/`remove`) trigger refresh, `uistate.testset_spans = {}` for artist management, cleared safely on output reset.
- No legend entry; works in light/dark; persisted visibility via existing `"show"` flag.
- Matches plan clarifications; no changes to `ui_designer.py`.

**Phase 3 – Sample feature**

- 3.1 Implement `set_group_sample()` (in `GroupMixin`) to toggle sample key _only_ in relevant `dd_groups[group_ID]["sample"] = rec_ID: str | None` (or clear it); a group has at most one sample (shared by all Test Sets). This also calls `group_save_dd()` to persist the changes.
- 3.2 Make ui.py def tableProjSelectionChanged update checkBox_is_group_sample to appropriate state.
  - tableProjSelectionChanged already checks if exactly one rec is selected. If not, set checkBox_is_group_sample unchecked and visibly disable it.
  - If one rec is selected, enable checkBox_is_group_sample and set it to the return of is_sample_rec(). This function returns True only if the selected rec_ID is the sample of all groups that it is a member of.
- 3.3 Add separate `sample_overlay()` function in `ui_plot.py` (reuses plotted line from `axe`, overlays it in upper-left corner of output graph ax1/ax2 using group color, y-axis only; supports all samples). Sample state lives _exclusively_ in `dd_groups`.
- 3.4 Hook into export routines so samples appear in final figures.

**Phase 4 – Polish & UI feedback**

- Add "New Test Set", "Rename", "Delete" controls in `verticalLayoutTestSet` (leveraging integer `set_ID`).
- Status bar messages ("Added sweeps 110-119 to Test Set 2 (set 2)").
- Make comparison table sortable/exportable; add "Clear comparison" button.
- Persist last-used Test Set.
- Update `groupCheckboxChanged`, test set state changes (including visualization refresh), and refresh signals.
- Support >2 groups (pairwise or ANOVA using selected Test Set).

## Open Questions / TODOs in Plan

- Exact widget type for Test Sets (reuse `CustomCheckBox` with `set_ID` vs new `TestSetWidget` class)?
- Should Test Sets be ordered? Support ranges in addition to flat lists?
- How to handle overlapping Test Set spans in visualization (layering, alpha, legend)?
- Automatic vs explicit comparison after creating/choosing a Test Set by `set_ID`?
- UI for selecting which Test Set (`set_ID`) to use for a comparison (combo box in comparison panel?)?
- Visual design consistency between `verticalLayoutGroups` and `verticalLayoutTestSet`, between blue current selection vs gray Test Set spans, and for `checkBox_is_group_sample` + sample overlay (upper-left on output graph)?
- Integration with existing `build_dfoutput` pipelines and paired vs unpaired tests?
- Where to store "comparison configuration" (metrics, normalization flags)?
- Details of `sample_overlay()` placement, y-axis scaling, and multi-sample handling on ax1/ax2.

## Success Criteria

- User can create groups and Test Sets (`add_to_set` button captures selected sweeps into integer `set_ID` entries with default names "set 1", "set 2", … shown dynamically in `verticalLayoutTestSet` with full rename/delete support matching the group pattern).
- Ticked Test Sets render as gray `axvspan` backgrounds on the output graph (via new visualization logic similar to `xSelect()`), updating on checkbox changes and refresh.
- Selecting a Test Set (`set_ID`) + groups produces statistical table in `verticalLayoutComparison` with correct p-values from `ttest_df` on the tagged sweep means.
- `checkBox_is_group_sample` correctly reflects/sets sample state (only on single grouped recording; toggles `dd_groups[...]["sample"]`); `sample_overlay()` draws axe-based trace (group color, y-only) in upper-left of output graph.
- All data (`dd_groups` with sample pointers, `dd_testsets` in `test_sets.pkl`) persists across project close/re-open via pickles. Clearing sample updates only overlay + dict key.
- No modifications to `ui_designer.py`; all dynamic controls follow the proven Group pattern using integer IDs and default names.
- Code stays inside `GroupMixin` where it belongs for cohesion.

This plan provides a concrete, phased roadmap that builds directly on the existing architecture (`GroupMixin`, `get_dfgroupmean`, `uistate.x_select`, `verticalLayoutTestSet`, `verticalLayoutComparison`) while respecting all coding constraints and the new `set_ID` + `test_sets.pkl` conventions. Visualization of Test Sets is now explicitly part of the v0.15 pillars.
