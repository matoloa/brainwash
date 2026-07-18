# Plan v0.16: Significance Markers for PP (Paired-Pulse) Tests + IO Auto-Hide

## Goal

Apply significance markers (`*`, `**`, `***`, `ns`) and journal brackets (export) to **Paired-Pulse (PP)** formal statistical tests. First enable in live UI (`ui_plot.py::show_test_markers`), then verify in exported PNG (`export_image.py`).

**IO is explicitly out of scope for significance markers.** When `experiment_type == "io"`, the sci-test tool frame is **auto-hidden** and an r-square goodness-of-fit is shown instead. This is the expected electrophysiology convention: IO curves report fit quality (r²) and derived parameters (slope/gain/threshold), not per-test-set significance markers on the curve itself. Significance markers apply to discrete between-condition or paired comparisons (time-course, PP), not to IO stimulus-response relationships.

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

## IO r² Display via Legend (New UX Requirement)

### Background

IO mode shows scatterplots (one color per group) with optional trendlines. The r² goodness-of-fit for each group's IO regression must be visible without cluttering the plot area.

### Design Decision: Legend Integration

**r² is shown as part of the legend entry for each group's trendline, not as a separate text label or on-image annotation.**

**Rationale:**

- Legend entries are the natural place for per-group metadata (name, color, fit statistics).
- Avoids visual clutter and overlap with data/trendlines on the plot.
- Scales cleanly to 4+ groups (inset tables or per-line labels become impractical).
- Matches journal conventions: values belong in legend or caption, not scattered on the figure.
- Implementation is localized to the legend-building code path (both live UI and export).

**Legend label format (example):**

```
● Group A (r² = 0.97) ── (trendline)
● Group B (r² = 0.94) ── (trendline)
```

Or compact variant when n is shown:

```
● Group A (r² = 0.97, n=12)
● Group B (r² = 0.94, n=10)
```

**Trendlines appear as part of the legend entry they represent, not as separate legend lines.** The legend shows the group's scatter symbol + color, optionally appended with the trendline style and r². No additional legend entry is created for the trendline itself.

### Complementary .md Caption (Export)

`build_figure_text_md` (already used for per-panel captions) must emit a structured line for the IO panel:

> **Panel io (EPSP_amp):** Group A: r² = 0.97 (linear fit, n=12); Group B: r² = 0.94 (linear fit, n=10).

This satisfies journals that prefer full statistical detail in the caption.

### Visibility Rules

- r² is shown in the legend whenever `experiment_type == "io"` and a fit has been computed (even if trendlines are toggled off).
- If no fit is possible (<2 points): show `r² = —` or omit the parenthetical.
- Norm/transforms: r² reflects the displayed data (same as the scatter).

### Implementation Touchpoints

- **Live UI** (`ui_plot.py`): Legend is built from `dict_group_labels` / `ax.legend()`. Inject r² into the label string for IO mode.
- **Export** (`export_image.py`): Same injection in `render_publication_figure` legend block (L537-540). No new `ax.text` calls.
- **No new artist storage** required; r² travels with the legend label.

### Architectural Constraint: Separate Trendline Legend Entries

**Current behavior (baked into architecture):** Trendlines are rendered as separate artists (e.g., `Line2D` objects) and appear as distinct entries in the legend, separate from their group's scatter symbol.

**Required fix for v0.16 (or prerequisite):** Before r² can be cleanly appended to a single unified legend entry per group, the existing legend-construction logic must be refactored so that:

1. Each group's scatter + trendline (if enabled) are combined into **one logical legend entry** (single label, single handle or composite handle).
2. The label text for that entry includes the r² (and optionally n) when in IO mode.
3. No duplicate or separate "trendline only" legend entry is generated.

**Approach options (choose one during implementation):**

- **Proxy handle + custom handler map:** Keep the scatter and trendline as separate artists internally, but use `ax.legend(..., handler_map={...})` with a custom `HandlerTuple` or `HandlerLine2D` subclass so they render as a single legend row with one label.
- **Label merging at construction time:** In the code path that populates `dict_group_labels` (or the equivalent list passed to `ax.legend`), detect IO mode and merge the trendline label into the group's primary entry rather than adding a second entry.
- **Post-legend filter:** After `ax.legend()` is called, inspect `ax.get_legend().get_texts()` and `ax.get_legend().get_lines()`, remove or hide the trendline-only entries, and rewrite the remaining labels to include r². (Fragile; prefer one of the above.)

**Files likely involved:** `ui_plot.py` (legend creation in `addGroup`, `update`, `graphRefresh`), `export_image.py` (`render_publication_figure` legend block around L537).

**Risk / scope note:** If this refactoring is non-trivial, the IO r² legend feature may be deferred to a follow-up; the design in this plan remains the target, but v0.16 delivery is gated on solving the separate-entry problem.

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

## Plan (Optimized for Agentic Efficiency v2)

**Assessment of Original Plan**: The plan is already strong in **minimalism** (high reuse of existing PP logic in export_image.py, statistics.py, graphRefresh PP bar handling; IO scoped to auto-hide). Phase 0 is well-identified. However, **agentic efficiency is improved** by:

- Treating Phase 0 as **parallel subagents** (`spawn_subagent` with `explore` type + `best-of-n` skill for x-position options).
- Reducing edits further (~20 LOC total in ui_plot.py; 5 LOC in ui.py for hide logic using confirmed `frameToolTest`).
- Explicit integration of `/check-work` skill and `todo_write` for verification.
- Clearer "Files to Edit", mitigated risks, and agent-parallel workflow to accelerate delivery while minimizing context switching and rework.
- Confirmed via code inspection: `show_test_markers` guard is the main gap (time-course only); `sweeps` align with bar centers; `frameToolTest` is the sci-test widget; export is ready.

### Optimized Phases (Agent-First, Parallel Exploration, <30 LOC Changed)

#### Phase 0: Parallel Agentic Validation (Do First — Zero Code Risk)

Launch in parallel using available tools/skills (this is the key agentic efficiency boost):

- **Subagent (explore type)**: Deep-dive `formal_test_results` for PP (structure, `sweeps` as bar indices [1-4 for aspects], p*amp/p_slope/q*\*/volley keys, norm). Read statistics.py, ui.py:1952 (apply_statistical_test_if_active), ui_plot.py:1477+.
- **Subagent (explore + best-of-n)**: Analyze PP x-positioning (`graphRefresh` L934-1000, addGroup bars/patches in dict_group_show, vs test `sweeps`/mean). Propose/implement 0-2 LOC remap if needed (likely `x = round(float(np.mean(sweeps)))` or patch lookup reuse).
- **Subagent (explore)**: Confirm IO guards in `apply_statistical_test_if_active`, widget for sci-test (`frameToolTest` from bwmain.ui and ui.py wiring for hide buttons/test*type_changed), existing visibility pattern (frameToolType_io, frameToolTest*\* subframes).
- Use `grep`, `read_file`, `todo_write` liberally. Run `check-work` on current state.
- **Outcome**: Precise edit diffs, confirmation that x-alignment works, reduced Phase 1 to guard+visibility swap. Update this plan.md with findings.

**Agentic win**: Parallel subagents + skills cut exploration from sequential 30min to <5min with comprehensive coverage. No blind edits.

#### Phase 1: Live UI (`ui_plot.py::show_test_markers`) — Core Focused Change (~20 LOC)

Update **only** lines ~110-180. Add early after ax1/ax2:

```python
        exp_type = getattr(self.uistate, "experiment_type", "time")
        if exp_type == "io":
            return  # Frame auto-hidden; r² is displayed metric per UX matrix
        # PP support: use checkBox (mirrors export L597-610 and graphRefresh L974+)
```

- Relax `if ax1 is None or ax2 is None:` to `if ax1 is None: return` (supports slope-only).
- Replace `amp_view = bool(getattr(self.uistate, "ampView", lambda: True)())` and `slope_view` with:
  ```python
  amp_v = bool(self.uistate.checkBox.get("EPSP_amp", True) or self.uistate.checkBox.get("volley_amp", True))
  slope_v = bool(self.uistate.checkBox.get("EPSP_slope", True) or self.uistate.checkBox.get("volley_slope", True))
  ```
  Update placements logic to use `amp_v`/`slope_v` and handle PP axes (ax1 for amp/volley_amp, ax2 for slope/volley_slope; high y=0.94 for single, dual as before). is_pp_mode optional for y if needed.
- X: Current mean(sweeps) + single-marker midpoint works (Phase 0 confirmation); optional `if exp_type == "PP": x = round(x)`.
- Rest (p/q extraction L184+, labels, blended transform, dict_test_markers, colors, clear, draw) **100% reused**.
- Call in graphRefresh (~L1104) already handles it.

**Files**: `src/lib/ui_plot.py` only.

#### Phase 2: Export (`export_image.py`) — Verification (0-2 LOC)

- Fully ready for PP (is_pp_mode, per-panel routing L597-610 matches new live logic, PP y-offset L192, brackets, guarded call L588).
- IO path inert due to auto-hide.
- **Action**: Verify with test call to `render_publication_figure` (PP data); add clarifying comment on IO guard if desired. No functional edits.

**Files**: None (verification only).

#### Phase 3: IO Auto-Hide for Sci-Test Frame (`ui.py`)

Add visibility control (reusing exact pattern from `frameToolType_io` and test sub-frames):

In `experiment_type_changed` (after L2911 IO block):

```python
        if hasattr(self, "frameToolTest"):
            self.frameToolTest.setVisible(exp_type != "io")
```

- Mirror in `setupToolBar` (~L3414) and `update_experiment_type_radio_buttons`/`applyConfigStates` for consistency on load/switch.
- This hides the entire `frameToolTest` (radios, FDR, variants, SW/Levene) for IO, preventing confusion. Test controls remain for PP/Time etc.
- No state persistence per-type (deferred).

**Files**: `src/lib/ui.py` (small visibility blocks).

#### Phase 4: Agentic Testing & Validation

- Post-edits: Run `/check-work` skill (spawns verifier for diffs, builds, targeted tests).
- Validate:
  - PP live: markers above bars, respect all checkboxes (EPSP/volley amp/slope), FDR/q\_\*, paired/single, norm.
  - Export: brackets + markers in PNGs for PP panels.
  - Auto-hide: `frameToolTest` hidden on IO select; restored on PP/Time; no formal_test_results for IO.
  - No time-course regression; edge cases (no sweeps, single aspect).
- Update this plan with test outputs/screenshots. Use `todo_write` to mark completion.

### Non-Goals / Out of Scope (Unchanged)

- IO significance markers (r² is the correct metric; sci-test frame auto-hidden).
- New statistical tests.
- Changing test result computation for PP (`compute_statistical_comparison` already agnostic).
- Modifying `ui_designer.py` (per project rule).
- Bracket rendering in live UI (journal-only).
- Persisting per-type test config (nice-to-have; deferred).
- **IO r² + trendline legend integration** (future work; scoped here for clarity but not implemented in v0.16).

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
- r² remains the displayed metric for IO.
- **Legend convention documented**: Trendlines and r² are represented as part of each group's legend entry (not separate legend lines or on-image labels); this is a design specification for future implementation, not delivered in v0.16.
