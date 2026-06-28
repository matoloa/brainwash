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

- **Core Semantics**: `<rec>` is the group's one and only sample recording. The test sets explain which sweeps from that rec are to be used for samples.
- **Data Structure**: `dd_group_samples` lives in `UIsub` (`self.dd_group_samples`). Outer dict is `group_ID: inner_dict`; inner dict is `test_ID: df`.
- **Data Access**: `get_ddgroup_sample(group_ID)` (new in `DataFrameMixin`) returns the inner dict if it exists in memory, otherwise reads it from the cache file (`<group_name>_sample.parquet`), if no file: build from scratch (modeled exactly on `get_dfgroupmean` / `get_dfmean` pattern, using sample rec + testset sweeps + same xSelect range constraints).
- **Computation & Visualization**: Compile a mean of the sweeps listed in the (single active) testset, on the same range constraints as in xSelect. New `sample_overlay()` in `ui_plot.py` reuses the plotted line logic from `axe`; places each sample in upper-left corner of output graph `ax1`/`ax2`, occupying one third of the height and width. Groups use their group colors; traces are superimposed. (For now, resolve a single test set only.)
- **Checkbox logic**: `is_sample_rec()` and `update_sample_checkbox()` only set correct state on the checkbox. The function that toggles the state (`set_group_sample()`) must also trigger refresh at some point.
- **Deletion**: Deleting a recording cascades into a group refresh, which should also trigger a sample refresh.
- **Export**: Hook into export routines so samples appear in final figures with suitable legend.

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
- 3.3 (now fully actionable):
  - In `DataFrameMixin` (`ui_data_frames.py`): add `self.dd_group_samples = {}` to `loadProject()` and `resetCacheDicts()`. Implement `get_ddgroup_sample(group_ID)` exactly mirroring `get_dfgroupmean`: (1) return from `self.dd_group_samples` if present, (2) read parquet cache file if exists, (3) else build (locate sample rec from `dd_groups[group_ID]["sample"]`, take sweeps from active testset, compute mean using identical xSelect range constraints, persist parquet, cache and return the inner dict `{test_ID: df}`).
  - In `UIplot` (`ui_plot.py`): implement `sample_overlay(self, dd_group_samples)`: clear prior sample artists (`uistate.sample_artists`), for each group with data reuse `axe`-style line plotting, position in upper-left of `ax1`/`ax2` (1/3 height/width, group color from `dd_groups`, superimposed, y-aligned, zorder/alpha compatible with light/dark mode and testset spans). Store artists for management.
  - Add dedicated `refresh_samples(self)` (see new section below) that populates `dd_group_samples` via the getter then calls `uiplot.sample_overlay(...)).
- 3.4 Flesh out skeletal functions (detailed sub-plan referencing update_axe_mean lines 306-352):
  - **3.4.1 Complete get_ddgroup_sample (ui_data_frames.py)**: Replace stub (current lines ~576-595) with full logic mirroring `update_axe_mean` (306-352) exactly: if no sample pointer in `dd_groups[group_ID]["sample"]` return `{}`; else resolve active testset (first checked `set_ID`), get its `"sweeps"` (or fall back to `uistate.x_select["output"]`), locate sample recording's `df = self.get_dfoutput(...)` or `uistate.df_rec_select_data` equivalent, filter with `df_sweeps = df[df["sweep"].isin(selected)]`, compute `df_mean = df_sweeps.groupby("time", as_index=False)[col].mean()` where `col = uistate.settings.get("filter") or "voltage"`, then loop over `df_t = self.get_dft(...)` (or `uistate.df_rec_select_time`) for per-stim windows: `window_start = t_stim + settings["event_start"]`, `window_end = ...`, extract `df_event`, shift `df_event["time"] -= t_stim`. The resulting DataFrames stored in `dd_group_samples[group_ID][test_ID]` **must retain a 'stim' column** and have **all time values shifted so each stim starts at t=0** (exactly as done in update_axe_mean lines 320-340). This enables easy extraction of specific stims and direct superimposition. Persist full mean_df via `self.df2file(..., key="sample")` as `<group_name>_sample.parquet`, store `self.dd_group_samples[group_ID] = {test_ID: mean_df}`, return inner dict. Add invalidation in `group_cache_purge` and testset CRUD.
  - **3.4.2 Implement full sample_overlay (ui_plot.py)**: Extend current stub (lines ~239-277) to exactly reuse `update_axe_mean` pattern (306-352): for each group_ID/test_ID retrieve mean_df (which has 'stim' column and t=0 per stim), call `self.plot_line(...)` with group color from `dd_groups`, `alpha = uistate.settings["alpha_line"]/2`, shifted `df_event["time"]`, per-stim event windows, and `stim=stim_num`. Create 1/3-size upper-left inset on `ax1`/`ax2` via `inset_axes([0.02, 0.68, 0.33, 0.30])` or `transAxes`; y-aligned only (share ylim or scale manually). Support multiple groups with vertical nudge/alpha stacking. Store in `uistate.sample_artists[(group_ID, test_ID)] = line` (mirroring `dict_rec_labels` and `testset_spans`). Hook into `styleUpdate` and `clear_axe_mean` style cleanup. Single `canvas.draw()` at end. Call `self.clear_sample_artists()` first (new helper modeled on `clear_testset_spans` lines 224-253).

Debugging 3.4.2, state 2026-04-22
Loads of code added to ui_plot.py in attempts address two issues:

1. group samples are never displayed, at all, ever.
2. display of the overlay does not respect show states of test sets, or groups
   Might be worth addressing with a series of print commands to see what's going on

- **3.4.3 Wire refresh_samples fully (GroupMixin in ui_groups.py + ui.py)**: Expand stub to loop over groups with non-None "sample", call `self.get_ddgroup_sample(g)` (populating via the update_axe_mean-style build), then `uiplot.sample_overlay(self.dd_group_samples, self.dd_groups)`. Add calls from: `testset_new/remove/rename`, `group_remove`, `checkBox_is_group_sample_changed` (after line 3930), `tableProjSelectionChanged` (after line 833 `update_sample_checkbox()`), recording deletion, and `graphRefresh` (after line 679 `update_axe_mean`).
- **3.4.4 Export integration (export_data.py / ui_plot.py menuExport)**: In figure export paths, if `uistate.sample_artists`, ensure visible, add legend "Sample (group X)" using group color (reuse `plot_line` + `dict_rec_labels` pattern from axe mean), include in EPS/PNG/PDF. Add optional toggle.
- 3.5 Hook `refresh_samples()` into all locations listed in the Sample Refresh Behavior section
- 3.6 update export routines (`menuExport` etc.) to include sample artists/legend.

### Sample Refresh Behavior (new dedicated section)

- Dedicated `refresh_samples(self)` method (added to `UIsub`/`GroupMixin`; per clarification 4). It rebuilds `self.dd_group_samples` (via `get_ddgroup_sample` for every group that has a sample pointer) then calls `uiplot.sample_overlay(self.dd_group_samples)`. The DataFrames in `dd_group_samples[group_ID][test_ID]` retain a 'stim' column and have all time values shifted so each stim starts at t=0 (exactly as done in update_axe_mean lines 320-340). This enables easy extraction of specific stims and direct superimposition.
- Triggers (per clarifications 4-6):
  - `set_group_sample()` (after `group_save_dd()`).
  - Test set CRUD (`testset_new()`, `testset_remove()`, rename) — sweeps used for mean may change.
  - Group removal, recording deletion (cascades into group refresh which must also call sample refresh).
  - `graphRefresh()`, `checkBox_is_group_sample_changed()`, and any other state change affecting samples.
- Keeps sample computation lazy/isolated; mirrors `graphRefresh(dd_groups, dd_testsets)` pattern. No full cache purge on every toggle.

- Add "New Test Set", "Rename", "Delete" controls in `verticalLayoutTestSet` (leveraging integer `set_ID`).
- Status bar messages ("Added sweeps 110-119 to Test Set 2 (set 2)").
- Persist last-used Test Set.
- Update `groupCheckboxChanged`, test set state changes (including visualization refresh), and refresh signals.

## Open Questions / TODOs in Plan

- Exact widget type for Test Sets (reuse `CustomCheckBox` with `set_ID` vs new `TestSetWidget` class)?
- Should Test Sets be ordered? Support ranges in addition to flat lists?
- How to handle overlapping Test Set spans in visualization (layering, alpha, legend)?
- Automatic vs explicit comparison after creating/choosing a Test Set by `set_ID`?
- UI for selecting which Test Set (`set_ID`) to use for a comparison (combo box in comparison panel?)?
- Visual design consistency between `verticalLayoutGroups` and `verticalLayoutTestSet`, between blue current selection vs gray Test Set spans, and for `checkBox_is_group_sample` + sample overlay (exact inset_axes coords per update_axe_mean reuse, vertical nudge for multiple groups, legend entry)?
- Integration with existing `build_dfoutput` pipelines and paired vs unpaired tests?
- Where to store "comparison configuration" (metrics, normalization flags)?
- Which testset is "active" for sample mean when multiple are checked (first? last? explicit flag in uistate?)?
- Should sample parquet also store originating sweep indices / df_t metadata for audit/debug (as done in update_axe_mean lines 320-340)?

## Success Criteria

- User can create groups and Test Sets (`add_to_set` button captures selected sweeps into integer `set_ID` entries with default names "set 1", "set 2", … shown dynamically in `verticalLayoutTestSet` with full rename/delete support matching the group pattern).
- Ticked Test Sets render as gray `axvspan` backgrounds on the output graph (via new visualization logic similar to `xSelect()`), updating on checkbox changes and refresh.
- Selecting a Test Set (`set_ID`) + groups produces statistical table in `verticalLayoutComparison` with correct p-values from `ttest_df` on the tagged sweep means.
- `<rec>` is the group's one and only sample; test sets define which of its sweeps are averaged. `dd_group_samples` (in `UIsub`) uses `group_ID: {test_ID: df}` structure (DataFrames **must retain a 'stim' column** and have **all time values shifted so each stim starts at t=0**, exactly as in update_axe_mean lines 320-340). Persisted as `<group_name>_sample.parquet`. `get_ddgroup_sample(group_ID)` (in `DataFrameMixin`, mirroring `get_dfgroupmean` and `update_axe_mean` lines 306-352) returns from memory/cache or builds using sample rec + testset sweeps + exact `df_sweeps.groupby("time")` + `df_t` per-stim window + `plot_line` shifted-time pattern. This enables easy extraction of specific stims and direct superimposition.
- `checkBox_is_group_sample` / `update_sample_checkbox()` / `is_sample_rec()` correctly reflect/set state (only on single grouped recording; `set_group_sample()` updates `dd_groups[...]["sample"]` and triggers `refresh_samples()`). `refresh_samples()` (new dedicated method) populates `dd_group_samples` then calls `uiplot.sample_overlay()`.
- `sample_overlay()` in `ui_plot.py` reuses `update_axe_mean` (306-352) line logic exactly (`df_mean`, `df_event` windowing, `plot_line` with `df_event["time"] - t_stim`, group color, alpha, zorder), places superimposed traces in 1/3-size upper-left inset of `ax1`/`ax2` (y-aligned only; single testset for now), with proper artist management in `uistate.sample_artists`, zorder/alpha for light/dark mode and testset spans.
- Deletion of recording/group and testset CRUD all trigger `refresh_samples()`. Samples appear in exported figures with legend entry "Sample (group X)". All data (`dd_groups` with sample pointers, `dd_testsets`, parquet caches) persists across reloads. No modifications to `ui_designer.py`.
- Code stays inside `GroupMixin`/`DataFrameMixin`/`UIplot` where it belongs for cohesion. Phase 3.4 sub-plan (full `get_ddgroup_sample` mirroring update_axe_mean lines 316-340 for mean/windowing, inset plotting + artist storage, full refresh wiring, export) completed without side effects.

This plan provides a concrete, phased roadmap that builds directly on the existing architecture (`GroupMixin`, `get_dfgroupmean`, `uistate.x_select`, `verticalLayoutTestSet`, `verticalLayoutComparison`) while respecting all coding constraints and the new `set_ID` + `test_sets.pkl` conventions. Visualization of Test Sets is now explicitly part of the v0.15 pillars.
