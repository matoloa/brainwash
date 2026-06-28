# Plan v0.16: Significance Markers for IO and PP Tests

## Goal
Apply significance markers (`*`, `**`, `***`, `ns`) to Input/Output (IO) and Paired Pulse (PP) formal statistical tests, first in the live UI (`ui_plot.py`) and then in the exported figure PNG (`export_image.py`).

## Current State

### `ui_plot.py::show_test_markers` (L97-235)
- Works for **time-course** test sets only.
- Uses `uistate.dict_test_markers` to store `Text` artists.
- Detects paired/one-sample via `test_t_variant`/`test_wilcox_variant`.
- Places markers using **blended transforms** (`transData` x, `transAxes` y).
- Y-placement convention:
  - Both aspects: amp at y=0.94 (top), slope at y=0.06 (bottom).
  - Single aspect: high position (0.94).
- Uses `p_amp`/`p_slope` (or `q_*` if FDR) from `results` list of dicts.
- Skips if `ax1`/`ax2` are None (IO/PP guard).

### `export_image.py::_add_significance_markers` (L82-233)
- Already **partially IO/PP aware** via `is_io_mode`/`is_pp_mode`.
- For IO: maps `io_output` → amp/slope semantics (L136-140):
  ```python
  if is_io_mode:
      if io_output and "slope" in io_output.lower():
          amp_pcols, slope_pcols = [], slope_pcols
      else:
          amp_pcols, slope_pcols = amp_pcols, []
  ```
- For PP: vertical offset override (L192-194):
  ```python
  if is_pp_mode:
      y = ymax2 * 0.92
  ```
- Draws sweep-range bracket (underline + end ticks) — absent in `show_test_markers`.
- Uses **data coordinates** (not blended transforms) for y.
- Called from `render_publication_figure` (L612) only when `formal_results` present.
- Panel routing (L599-610): `EPSP_amp`/`EPSP_slope` panels set single-aspect visibility.

### `render_publication_figure` (L274-637)
- Detects modes (L275-276):
  ```python
  is_io_mode = getattr(uistate, "experiment_type", "time") == "io"
  is_pp_mode = getattr(uistate, "experiment_type", "time") == "PP"
  ```
- For IO: `panels_to_render = ["io"]`.
- For PP: `panels_to_render = ["EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]` (filtered by checkboxes).
- Calls `_add_significance_markers` (L612-626) per panel with correct `amp_v`/`slope_v`.

### Statistical Results (`statistics.py`)
- `p_amp`/`p_slope` (or `p_amp_norm`/`p_slope_norm` when `norm=True`).
- `q_amp`/`q_slope` for FDR-adjusted.
- `sweeps` list per result row (used for x-positioning and bracket).
- Works identically for time/IO/PP because `get_group_testset_means` is agnostic.

### UI State
- `uistate.experiment_type` → `"time" | "io" | "PP"`.
- `uistate.io_output` → `"vamp" | "EPSPamp" | "EPSPslope" | "vslope" | "stim"`.
- `uistate.formal_test_results` stores the list of dicts.
- Test markers only shown when `test_type != "None"`.

## Gaps / Why It Doesn't Work Yet for IO/PP in UI

1. **`show_test_markers` early return**: `if ax1 is None or ax2 is None: return` (L112-113). IO/PP use `ax1`/`ax2` as output axes, but they are created; this guard may still pass. However:
   - IO/PP place data on `ax1`/`ax2` with different coordinate semantics (stim amp on x for IO; integer indices on x for PP bars).
   - The blended-transform placement assumes time-course sweep numbers on x.

2. **No IO/PP-specific y placement**: IO single-panel (`io`) and PP multi-panel (`EPSP_amp` vs `volley_amp`) need aspect-to-axis mapping analogous to `render_publication_figure` panel routing.

3. **No sweep-range bracket** in live UI (by design; bracket is journal-export only).

4. **`graphRefresh`** calls `show_test_markers` unconditionally on `formal_test_results` (L1103-1106); this will be a no-op for IO/PP until the function handles those modes.

## Plan

### Phase 1 — Live UI (`ui_plot.py`)

#### 1.1 Extend `show_test_markers` signature and early detection
- Add parameters (or infer from `uistate`):
  - `is_io_mode: bool`
  - `is_pp_mode: bool`
  - `io_output: str | None`
- Detect mode inside the function (same pattern as export):
  ```python
  is_io_mode = getattr(self.uistate, "experiment_type", "time") == "io"
  is_pp_mode = getattr(self.uistate, "experiment_type", "time") == "PP"
  io_out = getattr(self.uistate, "io_output", None) if is_io_mode else None
  ```

#### 1.2 Guard / axis selection
- For IO: target single `ax1` (or whichever hosts the IO plot); `ax2` may be unused or hidden.
- For PP: target `ax1`/`ax2` per aspect (`EPSP_amp` → `ax1`, `EPSP_slope` → `ax2`, volley same pattern).
- Remove or relax the `ax1 is None or ax2 is None` early return; instead check the relevant target axis per panel/aspect.

#### 1.3 Aspect-to-axis mapping for IO/PP
- Mirror the export logic (L599-610) inside `show_test_markers`:
  - If IO single-output: `io_output` containing `"slope"` → slope semantics on `ax1`; else amp semantics on `ax1`.
  - If PP multi-aspect: route `EPSP_amp`/`volley_amp` → high y on `ax1`; `EPSP_slope`/`volley_slope` → high y on `ax2` (or bottom if both).
- Re-use existing `amp_view`/`slope_view` derived from checkboxes:
  ```python
  amp_view = bool(getattr(self.uistate, "checkBox", {}).get("EPSP_amp", True))
  slope_view = bool(getattr(self.uistate, "checkBox", {}).get("EPSP_slope", True))
  ```
  Extend for volley if needed (`volley_amp`, `volley_slope`).

#### 1.4 X-positioning for IO/PP
- For IO: x is **stimulus amplitude** (from `sweeps` list which, in IO context, holds the IO input values).
- For PP: x is **bar index** (integer); center of the bar group for that test set.
- Current mean-of-sweeps logic (L138) works for both if `sweeps` are populated correctly by the test result row. Validate/adjust in caller if IO/PP use different x-scale.

#### 1.5 Y-placement (live UI)
- Keep the existing y_frac convention (0.94 top, 0.06 bottom) for single-aspect vs dual-aspect.
- For IO single-panel: always high (0.94) on `ax1`.
- For PP: same high/low rules, but note that PP bars sit on a discrete integer x-grid; the marker x will land between bars or at bar centers depending on how `sweeps` are coded.

#### 1.6 Color / text style
- Unchanged (white/black for significance, muted gray for `ns`; respects `darkmode`).

#### 1.7 Storage
- Store in `uistate.dict_test_markers` as before (keyed by `pcol` and x).
- `clear_test_markers` already iterates the dict; no change needed.

#### 1.8 Call site (`graphRefresh`)
- No change: it already passes `uistate.formal_test_results`.
- Ensure `apply_statistical_test_if_active` in `ui.py` is callable in IO/PP contexts (it is; `experiment_type` is read-only metadata).

### Phase 2 — Export (`export_image.py`)

#### 2.1 Verify `_add_significance_markers` IO handling
- Current code (L136-140) already collapses to slope-only or amp-only for IO based on `io_output`.
- Confirm that when `io_output` is `"EPSPslope"` or `"vslope"`, the `p_slope` column is used.
- Confirm that `"vamp"` / `"EPSPamp"` route to `p_amp`.

#### 2.2 Verify PP panel routing
- `render_publication_figure` (L278) already filters `panels_to_render` by checkbox for PP aspects.
- Per-panel call to `_add_significance_markers` (L612) sets `amp_v`/`slope_v` correctly for `EPSP_amp`/`EPSP_slope` (L599-606).
- **Gap**: volley panels (`volley_amp`, `volley_slope`) fall into the `else` branch (L607-610) which uses `checkBox["EPSP_amp"]` etc. — this may be acceptable if volley follows the same visibility, but verify.

#### 2.3 PP y-offset
- Current PP offset (L192-194) uses `ymax2 * 0.92`; this places the marker near the top of the current data range.
- Ensure this is above the tallest bar/errorbar for volley and EPSP aspects.

#### 2.4 Bracket rendering
- Already implemented (L219-231). Confirm it doesn't collide with PP bar labels or IO x-tick labels.
- IO x-scale is continuous (stim amps); bracket span should be correct if `sweeps` contains the actual IO input values used in the test set.

#### 2.5 Call in `render_publication_figure`
- Already guarded by `if formal_results:` (L589).
- For IO panel `"io"`, the `amp_v`/`slope_v` logic (L607-610) will use the checkbox values; this is correct when both are visible.
- No structural change required unless new edge cases surface during testing.

### Phase 3 — Testing & Validation

1. **Live UI**:
   - Time-course: no regression.
   - IO (single aspect): markers appear on `ax1` at correct x (stim amp) and y (high).
   - PP (single group, 2 test sets, paired t-test): single centered marker per aspect panel.
   - PP (multi-group, unpaired): per-test-set markers on the relevant aspect panels.

2. **Export PNG**:
   - IO figure: marker present, correct label, bracket spans the tested IO range.
   - PP figure: per-aspect PNGs show correct markers above the corresponding bar groups; volley panels included when checked.

3. **FDR, norm, Wilcoxon**: same paths as time-course; verify q-value usage and norm-suffixed p-keys (`p_amp_norm`).

4. **Edge cases**:
   - IO with only slope selected (`io_output = "EPSPslope"`): `amp_pcols` empty → no marker or slope marker on `ax1`.
   - PP with only `volley_amp` checked: marker only on that panel.
   - Paired one-sample vs ref: single marker (already handled by `is_single_marker`).

### Non-Goals / Out of Scope
- Adding new statistical tests.
- Changing how test results are computed for IO/PP (they already flow through the same `compute_statistical_comparison`).
- Modifying `ui_designer.py` (per project rule).
- Bracket rendering in live UI (journal-only).

## Files to Edit
- `src/lib/ui_plot.py` — extend `show_test_markers`.
- `src/lib/export_image.py` — minor guard / verification in `_add_significance_markers` and `render_publication_figure` (likely none or tiny).

## Risks / Unknowns
- IO/PP x-scale semantics: confirm that `sweeps` in result rows for IO contain the actual stimulus amplitudes (not sweep indices). If not, the caller building `formal_test_results` for IO may need adjustment.
- PP bar positioning: if PP bars are centered at integer x but test-set sweeps are sweep indices, the marker x may need mapping from sweep → bar center. Inspect `get_group_testset_means` usage in IO/PP context.

## Acceptance Criteria
- Significance markers visible and correctly placed for IO and PP formal tests in both live UI and exported PNGs.
- No regression for time-course tests.
- Markers respect aspect checkboxes, FDR, norm, and paired/one-sample variants.
- Journal brackets render for IO/PP in export.
