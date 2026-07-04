# Plan v0.16.1_IO: Proper IO Regression-Based Statistics (ANCOVA / Slope Comparison)

## Mission Statement

Replace the current nonsensical IO "statistical comparison" (mean amplitude/slope per recording, ignoring stimulus intensity) with scientifically valid regression-based comparisons appropriate for Input-Output (I/O) curves in electrophysiology.

**Current broken behavior (v0.16_n_stats_IO + v0.17_io_statusbar_fix):**

- When `experiment_type == "io"` and no explicit test sets are shown, `compute_statistical_comparison` triggers `use_implicit=True`.
- For ANOVA: runs `f_oneway` on per-group vectors of **mean response (amp/slope) across all sweeps** — collapsing across stimulus intensities.
- For t-test / Wilcoxon / etc.: same collapse to per-recording means.
- r² is computed on **dummy x = `np.arange(len(y))`** (arbitrary recording order), not stimulus intensity.
- Result: p-values and n values that have no meaningful interpretation for IO data; statusbar shows "real" numbers that answer the wrong question.

**Field-standard IO analysis:**

- I/O curves plot stimulus intensity (X) vs response (Y: EPSP amplitude or slope).
- The scientifically relevant question is: **"Do groups differ in their stimulus-response relationship?"**
  - Are regression slopes different? (ANCOVA interaction test)
  - Are intercepts different after slope adjustment?
  - Is r² (goodness of fit) different between groups?
  - Optionally: compare EC₅₀, max response, or other sigmoid parameters.

## Background / Data Model

### IO X/Y Column Mapping (from `uistate.io_input` / `uistate.io_output`)

The UI provides an IO toolframe (`frameToolType_io`) with radio button groups:

- **Input (X-axis)** via `uistate.io_input` (mapped in `ui.py:_RADIO_TO_IO_I`):
  - `vamp` → `volley_amp` (presynaptic volley amplitude)
  - `vslope` → `volley_slope` (presynaptic volley slope)
  - `stim` → `stim` (placeholder, currently disabled in `update_experiment_type_radio_buttons`)

- **Output (Y-axis)** via `uistate.io_output` (mapped in `ui.py:_RADIO_TO_IO_O`):
  - `EPSPamp` → `EPSP_amp` (postsynaptic EPSP amplitude)
  - `EPSPslope` → `EPSP_slope` (postsynaptic EPSP slope)

**Usage sites confirm the mapping** (`ui_plot.py:addRow`, `addGroup`, `updateStimLines`; `ui_interactive.py:_mouseover_output_io`, `_drag_update_io`; `ui_state_classes.py:x_axis_values`):

```python
x_col = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}.get(io_input, "volley_amp")
y_col = {"EPSPamp": "EPSP_amp", "EPSPslope": "EPSP_slope"}.get(io_output, "EPSP_amp")
```

### Accessor and dfoutput Shape

- `dfoutput` contains per-sweep rows with columns including `sweep`, `volley_amp`, `volley_slope`, `EPSP_amp`, `EPSP_slope`, and optionally `stim`.
- In IO mode, each recording has multiple sweeps at increasing stimulus levels.
- The accessor `get_group_testset_means(g, sweeps=None, aspect=col)` currently collapses to a **scalar mean per recording** when `sweeps=None` (see `ui_data_frames.py:670-679`).
- The `per_sweep=True` path returns a wide matrix (rec_ID + one column per sweep) — useful for preserving the X dimension if needed.
- For proper IO regression, we need **per-sweep X,Y pairs** (stim intensity or volley as X, response as Y) per recording or pooled per group.

**Existing r² intent (from plan_v0.16_scitest_IO.md):**

- IO plots already support trendlines (`np.polyfit` in `ui_plot.py:addGroup` / `addRow`).
- r² was planned for display in legend/caption but never computed or stored.
- The v0.17 r² block in `statistics.py:1244-1269` is a workaround that uses dummy x and only runs for implicit IO.

## Phase 0 — Exploration (Mandatory, Read-Only) — COMPLETED

**Findings (recorded after targeted reads of ui_data_frames.py:588-693, statistics.py:182-1286, ui.py:1700-2200, ui_state_classes.py:650-660, analysis_v3.py:769-938, pyproject.toml):**

### 0.1 Accessor behavior

- `get_group_testset_means(..., sweeps=None, per_sweep=False)` (default for implicit IO): returns scalar mean-per-rec (current broken behavior; collapses X dimension).
- `per_sweep=True`: returns **wide matrix** with columns `["rec_ID", "0", "1", "2", ...]` (sweep numbers as **string column names**; preserves identity via column labels). Easy to melt using `pd.melt(id_vars=["rec_ID"], var_name="sweep", value_name="y")`.
- **No new `per_sweep_long=True` mode needed** — we can add `_get_io_xy_pairs` helper in statistics.py that calls with `per_sweep=True` + `aspect=y_col`, then joins X from full `dfoutput` (via new accessor or direct `get_dfoutput` on df_project rows). Sweep order in wide matrix matches dfoutput sweep order (confirmed via get_group_obs_for_sweeps logic).

### 0.2 X column availability

- `dfoutput` (per-rec from `build_dfoutput` in analysis_v3.py) **always** contains `volley_amp`, `volley_slope`, `stim`, `sweep`, `EPSP_amp`, `EPSP_slope` for IO experiments (sweep-mode rows; stim-mode rows have sweep=NaN).
- `ui_state_classes.py:x_axis_values(mode="io")` and multiple plot/interactive sites confirm mapping works; volley columns populated even if stim radio disabled.
- No recordings missing X columns in standard IO workflow (volley_amp/volley_slope computed in every sweep-mode row).

### 0.3 Existing regression

- Only per-waveform (`analysis_v3.py:measureslope_vec`, `analysis_evaluation.py:compute_slope`, `analysis_v1.py`) or dummy r² (current statistics.py:1254-1269 using `np.arange`).
- **No group-level IO curve regression** (ANCOVA/slope-comparison) exists. Perfect for new helper. `statsmodels` is a soft dep (imported lazily for FDR; excluded in slim builds) — we'll implement simple slope test with `scipy.stats.linregress` + manual pooled ANCOVA (F-test on RSS reduced vs full model) to avoid new hard dep.

### 0.4 Checkpoint & Design Decisions

- (a) Melt wide matrix in new `_get_io_xy_pairs(g, y_col, x_col=None, get_dfoutput_fn=None)` helper (no accessor change — minimal diff).
- (b) X always available; fallback to sweep rank (0-based, sorted) if X column missing (rare).
- (c) **Yes** — new IO path must respect `uistate.io_input`/`io_output` (pass via UI or uistate to compute_statistical_comparison; map via same dicts as plot code). Add optional `io_input=None, io_output=None` params to `compute_statistical_comparison`.
- (d) **Option B chosen** (early guard in `compute_statistical_comparison` if `is_io and use_implicit`): minimal call-site impact, reuses `n_unit`, `get_group_testset_means_fn`, config persistence. New private `_compute_io_regression` + `_get_io_xy_pairs`.
- Regression granularity: **per-recording slopes, then aggregate to n_unit level** (subject/slice) for between-group comparison (avoids pseudoreplication; matches current n_unit philosophy). Use pooled regression + interaction for ANCOVA-style slope p-value.
- r² per-group + mean-r² + slope p (primary); simple intercept test if slopes parallel.
- Update plan_v0.16_scitest_IO.md to use this backend for legend r² (future).

**Next:** Proceed to Phase 1 (design + impl). No breaking changes.

## Phase 1 — Design IO-Specific Statistical Entry Point (Minimal, Non-Breaking)

**Constraint:** Do not alter the existing `compute_statistical_comparison` signature or non-IO behavior. Add an IO-aware path or wrapper.

### 1.1 Option A — New function `compute_io_regression_comparison`

- Signature:
  ```python
  def compute_io_regression_comparison(
      shown_groups: list,
      get_group_testset_means_fn: Callable,
      n_unit: str = "subject",
      x_col: str = "stim_intensity",  # or None → infer from sweep order / volley
      y_aspects: list[str] = ("amp", "slope"),
      norm: bool = False,
  ) -> dict:
  ```
- Returns:
  ```python
  {
    "results": [
      {
        "comparison": "slope",           # or "intercept", "r2", "ancova"
        "aspect": "amp",
        "stat": F_or_t,
        "p": pvalue,
        "group_ns": {"G1": n1, "G2": n2},
        "r2_per_group": {"G1": 0.92, "G2": 0.88},
        ...
      },
      ...
    ],
    "config": {"type": "IO regression", "x_col": ..., "n_unit": ...}
  }
  ```
- Uses `scipy.stats.linregress` per group for simple slope/intercept/r².
- For between-group slope comparison: implement a simple ANCOVA-style test (pooled regression + interaction term) or use `pingouin` / `statsmodels` if available.
- Respects `n_unit` by aggregating Y per subject/slice before fitting (or fitting per subject then meta-analyzing slopes).

### 1.2 Option B — Extend `compute_statistical_comparison` with early IO guard

- Keep the existing implicit ANOVA branch for backward compat (statusbar) but add:
  ```python
  if experiment_type == "io" and use_implicit:
      return _compute_io_regression_internal(...)  # new private helper
  ```
- This route reuses the single entry point but requires careful guard ordering (before the current ANOVA implicit branch).

**Decision checkpoint:** Choose A or B based on call-site count and UI wiring effort. Prefer minimal diff.

## Phase 2 — Implement Core Regression Logic (Private Helper)

### 2.1 `_get_io_xy_pairs`

- New private helper (or extend `_get_obs`):
  ```python
  def _get_io_xy_pairs(g, col, x_col=None) -> pd.DataFrame:
      """Return DataFrame with ['rec_ID', 'subject', 'slice', 'x', 'y'] for all sweeps in group.
      If x_col is None, use sweep index as proxy X (ordered by increasing stim).
      """
  ```
- Uses `get_group_testset_means_fn(g, sweeps=None, aspect=col, per_sweep=True)` to get wide matrix, then melts to long (X, Y) form.
- If a real stim intensity column exists in `dfoutput`, join it; otherwise fall back to sweep rank.

### 2.2 Per-group regression

- For each group, aggregate to unit level (subject/slice), then:
  - Fit `linregress(x, y)` → slope, intercept, r², p_slope.
  - Store per-group fit parameters + n (effective after aggregation).
- Compute pooled r² across all groups for comparison.

### 2.3 Between-group comparison

- **Slope test (ANCOVA interaction):** Fit a single model `y ~ x + group + x:group`; test the interaction coefficient.
  - Can be done with `statsmodels.OLS` or a manual F-test on residual sum of squares (reduced vs full model).
- **Intercept test:** After confirming parallel slopes, test group main effect.
- **r² homogeneity:** Optional Fisher's z-transform or bootstrap to compare goodness-of-fit between groups.
- Store results in a shape consumable by `_get_stat_test_warning` (or a new IO-specific formatter).

### 2.4 n_unit handling

- Subject mode: one slope per subject → compare subject slopes between groups (t-test or ANOVA on slopes).
- Slice mode: same at slice granularity.
- Recording mode (default for cluster): per-recording slopes, no further aggregation.

## Phase 3 — UI Integration (Statusbar + Persistence)

### 3.1 Statusbar formatting for IO regression

- Update `_get_stat_test_warning` (ui.py) to detect IO regression results:
  ```python
  if config.get("io_regression"):
      prefix = "IO regression"
      # e.g. "IO regression (Group1 n=5, Group2 n=4): amp slope p=0.012, r2 diff p=0.34"
  ```
- Show: per-group r², slope p-value (ANCOVA), n per group, and a note "(IO: stim vs response)".
- Suppress the old "IO all sweeps" / mean-comparison language.

### 3.2 Persistence

- Store `io_regression_results` and `io_regression_config` under `uistate.formal_test_results` (or a dedicated key).
- Ensure `experiment_type_changed` clears or recomputes when switching to/from IO.
- Same JSON round-trip pattern as existing `formal_test_results`.

### 3.3 Non-goals for v0.16.1

- No new UI widgets or test-type dropdown entries for "IO ANCOVA".
- No sigmoid / nonlinear curve fitting (linear regression only).
- No automatic X-column detection from `dfoutput` beyond a documented fallback.
- No changes to `ui_designer.py`.

### 3.4 Test toolframe refactor: split Test Type vs Test Options (UI wiring)

**Design decision:** When `experiment_type == "io"`, the test-type radios (t-test, ANOVA, Wilcoxon, etc.) are meaningless because IO always uses ANCOVA-style regression. However, `n_unit` (subject/slice/recording) and assumption checkboxes (`fdr`, `sw`, `levene`) remain relevant (or at least harmless) for the IO ANCOVA path.

**Refactor:** Split the existing `frameToolTest` into two sibling frames:

- `frameToolTestType` — contains only the test-type radio buttons (`radioButton_test_t`, `radioButton_test_anova`, `radioButton_test_wilcoxon`, `radioButton_test_friedman`, `radioButton_test_cluster`, `radioButton_test_none`).
- `frameToolTestOptions` — contains `n_unit` radios (`radioButton_test_n_subject`, `radioButton_test_n_slice`, `radioButton_test_n_rec`) plus assumption checkboxes (`checkBox_test_fdr`, `checkBox_test_sw`, `checkBox_test_levene`).

**Wiring requirements (all in `ui.py`):**

1. **New `pushButton_hide_test_options`** (or reuse existing hide pattern):
   - Placed on `frameToolTestOptions` (consistent with `pushButton_hide_test` on `frameToolTestType`).
   - Toggles visibility of `frameToolTestOptions`.
   - Persists state via `uistate.viewTools` (or a dedicated `test_options_visible` flag).

2. **Menu option "Show Test Options"**:
   - Added to the View / Toolbars menu (or a new "Analysis Options" submenu).
   - Calls `self.frameToolTestOptions.setVisible(True)` when triggered.
   - Disabled (grayed out) when `experiment_type == "io"` because `frameToolTestOptions` is the only test-related control visible in IO mode, and hiding it would leave the user with no n_unit control.

3. **Automatic hiding of `frameToolTestType` on IO**:
   - In `experiment_type_changed` (and `update_experiment_type_radio_buttons`):
     ```python
     if exp_type == "io":
         self.frameToolTestType.setVisible(False)
         # also disable any menu action that would show it
         if hasattr(self, "actionShowTestType"):
             self.actionShowTestType.setEnabled(False)
     else:
         # restore previous visibility or default to True
         self.frameToolTestType.setVisible(uistate.viewTools.get("frameToolTestType", True))
         if hasattr(self, "actionShowTestType"):
             self.actionShowTestType.setEnabled(True)
     ```

4. **Menu option "Show Test Type"** (counterpart to #2):
   - Exists for non-IO modes.
   - When `experiment_type == "io"`, this menu entry is disabled (because `frameToolTestType` must remain hidden).

5. **Initial visibility on startup / load**:
   - `frameToolTestType` visible by default for time-course/PP modes.
   - `frameToolTestOptions` visible by default (or respects persisted `uistate.viewTools`).
   - Both frames share the same parent layout container so that hiding `frameToolTestType` does not cause unexpected vertical collapse/expansion.

**IO-specific behavior summary:**

- `frameToolTestType` is **always hidden** when IO is selected (test type is forced to ANCOVA).
- `frameToolTestOptions` remains **visible and functional** (n_unit still applies to ANCOVA aggregation).
- The "Show Test Type" menu action is **disabled** in IO mode.
- The "Show Test Options" menu action remains **enabled** in IO mode (user can still hide/show n_unit controls).

**Naming convention:** `frameToolTestOptions` (preferred) or `frameToolTestParams`. Avoids the ambiguous term "Test params".

### 3.5 Context-aware statusbar for IO (recording selection vs group-level ANCOVA)

**Requirement:** The statusbar must adapt its content based on the current selection context when `experiment_type == "io"`:

- **Single recording selected:** Show that recording's per-recording regression statistics (r², slope, intercept, optionally p-value for the fit) instead of the group-level ANCOVA result.
- **No recording selected (or multiple/group selection):** Show the group-level ANCOVA results (n per group, slope p-value, intercept p-value, per-group r²) as specified in 3.1.

**Rationale:** When a user clicks a single point or recording in an IO scatter, they typically want to inspect that recording's fit quality (r² of its stimulus-response points) rather than the between-group comparison. When nothing is selected, the global group comparison (ANCOVA) is the appropriate summary.

**Implementation notes:**

1. **Detection of "single recording selected":**
   - Reuse existing selection state (`uistate.selected_rec` or equivalent from `ui_interactive.py` / graph click handlers).
   - When `len(selected) == 1` and `experiment_type == "io"`, switch statusbar path.

2. **Per-recording regression data source:**
   - The recording-level scatter + trendline already exists in `ui_plot.py:addRow` (IO branch, L1477+).
   - Compute (or retrieve cached) `linregress(x, y)` for that recording's sweeps using the same `io_input`/`io_output` column mapping.
   - Store per-recording fit results in `dict_rec_labels` (or a lightweight parallel dict) so the statusbar can read `r2`, `slope`, `intercept`, `pval` without re-fitting.

3. **Statusbar formatting (two modes):**
   - **Recording mode** (example):
     ```
     Rec_42 (GroupA): r²=0.94 slope=1.2 intercept=0.3 p=0.001
     ```
   - **Group/ANCOVA mode** (no selection):
     ```
     IO ANCOVA (Group1 n=5, Group2 n=4): slope p=0.012 | intercept p=0.34 | r²(G1=0.91, G2=0.88)
     ```
   - Both modes respect `io_input`/`io_output` labels for the X/Y axis names if space permits.

4. **Fallbacks:**
   - Recording has <2 points → "r²=N/A (insufficient data)".
   - No IO regression computed yet → fall back to existing IO plot label or empty.
   - Multiple recordings selected → treat as "no single selection" and show group ANCOVA.

5. **Integration with existing statusbar machinery:**
   - Extend `_get_stat_test_warning` or add a parallel `_get_io_status_text` helper.
   - Called from `graphRefresh` / selection change handlers so the statusbar updates live when the user clicks a point.

**Non-goals:**

- No new per-recording statistics panel or tooltip (statusbar only).
- No change to the recording-level scatter/trendline rendering (just expose the fit stats for statusbar consumption).

## Phase 4 — Verification

1. Non-IO paths unchanged (explicit test sets, time-course, all test types).
2. IO mode with no test sets:
   - Statusbar shows regression-based p-values + per-group r² (real values, not dummy-x).
   - n values reflect effective units after subject/slice aggregation.
   - r² uses actual stimulus intensity (or documented sweep-rank proxy).
   - Context-aware: single recording selected → shows that recording's r²/slope/intercept; no selection → shows group ANCOVA summary.
3. Edge cases: single group, <2 points per group, missing X column → graceful error + note in statusbar.
4. `py_compile` + import test passes; no new runtime exceptions on existing projects.
5. Manual harness (similar to debug_plan_io_statusbar_v0.16.md Phase 3) confirms correct output shape.

## Summary of Deliverables

- `src/lib/statistics.py`: new `_get_io_xy_pairs` + `_compute_io_regression_internal` (or `compute_io_regression_comparison`); early guard in `compute_statistical_comparison` if Option B chosen.
- `src/lib/ui.py`:
  - Statusbar formatting update in `_get_stat_test_warning` (or new `_get_io_status_text`) for IO regression results + context-aware switch (single recording vs group ANCOVA).
  - `frameToolTestType` / `frameToolTestOptions` split + all wiring (hide buttons, menu actions, `experiment_type_changed` guards, IO-specific disabling).
  - Per-recording fit stats exposed from `addRow` / `dict_rec_labels` for statusbar consumption.
- `work_plans/plan_v0.16.1_IO.md`: this document (kept up to date with findings and decisions).
- Optional: update `plan_v0.16_scitest_IO.md` to reference the regression backend now available for legend r² display.

## Constraints

- **Minimal changes:** Prefer new helpers over refactoring existing non-IO branches. The `frameToolTest` split is an explicit, scoped refactor (two new frame names + ~30 LOC of wiring) rather than a deep layout change.
- **Backward compat 100%:** Existing time-course + explicit test set behavior unchanged. IO mode simply hides `frameToolTestType` and forces ANCOVA.
- **Scientific validity:** Every p-value reported for IO must answer a regression-based question (slope difference, fit quality, etc.).
- **No UI designer changes.** All new frames/actions are created programmatically in `ui.py` (following the existing `frameToolType_io` pattern).
- **Use uv** for any venv / test commands; Python 3.12.

## Open Questions (to resolve in Phase 0)

1. **Accessor shape for X,Y pairs:** Does `get_group_testset_means(..., per_sweep=True)` produce a usable wide matrix that can be melted to long-form (rec_ID, sweep, X=volley_amp, Y=EPSP_amp), or do we need a new `per_sweep_long` mode? (Critical for `_get_io_xy_pairs`.)
2. **Regression granularity:** Should the regression be performed per-recording (then slopes aggregated by subject/slice per `n_unit`), or pooled across all sweeps in a group? The latter treats sweeps as independent (common in IO literature but statistically debated).
3. **Stats library:** Is `pingouin` or `statsmodels` available in the environment (check `pyproject.toml` / `uv.lock`), or must we implement ANCOVA with pure `scipy.stats` + manual F-test on RSS? Prefer minimal new dependencies.
4. **io_input/io_output integration:** The new IO regression path should respect the user's current `uistate.io_input` / `uistate.io_output` selection (vamp→volley_amp, EPSPamp→EPSP_amp, etc.) rather than hard-coding columns.
5. **Menu action naming:** Exact QAction names for "Show Test Type" / "Show Test Options" (match existing "Show/Hide" patterns in the View menu, or use "Analysis Options" submenu?). Confirm no collision with current menu structure.

---

**End of plan.** Next step: spawn exploration subagent or proceed with Phase 0 reads if running solo.
