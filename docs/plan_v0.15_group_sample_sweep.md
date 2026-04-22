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

- **UI**: `pushButton_sample` ("Sample sweep") in the same `frameToolTag`.
- **Wiring**: Already points to `triggerSample()` → `sample_selected()`.
- **Storage**: Add a column `is_sample` (bool) to `df_project` and/or a separate `samples.pkl` list of `(rec_ID, sweep_idx)` tuples. Test Sets may reference sample sweeps.
- **Behaviour**:
  - When clicked with a recording + sweep selection active, mark the first selected sweep (or all in range) of that recording as a sample.
  - `sample_selected()` should:
    - Update storage.
    - Add a "sample" entry to `uistate.dict_sample_lines`.
    - Call `uiplot.plot_sample_trace()` (new method) that draws a faint colored line on the mean graph.
- **Export integration**: When exporting mean graphs (`menuExport`), overlay the sample trace(s) with a legend entry "Example sweep".
- **Future**: Allow multiple samples per group or per Test Set; auto-pick "most representative" sweep by correlation to group mean.

### 5. UI Integration Points

- **Tag frame** (`frameToolTag`): contains renamed `pushButton_compare` (now triggers `add_to_set`), `pushButton_sample`, `pushButton_hide_tag`.
- **Test Set panel**: `verticalLayoutTestSet` — will host dynamic widgets mirroring the Group checkbox pattern (integer `set_ID`, default "set N" label, right-click rename, objectName-based cleanup, self-expanding list).
- **Comparison panel**: `verticalLayoutComparison` — remains the home for statistical result tables (populated after selecting a Test Set + groups).
- **Groups panel**: `verticalLayoutGroups` with colored `CustomCheckBox` widgets (already fully functional).
- **Menu**: `menuGroups` (extend with Test Set actions using `set_ID`); shortcuts preserved where possible.
- **Graph**: Group means + future Test Set indicators; samples overlaid on top.
- **Project table**: Show `groups` and (optionally) `testsets` columns — updated via `group_update_dfp()` style helpers.

### 6. Storage & Cache

- `project/groups.pkl` — pickled `dd_groups`.
- `project/test_sets.pkl` — new (underscore); pickled `dd_testsets` using integer `set_ID` keys (exactly like groups).
- `cache/group_{N}_mean.parquet` — per-group aggregated DataFrame (invalidated by `group_cache_purge`).
- `df_project["groups"]` (and future `testsets`) column for quick lookup.
- New: `project/samples.pkl` or `df_project["sample_sweeps"]`.
- All changes call appropriate save methods (`testset_save_dd()`, `group_save_dd()`) and `self.set_df_project(...)`. Test set changes should also trigger cache purge / graph refresh where relevant.

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

**Phase 2 – Visualizing Test Sets (next)**

- When a user drags to select sweeps on the output graph, a blue background (`axvspan`) is drawn via `uiplot.xSelect()`.
- All ticked (`show=True`) Test Sets should appear as gray `axvspan` backgrounds on the output graph (and optionally the mean graph), similar to the current selection highlight.
- Hook into `testsetCheckboxChanged`, `testsetControlsRefresh`, `graphRefresh()`, and checkbox state changes in `verticalLayoutTestSet`.
- New helper `visualizeTestSets()` (or extension of `xSelect()` / `graphRefresh()`) that iterates over `dd_testsets`, draws gray spans for active sets using their stored `sweeps` ranges, manages artist cleanup on changes, and respects `set_ID` ordering.
- Update `InteractivePlotMixin` or `UIplot` to support multiple persistent spans (store in `uistate` or a dict of test set artists).
- Call visualization on load, test set creation/rename/toggle, and sweep selection changes for immediate feedback.
- Gray color should be configurable (e.g. via `uistate.colors` or a muted default) and not interfere with the blue current-selection span.

**Phase 3 – Group-based Comparison using Test Sets**

- Add `compare_using_testset(set_ID)` that:
  - Loads selected Test Set by `set_ID`.
  - Subsets each active group's mean DataFrame using the stored sweep list.
  - Calls `analysis_v3.ttest_df(...)`.
  - Populates `verticalLayoutComparison` with results table.
- Add `display_comparison(...)` helper (clear prior widgets first).
- Integrate with status bar and `graphRefresh()` / `tableUpdate()`.

**Phase 4 – Sample feature**

- Implement `sample_selected()` to store sample metadata.
- Add `plot_sample_trace(rec_ID, sweep)` in `UIplot` (reuse existing trace plotting but with distinct style: dashed, thinner, labeled).
- Hook into export routines so samples appear in final figures. Allow samples to be linked to specific Test Sets.

**Phase 5 – Polish & UI feedback**

- Add "New Test Set", "Rename", "Delete" controls in `verticalLayoutTestSet` (leveraging integer `set_ID`).
- Status bar messages ("Added sweeps 110-119 to Test Set 2 (set 2)").
- Make comparison table sortable/exportable; add "Clear comparison" button.
- Persist last-used Test Set.
- Update `groupCheckboxChanged`, test set state changes (including visualization refresh), and refresh signals.
- Support >2 groups (pairwise or ANOVA using selected Test Set).

**Phase 6 – Testing & Release**

- Test with real electrophysiology projects (varying sweep counts, cache behavior).
- Verify both groups and test_sets survive project close/re-open.
- Add unit tests in `analysis_evaluation.py`.
- Update README, changelog, and expand this plan with discovered details.
- Add screenshots to `docs/`.
- Tag release v0.15 once grouping, Test Sets (with visualization), comparison, and samples are cohesive.

## Open Questions / TODOs in Plan

- Exact widget type for Test Sets (reuse `CustomCheckBox` with `set_ID` vs new `TestSetWidget` class)?
- Should Test Sets be ordered? Support ranges in addition to flat lists?
- How to handle overlapping Test Set spans in visualization (layering, alpha, legend)?
- Automatic vs explicit comparison after creating/choosing a Test Set by `set_ID`?
- UI for selecting which Test Set (`set_ID`) to use for a comparison (combo box in comparison panel?)?
- Visual design consistency between `verticalLayoutGroups` and `verticalLayoutTestSet`, and between blue current selection vs gray Test Set spans?
- Integration with existing `build_dfoutput` pipelines and paired vs unpaired tests?
- Where to store "comparison configuration" (metrics, normalization flags)?

## Success Criteria

- User can create groups and Test Sets (`add_to_set` button captures selected sweeps into integer `set_ID` entries with default names "set 1", "set 2", … shown dynamically in `verticalLayoutTestSet` with full rename/delete support matching the group pattern).
- Ticked Test Sets render as gray `axvspan` backgrounds on the output graph (via new visualization logic similar to `xSelect()`), updating on checkbox changes and refresh.
- Selecting a Test Set (`set_ID`) + groups produces statistical table in `verticalLayoutComparison` with correct p-values from `ttest_df` on the tagged sweep means.
- Sample button marks traces that appear overlaid on exported graphs.
- All data (`dd_groups`, `dd_testsets` in `test_sets.pkl`, samples) persists across project close/re-open via pickles.
- No modifications to `ui_designer.py`; all dynamic controls follow the proven Group pattern using integer IDs and default names.
- Code stays inside `GroupMixin` where it belongs for cohesion.

This plan provides a concrete, phased roadmap that builds directly on the existing architecture (`GroupMixin`, `get_dfgroupmean`, `uistate.x_select`, `verticalLayoutTestSet`, `verticalLayoutComparison`, `analysis_v3.ttest_df`) while respecting all coding constraints and the new `set_ID` + `test_sets.pkl` conventions. Visualization of Test Sets is now explicitly part of the v0.15 pillars.
