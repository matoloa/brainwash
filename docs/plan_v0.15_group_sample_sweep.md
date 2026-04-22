# Plan v0.15: Group, Sample, and Sweep Selection (Test Sets)

## Mission Statement

The primary goal of version 0.15 is to introduce functionality that allows users to select, highlight, and categorize specific sweeps and recordings for enhanced statistical analysis and data presentation.

Users can highlight important sweeps (for example, two bins of 10 sweeps—one immediately before and one after a stimulus train) by click-and-drag on the output graph or by typing values into the sweep range `lineEdit` widgets. This selection is stored in `uistate.x_select["output"]` (a set of 0-based sweep indices) via `ui_interactive.py:drag_released` and related methods.

This version focuses on three pillars:

1. **Statistical Grouping** — Assign recordings to named, colored groups; persist via `groups.pkl`.
2. **Test Sets (Sweep Sets)** — `add_to_set` button tags the currently selected sweeps as a named, reusable "Test Set" for use in group-based t-tests (e.g. "use mean of sweeps 110-119 when comparing groups").
3. **Sample Designation for Visual Overlay** — Mark specific recordings/sweeps as "samples" so that representative raw traces can be overlaid on exported mean graphs.

All features integrate with the existing `GroupMixin` (in `ui_groups.py`), `DataFrameMixin.get_dfgroupmean()`, plotting system (`uiplot.addGroup()` / `unPlotGroup()`), the new `verticalLayoutTestSet`, and `verticalLayoutComparison` panel.

**Core Constraint**: NEVER alter `ui_designer.py` or run `puic`. All button wiring must be performed via the dynamic `self.pushButtons` dictionary in `UIstate.reset()` (consumed by `UIsub.connectUIstate()`). The button formerly known as `pushButton_compare` is now wired to `add_to_set`.

## Detailed Features

### 1. Sweep Selection & Highlighting

- **UI**: Drag on `canvasOutput` (or use `lineEdit_sweeps_range_from` / `to` + "Even"/"Odd" buttons).
- **Storage**: `uistate.x_select["output"]` (set of int sweep indices). Updated in `InteractivePlotMixin.drag_released()` and `xDrag()`.
- **Highlighting**: `uiplot.xSelect()` draws vertical spans or markers on the mean and output axes.
- **Use in v0.15**: Selected sweeps are captured by the `add_to_set` button to create named Test Sets. These sets are later used to subset group-mean DataFrames before running statistics.
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

Modeled directly on the Group controls pattern in `ui_groups.py:214-261` (`group_controls_add` / `group_controls_remove`):

- **UI**: New `verticalLayoutTestSet` (added in UI designer after the Tag frame). Dynamic widgets will be added here, similar to `verticalLayoutGroups`.
- **Data model** (`dd_testsets` — lives alongside `dd_groups` in `GroupMixin`):
  ```python
  {
    "baseline": {
      "name": "baseline",
      "sweeps": [0, 1, ..., 19],          # sorted list of 0-based indices
      "description": "Pre-stimulus reference sweeps",
      "color": "#888888",                 # for UI/legend
      "show": True
    },
    "post_train_1": {
      "name": "post_train_1",
      "sweeps": [110, 111, ..., 119],
      "description": "Sweeps immediately after first stimulus train",
      ...
    },
    ...
  }
  ```
- **Persistence**:
  - New helpers `testset_get_dd()` / `testset_save_dd()` will write `project/testsets.pkl` (parallel to `groups.pkl`).
  - Call `testset_save_dd()` after changes; integrate with existing `group_update_dfp()` for optional table summary column.
- **Core methods** (to be added to `GroupMixin`):
  - `testset_new(name=None, sweeps=None)` — create from current `uistate.x_select["output"]` or prompt for name.
  - `testset_remove(name)` / `testset_rename(old_name, new_name)`.
  - `add_to_set()` (renamed from `add_compare`):
    - Reads currently selected sweeps from `uistate.x_select.get("output", set())`.
    - Prompts for / uses a name (or adds to currently selected test set).
    - Updates `dd_testsets`, saves, and refreshes the `verticalLayoutTestSet` widgets.
  - Dynamic control creation (`testset_controls_add(name)`):
    - Similar pattern to `group_controls_add`: create widget (CustomCheckBox or QPushButton subclass), set objectName (`testSetWidget_{name}`), connect right-click for rename, add to `verticalLayoutTestSet`.
    - Menu integration under `menuGroups` or new `menuTestSets` (dynamic actions like "Use this set for comparison").
    - `testset_controls_remove(name)` mirrors `group_controls_remove` using `findChild`, `deleteLater()`, and attribute cleanup.
  - `get_testset(name)` — returns the sweep list for use in comparisons.
- **Comparison flow** (updated):
  - User creates 2+ Test Sets via `add_to_set` button.
  - A future "Compare groups using Test Set" action (or automatic) will:
    1. Let user pick a Test Set name.
    2. For each active group: `dfm = self.get_dfgroupmean(gid).loc[self.dd_testsets[set_name]["sweeps"]]`.
    3. Build `d_group_ndf` and call `analysis_v3.ttest_df(...)`.
    4. Display results in `verticalLayoutComparison`.
- **Edge cases**:
  - Clamp sweep indices to actual data length per recording.
  - Warn on empty selection or duplicate set names.
  - Persist across project reload via pickle.

### 4. Sample Designation for Visual Overlay

- **UI**: `pushButton_sample` ("Sample sweep") in the same `frameToolTag`.
- **Wiring**: Already points to `triggerSample()` → `sample_selected()`.
- **Storage**: Add a column `is_sample` (bool) to `df_project` and/or a separate `samples.pkl` list of `(rec_ID, sweep_idx)` tuples.
- **Behaviour**:
  - When clicked with a recording + sweep selection active, mark the first selected sweep (or all in range) of that recording as a sample.
  - `sample_selected()` should:
    - Update storage.
    - Add a "sample" entry to `uistate.dict_sample_lines`.
    - Call `uiplot.plot_sample_trace()` (new method) that draws a faint colored line on the mean graph.
- **Export integration**: When exporting mean graphs (`menuExport`), overlay the sample trace(s) with a legend entry "Example sweep".
- **Future**: Allow multiple samples per group; auto-pick "most representative" sweep by correlation to group mean. Test Sets can reference sample sweeps.

### 5. UI Integration Points

- **Tag frame** (`frameToolTag`): contains renamed `pushButton_compare` (now triggers `add_to_set`), `pushButton_sample`, `pushButton_hide_tag`.
- **Test Set panel**: `verticalLayoutTestSet` — will host dynamic widgets mirroring the Group checkbox pattern (rename on right-click, objectName-based cleanup, self-expanding list).
- **Comparison panel**: `verticalLayoutComparison` — remains the home for statistical result tables (populated after selecting a Test Set + groups).
- **Groups panel**: `verticalLayoutGroups` with colored `CustomCheckBox` widgets (already fully functional).
- **Menu**: `menuGroups` (extend with Test Set actions); shortcuts preserved where possible.
- **Graph**: Group means + future Test Set indicators; samples overlaid on top.
- **Project table**: Show `groups` and (optionally) `testsets` columns — updated via `group_update_dfp()` style helpers.

### 6. Storage & Cache

- `project/groups.pkl` — pickled `dd_groups`.
- `project/testsets.pkl` — new; pickled `dd_testsets`.
- `cache/group_{N}_mean.parquet` — per-group aggregated DataFrame (invalidated by `group_cache_purge`).
- `df_project["groups"]` (and future `testsets`) column for quick lookup.
- New: `project/samples.pkl` or `df_project["sample_sweeps"]`.
- All changes call appropriate save methods and `self.set_df_project(...)`. Test set changes should also trigger cache purge / graph refresh where relevant.

### 7. Phased Implementation Steps

**Phase 0 – Foundation (done)**

- Wiring of `pushButton_compare` (now `add_to_set`) and `pushButton_sample` via `pushButtons` dict.
- Existing group creation, assignment, caching, plotting, and `verticalLayoutTestSet` placeholder in UI.
- Stub `add_compare()` renamed to `add_to_set()`.

**Phase 1 – Test Set UI & Persistence (current priority)**

- Add `dd_testsets`, `testset_get_dd()`, `testset_save_dd()` to `GroupMixin`.
- Implement `testset_controls_add(name)`, `testset_controls_remove(name)` modeled exactly on `group_controls_add` / `group_controls_remove` (use `CustomCheckBox` or custom widget, right-click rename, `verticalLayoutTestSet.addWidget`).
- Flesh out `add_to_set(self)`:
  - Capture `selected_sweeps = sorted(uistate.x_select.get("output", set()))`.
  - Prompt for name or select existing set; store in `dd_testsets`.
  - Refresh controls and save pickle.
- Update plan document and add usage logging.

**Phase 2 – Group-based Comparison using Test Sets**

- Add `compare_using_testset(set_name)` that:
  - Loads selected Test Set.
  - Subsets each active group's mean DataFrame using the stored sweep list.
  - Calls `analysis_v3.ttest_df(...)`.
  - Populates `verticalLayoutComparison` with results table.
- Add `display_comparison(...)` helper (clear prior widgets first).
- Integrate with status bar and `graphRefresh()` / `tableUpdate()`.

**Phase 3 – Sample feature**

- Implement `sample_selected()` to store sample metadata.
- Add `plot_sample_trace(rec_ID, sweep)` in `UIplot` (reuse existing trace plotting but with distinct style: dashed, thinner, labeled).
- Hook into export routines so samples appear in final figures. Allow samples to be linked to specific Test Sets.

**Phase 4 – Polish & UI feedback**

- Add "New Test Set", "Rename", "Delete" controls in `verticalLayoutTestSet`.
- Status bar messages ("Added sweeps 110-119 to Test Set 'post_train_1'").
- Make comparison table sortable/exportable; add "Clear comparison" button.
- Persist last-used Test Set.
- Update `groupCheckboxChanged`, test set state changes, and refresh signals.
- Support >2 groups (pairwise or ANOVA using selected Test Set).

**Phase 5 – Testing & Release**

- Test with real electrophysiology projects (varying sweep counts, cache behavior).
- Verify both groups and testsets survive project close/re-open.
- Add unit tests in `analysis_evaluation.py`.
- Update README, changelog, and expand this plan with discovered details.
- Add screenshots to `docs/`.
- Tag release v0.15 once grouping, Test Sets, comparison, and samples are cohesive.

## Open Questions / TODOs in Plan

- Exact widget type for Test Sets (CustomCheckBox reuse vs new TestSetWidget class)?
- Should Test Sets be ordered? Support ranges in addition to flat lists?
- Automatic vs explicit comparison after creating/choosing a Test Set?
- UI for selecting which Test Set to use for a comparison (combo box in comparison panel?)?
- Visual design consistency between `verticalLayoutGroups` and `verticalLayoutTestSet`?
- Integration with existing `build_dfoutput` pipelines and paired vs unpaired tests?
- Where to store "comparison configuration" (metrics, normalization flags)?

## Success Criteria

- User can create groups and Test Sets (`add_to_set` button captures selected sweeps into named reusable sets shown dynamically in `verticalLayoutTestSet` with rename/delete support).
- Selecting a Test Set + groups produces statistical table in `verticalLayoutComparison` with correct p-values from `ttest_df` on the tagged sweep means.
- Sample button marks traces that appear overlaid on exported graphs.
- All data (`dd_groups`, `dd_testsets`, samples) persists across project close/re-open via pickles.
- No modifications to `ui_designer.py`, `ui_designer.py` remains untouched, and all dynamic controls follow the proven Group pattern.
- Code stays inside `GroupMixin` where it belongs for cohesion.

This plan provides a concrete, phased roadmap that builds directly on the existing architecture (`GroupMixin`, `get_dfgroupmean`, `uistate.x_select`, `verticalLayoutTestSet`, `verticalLayoutComparison`, `analysis_v3.ttest_df`) while respecting all coding constraints and the rename to `add_to_set`.
