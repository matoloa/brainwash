# Plan: v0.16_scitest_figtext — Generate Companion .md with Journal-Ready Figure Text

## Objective

When the user exports a journal figure (PNG) via the existing export pipeline, also emit a companion Markdown file (`.md`) with the **same base filename** (e.g., `JNeurosci_1col_amp.md` next to `JNeurosci_1col_amp.png`). The **entire contents** of that `.md` are a concise, journal-convention figure text / caption fragment that the user can copy-paste directly into a manuscript or submission system.

- The `.md` is **not** rendered into the image (no `ax.text`, no `fig.text`).
- The `.md` is **not** a verbose log or table; it is publication-oriented prose or a compact legend block.
- The generator draws on the same information already available to the program at export time: `test_type`, variant/tails/FDR, `formal_test_results` (p/q values, `n1`/`n2`, `eta2`, `stat_*`), shown aspects, group names, and the selected `JournalTemplate`.

This plan replaces the earlier "draw text on image" interpretation. **Generator location confirmed in `export_image.py`** (publication layer, reuses existing statistical parsing). Per-panel `.md` strategy finalized. Signature refined for practicality. All open questions resolved.

## Background

### Current export behavior

- `export_data.py::triggerExportOutputImage(template_key)` calls `export_image.render_publication_figure(...)` and writes one or more PNG files to `Export/`.
- Each PNG corresponds to a panel or aspect (amp, slope, io, PP aspects, etc.).
- No textual companion is produced.

### What the program already knows at export time (recap)

- `uistate.test_type`, `test_t_variant`/`test_wilcox_variant`, `test_t_tails`/`test_wilcox_tails`, `test_fdr`, `test_sw`, `test_levene`
- `uistate.formal_test_results`: list[dict] with `set_name`/`set_id`, `sweeps`, `p_amp`/`p_slope` (and `q_*` if FDR), `n1`/`n2`, `stat_*`, `eta2` (ANOVA), cluster stat, etc.
- `uistate.checkBox["EPSP_amp"]`/`["EPSP_slope"]`, `ampView`/`slopeView`
- Shown groups via `dict_group_labels` or `dd_groups`; per-group `n` from result rows
- Selected `JournalTemplate` (name, width_mm, font metrics) — used only for guidance (e.g., line-length, tier selection), not for drawing

### Existing textual outputs (not suitable as figure text)

- `_print_statistical_test_table`: developer console dump (raw stats, multi-line, not journal prose)
- Statusbar summary: ultra-abbreviated, live-UI-oriented (`"t-test (FDR) (unpaired): set 1: amp p=0.012 | ..."`), includes internal tokens like `__anova_rm_omnibus__`
- Graph markers (`*`/`**`/`ns`): visual only

### Journal conventions for figure text

Journals differ in expected density, but common patterns include:

- A compact legend block or caption paragraph that states:
  - Test type + key qualifiers (unpaired/paired/one-sample, two-sided/greater/less, FDR or not)
  - n per group/condition
  - Significance thresholds or representative p/q values (or "ns" where appropriate)
  - Effect size when relevant (η² for ANOVA)
  - Short limitation note when applicable (e.g., "omnibus only; post-hoc deferred")

Examples (illustrative):

> Two-sided unpaired t-test with FDR; \*p<0.05, \*\*p<0.01; n=7 Control, n=6 Drug. Pre vs Post comparisons shown.

> Repeated-measures ANOVA (omnibus); η²=0.31; n=8; \*p<0.05 (simplified; RM-ANOVA+post-hoc deferred).

> Cluster permutation test (between-subjects); amp p=0.012 (cluster); n1=5, n2=6.

The generated `.md` should be **ready to paste** — either as a standalone caption fragment or as a small legend paragraph that can sit under the figure in the manuscript.

## Scope

Implement a generator that, during export, produces a `.md` companion for each exported PNG (or a single shared `.md` per export batch — decide in implementation; document either way).

The generator must handle:

- All five active test types (t-test, ANOVA, Wilcoxon, Friedman, Cluster perm.)
- Variant, tails, FDR, SW/Levene diagnostics
- Multiple test sets (per-set or omnibus wording)
- Paired/one-sample semantics (single comparison wording)
- Non-finite p/q → "NA" or omission
- Effect size (η²) when present
- n values per group/condition
- Aspect visibility (only mention enabled aspects)
- Journal-aware formatting hints (e.g., shorter form for 1-col templates)

Out of scope:

- Full multi-paragraph Methods + Results + Conclusions caption (future extension)
- User-editable caption UI
- Per-journal "mandatory elements" policy engine
- Automatic insertion into a Word/LaTeX document

## Design

### 1. Generator location and signature

Add a pure helper in `src/lib/export_image.py` (confirmed correct placement: publication/JournalTemplate layer, reuses existing `formal_test_results` parsing from `_add_significance_markers` and statusbar logic):

```python
def build_figure_text_md(
    results: list[dict],
    test_type: str,
    variant: str | None = None,
    tails: str | None = None,
    fdr: bool = False,
    sw: bool = False,
    levene: bool = False,
    norm: bool = False,
    amp_enabled: bool = True,
    slope_enabled: bool = True,
    template: JournalTemplate,
    group_names: Optional[dict] = None,
) -> str:
    """
    Return a single Markdown string (complete file contents) ready to paste
    as journal figure text / caption fragment / compact legend. May contain
    line breaks for readability. No YAML front-matter.
    """
    ...
```

(Note: simplified signature; `variant`/`tails` derived from `test_type` + `results`/`uistate` where needed. `n_map` not required — derive `n` from `results` rows.)

### 2. Output shape (examples)

**t-test (unpaired, FDR, two test sets):**

```
Unpaired two-sided t-test with FDR correction. Amp: Pre p=0.012, Post p=0.340. n=7 Control, n=6 Drug per set. *p<0.05, **p<0.01, ***p<0.001.
```

**ANOVA (RM omnibus):**

```
Repeated-measures ANOVA (omnibus); η²=0.31; n=8. *p<0.05 (simplified; RM-ANOVA+post-hoc deferred).
```

**Cluster perm. (between-subjects):**

```
Cluster permutation test (between-subjects). Amp p=0.012 (cluster); n1=5, n2=6.
```

**Paired t-test (single comparison):**

```
Paired two-sided t-test; amp p=0.008; n=9. *p<0.05.
```

**No active test:**

```
(Exported without statistical comparison overlay.)
```

Edge cases (non-finite p, missing n, etc.) should degrade gracefully to "NA" or omission rather than crash.

### 3. Journal-driven formatting (light touch)

- Use `template.name` (e.g., "JNeurosci (1 col)") to decide tier or abbreviation level:
  - 1-col / narrow templates → shorter form, fewer exact p-values, more "n=..." summary
  - 2-col / wider templates → allow slightly more detail
- Font metrics (`font_size_legend`) are **not** used for rendering (text is not drawn); they may inform future "suggested font size for caption" notes if desired.
- The generator is **stateless** and can be unit-tested without Qt or a figure.

### 4. When and where the .md is written

- Prefer calling from inside `render_publication_figure(...)` (in `export_image.py`) after figure construction but before returning the dict. This keeps all publication logic together and gives direct access to `panel`, `template`, `uistate`, and per-panel visibility. The caller in `export_data.py::triggerExportOutputImage(...)` (after PNG save loop) then writes the returned text to disk.
- Naming: for each PNG `PROJECT_jneurosci_1col_amp.png` emit companion `PROJECT_jneurosci_1col_amp.md` (per-panel, Option A). This gives context per exported aspect/panel; duplication of statistical summary is acceptable and matches "same base filename" intent.
- Always emit a `.md` (even if `test_type == "None"` or no `formal_test_results`): short fallback text ensures user always gets a companion file.

### 5. File layout (implementation choice)

**Chosen: Option A (per-panel)** — one `.md` per PNG with identical base name (e.g. `..._amp.md` next to `..._amp.png`). Simpler mapping from the existing `figures` dict loop; each panel gets its own ready-to-paste text (aspects, visibility, and panel-specific notes differ). Duplication of the core statistical summary is acceptable for v0.16 (future work can deduplicate into a shared `..._figure.md`).

Document this choice in code comments and the updated base plan.

## Implementation Phases

### Phase 0 — Skeleton + smoke test

- Add `build_figure_text_md(...)` (public for potential "Copy figure text" reuse) stub returning a placeholder string like "(Figure text generator v0.16 stub)".
- Verify import via `uv run python -c "from export_image import build_figure_text_md; print('ok')"`.
- Add minimal call site inside `render_publication_figure` (return both `fig` and text in a tuple or separate dict key) + write logic in `triggerExportOutputImage` that creates a matching `.md` next to each PNG.

### Phase 1 — Core t-test / Wilcoxon formatting

- Implement realistic output for t-test (all three variants) and Wilcoxon.
- Include n values, aspect list, FDR/tails/variant notes, significance thresholds.
- Handle "NA" for non-finite p; single-comparison wording for paired/one-sample.
- Add simple assertions or manual checks against example states.

### Phase 2 — ANOVA / Friedman / Cluster extensions

- Extend generator for omnibus rows: include η²; use "(repeated, omnibus)" / "(repeated-measures omnibus)" wording.
- Handle Cluster perm. rows (per-test-set or paired-cluster combined row).
- Verify statusbar-derived notes (e.g., "(cluster)", "(simplified; RM-ANOVA+post-hoc deferred)") are rendered appropriately for publication context (trim internal tokens).

### Phase 3 — Diagnostics, edge cases, journal hints

- Incorporate SW/Levene flags (from `results` or params) into a short qualifier when relevant (full tier / wider templates only; reuse statusbar phrasing but publication-polished).
- Graceful degradation when `test_type == "None"`, `results == []`, or no `formal_test_results`.
- Respect aspect visibility (`amp_enabled` / `slope_enabled` from checkboxes or panel context; omit disabled aspects).
- Use `template.width_mm` (or `template.name`) for tiered wording: shorter on 1-col (<90mm), more detail on 2-col. (Aligns with existing `_add_significance_markers` logic.)

### Phase 4 — Integration with export pipeline

- Wire `build_figure_text_md(...)` into `render_publication_figure(...)` (receives all needed state; returns text alongside each `fig`).
- Update `triggerExportOutputImage` to write the companion `.md` immediately after each `fig.savefig(...)` (use `Path.with_suffix('.md')` for naming).
- Per-panel strategy (Option A) is now finalized — document in code and base plan.

### Phase 5 — Documentation + validation

- Append one-line note to Success Criteria in `docs/plan_v0.16_scitest.md` (e.g. "- Figure text companion `.md` files are emitted on every journal PNG export (per `plan_v0.16_scitest_figtext.md`).").
- Run `uv run python -c "import export_image; print('ok')"` + basic export smoke test (verify `.md` appears next to PNG with sensible content).
- Close this plan file with "Implemented" date + short summary of choices (per-panel, location in `export_image.py`, reuse of statusbar/result parsing logic).

## File Change Summary

| File                            | Changes                                                                                                                                                                                             |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/export_image.py`       | **NEW:** `build_figure_text_md(...)` pure helper (reuses result parsing from `_add_significance_markers` + statusbar logic in `ui.py`). Updated `render_publication_figure` to invoke it per panel. |
| `src/lib/export_data.py`        | Minor update to `triggerExportOutputImage`: write `.md` companion (via returned text) immediately after each PNG save.                                                                              |
| `docs/plan_v0.16_scitest.md`    | Append one-line note to Success Criteria referencing this plan.                                                                                                                                     |
| `plan_v0.16_scitest_figtext.md` | This file (refined signature, confirmed location in `export_image.py`, finalized per-panel strategy, clarified integration and reuse of existing patterns).                                         |

(No changes to `ui_designer.py` per project rule. No new runtime dependencies.)

## Dependencies & Environment

- Existing: `numpy`, `textwrap` (stdlib). No new runtime deps.
- Use `uv` for any environment operations; do not edit `ui_designer.py`.
- Target Python 3.12; after code generation, run `uv run python -c "import export_image; print('ok')"` (or equivalent project entrypoint) to validate import.

## Acceptance Criteria

1. For each exported PNG, a companion `.md` with the **same base name** (e.g. `..._amp.md` next to `..._amp.png`) is written to `Export/`.
2. The `.md` is a single, ready-to-paste block (publication-oriented prose or compact legend) containing: test type + qualifiers (variant/tails/FDR), n per group/condition, aspect-specific p/q (or "NA"), η² when present, significance thresholds, and appropriate omnibus/cluster notes.
3. All five test types (t-test, Wilcoxon, ANOVA, Friedman, Cluster perm.) produce sensible journal-ready output; paired/one-sample use concise single-comparison wording.
4. Aspect visibility (`amp_enabled`/`slope_enabled`), non-finite p/q values, and missing data are handled gracefully (no crashes, "NA" or omission).
5. No regression: exports without active test (`test_type == "None"`) still produce a short meaningful `.md`.
6. Code passes `uv run python -c "import export_image; print('ok')"`. Per-panel strategy and generator location in `export_image.py` are documented.

## Risks & Mitigations

- Duplicate statistical summary across per-panel `.md` files (per-panel chosen): acceptable for v0.16; future "shared figure.md" or deduplication is low-effort.
- Overly long output on 1-col templates: mitigated by `template.width_mm`-aware tier selection (shorter form, reuse existing marker logic patterns).
- Text quality: generator reuses battle-tested statusbar/result-parsing code from `ui.py` + `statistics.py` for consistency with live UI.
- Future journal-specific rules or "Copy figure text" action: data-driven design + public function in `export_image.py` make extensions straightforward without touching export pipeline.

## Open Questions (for implementer) — Resolved in this update

- **Per-panel vs. per-export**: Finalized as **per-panel (Option A)** — one `.md` per PNG with matching base name. Documented above and will be noted in code.
- `.md` contains **only the ready-to-paste text block** (no suggested filename or YAML).
- Future "Copy figure text" menu action (reusing the same generator on live `uistate`) remains out of scope for v0.16 but is now easier (public function in `export_image.py`).

All major design decisions are now closed.

**Rollback & Lessons (2026)**: Initial implementation (phases 0-5) introduced multiple regressions:

- Repeated `'NoneType' object has no attribute 'keys'` during UI refreshes/statusbar (caused by assuming `formal_test_results`, `group_names`, `dd_groups`, `dict_group_show` always present; fixed with `getattr(..., None)` + `or {}` guards).
- `RuntimeWarning: More than 20 figures have been opened` + export crash (caused by `plt.subplots()` in module-level test block at bottom of `export_image.py`; fixed by switching to pure `matplotlib.figure.Figure()` + explicit `plt.close()`).
- No `.md` produced in real export (likely due to tuple return vs. dict expectation mismatch in `triggerExportOutputImage` loop, exception swallowing, or early return on missing data in `render_publication_figure` when called from live `uistate` vs. mock).
- Test block at bottom of `export_image.py` polluted global pyplot state on every import.

**Rollback plan**: Revert `export_image.py` and `export_data.py` changes related to figure-text (keep only the figure-leak fix in test block). Restore original `render_publication_figure` return type (dict of `Figure` only) and PNG-only logic in trigger. Then re-implement cleanly using a **minimal, non-intrusive approach**.

**Revised Design (safer v2)**:

- Keep `build_figure_text_md(uistate, template, selected_groups=None)` as **pure top-level function** in `export_image.py` (no side effects, always returns str, uses only safe `getattr`).
- **Do not** change `render_publication_figure` signature or return type. Call the text generator **only inside `triggerExportOutputImage`** _after_ successful `figures = render...` and inside the save loop (per-panel text derived from panel key + uistate).
- Fallback text if `uistate.formal_test_results is None` or `test_type == "None"`.
- Write `.md` with `out_path_md.write_text(figure_text_md)` immediately after each PNG (use `Path.with_suffix(".md")`).
- Add `plt.rcParams['figure.max_open_warning'] = 0` or ensure all test figures are closed.
- Keep test block at bottom but guard it with `if __name__ == "__main__":` so it doesn't run on import.
- Update acceptance criteria to require **real export test** (not just mock) + check that `.md` appears with correct content for current uistate.

This minimizes blast radius: no changes to figure rendering path, no tuple returns that could break downstream code, easier debugging of real `uistate` vs mock.

**New Phase 0 (rollback + minimal skeleton)**: Revert breaking edits, add guarded test block, add stub `build_figure_text_md` that returns fallback text, call it only from `triggerExportOutputImage`, write `.md`. Verify with real export call (no crash, `.md` present even if placeholder).

Subsequent phases build the prose logic without touching render path.

**Updated Success Criteria**:

1. Export no longer crashes (no None.keys(), no figure warning).
2. Companion `.md` **always** written next to each PNG (even for no-test case).
3. Text is publication-ready (per examples above) when test active.
4. `uv run python -c "import export_image; print('ok')"` passes cleanly.
5. Real `triggerExportOutputImage("jneurosci_1col")` (or UI menu) succeeds and produces usable `.md`.

Document all lessons in this file. Re-implement from clean slate following revised design.

**Status**: Fully implemented (Phases 0-5). `build_figure_text_md` produces publication-ready text for all 5 test types (t-test/Wilcoxon/ANOVA/Friedman/Cluster), with n values, aspect-specific p/q (or NA), FDR/variant/tails notes, η², SW/Levene qualifiers, single-comparison wording for paired/one-sample, graceful fallbacks, and template.width_mm tiering (shorter for 1-col). Per-panel .md emitted next to each PNG (Option A). Reuses patterns from ui.py statusbar + \_add_significance_markers. All regressions fixed; ax1/ax2 marker bug resolved (user-confirmed). Full export test (PNG + sensible .md) passes. No gold-plating.

**Lessons learned** (added to rollback section):

- Keep `build_figure_text_md(uistate, template, group_names=None)` pure in export_image.py; call _only_ from triggerExportOutputImage.
- Defensive `getattr(..., None) or []`, `np.isfinite`, aspect visibility from checkBox.
- Statusbar logic is excellent reuse target for publication text (pstr rounding, notes).
- y-position bug in dual-aspect was in shared `_add_significance_markers` (va branch was noop).

**Implemented** per this document (full v0.16 figtext feature + marker fix). Updated 2026-06-21. See docs/plan_v0.16_scitest.md for success note.

---

_Implemented (Phases 0-5 + ax1/ax2 marker fix); no ui_designer.py changes. Per revised safe design._
