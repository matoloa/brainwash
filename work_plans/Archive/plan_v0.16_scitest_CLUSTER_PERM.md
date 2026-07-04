# Implementation Plan: Add Cluster Permutation Test Option (v0.16 extension)

## Context

The v0.16 base plan (`docs/plan_v0.16_scitest.md`) lists "Cluster perm." as one of the top-level test radio options (alongside t-test, ANOVA, Wilcoxon, Friedman). The radio button `radioButton_test_cluster` and its mapping in `_RADIO_TO_TEST` already exist (`"radioButton_test_cluster": "Cluster perm."`). The guard in `ui.py:apply_statistical_test_if_active` and `_get_stat_test_warning` currently rejects any `test_type` not in `("t-test", "ANOVA", "Wilcoxon", "Friedman")`, and `statistics.py:compute_statistical_comparison` returns `{"not_implemented": test_type, ...}` for anything else.

**Goal:** Activate the "Cluster perm." radio as a **time-series cluster-based permutation test** comparing per-sweep vectors (not scalar per-testset means). This addresses the need to compare entire response curves (across sweeps) while controlling the family-wise error rate via cluster-level inference — a standard approach in neuroscience for ERP/curve comparisons.

**Why Cluster Permutation?** Provides robust correction for multiple comparisons across sequential time/sweep points when the scientific question is "do the curves differ anywhere?" rather than testing a single pre-specified sweep or scalar aggregate. Complements the scalar omnibus tests (ANOVA/Friedman) for the per-sweep family of comparisons.

**Scope (MVP)**

Implement **cluster permutation test** for the two primary use cases:

1. **Between-subjects (2 groups, 1+ test sets):** Compare per-sweep vectors between two groups within each shown test set (or across all sweeps if no test sets shown — future). Uses `mne.stats.permutation_cluster_test` on the (n_obs, n_sweeps) arrays.
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
   - Result row shape per test set: `set_id=<sid>, set_name=<name>, p_amp, p_slope, stat_amp, stat_slope, n1, n2, cluster_p_amp, cluster_p_slope` (or reuse `p_*` for the cluster p; document either way).
   - If no test sets are shown, the guard warns ("Cluster perm. requires at least one shown test set").

**No variant/tails controls:** Cluster permutation inherits the design from the group/testset count:

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
   - Minimum sweeps per test set: ≥2 (cluster formation requires adjacency).

5. **Result row shape:** One row per shown test set (no omnibus row). Each row contains:
   - `set_id`, `set_name`, `sweeps` (list from the test set)
   - `group1`, `group2` (or single group for paired)
   - `n1`, `n2` (effective aligned counts)
   - `p_amp`, `p_slope` (cluster-level p-values)
   - `stat_amp`, `stat_slope` (max cluster statistic)
   - Optional `q_*` if FDR applied across test sets.
   - No `eta2` (cluster permutation uses different effect concepts).

6. **Statusbar & table:** The existing `_refresh_test_statusbar`, `_print_statistical_test_table`, and `show_test_markers` paths already handle per-testset result rows generically; they will work once results are produced. Statusbar may show e.g. `"Cluster perm. set 1: amp p=0.012, set 2: amp p=0.340"`.

7. **MNE dependency:** Attempt `from mne.stats import permutation_cluster_test, permutation_cluster_1samp_test`. If import fails, return a clear `{"error": "MNE-Python not installed; cluster permutation requires `pip install mne`", "results": []}` and do not crash.

8. **Persistence:** No new fields; the shared `test_fdr`/`test_sw`/`test_levene` already round-trip via `UIstate.get_state`/`set_state`/`load_cfg`/`save_cfg`.

### Non-functional

- Follow the exact same code style and patterns as the Wilcoxon, ANOVA RM, and Friedman implementations (early return on `not_implemented`, explicit error dicts, try/except around scipy/MNE calls, usage logging).
- Keep changes minimal and focused; do not touch `ui_designer.py`.
- All new code must be covered by the existing test harness style (no new unit tests required for this plan unless a regression appears).
- Cluster permutation is computationally heavier than scalar tests; the UI should remain responsive (consider a brief "Computing clusters..." message or reuse the existing freeze/thaw if needed, but prefer non-blocking for typical dataset sizes).

---

## Implementation Phases

### Phase 0 — Preparation (no code change)

- Confirm current state of guards and the `not_implemented` path by running the app and selecting "Cluster perm." (expect the existing "not yet implemented" message).
- Verify whether `mne` is already a dependency or must be added to `pyproject.toml` / `requirements.txt`. Document the decision.
- If MNE will be optional, plan the lazy import + graceful fallback.

### Phase 1 — Guard relaxation (src/lib/ui.py)

1. In `_get_stat_test_warning`:
   - Add `"Cluster perm."` to the allowed list: `if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):`
   - Insert an `elif test_type == "Cluster perm.":` block after the Friedman block that:
     - Obtains `shown_ts = self._get_shown_testsets()`
     - If `len(shown_groups) >= 2`:
       - Allow (between-subjects path).
     - Elif `len(shown_groups) == 1 and len(shown_ts) == 2`:
       - Allow (within-subjects/paired path).
     - Else:
       - Return a clear message: `"Cluster perm. requires either >=2 groups (between-subjects) or exactly 1 group + exactly 2 test sets (within-subjects/paired)"`.
   - Keep the "Show at least one test set..." check common (cluster needs test sets to define the sweep ranges for comparison).

2. In `apply_statistical_test_if_active`:
   - Add `"Cluster perm."` to the allowed list: `if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):`
   - No `min_groups` adjustment needed beyond the guard in `_get_stat_test_warning` (the between vs. within logic is handled inside `compute_statistical_comparison`).
   - The `ref_attr` line can stay as-is (Cluster perm. never uses one-sample ref in v0.16).

### Phase 2 — Core computation (src/lib/statistics.py)

1. Add `"Cluster perm."` to the early guard:

   ```python
   if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
       return {"not_implemented": test_type, "results": []}
   ```

2. Insert a new block **after** the Friedman branch (and before the generic t-test/ANOVA paths) modeled on the RM-ANOVA / Friedman omnibus blocks:

   ```python
   # --- Cluster permutation (time-series) ---
   if test_type == "Cluster perm.":
       # Between-subjects: >=2 groups, compare per-sweep vectors within each shown test set
       # Within-subjects (paired): 1 group + exactly 2 test sets, cluster on difference curves
       try:
           from mne.stats import permutation_cluster_test, permutation_cluster_1samp_test
       except Exception:
           return {"error": "MNE-Python not installed; cluster permutation requires `pip install mne`", "results": []}

       results = []
       raw_p_amp = []
       raw_p_slope = []
       aspects = []
       if amp:
           aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
       if slope:
           aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))

       if len(shown_groups) >= 2:
           # Between-subjects path: compare group1 vs group2 within each test set
           g1, g2 = shown_groups[0], shown_groups[1]
           for sid, tset in shown_sets:
               sweeps = list(tset.get("sweeps", []))
               if len(sweeps) < 2:
                   continue  # need at least 2 points for cluster adjacency
               res_row = {
                   "set_id": sid,
                   "set_name": tset.get("set_name", f"set {sid}"),
                   "sweeps": sweeps,
                   "group1": [g1],
                   "group2": [g2],
                   "n1": 0,
                   "n2": 0,
               }
               for short, col in aspects:
                   try:
                       df1 = get_group_testset_means_fn(g1, sweeps, aspect=col, per_sweep=True)
                       df2 = get_group_testset_means_fn(g2, sweeps, aspect=col, per_sweep=True)
                       # Expect df with columns: rec_ID, sweep_0, sweep_1, ... or long form; adapt as needed
                       # For MVP we assume a helper that returns (n_recs, n_sweeps) matrix sorted by rec_ID
                       X1 = _to_matrix(df1, sweeps)  # implement small adapter if needed
                       X2 = _to_matrix(df2, sweeps)
                       if X1.shape[0] < 2 or X2.shape[0] < 2:
                           continue
                       # Cluster test on adjacency (adjacent sweeps); threshold=None uses t-stat default
                       res = permutation_cluster_test([X1, X2], n_permutations=1000, threshold=None, tail=0)
                       # res typically returns (F_obs, clusters, cluster_p_values, H0)
                       cluster_p = float(np.min(res[2])) if len(res[2]) > 0 else np.nan
                       cluster_stat = float(np.max(res[0])) if hasattr(res[0], "size") else np.nan
                       res_row[f"p_{short}"] = cluster_p
                       res_row[f"stat_{short}"] = cluster_stat
                       res_row["n1"] = X1.shape[0]
                       res_row["n2"] = X2.shape[0]
                       if short == "amp":
                           raw_p_amp.append(f"p_{short}")
                       else:
                           raw_p_slope.append(f"p_{short}")
                   except Exception:
                       pass
               if "p_amp" in res_row or "p_slope" in res_row:
                   results.append(res_row)

       elif len(shown_groups) == 1 and len(shown_sets) == 2:
           # Within-subjects / paired path: 1 group, 2 test sets → cluster on difference curves
           g = shown_groups[0]
           s1, tset1 = shown_sets[0]
           s2, tset2 = shown_sets[1]
           sweeps1 = list(tset1.get("sweeps", []))
           sweeps2 = list(tset2.get("sweeps", []))
           # For MVP require identical sweep lists (or intersect); document behavior
           if sweeps1 != sweeps2 or len(sweeps1) < 2:
               return {"error": "paired cluster perm. requires two test sets with identical sweep ranges", "results": []}
           res_row = {
               "set_id": f"{s1}_{s2}",
               "set_name": f"Cluster (paired {tset1.get('set_name','set1')} vs {tset2.get('set_name','set2')})",
               "sweeps": sweeps1,
               "group1": [g],
               "n1": 0,
               "n2": 0,
           }
           for short, col in aspects:
               try:
                   df1 = get_group_testset_means_fn(g, sweeps1, aspect=col, per_sweep=True)
                   df2 = get_group_testset_means_fn(g, sweeps2, aspect=col, per_sweep=True)
                   X1 = _to_matrix(df1, sweeps1)
                   X2 = _to_matrix(df2, sweeps2)
                   # Align by rec_ID intersection (same recs in both sets)
                   common = np.intersect1d(df1["rec_ID"].values if "rec_ID" in df1.columns else [],
                                           df2["rec_ID"].values if "rec_ID" in df2.columns else [])
                   if len(common) < 2:
                       continue
                   # Build difference matrix (row per common rec)
                   # ... (implementation detail: index by rec_ID and subtract)
                   Xdiff = X2_aligned - X1_aligned  # shape (n_common, n_sweeps)
                   res = permutation_cluster_1samp_test(Xdiff, n_permutations=1000, threshold=None, tail=0)
                   cluster_p = float(np.min(res[2])) if len(res[2]) > 0 else np.nan
                   cluster_stat = float(np.max(res[0])) if hasattr(res[0], "size") else np.nan
                   res_row[f"p_{short}"] = cluster_p
                   res_row[f"stat_{short}"] = cluster_stat
                   res_row["n1"] = Xdiff.shape[0]
                   if short == "amp":
                       raw_p_amp.append(f"p_{short}")
                   else:
                       raw_p_slope.append(f"p_{short}")
               except Exception:
                   pass
           if "p_amp" in res_row or "p_slope" in res_row:
               results.append(res_row)

       # FDR across test-set cluster p-values (per aspect)
       if fdr and raw_p_amp:
           try:
               from statsmodels.stats.multitest import multipletests
               # collect p_amp values from results rows...
               # (pattern identical to Friedman / ANOVA RM)
           except Exception:
               pass
       # same for slope...

       return {"results": results, "config": {"test_type": test_type, "variant": "cluster", "fdr": fdr, "norm": norm}}

   # (existing generic t-test / ANOVA path continues here)
   ```

3. **Adapter helper (optional, internal):** If `get_group_testset_means_fn` currently returns a long-form DataFrame with one row per (rec, sweep), a small internal `_to_matrix(df, sweeps)` can pivot to `(n_recs, n_sweeps)`. Document whether the existing helper is extended with a `per_sweep=True` flag or a new accessor is introduced in `ui_groups.py`.

4. Ensure the generic t-test/ANOVA path is never reached for Cluster perm. (the early `if` returns before it).

### Phase 3 — Statusbar / table / markers (no code change expected)

- The existing `_print_statistical_test_table`, `_refresh_test_statusbar`, and `uiplot.show_test_markers` already treat any result row generically.
- Verify that per-testset cluster rows render clearly (test set name + "cluster p=..." is sufficient). Minor label tweaks in `_print...` are acceptable if needed for readability.

### Phase 4 — Validation

- Manual test flow (between-subjects):
  1. Tag ≥1 test set (e.g., sweeps 10-19).
  2. Create two groups with recordings that have data in the test set.
  3. Show the test set and both groups.
  4. Select "Cluster perm." radio.
  5. Expect: one result row per shown test set, statusbar summary with cluster p-values, markers on the test set region, usage log entry.
- Manual test flow (within-subjects/paired):
  1. Tag exactly two test sets with identical sweep ranges.
  2. Create one group containing recordings present in both sets.
  3. Show both test sets.
  4. Select "Cluster perm.".
  5. Expect: single paired-difference cluster result row, statusbar note indicating "paired", markers appear.
- Edge cases:
  - 1 group + 1 test set → guard warning.
  - 1 group + 3 test sets → guard warning (needs exactly 2 for paired).
  - 2 groups + 0 test sets shown → guard warning (cluster requires test sets to define sweep windows).
  - MNE not installed → clear error message, no crash.
  - Test set with <2 sweeps → skip that set (or warn).
  - Toggle FDR/SW/Levene while Cluster perm. active → re-apply, usage log reflects the flags.
  - Switch back to "None" or another test → clears results cleanly.

### Phase 5 — Documentation update

- Append a one-line status note to the original `plan_v0.16_scitest.md` success criteria (or the ANOVA plan) that Cluster perm. is now active.
- Close this plan file with "Implemented" date.
- If MNE is added as a dependency, update `pyproject.toml` / `requirements.txt` and note it here.

---

## File Change Summary

| File                                      | Changes                                                                                                                                                                                                                                                                 |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/ui.py`                           | Extend allowed `test_type` list in two guards; add `elif test_type == "Cluster perm.":` block in `_get_stat_test_warning` with between vs. within logic; add to allowed list in `apply_statistical_test_if_active`.                                                     |
| `src/lib/statistics.py`                   | Add `"Cluster perm."` to early `not_implemented` guard; new `if test_type == "Cluster perm.":` branch that calls `mne.stats.permutation_cluster_test` / `permutation_cluster_1samp_test`; lazy import with graceful fallback; implement `_to_matrix` adapter if needed. |
| `docs/plan_v0.16_scitest_CLUSTER_PERM.md` | This file.                                                                                                                                                                                                                                                              |

No changes to `ui_designer.py`, `ui_state_classes.py`, or any Qt .ui files.

Optional (if MNE becomes required): update dependency files.

---

## Open Questions / Future Work

- Full MNE dependency vs. optional: decide whether to add `mne` to the project requirements or keep it optional with a clear error.
- Effect size for cluster tests (e.g., cluster mass, Cohen's d within significant clusters) — add if user requests.
- One-sample cluster test (vs. non-zero reference curve) — deferred.
- Integration with the Heatmap (H) full-range path — deferred (cluster results are scoped to shown test sets).
- Dedicated cluster threshold / n_permutations controls in a sub-panel — deferred (use MNE defaults for v0.16).
- Post-hoc cluster localization with bracket drawing on the graph — deferred.

---

## Success Criteria (for this extension) — NOT YET IMPLEMENTED

- "Cluster perm." radio activates without "not implemented" message.
- Valid between-subjects configuration (≥2 groups, ≥1 shown test set) produces per-testset cluster p-value rows.
- Valid within-subjects configuration (1 group + exactly 2 test sets with matching sweeps) produces a paired-difference cluster result.
- Graph markers and statusbar update correctly (cluster p-values, "(cluster)" label if needed).
- All shared checkboxes (FDR/SW/Levene) continue to work and are logged.
- No breakage to existing t-test / ANOVA / Wilcoxon / Friedman paths.
- MNE-not-installed path produces a clear, actionable error message.
- Manual validation with real test data, edge cases (N<2, wrong group/testset counts, <2 sweeps), FDR toggle all pass.

---

## Heatmap

(See base plan; cluster permutation results feed the same `formal_test_results` → statusbar/marker path. Heatmap (H) toggle remains a separate full-range crude path.)

---

## Assumption Test Statusbar (SW + Levene)

Already wired for all tests via the shared checkbox handlers in `viewSettingsChanged`. The warning coloring on violation (p<0.05) works unchanged. For cluster permutation, SW/Levene are accepted as diagnostics even though the cluster test itself is non-parametric; the statusbar will reflect any flagged violations alongside the cluster p-values.
