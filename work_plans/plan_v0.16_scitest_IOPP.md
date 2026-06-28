# Plan v0.16: Significance Markers for IO and PP Tests

## Goal

Apply significance markers (`*`, `**`, `***`, `ns`) (and journal brackets in export) to IO and PP formal statistical tests. First enable in live UI (`ui_plot.py::show_test_markers`), then verify in exported PNG (`export_image.py`). **Optimized for agentic efficiency**: minimal changes via heavy reuse of existing logic (p/q extraction, single-marker paired handling, visibility, x-positioning, storage, transforms).

## Current State (Updated from Code Inspection)

### `ui_plot.py::show_test_markers` (L97-235)

- Works for **time-course** only (early `if ax1 is None or ax2 is None` guard L112; time-centric `ampView`/`slopeView` + fixed ax1/ax2 mapping L162).
- **High reuse**: paired/one-sample (`is_single_marker` L126-131), p/q extraction + labels (L184-202), blended transforms (L214 `transData`+`transAxes`), `dict_test_markers` storage/clear (L115-119, L237), darkmode colors, y-convention (0.94/0.06). `graphRefresh` already calls unconditionally (L1104).

### `export_image.py::_add_significance_markers` (L82-233) + `render_publication_figure` (L274+)

- **Strongly IO/PP-aware already** (~80%): modes (L275 `is_io_mode`/`is_pp_mode`), IO `io_output`→pcol remap (L136-140), PP y-offset (L192-194 `ymax2*0.92`), per-panel routing/visibility (L597-610 exactly mirrors planned UI logic; L278 volley checkbox filter), brackets (L219-231 data-coords), guarded call (L588 `formal_results`).
- PP bar x-logic in `graphRefresh` (L934-961 patches) and export (L511-522) reusable for marker positioning.

### Stats, State & Callers (`statistics.py`, `ui.py:1952`, `ui_plot.py:823`)

- `apply_statistical_test_if_active` + `compute_statistical_comparison` fully support IO/PP (`experiment_type`, `checkBox["EPSP_*"|"volley_*"]`, `io_output`, `test_type`/`variant`/`fdr`/`norm`).
- Results dicts consistent (`sweeps` for x, `p_*`/`q_*`/`*_norm` keys). `get_group_testset_means` agnostic.

### Gaps (Narrowed)

1. `show_test_markers` guard + axis/view mapping (primary ~60 LOC fix).
2. PP x for markers (bars at integer centers; reuse patch lookup).
3. Minor export verification (volley routing, IO single-panel).
4. No live bracket (intentional).

**Insight**: One focused UI edit + verification leverages existing mirrored logic across files. Enables fast, low-risk implementation.

## Plan (Optimized for Agentic Efficiency)

### Optimized Phases (Minimal Changes, High Reuse)

#### Phase 0: Quick Validation (Do First — Low Cost, High Signal)

- Confirm `formal_test_results` structure for IO/PP (via `uistate.formal_test_results` after `apply_statistical_test_if_active`): verify `sweeps` holds stimulus amps (IO) or bar indices (PP), `p_amp`/`p_slope` (or `_norm`/`q_*`) keys present. (Parallel: `grep`/`read_file` on `ui.py:1952`, `statistics.py`, `ui_plot.py:1477`).
- Inspect PP bar x-positions in `graphRefresh` (L934-961, `dict_group_show` patches) vs test-set `sweeps` — if mismatch, add lightweight x-remap (1-2 lines).
- **Agentic win**: Parallel subagents for exploration. No code changes yet.

#### Phase 1: Live UI (`ui_plot.py::show_test_markers`) — Core Focused Change

Update **only** this function (L97-235; ~40-60 LOC added). Keep original signature `def show_test_markers(self, results):`. Infer modes, visibility, axes from `self.uistate` (reuse `checkBox`, `io_output`, `experiment_type`).

**Targeted Edits** (reuse existing p/q extraction, single-marker, placements, storage, transforms, colors):

1. **Mode Detection** (after `ax1/ax2` fetch, before early return):

   ```python
   exp_type = getattr(self.uistate, "experiment_type", "time")
   is_io_mode = exp_type == "io"
   is_pp_mode = exp_type == "PP"
   io_output = getattr(self.uistate, "io_output", None) if is_io_mode else None
   ```
   - Relax guard: `if ax1 is None: return` (ax2 optional for IO/slope-only). Select `target_ax` dynamically per aspect.

2. **Aspect-to-Axis + Visibility Mapping** (replace L162-179):
   - Mirror `render_publication_figure` (L597-610) + `graphRefresh` PP logic (L974-985) + ui.py checkbox handling.
   - Use `uistate.checkBox.get("EPSP_amp", True)`, `get("volley_amp", True)`, etc. (already in file).
   - IO: single `ax1` (amp/slope via `io_output` containing "slope").
   - PP: `EPSP_amp`/`volley_amp` → `ax1` (high y=0.94), `EPSP_slope`/`volley_slope` → `ax2` (high/low per both/single rule).
   - Reuse `placements` list + `is_single_marker` logic (L123-153 unchanged).

3. **X-Positioning** (enhance L134-153 if needed):
   - Current `x = float(np.mean(sweeps))` + paired midpoint works for IO/time.
   - PP: optional `if is_pp_mode: x = round(x)` or lookup from `dict_group_show` patches (reuse pattern from L935-961 / export L511). Validate in Phase 0.

4. **Y-Placement & Rest**:
   - IO: always `0.94` (top) on `ax1`.
   - PP: reuse dual-aspect convention (0.94/0.06).
   - Blended transform, colors (`darkmode`), storage (`dict_test_markers` by `pcol`+`x`), `clear_test_markers` unchanged.
   - Callsite (`graphRefresh` L1104) unchanged.

**Files**: Only `src/lib/ui_plot.py` (one function; minimal).

#### Phase 2: Export (`export_image.py`) — Verification Only (Minimal/No Edits)

- Already ~80% ready: mode detection (L275-282), IO remap (L136-140), per-panel `amp_v`/`slope_v` routing (L599-610, L278 volley filter), PP y-offset (L192-194 `ymax2*0.92`), brackets (L219-231), call guarded by `formal_results` (L588).
- **Tasks** (no structural changes):
  - Confirm IO `io_output="EPSPslope"` routes to `slope_pcols`/`p_slope`.
  - Volley panels hit correct branch (L607-610 uses EPSP checkboxes — acceptable).
  - Bracket collision/span OK (data coords; sweeps correct per Phase 0).
- If tiny gap (volley visibility), add 1-2 lines. Update docstring only.

**Files**: `src/lib/export_image.py` (comments/verification; avoid edits if tests pass).

#### Phase 3: Testing & Validation (Minimal, Reuse Existing)

- **Live UI**: Time-course (no regression); IO (ax1, stim x, high y, io_output); PP (per-aspect panels/checkboxes, bar centers, single/multi-group).
- **Export**: IO (marker+bracket); PP (per-aspect PNGs, above bars).
- **Cross-cutting**: FDR (`q_*`), norm (`*_norm`), Wilcoxon/paired/one-sample (`is_single_marker`), edges (single-aspect, no sweeps).
- **Agentic efficiency**: Post-Phase 1, run `check-work` skill + targeted tests via existing `apply_statistical_test_if_active` + test sets. No new harness.

### Non-Goals / Out of Scope (Unchanged)

- New statistical tests.
- Changing test result computation for IO/PP (`compute_statistical_comparison` already agnostic).
- Modifying `ui_designer.py` (per project rule).
- Bracket rendering in live UI (journal-only).

## Files to Edit

- `src/lib/ui_plot.py` (main: `show_test_markers`; optional x-remap in `graphRefresh`).
- `src/lib/export_image.py` (optional: 0-5 LOC comments/guards).

## Risks / Unknowns (Mitigated by Phase 0)

- **X-semantics**: `sweeps` for IO (stim amps) / PP (indices vs bar centers). Validate first; reuse existing patch lookup from `graphRefresh`/`export` (L935, L511).
- **Axis availability**: IO hides ax2; PP unified y — dynamic `target_ax` + relaxed guard.
- **Volley**: Parallel to EPSP via checkboxes; current routing sufficient.
- Performance/storage: Existing Text artists + clear logic already robust.

## Acceptance Criteria (Unchanged)

- Significance markers visible and correctly placed for IO and PP formal tests in both live UI and exported PNGs.
- No regression for time-course tests.
- Markers respect aspect checkboxes, FDR, norm, and paired/one-sample variants.
- Journal brackets render for IO/PP in export.
