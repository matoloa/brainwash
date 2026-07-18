# Plan: Extract Remaining Logic from UIsub into Mixins (ui.py Refactor)

**Date**: 2026-07-12  
**Status**: **Archived** (2026-07-18). ✅ Complete (Phases 0–5). Manual regression: [../manual_smokes_after_refactor.md](../manual_smokes_after_refactor.md).  
**Related**: Previous mixin_problems.md (Archive/), UI refactor History indices.

## Background

`src/lib/ui.py` remains the largest file despite prior extractions using the established mixin pattern:

```python
class UIsub(
    ui_designer.Ui_mainWindow,
    ui_groups.GroupMixin,
    ui_sweep_ops.SweepOpsMixin,
    ui_project.ProjectMixin,
    ui_data_frames.DataFrameMixin,
    ui_menus.MenuMixin,
    export_data.ExportMixin,
    ui_interactive.InteractivePlotMixin,
):
```

### Existing Mixin Coverage (approximate method counts)
- `GroupMixin` (ui_groups.py): ~29 (groups, testsets, dd management)
- `SweepOpsMixin` (ui_sweep_ops.py): ~22 (sweep selection/removal/splitting)
- `ProjectMixin` (ui_project.py): ~16 (bootstrap, loadProject, new/open, persist, df2file)
- `DataFrameMixin` (ui_data_frames.py): ~22 (get_df*, recalculate, level-aware group means, V2mV)
- `MenuMixin` (ui_menus.py): ~5
- `ExportMixin` (export_data.py): ~9
- `InteractivePlotMixin` (ui_interactive.py): ~36 (mouse/drag/ghost/zoom events)

Many coordination, table, graph refresh, parse, and stat test methods remain in `UIsub` inside `ui.py`. There are also ~15 small helper classes defined at the top of `ui.py` (Config, TableModel, dialogs, threads, MplCanvas, etc.).

Code comments already flag opportunities:
- "trigger functions TODO: break out the big ones"
- "WIP section: TODO: move to appropriate header"
- "uisub init refactoring (bootstrap and loadProject live in ProjectMixin)"
- Sections like "# Selection changers", "# Graph interface", "# Table handling"

## Goals
- Reduce `ui.py` size significantly (target: core `UIsub` + wiring < ~2500-3000 LOC).
- Move clusters of related methods into **existing mixins** (prefer when logical) or **new mixins** with clear, consistent names.
- Preserve the current multiple-inheritance + module-level singleton injection pattern for consistency (see mixin_problems.md for known drawbacks; this plan does not overhaul the injection mechanism).
- Improve navigability: related code lives together in files named after their concern.
- Keep all cross-calls working via `self.` (UIsub remains the shared host).
- First, extract the polluting small Qt/helper classes.
- Enable future work (e.g. better testing, composition experiments) without breaking the app.

**Non-goals**:
- Switch to composition / service objects (defer; would address deeper mixin drawbacks).
- Change singleton injection.
- Full rewrite of signal wiring or Qt setup.
- Moving heavy implementation (plotting stays in ui_plot.py; mouse logic stays in ui_interactive.py).

## Analysis: Method Clusters in UIsub (defined directly in ui.py)

(Inventory derived from AST + section comments. Many "trigger*" are thin dispatchers; some have already been partially moved per comments.)

**Core / Lifecycle / Setup** (~17+)
- `__init__`, `closeEvent`, `_cleanup_threads`, `_save_cfg_now`, `_debounced_save_cfg`
- `uiFreeze`, `uiThaw`
- `setupFolders`, `build_dict_folders`, `connectUIstate`, `applyConfigStates`
- `setupCanvases`, `setupTableProj`, `setupTableStim`, `setupToolBar`, `formatTableLayout`, `formatTableStimLayout`, `setSplitterSizes`

**Table + Basic Selection** 
- `tableProjSelectionChanged`, `tableUpdate`, `_restore_table_selection`, `tableFormat`
- `get_prow`, `get_trow`
- `update_recs2plot`, `update_sample_checkbox`

**Visibility / Show Logic**
- `update_show`, `_is_rec_visible`, `_is_group_visible`

**Graph Coordination** (orchestration only; heavy drawing in UIplot)
- `graphRefresh`, `graphWipe`, `graphAxes`, `graphPreload`, `ongraphPreloadFinished`, `graphGroups`, `graphUpdate`
- Zoom helpers: `zoomAuto`, `zoomReset`, `_fit_output_zoom_to_groups`, `_xlim_from_artists`, `_ylim_from_artists`, drag zone recalc
- Related: `onSplitterMoved`

**Parse / Data Loading Orchestration**
- `parseData`, `onParseDataFinished`, `addData`, `setButtonParse`, `updateProgressBar`, `updateSubProgressBar`, `updateStatusBar`, `slotAddDfData`
- `reanalyze_recordings`, `duplicate_recording`, `create_recording`, `purgeRecordingData`
- `triggerAddData`, `triggerParse`, `triggerReanalyze`

**Statistical Tests / Statusbar Coordination** (large cluster)
- `update_test`, `apply_statistical_test_if_active`, `_apply_non_io_test`, `_print_statistical_test_table`
- Status: `set_statusbar`, `_on_statusbar_message_cleared`, `_set_statusbar_appearance`, `_get_statusbar_for_current_state`
- Formatters: `_format_io_regression_statusbar`, `_format_non_io_stat_test_statusbar`
- Checks: `_get_stat_test_warning`, `_check_ttest_applicability`, ... (all _check_*), `_is_io_mode`, `_effective_test_type`, `_should_show_stat_test_frame`
- `_apply_io_regression`
- `clear_formal_test_results`, `update_anova_label`
- `_get_shown_group_ids`, `_get_shown_testsets`
- `n_unit_changed` (and related radio updates)

**UI State / Radio / Checkbox Handlers** (many small)
- `experiment_type_changed`, `io_input_changed`, `io_output_changed`
- `test_type_changed`, `test_t_variant_changed`, `test_t_tails_changed`, `test_wilcox_*`, `editTest*Value`
- `filter_mode_changed`, `viewSettingsChanged`
- `n_unit_changed`, `update_experiment_type_radio_buttons`
- `checkBox_*_changed` (splitOddEven, timepoints, group_sample)
- Amp/slope edits: `update_amp_lineEdits`, `update_slope_lineEdits`, `editSlopeWidth`, `editAmpHalfwidth`, `edit*Range`, `editBinSize`, `editSort`, `editImportOptions`, `stimDetect`

**Triggers / Commands** (34; many already annotated as belonging elsewhere)
- Group/testset: `groupCheckboxChanged`, `triggerGroupRename`, `testsetCheckboxChanged`, `triggerTestSetRename`, `triggerNewGroup`, `triggerRemoveLast*`, `triggerClearGroups`, `triggerEditGroups`, `triggerAddToSet`, `trigger*TestSet`
- Sweep/norm/bin: `trigger_set_sweeps_even/odd`, `trigger_set_norm_range_all`, `trigger_set_bin_size_all`
- Export/copy already moved (per comments)
- Others: `triggerRenameRecording`, `triggerDelete`, `triggerAddSelectionToTestSet`, `triggerRefresh`, `triggerDarkmode`, `triggerShow*`, `triggerToggle*`, `triggerHideHierarchy`, `triggerSetGain`, `triggerSetSweepHz`, `triggerRenameProject`, `triggerNewProject`, `triggerOpenProject`, `triggerClearGroups` etc.

**Hierarchy / Recording Mgmt**
- `applyHierarchyToSelection`, `refreshHierarchyLineEdits`, `triggerHideHierarchy`
- `renameRecording`, `rename_files_by_rec_name`, `deleteSelectedRows`
- `set_rec_status`

**Zoom / View / Canvas**
- (Overlaps GraphCoord)
- `setTableStimVisibility`, `update_stim_buttons`

**Utilities / Debug / Misc**
- `usage`, `write_usage`, `talkback`, `setupTalkback`, `darkmode`, `resetCacheDicts`
- `checkFocus`, `find_widgets_with_top_left_coordinates`
- `deleteFolder`, `toggleHeatmap`, `turn_heatmap_off`
- `stimSelectionChanged`, `update_filter_settings`
- `_is_loading_active`

**Unassigned / Small** (few): `_is_loading_active`, `setupToolBar`, `update_stim_buttons`, `rename_files_by_rec_name`, etc.

Many cross-cutting calls exist (e.g. GroupMixin calls `self.graphRefresh()`, `self.apply_statistical_test_if_active()`, `self.turn_heatmap_off()`).

## Proposed Logical Mixins and Targets

Follow existing naming: `ui_foo.py` containing `FooMixin`. Prefer extending existing where it fits cleanly.

### 1. Move Small Helper Classes First (Prep)
**Target**: New `src/lib/ui_widgets.py` (or split `ui_dialogs.py` + `ui_models.py` + `ui_threads.py` if it grows).
- Move out of `ui.py` top: `Config`, `TableModel`, `FileTreeSelector*`, `MplCanvas`, `CustomCheckBox`, `ProgressBarManager`, `ParseDataThread`, `graphPreloadThread`, `Ui_Dialog`, `InputDialogPopup`, `ConfirmDialog`, `TableProjSub`, `Filetreesub`.
- Update imports and any references in `ui.py` + mixins.
- Benefit: Immediately cleans `ui.py` top matter (currently ~15 classes pollute the module).

### 2. Extend Existing Mixins
- **ProjectMixin** (`ui_project.py`):
  - Core/lifecycle setup: `setupFolders`, `build_dict_folders`, `connectUIstate`, `applyConfigStates`, parts of `__init__` wiring, `setSplitterSizes`.
  - Hierarchy: `applyHierarchyToSelection`, `refreshHierarchyLineEdits`, `triggerHideHierarchy`, related recording mgmt helpers.
  - (bootstrap/loadProject already here; keep consistency).

- **DataFrameMixin** (`ui_data_frames.py`): Already strong; move any remaining internal df helpers if found (most `get_df*` already moved).

- **GroupMixin** / **SweepOpsMixin**: Already well-scoped; move any stray group/testset trigger coordination if it fits cleanly (most triggers already documented as moved).

### 3. New Mixins (Recommended Logical Names)
- **TableMixin** (`src/lib/ui_table.py` → `TableMixin`):
  - `tableProjSelectionChanged`, `tableUpdate`, `_restore_table_selection`, `tableFormat`, `get_prow`, `get_trow`.
  - Table setup/format: `setupTableProj`, `setupTableStim`, `formatTableLayout`, `formatTableStimLayout`.
  - Related: `update_recs2plot` (partial), `setTableStimVisibility`.
  - Logical name: "Table" (focuses on the project table + stim table concerns).

- **SelectionMixin** (or **ViewStateMixin**) (`src/lib/ui_selection.py` → `SelectionMixin`):
  - Visibility core: `update_show`, `_is_rec_visible`, `_is_group_visible`.
  - Supporting: `update_sample_checkbox`, `setViewToolVisible`, parts of selection changed.
  - Logical name: Emphasizes the show/visibility contract (used by graph and table).

- **GraphCoordinatorMixin** (`src/lib/ui_graph.py` → `GraphCoordinatorMixin`):
  - All `graph*`: `graphRefresh`, `graphWipe`, `graphAxes`, `graphPreload*`, `graphGroups`, `graphUpdate`.
  - Zoom/view: `zoomAuto`, `zoomReset`, `_fit_output_zoom_to_groups`, zone recalc, `_xlim...` helpers.
  - Canvas: `setupCanvases`, `onSplitterMoved`.
  - Note: Delegates to `uiplot` (UIplot) and `InteractivePlotMixin`. Thin coordinator only.
  - Logical name: "GraphCoordinator" to distinguish from implementation in `ui_plot.py`.

- **ParseMixin** (`src/lib/ui_parse.py` → `ParseMixin`):
  - Orchestration: `parseData`, `onParseDataFinished`, `addData`, `setButtonParse`.
  - Progress/status: `updateProgressBar*`, `updateStatusBar`.
  - Entry points: `slotAddDfData`, `triggerAddData`, `triggerParse`.
  - Reanalysis: `reanalyze_recordings`, `duplicate_recording`, `create_recording`, `purgeRecordingData`.
  - Logical name: "Parse" (focus on the import/parse flow, separate from low-level parsing in `parse.py`).

- **StatTestMixin** (`src/lib/ui_stat_test.py` → `StatTestMixin`):
  - Core: `update_test`, `apply_statistical_test_if_active`, `_apply_non_io_test`, `_apply_io_regression`, `_print_statistical_test_table`.
  - Statusbar/test UI: All `_format_*`, `_get_statusbar_*`, `set_statusbar`, `_on_statusbar...`, `_set_statusbar_appearance`, `clear_formal_test_results`, `update_anova_label`.
  - Checks: `_get_stat_test_warning`, all `_check_*_applicability`, `_is_io_mode`, `_effective_test_type`, `_should_show_stat_test_frame`.
  - Helpers: `_get_shown_group_ids`, `_get_shown_testsets`.
  - Related radios: `n_unit_changed`, `test_*_changed` handlers, `editTest*Value`.
  - Logical name: "StatTest" (or "TestCoordinator") for the formal test + statusbar + n_unit coordination layer. (Keeps pure stats in `statistics.py` / `brainwash_stats/`.)

### 4. Distribution of Remaining Handlers / Triggers
- Many `trigger*` and `*_changed` are thin. Options:
  - Leave thin dispatchers in core `UIsub`.
  - Move feature-specific ones into the relevant new mixin (e.g. parse triggers → ParseMixin, stat radios → StatTestMixin, amp edits → perhaps a small `MeasurementUIMixin` or keep in core).
- `UIHandlers/Radios/Changes` and `AmpSlopeEdits` can be split by domain into the mixins above.
- `GroupTestsetControls` and `SweepEvenOddNormBin` mostly belong in existing Group/Sweep mixins (move stragglers).
- `Hierarchy/RecMgmt` → ProjectMixin or TableMixin.

### 5. Core UIsub After Extractions (What Stays in ui.py)
- `__init__` (high-level wiring only).
- Qt Designer setup and custom widget init.
- Signal connections (`connectUIstate` etc. — some may move).
- Top-level orchestration that crosses many concerns (e.g. final `graphRefresh` calls after selection).
- Debug/utilities that don't fit elsewhere (`usage`, `talkback`, `darkmode`).
- Any remaining tiny methods.
- The mixin wiring block (updated).
- Main guard.

Small helpers like `checkFocus`, `find_widgets...` can stay or go to a `DebugMixin`.

## Phased Implementation Plan

**Phase 0: Preparation (low risk)**
- Move all small helper classes to `ui_widgets.py` (or split).
- Update all imports/references.
- Clean up top-of-file comments and the "WIP" section.
- Add/improve docstrings in mixins listing "host requirements" (e.g. "Assumes self.dd_groups, self.update_show(), ...") to mitigate discoverability issues.
- Run full manual smoke test (load project, select recs, groups, stats, parse).

**Phase 1: Table + Selection (high impact on navigability)**
- Create `ui_table.py` + `TableMixin`.
- Create `ui_selection.py` + `SelectionMixin` (or combine if small).
- Move methods + any supporting private helpers.
- Update `UIsub` inheritance + injection.
- Update cross-references and comments.
- Verify table selection, visibility toggles, multi-select still work.

**Phase 2: Graph Coordination**
- Create `ui_graph.py` + `GraphCoordinatorMixin`.
- Move graph* + zoom helpers.
- Ensure delegation to `uiplot` and interactive remains clean.
- Test zoom, preload, group means display, n_unit changes.

**Phase 3: Parse / Import Flow**
- Create `ui_parse.py` + `ParseMixin`.
- Move parse orchestration + progress + reanalyze.
- Test drag-drop, parse button, progress, addData.

**Phase 4: Stat Test Coordination**
- Create `ui_stat_test.py` + `StatTestMixin`.
- Move the large stats cluster (biggest win for reducing god-object feel).
- Move related n_unit / radio handlers.
- Test all stat tests (t, ANOVA, etc.), statusbar, n_unit radio, formal markers.

**Phase 5: Polish + Remaining**
- Move remaining triggers/handlers into logical homes (or leave thin ones).
- Extend ProjectMixin with more lifecycle/setup.
- Update all comments (remove outdated "→ Mixin" annotations).
- Global search/replace for any stale references.
- Full regression: project load/save, all experiment types (time/PP/IO), groups, stats, export, darkmode, etc.
- Update `plan.md` or add cross-ref if needed.

**Optional Phase 6 (future)**: After this, evaluate if some thin coordinators can become composed objects (addressing mixin_problems.md drawbacks).

## Considerations & Risks
- **Cross-mixin calls**: Will continue to work via `self.` on the UIsub host. Use `hasattr` defensively only where already present; prefer direct calls after extraction.
- **Singleton injection**: Add new lines for each new mixin in the wiring section. Keep the comment block.
- **MRO / ordering**: Add new mixins in a logical position in the inheritance list (group data-related early?).
- **Testing**: Primarily manual + existing characterization tests. No new isolated mixin tests yet (known limitation).
- **Drawbacks mitigation** (from archived mixin_problems.md): 
  - Add "Host requirements" sections to each mixin docstring.
  - Keep files focused (one primary concern per mixin).
  - Update the "Mixin wiring" comment to list new files.
- **Size targets**: Each new mixin should be 300-800 LOC initially.
- **Naming consistency**: Use `ui_<concern>.py` and `<Concern>Mixin`. Avoid over-long names.
- **Rollback**: Extractions are additive (new files + inheritance changes); easy to revert a phase.
- Dependencies: Some methods (e.g. stats) depend on dataframes/groups; order phases accordingly or ensure all prereqs are available via host.

## Success Metrics
- `ui.py` < 3000 LOC with clear "core only" feel.
- New files follow existing mixin style (singleton injection comments, focused classes).
- No functional regressions in key flows (selection → graph/stats → parse).
- Improved comments make "where does X live?" answerable from `ui.py` or the mixin header.

## Next Steps (after plan acceptance)
1. Review / edit this plan.
2. Implement Phase 0 (widgets + prep).
3. Proceed phase-by-phase with smoke tests after each.
4. Commit with clear messages referencing this plan.
5. Update `AGENTS.md` or `plan.md` if this changes architectural guidelines.

This plan continues the successful incremental extraction style while targeting the largest remaining clusters identified in the current codebase.