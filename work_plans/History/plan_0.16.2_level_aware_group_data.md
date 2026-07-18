# Plan: 0.16.2 — Level-Aware Group Data for Graphs (Respect Subject/Slice n) + Global Unit DFs

> **Archived** (2026-07-18). Core implemented on `0.16.2` / `ui-refactor/phase0-3`. Follow-on plot artists: [plan_nunit_group_plotting.md](plan_nunit_group_plotting.md). Active n-unit troubleshooting: branch `0.16.3-nunit`.

**Status**: ✅ Implemented (core). Residual bugfix on `0.16.3-nunit`.

**Date**: 2026-07-12
**Branch goal**: Deliver the core refactor so that graphs (group means, SEMs, bars, points) respect the `n_unit` (Subject/Slice/Recording) choice the same way statistical tests do. Add global (project-wide) Subject/Slice aggregated dfs for new use cases (e.g., compare individual recording to its Subject mean). Prioritize robust + functional correctness. "Direct operation on group-independent globals inside group summaries" is Nice-To-Have / future.

**Key settled requirements from discussion** (see full thread for details):
- Three levels: `rec` (current), `slice` (avg of recs within (subject,slice)), `subject` (avg of slices within subject, or equiv. hierarchical collapse).
- Global (project-independent of groups) `df_output_subject` and `df_output_slice` **must** be calculated and persisted (full averages across *all* recs of the unit). Used for "rec vs its Subject mean" comparisons and similar. Built with SEM (modeled on group means).
- For **groups** (user-defined comparison sets via rec assignment): summaries at higher `n_unit` must be **contextual** (only use recs assigned to *that* group for the unit averages). This ensures graphs match stats (current `_aggregate_to_unit_level` behavior on group's recs) and handles split-rec cases (e.g., different recs of same subject in different groups).
- `n_unit` (from `uistate.buttonGroup_test_n`, default "subject") chooses the level for *both* stats **and** display/graphs.
- Lazy: based on selected `n_unit` (rec only; +slice; all for subject). Globals calculated "alongside groups (if present)".
- Persistence: file-based (via existing `df2file`/`persistOutput` patterns + parquet in cache/).
  - Globals: `Subject_<sanitized>` / `Subject_<s>_- _Slice_<sl>` (sanitized for FS safety).
  - Group-level at granularity: `group_<id>_<level>_mean.parquet` (or equiv.); optionally per-unit contextual series inside group using `group_<id>_- _Subject_...` style for intermediates (minimal for first cut).
- Invalidation: rec change/hierarchy edit on rec → destroy affected global unit files + higher-level group artifacts for groups containing the rec. Group membership change → purge that group's higher artifacts. Lazy recreate on demand.
- Different sweeps across members of a unit → NaN in averages (skipna for mean/sem).
- No migration (assume clean/no existing projects for 0.16.2 design).
- Display "acquire the correct df depending on settings": `n_unit` selects level; other settings (aspect, norm) select columns inside the df (unchanged).
- Graphs must now produce correct mean + between-unit SEM + (for PP) per-unit points when `n_unit` > recording.
- Stats: keep existing behavior (contextual via accessor + `_aggregate`) for robustness in v1 of this change. "Operate directly on the (global) parallel subject dfs" for group stats/summaries = future Nice-To-Have.
- PP/IO/timecourse/export/samples: timecourse group lines + SEM are primary; PP bars/points must aggregate by unit (not rec); samples stay rec-based (intentional "raw example"); export replays artists (will follow); IO handled similarly.
- Hierarchy (`subject`/`slice` in `df_project`) is already present + editable; just not used for display agg until now.
- "Vast majority whole-subject" noted, but we do **not** optimize via global reuse inside groups yet (robustness first; avoids partial-detection + custom flags).
- Weighting (unequal recs/slices per unit) and cross-group subject visualization = deferred.

**Non-goals for this change** (deferred):
- Full UI for rec-vs-subject-mean (toggle/overlay/comparison view).
- Direct stats consumption of globals inside groups.
- Changes to per-sweep/cluster paths beyond what's needed.
- Full per-unit-within-group caching strategy (longer discussion).
- Migration for old projects/caches.
- Altering sample inset or single-rec selection (stay rec-level).

## Background & Problem
- Stats (v0.16_n_stats + later) correctly use `n_unit` via per-rec obs + `_aggregate_to_unit_level` (in `brainwash_stats/data.py`) + hierarchy join in `get_group_testset_means`. n reported in statusbar/markers; avoids pseudoreplication per `statistical_protocol.md`.
- Graphs (group means via `get_dfgroupmean` → `plot_group_lines`/`addGroup`) are *always* rec-level concat + `groupby("sweep")` mean/sem across recs. No hierarchy, no n_unit awareness. SEMs, points (PP), etc. overstate n and use wrong independence.
- Result: visual data (lines, bands, bars, jitter points) does not match the n/values used for p-values/tests. "Real problem."
- Additional driver: users want global Subject/Slice means for direct comparisons (e.g., one rec vs full subject mean), independent of groups.
- Groups are arbitrary rec collections (recs assigned freely; same subject can contribute different recs to different groups for different comparisons, e.g., sex + intervention).

## High-Level Design
**Two parallel higher-level data worlds** (robust separation):
1. **Global (project-wide, group-independent) unit dfs**:
   - `df_output_subject` / `df_output_slice`: full averages for the unit (across *all* its recs in the project).
   - Slice = mean of its recs (with SEM across recs).
   - Subject = mean of its slices (two-stage; SEM across slices). This respects hierarchy and is common ephys convention (matches project protocol intent).
   - Queried by subject key (or subject+slice). Used for rec-to-unit comparisons (future UI) and any non-group subject views.
   - Always calculated when `n_unit` selects the level (or on explicit demand).

2. **Group summaries at chosen granularity** (contextual):
   - When `n_unit` > "recording" for a group: aggregate *only the recs in that group*.
   - Group recs by unit key (subject or (subject,slice) from `df_project`).
   - Within unit: avg rec series → contextual unit series for the group.
   - Across units: mean (group line) + SEM (between-unit variability).
   - This matches exactly what stats does for the group (via `get_group_testset_means` + aggregate on group's recs).
   - Persisted separately per level (so `n_unit` change picks different cache without invalidating others).
   - `n_unit="recording"` → existing rec-level behavior (no change).

**"Acquire the correct df"**:
- `n_unit` (global setting) drives level choice everywhere for groups + globals.
- Other toggles (aspect, normalize, etc.) select columns (unchanged).
- Callers (plot, group add, etc.) will query level-aware version based on current `uistate.buttonGroup_test_n`.

**Consistency**:
- Group graphs at higher level now use same n and aggregation as the tests for that group.
- Globals are orthogonal (for "full subject" views).

**Caching & Persistence** (extend existing patterns):
- Use `df2file` + parquet (in `cache/` or versioned cache dir).
- Globals: e.g. `Subject_S1_output.parquet`, `Subject_S1_-_Slice_1_output.parquet` (sanitized keys; key="output" or dedicated).
- Group level means: `group_{id}_subject_mean.parquet`, `group_{id}_slice_mean.parquet` (plus rec-level as before).
- Optional (minimal for v1): per-group per-unit contextual series under group-qualified names only if it simplifies stats or display (defer heavy strategy per discussion).
- In-memory: extend `dict_group_means` to be level-aware (keyed by (group_ID, level)) or separate dicts.
- `get_dfgroupmean` generalized (or new `get_group_mean_at_level(group_ID, level)`) dispatches:
  - level=="recording": current logic.
  - else: hierarchical within-group + final across-unit agg + SEM.
- Globals via new `get_global_unit_df(level, subject=..., slice=...)`.
- Build helpers: shared `_average_dfs_to_series(dfs_list, include_sem=True)` (concat + groupby sweep + agg mean/sem; NaN handling).
- For subject global: two-stage (per-slice series first, then avg those).

**n_unit & Refresh**:
- `n_unit_changed`: save, `update_test()`, **and** `graphRefresh()` (or targeted group re-plot) so visuals update.
- Hierarchy edits (`applyHierarchyToSelection`): already refresh + purge; extend to invalidate affected globals + groups.

**Plotting Updates** (make respect level):
- Timecourse: `plot_group_lines` unchanged (expects same df shape with _mean/_SEM).
- `addGroup` (time path): use level-aware df.
- PP path: instead of looping recs for PPR vals/points, group by unit (from `df_project` on group's recs). Bar = mean across units; points = one per unit (jitter; label with unit key). SEM across units.
- IO: analogous collection/agg by unit for group scatter/trend (if applicable).
- `graphGroups` / refresh paths / callers: fetch using current n_unit.
- `update_show`, labels, visibility: extend minimally for unit vs rec (e.g., points labeled by unit).
- Samples: unchanged (rec-based by design).
- Export: mostly replays `dict_group_labels` artists → will automatically use correct data once plotted.

**Stats**:
- No behavioral change (robust first).
- `get_group_testset_means` etc. continue returning per-rec + hierarchy; agg happens in `brainwash_stats/*`.
- Future (Nice-To-Have): accessor that can return pre-agg per-unit observations directly from globals or contextual series; callers operate on them with less `_aggregate`.

**Invalidation & Lifecycle**:
- Extend `group_cache_purge` (and sample) to handle levels (purge specific or all levels for affected groups).
- On rec output change / hierarchy change: compute affected units (globals) + groups containing the rec → purge.
- Globals purge: delete their specific Subject_ files.
- On `n_unit` change or group CRUD: appropriate purges + rebuilds.
- `dict_group_means` etc. updated to level-aware.

**Edge Cases**:
- Old projects (no subject/slice): globals fall back or warn (like stats); groups stay recording-level.
- Unequal data / NaNs / missing sweeps per unit: use pandas `mean(skipna=True)` + careful sem (count non-na).
- Stim-mode rows (sweep=NaN): decide later (focus sweep-mode for v1; or replicate current groupmean logic which is sweep-focused).
- Binning: respect per-rec bin state when fetching; unit avgs on binned data.
- Empty / single-unit groups: sensible empty or pass-through.
- PP discrete x, IO: adapt unit aggregation (fewer "points" = #units).
- Sanitization for filenames (e.g., `re.sub(r'[^A-Za-z0-9_.-]', '_', str(val))` + length limits).
- Threading / state: uistate is singleton; access via bound methods where needed.

**Multiple Approaches Considered & Trade-offs** (why this one):
- **A (chosen)**: Globals separate + contextual group summaries (always build from group's recs for higher levels). 
  - Pros: Robust/correct always (matches stats); no partial-detection complexity now; clear separation of concerns; easy to add "direct globals" later as opt-in.
  - Cons: Some re-averaging in full-subject common case (mitigable with internal short-circuit later without changing API).
- **B (tempting but deferred)**: For groups at high n_unit, default to globals + detect "full vs partial" + custom per-(group,unit) when needed.
  - Pros: "Operate directly" in common case; fewer avgs.
  - Cons: Detection + storage of "custom" flag + more invalidation surface + risk of mismatch if detection wrong. User explicitly chose robust first.
- **C (unify everything)**: Single set of unit dfs that are always global; groups just select which units to include and avg their globals.
  - Pros: Simplest data model.
  - Cons: Incorrect for partial splits (violates "groups are whatever user wishes to compare" using assigned recs); changes current stats semantics for groups with partial subjects. Rejected.
- Caching: Level-specific files (avoids invalidating recording cache when switching n_unit). In-memory level-aware.
- Stats integration: Keep accessor-based for now (works, tested). Future direct use can evolve the accessor without breaking display.

**Why this matches ephys convention + project protocol**: Hierarchical collapse (recs→slice→subject); subject as independent n; explicit support for full hierarchy reporting.

## Detailed Implementation Strategy (Phased, Minimal for Functional)

**Phase 0: Prep & Helpers (low risk)**
- Add sanitization helper (e.g., in `ui_data_frames.py` or `ui_project.py`): `_sanitize_for_filename(val)`.
- Add shared averaging helper: `_build_unit_series_from_rec_dfs(rec_dfs, include_sem=True) → df` (concat, groupby("sweep"), agg mean + sem if requested; handle columns like current groupmean; NaN policy).
- For two-stage subject: helper that first builds per-slice series, then averages those (for globals).
- Update `df_projectTemplate` / migration docs if needed (no schema change).
- Add level constants or enum (or just strings "recording"|"slice"|"subject").

**Phase 1: Global Unit DFs (new capability)**
- In `DataFrameMixin` (ui_data_frames.py):
  - `get_global_subject_df(subject)`: lookup all recs with that subject in `df_project`; fetch their `get_dfoutput`; use averaging helper → mean + SEM across recs (or slices? per #1: for subject, avg of slice means).
  - `get_global_slice_df(subject, slc)`: similar, only recs for exact (s,sl) → avg of recs + SEM.
  - Cache in new `dict_global_units` (keyed by (level, subject, slice?)) + persist (e.g., `Subject_{sanitized}_output.parquet` via `df2file(filename=..., key=...)` or direct name).
  - Lazy: build on first call (or when `n_unit` high).
- Invalidation: extend existing purge paths (hierarchy edit, rec change) to compute unit keys from affected rec + unlink global files + clear mem cache.
- Expose via UI if needed (e.g., for future compare); for now, internal + available for tests.
- Handle volley? Match current groupmean scope (amp/slope focus) or include if easy.
- Update `get_df_project` joins etc. if needed (already good).

**Phase 2: Level-Aware Group Summaries (core for graphs)**
- Generalize/extend in `ui_data_frames.py`:
  - `get_dfgroupmean(group_ID, level=None)`: if level is None or "recording": current.
    Else: 
      - Get recs for group.
      - df_p = get_df_project(); map rec → unit_key (subject or (s,sl) based on level).
      - Group recs by unit_key.
      - For each unit: fetch its rec dfs (only group's), `_build_unit_series...` (contextual mean; no sem needed here or yes?).
      - Concat the unit series dfs; `groupby("sweep").agg(mean + sem)` → final group mean at level (sem = between-unit).
      - Persist as `group_{group_ID}_{level}_mean.parquet` (or key).
      - Cache level-aware (e.g. `self.dict_group_means[(group_ID, level)]`).
  - `get_dfgroupmean_for_sweeps` extend similarly (filter after).
  - Update `get_group_testset_means`? No change for now (it already provides the per-rec foundation that stats aggregates; display will parallel it).
- New/updated purge: `group_cache_purge(..., levels=None)` — purge specific levels or all.
- For subject level in groups: the "per-unit" inside group is avg of its recs in *group* (contextual). Matches stats.

**Phase 3: Wire n_unit into Display + Refresh**
- In `ui_state_classes.py`: already has `buttonGroup_test_n`.
- `n_unit_changed` (ui.py): after save + update_test, call `graphRefresh(reeval_formal_test=False)` (or targeted "replot groups at new level").
- In `graphRefresh`, `graphGroups`, `graphUpdate` paths (ui.py + ui_interactive.py): 
  - `level = getattr(uistate, "buttonGroup_test_n", "recording")`
  - `df = self.get_dfgroupmean(gid, level=level)` (or new `get_group_mean_at_level`).
  - Pass to `uiplot.addGroup(...)`.
- Callers that unconditionally fetch (ui_groups.py assign/ungroup, etc.): make level-aware or use current n_unit.
- In `group_cache_purge` triggers: also consider current level or purge all levels for safety.
- `update_show` etc.: no major change (visibility is per group, not per level yet).

**Phase 4: Update Plotting Consumers (make visuals respect level)**
- `ui_plot.py`:
  - `addGroup`: for timecourse path → unchanged (df already correct).
  - PP path: 
    - Instead of `for rec_id in rec_IDs`: collect per-unit.
    - Use `df_p` or pre-mapped units for group's recs.
    - Compute per-unit PPR mean (from labels or data).
    - Bar = np.mean(per-unit vals); sem across units.
    - Jittered points: one per unit (not per rec); label with unit (e.g. subject or "S1-Sl1").
    - Update labels/storage to carry unit info where rec_ID was used.
  - IO path: similar unit-grouping for scatter collection if group-level.
  - `plot_group_lines`: unchanged.
  - `sample_overlay`: leave as-is (rec-based).
- Handle discrete x (PP), shifts, overlays.
- Update any PP-specific x-tick / legend logic if it hardcodes rec count.

**Phase 5: Callers, Refresh, & Integration Points**
- `ui.py`: `graphGroups`, places fetching group_mean → pass/use level. n_unit change → refresh. Hierarchy edit → extra invalidation.
- `ui_groups.py`: purges, assign/ungroup → level-aware if needed; `refresh_samples` unchanged.
- `ui_interactive.py`: output/mouseover updates that re-add groups.
- `graphRefresh` / `update_test` interactions: ensure level change or group change triggers correct visuals.
- Export (`export_data.py`, `export_image.py`): mostly follow artists or re-fetch via updated paths → should work; spot-check group mean usage.
- Statusbar / n_report: already uses n_unit; will now be backed by matching visuals.

**Phase 6: Globals + Non-Group Use + Polish**
- Ensure globals are built when n_unit=subject/slice (even with groups present).
- Add simple access (e.g., for a rec, `get_global_subject_df( its subject )`).
- SEM on globals: yes (across lower units).
- Update any direct `get_dfgroupmean` in export/elsewhere to be level-aware where it represents a "group summary".
- Docs/comments: reference this plan + statistical_protocol.
- Handle binning/filter/norm inheritance (unit avgs on already-processed per-rec outputs).

**Phase 7: Testing, Characterization, Cleanup**
- Extend `test_statistics_fixtures.py` / characterization if needed (already good for stats).
- New tests: unit builders (global + contextual group), NaN cases, partial groups, level switching, PP unit points, invalidation.
- Manual: load project with subjects/slices (some full, some partial splits); switch n_unit; verify group lines/SEMs/points use correct n and match test p-values/n; globals queryable.
- `graphRefresh` on n_unit change.
- Purge + reload.
- Run existing tests (`pytest ...test_statistics*`).
- Check PP, IO, timecourse, export.
- Cleanup: remove DEBUG prints if any; update AGENTS.md if patterns change.
- Since 0.16.2: version bump? cache dir considerations?

**Order of Work (incremental, testable)**:
1. Helpers + sanitization + global unit builders + persistence (unit test the builders).
2. Level-aware group mean (contextual) + cache/purge updates (test get_ returns correct agg).
3. n_unit wiring + basic graphRefresh on change (timecourse groups first).
4. Plot updates (timecourse → PP → IO).
5. Callers / refresh paths / invalidation.
6. Globals integration + non-group paths.
7. Polish, tests, export, edge cases.
8. (Future) optimize direct globals, full stats direct-use, UI compare.

**Files Likely Touched** (high-level; exact edits after exploration):
- `src/lib/ui_data_frames.py` (core new logic + extension of get_*group*).
- `src/lib/ui_plot.py` (PP/IO aggregation by unit; minor).
- `src/lib/ui.py` (n_unit change, graph paths, callers, invalidation hooks).
- `src/lib/ui_groups.py`, `ui_interactive.py` (purge, assign paths).
- `src/lib/ui_project.py` (if new persist helpers or sanitization).
- `src/lib/ui_state_classes.py` (minor).
- Tests: `test_statistics_*`, perhaps new or in ui tests.
- Possibly `export_*.py` (spot fixes).
- Work plans / docs (update references).

**Risks & Mitigations**:
- **Cache invalidation bugs**: Comprehensive purge on hierarchy/rec change; test reloads.
- **Sweep alignment / NaN / binning**: Reuse pandas groupby patterns from current; add unit tests.
- **PP/IO special cases**: They already deviate from df_groupmean; explicit unit agg will be needed.
- **Performance**: Globals + contextual = more avgs on large projects. Lazy + caching mitigate. "Vast majority full" helps if we add opt later.
- **Consistency during transition**: n_unit change always forces refresh; old caches coexist by level.
- **Stats/display drift**: By keeping stats unchanged and making display mirror the *same* contextual logic, drift is avoided.
- **Old code paths**: `get_dfgroupmean` backward compat (default recording).
- **No projects assumption**: Simplifies; real users will hit clean caches on upgrade.

**Verification / Acceptance**:
- Group means + SEMs + PP points at subject/slice n match the n and (contextual) values from tests.
- Globals exist and can be queried/used for full unit means.
- Switching n_unit updates graphs immediately.
- No breakage for recording n, old projects, IO/PP/time, export, samples.
- Tests pass + manual scenarios with splits + full subjects.
- `/check-work` equivalent (diffs, builds if needed, run tests).

**Open Decisions to Resolve During Impl (or pre-start)**:
- Exact column set / inclusion of volley/norm in unit globals (match groupmean?).
- Stim-mode row handling in unit avgs.
- Whether to always persist per-unit contextual series for groups (or just final means).
- Sanitization rules + max filename length.
- Whether `get_dfgroupmean` signature changes or new parallel API.
- Any impact on `get_ddgroup_sample` (probably none).
- Version / cache dir for 0.16.2.

This plan is concrete, phased, and prioritizes the "robust and functional" mandate while delivering the core fix (graphs now respect n:s for group data) + the globals capability. Implementation can start immediately on the 0.16.2 branch after acceptance.

Next steps after plan acceptance: branch, implement Phase 0-1, test, iterate per feedback.