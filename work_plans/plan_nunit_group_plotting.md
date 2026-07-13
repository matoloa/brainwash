# Plan: Upgrade Group Plotting for Per-n_unit Level Artists

## Context & Motivation

The app supports hierarchical n_unit levels for statistical analysis and group display: `recording`, `slice`, and `subject` (controlled by `buttonGroup_test_n` / `uistate.buttonGroup_test_n`).

- `get_dfgroupmean(group_ID, level=...)` already computes and caches group means (with `_mean` + `_SEM` columns) per level using `(group_ID, level)` cache keys and suffixed parquet files.
- `group_cache_purge(..., levels=...)` supports level-specific invalidation.
- However, the *plotting* side does not:
  - Artists (mean lines + `fill_between` SEM bands, plus PP/IO special cases) are created in `addGroup` / `plot_group_lines` and stored in `uistate.dict_group_labels` / `dict_group_show` **without level distinction**.
  - On n_unit switch, code currently does `unPlotGroup()` + `get_dfgroupmean(level=...)` + `addGroup(...)` (full destroy + recreate).
  - Visibility toggling in `update_show()` and legend logic in `graphRefresh()` also ignores level.
  - This leads to unnecessary work, risk of stale visuals ("graph or SEM-bars do not move"), and inconsistency with the "toggle hide/show rather than redraw" pattern used for rec lines, raw/norm, amp/slope, etc.

User observation: Lines on the output graph (ax1/ax2) are typically plotted once and toggled for visibility. Separate per-level plots (toggled on switch) + lazy df computation + level-aware staleness cleanup would be cleaner and more efficient.

## Goals

- Store **separate plot artists per level** for each group (mean line + SEM fill, and equivalent in PP/IO modes).
- Switching n_unit becomes a **cheap visibility toggle** (set_visible + legend update) rather than recreate.
- **Lazy computation**: Only build `df_groupmean` (and thus the plots) for levels that are actually required/used. E.g., only compute slice-level means if the user has ever selected "Slice"; never compute Subject if not needed.
- **Level-granular staleness**: When data/settings change (filter, normalization, hierarchy edits, etc.), destroy only the plots (and cached dfs) for the affected level(s) — in the *same places* we already invalidate dfs.
- Preserve (and improve) current behavior for the active level.
- Make n_unit switches fast and robust.
- Align plotting with the existing level-aware data layer.

## Proposed Architecture

### Data Layer (already mostly done)
- `get_dfgroupmean(group_ID, level)` uses `(group_ID, eff_level)` cache keys + level-suffixed parquet.
- `group_cache_purge(group_IDs, levels=...)` already handles this.
- Lazy: only builds on explicit request for a level.

### Plotting Layer (main upgrade)
- Artists created by `plot_group_lines` (and PP/IO paths in `addGroup`) will be **tagged with level**.
  - Store `"level": eff_level` in each entry in `dict_group_labels`.
  - Optionally use compound keys for the dict (e.g., `f"{base_label}_{level}"`) for easier debugging.
- `unPlotGroup(group_ID=None, level=None)` supports optional level filtering (only remove artists matching the level).
- `update_show` (group section) + `graphRefresh` legend/axis logic will filter by current `uistate.buttonGroup_test_n`.
- **Lazy creation**: Plots for a level are only created the first time that level becomes active (or is explicitly requested). Subsequent switches just toggle visibility.
- On n_unit change:
  - Ensure artists for the target level exist (call `get_dfgroupmean(level=...)` + `addGroup` only if missing for that group/level).
  - Toggle visibility so only the current level's artists are shown (others hidden).
  - No blanket `unPlotGroup()` of unrelated levels.

### Staleness & Invalidation
- Extend `unPlotGroup` and related helpers to be level-aware.
- When a change invalidates data for a specific level, call `group_cache_purge(..., levels=[affected])` *and* `unPlotGroup(..., level=...)` (or equivalent) in the same call sites that currently do blanket clears (e.g., `recalculate`, filter changes, hierarchy edits, group edits).
- Sites like `recalculate`, `group_cache_purge` callers, `ui_interactive.py` edit paths, `ui_project.py`, etc. will thread `levels` where appropriate.
- This mirrors exactly how dfs are destroyed when made stale.

### Visibility Model
- Multiple level-specific artist sets coexist in `dict_group_labels`.
- Only the set for the *current* n_unit level (plus normal selection/group visibility rules) is made visible.
- Consistent with existing toggles (raw/norm, overlays, etc.).

### Special Cases
- PP mode: bars + errorbars + points (and overlays) per level.
- IO mode: scatters + trendlines per level.
- Group samples / `dd_group_samples` / overlays: mostly stay tied to active level, but can be extended if needed.
- Legends, axis ticks (especially PP), and redraws must select the active level's artists.

## Step-by-Step Implementation Plan (Phased)

### Phase 0: Preparation (no behavior change)
- Add/ensure shared constants (`LEVEL_RECORDING`, etc.) and helpers if needed.
- Audit all call sites of `get_dfgroupmean`, `addGroup`, `unPlotGroup`, `group_cache_purge`, and `dict_group_*` access.
- Add verbose debug logging for level-specific plot creation/toggling (behind `config.verbose`).
- Update docstrings and comments.
- Smoke-test current n_unit switching + group display.

### Phase 1: Level-aware Artist Storage
- Modify `plot_group_lines(axid, group_ID, dict_group, df_groupmean, aspect=None, level=None)`:
  - Determine `eff_level`.
  - When storing in `dict_group_labels`, include `"level": eff_level`.
  - (Optional) suffix keys for the level.
- Update PP and IO branches inside `addGroup` to pass and record the level (they already inspect `buttonGroup_test_n` — make this explicit).
- Update `unPlotGroup(group_ID=None, level=None)`:
  - Filter keys_to_remove by level when provided.
  - Update removal logic for line/fill/patches.
- Add helper: `_make_level_key(base_label, level)` or similar.
- Update any direct iteration over `dict_group_labels` that assumes single-per-group (export, debug, etc.).

### Phase 2: Visibility Toggling & n_unit Switch
- Add/extend helper (e.g. in `UIplot` or `SelectionMixin`): `update_group_level_visibility(active_level=None)`.
  - For each group, get current level from `uistate.buttonGroup_test_n`.
  - Set `visible = (entry.get("level") == active_level) and _is_group_visible(...)`.
  - Apply `set_visible` to line/fill/etc.
  - Rebuild `dict_group_show`.
- Update `update_show` (group block) to incorporate level visibility.
- Update legend and axis logic in `graphRefresh` to only include the active level's artists.
- Refactor `n_unit_changed`:
  - After `update_test()` and state save:
    - For each group with recs: if no artists exist yet for the target level, compute df + call `addGroup(..., level=...)`.
    - Call the visibility toggler (instead of blanket unplot + re-add).
  - Remove (or guard) the aggressive per-switch cache clear + unPlot + re-add.
- Add explicit `canvas*.draw_idle()` where needed after toggles/lazy creation.

### Phase 3: Lazy Per-Level Computation
- In plotting callers (`graphGroups`, `n_unit_changed`, `ui_interactive.py`, `ui_groups.py` post-edit paths, etc.):
  - Only invoke `get_dfgroupmean(..., level=...)` (and thus `addGroup`) for the *current* level or a small set of "materialized" levels.
  - Introduce lightweight tracking (e.g. per-group set of "plotted_levels" or just rely on presence in `dict_group_labels`).
- Keep `get_dfgroupmean` lazy (it already is per `(group, level)` request).
- Optional: config flag to precompute all levels (default: false / on-demand).

### Phase 4: Level-Aware Staleness & Cleanup
- Make `unPlotGroup` and related removal logic fully level-aware (from Phase 1).
- Thread `levels` parameter through invalidation sites:
  - `recalculate` (in `ui_data_frames.py`).
  - Filter/normalization/hierarchy change paths.
  - `group_cache_purge` callers (already supports it).
  - Edit paths (`ui_interactive.py`, `ui_groups.py`, `ui_project.py`, etc.).
  - Any place that does blanket `uiplot.unPlotGroup(group_ID)`.
- When clearing a level's df (in `group_cache_purge` or directly), also ensure its plot artists are removed via `unPlotGroup(..., level=...)`.
- Update `dict_group_means` clearing to stay level-granular.
- Add convenience: `clear_group_level(group_ID, level)` that handles both df cache + plot removal.

### Phase 5: Special Modes, Redraws, Polish
- Ensure PP (bar + err + points + overlays) and IO paths fully respect and store level.
- Update any PP/IO-specific legend or tick logic.
- Ensure `V2mV` (if used on group data) is applied to the correct level's df.
- After visibility changes or lazy creation, ensure canvases are redrawn (`draw_idle` on output/mean/event as appropriate).
- Clean up temporary debug code and old "recreate on switch" paths once toggling is solid.
- Update documentation/comments around n_unit, groups, and plotting.

### Phase 6: Testing & Validation
- Manual: Switch n_unit with groups visible (time + PP + IO modes). Verify only the correct level's mean/SEM updates and others stay hidden. Check performance (switch should be near-instant after first materialization).
- Test lazy creation: First time selecting "subject" for a group, plots appear; previous levels remain.
- Test staleness: Change filter while in "slice" → only slice-level group plots/dfs are cleared; subject level unaffected.
- Test mixed selection + n_unit.
- Test group add/remove while at non-recording level.
- Regression: Existing rec-level behavior, visibility rules, legends, redraws.
- Add or expand smoke tests / characterization if appropriate.
- Verify no duplicate artists or key collisions.

## Files to Modify (Approximate Order)

1. `src/lib/ui_plot.py` — primary (artist storage, `plot_group_lines`, `addGroup` PP/IO paths, `unPlotGroup`)
2. `src/lib/ui_selection.py` — `update_show` group logic + visibility helper
3. `src/lib/ui_stat_test.py` — `n_unit_changed` (main switch logic)
4. `src/lib/ui_groups.py` — `group_cache_purge` call sites and helpers
5. `src/lib/ui_data_frames.py` — `recalculate`, other staleness paths, callers of `get_dfgroupmean`
6. `src/lib/ui_graph.py`, `src/lib/ui_interactive.py`, `src/lib/ui_project.py` — update callers of unplot/add and cache purges
7. `src/lib/ui.py` — any remaining state/wiring for active levels or n_unit
8. (Optional) docs or work plans updates

## Risks & Mitigations

- **Artist key management during transition**: Use an explicit `"level"` field in the dict entries (in addition to any key suffixing). Filter logic will rely on the field.
- **PP/IO special casing**: These were recent sources of bugs — handle and test explicitly.
- **Memory**: Up to 3× group artists per group is negligible compared to per-recording lines.
- **Legends & formatting**: `graphRefresh` and PP tick logic must select the active level's artists (already partially level-aware in places).
- **Backward compat**: External/debug code iterating the dicts will see the new `"level"` key (document it).
- **Performance of first switch**: Acceptable because higher-level computation is now lazy and only done on demand.
- **Migration of existing sessions/caches**: Old recording-only entries are harmless; new level-specific files will be created on first use of those levels. Consider a one-time cache clear note if desired.

## Benefits

- Matches the established "plot once, toggle visibility" pattern used throughout the output graph.
- Only pays for higher-level aggregation (Subject especially) when the user actually uses it.
- Fast, flicker-free n_unit switching.
- Precise, level-specific staleness (same invalidation sites as the df layer).
- Cleaner separation and easier future extensions (e.g., multi-level display).
- Reduces risk of the "plots do not move" class of bugs.

## Open Questions / Follow-ups

- Do we want to pre-materialize the last N levels, or stay purely on-demand?
- Should group samples (`dd_group_samples`) also become per-level?
- Any UI affordance to "clear specific level" for a group?
- Performance numbers after implementation (especially with many groups + high sweep counts).

## Next Steps

1. Review and refine this plan.
2. Start with Phase 0 + Phase 1 (storage + unPlotGroup) as they are low-risk.
3. Implement toggling in Phase 2 and refactor `n_unit_changed`.
4. Propagate level awareness through staleness paths.
5. Test incrementally (especially PP/IO and mixed n_unit usage).

This upgrade will make the n_unit feature feel solid and efficient.