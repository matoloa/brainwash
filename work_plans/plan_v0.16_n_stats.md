# Plan v0.16_n_stats: Apply Subject/Slice hierarchy to statistical tests [L1-XXX]

> **Update (post-designer change)**: The pre-placed `buttonGroup_test_n` (Subject / Slice / Recording radios inside `frameToolTest`) replaces the generic checkbox/combo sketched in the initial draft. All wiring constraints remain: never edit `ui_designer.py`, use `connectUIstate` + existing buttonGroup persistence. The internal flag is now the tri-state string `n_unit` (default `"recording"`) for full backward compatibility.

## Mission Statement

Extend `compute_statistical_comparison` (statistics.py) to honor the `subject` (animal) column from `df_project` as the **experimental unit defining n**, per `statistical_protocol.md`. Slice is a nested repeated measure. Current implementation treats each recording (`rec_ID`) as an independent observation; the plan defines how to aggregate to subject-level means while preserving backward compatibility and enabling future mixed-effects modeling.

- **Input change**: `get_group_testset_means_fn` or its callers must surface `subject`/`slice` alongside `rec_ID`/`value`.
- **Core aggregation**: For each subject, compute the mean of per-recording observations (within a test set/sweep window) → one value per subject per test set.
- **n semantics**: `n1`/`n2` become counts of **unique subjects** (not recordings).
- **Backward path**: Default to recording-level (current) when `subject` is absent or uniform; opt-in to subject-level via a `use_subject_unit` flag.
- **Scope**: Focus on `compute_statistical_comparison` entry point + `ttest_per_sweep`/`_bh_fdr` consumers. No changes to `ui_designer.py`. Defer full linear mixed models (LMM) and UI n-display updates.

---

## What Exists Today

### `compute_statistical_comparison` (statistics.py:177–1047)

High-level orchestrator called by UI (`apply_statistical_test_if_active`). For each shown test set:

- Calls `get_group_testset_means_fn(group_ID, sweeps, aspect, per_sweep=False)` → returns DataFrame with `rec_ID` + `value` (one row per recording in the group/test-set intersection).
- Computes t-test/ANOVA/Wilcoxon/Friedman/cluster-perm on the vectors of per-recording values.
- Stores `n1`/`n2` as `len(valid_obs)` (count of recordings with finite values).
- Results dict per test set contains `p_*`, `stat_*`, `n1`, `n2`, optional `q_*`, assumption tests.

The accessor `get_group_testset_means_fn` lives in `ui_data_frames.py` (not shown in outline; consumes `df_project`/`df_output` and test-set definitions). It currently returns `rec_ID` but has no `subject`/`slice` columns in its output schema.

### `ttest_per_sweep` (statistics.py:44–174)

Lower-level helper for per-sweep tests (used by cluster and possibly heatmap paths). Accepts aggregated mean/SEM DataFrames or per-observation rows; does not receive `subject` info.

### Data model post-v0.16_n (`df_project`)

- `subject` (str): biological subject/animal ID; defines the experimental unit.
- `slice` (str): nested slice within subject; default `"1"`.
- Migration (`_migrate_hierarchy`) ensures every row has non-null values on load/import (lowest-unique-integer subjects, slice="1").
- Table always displays `subject`/`slice` after `recording_name` (`formatTableLayout`).

### Call sites

UI code (`ui.py`, `analysis_v3.py` wrappers) builds `dd_groups`/`dd_testsets`, resolves shown groups/sets, calls `compute_statistical_comparison(..., get_group_testset_means_fn=..., ...)`. No subject-aware grouping yet.

---

## Phase 0 — Extend the accessor contract (minimal, non-breaking)

**Goal**: Make `subject`/`slice` available to stats without changing existing call signatures or behavior.

### 0.1 Update `get_group_testset_means_fn` return schema (ui_data_frames.py)

Current return (per docstring): DataFrame with at least `rec_ID`, `value`.

Extend to optionally include:

- `subject` (str or object)
- `slice` (str or object)

Implementation: when building the per-group/test-set means DataFrame, left-join `df_project[['rec_ID','subject','slice']]` on `rec_ID`. If columns absent (old projects), they are NaN.

Keep `per_sweep=True` path consistent (adds sweep columns; join still applies).

No signature change; consumers that ignore extra columns continue to work.

### 0.2 Add `use_subject_unit: bool = False` parameter to `compute_statistical_comparison`

Signature update (non-breaking default):

```python
def compute_statistical_comparison(
    groups: list,
    dd_groups: dict,
    dd_testsets: dict,
    get_group_testset_means_fn,
    test_type: str = "t-test",
    variant: str = "unpaired",
    tails: str = "two-sided",
    fdr: bool = False,
    norm: bool = False,
    amp: bool = True,
    slope: bool = True,
    ref: float = 0.0,
    use_subject_unit: bool = False,   # NEW
) -> dict:
```

When `False` (default): existing recording-level behavior unchanged.

When `True`:

- For each `(group, test_set, aspect)` call, after receiving `obs_df` from the accessor:
  - If `subject` column present and non-null: group by `subject`, compute `mean(value)` per subject → replace `obs1`/`obs2` vectors with subject-level means.
  - `eff_n1`/`eff_n2` become `len(unique_subjects_with_valid_mean)`.
  - `n1`/`n2` in result rows reflect subject counts.
- If `subject` missing or all NA for a group/test-set: fall back to recording-level (emit warning once per call? or silent) and keep current n.

Store `use_subject_unit` in the returned `"config"` snapshot.

### 0.3 Aggregation helper (private)

Add inside `compute_statistical_comparison` or as a module helper:

```python
def _aggregate_to_subject_level(obs_df: pd.DataFrame, aspect_col: str) -> pd.DataFrame:
    """Return DataFrame with one row per subject: subject, value (mean over recs)."""
    if obs_df.empty or 'subject' not in obs_df.columns:
        return obs_df  # unchanged; caller treats as recording-level
    valid = obs_df[['subject', 'value']].dropna()
    if valid.empty:
        return pd.DataFrame({'subject': [], 'value': []})
    agg = valid.groupby('subject', as_index=False)['value'].mean()
    return agg  # columns: subject, value
```

Use this in the main loop after each `get_group_testset_means_fn(...)` when `use_subject_unit` is True. For paired paths, align by subject (intersection) instead of rec_ID.

For cluster perm (`per_sweep=True`): subject-level aggregation on the wide matrix is more complex (per-subject mean curve). Defer or implement a simple row-mean per subject if `per_sweep=True` and `use_subject_unit=True`. For MVP, `use_subject_unit` only affects scalar-per-test-set paths; cluster path stays recording-level or errors if both flags set.

---

## Phase 1 — Apply to each test family (t-test, ANOVA, Wilcoxon, Friedman, Cluster)

**Goal**: Ensure each statistical branch correctly uses subject-level n and vectors when `use_subject_unit=True`.

### 1.1 t-test / one-sample / paired branches (around L882–950)

- After fetching `obs1_df`/`obs2_df`, if `use_subject_unit`:
  - `obs1_df = _aggregate_to_subject_level(obs1_df, col)`
  - same for obs2
  - For paired: intersect on `subject` (not rec_ID) to form `v1`/`v2`.
- `eff_n1`/`eff_n2` derived from subject counts after aggregation.
- Result rows retain same shape (`p_*`, `stat_*`, `n1`, `n2`, ...); semantics of n change.

### 1.2 ANOVA branch (L907–936, repeated-measures omnibus L257–330)

- For between-subjects one-way ANOVA (`len(shown_groups) >= 2`): each group's per-test-set values become subject-level means.
- For repeated-measures omnibus (`len(shown_groups)==1`, `>=2` test sets): current code collects per-recording vectors across test sets and runs `f_oneway`. With `use_subject_unit`, the repeated factor becomes subject; we would need subject-aligned vectors (same subjects across test sets). This is the "full subject-aligned RM-ANOVA" noted as deferred in existing comments (L256). For v0.16_n_stats, when `use_subject_unit=True` and repeated-measures ANOVA:
  - If all test sets share a common set of subjects (after aggregation), run `f_oneway` on the subject-aligned vectors (length = unique subjects).
  - Otherwise fall back or emit `anova_note`.
- Effect size (`eta2`) computation stays valid; `df_within` reflects subject count.

### 1.3 Friedman branch (L334–411)

- Similar to RM-ANOVA: requires aligned k vectors of equal length. Subject-level means provide one value per subject per test set. Align by subject intersection; `min_len` becomes min unique subjects across sets.
- Non-parametric; `friedmanchisquare` call unchanged.

### 1.4 Wilcoxon branch (L608–801)

- Paired (`1 group + 2 test sets`): align by subject (not rec_ID) when `use_subject_unit`.
- One-sample: aggregate to subject means, then test vs ref; `eff_n` = unique subjects.

### 1.5 Cluster permutation branch (L417–605)

- **MVP decision**: `use_subject_unit` with `per_sweep=True` (cluster) is **not supported** in this increment; return error or ignore flag and proceed with recording-level matrices.
- Rationale: subject-level mean curves require careful handling of per-subject sweep matrices (different numbers of recs per subject). Deferred to a dedicated cluster-subject plan.
- If user requests both flags, `compute_statistical_comparison` returns `{"error": "use_subject_unit with Cluster perm. not supported; use recording-level or implement subject-curve aggregation", "results": []}`.

---

## Phase 2 — UI integration point (thin wiring)

**Goal**: Wire the pre-placed `buttonGroup_test_n` (Subject / Slice / Recording radios in `frameToolTest`) to drive the unit-of-analysis choice. No designer edits.

### 2.1 Wire `buttonGroup_test_n` via existing `connectUIstate` + `buttonGroup` patterns

The designer already contains (ui_designer.py:752–769):

```python
radioButton_test_n_subject  # objectName
radioButton_test_n_slice
radioButton_test_n_rec
buttonGroup_test_n            # QButtonGroup owning the three radios
```

**Wiring steps** (all in `src/lib/ui.py` and `src/lib/ui_state_classes.py`):

1. **State key (UIstate.reset, ui_state_classes.py)** — add inside the `checkBox` / `viewSettings` dict (near other test-panel toggles):

   ```python
   "buttonGroup_test_n": "recording",   # default = per-recording (backward compat)
   ```

   Value is one of: `"subject"`, `"slice"`, `"recording"`.

2. **Auto-connect the buttonGroup** — `connectUIstate` (the loop at ~3665 that matches `objectName` to `pushButtons`/`checkBox`/`buttonGroup_*`) already handles `QButtonGroup`. The generic handler stores the checked button's `objectName` (minus the `radioButton_test_n_` prefix) under the state key. No extra code if the naming matches the existing pattern used by `buttonGroup_test`, `buttonGroup_type`, etc.

3. **Explicit mapping (optional safety)** — if the generic handler stores full names, add a tiny normalizer in the caller or in `get_state`:

   ```python
   mapping = {"radioButton_test_n_subject": "subject",
              "radioButton_test_n_slice": "slice",
              "radioButton_test_n_rec": "recording"}
   ```

4. **Initial/default selection** — after `setupUi`, or inside `applyConfigStates` / a one-time `QTimer.singleShot`, ensure `radioButton_test_n_rec.setChecked(True)` when the saved state is `"recording"` (or absent). The other two radios start unchecked. This guarantees a defined selection on first launch with old configs.

5. **No tab-order or visibility wiring needed** — radios live inside the always-visible `frameToolTest`; they inherit the parent's layout.

### 2.2 Pass the choice to `compute_statistical_comparison`

- Change the internal flag from boolean `use_subject_unit` to string `n_unit: str = "recording"` (values: `"subject" | "slice" | "recording"`).
- Update signature and docstring accordingly; default `"recording"` yields 100 % identical behavior to pre-plan.
- In the single call site (ui.py) that builds the kwargs for `compute_statistical_comparison`, read the state:

  ```python
  n_unit = uistate.buttonGroup_test_n or "recording"
  ...
  compute_statistical_comparison(..., n_unit=n_unit)
  ```

- Store `n_unit` in the returned `"config"` snapshot for result display.

### 2.3 Aggregation & branch logic (see Phase 1)

- `n_unit == "subject"` → aggregate by `subject` (current `_aggregate_to_subject_level`).
- `n_unit == "slice"` → aggregate by the composite key `(subject, slice)` (or treat each `slice` value as a pseudo-subject within its animal). This is a middle ground between recording and subject; implement a thin variant `_aggregate_to_slice_level` if needed, or reuse the subject aggregator with an extra grouping column.
- `n_unit == "recording"` (default) → pass-through (no aggregation).
- All test-family branches (t-test, ANOVA, Wilcoxon, Friedman) switch on `n_unit`; Cluster path still rejects `"subject"` / `"slice"` (error) and only accepts `"recording"`.

### 2.4 Result display / statusbar

- `n1`/`n2` already shown; the result text can now read e.g. `"n=5 subjects"`, `"n=7 slices"`, or `"n=12 recordings"` based on `config["n_unit"]`.
- Tooltip or small label next to the radios can reuse the existing `label_test_n` ("n =") for clarity.

### 2.5 Persistence

- `buttonGroup_test_n` state is saved automatically via the existing `get_state`/`set_state` + `cfg.pkl` machinery for buttonGroups.
- Old configs without the key default to `"recording"` (explicit guard in `applyConfigStates` or the normalizer).

### 2.6 Non-goals for Phase 2

- No enabling/disabling radios dynamically (e.g., disable Subject until `df_project` has the column).
- No extra validation or "are you sure" dialogs.
- Slice-level aggregation semantics are intentionally simple (composite key or per-slice mean); deeper hierarchical modeling is future work.
- No changes to `ui_designer.py` or `puic`.

---

## Detailed Requirements

### 1. Schema / data contract (no change to df_project)

- `get_group_testset_means_fn` output gains optional `subject`/`slice` columns (joined from `df_project`).
- `subject` is the grouping key for aggregation when `n_unit="subject"`.
- `slice` is informational (future stratification or LMM random effect) and is used when `n_unit="slice"` (composite key); not used for aggregation when `n_unit="recording"`.

### 2. Backward compatibility (explicit)

- Default `n_unit="recording"` → identical behavior and identical numeric results to pre-plan.
- Old projects without `subject` column: accessor returns NaN subjects; aggregation for `"subject"` or `"slice"` falls back to recording-level (no crash).
- `n1`/`n2` remain present and finite; only their interpretation changes with the `n_unit` choice.
- Old configs lacking `buttonGroup_test_n` default to `"recording"` (explicit guard).

### 3. Error / edge handling

- If after subject/slice aggregation a vector has length < required minimum (e.g., 2 for t-test paired, 1 for one-sample), the aspect is skipped or p/stat set to NaN (existing pattern).
- If `n_unit="subject"` but every subject has only one recording (no repeated measures), results are numerically identical to recording-level, but n equals number of subjects.
- Mixed subject presence (some rows have subject, some do not): drop NA-subject rows for aggregation; if zero remain, fall back to recording-level.
- `n_unit="slice"` with no `slice` column or all-NA slices: fall back identically.
- Cluster + `n_unit != "recording"` → explicit error (unsupported).

### 4. Persistence

- `buttonGroup_test_n` state saved via existing buttonGroup / `viewSettings` machinery in `cfg.pkl` (generic handler).
- No project-file schema change.

### 5. Documentation / comments

- Add module-level note in `statistics.py` referencing `statistical_protocol.md` and this plan.
- Docstring for `compute_statistical_comparison` updated with `n_unit: str = "recording"` parameter and n-semantics (Subject / Slice / Recording).
- Inline comments at aggregation site and each test-family branch explaining the conditional.
- Comment the buttonGroup wiring in ui.py / ui_state_classes.py with a pointer to `radioButton_test_n_*` names from the designer.

### 6. Non-goals (explicit)

- No full linear mixed models (LMM) or `statsmodels.mixedlm` / `pymer4` integration.
- No changes to `ttest_per_sweep` signature or implementation for subject aggregation (cluster path only).
- No UI n-count display overhaul beyond the `n_unit`-driven `n1`/`n2` values and optional label.
- No drag-drop or hierarchy-checkbox interaction with stats.
- **No `ui_designer.py` edits** — the radios and `buttonGroup_test_n` are already present; only Python wiring.
- Slice is stored and joined; `"slice"` choice in the buttonGroup triggers a simple composite-key aggregation (no deeper hierarchy yet).

---

## Verification Steps (for agent/check-work)

1. Old project (no subject col) → `n_unit="recording"` (default) → identical p-values/n as before.
2. Old project + `n_unit="subject"` → falls back gracefully (subject NaN) → same numeric results.
3. New project with distinct subjects (e.g., 3 subjects × 2 recs each) → `n_unit="subject"` → n=3 (subjects) not 6; p-value reflects subject-level means.
4. Paired t-test (1 group + 2 test sets): with `n_unit="subject"`, pairing by subject yields correct within-subject contrast; n = unique subjects with both test sets.
5. ANOVA / Friedman repeated-measures omnibus: subject-aligned vectors used when `n_unit="subject"`; falls back or notes when subjects do not fully overlap.
6. Cluster perm + `n_unit != "recording"` → returns explicit error (unsupported combo).
7. `buttonGroup_test_n` selection persists across sessions via cfg.pkl; results panel reflects chosen unit ("n = X subjects", "n = Y slices", or "n = Z recordings") in n values and optional label.
8. Existing tests (`test_parse.py`, stats smoke) pass; new paths covered by manual verification.
9. No `ui_designer.py` touched; all wiring via `connectUIstate`, generic buttonGroup handler, `viewSettings`.

---

## Summary of Deliverables

| File                                 | Changes                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/statistics.py`              | (1) Change parameter to `n_unit: str = "recording"` (values `"subject"                                                                                                                                                                                                                                                                                                                                                 | "slice" | "recording"`). (2) Private `_aggregate_to_subject_level`(+ thin slice-level variant or composite-key reuse). (3) Conditional aggregation + subject-/slice-aware intersection in each test branch (t-test, ANOVA, Wilcoxon, Friedman). (4) Cluster path rejects`n_unit != "recording"`. (5) Store `n_unit`in`"config"`. (6) Updated docstring + protocol reference comment. |
| `src/lib/ui_data_frames.py`          | (1) Extend `get_group_testset_means_fn` (and per_sweep variant) to left-join `subject`/`slice` from `df_project` onto returned means DataFrame. No signature change.                                                                                                                                                                                                                                                   |
| `src/lib/ui.py`                      | (1) Wire `buttonGroup_test_n` (radios `radioButton_test_n_subject`/`_slice`/`_rec`) via existing `connectUIstate` + generic buttonGroup handler. (2) Pass `n_unit=...` (from `uistate.buttonGroup_test_n`) into the `compute_statistical_comparison` call site. (3) Ensure default `radioButton_test_n_rec.setChecked(True)` on first launch / missing config. (4) Optional: surface unit label in result/status text. |
| `src/lib/ui_state_classes.py`        | (1) Add `"buttonGroup_test_n": "recording"` default so it is persisted via `get_state`/`set_state`.                                                                                                                                                                                                                                                                                                                    |
| `work_plans/plan_v0.16_n_stats.md`   | This file (updated to integrate the concrete `buttonGroup_test_n` widget from ui_designer.py).                                                                                                                                                                                                                                                                                                                         |
| `work_plans/statistical_protocol.md` | No change (reference only).                                                                                                                                                                                                                                                                                                                                                                                            |

**Dependencies**: v0.16_n (subject/slice in `df_project`, migration, table visibility) must be merged/present.

**Risk / migration note**: The default `n_unit="recording"` yields identical behavior to pre-plan, so existing analyses are unaffected. Choosing `"subject"` or `"slice"` changes the effective sample size and thus p-values for any dataset where animals have multiple recordings or slices. Users should understand the statistical model before selecting a non-recording unit. Future work will add LMM options and UI warnings for low n after aggregation.

(End of plan — ready for implementation on a feature branch after v0.16_n.)
