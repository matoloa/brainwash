# Plan v0.16_n_stats_IO: Statistical tests without requiring test sets (IO-aware, backward-compatible, agent-efficient v2)

## Mission Statement

In IO (Input-Output) experiments and other common analysis workflows, users frequently want to run statistical comparisons **without defining explicit test sets**. Currently, `compute_statistical_comparison` and all its call sites require at least one shown test set (`shown_sets` must be non-empty). For IO mode (and other non-time-series analyses), this is an artificial constraint. The fix must:

1. Make test sets **optional** when `experiment_type == "io"`.
2. When no test sets are shown, fall back to **all sweeps** for each recording in the group (via accessor).
3. Preserve **100% backward compatibility** for time/sweep/stim/PP experiments (test set required).
4. Respect the `n_unit` hierarchy (v0.16_n_stats: subject/slice/recording).
5. Keep all existing error paths, statusbar messaging, persistence, and UI intact.
6. **Improve agentic efficiency**: Centralize logic (single guard + helper), minimize duplication/edits, provide exact code snippets for `search_replace`, integrate verification subagent.

This plan builds directly on v0.16_n_stats (`_aggregate_to_unit_level`, hierarchy) and v0.14_IO (`experiment_type`).

---

## What Exists Today (updated v0.17)

### `compute_statistical_comparison` (statistics.py:~182–1265)
**v0.17_io_statusbar_fix**: Added dedicated early implicit-ANOVA branch (L271+) for IO+no-testsets+>=2 groups. Uses f_oneway on all-sweeps aggregated data per group (_get_obs(g, None, col) + _aggregate_to_unit_level). Produces full set_result ("IO all sweeps", p-values, n1, group_ns, eta2) instead of config-only. Integrates r². Fixes statusbar nonsense (no more "Set ?:" / p=NA / n=?). UI n_report updated to consume group_ns. All other paths (RM, t-test implicit, non-IO) unchanged.

- `shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items() if info.get("show", False) and info.get("sweeps")]`.
- If `not shown_sets`: returns `{"error": "no shown test sets", "results": []}` (multiple duplicate sites: early return ~L253, Cluster ~L504, Wilcoxon ~L688).
- All branches iterate `shown_sets` calling `get_group_testset_means_fn(g, sweeps, aspect=...)` (10+ sites).
- `n_unit` param (default `"subject"`); `_aggregate_to_unit_level` for unit-level scalars.
- Cluster forces `n_unit="recording"`.

### `get_group_testset_means` (ui_data_frames.py:~631)

- `(group_ID, sweeps, aspect="EPSP_amp", per_sweep=False)`.
- Guard: `if not group_ID or not sweeps: return empty DF`.
- Uses `get_group_obs_for_sweeps` (filters with `.isin(sweeps)`) → mean over provided sweeps.
- Joins `subject`/`slice` from `df_project` (v0.16_n_stats).

### Experiment type and IO mode (ui.py)

- `uistate.experiment_type` ∈ `{"time", "stim", "sweep", "io", "PP"}`.
- IO affects plotting (scatter, labels, trendlines) but **not** stats routing yet.
- `_get_shown_testsets()` and `apply_statistical_test_if_active(~L2108)` always require shown testsets for non-special cases.

### Call sites

- `ui.py:apply_statistical_test_if_active(L2110)`: passes `dd_testsets`, `n_unit`; no `experiment_type`.
- Statusbar (`_get_stat_test_warning(~L1698)`) handles hierarchy/cluster notes but not implicit IO.
- No `ui_designer.py` involvement.

---

## Proposed Solution (Agent-Efficient v2)

### Core idea

- Pass `experiment_type` (default `"time"`) to `compute_statistical_comparison`.
- **Single centralized guard** after group resolution: if `not shown_sets` and `is_io`, set `use_implicit=True` (else error).
- For implicit IO: use helper in accessor to fetch **all sweeps** per recording/group (no per-testset `tset["sweeps"]`).
- Add thin `_get_obs(g, tset, col, per_sweep=False)` helper in stats to avoid duplicating the `sweeps_arg` logic across branches.
- `n_unit` aggregation applies identically (subject/slice/recording level means over the sweep pool).
- Store `"implicit_testset": True` only in final `config` (for statusbar).
- **Efficiency gains**: 1 guard (vs 3), 1 helper (vs 10+ inline `if use_all_sweeps`), minimal UI delta, exact `search_replace`-ready snippets, built-in `/check-work` hooks.

Non-IO modes unchanged. Explicit testsets in IO take precedence.

### Implementation locations (precise, minimal edits)

1. **`src/lib/ui_data_frames.py` (~L588 get_group_obs_for_sweeps + ~L631 get_group_testset_means)**:
   - Update guard/docstring: `sweeps=None` (or empty) means "all available sweeps for recordings in group".
   - In `get_group_obs_for_sweeps`: if `sweeps is None`, skip `.isin(sweeps)` filter or collect `dfo["sweep"].unique()`.
   - In `get_group_testset_means`: route `None` → full per-rec means (no empty return). Update per_sweep path if needed.
   - ~20 LOC. Makes accessor the single source of truth for "all sweeps".

2. **`src/lib/statistics.py:compute_statistical_comparison` (signature + ~L250 + branches)**:

   ```python
   def compute_statistical_comparison(
       ...,
       n_unit: str = "subject",
       experiment_type: str = "time",  # NEW, default for 100% compat
   ) -> dict:
       ...
       shown_sets = [(sid, info) for sid, info in (dd_testsets or {}).items()
                     if info.get("show", False) and info.get("sweeps")]
       is_io = experiment_type == "io"
       use_implicit = False
       if not shown_sets:
           if is_io:
               use_implicit = True  # implicit "all sweeps" per group
           else:
               return {"error": "no shown test sets", "results": []}
       ...
       # Helper to centralize (replace all get_group_testset_means_fn calls)
       def _get_obs(g, tset, col, per_sweep=False):
           sweeps_arg = None if use_implicit else (tset.get("sweeps", []) if tset else [])
           return get_group_testset_means_fn(g, sweeps_arg, aspect=col, per_sweep=per_sweep)

       # Update docstring (top): "For experiment_type='io' and no shown_sets, uses all sweeps per group via accessor (implicit_testset=True in config). n_unit respected."
       # Inline comment at guard: "# IO exception: implicit all-sweeps (v0.16_n_stats_IO); non-IO requires test sets"
       # In ALL branches (ANOVA L340, Friedman L424, Cluster L559/L610, Wilcoxon L720/L813, main loop L921+):
       #   obs_df = _get_obs(g, tset, col)   # or per_sweep=True variant
       # At successful return points, add to config:
       if use_implicit:
           config["implicit_testset"] = True
       ...
   ```
   - Update 3 old line numbers in comments if shifted.
   - ~60 LOC total (centralization saves duplication).

3. **`src/lib/ui.py`**:
   - `apply_statistical_test_if_active(~L2104)`:
     ```python
     experiment_type = getattr(uistate, "experiment_type", "time")
     comp = stats.compute_statistical_comparison(
         ...,
         n_unit=n_unit,
         experiment_type=experiment_type,  # NEW
     )
     ```
   - `_get_stat_test_warning(~L1832, after cluster note)`:
     ```python
     if first_res.get("config", {}).get("implicit_testset"):
         global_notes.append("(IO: all sweeps)")
     ```
   - ~10 LOC. No change to `_get_shown_testsets`, `graphRefresh`, or designer.

4. **Persistence / edge cases / docs**:
   - No new state. `dd_testsets={}` ok for IO.
   - Mixed (explicit + IO): explicit wins.
   - Update module/function docstrings + this plan's verification.
   - Non-goals unchanged (no UI controls, no LMM, one-sample IO out-of-scope).

---

## Detailed Requirements (v2)

### 1. Schema / data contract

- No change to `df_project`, `dd_testsets`, or existing return shapes.
- New param `experiment_type: str = "time"`.
- `config` may include `"implicit_testset": True`.
- Accessor now interprets `sweeps=None` as "all".

### 2. Backward compatibility (explicit)

- Default `"time"` → identical to today.
- Non-IO: always requires test sets.
- IO with test sets: unchanged (explicit precedence).
- Old call sites work (default triggers error path).
- `n_unit`/`n1`/`n2` semantics identical.

### 3. Error / edge handling

- IO + no data → NaN p-values (existing).
- Hierarchy missing → existing warning + fallback.
- Cluster in IO → recording-level + implicit (forces n_unit as before).
- `use_implicit` only when `shown_sets == [] and is_io`.

### 4. Persistence

- None new. `buttonGroup_test_n` unchanged.

### 5. Documentation / comments

- Updated docstrings in `statistics.py` and `ui_data_frames.py`.
- Inline comments at guard/helper.
- **This plan revised** with agent-efficient structure, exact snippets, verification hooks.

### 6. Non-goals (explicit)

- Same as v1 (no `ui_designer.py`, no new controls, no `ttest_per_sweep` changes, no LMM, no IO one-sample).

---

## Verification Steps (for /check-work or verification subagent)

**Use `/check-work` (or spawn "check-work" subagent) after each major edit.** Key tests (run in IO project + time project):

1. **Non-IO (time/default, no test sets)**: `compute_statistical_comparison(..., experiment_type="time")` → `{"error": "no shown test sets", ...}` (unchanged).
2. **IO (no test sets)**: succeeds with `implicit_testset=True` in config; uses all sweeps; correct p-values/n_unit.
3. **IO (with explicit test sets)**: uses explicit; no `implicit_testset` flag.
4. **n_unit variants in IO**: subject/slice/recording aggregation works on implicit data (subject/slice use `_aggregate_to_unit_level`).
5. **Hierarchy missing in IO**: statusbar warning `"{n_unit} not assigned for included recording(s)"` + fallback.
6. **Cluster perm. in IO**: recording-level n, implicit sweeps, note preserved.
7. **Statusbar**: shows `n` report (same format as time-course: `(SAL=5, KETA=4)`) + `(IO: all sweeps)` + `r²=0.XX` (from linregress on unit-level means per group; compact, first available aspect). Uses "info" state (bold, default theme color).
8. **Call site without kwarg**: defaults to `"time"` (compat).
9. **End-to-end**: Manual IO project (no testsets) produces stats markers/statusbar with n + r²; existing tests/projects unchanged.
10. Run full verification subagent; update this plan with results. **Verified PASS** (current implementation post-v0.17 r²): IO statusbar shows n-report + r² (e.g. "ANOVA (IO: all sweeps) (SAL=3, KETA=3) r²=0.85") with "info" bold styling, no "no statusbar at all" regression. ANOVA/t-test succeed on implicit IO (no testsets). r2 calc uses dummy x=range (TODO real IO intensity/volley_amp from dfoutput). Statusbar length ok (centered expanding label handles it). experiment_type_changed + update_anova_label refresh statusbar correctly for IO. No other bugs found. Backward compat intact.

---

## Summary of Deliverables (Agent-Efficient)

| File                                  | Changes (Minimized for efficiency)                                                                                                                                                                               |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/ui_data_frames.py`           | Extend `get_group_testset_means` + `get_group_obs_for_sweeps` to support `sweeps=None` as "all sweeps per group/recording". Update docstring. (~20 LOC)                                                          |
| `src/lib/statistics.py`               | Add `experiment_type: str = "time"` param. Single centralized `use_implicit` guard + `_get_obs` helper (avoids 3 duplicate guards + 10+ ifs). Update all accessor calls, config, docstring + comments. (~60 LOC) |
| `src/lib/ui.py`                       | Pass `experiment_type` in `apply_statistical_test_if_active`. Add implicit note in `_get_stat_test_warning`. (~10 LOC)                                                                                           |
| `work_plans/plan_v0.16_n_stats_IO.md` | This revised agent-efficient version with precise snippets, centralized logic, verification hooks.                                                                                                               |

**Dependencies**: v0.16_n_stats (hierarchy, aggregator) + v0.14_IO (`experiment_type`). Line numbers approximate (use `grep`/`read_file` before edits).

**Risk / migration note**: Low. IO users gain automatic stats (all sweeps = scientifically appropriate for IO curves). Time-mode unchanged. Default param ensures external scripts/tests unaffected. Centralization reduces future maintenance.

**Agent workflow recommendation**:

- `read_file` on full functions first.
- `search_replace` using exact snippets above.
- After each file: `/check-work` or spawn verification subagent.
- `git commit` with clear message referencing plan.
- Final: update verification results in this MD.

(End of revised plan — optimized for agentic execution. Ready for implementation. Follow "ask when unclear".)
