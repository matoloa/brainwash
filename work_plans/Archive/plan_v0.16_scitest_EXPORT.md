# Plan: v0.16_scitest_EXPORT — Significance Markers on Exported Journal Images

## Objective

Extend the journal figure export pipeline (`triggerExportOutputImage` → `render_publication_figure`) to include significance markers (`*`, `**`, `***`, `ns`) on the exported images, using the same formal statistical test results that are already computed and displayed on the interactive plot.

## Background

### Current State (v0.16)

- **Statistical testing layer**: `src/lib/statistics.py::compute_statistical_comparison()` performs t-test, ANOVA, Wilcoxon, Friedman, and Cluster permutation tests on Test Sets. Results are stored per-aspect (`p_amp`, `p_slope`, optionally `q_amp`/`q_slope` when FDR is enabled).

- **Interactive display**: `src/lib/ui.py::apply_statistical_test_if_active()` calls the comparator, stores results in `uistate.formal_test_results`, and delegates rendering to `uiplot.show_test_markers(results)`.

- **Marker rendering (interactive)**: `src/lib/ui_plot.py::show_test_markers()` draws text markers on `ax1`/`ax2`:
  - Uses `uistate.dict_test_markers` for storage.
  - Places amp markers on `ax1` (bottom when both aspects shown; top-right when only amp).
  - Places slope markers on `ax2` (top when both; top-right when only slope).
  - For paired/one-sample variants: single marker centered horizontally between the two test sets.
  - Significance thresholds: `<0.001` → `***`, `<0.01` → `**`, `<0.05` → `*`, else `ns`.
  - Uses q-value if present and finite, else raw p-value.
  - Color: high-contrast (white/black) for significant; muted gray for `ns`; adapts to darkmode.
  - **Sweep range indication (interactive)**: The interactive view uses a shaded rectangular background patch on `ax1`/`ax2` to highlight the sweeps included in each test set. The marker (`*` etc.) is placed at the centroid (mean) of that range; no bracket or underline is drawn in the interactive view.

- **Export pipeline**:
  - `src/lib/export_data.py::ExportMixin::triggerExportOutputImage(template_key)` gathers visible groups, resolves a `JournalTemplate`, calls `export_image.render_publication_figure(...)`, and saves each panel PNG to `Export/`.
  - `src/lib/export_image.py::render_publication_figure(uistate, uiplot, template, selected_groups, group_names)` creates fresh `Figure`/`Axes` per panel (`amp`, `slope`, `event`, `mean`, `io`, or PP aspects), replots group means/errorbars/bars from `uistate.dict_group_labels`, applies journal typography and dimensions, optionally adds inset, and returns a dict of figures.

### Gap

`render_publication_figure()` has access to `uistate` (which may contain `formal_test_results` and `dict_test_markers`) but currently **ignores statistical test results**. Consequently, exported journal figures lack the significance markers that users see and rely on in the interactive view.

## Scope

Implement significance marker placement on exported images for all exportable panel types that can carry statistical annotations:

- Time-series panels: `amp`, `slope` (standard experiment_type).
- IO panel: `io` (single panel covering chosen input→output).
- PP (paired-pulse) panels: `EPSP_amp`, `EPSP_slope`, `volley_amp`, `volley_slope` (barplots).
- Exclude `event`/`mean` panels (no current test-set mapping).

Markers must respect:

- The currently selected journal template (font sizes, figure scale).
- Whether FDR was applied (prefer q over p).
- Paired/one-sample vs. unpaired layout rules (single centered marker vs. per-set markers).
- Visibility toggles (`checkBox['EPSP_amp']`, `checkBox['EPSP_slope']`, `ampView`/`slopeView`).
- **Sweep-range bracket**: first/last sweep from the `sweeps` list must be rendered as a horizontal bracket/underline (journal convention); the interactive shaded patch is not reproduced.
- Color on export: black/medium-gray on white background (never white text).

## Design

### 1. Data Contract

- `uistate.formal_test_results` (list[dict] | None): each dict has keys `set_id`, `set_name`, `sweeps`, plus `p_amp`/`p_slope` (and optionally `q_amp`/`q_slope`), `sw_*` normality diagnostics, etc.
- `uistate.test_type`, `uistate.test_t_variant`/`test_wilcox_variant`, `uistate.test_fdr`, `uistate.darkmode`, `uistate.checkBox`, `uistate.ampView`/`slopeView` remain the source of truth for configuration.
- The export function must **not** mutate `uistate` or `uiplot`.

### 2. Placement Logic (re-use/adapt from `show_test_markers`)

- Compute `x` per result as `mean(sweeps)`; for paired/one-sample override to midpoint between first and second set (process only result[0]).
- **Sweep-range bracket (journal convention)**: The interactive shaded background patch is **not** reproduced. Instead, draw a horizontal bracket (or underline with short vertical end-ticks) spanning `min(sweeps)` to `max(sweeps)` for each test-set result. First/last sweep values are directly accessible from the `sweeps` list in each result dict. The bracket sits at the marker y-position (or 1–2 pt below for underline style).
- Determine placements per aspect visibility:
  - Both aspects visible → amp bottom (y_frac≈0.06, va=bottom on ax), slope top (y_frac≈0.94, va=top on ax).
  - Only amp → top-right on amp ax.
  - Only slope → top-right on slope ax.
- PP mode: markers placed above each bar group (or centered if paired). Use the same x-tick mapping already built for PP bar labeling; bracket may span a multi-bar test-set group.
- IO mode: single panel; treat `io_output` to decide amp vs. slope semantics and apply analogous y placement.

### 3. Journal Styling

- Font family/size inherit from `template.font_*`.
- Marker `fontsize`: scale from `template.font_size_axis_label` (≈1.5–1.8×), clamped to 7–10 pt for 1-col templates and 8–11 pt for 2-col; keep bold.
- **Color (journal export on white/light background)**: All six journal templates (`jneurosci_*`, `jphysiol_*`, `nature_*`) render on a forced white background (`"figure.facecolor": "white"` in rc_params). Therefore `dark` must be treated as `False` for export: significant markers use **black** (or the template's primary text color); `ns` uses a **medium gray** (e.g., `#555555`). White text is never used on export figures.
- Bracket/underline line width: `template.linewidth_axes` or slightly thicker (e.g., 0.75 pt).
- No background box or edge around markers; bare text + bracket (consistent with interactive style but adapted for print).
- For multi-panel vertical layouts, each panel figure is independent; markers and brackets are drawn on their respective axes.

### 4. API Sketch (illustrative; final names in implementation)

```python
# Inside render_publication_figure, after the existing per-panel loop body:

if getattr(uistate, "formal_test_results", None):
    _add_significance_markers(
        ax=ax,
        panel=panel,
        template=template,
        results=uistate.formal_test_results,
        is_pp_mode=is_pp_mode,
        is_io_mode=is_io_mode,
        io_output=getattr(uistate, "io_output", None),
        amp_view=bool(getattr(uistate, "checkBox", {}).get("EPSP_amp", True)),
        slope_view=bool(getattr(uistate, "checkBox", {}).get("EPSP_slope", True)),
        dark=bool(getattr(uistate, "darkmode", False)),
        variant=...,  # derived from test_*_variant
        fdr=bool(getattr(uistate, "test_fdr", False)),
    )
```

`_add_significance_markers(...)` encapsulates the marker-drawing algorithm; it can be a module-level helper in `export_image.py`. It should mirror the decision tree in `ui_plot.py::show_test_markers` but operate on a plain `Axes` and `JournalTemplate` rather than live `ax1`/`ax2`.

### 5. Edge Cases & Guards

- No test results → silently skip (current export behavior unchanged).
- Test active but no shown test sets → no markers (consistent with interactive clear).
- Single aspect hidden via checkbox → respect visibility.
- PP mode with overlays → skip overlay labels (already filtered in bar loop).
- IO mode without `io_output` → default to `EPSPamp`.
- Non-finite p/q → treat as `ns`.
- Very small figures (1-col templates): ensure marker font does not overflow; consider a small downward adjustment if width_mm < 90.

### 6. Testing Strategy

- Manual: open a project with ≥2 groups + ≥1 test set, run a t-test (paired/unpaired), toggle FDR, export via each journal template (1-col/2-col). Compare marker presence/positions to interactive view.
- Verify: amp-only, slope-only, both; darkmode; PP export; IO export.
- No automated unit test for visual export is required for v0.16; visual diff via saved PNGs is acceptable.

### 7. Files to Modify

- `src/lib/export_image.py` — add helper and integrate call inside `render_publication_figure`.
- (No changes to `ui_designer.py` per user rule.)
- Optionally: light touch in `export_data.py` if a status message about "markers included" is desired (non-blocking).

### 8. Dependencies & Environment

- Existing: `matplotlib`, `numpy`, `pandas`, `PyQt5`.
- Use `uv` for any environment operations; do not edit `ui_designer.py`.
- Target Python 3.12; after code generation, run `uv run python -c "import export_image; print('ok')"` (or equivalent project entrypoint) to validate import.

## Acceptance Criteria

1. When a formal test is active and results exist, exported PNGs for `amp`/`slope`/`io`/PP-aspect panels contain the same `*`/`**`/`***`/`ns` markers (and in the same logical positions) as the interactive plot.
2. Marker style (font, color, no bbox) and significance mapping are identical to interactive behavior.
3. Journal templates continue to control typography and figure size; markers adapt.
4. No regression: exports without active tests produce identical images to v0.16 baseline.
5. Code passes Python 3.12 import/run check via `uv`.

## Risks & Mitigations

- Marker overlap on dense PP bar groups: mitigate by slight vertical jitter or by placing above error bars (implementation detail).
- Slight differences in text anchoring between interactive blended_transform and export Axes: accept minor visual variance; prioritize semantic equivalence.
- Future multi-page or composite figures (out of scope for v0.16).

## Open Questions (for implementer)

- Exact vertical offset tuning for PP markers when bars are present (inspect `uistate.dict_group_labels` bar tops).
- Whether to expose a per-journal "marker style override" (defer unless requested).

---

_End of plan. Implementation follows this document; no changes to ui_designer.py._
