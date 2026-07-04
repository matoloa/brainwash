# Plan v0.16: Significance Markers for PP (Paired-Pulse) Tests + IO Auto-Hide

## Goal

Apply significance markers (`*`, `**`, `***`, `ns`) and journal brackets (export) to **Paired-Pulse (PP)** formal statistical tests. First enable in live UI (`ui_plot.py::show_test_markers`), then verify in exported PNG (`export_image.py`).

**IO is explicitly out of scope for significance markers and for this plan's marker work.** When `experiment_type == "io"`, the sci-test tool frame is **auto-hidden** and an r-square goodness-of-fit is shown instead (see companion `plan_v0.16_scitest_IO.md` for r² display implementation). Significance markers apply to discrete between-condition or paired comparisons (time-course, PP), not to IO stimulus-response relationships.

## Auto-Hide Behavior (New UX Requirement)

### Project Type Visibility Matrix

| Project Type          | Sci-Test Frame     | Rationale                                                                                                                                                |
| --------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Time Course**       | ✅ Visible         | Classic repeated-measures; test sets are temporal windows.                                                                                               |
| **Sweep count**       | ✅ Visible         | Same as Time Course semantically (sweep index on x); formal tests apply.                                                                                 |
| **Timestamp**         | ✅ Visible         | Wall-clock time on x; same test-set logic.                                                                                                               |
| **Train**             | ✅ Visible         | Within-train or across-train comparisons are valid paired/unpaired tests.                                                                                |
| **PP (Paired-Pulse)** | ✅ Visible         | Discrete conditions (pulse intervals); paired t-test / Wilcoxon natural.                                                                                 |
| **IO**                | ❌ **Auto-hidden** | IO is a stimulus-response curve; the metric is r² + derived parameters, not per-test-set significance markers. Formal tests are conceptually mismatched. |

### Implementation Notes

- Drive visibility from `experiment_type` (same pattern as `frameToolType_io` at `ui.py:3391-3392`).
- When IO is selected: hide the sci-test frame (prevents user confusion; `formal_test_results` will never be populated).
- When switching back to a compatible type: restore the frame (optionally restore last test config per type).
- This eliminates any need for `show_test_markers` to defensively handle IO; the UI simply never offers the option.

## Current State (Updated from Code Inspection)

### `ui_plot.py::show_test_markers` (L97-235)

- Works for **time-course** only (early `if ax1 is None or ax2 is None` guard L112; time-centric `ampView`/`slopeView` + fixed ax1/ax2 mapping L162).
- **High reuse**: paired/one-sample (`is_single_marker` L126-131), p/q extraction + labels (L184-202), blended transforms (L214 `transData`+`transAxes`), `dict_test_markers` storage/clear (L115-119, L237), darkmode colors, y-convention (0.94/0.06). `graphRefresh` already calls unconditionally (L1104).

### `export_image.py::_add_significance_markers` (L82-233) + `render_publication_figure` (L274+)

- **Strongly PP-aware already** (~80%): modes (L275 `is_io_mode`/`is_pp_mode`), PP y-offset (L192-194 `ymax2*0.92`), per-panel routing/visibility (L597-610 exactly mirrors planned UI logic; L278 volley checkbox filter), brackets (L219-231 data-coords), guarded call (L588 `formal_results`).
- PP bar x-logic in `graphRefresh` (L934-961 patches) and export (L511-522) reusable for marker positioning.
- IO branch (L136-140 `io_output` remap, L280 `panels_to_render=["io"]`) is defensive; will not be exercised because (a) formal tests are disabled for IO and (b) the sci-test frame is auto-hidden.

### Stats, State & Callers (`statistics.py`, `ui.py:1952`, `ui_plot.py:823`)

- `apply_statistical_test_if_active` + `compute_statistical_comparison` fully support PP (`experiment_type`, `checkBox["EPSP_*"|"volley_*"]`, `test_type`/`variant`/`fdr`/`norm`).
- Results dicts consistent (`sweeps` for x, `p_*`/`q_*`/`*_norm` keys). `get_group_testset_means` agnostic.

### Gaps (Narrowed to PP + Auto-Hide)

1. `show_test_markers` guard + axis/view mapping (primary ~40-60 LOC fix).
2. PP x for markers (bars at integer centers; reuse patch lookup from `dict_group_show`).
3. Minor export verification (volley routing, bracket span vs bar labels).
4. Auto-hide sci-test frame for IO (new; `ui.py` or `ui_groups.py`).
5. No live bracket (intentional; journal-only).

**Insight**: One focused UI edit + verification leverages existing mirrored logic across files. Enables fast, low-risk implementation. IO references pruned; auto-hide eliminates defensive code paths.

## Plan (Optimized for Agentic Efficiency)

### Optimized Phases (Minimal Changes, High Reuse)

#### Phase 0: Quick Validation (Do First — Low Cost, High Signal)

- Confirm `formal_test_results` structure for PP (via `uistate.formal_test_results` after `apply_statistical_test_if_active`): verify `sweeps` holds bar indices or interval values, `p_amp`/`p_slope` (or `_norm`/`q_*`) keys present for `EPSP_*` and `volley_*` aspects. (Parallel: `grep`/`read_file` on `ui.py:1952`, `statistics.py`, `ui_plot.py:1477`).
- Inspect PP bar x-positions in `graphRefresh` (L934-961, `dict_group_show` patches) vs test-set `sweeps` — if mismatch, add lightweight x-remap (1-2 lines) or reuse existing patch-center lookup.
- Verify IO path is disabled: confirm `apply_statistical_test_if_active` early-exits or UI hides test-type controls when `experiment_type == "io"`.
- Locate the sci-test frame widget (likely `frameToolType_test` or similar) and the existing `experiment_type` → visibility pattern (cf. `frameToolType_io` at `ui.py:3391`).
- **Agentic win**: Parallel subagents for exploration. No code changes yet.

#### Phase 1: Live UI (`ui_plot.py::show_test_markers`) — Core Focused Change

Update **only** this function (L97-235; ~40-60 LOC added). Keep original signature `def show_test_markers(self, results):`. Infer modes, visibility, axes from `self.uistate` (reuse `checkBox`, `experiment_type`).

**Targeted Edits** (reuse existing p/q extraction, single-marker, placements, storage, transforms, colors):

1. **Mode Detection** (after `ax1/ax2` fetch, before early return):

   ```python
   exp_type = getattr(self.uistate, "experiment_type", "time")
   is_pp_mode = exp_type == "PP"
   # IO is intentionally excluded (auto-hidden + r² shown instead of formal tests)
   if exp_type == "io":
       return  # no markers; r² is the displayed metric
   ```

   - Relax guard: `if ax1 is None: return` (ax2 optional for slope-only). Select `target_ax` dynamically per aspect.

2. **Aspect-to-Axis + Visibility Mapping** (replace L162-179):
   - Mirror `render_publication_figure` (L597-610) + `graphRefresh` PP logic (L974-985) + ui.py checkbox handling.
   - Use `uistate.checkBox.get("EPSP_amp", True)`, `get("volley_amp", True)`, etc. (already in file).
   - PP: `EPSP_amp`/`volley_amp` → `ax1` (high y=0.94), `EPSP_slope`/`volley_slope` → `ax2` (high/low per both/single rule).
   - Reuse `placements` list + `is_single_marker` logic (L123-153 unchanged).

3. **X-Positioning** (enhance L134-153 if needed):
   - Current `x = float(np.mean(sweeps))` + paired midpoint works if `sweeps` encode bar indices.
   - PP: optional `if is_pp_mode: x = round(x)` or lookup from `dict_group_show` patches (reuse pattern from L935-961 / export L511). Validate in Phase 0.

4. **Y-Placement & Rest**:
   - PP: reuse dual-aspect convention (0.94/0.06).
   - Blended transform, colors (`darkmode`), storage (`dict_test_markers` by `pcol`+`x`), `clear_test_markers` unchanged.
   - Callsite (`graphRefresh` L1104) unchanged.

**Files**: Only `src/lib/ui_plot.py` (one function; minimal).

#### Phase 2: Export (`export_image.py`) — Verification Only (Minimal/No Edits)

- Already ~80% ready for PP: mode detection (L275-282), per-panel `amp_v`/`slope_v` routing (L599-610, L278 volley filter), PP y-offset (L192-194 `ymax2*0.92`), brackets (L219-231), call guarded by `formal_results` (L588).
- **Tasks** (no structural changes):
  - Confirm volley panels hit correct branch (L607-610 uses EPSP checkboxes — acceptable if volley visibility mirrors EPSP).
  - Bracket collision/span OK (data coords; sweeps correct per Phase 0).
- IO branch (L136-140, L280) will not be exercised (frame auto-hidden + early-return in `show_test_markers`); consider a comment or early-return guard for clarity.
- If tiny gap (volley visibility), add 1-2 lines. Update docstring only.

**Files**: `src/lib/export_image.py` (comments/verification; avoid edits if tests pass).

#### Phase 3: Auto-Hide Sci-Test Frame (New)

Add visibility logic tied to `experiment_type`:

1. Locate the sci-test frame widget (e.g., `frameToolType_test` or the container holding test-type radios, variant, tails, FDR, etc.).
2. On `experiment_type` change (or initial load via `applyConfigStates` / `update_experiment_type_radio_buttons`):
   - If `io`: hide the frame.
   - Else: show the frame.
3. Pattern already exists for `frameToolType_io` (`ui.py:3391-3392`); replicate for the test frame.
4. Optionally persist last test config per project type (future polish; not required for v0.16).

**Files**: `src/lib/ui.py` (or `ui_groups.py` if grouped with other type-dependent UI). One conditional visibility block.

#### Phase 4: Testing & Validation (Minimal, Reuse Existing)

- **Live UI**: Time-course (no regression); PP (per-aspect panels/checkboxes, bar centers, single/multi-group, `EPSP_*` + `volley_*`).
- **Export**: PP (per-aspect PNGs, above bars, brackets).
- **Auto-hide**: IO hides sci-test frame; switching to Time/PP shows it; no `formal_test_results` possible for IO.
- **Cross-cutting**: FDR (`q_*`), norm (`*_norm`), Wilcoxon/paired/one-sample (`is_single_marker`), edges (single-aspect, no sweeps).
- **Agentic efficiency**: Post-Phase 1+3, run `check-work` skill + targeted tests via existing `apply_statistical_test_if_active` + test sets. No new harness.

### Non-Goals / Out of Scope (Unchanged)

- IO significance markers (r² is the correct metric; sci-test frame auto-hidden). IO r² display is covered in companion `plan_v0.16_scitest_IO.md`.
- New statistical tests.
- Changing test result computation for PP (`compute_statistical_comparison` already agnostic).
- Modifying `ui_designer.py` (per project rule).
- Bracket rendering in live UI (journal-only).
- Persisting per-type test config (nice-to-have; deferred).

## Files to Edit

- `src/lib/ui_plot.py` (main: `show_test_markers`; optional x-remap in `graphRefresh`).
- `src/lib/export_image.py` (optional: 0-5 LOC comments/guards; IO branch can be left as-is or documented).
- `src/lib/ui.py` (auto-hide sci-test frame on IO; visibility pattern replication).

## Risks / Unknowns (Mitigated by Phase 0)

- **PP x-semantics**: `sweeps` for PP (indices vs bar centers). Validate first; reuse existing patch lookup from `graphRefresh`/`export` (L935, L511).
- **Axis availability**: PP unified y — dynamic `target_ax` + relaxed guard.
- **Volley**: Parallel to EPSP via checkboxes; current routing sufficient.
- **Frame widget identity**: Need to confirm the exact container name for the sci-test controls (Phase 0 exploration).
- Performance/storage: Existing Text artists + clear logic already robust.

## Acceptance Criteria

- Significance markers visible and correctly placed for PP formal tests in both live UI and exported PNGs.
- No regression for time-course tests.
- Markers respect aspect checkboxes (`EPSP_amp`/`EPSP_slope`/`volley_amp`/`volley_slope`), FDR, norm, and paired/one-sample variants.
- Journal brackets render for PP in export.
- **IO auto-hide**: Sci-test frame is hidden when IO is selected; shown for all other project types (Time Course, Sweep count, Timestamp, Train, PP). No `formal_test_results` or markers attempted for IO.
- r² remains the displayed metric for IO (implementation per companion plan).
