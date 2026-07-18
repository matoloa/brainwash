# Plan: IO ANCOVA Statusbar Format Fix (for grok build server)

## Problem Statement

The IO ANCOVA statusbar does not match the required field-standard format per `plan_v0.16.1_IO.md:15-21` and user spec:

**Expected output:**

```
IO ANCOVA (Group 1=4, Group 2=4) EPSP amp / EPSP amp: (results of ANCOVA between selected groups)
```

**Current output (from `_format_io_regression_statusbar`):**

```
IO ANCOVA (slope p=0.123 r²(G1)=0.85 Group 1=4, Group 2=4)
```

**Specific mismatches:**

1. `n_report` (Group 1=4, Group 2=4) is appended **last** instead of immediately after "IO ANCOVA"
2. **X/Y axis labels are missing entirely** — config stores `x_col`/`y_col` (e.g., "EPSP_amp", "volley_amp") but statusbar never renders them
3. No `:` separator before ANCOVA results
4. User wants Y first, then X: `EPSP amp / EPSP amp` (y/x per user: "y and x values, respectively")

## Root Cause Analysis

The statusbar path is correct per `plan.md`:

- `experiment_type_changed` → `apply_statistical_test_if_active` → `_apply_io_regression`
- `_apply_io_regression` calls `compute_statistical_comparison(experiment_type="io")` → `_compute_io_regression_internal`
- Results stored in `uistate.formal_test_results` with `config: {"type": "IO regression", "x_col", "y_col", "group_ns", "slope_p", "r2_per_group"}`
- `_get_statusbar_for_current_state` dispatches to `_format_io_regression_statusbar` when `is_io_mode() or eff=="ANCOVA"`

The formatting function (`_format_io_regression_statusbar`, ui.py:1732) builds `global_notes` in this order:

1. `slope_p` (if present)
2. First `r2_per_group` entry (if present)
3. `n_report` via `group_ns` (if present)

It never consults `cfg.get("x_col")` / `cfg.get("y_col")` and has no human-readable label mapping.

## Design Constraints (from AGENTS.md + plan.md)

- **One source of truth**: `_get_statusbar_for_current_state` → `_format_io_regression_statusbar` (keep pure; state set only by caller `_refresh_test_statusbar`)
- **Salvage, don't rewrite**: `_format_io_regression_statusbar` logic is sound; reorder + add X/Y display
- **No sentinel leakage**: `experiment_type="io"` is the signal; `"ANCOVA"` is UI-only via `_effective_test_type()`
- **Config shape is stable**: `config` already has `x_col`, `y_col`, `io_input`, `io_output`, `group_ns`, `slope_p`, `r2_per_group`
- **Human labels**: Map internal cols (`EPSP_amp`, `volley_amp`, `volley_slope`, `stim`) → display names (`EPSP amp`, `volley amp`, `volley slope`, `stim`)
- **Y first, X second**: Per user: "EPSP amp / EPSP amp [y and x values, respectively]"
- **Minimal diff**: Keep function <40 LOC; no new helpers unless justified

## Proposed Fix (Minimal, Incremental)

**File**: `src/lib/ui.py`, function `_format_io_regression_statusbar` (L1732-1773)

### Change 1: Reorder `global_notes` construction

- Build `n_report` FIRST (from `group_ns` / `cfg.get("group_ns")`)
- Append to `global_notes` immediately after `prefix = "IO ANCOVA"`
- Then add slope_p / r² results
- This matches user's expected: `IO ANCOVA (Group 1=4, Group 2=4) ...`

### Change 2: Insert X/Y label display after n_report

- After n_report, before slope/r² results, add:
  ```python
  x_label = _human_label(cfg.get("x_col", "volley_amp"))
  y_label = _human_label(cfg.get("y_col", "EPSP_amp"))
  global_notes.append(f"{y_label} / {x_label}")
  ```
- Define a small inline map (or reuse existing if any):
  ```python
  label_map = {"EPSP_amp": "EPSP amp", "EPSP_slope": "EPSP slope", "volley_amp": "volley amp", "volley_slope": "volley slope", "stim": "stim"}
  ```
- Result: `IO ANCOVA (Group 1=4, Group 2=4) EPSP amp / EPSP amp ...`

### Change 3: Add `:` separator before ANCOVA results

- After X/Y labels (which are always shown if config present), append `:` only when slope_p or r² results follow
- If no slope_p/r² yet (initial switch), omit `:` and show only the hint
- Ensures: `IO ANCOVA (Group 1=4, Group 2=4) EPSP amp / EPSP amp: slope p=0.123 ...`

### Change 4: Keep r² display but move after X/Y

- Current logic takes first r² entry only (`for g, r2v in cfg.get("r2_per_group", {}).items(): ... break`)
- Keep as-is but it now appears after X/Y labels
- Optionally drop the first-r²-only heuristic if user wants all groups; but spec says "results of ANCOVA between selected groups" which is slope_p primarily

## Trade-offs Considered

| Option                                                                 | Pros                                                                                                            | Cons                                                                       |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Salvage `_format_io_regression_statusbar`** (chosen)                 | Minimal LOC, preserves purity contract, reuses existing `formal`/`cfg` extraction, matches plan.md architecture | Requires careful reordering + label mapping                                |
| Rewrite statusbar from scratch                                         | Could centralize all IO formatting                                                                              | Violates "salvage" guidance, larger diff, risks new bugs in state handling |
| Add `x_label`/`y_label` to config in `_compute_io_regression_internal` | Stats layer owns labels                                                                                         | Unnecessary; config already has `x_col`/`y_col` and UI knows the mapping   |

## Implementation Checklist (for grok build server)

1. **Edit** `src/lib/ui.py:_format_io_regression_statusbar`
   - Insert label_map (dict literal, 1 line)
   - Reorder: n_report first → X/Y labels → slope_p/r²
   - Insert `:` before results when results exist
   - Use `cfg.get("x_col")` / `cfg.get("y_col")` (fallback to "volley_amp"/"EPSP_amp")
2. **Run** `uv run pytest` (targeted to statusbar or IO regression tests if exist)
3. **Manual validation** (per AGENTS.md IO/Stats workflow):
   - Open project with ≥2 groups + sweep data
   - Switch `experiment_type` to IO
   - Verify statusbar: `IO ANCOVA (Group 1=N, Group 2=M) EPSP amp / EPSP amp: slope p=...`
   - Change `io_input` / `io_output` → statusbar X/Y labels update (e.g., `volley slope / EPSP slope`)
   - Check `io_input_changed` / `io_output_changed` trigger `triggerRefresh` → statusbar refresh via existing path
4. **Use** `check-work` skill after edit to verify diff
5. **No changes** to:
   - `statistics.py` (config shape is correct; early IO guard already hoisted)
   - `_get_statusbar_for_current_state` (already dispatches correctly)
   - `_apply_io_regression` (already sets `formal_test_results` + `statusbar_state="info"`)

## Notes for Implementer

- The `config` produced by `_compute_io_regression_internal` (statistics.py:229-241) already includes:
  ```python
  "x_col": x_col,      # e.g., "volley_amp"
  "y_col": y_col,      # e.g., "EPSP_amp"
  "io_input": ...,     # "vamp" | "vslope" | "stim"
  "io_output": ...,    # "EPSPamp" | "EPSPslope"
  ```
- Human label mapping is purely a UI concern; keep it local to `_format_io_regression_statusbar`
- Per user spec, the "results of ANCOVA" (slope p, r²) follow the `:` — current code already extracts these from `cfg`/`formal[0]`
- Edge case: if `group_ns` empty (no valid X/Y pairs), statusbar shows the hint path (`uistate.statusbar_state=None; return "IO regression: select ≥2 groups..."`) — this is correct and unchanged

## Additional Bug: Wrong n Reported in group_ns (Critical for Statusbar)

**Symptom:** With 4 subjects/group (1 slice each), `n_unit="subject"` often reports n=0; `n_unit="slice"`/`"recording"` report n=40+ (way too high). Expected: all modes report n=4 (4 linear regressions per group).

**Root Cause (statistics.py:141):**

```python
# After _get_io_xy_pairs returns (already aggregated to n_unit level via groupby on L102)
x = xy_df["x"].to_numpy(dtype=float)
y = xy_df["y"].to_numpy(dtype=float)
valid = np.isfinite(x) & np.isfinite(y)
group_data[g] = {"x": x[valid], "y": y[valid], "n": int(valid.sum())}  # BUG: counts rows, not units
group_ns[g] = group_data[g]["n"]
```

The `valid.sum()` counts the number of (x,y) pairs after melt+join, which for a typical IO curve (8–10 stimulus levels) is `n_units × n_stim_levels` (e.g., 4 × 10 = 40). For subject mode, if the groupby on L102 produces no rows (hierarchy columns missing or mismatch), n=0.

**Secondary Issue (L104):** After subject/slice aggregation:

```python
long["rec_ID"] = long["subject"]  # placeholder overwrites real rec_ID; harmless for n but confusing
```

**Fix Location:** `_compute_io_regression_internal` (L141) or `_get_io_xy_pairs` return value.

**Correct behavior:**

- `n` = number of **unique units** after aggregation (unique `subject` values for subject mode; unique `(subject,slice)` for slice mode; unique `rec_ID` for recording mode)
- For data with 4 subjects, 1 slice each: `n=4` regardless of `n_unit` (since 1 slice/rec per subject, all modes collapse to the same 4 units)

**Proposed minimal fix (in `_compute_io_regression_internal` after line 141):**

```python
# n = count of unique units, not count of XY pairs
if n_unit == "subject":
    n_unique = xy_df["subject"].nunique() if "subject" in xy_df.columns else len(valid)
elif n_unit == "slice":
    if {"subject", "slice"}.issubset(xy_df.columns):
        n_unique = xy_df[["subject", "slice"]].drop_duplicates().shape[0]
    else:
        n_unique = xy_df["subject"].nunique() if "subject" in xy_df.columns else len(valid)
else:  # recording
    n_unique = xy_df["rec_ID"].nunique() if "rec_ID" in xy_df.columns else len(valid)
group_data[g] = {"x": x[valid], "y": y[valid], "n": int(n_unique)}
group_ns[g] = group_data[g]["n"]
```

Or simpler: count unique units from the aggregated DF keys before extracting x/y arrays. This ensures `group_ns` passed to `config` and `res_row` has correct per-group n for statusbar n_report.

**Impact on plan:** The statusbar format fix (reorder + X/Y labels) depends on correct `group_ns`. This n-bug must be fixed in the same edit pass; otherwise the formatted string will show wrong counts (e.g., `Group 1=40` or `Group 1=0`).

## Validation Target

After fix, with a project containing Group 1 (n=4) and Group 2 (n=4), EPSP amp output vs volley amp input:

```
IO ANCOVA (Group 1=4, Group 2=4) EPSP amp / EPSP amp: slope p=0.042 r²(Group 1)=0.87
```

Or if r² omitted per current first-only heuristic:

```
IO ANCOVA (Group 1=4, Group 2=4) EPSP amp / EPSP amp: slope p=0.042
```

The exact r² inclusion is secondary; the primary fix is **order + X/Y labels + `:` separator**.

---

**Reference files**:

- `plan.md` (current architecture target)
- `plan_v0.16.1_IO.md:15-21` (field-standard IO analysis spec)
- `src/lib/ui.py:1720-1773` (`_get_statusbar_for_current_state`, `_format_io_regression_statusbar`)
- `src/lib/ui.py:1775-1820` (`_apply_io_regression`)
- `src/lib/statistics.py:109-248` (`_compute_io_regression_internal` — produces correct config shape)
- `src/lib/statistics.py:493-506` (early IO guard — already hoisted per AGENTS.md)
