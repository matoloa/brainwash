# Implementation Plan: Add Wilcoxon Signed-Rank Test (v0.16 extension)

## Context

Brainwash v0.16 introduced formal statistical testing on Test Sets (t-test with unpaired/paired/one-sample variants, one-way ANOVA including simplified repeated-measures omnibus). The UI already contains a disabled `radioButton_test_wilcoxon` (see `QtDesigner/bwmain.py: L678` and `retranslateUi: L897`), and the guard in `ui.py: apply_statistical_test_if_active` explicitly rejects any `test_type` not in `("t-test", "ANOVA")`.

**Goal:** Add a non-parametric Wilcoxon signed-rank test option parallel to the existing t-test variants, following the same architecture (early guards, core computation in `statistics.py`, statusbar summary, and graph markers).

**Why Wilcoxon?** Provides a robust alternative when normality assumptions are violated (users can toggle Shapiro-Wilk to diagnose). Complements t-test rather than replacing it; both appear as radio options.

## Scope (MVP)

Implement **Wilcoxon signed-rank** for the use cases already supported by t-test:

1. **Paired (default for Wilcoxon):** 1 group + exactly 2 test sets → compare the two sets within subjects (rec_ID alignment).
2. **One-sample:** 1 group + 1 (or N) test set(s) → compare each set's per-rec means against a reference value (default 0.0).

**Out of scope for this plan (future extension):**

- Between-subjects unpaired Wilcoxon rank-sum (Mann-Whitney U) — different test; would need new variant or separate radio.
- Multi-test-set repeated-measures omnibus (Friedman) — already has a placeholder radio, out of scope.
- Full post-hoc pairwise contrasts with bracket drawing (deferred alongside RM-ANOVA post-hoc).

**Success criteria:**

- Selecting "Wilcoxon" enables the test; statusbar shows concise p-value(s) and optional assumption notes.
- Graph markers ("\*", "**", "\***", "ns") appear on Test Sets for valid configurations.
- Guard messages are clear when prerequisites are not met.
- A dedicated `frameToolTest_Wilcoxon` (or equivalent) is added in `ui_designer.py` for clean variant/tails/ref controls scoped to Wilcoxon signed-rank.

---

## Requirements

### Functional

1. **Test type entry point:** Extend `test_type` to accept `"Wilcoxon"` (or `"wilcoxon"` internally; decide on casing). The radio button `radioButton_test_wilcoxon` must be wired to set `uistate.test_type = "Wilcoxon"`.

2. **Semantics (per-record means, aligned by rec_ID):**
   - Each observation for a test set = average of aspect (amp/slope) over sweeps for one recording (same as t-test / ANOVA).
   - For **paired Wilcoxon:** compare the two vectors of per-recording averages from the two shown test sets, paired by rec_ID intersection.
   - For **one-sample Wilcoxon:** compare the single vector of per-recording averages against `ref` (default 0.0).

3. **Variants to expose (via dedicated `frameToolTest_Wilcoxon`):**
   - "Paired" (default when Wilcoxon selected) → requires 1 group + exactly 2 test sets.
   - "One-sample" → requires 1 group; compares against a ref value shown in the Wilcoxon frame (e.g., `label_test_wilcox_one_sample_value`).

4. **Tails:** A dedicated `frameToolTest_Wilcoxon` provides its own paired/one-sample radios and two-sided/greater/less radios (mirroring the t-test pattern but without an "Unpaired" option). State attributes are Wilcoxon-scoped (e.g., `test_wilcox_variant`, `test_wilcox_tails`). Pass the selected values to `wilcoxon(alternative=...)`.

5. **FDR, SW, Levene:** Reuse the shared checkboxes. FDR applies across test sets per aspect family (BH). SW/Levene remain meaningful (normality/homogeneity diagnostics) even though Wilcoxon itself is non-parametric.

6. **Output:**
   - Statusbar: `Wilcoxon (paired): set 1: amp p=0.031 | slope p=0.12` (or single line for paired using first-set convention, matching t-test paired behavior).
   - For one-sample: include the ref value in the prefix if non-zero, e.g., `Wilcoxon (one-sample vs 0.5): ...`.
   - Graph markers: identical "\*" / "**" / "\***" / "ns" convention using p or q if FDR applied.
   - For paired: single marker centered between the two test sets (same as t-test paired).

7. **Assumption notes (SW/Levene):** Still show when enabled (users may want to see that normality failed, motivating Wilcoxon). Format unchanged.

### Non-Functional

- Keep `compute_statistical_comparison` signature stable; add a new branch inside for `test_type == "Wilcoxon"`.
- `ui_designer.py` will be modified to add `frameToolTest_Wilcoxon` (per user decision to avoid piggy-backing on the t-test frame).
- Preserve existing t-test / ANOVA behavior exactly.
- Use `scipy.stats.wilcoxon` (already a SciPy import dependency).

---

## Parameters (UI State)

Extend or reuse:

- `uistate.test_type`: `"Wilcoxon"` (string).
- `uistate.test_wilcox_variant`: `"paired"` | `"one-sample"` (Wilcoxon-scoped; no "unpaired" option).
- `uistate.test_wilcox_tails`: `"two-sided"` | `"greater"` | `"less"`.
- `uistate.test_fdr`, `uistate.test_sw`, `uistate.test_levene`: shared with other tests.
- `uistate.label_test_wilcox_one_sample_value`: ref value for one-sample path (Wilcoxon-scoped label).

When Wilcoxon is selected:

- `frameToolTest_Wilcoxon.setVisible(True)`; all other test sub-frames hidden.
- The Wilcoxon frame contains only the relevant variant options (paired/one-sample) plus tails and the one-sample ref value.

---

## Implementation Steps

### 1. `src/lib/statistics.py`

- Import `wilcoxon` from `scipy.stats` (add to existing SciPy import line).
- In `compute_statistical_comparison`:
  - Accept `test_type == "Wilcoxon"` (case-insensitive compare or normalize at call site).
  - After the ANOVA RM block and before the t-test tail mapping, add:
    ```python
    if test_type == "Wilcoxon":
        # Wilcoxon path (paired or one-sample only)
        ...
    ```
  - **Paired branch:**
    - Require exactly 1 shown group + exactly 2 shown test sets (mirror paired t-test guard).
    - Align by rec_ID intersection (reuse the same `set1`/`set2`/`common` logic as paired t-test).
    - For each aspect, call `wilcoxon(v1, v2, alternative=alt, zero_method="wilcox", correction=False, ...)` (or modern signature).
    - Store `p_{short}`, `stat_{short}` (the W statistic).
    - Optionally compute an effect size (e.g., rank-biserial correlation) if desired for future; MVP may omit.
  - **One-sample branch:**
    - Require exactly 1 shown group.
    - For each test set, take per-rec values vs `ref`.
    - Call `wilcoxon(vals - ref, alternative=alt, zero_method=..., correction=...)` or the one-sample form if available in the SciPy version.
    - Store per-set results (multiple rows, unlike paired which collapses to first set).
  - Assumption tests (SW, Levene) remain applicable and should run for Wilcoxon results (they diagnose the data regardless of test chosen).
  - FDR path should work unchanged (it operates on the `raw_p_*` lists appended during result construction).
  - Early return for unknown test_type should now list `"Wilcoxon"` alongside `"t-test"` and `"ANOVA"`.

- Consider a small internal helper `_wilcoxon_safe(v1, v2_or_ref, alternative)` that catches edge cases (all zero differences → p=NaN, n<2 → p=NaN) and returns `(stat, p)`.

### 2. `src/lib/ui.py`

- **`apply_statistical_test_if_active`:**
  - Add `"Wilcoxon"` to the allowed set (replace the `not in ("t-test", "ANOVA")` guard with a broader check or explicit list).
  - Variant checks:
    - If variant == "paired": require 1 group + exactly 2 test sets (identical to paired t-test).
    - If variant == "one-sample": require 1 group (any number of test sets ≥1).
    - Reject variant == "unpaired" for Wilcoxon (or map it to an error: "Wilcoxon signed-rank does not support unpaired; use Mann-Whitney outside scope").
  - Snapshot the same config flags (`variant`, `tails`, `fdr`, `norm`, `amp`, `slope`, `ref_value`).
  - Call `stats.compute_statistical_comparison(..., test_type="Wilcoxon", ...)`.

- **`_get_stat_test_warning`:**
  - Accept `"Wilcoxon"` (no "not implemented" warning).
  - Mirror paired t-test guard for Wilcoxon + paired.
  - Mirror one-sample guard for Wilcoxon + one-sample.
  - Build statusbar string with prefix `Wilcoxon (paired)` or `Wilcoxon (one-sample vs X.X)`.
  - For paired, reuse the `results_to_report = results_to_report[:1]` logic so only one marker line appears.
  - SW/Levene notes append identically.

- **Statusbar formatting:** The existing logic for `prefix`, `parts`, and assumption parts should work without modification once `test_type` passes the guard.

- **`_refresh_test_statusbar` and helpers:** No changes needed.

### 3. Graph markers (`src/lib/ui_plot.py`)

- `show_test_markers` already iterates results and places markers based on p/q columns. It should work for Wilcoxon results without changes.
- Paired detection uses `variant == "paired"` (already read from `uistate.test_t_variant`), so Wilcoxon + paired will automatically get the centered single marker.
- Confirm that the placement logic (amp low/slope high when both shown, etc.) is variant-agnostic — it is.

### 4. UI wiring (with `ui_designer.py` edits for the dedicated frame)

- The radio button `radioButton_test_wilcoxon` already exists in the `.ui`/`bwmain.py` generated file.
- In `ui_designer.py`, add a new frame `frameToolTest_Wilcoxon` (modeled on `frameToolTest_t`) containing:
  - `radioButton_test_wilcox_variant_paired` and `radioButton_test_wilcox_variant_one` (button group `buttonGroup_test_wilcox_variant`).
  - `radioButton_test_wilcox_tails_two`, `radioButton_test_wilcox_tails_greater`, `radioButton_test_wilcox_tails_less` (button group `buttonGroup_test_wilcox_tails`).
  - `label_test_wilcox_one_sample_value` (the ref value label, editable or paired with a spinbox if numeric input is desired).
- Somewhere in `ui.py` (likely `test_type_changed` or a `buttonGroup_test` handler) there is logic like:
  ```python
  if self.radioButton_test_t.isChecked():
      uistate.test_type = "t-test"
  elif self.radioButton_test_anova.isChecked():
      uistate.test_type = "ANOVA"
  elif self.radioButton_test_wilcoxon.isChecked():
      uistate.test_type = "Wilcoxon"
  ```
- Add visibility wiring (mirroring ANOVA):
  ```python
  self.frameToolTest_Wilcoxon.setVisible(test_type == "Wilcoxon")
  self.frameToolTest_t.setVisible(test_type == "t-test")
  self.frameToolTest_ANOVA.setVisible(test_type == "ANOVA")
  ```
- Wire handlers for the new Wilcoxon-specific radios to update `uistate.test_wilcox_variant`, `uistate.test_wilcox_tails`, and `uistate.label_test_wilcox_one_sample_value`, then call `apply_statistical_test_if_active()` (or the existing change trigger).
- If there is a mapping from persisted `test_type` string back to radio state (in `applyConfigStates` or `setupToolBar`), add the Wilcoxon case and restore the Wilcoxon frame's radio states.

### 5. State persistence (`src/lib/ui_state_classes.py`)

- `test_type` is likely stored as a free string; no schema change needed.
- Confirm that loading a project with `test_type: "Wilcoxon"` correctly selects the radio on startup.

### 6. Optional: effect size for Wilcoxon (stretch)

If time permits, compute rank-biserial correlation or a simple `r = z / sqrt(N)` approximation and store as `effect_r` or similar in the result row. Display in statusbar analogous to `η²` for ANOVA. Deferrable.

---

## Output in Status Bar (Examples)

**Wilcoxon (paired), 2 aspects, no FDR:**

```
Wilcoxon (paired): amp p=0.031 | slope p=0.12
```

**Wilcoxon (one-sample vs 0), FDR on:**

```
Wilcoxon (one-sample) (FDR): set 1: amp p=0.031 | slope p=0.12 | set 2: amp p=0.005
```

**Wilcoxon (paired) + SW enabled, normality violation:**

```
Wilcoxon (paired): amp p=0.031 | slope p=0.12 | SW ✗ 0.82 (<0.001) | Distribution NOT normal
```

**Invalid config (0 groups):**

```
Create groups to use statistical test   (red/white statusbar)
```

---

## Graph Indicators

- Same visual language as t-test / ANOVA:
  - "\*" p/q < 0.05
  - "\*\*" p/q < 0.01
  - "\*\*\*" p/q < 0.001
  - "ns" otherwise
- Color: white (darkmode) / black (light) for significant; muted gray for "ns".
- Placement follows the same legend-convention rules (amp bottom when both shown, top-right when only one aspect).
- Paired: single marker at midpoint x between the two test sets.

---

## Edge Cases & Error Messages

| Situation                                                       | Message / Behavior                                                                                 |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| test_type="Wilcoxon", variant="unpaired"                        | Warning: "Wilcoxon requires paired or one-sample" (or silently force "paired" with a console note) |
| Wilcoxon + paired, 0 or 1 test set shown                        | "Wilcoxon (paired) requires exactly 1 group and exactly 2 test sets"                               |
| Wilcoxon + paired, 1 group but N<2 recs                         | "Wilcoxon (paired) requires N ≥ 2 recordings"                                                      |
| Wilcoxon + one-sample, 0 groups                                 | "Wilcoxon (one-sample) requires exactly 1 group with data"                                         |
| No shown test sets                                              | "Show at least one test set to run the test"                                                       |
| All differences zero (paired) or all values == ref (one-sample) | `wilcoxon` returns NaN; statusbar shows `p=NA`; marker "ns"                                        |
| n=1 observation                                                 | `wilcoxon` cannot run; guard or result becomes `p=NA`                                              |

---

## Testing & Validation

1. **Syntax/import:** `uv run python -c "from src.lib import statistics, ui; print('ok')"`
2. **Manual flow:**
   - Load a project with ≥1 group, ≥2 recordings, create 2 test sets.
   - Select Wilcoxon + Paired → expect statusbar p-values and one centered marker.
   - Toggle to One-sample → expect per-set markers and ref-aware prefix.
   - Toggle FDR → q-values used for markers, "(FDR)" in prefix.
   - Enable SW → normality diagnostics appear; violations promote statusbar to warning color.
3. **Guard matrix:** 0 groups, 1 group + 1 set (paired), 1 group + 2 sets (paired), 2 groups (paired) → appropriate errors.
4. **No regressions:** t-test and ANOVA continue to work identically.

---

## File Change Summary

| File                                | Changes                                                                                                                                                          |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/statistics.py`             | Import `wilcoxon`; new branch in `compute_statistical_comparison` for Wilcoxon paired/one-sample; reuse FDR/SW/Levene paths.                                     |
| `src/lib/ui.py`                     | Allow `"Wilcoxon"` in guards; variant-specific checks; call compute with `test_type="Wilcoxon"`; statusbar prefix includes variant/ref; frame visibility wiring. |
| `src/lib/ui_state_classes.py`       | Add `test_wilcox_variant`, `test_wilcox_tails`, `label_test_wilcox_one_sample_value` to state (get/set/reset, cfg persistence).                                  |
| `QtDesigner/bwmain.py`              | (Auto-generated; no manual edit. Radio already exists.)                                                                                                          |
| `ui_designer.py`                    | Add `frameToolTest_Wilcoxon` with paired/one-sample variant radios, tails radios, and one-sample ref label (modeled on `frameToolTest_t`).                       |
| `docs/plan_v16_scitest_WILCOXON.md` | This file.                                                                                                                                                       |

---

## Open Questions / Future Work

- Should Wilcoxon expose its own variant radios, or piggy-back on the t-test `frameToolTest_t`? (Current plan: piggy-back.)
- Mann-Whitney U (unpaired non-parametric) — separate radio or a "non-parametric" sub-menu later?
- Full Friedman test for >2 repeated measures (placeholder radio exists).
- Effect size for Wilcoxon (rank-biserial) — include in MVP or defer?
- Console usage logging (`stat_test applied: Wilcoxon variant=paired fdr=...`) — mirror the t-test/ANOVA pattern.

---

_This plan is self-contained and follows the existing v0.16 architecture for statistical tests. Implementation can proceed without altering `ui_designer.py`._
