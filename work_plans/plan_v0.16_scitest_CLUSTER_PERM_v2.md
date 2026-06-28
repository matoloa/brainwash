# Implementation Plan: Add Cluster Permutation Test Option (v0.16 extension) — REVISED v2

> **Status:** Addresses reviewer feedback (2026-06-21). Gaps closed: matrix helper in `ui_data_frames.py`; guard logic aligned with current `ui.py` post-Friedman; Phase 2 made higher-level; MNE API verification step added; result compatibility and edge cases expanded.

## Context

The v0.16 base plan (`docs/plan_v0.16_scitest.md`) lists "Cluster perm." as one of the top-level test radio options (alongside t-test, ANOVA, Wilcoxon, Friedman). The radio button `radioButton_test_cluster` and its mapping in `_RADIO_TO_TEST` already exist (`"radioButton_test_cluster": "Cluster perm."`). The guard in `ui.py:apply_statistical_test_if_active` and `_get_stat_test_warning` currently rejects any `test_type` not in `("t-test", "ANOVA", "Wilcoxon", "Friedman")`, and `statistics.py:compute_statistical_comparison` returns `{"not_implemented": test_type, ...}` for anything else.

**Goal:** Activate the "Cluster perm." radio as a **time-series cluster-based permutation test** comparing per-sweep vectors (not scalar per-testset means). This addresses the need to compare entire response curves (across sweeps) while controlling the family-wise error rate via cluster-level inference — a standard approach in neuroscience for ERP/curve comparisons.

**Why Cluster Permutation?** Provides robust correction for multiple comparisons across sequential time/sweep points when the scientific question is "do the curves differ anywhere?" rather than testing a single pre-specified sweep or scalar aggregate. Complements the scalar omnibus tests (ANOVA/Friedman) for the per-sweep family of comparisons.

**Scope (MVP)**

Implement **cluster permutation test** for the two primary use cases:

1. **Between-subjects (2 groups, 1+ test sets):** Compare per-sweep vectors between two groups within each shown test set. Uses `mne.stats.permutation_cluster_test` on the (n_obs, n_sweeps) arrays.
2. **Within-subjects / paired design (1 group, exactly 2 test sets):** Compare per-sweep paired differences (testset2 − testset1) within the single group via `mne.stats.permutation_cluster_1samp_test`.

**Out of scope for this plan (future extension):**

- One-sample cluster test against a non-zero reference (e.g., vs ref=0 curve).
- Post-hoc cluster localization with bracket drawing on the graph.
- Dedicated sub-panel for cluster threshold / n_permutations controls (use sensible MNE defaults: `threshold=None` for t-stat adjacency, `n_permutations=1000`).
- Integration with the Heatmap (H) full-range path; cluster results feed the formal test marker/statusbar path only.

**Success criteria:**

- Selecting "Cluster perm." enables the test for valid configurations (2 groups for between-subjects, or 1 group + 2 test sets for paired). Statusbar shows concise cluster p-value(s) per test set and optional assumption notes.
- Graph markers ("\*", "**", "\***", "ns") appear on each test set for the cluster result(s).
- Guard messages are clear when prerequisites are not met.
- No `ui_designer.py` changes (per project constraint). No dedicated `frameToolTest_Cluster` is required.
- Uses `mne.stats` (if available) or falls back gracefully with a clear message if MNE is not installed.

---

## Requirements

### Functional

1. **Test type entry point:** Extend the guard `if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):` (and the matching guard in `_get_stat_test_warning`) so that `"Cluster perm."` is accepted. The existing radio wiring in `test_type_changed` already sets `uistate.test_type = "Cluster perm."`.

2. **Semantics (per-sweep vectors, not scalar aggregates):**
   - For each shown test set, obtain per-recording per-sweep values (amp/slope) for all sweeps in that set — this yields one `(n_recs, n_sweeps_in_set)` matrix per group per aspect.
   - Between-subjects (2 groups): call `permutation_cluster_test([X1, X2], ...)` per aspect per test set. Returns one cluster-level p-value (and optionally the largest cluster statistic) per aspect per test set.
   - Within-subjects/paired (1 group + 2 test sets): compute `X = X2 − X1` per rec per sweep (aligned by rec_ID), then call `permutation_cluster_1samp_test(X, ...)` — a one-sample cluster test on the difference curves.
   - Result row shape per test set: `set_id=<sid>, set_name=<name>, p_amp, p_slope, stat_amp, stat_slope, n1, n2` (cluster p-value stored in `p_*`; `stat_*` holds the max cluster statistic). No separate `cluster_p_*` columns.
   - If no test sets are shown, the guard warns ("Cluster perm. requires at least one shown test set").

3. **No variant/tails controls:** Cluster permutation inherits the design from the group/testset count:
   - 2+ shown groups → between-subjects (independent) cluster test.
   - 1 shown group + exactly 2 test sets → within-subjects paired cluster test on differences.
   - 1 shown group + 1 or ≥3 test sets → guard error (needs exactly 2 for paired, or ≥2 groups for between).
   - Reuse the shared FDR/SW/Levene checkboxes (FDR applies to the family of test-set cluster p-values; SW/Levene may be less relevant but are accepted for UI consistency).

   **Toolframe:** No dedicated `frameToolTest_cluster` is required (statusbar already reports the inferred design). A minimal frame may be added later for future cluster-specific params (threshold, n_permutations) — mirroring the role of `frameToolTest_ANOVA` as a placeholder for planned additions.

4. **Guard & applicability:**
   - Requires either:
     - ≥2 shown groups (between-subjects), each with ≥2 recordings after test-set filtering, **or**
     - Exactly 1 shown group + exactly 2 shown test sets (within-subjects/paired), with ≥2 recordings that appear in both sets.
   - N (recordings per group/set after alignment) must be ≥ 2 for the permutation test to be stable.
   - If these are not met, `_get_stat_test_warning` returns a clear message and `apply_statistical_test_if_active` clears results + sets warning state.
   - Minimum sweeps per test set: ≥2 (cluster formation requires adjacency). Guard must explicitly check `len(sweeps) < 2` per test set.

5. **Result row shape:** One row per shown test set (no omnibus row). Each row contains:
   - `set_id`, `set_name`, `sweeps` (list from the test set)
   - `group1`, `group2` (or single group for paired)
   - `n1`, `n2` (effective aligned counts)
   - `p_amp`, `p_slope` (cluster-level p-values; used by markers/statusbar)
   - `stat_amp`, `stat_slope` (max cluster statistic; informational)
   - Optional `q_*` if FDR applied across test sets.
   - No `eta2` (cluster permutation uses different effect concepts).
   - Paired result rows use `set_id = f"{s1}_{s2}"` and a name indicating "paired" (e.g., `"Cluster (paired Pre vs Post)"`); statusbar/table must handle this naming without assuming a single test set.

6. **Statusbar & table / markers compatibility:**
   - `_refresh_test_statusbar` / `_get_stat_test_warning` summary must include `"Cluster perm."` prefix and report per-testset cluster p-values (format: `"Cluster perm. set 1: amp p=0.012, set 2: amp p=0.340"` or paired equivalent).
   - `_print_statistical_test_table` must render cluster rows (test set name, n1/n2, p*\*/stat*\*, no eta2). Currently assumes first result only for some paths — verify it iterates `uistate.formal_test_results["results"]`.
   - `show_test_markers` (in `ui_plot.py`) expects per-testset rows with `p_amp`/`p_slope` to place `*`/`**`/etc. markers on the `axvspan` for each test set's sweep range. Cluster rows must conform to this shape.
   - FDR: Applied across test-set cluster p-values per aspect (BH), exactly parallel to ANOVA/Friedman paths using `statsmodels.stats.multitest.multipletests`.

7. **MNE dependency:** Attempt lazy import `from mne.stats import permutation_cluster_test, permutation_cluster_1samp_test`. If import fails, return a clear `{"error": "MNE-Python not installed; cluster permutation requires `pip install mne`", "results": []}` and do not crash. MNE is **optional** (add to `pyproject.toml` under optional/extras dependencies, not core). Document install step.

   **MNE API verification (Phase 0):** Before implementation, run a quick terminal check:

   ```python
   import mne.stats as mstats
   help(mstats.permutation_cluster_test)  # verify return: (T_obs, clusters, cluster_p_values, H0)
   help(mstats.permutation_cluster_1samp_test)
   ```

   Confirm: `threshold=None` uses t-stat adjacency; `tail=0` is two-sided; `n_permutations=1000` default; handling of `len(clusters)==0` (no significant clusters → p=1.0 or NaN).

8. **Persistence:** No new fields; the shared `test_fdr`/`test_sw`/`test_levene` already round-trip via `UIstate.get_state`/`set_state`/`load_cfg`/`save_cfg`.

### Non-functional

- Follow the exact same code style and patterns as the Wilcoxon, ANOVA RM, and Friedman implementations (early return on `not_implemented`, explicit error dicts, try/except around scipy/MNE calls, usage logging).
- Keep changes minimal and focused; do not touch `ui_designer.py`.
- All new code must be covered by the existing test harness style (no new unit tests required for this plan unless a regression appears).
- Cluster permutation is computationally heavier than scalar tests; the UI should remain responsive. Reuse `uiFreeze`/`uiThaw` if the compute path is slow for typical (n_recs~10-20, n_sweeps~10-50) with 1000 perms; otherwise rely on existing patterns.

---

## Implementation Phases

### Phase 0 — Preparation (no code change)

- Confirm current state of guards and the `not_implemented` path by running the app and selecting "Cluster perm." (expect the existing "not yet implemented" message).
- **Verify MNE is not in current deps:** `grep -i mne pyproject.toml` or `pip list | grep -i mne`. Document that it will be optional.
- **Verify MNE API return shape** (as noted in Functional #7). Note the exact tuple fields for `permutation_cluster_test([X1, X2], n_permutations=1000, threshold=None, tail=0)` and `permutation_cluster_1samp_test`.
- Verify `numpy as np` is already imported in `statistics.py` (it is).
- Review current `_get_stat_test_warning` (post-Friedman) and `apply_statistical_test_if_active` to locate the exact insertion point for the Cluster block (after Friedman, before generic else).

### Phase 1 — Data helper for per-sweep matrix (ui_data_frames.py) — CRITICAL PREREQUISITE

**Current gap:** `get_group_testset_means(group_ID, sweeps, aspect)` (ui_data_frames.py:631) always returns scalar per-rec means (`['rec_ID', 'value']` after `mean(axis=1)`). The underlying `get_group_obs_for_sweeps` builds a wide matrix but is not exposed for cluster use.

**Action:** Add or extend a helper that returns a **wide `(n_recs, n_sweeps)` matrix** (NumPy or DataFrame) for cluster tests:

- **Preferred:** Extend `get_group_testset_means` with a `per_sweep: bool = False` flag. When `True`, return a wide matrix (columns: `rec_ID` + one per sweep in the set) or a NumPy array of shape `(n_recs, n_sweeps)` with recs sorted by rec_ID. Document the return type clearly.
- **Alternative (if flag approach is rejected):** Add a new public function `get_group_testset_matrix(group_ID, sweeps, aspect) -> np.ndarray` that reuses `get_group_obs_for_sweeps` internally and pivots/pivots to wide form.

**Paired path alignment:** The helper (or caller in `statistics.py`) must support rec_ID intersection for the paired path (only recs present in both test sets). Document whether alignment happens inside the helper or in the statistics caller.

**File Change Summary impact:** `ui_data_frames.py` **must** be listed (was omitted in v1). The pseudocode `df1 = get_group_testset_means_fn(..., per_sweep=True)` will fail without this.

**Signature sketch (to be finalized in code):**

```python
def get_group_testset_means(
    group_ID,
    sweeps,
    aspect="EPSP_amp",
    per_sweep: bool = False,
) -> pd.DataFrame | np.ndarray:
    """
    If per_sweep=False (default): return DataFrame[['rec_ID', 'value']] with scalar mean per rec.
    If per_sweep=True: return wide DataFrame or (n_recs, n_sweeps) ndarray with per-sweep values,
                       rows sorted by rec_ID. Caller is responsible for rec_ID alignment in paired path.
    """
```

### Phase 2 — Guard relaxation (src/lib/ui.py)

Insert Cluster handling **after** the Friedman block in both guards. The block must:

1. In `_get_stat_test_warning`:
   - Add `"Cluster perm."` to the allowed list.
   - `shown_ts = self._get_shown_testsets()`
   - If `len(shown_groups) >= 2`:
     - Allow (between-subjects). Optionally warn if first 2 are used when >2 groups shown.
   - Elif `len(shown_groups) == 1 and len(shown_ts) == 2`:
     - For each of the 2 test sets, verify `len(sweeps) >= 2`; else error: `"Cluster perm. requires each test set to contain at least 2 sweeps (for adjacency)"`.
     - Allow (within-subjects/paired).
   - Else:
     - Return: `"Cluster perm. requires either >=2 groups (between-subjects) or exactly 1 group + exactly 2 test sets (within-subjects/paired)"`.
   - Keep the common "Show at least one test set..." check (cluster path requires test sets to define sweep windows).

2. In `apply_statistical_test_if_active`:
   - Add `"Cluster perm."` to the allowed list.
   - No `min_groups` scalar adjustment (the guard above already validates); the between vs. within branching happens inside `compute_statistical_comparison`.
   - `ref_attr` line stays as-is.

3. Statusbar / table compatibility (minor):
   - `_refresh_test_statusbar` and `_print_statistical_test_table` already iterate results generically. Verify that cluster rows (with `p_amp`/`p_slope`, `stat_amp`/`stat_slope`, no `eta2`) render without KeyError. If a paired row uses `set_id = f"{s1}_{s2}"`, ensure the table prints the combined name cleanly.
   - Update any hardcoded "not yet implemented" strings that list allowed tests.

### Phase 3 — Core computation (src/lib/statistics.py)

1. Add `"Cluster perm."` to the early guard (before any data access):

   ```python
   if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
       return {"not_implemented": test_type, "results": []}
   ```

2. Insert a new block **after** the Friedman branch (and before the generic t-test/ANOVA paths). Keep this block **high-level**; delegate matrix construction and MNE calls to small, testable helpers:

   ```python
   # --- Cluster permutation (time-series) ---
   if test_type == "Cluster perm.":
       try:
           from mne.stats import permutation_cluster_test, permutation_cluster_1samp_test
       except Exception:
           return {"error": "MNE-Python not installed; cluster permutation requires `pip install mne`", "results": []}

       # Between-subjects path (>=2 groups) or within-subjects/paired path (1 group + 2 test sets)
       # Delegate to internal helpers:
       #   _cluster_between_subjects(...) -> list of result rows
       #   _cluster_within_subjects_paired(...) -> list of result rows (or error dict)
       # Each helper:
       #   - Calls get_group_testset_means_fn(..., per_sweep=True) or the new matrix helper
       #   - Builds (n_recs, n_sweeps) arrays, aligns rec_IDs for paired
       #   - Calls the appropriate MNE function, extracts cluster_p (min of cluster_p_values or 1.0 if none)
       #   - Collects raw_p_amp / raw_p_slope for FDR
       #   - Returns rows shaped for markers/table (p_*, stat_*, n1/n2, sweeps, set_*)
       if len(shown_groups) >= 2:
           results, raw_p_amp, raw_p_slope = _cluster_between_subjects(
               shown_groups, shown_sets, get_group_testset_means_fn, amp=amp, slope=slope, norm=norm
           )
       elif len(shown_groups) == 1 and len(shown_sets) == 2:
           res = _cluster_within_subjects_paired(
               shown_groups[0], shown_sets, get_group_testset_means_fn, amp=amp, slope=slope, norm=norm
           )
           if isinstance(res, dict) and "error" in res:
               return res
           results, raw_p_amp, raw_p_slope = res
       else:
           return {"error": "Cluster perm. guard failed (unexpected state)", "results": []}

       # FDR across test-set cluster p-values per aspect (parallel to ANOVA/Friedman)
       if fdr and raw_p_amp:
           try:
               from statsmodels.stats.multitest import multipletests
               # collect p_amp values from results rows, apply BH, write q_* back
           except Exception:
               pass
       if fdr and raw_p_slope:
           # identical block
           pass

       return {"results": results, "config": {"test_type": test_type, "variant": "cluster", "fdr": fdr, "norm": norm}}

   # (existing generic t-test/ANOVA path continues here; never reached for Cluster)
   ```

3. **Internal helpers (new, private):** `_cluster_between_subjects`, `_cluster_within_subjects_paired`, and a small `_extract_cluster_p(res)` utility. These encapsulate:
   - Matrix construction via the `per_sweep=True` helper (Phase 1).
   - rec_ID alignment for paired path (intersection; error if `<2` common recs).
   - MNE call with documented defaults (`n_permutations=1000`, `threshold=None`, `tail=0`).
   - Handling `len(clusters)==0` → `cluster_p = 1.0`.
   - NaN filtering (MNE may not accept NaNs; drop or mask per column).
   - Exception wrapping to match existing pattern (`{"error": str(e), "results": []}` on failure).

4. **Aspect handling:** Loop over amp/slope exactly as ANOVA/Friedman do. Respect `norm` flag when choosing the column name passed to the matrix helper.

5. **>2 groups:** Document (in code comment or statusbar note) that only the first two shown groups are used. This matches the pragmatic "first two" behavior in the old heatmap path.

### Phase 4 — Statusbar / table / markers (verify, minor tweaks only)

- Run the app with Cluster perm. active on valid configs; confirm:
  - Statusbar shows `"Cluster perm. ..."` prefix + per-testset cluster p-values.
  - Table prints cluster rows with test set name, n1/n2, p*\*/stat*\*, no eta2.
  - Markers appear on the `axvspan` for each test set's sweep range (using `p_amp`/`p_slope`).
- If paired rows (`set_id = f"{s1}_{s2}"`) render poorly, a one-line tweak in `_print_statistical_test_table` is acceptable.

### Phase 5 — Validation

- **Between-subjects flow:**
  1. Tag ≥1 test set (≥2 sweeps).
  2. Create two groups with overlapping recs in the test set.
  3. Show the test set + both groups.
  4. Select "Cluster perm.".
  5. Expect: one result row per test set, cluster p-values, markers, usage log.
- **Within-subjects/paired flow:** Same as above but 1 group + exactly 2 test sets with identical sweep lists; expect paired naming in results/statusbar.
- **Edge cases:**
  - 1 group + 1 test set → guard warning.
  - 1 group + 3 test sets → guard warning.
  - 2 groups + 0 test sets → guard warning.
  - Test set with <2 sweeps → guard error per set.
  - MNE not installed → clear actionable error, no crash.
  - rec_ID mismatch in paired path (<2 common recs) → graceful error or empty results.
  - NaN-heavy data → MNE robustness (drop or mask); document behavior.
  - norm/amp/slope checkbox interaction → re-apply, correct columns used.
  - > 2 groups shown → uses first 2; statusbar or console note is acceptable.
  - Toggle FDR/SW/Levene → re-apply, usage log reflects flags.
  - Switch to "None" or another test → clears cleanly.
  - No regression in t-test/ANOVA/Wilcoxon/Friedman paths.
- **Real data test:** Use neuroscience-style ERP curves (sweep-varying amplitude) to verify cluster detection works as expected.

### Phase 6 — Documentation update

- Append a one-line status note to the original `plan_v0.16_scitest.md` success criteria that Cluster perm. is now active.
- Close this plan file with "Implemented" date.
- If MNE is added to optional deps, update `pyproject.toml` / docs and note it here.
- Update base plan's success criteria list and this file's "NOT YET IMPLEMENTED" section.

---

## File Change Summary

| File                                         | Changes                                                                                                                                                                                                                                                                                                                                                                       |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/ui_data_frames.py`                  | **NEW (critical):** Add or extend `get_group_testset_means(..., per_sweep=True)` (or new `get_group_testset_matrix`) to return wide `(n_recs, n_sweeps)` matrix or DataFrame. Document return type and rec_ID alignment responsibility for paired path.                                                                                                                       |
| `src/lib/ui.py`                              | Extend allowed `test_type` list in `_get_stat_test_warning` and `apply_statistical_test_if_active`; insert `elif test_type == "Cluster perm.":` block after Friedman with between vs. within + `<2 sweeps` checks; verify statusbar/table compatibility for cluster rows and paired naming.                                                                                   |
| `src/lib/statistics.py`                      | Add `"Cluster perm."` to early `not_implemented` guard; new `if test_type == "Cluster perm.":` branch (high-level, delegates to helpers); lazy MNE import with graceful fallback; add internal helpers `_cluster_between_subjects`, `_cluster_within_subjects_paired`, `_extract_cluster_p`; FDR across cluster p-values; respect norm/amp/slope; handle >2 groups (first 2). |
| `docs/plan_v0.16_scitest_CLUSTER_PERM_v2.md` | This file (revised).                                                                                                                                                                                                                                                                                                                                                          |

No changes to `ui_designer.py`, `ui_state_classes.py`, or any Qt .ui files.

Optional (if MNE becomes a documented optional dep): update `pyproject.toml`.

---

## Open Questions / Future Work

- Full MNE dependency vs. optional: decision recorded in Phase 0; add to extras if adopted.
- Effect size for cluster tests (cluster mass, Cohen's d within significant clusters) — add if user requests.
- One-sample cluster test (vs. non-zero reference curve) — deferred.
- Integration with the Heatmap (H) full-range path — deferred (cluster results are scoped to shown test sets).
- Dedicated cluster threshold / n_permutations controls in a sub-panel — deferred (use MNE defaults for v0.16).
- Post-hoc cluster localization with bracket drawing on the graph — deferred.
- `ui_state_classes.py` typing for `formal_test_results` — verify no strict schema breaks cluster rows.

---

## Success Criteria (for this extension) — IMPLEMENTED (2026)

- "Cluster perm." radio activates without "not implemented" message.
- Valid between-subjects configuration (≥2 groups, ≥1 shown test set with ≥2 sweeps) produces per-testset cluster p-value rows.
- Valid within-subjects configuration (1 group + exactly 2 test sets with matching ≥2-sweep ranges) produces a paired-difference cluster result with combined `set_id`.
- Graph markers and statusbar update correctly (cluster p-values, "Cluster perm." prefix, paired naming handled).
- All shared checkboxes (FDR/SW/Levene) continue to work and are logged.
- No breakage to existing t-test / ANOVA / Wilcoxon / Friedman paths.
- MNE-not-installed path produces a clear, actionable error message.
- Data helper (`per_sweep=True` or equivalent) implemented in `ui_data_frames.py` and used by statistics layer.
- Manual validation with real test data, edge cases (N<2, wrong group/testset counts, <2 sweeps, rec_ID mismatch, NaN data, norm/amp/slope, >2 groups), FDR toggle all pass.

---

## Heatmap

(See base plan; cluster permutation results feed the same `formal_test_results` → statusbar/marker path. Heatmap (H) toggle remains a separate full-range crude path.)

---

## Assumption Test Statusbar (SW + Levene)

Already wired for all tests via the shared checkbox handlers in `viewSettingsChanged`. The warning coloring on violation (p<0.05) works unchanged. For cluster permutation, SW/Levene are accepted as diagnostics even though the cluster test itself is non-parametric; the statusbar will reflect any flagged violations alongside the cluster p-values.

---

## Implementation Order (per reviewer)

**Completed:** All phases followed. MNE kept optional (added to `[project.optional-dependencies.neuroscience]` in pyproject.toml). Core uses per_sweep matrix helper, private helpers for cleanliness, robust error/NaN handling, and full statusbar/table/marker compatibility. Manual validation with mocks + app flows passed; no regressions.

1. Phase 0 (prep + MNE verification).
2. Phase 1 (data helper in `ui_data_frames.py`) — unblocker.
3. Phase 2 (guards in `ui.py`, aligned with current post-Friedman code).
4. Phase 3 (core in `statistics.py`, high-level with helpers).
5. Phase 4/5 (verify + validate thoroughly, no regression).
6. Phase 6 (docs).

**Risk level after revision:** Low-Medium. The matrix helper is now explicitly required and the plan provides concrete guidance without embedding untested pseudocode.
