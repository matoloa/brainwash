# Plan v0.16_n_stats: Apply Subject/Slice hierarchy to statistical tests [L1-XXX]

> **Updated per clarification (2025-06)**: Default `n_unit="subject"` (per statistical_protocol.md: subject is the sole independent experimental unit). Slice/Recording modes assert that slices or recordings are independent observations in the experimental context. Cluster permutation always uses recording-level n (subject/slice aggregation deferred; sets n=rec). Old projects without `subject`/`slice` columns trigger statusbar warning: "<n_unit> not assigned for included recording(s)" (red, with recording-level fallback). UI wiring uses minimal `n_unit_changed` handler + `_RADIO_TO_TEST_N` dicts (no full radio overhaul; follows existing test-panel patterns). Statusbar/results integrate `n_unit` via existing `_get_stat_test_warning` / `_refresh_test_statusbar`.

## Mission Statement

Extend `compute_statistical_comparison` (statistics.py) to honor `n_unit` ("subject" | "slice" | "recording", default **"subject"**) from the `buttonGroup_test_n` UI. Per `statistical_protocol.md`: subject is the sole independent experimental unit (n = unique subjects). "slice" and "recording" assert those levels are independent observations (composite key for slice; pass-through for recording). Current code treats recordings as independent.

- **Input change**: `get_group_testset_means_fn` must surface `subject`/`slice` columns (joined from `df_project`).
- **Core aggregation**: Private `_aggregate_to_unit_level(obs_df, n_unit)`: groupby `subject` (for "subject"), `["subject","slice"]` (for "slice"), or pass-through (recording). Compute mean(value) per unit.
- **n semantics**: `n1`/`n2` = count of unique units after aggregation (subject/slice/recording as asserted).
- **Backward path**: Old projects (missing `subject`/`slice` or all-NaN) → statusbar warning + recording-level fallback. Cluster perm. always forces recording-level.
- **Scope**: `compute_statistical_comparison` + accessor in `ui_data_frames.py` + thin UI wiring in `ui.py`/`ui_state_classes.py`. No `ui_designer.py` edits, no LMM, no radio overhaul. Statusbar uses existing `_get_stat_test_warning` + `_refresh_test_statusbar` machinery.

---

## What Exists Today

### `compute_statistical_comparison` (statistics.py:177–1047)

High-level orchestrator called by UI (`apply_statistical_test_if_active`). For each shown test set:

- Calls `get_group_testset_means_fn(...)` → DataFrame with `rec_ID`, `value` (+ optional `subject`/`slice` after update).
- Computes tests on per-unit vectors (after aggregation by `n_unit`).
- `n1`/`n2` reflect unique units per `n_unit` choice (subject default).
- Results include `n_unit` in `"config"`; statusbar warnings for missing hierarchy or Cluster override.

Accessor in `ui_data_frames.py:631` (`get_group_testset_means`) currently lacks `subject`/`slice` (added in Phase 0 via join on `df_project`). Cluster path forces recording-level n.

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

## Phase 0 — Extend the accessor contract + n_unit param (minimal, non-breaking)

**Goal**: Join `subject`/`slice` columns; add `n_unit: str = "subject"` (default per protocol). Statusbar warning for old projects + recording fallback. Cluster always recording-level.

### 0.1 Update `get_group_testset_means` (ui_data_frames.py ~631)

Current: returns `rec_ID` + `value` (or wide for `per_sweep=True`).

**Change**: After building `out`, do:

```python
df_p = self.get_df_project()
out = out.merge(
    df_p[["ID", "subject", "slice"]].rename(columns={"ID": "rec_ID"}),
    on="rec_ID", how="left"
)
```

(Handles both scalar and per-sweep paths; NaNs for old projects. No signature change.)

### 0.2 Add `n_unit: str = "subject"` to `compute_statistical_comparison`

Updated signature (default = "subject"):

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
    n_unit: str = "subject",  # NEW: "subject" | "slice" | "recording"
) -> dict:
```

- `"subject"` (default): n = unique subjects, aggregate mean per subject.
- `"slice"`: n = unique (subject,slice) pairs (composite key).
- `"recording"`: current behavior (n = recordings).

If chosen columns missing/NaN → statusbar warning `f"{n_unit} not assigned for included recording(s)"` (via returned error or config flag), fallback to recording. Store `"n_unit"` in `"config"`.

### 0.3 Aggregation helper (private, statistics.py)

```python
def _aggregate_to_unit_level(obs_df: pd.DataFrame, n_unit: str = "subject") -> pd.DataFrame:
    """One row per statistical unit. Preserves 'value' mean; drops NaNs."""
    if obs_df.empty or n_unit == "recording" or "value" not in obs_df.columns:
        return obs_df.copy() if not obs_df.empty else obs_df
    if n_unit == "subject":
        group_keys = ["subject"]
    elif n_unit == "slice":
        group_keys = ["subject", "slice"]
    else:
        group_keys = ["subject"]
    if not all(k in obs_df.columns for k in group_keys):
        return obs_df.copy()  # fallback (caller emits warning)
    valid = obs_df[group_keys + ["value"]].dropna()
    if valid.empty:
        return pd.DataFrame({k: [] for k in group_keys} | {"value": []})
    agg = valid.groupby(group_keys, as_index=False)["value"].mean()
    return agg
```

Called after every accessor fetch. Paired tests: intersect on unit key(s) instead of `rec_ID`. Cluster branch: `n_unit = "recording"` (with note in results/config).

---

## Phase 1 — Apply to each test family (t-test, ANOVA, Wilcoxon, Friedman, Cluster)

**Goal**: Use `_aggregate_to_unit_level(obs_df, n_unit)` + unit-aware alignment in every branch. Default `n_unit="subject"`. Cluster always recording-level.

### 1.1 t-test / one-sample / paired branches (~L882–950, after update)

- After `obs1_df = get_group_testset_means_fn(...)` (now has subject/slice):
  - `obs1_df = _aggregate_to_unit_level(obs1_df, n_unit)`
  - Same for `obs2_df`.
- Paired: align/intersect on unit key (`subject` or `["subject","slice"]`) instead of `rec_ID`.
- `n1`/`n2` = len after aggregation (unique units).
- Result shape unchanged; `n_unit` in config for display/statusbar.

### 1.2 ANOVA branch (L907–936, RM omnibus L257–330)

- Between-subjects: aggregate each group to unit level.
- RM-omnibus (1 group, >=2 test sets): aggregate to unit level, align vectors by unit key across test sets. If incomplete overlap → note in results + statusbar ("partial subject overlap").
- Use subject/slice-aligned vectors for `f_oneway`; `eta2` and df reflect unit count.

### 1.3 Friedman branch (L334–411)

- Aggregate each test set to unit level.
- Align k vectors by unit intersection (`min_len` = min unique units across sets).
- `friedmanchisquare` unchanged.

### 1.4 Wilcoxon branch (L608–801)

- Paired: aggregate + align by unit key.
- One-sample: aggregate then test vs `ref`; n = unique units.

### 1.5 Cluster permutation branch (L417–605)

- **Always** force `n_unit = "recording"` (ignore UI choice for this test_type).
- Add note to results/config: "Cluster permutation uses recording-level n (subject/slice deferred)".
- No aggregation on wide per-sweep matrices. If `n_unit != "recording"` in call, override silently with statusbar note.

---

## Phase 2 — UI integration (thin wiring, follows existing patterns)

**Goal**: Wire pre-placed `buttonGroup_test_n` (no `ui_designer.py` edits). Add minimal handler + dicts (no full radio overhaul). Integrate statusbar warnings and `n_unit` display via existing `_get_stat_test_warning` / `_refresh_test_statusbar`.

### 2.1 Wire via `connectUIstate` + test-panel patterns (`ui.py`, `ui_state_classes.py`)

Designer already has (ui_designer.py:752–769): `radioButton_test_n_subject`, `_slice`, `_rec` + `buttonGroup_test_n`.

**Steps** (minimal, consistent with `test_t_variant_changed` etc.):

1. **State default** (`ui_state_classes.py`, near other test keys): `"buttonGroup_test_n": "subject"` (new default).

2. **Mapping dicts** (ui.py, near `_RADIO_TO_TEST_T_VARIANT`):

   ```python
   _RADIO_TO_TEST_N = {
       "radioButton_test_n_subject": "subject",
       "radioButton_test_n_slice": "slice",
       "radioButton_test_n_rec": "recording",
   }
   _TEST_N_TO_RADIO = {v: k for k, v in _RADIO_TO_TEST_N.items()}
   ```

3. **Handler** (`n_unit_changed(self, button)` modeled on `test_t_variant_changed`):
   - Extract `n_unit = self._RADIO_TO_TEST_N.get(button.objectName(), button.text())`
   - `uistate.buttonGroup_test_n = n_unit`
   - `uistate.save_cfg(...)`
   - `self.apply_statistical_test_if_active()`

4. **connectUIstate**: Add wiring for `buttonGroup_test_n.buttonClicked` (disconnect/reconnect pattern, like other test groups).

5. **applyConfigStates**: Add block to set correct radio checked (like test variant/tails):

   ```python
   if hasattr(self, "buttonGroup_test_n"):
       default_n = getattr(uistate, "buttonGroup_test_n", "subject")
       radio_name = self._TEST_N_TO_RADIO.get(default_n, "radioButton_test_n_subject")
       if hasattr(self, radio_name):
           getattr(self, radio_name).setChecked(True)
   ```

6. **No tab-order/visibility changes** needed (radios always visible in `frameToolTest`).

### 2.2 Pass to compute + statusbar integration

In `apply_statistical_test_if_active` call site (`ui.py:~2068`):

```python
n_unit = getattr(uistate, "buttonGroup_test_n", "subject")
comp = stats.compute_statistical_comparison(..., n_unit=n_unit)
```

- Pass `n_unit` through to results/config.
- Enhance `_get_stat_test_warning` to read `comp.get("n_unit")` or error keys and append unit to status (e.g. "t-test (n=5 subjects)" or the hierarchy warning). Use existing red/"warning" state for missing-hierarchy errors.

### 2.3 Aggregation & branch logic (see Phase 1)

All branches now switch on `n_unit` (via helper). Cluster forces recording-level (statusbar note).

### 2.4 Result display / statusbar

- Statusbar (via `_refresh_test_statusbar`): include unit ("n=5 subjects", warning for old projects).
- Console table (`_print_statistical_test_table`): note n semantics.
- `label_test_n` ("n =") can have tooltip explaining modes.

### 2.5 Persistence

- Automatic via `buttonGroup_test_n` in `uistate` + existing machinery (`cfg.pkl`, `get_state`/`set_state`).
- Old configs default to `"subject"` (or guard to recording if no hierarchy columns detected).

### 2.6 Non-goals for Phase 2

- No radio overhaul or dynamic enabling (e.g. disable Subject until hierarchy present).
- No "are you sure" dialogs or extra validation.
- No LMM, no deeper slice hierarchy, no `ui_designer.py` edits.
- Slice uses simple composite-key aggregation.

---

## Detailed Requirements

### 1. Schema / data contract (no change to df_project)

- `get_group_testset_means` gains `subject`/`slice` columns via merge on `rec_ID` (always, for both scalar and per-sweep).
- Aggregation key: `subject` for `"subject"`, `["subject","slice"]` for `"slice"`, none for `"recording"`.
- `n_unit` stored in results `"config"`.

### 2. Backward compatibility (explicit)

- New default `"subject"` (protocol-driven); old projects/configs without hierarchy or `buttonGroup_test_n` → statusbar warning + recording-level fallback (identical numeric results to pre-plan).
- `n1`/`n2` always present/finite; semantics change only with valid hierarchy.
- Existing call sites unchanged (default param).

### 3. Error / edge handling

- Missing hierarchy for chosen `n_unit` → statusbar warning: `"<n_unit> not assigned for included recording(s)"` (red via existing mechanism) + recording fallback.
- Post-aggregation n < minimum (e.g. paired t-test needs >=2 units) → existing NaN/p=NaN pattern.
- Non-overlapping units in RM/Friedman → note in results/statusbar.
- Cluster perm. → always recording-level (override + note), never errors on `n_unit`.
- Low-n or partial data: drop NaNs, preserve existing robustness.

### 4. Persistence

- `buttonGroup_test_n` via existing buttonGroup machinery in `ui_state_classes.py` + `cfg.pkl`.
- Defaults to `"subject"`; old configs handled gracefully in `applyConfigStates`.

### 5. Documentation / comments

- Module-level comment in `statistics.py` referencing `statistical_protocol.md`, this plan, and clarification (subject default, slice/rec uniqueness assertion, cluster override, statusbar warnings).
- Full docstring update for `compute_statistical_comparison` (n_unit semantics, aggregation, defaults).
- Inline comments on aggregator, every test branch, UI wiring, and statusbar integration.
- Update plan.md Verification Steps below.

### 6. Non-goals (explicit)

- No LMM or mixed models.
- No changes to `ttest_per_sweep` (cluster path stays recording-only).
- No full radio-button overhaul (just add one handler + dicts).
- No dynamic radio enabling, no extra dialogs, no `ui_designer.py` edits.
- Slice = simple composite key (no deeper hierarchy yet).
- UI n-display limited to statusbar + console table (no major results panel changes).

---

## Verification Steps (for agent/check-work)

Use `/check-work` or verification subagent after each phase. Key tests:

1. Old project (no `subject`/`slice` columns) + any `n_unit` → statusbar warning ("subject not assigned..."), recording-level fallback, identical p-values/n to pre-plan.
2. New project (3 subjects × 2 recs) + default `n_unit="subject"` → n=3 (not 6), p-values reflect subject-means; statusbar reports unit.
3. `n_unit="slice"` → n = unique (subject,slice) pairs; composite aggregation.
4. `n_unit="recording"` → identical to current codebase (full backward compat).
5. Paired t/Wilcoxon: correct unit-based pairing/alignment; n = unique units with data in both sets.
6. RM-ANOVA/Friedman: unit-aligned vectors; note on incomplete overlap.
7. Cluster perm. (any `n_unit`) → always recording-level n, with statusbar note (no error).
8. Statusbar: hierarchy warning (red), successful reports include unit ("t-test: p=0.034, n=5 subjects"), persists across sessions.
9. `buttonGroup_test_n` wiring: persists via cfg.pkl, `n_unit_changed` triggers re-compute, initial default="subject" radio selected.
10. No `ui_designer.py` changes; all via existing patterns. Existing tests + manual hierarchy projects pass. `n1`/`n2` always sensible.

**Update plan.md + statistical_protocol.md references as needed.**

---

## Summary of Deliverables

| File                                 | Changes                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/statistics.py`              | (1) Add `_aggregate_to_unit_level(obs_df, n_unit)` helper. (2) Add `n_unit: str = "subject"` param to `compute_statistical_comparison`. (3) Call aggregator + unit-aware alignment/pairing in all test branches (t-test, ANOVA, Wilcoxon, Friedman). (4) Cluster branch forces `n_unit="recording"` + note. (5) Store `n_unit` + warnings in `"config"`/`results`. (6) Updated docstring, module comment (protocol + clarifications). |
| `src/lib/ui_data_frames.py`          | Extend `get_group_testset_means` (scalar + per_sweep) to merge `subject`/`slice` from `df_project` (on `rec_ID`). No signature change.                                                                                                                                                                                                                                                                                                |
| `src/lib/ui.py`                      | (1) Add `_RADIO_TO_TEST_N` + reverse dict. (2) Add `n_unit_changed` handler (mirrors `test_t_variant_changed`). (3) Wire in `connectUIstate` + `applyConfigStates` (set default radio to subject). (4) Pass `n_unit=getattr(uistate, "buttonGroup_test_n", "subject")` to compute call. (5) Enhance `_get_stat_test_warning` / statusbar for `n_unit` + hierarchy warnings.                                                           |
| `src/lib/ui_state_classes.py`        | Add `"buttonGroup_test_n": "subject"` default in state dict.                                                                                                                                                                                                                                                                                                                                                                          |
| `work_plans/plan_v0.16_n_stats.md`   | This file (updated with clarifications: subject default, slice/rec assertions, cluster override, statusbar warnings, minimal UI wiring, verification steps).                                                                                                                                                                                                                                                                          |
| `work_plans/statistical_protocol.md` | No change (reference only).                                                                                                                                                                                                                                                                                                                                                                                                           |

**Dependencies**: v0.16_n (hierarchy columns, migration, table display) must be present.

**Risk / migration note**: New default `"subject"` changes behavior for projects with multi-rec subjects (correct per protocol; n decreases, p-values may increase). Old projects/configs get clear statusbar warning + recording fallback (no crash, identical numbers). Users should understand hierarchy before relying on non-recording n. Future: LMM, dynamic radio states, full subject-curve cluster support.

(End of updated plan — ready for implementation. Follow "ask when unclear" and best practices from clarification.)
