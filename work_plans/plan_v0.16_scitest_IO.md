# Plan v0.16: IO r² Display

## Goal (Single, Focused Deliverable)

When `experiment_type == "io"`, display the r² goodness-of-fit for each group's IO regression in a clear, non-cluttered location on both the live UI and exported PNG.

**Constraint (baked into architecture):** Trendlines currently generate separate legend entries from their group's scatter symbol. Any solution must either:

- Merge scatter + trendline into a single legend entry (preferred), or
- Accept r² on the trendline's separate legend entry, or
- Use an alternative location (caption, status bar, inset).

**v0.16 will implement exactly one of the three options above after Phase 0 exploration determines the minimal viable path.**

## Background

- IO plots show scatter (one color per group) with optional trendlines (linear or other fit).
- Each group has a computed r² for its fit.
- Formal statistical tests are disabled for IO (sci-test frame auto-hidden per companion plan); r² is the appropriate metric.
- Current legend construction in `ui_plot.py` and `export_image.py` creates separate entries for trendlines.

## Phase 0: Locate Data Sources and Legend Construction (Mandatory First Step)

**Do not edit any code until Phase 0 is complete and a location decision is recorded.**

### Tasks (Parallelizable via Sub-Agents)

1. **Find where r² is computed or stored for IO fits.**
   - Search: `r2`, `r_squared`, `rsquared`, `R2`, `goodness` in `ui_plot.py`, `ui.py`, `export_image.py`.
   - Identify the data structure: per-group? per-aspect (amp/slope)? stored on which object (`uistate`, `dict_group_labels`, fit result)?

2. **Map the legend construction path.**
   - Find all calls to `ax.legend(...)`.
   - Identify where legend labels/handles are built: `dict_group_labels`, `addGroup`, `update`, `graphRefresh`, or a helper.
   - Determine whether trendline artists are added as separate entries and how their labels are generated.

3. **Check `build_figure_text_md` for IO panel handling.**
   - Does it already iterate groups for the `"io"` panel?
   - Can it emit a caption line like: "Group A: r² = 0.97 (n=12)"?

4. **Decision checkpoint (end of Phase 0).**
   - Record in this plan (or a follow-up note):
     - Where r² lives (variable/path).
     - Whether merging legend entries is <20 LOC or requires deeper refactor.
     - Chosen location for r²: (a) merged legend entry, (b) trendline's existing separate entry, (c) `.md` caption only, (d) other.

**Agentic note:** This phase is read-only exploration. Use `grep`, `read_file` (targeted line ranges), and `spawn_agent` for parallel searches. No edits.

### Phase 0 Findings (Recorded Results)

**Trendline creation sites:**

- Recording-level: `ui_plot.py:addRow` L1513-1550 (per-rec IO scatter + trendline; stored in `dict_rec_labels`).
- Group-level: `ui_plot.py:addGroup` L2179-2215 (aggregated per-group; stored in `dict_group_labels`).
- Both use `np.polyfit` (centered) or `io_force0` special case. **r² is never computed.**

**Logical r² insertion point:** Inside the `if len(x_vals) > 1:` block immediately after `m, c` computation, using:

```python
y_pred = m * x_vals + c
ss_res = np.sum((y_vals - y_pred) ** 2)
ss_tot = np.sum((y_vals - np.mean(y_vals)) ** 2)
r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
```

**Storage:** Add `"r2": r2` key to the existing `dict_group_labels` / `dict_rec_labels` entries (~5 LOC total).

**Legend path:** Labels originate from the `label=` kwarg in `scatter`/`plot`. Export (`render_publication_figure` L537-540) uses `get_legend_handles_labels` + dedup. To show r² in legend, append to the label string at creation time.

**build_figure_text_md:** No IO branch exists. If caption-only path chosen, a new `if experiment_type == "io"` block is required.

**Effort summary:** Storing r² is ~5 LOC. Appending to legend labels is 1-2 string edits. Legend entry merging (visual scatter+line) requires further inspection of `HandlerTuple` or custom handler usage.

## Phase 1: Implement Chosen r² Location (After Phase 0 Decision)

### Option A — Merged Legend Entry (Preferred if Low Effort)

- Refactor legend construction so each group's scatter + trendline share one entry.
- Append `r² = X.XX` (and optionally `n=`) to that label when `experiment_type == "io"`.
- Update both live UI and export paths.
- Test: 1–4 groups, trendlines on/off, IO vs non-IO modes (no regression).

### Option B — r² on Trendline's Separate Entry

- No merge required.
- When building the trendline's legend label (in IO mode), append `r² = X.XX`.
- Ensure scatter entry remains clean (group name only).
- Test: same as Option A.

### Option C — `.md` Caption Only (Fallback if A/B Too Costly)

- Leave legend untouched.
- Extend `build_figure_text_md` to emit one line per IO panel with all groups' r² values.
- Update `triggerExportOutputImage` or equivalent to ensure the `.md` is written alongside the PNG.
- Test: export produces correct caption; live UI shows nothing new (or a transient status).

**Implementation rule:** Edit the minimal number of functions. If Option A requires changes in >3 functions or >50 LOC, escalate to Option B or C.

## Phase 2: Testing (Targeted)

- **Live UI:** Switch to IO mode → r² appears in chosen location → switch away → no regression in other modes.
- **Export:** IO panel PNG + `.md` companion shows r² correctly.
- **Edge cases:** No trendline (r² still shown), <2 points (r² = "—"), multiple aspects if applicable.
- **Cross-check:** Non-IO modes unaffected.

## Non-Goals (Explicit)

- Significance markers (`*`/`**`) on IO plots — never appropriate.
- Auto-hide of sci-test frame — see companion `plan_v0.16_scitest_PP.md`.
- New fit models or IO computation changes.
- Per-aspect r² if IO currently only fits one output (`io_output`).

## Files Likely Touched (Post-Phase 0)

- `src/lib/ui_plot.py` (legend building, IO scatter/trendline path)
- `src/lib/export_image.py` (legend in `render_publication_figure`, `build_figure_text_md`)
- Possibly `src/lib/ui.py` (export trigger, IO output change handler)

## Acceptance Criteria (Measurable)

1. When an IO project is loaded with ≥1 group and a fit computed, r² is visible for each group in the location chosen after Phase 0.
2. No new legend entries or visual clutter introduced beyond the chosen design.
3. Export PNG (if location is on-figure) and/or `.md` companion contains the r² values.
4. Switching project type or de-selecting IO removes r² display cleanly.
5. Zero regression in non-IO modes (legend, time-course, PP, etc.).

## Post-v0.16 Note

If Option C (caption only) is chosen for v0.16 due to legend complexity, the design preference for merged legend entries remains documented and can be scheduled for v0.17 without re-discussion.
