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

## Phase 1 — Design IO-Specific Statistical Entry Point (Minimal, Non-Breaking) — COMPLETED

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

## Phase 2 — Implement Core Regression Logic (Private Helper) — COMPLETED

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

## Phase 3 — UI Integration (Statusbar + Persistence, Tight Scope per Discussion)

**Reassessment (post-update):** Plan is now tight, executable, and agent-friendly (core stats first, ~40 LOC UI total, explicit deferrals in 3.3.1, `test_type=None` sentinel for IO, resolved questions, risks mitigated). Improvements incorporated: lazy OLS for clean ANCOVA, minimal menu graying (reuse existing action), no viewTools bloat, deferred per-rec statusbar. No further changes needed for v0.16.1. Ready for implementation (statistics.py core first).

### 3.1 Statusbar formatting for IO regression

- Update `_get_stat_test_warning` (ui.py: ~1886 section) to detect `config.get("type") == "IO regression"` (or `io_regression` key).
  ```python
  if config.get("type") == "IO regression":
      prefix = "IO regression"
      # e.g. "IO regression (SAL=5, KETA=4): slope p=0.012 | r²(G1=0.91, G2=0.88)"
  ```
- Show per-group r², primary slope p (ANCOVA interaction), n_report (using group_ns), X/Y labels if space allows.
- Suppress old "IO all sweeps" / dummy r² / mean-comparison language. Reuse existing implicit_testset + group_ns logic where possible.

### 3.2 Persistence & experiment_type_changed

- Reuse `uistate.formal_test_results` + "config" (add `"type": "IO regression", "io_input": ..., "io_output": ..., "n_unit": ...`).
- In `experiment_type_changed` (ui.py:3024+): if switching **to** "io", set `uistate.test_type = "None"` (clears test-type radios/variant frames), trigger `apply_statistical_test_if_active()` for implicit regression.
- Clear/recompute on to/from IO switch (already partially there via `graphRefresh` + `apply...`).
- Same JSON round-trip as existing `formal_test_results` / `statusbar_state`.

### 3.3 Non-goals for v0.16.1 (updated)

- No new UI widgets, test-type dropdown entries, or "IO ANCOVA" radio.
- No sigmoid / nonlinear curve fitting (linear + ANCOVA only).
- No automatic X-column detection beyond documented fallback (use uistate.io_input mapping).
- **No deep viewTools/menu refactor** or new actions. No context-aware per-rec statusbar (group-level only). No changes to ui_designer.py (already done by user).
- No per-recording fit caching in `ui_plot.py:addRow` / `dict_rec_labels`.

### 3.3.1 Future Work / Deferred to v0.16.2+ (full toolframe + context-aware statusbar)

The following enhancements are **explicitly deferred** to keep v0.16.1 scope tight. They add value but are not required for the core scientific deliverable (correct IO regression statistics + statusbar).

**Deferred items:**

1. **New menu actions** ("Show Test Type", "Show Test Options") with dedicated enable/disable logic and `actionShow*` QAction objects.
2. **Dedicated `test_options_visible` key in `uistate.viewTools`** — full persistence round-trip for the Options frame independent of the Test Type frame.
3. **Context-aware statusbar** (single recording selected → show its r²/slope/intercept; group selection or none → show ANCOVA summary). Requires:
   - Per-recording fit caching in `ui_plot.py:addRow` / `dict_rec_labels`.
   - Selection detection via `ui_interactive.py` handlers.
   - Live update on `graphRefresh` / click.
4. **Full viewTools/menu sync** beyond the minimal IO guards (e.g., restoring previous visibility of Test Type on switch back to time-course).

**Justification for deferral:**

- Tight scope delivers the mission (real ANCOVA p-values, r² from actual X, n_unit respected) with ~40 LOC in `ui.py` and zero changes to `ui_plot.py` or `ui_interactive.py`.
- Full polish adds coupling, testing surface, and menu-state complexity that can be tackled once the regression backend is validated.
- The designer already provides the split frames; wiring can be incrementally extended later without breaking the v0.16.1 contract.

**When to pick up:** After v0.16.1 verification passes and user requests the per-recording inspection or menu polish.

### 3.4 Minimal Test Toolframe Wiring for IO (no full refactor)

**Design decision (confirmed):** Test Type frame irrelevant for IO (ANCOVA forced by stats guard). Test Options (n_unit + assumptions) remains relevant and visible. Since designer already provides the split frames + hide button for options, wiring is scoped to visibility guards.

**Wiring (all in ui.py, ~30 LOC total):**

- Extend `experiment_type_changed` and `update_experiment_type_radio_buttons`:
  ```python
  if exp_type == "io":
      uistate.test_type = "None"  # critical: suppresses test_type_changed side-effects
      self.frameToolTestType.setVisible(False)  # or frameToolTest if not split in current build
      # hide dependent variant frames (t-test, ANOVA, wilcoxon, etc.)
      for f in (getattr(self, "frameToolTest_t", None), getattr(self, "frameToolTest_ANOVA", None), ...):
          if f: f.setVisible(False)
      # gray menu actions for Test Type if they exist (reuse existing "Statistical test" action)
      for action in self.menuView.actions() if hasattr(self, "menuView") else []:
          if "Test" in action.text() or "Statistical" in action.text():
              action.setEnabled(False)
      self.frameToolTestOptions.setVisible(True)  # ensure n_unit available
  else:
      # restore non-IO (use viewTools or defaults)
      ...
  ```
- Leverage existing `pushButton_hide_test_options` / `setViewToolVisible` for options toggle.
- Update `setupToolBar` / load_cfg restore to respect IO (hide Test Type by default for IO projects).
- No new `test_options_visible` in viewTools (reuse "frameToolTest" key or add only if strictly needed; minimize persistence changes).

**IO-specific behavior:**

- `frameToolTestType` (or equivalent) **always hidden** in IO.
- `frameToolTestOptions` **visible** (n_unit controls aggregation in regression).
- Menu "Statistical test" / Test Type actions grayed in IO.
- `test_type_changed` effectively bypassed for IO via `test_type=None`.

## Phase 4 — Verification

1. Non-IO paths unchanged (explicit test sets, time-course, all test types, variant frames, menu actions).
2. IO mode (no test sets, implicit):
   - `compute_statistical_comparison` returns regression results (slope p from ANCOVA interaction, per-group r² from linregress, group_ns).
   - Statusbar shows clean "IO regression (G1=5, G2=4): slope p=0.012 | r²=0.91/0.88" (no dummy x, no mean-collapse nonsense).
   - n_unit respected (subject/slice aggregation before per-unit slopes).
   - `experiment_type_changed` to IO sets `test_type=None`, hides Test Type frame + variants, keeps Options visible.
3. Edge cases: <2 points per group/rec, single group, missing X col (fallback to sweep rank), norm=True, fdr=True → graceful (N/A or note in statusbar).
4. `uv run pyright src/lib/*.py`, `python -m pycompile src/lib/statistics.py src/lib/ui.py`, no new exceptions on existing projects.
5. Manual test: load IO project, select groups, switch experiment_type, toggle n_unit, check statusbar vs. plot trendlines. Compare to old dummy r².
6. Update `plan_v0.16_scitest_IO.md` to reference new backend for future legend r².
7. Deferred features (3.3.1) are NOT tested in v0.16.1 (no new menu actions, no per-rec context, no extra viewTools keys).

## Summary of Deliverables (Tight Scope)

- `src/lib/statistics.py`: `_get_io_xy_pairs(g, io_input, io_output, get_group_testset_means_fn)`, `_compute_io_regression_internal(...)` (uses `linregress` per-unit + `statsmodels.api.OLS` for ANCOVA interaction if available; lazy import). Early guard `if experiment_type == "io" and use_implicit: return _compute...`. Compatible output shape for statusbar.
- `src/lib/ui.py`:
  - `experiment_type_changed`: `if exp_type == "io": uistate.test_type = "None"; hide Test Type frame + variants; ensure Options visible; gray menu if present.
  - Minimal update to `_get_stat_test_warning` / statusbar path to handle new "IO regression" config (r², slope p, n_report).
  - No per-rec context-aware (deferred per 3.3.1); no deep viewTools/menu changes; no new menu actions.
- `work_plans/plan_v0.16.1_IO.md`: this document (updated with assessment, tight scoping, risks, "set test_type=None for IO", deferred items in 3.3.1).
- Optional: small update to `plan_v0.16_scitest_IO.md` for legend r² backend.
- No changes to ui_plot.py, ui_interactive.py, ui_data_frames.py (accessor sufficient per Phase 0).

## Constraints (Updated for Tight Scope)

- **Minimal changes:** New private helpers in `statistics.py` only. UI limited to `experiment_type_changed` guards + statusbar formatter (~40 LOC total in ui.py). No viewTools extension, no new menu actions, no per-rec caching. Full toolframe wiring + context-aware statusbar explicitly deferred (see 3.3.1).
- **Backward compat 100%:** Non-IO paths, explicit test sets, all test types, variant frames, menu sync, cfg load/save untouched. IO simply forces `test_type=None`, hides Test Type, uses regression instead of implicit ANOVA/dummy r².
- **Scientific validity:** All IO p-values from regression (slope interaction via OLS or equivalent F-test on RSS; per-group r² from real X). n_unit aggregation before fitting (avoids pseudoreplication).
- **Agentic efficiency:** Core stats first (verify p/r² before UI). Use existing frames (designer already split). Ask user if unclear on menu graying details or OLS vs manual ANCOVA.
- **Use `uv`** for any venv/test commands; Python 3.12. Prefer `search_replace` for edits.
- **Scope boundary:** v0.16.1 delivers correct IO statistics. Polish (per-rec statusbar, new menu actions) is tracked in 3.3.1 for a follow-up phase.

## Resolved Open Questions (from Phase 0 + Exploration + Reassessment)

1. **Accessor:** Wide matrix from `per_sweep=True` works perfectly (melt + join X from dfoutput or sweep rank). No new mode needed.
2. **Granularity:** Per-recording slopes → aggregate/compare at n_unit level (subject/slice). Matches current philosophy and avoids treating sweeps as independent.
3. **Stats library:** `statsmodels` available (lazy import already used for FDR). Use `statsmodels.api.OLS` (with `y ~ x * C(group)`) inside IO guard for clean ANCOVA interaction p-value. Fallback to `linregress` + manual RSS F-test if import fails. No hard dep.
4. **io_input/io_output:** Pass explicitly from uistate (update the single call site in ui.py). Map exactly as in `ui_plot.py:1481` and `ui_state_classes.py:x_axis_values`.
5. **Menu/UI:** Reuse existing "Statistical test" menu action for graying (no new QActions). `test_type=None` sentinel cleanly bypasses `test_type_changed` and variant frames. No viewTools extension.

**Reassessment summary:** Tight scope delivers mission with minimal risk. Core stats (new helpers + guard replacing dummy r²) first; UI guards second. Deferred items (full menu, per-rec statusbar) tracked in 3.3.1. Agentic best practice followed (verify early, ask if unclear on OLS vs manual or exact frame names). No further updates needed.

---

**End of plan.** Phase 1+2 completed (Option B early guard + private helpers in statistics.py only; real X/Y via uistate.io_input + per_sweep melt, linregress + lazy OLS ANCOVA, compatible config, dummy r² removed). Next: Phase 3 (minimal UI in ui.py for statusbar formatting of "IO regression" + test_type=None guard in experiment_type_changed; deferred items in 3.3.1 remain out of scope for v0.16.1).
