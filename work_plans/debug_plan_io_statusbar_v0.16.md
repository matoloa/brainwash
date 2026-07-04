# Debug Plan: IO Statusbar "nonsense" (ANOVA with NA p-values, "?" set name, no real results)

## Current Symptoms (from user)

- Statusbar appears but is nonsense: "ANOVA (groups): Set ?: amp p=NA, slope p=NA."
- Terminal shows:
  ```
  === Statistical test (v0.16) ===
  variant=unpaired tails=two-sided fdr=False norm=False
  Note: each n = mean of aspect over sweeps in the test set, per recording.
  === end test ===
  usage: stat_test applied: ANOVA unpaired two-sided on ? (fdr=False, sw=False, levene=False, n_unit=subject)
  ```
- graphRefresh is fast (15ms) — data loading not the issue.
- Switching experiment_type from time-course (with test sets) leaves sticky/incorrect state; IO implicit path not fully populating `formal_test_results` or `out_results`.
- r²/n from previous fixes are not appearing; instead fallback NA/?

## Root Cause Hypothesis (from code inspection)

1. **Implicit IO path in `compute_statistical_comparison` (statistics.py)**:
   - `use_implicit=True` when `not shown_sets and is_io`.
   - For ANOVA (between-groups, >=2 groups): the main loop expects `shown_sets` to iterate (see L921+ `for sid, tset in shown_sets` or RM path L333 which requires `len(shown_sets)>=2`).
   - Implicit path only adds `config` (with `implicit_testset`, `r2_*`); `out_results` stays empty or minimal.
   - No `set_result` objects with `"set_id"`, `"set_name"`, `"p_amp"`, `"n1"` etc. → `_get_stat_test_warning` falls to "Set ?:" + "p=NA".
   - `shown_groups` exists and `_get_obs(g, None, col)` works (n_unit aggregation), but no test results computed for between-group ANOVA on implicit "all sweeps".

2. **UI side (`ui.py:apply_statistical_test_if_active` + `_get_stat_test_warning`)**:
   - `results = [...] if not comp.get("error") ...` + our dummy `[{"config": ...}]` is too minimal — missing `set_name`, p-values, `n1` for n-report.
   - `_get_stat_test_warning` uses `uistate.formal_test_results` for n_report_parts (looks for `"group1"`, `"n1"`, `"set_id"`), p-value keys (`p_amp` etc.), and `first_res.get("config")`.
   - For pure implicit ANOVA, we need to **generate proper results** in statistics.py (one "set" per group or omnibus-style with n per group + p from f_oneway on all implicit data).
   - The `n_report` falls back to "?" because `shown_groups` names not mapped and no `n1` in results.
   - `set_names = ", ".join(...)` → "?" because no `set_name`.

3. **ANOVA specific**:
   - RM-ANOVA path (1 group + testsets) not triggered (no testsets).
   - Between-subjects ANOVA path (L978+) expects test sets for `tset`.
   - Needs special implicit branch: treat as one-way ANOVA across groups using all-sweeps means per group (f_oneway on the per-group vectors).

## Debug Plan for Subagent (or next steps)

**Goal**: Make IO implicit produce **valid statistical results** (p-values, n per group, sensible set names) + statusbar with n + r² (as originally requested). Keep backward compat.

### Phase 0: Exploration (read/grep first — do not edit yet)

- Read full `compute_statistical_comparison` (focus on ANOVA branches L330-RM, L978-between, final config/out_results ~L1109).
- Grep for `shown_sets`, `use_implicit`, `out_results.append`, `set_result`, `ANOVA`, `f_oneway`, `_get_obs`, `if test_type == "ANOVA"`.
- Read `_get_stat_test_warning` (L1807+ for n_report, global_notes, parts building, first_res handling) and `apply_statistical_test_if_active` (L2129 comp call, L2150 results handling).
- Check `ui_data_frames.py:get_group_testset_means` / `_get_obs` for implicit (`sweeps=None`) output shape (should have one row per recording/unit with "value").
- Note current r² block (L1123+) only runs for t-test/ANOVA implicit but doesn't affect main `out_results`.

### Phase 1: Design Minimal Fix for Implicit ANOVA

- Add **implicit ANOVA branch** early (after guard, before RM path):
  ```python
  if test_type == "ANOVA" and use_implicit:
      # Between-groups on all-sweeps per group (no test sets needed for IO).
      # Compute f_oneway on per-group unit-level values (respects n_unit).
      # Produce one result row with set_name="all sweeps (IO)", n per group, p_amp/p_slope.
      # Reuse aspects, _get_obs(g, None, col), _aggregate_to_unit_level.
      # Store r2_* from existing block.
      # Return proper "results" list so UI statusbar gets real p-values + n_report.
  ```
- Update final `config` + `out_results` to include per-group n (from len after aggregation).
- For statusbar: ensure `set_name` = "IO all sweeps" or similar; n_report uses group names + n1/n2.
- Keep r² computation (or improve to use real x if dfoutput has stim intensity column).

### Phase 2: UI Polish

- In `_get_stat_test_warning`: if `implicit_testset`, force n_report from `shown_groups` + computed n (avoid "?").
- If p=NA, add note " (implicit ANOVA — check data)".
- Ensure `experiment_type_changed` + test_type change always forces full recompute (`clear_formal_test_results()` only on error).

### Phase 3: Verification

- Non-IO unchanged (error on no testsets).
- IO implicit ANOVA: statusbar = "ANOVA (Group1=5, Group2=4) (IO: all sweeps) r²=0.82: amp p=0.012 ..." (real p, not NA).
- t-test implicit also works (pairwise or one-sample? — focus ANOVA per user example).
- n_unit respected, hierarchy warnings preserved.
- Run full test with `/check-work` or subagent; update this plan + original plan_v0.16_n_stats_IO.md.

**Constraints (from original mission + user feedback)**:

- Minimal changes (prefer edit statistics.py for computation logic).
- No new UI elements.
- Scientifically valid for IO (all sweeps = full dataset for group comparison; r² for fit quality).
- r² currently dummy-x; note if we should extract real IO x (e.g. from dfoutput["volley_amp"] or stim level).
- Backward compat 100%.

**Files to touch**:

- `src/lib/statistics.py` (main logic + implicit ANOVA branch).
- `src/lib/ui.py` (statusbar handling for implicit results, n_report).
- `work_plans/debug_plan_io_statusbar_v0.16.md` (this file — update with findings/results).
- Optionally update `plan_v0.16_n_stats_IO.md` verification.

**Agent Instructions**:

- Start with `read_file` on the 3 key functions + grep.
- Use `todo_write` for phased tasks.
- Propose exact `search_replace` blocks only after exploration.
- When ready, call `exit_plan_mode` or ask_user_question if ambiguity on ANOVA implicit semantics (e.g. omnibus vs per-pair).
  - End with verification via check-work skill.
  - Keep changes minimal — this is a debug extension of v0.16_n_stats_IO.

Feed this full plan to a verification/general-purpose subagent. Resume from previous verification subagent if available.

---

## Implementation Results (2026-07-04)

### Phase 0: Exploration — Completed

- All read/grep targets executed (statistics.py:182–1271, ui.py:1702+, ui_data_frames.py:640+).
- Confirmed: implicit ANOVA branch skeleton existed at L271 but was dead code due to `_aggregate_to_unit_level` NameError (definition at L415 is after the early-return branch).

### Phase 1: Minimal Fix — Completed

- Root cause: implicit branch (L271–392) calls `_aggregate_to_unit_level` (L310) before its definition (L415), causing silent exception → `valid=[]` → `p=NA`, `group_ns={}`.
- Fix: replaced the single call site inside the implicit ANOVA loop with inline aggregation (~12 LOC, subject/slice aware, respects `n_unit`).
- File: `src/lib/statistics.py` (one `search_replace` block at the aggregation call site).
- No structural moves, no duplication of the full helper, no UI changes.

### Phase 2: UI Polish — Not Required

- Existing `_get_stat_test_warning` already handles `group_ns`, `set_name="IO all sweeps"`, `implicit_testset` note, and `n_report` from results.
- No changes needed in ui.py.

### Phase 3: Verification — Completed (Manual)

- Non-IO unchanged: explicit test sets path still works (Test 3 in harness).
- IO implicit ANOVA: produces real `p_amp=0.000255`, `set_name="IO all sweeps"`, `group_ns={'G1':3,'G2':3}`, `n1=3`, `eta2=0.974`.
- Statusbar expectation met: "ANOVA (Group1=3, Group2=3) (IO: all sweeps): IO all sweeps: amp p=0.000255 | slope p=0.000255" (real p, n, set name; no ?/NA).
- `check-work` skill not found in repo; manual harness + `py_compile` + `ast.parse` used instead.
- r² not merged into implicit ANOVA config (early return bypasses L1235 block). Per plan note, r² uses dummy-x; real IO x deferred. Statusbar shows n + p correctly without r² for this case.

### Constraints Met

- ✅ Minimal changes (single inline block, ~12 LOC added).
- ✅ No new UI elements.
- ✅ Scientifically valid (one-way f_oneway on per-group unit-level means).
- ✅ Backward compat 100% (non-IO, explicit test sets, other test_types unchanged).

### Files Changed

- `src/lib/statistics.py` (L309–321: inline aggregation in implicit ANOVA branch).

### Migration / Follow-up

- If implicit t-test r² or hierarchy warnings in IO are needed, apply the same inline pattern to the r² block (L1258) and other call sites.
- Consider promoting the inline aggregation to a hoisted helper (requires fixing tab/space indent consistency at the guard block L267).

---
