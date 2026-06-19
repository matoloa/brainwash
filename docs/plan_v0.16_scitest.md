# Plan v0.16: Scientific Test (Statistical Comparisons with Test Sets)

## Mission Statement

Version 0.16 completes the "scientific methods" functionality so that users can:

1. Tag specific sweep ranges (e.g., sweeps 10-19) as reusable **Test Sets**.
2. Assign recordings to named **Groups**.
3. Configure a statistical test via the **Statistical test** panel (frameToolTest + frameToolTest_t).
4. Have the comparison applied automatically (when a non-None test type is selected) and kept up to date as groups and test sets change, using the chosen test type/options **and** the tagged sweeps in the active Test Set(s).

The result is a properly configured statistical test (initially t-test with variant/tails/FDR support) comparing group means computed only over the user-tagged sweeps.

**User example flow**: Drag or type range 10-19 on the output graph → click "Add to Test Set" (in frameToolTag) → create Group(s) → choose "t-test", "unpaired", "two-sided", enable FDR if desired. As soon as a non-None test type is selected, the comparison is applied automatically using the shown groups and active test sets. Results update live whenever the composition of the groups (or shown test sets, or test config) changes.

**Core Constraint** (carried from v0.15): NEVER alter `ui_designer.py` or run `puic`. All button wiring must be performed via the dynamic `self.pushButtons` dictionary in `UIstate.reset()` (consumed by `UIsub.connectUIstate()`) or by connecting to existing Qt signals (buttonGroups, stateChanged, etc.) that are already present in the compiled UI.

## What Exists Today (post "Basic wiring for tests")

### States of the test buttons are tracked in `src/lib/ui_state_classes.py`

- Direct attributes on `UIstate` (persisted in `cfg.pkl`):
  - `test_type` (default "None")
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
  - Radio button apply logic in `applyConfigStates` and enable/disable logic in `uiFreeze`/`uiThaw` + `update_experiment_type_radio_buttons` were added, but selecting a test type (other than "None") currently does nothing beyond showing the sub-panel. There is no automatic computation or display that reacts to `test_type`, group composition, or test sets.
  - `checkBox_test_fdr` is observed in `viewSettingsChanged`, but nothing uses `uistate.test_fdr` for the scientific test.

- **analysis_v3.py**:
  - `ttest_df(d_group_ndf, norm, amp, slope)` is narrowly implemented with `ttest_ind_from_stats` (independent, two-sample, no tails control, always produces per-sweep p-values).
  - No support for one-sample, paired/related, one-sided tails, or FDR correction.
  - No entry point that accepts the UI's `test_*` configuration.

- **Data flow gap** (`ui_data_frames.py` + `ui_groups.py`):
  - `get_dfgroupmean(group_ID)` always aggregates over _all_ sweeps present in the group's recordings.
  - There is no first-class helper to obtain a group mean (or per-aspect scalars) restricted to an arbitrary list of sweeps from a Test Set.
  - Test sets are used for visualization and per-testset samples, but not yet for statistical comparison inputs.

- Result display for the _old_ full-range path lives in `uiplot.heatmap` (red scatter dots) + console print. The formal statistical test (when a non-None type is selected) will drive its own markers via a parallel path. Markers must appear and update automatically. The v0.15 plan referenced a `verticalLayoutComparison` that does not exist in the compiled UI (and cannot be added without touching designer files).

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

Shown groups (`dd_groups[g]["show"]`) determine which groups participate, but the actual recordings that belong to each group (the group _components_ / membership) are what get filtered by test sets and compared. Changes to either participation or membership must trigger re-application of an active test.

For t-test a pragmatic starting constraint is exactly two shown groups (other tests such as ANOVA naturally support >2). The old `toggleHeatmap` implementation had this limitation; the new path is free to choose its rule (first two, require two, or error) and document it.

### 4. Automatic application (no explicit "run" command)

There is no "Run test" action, menu item, or separate toggle for the formal statistical test. Selecting a test type other than "None" in the Statistical test panel **applies** the test immediately. The test remains applied and is **re-applied automatically** every time the components of the groups change.

"Components of the groups change" means any mutation to the actual membership or participation of recordings in groups, including:

- Adding or removing recordings from groups
- Creating, deleting, or renaming groups that affect membership
- Toggling a group's show state (which groups are included in the comparison)
- Changes to shown test sets (since they filter the data used for each group)
- Changes to the test configuration itself (type/variant/tails/FDR/aspect)

Implementation approach:

- In `test_type_changed`, `test_t_variant_changed`, `test_t_tails_changed`, and the FDR checkbox handler: if the selected test is not "None", call an applicator that computes results using the current shown groups + shown test sets (filtered to test-set sweeps) and displays them.
- When `test_type` is changed to "None", clear formal test results/markers.
- Find and hook into the actual group mutation paths (e.g. after adding/removing recs to groups, after testset modifications) so that a currently-selected test is re-applied.
- Leverage or extend existing refresh points (`groupCheckboxChanged`, testset checkbox handlers, `graphRefresh`, data reload paths) to trigger re-application when a test is active.
- A simple dirty flag (`test_results_dirty`) or direct call to an `apply_statistical_test_if_active()` helper can be used. The goal is automatic, live updating without any user "run" step.

The Heatmap ("H") path is completely independent and untouched by this logic. Formal test results use their own display path.

### 5. Analysis layer

- Extend or wrap `ttest_df` (or introduce a clear `compute_statistical_comparison(...)` or `apply_test(...)` entry point) in `analysis_v3.py` (or a small new helper) so it can be called with the UI configuration.
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

- Visual: Reuse the existing red-dot marker machinery on ax1/ax2 (currently in `uiplot.heatmap`) but drive it from formal test results (via a separate path or wrapper). Markers appear automatically when a non-None test is selected. When test sets are active for the test, markers are restricted to (or labeled by) the sweeps belonging to shown test sets. Markers are cleared when the test is set to None or when configuration makes results invalid.
- Textual: Print a clear table (test set name, group names, N, statistic, p, corrected p if FDR). Use `print` + optionally the status bar.
- Management of formal test markers can reuse or lightly extend structures like `dict_heatmap`, but clearing and visibility must be independent of the Heatmap toggle.
- The old full-range behavior lives only in the separate Heatmap tool.

### 8. Refresh & invalidation (automatic re-application)

Because the test is applied as soon as a non-None type is selected and must re-apply automatically, results are invalidated and recomputed on:

- Any change to the _components_ of groups (recordings added to or removed from groups, group create/delete/rename that affects membership)
- Toggling shown groups or shown test sets
- Test set add/remove/rename or sweep content changes
- Test configuration changes (type, variant, tails, FDR, aspects)
- Underlying data changes that affect the filtered group data

Key hooks:

- After the actual group membership mutation functions (the points that modify `dd_groups[...]["rec_IDs"]` etc.).
- `groupCheckboxChanged`, testset checkbox handlers, `testset_new`/`testset_remove`, etc.
- `test_*_changed` handlers and FDR checkbox (when a test is active).
- `graphRefresh` and data reload paths as a safety net.

Use a dirty flag or direct applicator call. When `test_type == "None"`, results are cleared rather than updated. Heatmap state is independent.

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

**Phase 1 – Make test configuration drive automatic application (ui.py)**

- Flesh out `test_t_variant_changed`, `test_t_tails_changed`, and the FDR handler so they save state and, when `test_type != "None"`, immediately trigger computation + display of results.
- Implement the core applicator (e.g. `apply_statistical_test()` or `update_test_results_if_active()`). It is **not** invoked from any menu; it is called:
  - From the test config change handlers (when a real test is selected).
  - From group membership mutation points (after recs are added/removed from groups).
  - From test set change paths (add/remove/rename/toggle show).
  - From `groupCheckboxChanged` and equivalent testset handlers when a test is active.
  - Opportunistically from `graphRefresh` / data update paths if a test is currently selected.
- When `test_type` becomes "None", clear any active formal test markers/results.
- Introduce a simple dirty / active-test check so that relevant changes automatically cause re-application without user intervention.
- Decide/document behavior when no shown test sets (e.g. use all sweeps for the groups, or require at least one — the Heatmap full-range tool is unaffected either way).

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

- Add or extend result display (e.g. `show_test_results(results)`) that reuses the existing red-dot marker placement on ax1/ax2 but is driven by the formal test results independently of `showHeatmap`:
  - Markers appear only for sweeps belonging to the active (shown) test set(s).
  - Multiple test sets can be distinguished (different colors/alpha or labels).
  - Markers/results are shown automatically whenever a non-None test is selected; they are cleared when test type is set to "None".
  - Clearing of formal test markers is independent of `heatunmap`.
- Improve the printed table to include test set name, chosen configuration (type/variant/tails/FDR), and corrected p-values.
- Ensure display updates (or is refreshed) as part of the automatic re-application on group component changes.

**Phase 5 – Polish, wiring, and edge cases**

- Ensure that group membership mutations, testset changes, shown-group toggles, and test config changes all cause automatic re-application when a test is active.
- Make the radio buttons and FDR checkbox directly trigger (or dirty + refresh) the test results.
- Handle 0/1/N groups and 0/1/N test sets gracefully (clear or message appropriately).
- Add usage logging when a test is applied or re-applied.
- Do not alter the body or callers of the existing `toggleHeatmap` (it remains the separate full-range tool).
- Manual test with real data: tag 10-19 and 170-179 or similar, create two groups, select t-test / unpaired / two-sided (FDR optional). Verify that results appear immediately, use only the tagged sweeps, and automatically update when you add/remove recordings from the groups.
- Verify persistence across project close/reopen.
- Verify no changes were made to designer files.

**Phase 6 – Documentation & future hooks (optional for v0.16)**

- Update README or method.md if user-facing behavior changed.
- Leave clear comments/TODOs for ANOVA, Wilcoxon, etc.
- Note any desired future UI (e.g. a results table widget creatable in code without puic).

## Open Questions / Decisions Recorded in This Plan

- Exact semantics of "mean of sweeps 10-19": the plan allows starting with row-filter on the existing group-mean df (simple) and upgrading to a dedicated filtered aggregation if SEM or degrees-of-freedom calculations must be recomputed only over the selected sweeps.
- Because application is automatic on test selection + group component changes, we do not need (and should not have) a separate visibility toggle or menu action for the formal test. Results are shown while a non-None test is selected and cleared when set to None. Heatmap remains completely independent.
- FDR scope: across sweeps within one comparison, or also across multiple active test sets? Pragmatic first implementation is fine.
- One-sample reference value: default to 0 for v0.16.
- If >2 groups are shown for a t-test: either take the first two, require exactly two, or error. Document the chosen rule.

## Success Criteria

- User can reproduce the classic example: select sweeps 10-19 (via range controls or drag), "Add to Test Set", create two groups containing different recordings, select t-test / unpaired / two-sided (FDR optional). Results appear automatically (no "run" step).
- The computation uses only the tagged sweeps for the group aggregates passed to the test.
- The chosen variant and tails affect the scipy call and p-value.
- When FDR is enabled, corrected p-values appear in output.
- Results appear as red markers (restricted to the relevant sweep range) on the output graph + a readable printed table.
- Adding or removing recordings from a group, toggling group or test-set show states, or changing test options causes the results to be automatically re-computed and updated.
- Non-t-test selections produce a polite "not implemented" without side effects.
- All state round-trips in cfg.pkl; test sets continue to work exactly as in v0.15 for visualization and samples.
- No modifications to `ui_designer.py` or generated designer code.
- Code remains inside the existing mixin structure (`GroupMixin`, `DataFrameMixin`, `UIplot`, etc.) and follows the dynamic wiring pattern.

This plan provides a concrete, minimal-UI-change path to turn the partially wired "Statistical test" panel + existing Test Set tagging into a working scientific comparison tool for v0.16, with automatic application on test selection and live re-application on group component changes.

## Heatmap

Heatmap is a separate and crude tool to see where data differs. Contrary to the tests, it runs on the full range of all group samples, and shows the x-points where the groups are significantly different. It is a purely prospective tool; not intended as an independently meaningful analysis. It overlaps with the statistical test, but it's not integrated.
