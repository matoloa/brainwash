# Plan v0.16: Scientific Test (Statistical Comparisons with Test Sets)

## Mission Statement

Version 0.16 completes the "scientific methods" functionality so that users can:

1. Tag specific sweep ranges (e.g., sweeps 10-19) as reusable **Test Sets**.
2. Assign recordings to named **Groups**.
3. Configure a statistical test via the **Statistical test** panel (frameToolTest + frameToolTest_t).
4. Execute a comparison that respects the chosen test type/options **and** the tagged sweeps in the active Test Set(s).

The result is a properly configured statistical test (initially t-test with variant/tails/FDR support) comparing group means computed only over the user-tagged sweeps.

**User example flow**: Drag or type range 10-19 on the output graph → click "Add to Test Set" (in frameToolTag) → create Group(s) → choose "t-test", "unpaired", "two-sided", enable FDR if desired → invoke the statistical test (via dedicated menu action) → obtain p-value(s) computed on the mean of the tagged sweeps (or per-sweep within the tag) between the shown groups.

**Core Constraint** (carried from v0.15): NEVER alter `ui_designer.py` or run `puic`. All button wiring must be performed via the dynamic `self.pushButtons` dictionary in `UIstate.reset()` (consumed by `UIsub.connectUIstate()`) or by connecting to existing Qt signals (buttonGroups, stateChanged, etc.) that are already present in the compiled UI.

## What Exists Today (post "Basic wiring for tests")

### States of the test buttons are tracked in `src/lib/ui_state_classes.py`

- Direct attributes on `UIstate` (persisted in `cfg.pkl`):
  - `test_type` (default "t-test")
  - `test_t_variant` (default "unpaired")
  - `test_t_tails` (default "two-sided")
  - `test_fdr` (also mirrored in `checkBox["test_fdr"]`)
- The generic `checkBox` dict already contains `"test_fdr": False`.
- `viewTools` already contains entries for `"frameToolTest"` and `"frameToolTest_t"`.
- `pushButtons` already wires the tagging control:
  ```python
  "pushButton_add_to_set": "triggerAddToSet",
  ```

`get_state` / `set_state` / `load_cfg` / `save_cfg` were extended in the basic wiring commit to round-trip the new test\_\* fields.

### Tagging controls (select sweeps and tag them as Test Sets)

The elements to be tested are tagged by the user here:

- **Sweep selection** (frameToolSweeps):
  - `lineEdit_sweeps_range_from` / `lineEdit_sweeps_range_to`
  - `pushButton_sweeps_even` / `pushButton_sweeps_odd` (wired in `pushButtons`)
  - Click-and-drag on the output graph (`canvasOutput` → `InteractivePlotMixin.drag_released` etc.) updates `uistate.x_select["output"]` (set of 0-based int sweep indices).

- **Tagging action** (frameToolTag):
  - `pushButton_add_to_set` ("Add to Test Set")
  - Wired to `triggerAddToSet` → `add_to_data_set` (in `GroupMixin`) → `testset_new()`.
  - Creates an entry in `self.dd_testsets`:
    ```python
    {
      1: {
        "set_name": "set 1",
        "color": "...",
        "show": True,
        "sweeps": [10, 11, ..., 19],   # sorted list from current x_select["output"]
        "description": "..."
      },
      ...
    }
    ```
  - Persisted to `project/test_sets.pkl`.
  - Dynamic checkboxes appear in `verticalLayoutTestSet` (mirrors group pattern; `checkBox_testset_{ID}`).
  - "show" state controls visibility of gray `axvspan` backgrounds (via `visualize_test_sets` in `ui_plot.py`).

- Supporting menu actions (in `ui_menus.py`): "Add selection to test set", "Remove last test set", "Clear test sets".
- Test sets participate in `graphRefresh(dd_groups, dd_testset, ...)` and sample overlay logic.

### Incomplete wiring is in `src/lib/ui.py` and `src/lib/analysis_v3.py`

- **ui.py**:
  - `test_type_changed` is functional (saves state, shows/hides `frameToolTest_t`).
  - `test_t_variant_changed` and `test_t_tails_changed` are explicitly marked **"Placeholder wiring"** — they print and save but perform no further action and do not trigger any computation or validation.
  - `toggleHeatmap` (bound to the existing "Heatmap" menu + "H" shortcut) is the old full-range crude path; it completely ignores the new test configuration and test sets:
    - `uistate.test_type`
    - `uistate.test_t_variant`, `test_t_tails`, `test_fdr`
    - `self.dd_testsets` (and shown test sets)
  - It hardcodes a two-group, full-sweep, independent two-sample t-test using `get_dfgroupmean(key)` (all sweeps) + `analysis.ttest_df`.
  - Radio button apply logic in `applyConfigStates` and enable/disable logic in `uiFreeze`/`uiThaw` + `update_experiment_type_radio_buttons` were added, but there is no dedicated "run" path yet that consumes the full test configuration + test sets for the formal statistical test.
  - `checkBox_test_fdr` is observed in `viewSettingsChanged`, but nothing uses `uistate.test_fdr` for the scientific test.

- **analysis_v3.py**:
  - `ttest_df(d_group_ndf, norm, amp, slope)` is narrowly implemented with `ttest_ind_from_stats` (independent, two-sample, no tails control, always produces per-sweep p-values).
  - No support for one-sample, paired/related, one-sided tails, or FDR correction.
  - No entry point that accepts the UI's `test_*` configuration.

- **Data flow gap** (`ui_data_frames.py` + `ui_groups.py`):
  - `get_dfgroupmean(group_ID)` always aggregates over _all_ sweeps present in the group's recordings.
  - There is no first-class helper to obtain a group mean (or per-aspect scalars) restricted to an arbitrary list of sweeps from a Test Set.
  - Test sets are used for visualization and per-testset samples, but not yet for statistical comparison inputs.

- Result display for the _old_ full-range path lives in `uiplot.heatmap` (red scatter dots) + console print. The formal statistical test will use a parallel (but separate) display path for its markers. The v0.15 plan referenced a `verticalLayoutComparison` that does not exist in the compiled UI (and cannot be added without touching designer files).

## Detailed Requirements for v0.16

### 1. Test Configuration (already mostly stored)

The Statistical test panel provides:

- Top-level type: t-test | ANOVA | Wilcoxon | Friedman | Cluster perm. (radio group `buttonGroup_test`)
- t-test sub-options (visible only for t-test): variant (one-sample | paired | unpaired) and tails (two-sided | greater | less) in `frameToolTest_t`
- FDR checkbox (`checkBox_test_fdr`)

All changes must immediately persist via `uistate.save_cfg` and be restorable. Changing the type must show/hide the t sub-panel (already partially wired).

### 2. Using Test Sets as the "elements to be tested"

A Test Set (e.g. sweeps 10-19) defines _which sweeps_ participate in the comparison for each shown group.

When the test runs:

- Only shown test sets (`"show": True`) are considered.
- For each shown test set, the comparison input for a group is derived from only the sweeps listed in that set (filter the per-sweep output rows or the raw per-recording data before aggregation).
- If no test sets are shown, behavior may fall back to "all sweeps" (or require at least one — decide in implementation; document either way).
- Multiple shown test sets produce multiple comparisons (or a multi-condition view).

This matches the v0.15 intent: "use mean of sweeps 110-119 when comparing groups".

### 3. Groups remain the units of comparison

Shown groups (`dd_groups[g]["show"]`) supply the sets of recordings whose measurements are aggregated (within the test-set sweep filter) and then statistically compared.

For t-test a pragmatic starting constraint is exactly two shown groups (other tests such as ANOVA naturally support >2). The old `toggleHeatmap` implementation had this limitation; the new path is free to choose its rule (first two, require two, or error) and document it.

### 4. Execution trigger

The formal statistical test must use its own execution path, separate from Heatmap. Because `ui_designer.py` cannot be modified, the trigger will be a menu action (following the existing pattern used for "Add selection to test set" etc. in `ui_menus.py`).

Proposed trigger:

- Add a menu entry (e.g. under Data or a lightweight Test section): "Run statistical test" (or "Compare groups using Test Sets").
- This action calls a new dedicated function (e.g. `run_statistical_test()` in ui.py or a mixin) that:
  - Reads current `uistate.test_*` values + shown groups + shown test sets.
  - Builds inputs filtered to the shown test-set sweeps.
  - Dispatches by `test_type`.
  - For t-test: respects variant, tails, and FDR.
  - Produces visual feedback (restricted markers on the output graph) and a textual results table.

Results should also be invalidated and optionally re-computed when relevant state changes while results are visible (test config, shown test sets, shown groups). A lightweight `test_results_dirty` flag (or equivalent) plus hooks from `testsetCheckboxChanged`, group checkbox handlers, the `test_*_changed` handlers, and `graphRefresh` are appropriate. The old Heatmap path is **not** used for this.

### 5. Analysis layer

- Extend or wrap `ttest_df` (or introduce `run_statistical_test(...)`) in `analysis_v3.py` (or a small new helper) so it can be called with the UI configuration.
- Implement the three t variants using the appropriate scipy functions:
  - unpaired → `ttest_ind_from_stats` (or `ttest_ind`)
  - paired → `ttest_rel` (requires aligned observations; see pairing notes)
  - one-sample → `ttest_1samp` (compare to a reference value; the reference may default to 0 or be configurable later)
- Honor tails (alternative hypothesis).
- Apply FDR correction across the family of tests when `test_fdr` is true (per-sweep p-values, or across testsets, or both — keep pragmatic for v0.16).
- For amp vs. slope vs. norm: continue to respect `uistate.checkBox["EPSP_amp"]`, `["EPSP_slope"]`, `["norm_EPSP"]`.
- Non-t-test selections: emit a clear "not yet implemented for v0.16" message (and do not crash or corrupt state). The radios remain enabled for future work.

### 6. Pairing model (for "paired" variant)

Groups are independent collections of rec_IDs today. A pragmatic v0.16 approach:

- If exactly two groups are shown and they contain the same number of recordings, attempt to pair by sorted rec_ID order (or exact rec_ID overlap if the same IDs appear in both groups for a within-subject design).
- If pairing cannot be established, fall back to unpaired with a warning, or error and tell the user.
- Full "define pairs explicitly" UI is future work.

One-sample does not require pairing.

### 7. Result presentation (no designer changes)

- Visual: Reuse the existing red-dot marker machinery on ax1/ax2 (currently in `uiplot.heatmap`) but drive it from formal test results (via a separate path or wrapper). When test sets are active for the test, markers are restricted to (or labeled by) the sweeps belonging to shown test sets. Clear prior formal-test markers when configuration changes.
- Textual: Print a clear table (test set name, group names, N, statistic, p, corrected p if FDR). Use `print` + optionally the status bar.
- Management of formal test markers can reuse or lightly extend structures like `dict_heatmap`, but clearing and visibility must be independent of the Heatmap toggle.
- The old full-range behavior lives only in the separate Heatmap tool.

### 8. Refresh & invalidation

- Formal test results must be invalidated when:
  - Shown test sets change (add/remove/rename/toggle show, sweep contents)
  - Shown groups change
  - Test configuration changes (type/variant/tails/fdr, or amp/slope/norm checkboxes)
  - Underlying data or group membership changes
- Hooks similar to `refresh_samples()` (added in v0.15) are appropriate: call from `testsetCheckboxChanged`, `groupCheckboxChanged`, the `test_*_changed` handlers (when formal results visible), `graphRefresh`, etc.
- `uistate` can hold a lightweight `test_results_dirty` or the results themselves for re-display. The Heatmap dirty state remains separate.

### 9. Persistence

- Test configuration is already persisted in `cfg.pkl` via the recent wiring.
- Test sets and groups are already persisted.
- No new top-level project files are required for v0.16 (cached per-testset means can be added later if performance demands it; reuse existing group mean cache + filter for now).

### 10. Edge cases & UX

- 0 or 1 shown group → clear message.
- Empty test set sweeps → warn and skip.
- Mismatched sweep counts between groups for a given test set → handle gracefully (different N is usually ok for unpaired).
- Norm vs. raw, amp vs. slope selections still apply.
- Dark/light mode compatibility for any new markers/text.
- Status bar / usage logging for the new actions (e.g. "t-test unpaired two-sided on set 2 (sweeps 10-19) between group 1 and group 2").
- Frozen UI during heavy work (reuse existing freeze/thaw).

## Implementation Phases

**Phase 0 – Inventory & small cleanups (mostly done by basic wiring commit)**

- State storage, radio maps, basic handlers, checkbox wiring, hide button, apply/restore logic, enable/disable on freeze.
- Tagging flow (Test Sets) fully functional from v0.15.

**Phase 1 – Make test configuration drive execution (ui.py)**

- Flesh out `test_t_variant_changed` and `test_t_tails_changed` (they already save; ensure they mark results dirty and trigger re-computation of the formal test results when visible).
- Implement a dedicated runner (new function `run_statistical_test()` or similar, **not** `toggleHeatmap`). Invoked from a new menu action:
  - Read the full test config (`uistate.test_*` + FDR + amp/slope/norm).
  - Collect shown groups + shown test sets.
  - For each shown test set, build filtered group data using only that set's sweeps.
  - Call the analysis layer.
  - Display via restricted markers + printed table.
- Add a `test_results_dirty` (or equivalent) invalidation flag and a visibility flag for the formal results (distinct from `showHeatmap`).
- Wire calls from relevant checkbox changed handlers (`testsetCheckboxChanged`, group changes) and the test radio/FDR handlers (when formal results are visible).
- Decide and document fallback when no test sets are shown (e.g., require at least one shown test set, or fall back to all sweeps for the new path — the old Heatmap behavior is separate).

**Phase 2 – Data helpers for test-set-filtered means (ui_data_frames.py + ui_groups.py)**

- Add (or extend) a method such as `get_dfgroupmean_for_sweeps(group_ID, sweeps)` or `get_testset_group_data(testset_ID, group_IDs)` that:
  - Obtains per-recording output for the recs in the group.
  - Filters to the listed sweeps.
  - Aggregates to produce the same shape as today (per-sweep mean/SEM for amp/slope/norm) or a scalar summary per aspect if the scalar-per-testset model is chosen.
- Update `get_dfgroupmean` callers in the test path to go through the filtered version when a test set is active.
- Invalidate relevant caches when test sets or group membership change (similar to `group_cache_purge`).

Alternative (simpler start): after calling the existing `get_dfgroupmean`, do `df = df[df["sweep"].isin(testset_sweeps)].reset_index(drop=True)`. This works because the df has a "sweep" column with the original indices. Upgrade to a proper filtered path if semantics or SEM calculations require re-aggregation only over the selected sweeps.

**Phase 3 – Generalize analysis (analysis_v3.py)**

- Keep `ttest_df` for the current per-sweep shape or introduce a clearer `compute_group_comparison(groups, testset_sweeps, config)` entry point.
- Implement variant/tails logic:
  - Map UI strings to scipy calls and `alternative` parameters.
  - Handle one-sample reference value (start with 0.0 or a sensible default; make it explicit later if needed).
  - For paired: align observations (by index in the filtered df or by rec order) and use the paired test.
- Add FDR correction step (e.g. `from scipy.stats import false_discovery_rate` or a local Benjamini-Hochberg implementation) controlled by `test_fdr`.
- Return a richer result structure (p-values + which testset they belong to, raw statistic, N per side, etc.).
- Leave clean extension points for ANOVA / non-parametric tests.

**Phase 4 – Display & feedback (ui_plot.py + ui.py)**

- Add or extend result display (e.g. `show_test_results(results)`) that reuses the existing red-dot marker placement on ax1/ax2 but is driven by the formal test results, not by `showHeatmap`:
  - Markers appear only for sweeps belonging to the active (shown) test set(s).
  - Multiple test sets can be distinguished (different colors/alpha or labels).
  - Clearing of formal test markers is independent of `heatunmap`.
- Improve the printed table to include test set name, chosen configuration (type/variant/tails/FDR), and corrected p-values.
- Hook clearing on configuration changes and when the formal test results are dismissed.
- Optional: surface a one-line summary in the status bar.

**Phase 5 – Polish, wiring, and edge cases**

- Ensure all paths that should invalidate results do so (`testset_new/remove/rename`, group CRUD, relevant checkbox changes, data re-parse, etc.).
- Make the radio buttons and FDR checkbox trigger the right refreshes.
- Handle 0/1/N groups and 0/1/N test sets gracefully.
- Add usage logging for the new test execution.
- Do not alter the body or callers of the existing `toggleHeatmap` for the new formal test (it remains the separate full-range tool). If `ttest_df` signature changes for the generalized analysis, update only the new `run_statistical_test` path and any internal helpers.
- Manual test with real data: tag 10-19 and 170-179 or similar, two groups, run t-test with different options, verify p-values change appropriately and are restricted to the tagged range.
- Verify persistence across project close/reopen.
- Verify no changes were made to designer files.

**Phase 6 – Documentation & future hooks (optional for v0.16)**

- Update README or method.md if user-facing behavior changed.
- Leave clear comments/TODOs for ANOVA, Wilcoxon, etc.
- Note any desired future UI (e.g. a results table widget creatable in code without puic).

## Open Questions / Decisions Recorded in This Plan

- Exact semantics of "mean of sweeps 10-19": the plan allows starting with row-filter on the existing group-mean df (simple) and upgrading to a dedicated filtered aggregation if SEM or degrees-of-freedom calculations must be recomputed only over the selected sweeps.
- The formal test results are driven by a dedicated visibility flag / menu action. Heatmap remains an independent toggle and should never be required to view the statistical test output.
- FDR scope: across sweeps within one comparison, or also across multiple active test sets? Pragmatic first implementation is fine.
- One-sample reference value: default to 0 for v0.16.
- If >2 groups are shown for a t-test: either take the first two, require exactly two, or error. Document the chosen rule.

## Success Criteria

- User can reproduce the classic example: select sweeps 10-19 (via range controls or drag), "Add to Test Set", create two groups containing different recordings, select t-test / unpaired / two-sided (FDR optional), invoke "Run statistical test" (menu action).
- The computation uses only the tagged sweeps for the group aggregates passed to the test.
- The chosen variant and tails affect the scipy call and p-value.
- When FDR is enabled, corrected p-values appear in output.
- Results appear as red markers (restricted to the relevant sweep range) on the output graph + a readable printed table.
- Selecting a different test set, toggling its show state, or changing radio buttons while formal test results are visible produces updated results on next computation (or on re-invoking the menu action).
- Non-t-test selections produce a polite "not implemented" without side effects.
- All state round-trips in cfg.pkl; test sets continue to work exactly as in v0.15 for visualization and samples.
- No modifications to `ui_designer.py` or generated designer code.
- Code remains inside the existing mixin structure (`GroupMixin`, `DataFrameMixin`, `UIplot`, etc.) and follows the dynamic wiring pattern.

This plan provides a concrete, minimal-UI-change path to turn the partially wired "Statistical test" panel + existing Test Set tagging into a working scientific comparison tool for v0.16.

## Heatmap

Heatmap is a separate and crude tool to see where data differs. Contrary to the tests, it runs on the full range of all group samples, and shows the x-points where the groups are significantly different. It is a purely prospective tool; not intended as an independently meaningful analysis. It overlaps with the statistical test, but it's not integrated.
