# Manual smokes after refactor

**Branch**: `ui-refactor/phase0-3`  
**Date**: 2026-07-14  
**Scope**: Post-refactor regression checklist covering UI refactor (Phases 0–X), modularity (Phases 6–8), mixin extraction, `brainwash_ui/` pure-layer extractions, and Phase 7b `UIplot` thinning.

**Related plans**: [plan_ui_refactor.md](plan_ui_refactor.md) · [plan_modularity_phase6.md](plan_modularity_phase6.md) · [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md) · [ui_refactor/CONTRACT.md](ui_refactor/CONTRACT.md) · [phase6/README.md](phase6/README.md)

**Rollback point** (pre–Phase 6): `a2f2dd2`

---

## How to use

1. Run automated preflight (below).
2. Work through sections in order for a full pass, or jump to a section after a targeted PR.
3. Mark each item **PASS** / **FAIL** / **SKIP** (with reason).
4. On FAIL: note step number, recording/project used, console output; see [Failure triage](#failure-triage).

**Recommended test data**

| Asset | Use |
|-------|-----|
| Existing project with ≥2 groups, ≥2 test sets, sweep-tagged data | Stats, groups, testset spans |
| `data_source/01/Concatenate000.abf` (1080 sweeps) | Large-recording drag/perf, pipeline |
| Multi-stim train recording (`stims > 1`) | Stim x-axis, stim-mode rows |
| IO-capable project (volley + EPSP columns) | IO regression statusbar |
| PP project (2 stims) | PPR overlay, paired paths |

---

## Automated preflight (run first)

```sh
uv run pytest src/brainwash/ -q
```

**Expected**: all tests pass (currently **273** collected, **272** passed + **1** skipped).

Optional targeted suites after a specific extraction:

```sh
uv run pytest src/brainwash/test_ui_singletons.py -q          # Phase 6a
uv run pytest src/brainwash/test_plot_stim.py src/brainwash/test_plot_drag.py -q   # drag / 7b
uv run pytest src/brainwash/test_refresh_bus.py src/brainwash/test_refresh_bus_qt.py -q  # graph refresh bus
uv run pytest src/brainwash/test_pipeline_integration.py -q   # recording pipeline
uv run pytest src/brainwash/test_statusbar_characterization.py -q
```

**Import smoke** (Phase 8 — no `src/lib` shim required):

```sh
PYTHONPATH=src uv run python -c "from brainwash import ui; from brainwash.brainwash_ui import plot_stim, plot_series, plot_model"
```

### Automated verification run (2026-07-14)

| Check | Result |
|-------|--------|
| `uv run pytest src/brainwash/ -q` | **PASS** — 272 passed, 1 skipped |
| Import smoke (`PYTHONPATH=src`) | **PASS** |
| Headless launch (`QT_QPA_PLATFORM=offscreen`, 5s) | **PASS** — `UIsub instantiated successfully` |
| Interactive GUI sections (1–15) | **PENDING** — requires human session with project data |

---

## 0. Launch & session lifecycle (Phase 6a–6c)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 0.1 | `uv run python src/main.py` | App starts; no import errors | 6a |
| 0.2 | Open or create project | Tables populate; no stale widgets | 6a |
| 0.3 | Select recording → graphs draw | Mean / event / output canvases render | 6a |
| 0.4 | Close project → open another (or New) | Fresh `UIsub` state; no leaked selection/plots from prior session | 6a |
| 0.5 | Re-open first project | Persisted cfg restored; graphs match saved state | 6a |

---

## 1. Project & recording tables (mixin extraction, pipeline)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 1.1 | Load saved `.bwproj` | Recordings, groups, test sets appear | mixin |
| 1.2 | Multi-select recordings in project table | Selection highlights; graph updates | selection |
| 1.3 | Toggle recording visibility (show checkbox) | Lines appear/disappear without crash | view_state |
| 1.4 | Select single stim in stim table | Event + output focus that stim | selection |
| 1.5 | Multi-stim selection | Appropriate guard (graph refresh or single-stim constraint) | selection |
| 1.6 | Edit norm line edits (`norm_output_from` / `to`) | Output norms refresh after graph refresh | 3b pipeline |
| 1.7 | Save project → reload | Parquet caches, `dft`, `dfoutput` intact | 3b |

---

## 2. Three-pane graphs & refresh bus (Phases II–IX)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 2.1 | Single rec selected: mean (top) shows waveform | Voltage trace; stim markers if applicable | plot_stim |
| 2.2 | Event (middle) shows shifted stim window | Blue/green measurement artists visible | 7b |
| 2.3 | Output (bottom) shows per-sweep lines | ax1 amp / ax2 slope per CONTRACT | plot_series |
| 2.4 | Rapid selection changes (click several recs quickly) | No duplicate artists; graphs settle; no hang | refresh bus 42 |
| 2.5 | `graphRefresh`-heavy action (toggle norm EPSP) | One coherent redraw; legend sane | 33, 74 |
| 2.6 | Zoom scroll on each canvas | Limits update; artists stay aligned | interactive |
| 2.7 | View menu: toggle mean/event/output frames | Frames show/hide per Phase 0.7 | xaxis plan |
| 2.8 | `zoomAuto` after selection change | Sensible xlim/ylim on all visible axes | 43 xdata |

---

## 3. Experiment type — Time (default)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 3.1 | `experiment_type` = time / default | Sweep x-axis; standard output lines | — |
| 3.2 | Mouseover output graph (single rec) | Ghost sweep waveform on event axe | 26 PPR dedupe |
| 3.3 | Mouseover moves across sweeps | Ghost updates; no artist leak | interactive |
| 3.4 | Toggle amp vs slope view | Correct axis (ax1 vs ax2) active | view |
| 3.5 | Toggle norm EPSP checkbox | Output uses `_norm` columns; SI/mV boundary correct | CONTRACT |

---

## 4. Event-plot drag — middle graph (Phase 7b + drag defer)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 4.1 | Drag **EPSP amp** marker (middle plot) | Marker/slope line follows pointer on **event** canvas during drag | 7b |
| 4.2 | **While dragging** (large rec, e.g. 1080 sweeps) | Console does **not** spam `build_dfoutput` per index step; at most event-canvas `draw_idle` | drag defer |
| 4.3 | Release mouse | **One** `build_dfoutput` run; output plot updates; `dfoutput` persisted | release path |
| 4.4 | Drag **EPSP slope** (move + resize zones) | Slope segment + resize handles work; zones from `plot_drag` | 36 |
| 4.5 | Drag **volley amp** / **volley slope** | Same pattern as EPSP aspects | 7b |
| 4.6 | After release: stim table | `dft` row shows `method=manual`; timepoints updated | interactive |
| 4.7 | After release: group means (if rec in group) | Group cache purged; group lines redraw | groups |
| 4.8 | `timepoints_per_stim` linked stims (multi-stim, checkbox off) | All stims move together on drag | interactive |

---

## 5. Output sweep selection drag (PR-37, PR-39)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 5.1 | Click-drag on **output** canvas (time mode) | Sweep range highlights; no `KeyError: -1` | 37 |
| 5.2 | Release drag | `x_select["output"]` populated; sweep range line edits updated | 37 |
| 5.3 | Click only (no drag) | Single sweep selected | 37 |
| 5.4 | Use sweep range for group assignment / stats | Selected sweeps respected | — |

---

## 6. X-axis modes (stim / sweep / time)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 6.1 | Multi-stim recording: switch x-axis to **Stim** | Output shows one point per stim per aspect; sweep lines hidden | 9.1a |
| 6.2 | Switch back to **Sweep** | Per-sweep lines visible; stim lines hidden | 9.1a |
| 6.3 | Recording with valid `sweep_hz`: switch to **Time** | Time-based x-axis enabled | 9.2 |
| 6.4 | Select recording without stims while in stim mode | Auto-revert to sweep; radio disabled styling visible | 9.2 |
| 6.5 | Stim mode: drag timepoint → release | Stim-mode aggregate row (`sweep==NaN`) updates | 8.4 xaxis plan |
| 6.6 | Stim mode: mouseover output | Ghost uses correct stim snippet | 8.6 |

---

## 7. Experiment type — PP

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 7.1 | Switch to PP experiment type | PP overlay positions (`pp_overlay_x_map`); bar + points layout | 18, 21 |
| 7.2 | PPR values finite where expected | `v2/v1`; non-finite → gap | CONTRACT |
| 7.3 | Event drag in PP mode | Middle plot updates; output updates on release (PPR or aspect per config) | 7b |
| 7.4 | `graphRefresh` in PP | PP-specific labels/ticks; no duplicate PPR artists | 33 |
| 7.5 | Formal PP test (if configured) | Statusbar + markers consistent with plot | stats |

---

## 8. Experiment type — IO

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 8.1 | Switch to IO; clear test sets | Statusbar shows **IO regression** (slope p, r², n) — **not** implicit ANOVA | stats CONTRACT |
| 8.2 | Change `io_input` / `io_output` | Scatter + trendline labels (`IO scatter` / `IO trendline`); graph refresh | 7b IO addRow |
| 8.3 | ≥2 groups with sweep data | IO ANCOVA-style statusbar when formal test runs | IO plan |
| 8.4 | Event drag in IO mode | Middle plot live; output IO scatter updates on release | 7b |
| 8.5 | Output canvas click-drag | IO mode does not enter sweep-select drag (guarded) | interactive |

---

## 9. Groups & n_unit (plan_nunit_group_plotting)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 9.1 | Create / assign group; show group | Group mean ± SEM on output; legend entry | 7b group specs |
| 9.2 | Hide group | Lines removed; no orphan artists | view_state |
| 9.3 | Switch `n_unit`: recording → subject → slice | Only active level's group mean/SEM visible; near-instant after first build | n_unit plan |
| 9.4 | Change filter on recording while at slice level | Slice-level cache cleared; subject level unaffected | n_unit plan |
| 9.5 | Add/remove rec from group | Group plots invalidate and redraw | groups |
| 9.6 | Multiple groups visible | Colors distinct; no key collisions in `dict_group_show` | 17 contract |

---

## 10. Test sets & spans (Phase IV)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 10.1 | Define test set with sweep range | Gray spans on ax1/ax2 (`testset_span_{id}`) | 34 |
| 10.2 | Toggle test set visibility | Spans show/hide | view_state |
| 10.3 | Paired t-test with 2 test sets | Applicability OK; statusbar shows p, n_report | 24 |
| 10.4 | Friedman with <3 test sets | Warning string per CONTRACT | applicability |

---

## 11. Statistical tests & statusbar (Phases 3–4, stats refactor)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 11.1 | Time: unpaired t-test, 2 groups | Statusbar: p, n_report; markers on plot | 24 |
| 11.2 | Paired t-test | Requires exactly 2 test sets; warning if not | applicability |
| 11.3 | Switch `n_unit` during active test | n in statusbar updates | stats |
| 11.4 | ANOVA / RM-ANOVA (if project supports) | Markers + statusbar coherent | stats |
| 11.5 | FDR toggle | q-values reflected in statusbar text | stats |
| 11.6 | Cluster permutation (if MNE available) | Recording-level note; no crash | stats |
| 11.7 | Old project without subject/slice columns | Hierarchy warning unchanged | stats smoke |
| 11.8 | `update_test` path | Bold statusbar on success; warning state on applicability fail | CONTRACT |

---

## 12. Parse & import (ParseMixin)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 12.1 | Parse new ABF via UI | Progress bar; recording appears in table | parse mixin |
| 12.2 | `data_source/01` or project ABF | Pipeline produces `dft` + `dfoutput`; 1080 rows for 01 | 28–30 |
| 12.3 | Re-analyze recording | Cache refresh; graphs updated | pipeline |
| 12.4 | Drag-drop add data (if enabled in build) | Same as parse button path | parse |

---

## 13. Export (Phases IV, VIII)

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 13.1 | Export image (current view) | PNG written; no crash on artist xdata | 35, 40 |
| 13.2 | Export with formal test markers visible | Markers appear in export matching screen | export plan |
| 13.3 | Journal template export (if used) | Layout sane; no missing lines | export plan |

---

## 14. UI polish & wiring

| # | Step | Expected | Phase |
|---|------|----------|-------|
| 14.1 | Dark mode toggle | Colors update; disabled radio buttons readable | xaxis 9.2 |
| 14.2 | `sample_overlay` / group sample (if enabled) | Inset on output axes; clears on refresh | 77 |
| 14.3 | `updateStimLines` after drag release | Stim lines on mean/output match new `dfoutput` | 27, 12120f9 |
| 14.4 | `updateOutLineFromDf` / PPR refresh paths | Output lines match dataframe, not stale `mouseover_out` | 2cc8052 |
| 14.5 | SavGol / filter column (if used) | `build_dfoutput` uses selected filter col | savgol plan |
| 14.6 | `pytest-qt` wiring (`test_ui_wiring`) | Radio/checkbox ↔ `uistate` sync (sanity via automated test) | 07 |

---

## 15. Phase 7b extraction regression matrix

Quick spot-check that pure helpers still drive the same visuals:

| Area | Trigger | Watch for |
|------|---------|-----------|
| `plot_stim.build_axe_mean_plot_specs` | Select rec | Mean stim markers |
| `plot_stim` drag plans | Event drag release | `updateLine` / `updateAmpMarker` / output line |
| `plot_series` PP aggregate | PP + groups | Bar positions, PPR |
| `plot_model` group/rec labels | `graphRefresh` | Legend text, PP ticks |
| `plot_drag` zones | Hover event plot | Move vs resize cursor zones |
| `recording_pipeline.build_dfoutput_from_inputs` | Open rec first time | Parquet output cache |

---

## Summary scorecard

| Section | PASS | FAIL | SKIP | Tester | Date |
|---------|------|------|------|--------|------|
| 0 Launch | 0.1 | | 0.2–0.5 | agent (headless) | 2026-07-14 |
| 1 Project/tables | | | all | | |
| 2 Graphs/refresh | | | all | | |
| 3 Time mode | | | all | | |
| 4 Event drag | | | all | | |
| 5 Output sweep drag | | | all | | |
| 6 X-axis modes | | | all | | |
| 7 PP mode | | | all | | |
| 8 IO mode | | | all | | |
| 9 Groups/n_unit | | | all | | |
| 10 Test sets | | | all | | |
| 11 Stats/statusbar | | | all | | |
| 12 Parse | | | all | | |
| 13 Export | | | all | | |
| 14 UI polish | 14.6 | | 14.1–14.5 | pytest | 2026-07-14 |
| 15 7b matrix | | | all | | |
| Preflight (pytest + import) | all | | | agent | 2026-07-14 |

**Full pass criteria**: all non-SKIP items PASS; pytest green. **Close-out status**: automated preflight PASS; interactive sections pending human run.

---

## Failure triage

| Symptom | Likely refactor area | First check |
|---------|---------------------|-------------|
| App won't start | Phase 6a singletons, Phase 8 imports | `test_ui_singletons.py`; import smoke |
| Wrong state after New/Open project | Phase 6a `UIsub` lifetime | Section 0.4 |
| `KeyError: -1` on output drag | PR-37 artist xdata | `plot_drag.artist_xdata` |
| `build_dfoutput` every drag step | Drag defer regression | Section 4.2; `ui_interactive._update_dft_temp_from_drag` |
| IO statusbar shows ANOVA | Stats dispatcher guard | `experiment_type=io` + empty test sets |
| Duplicate plot lines | refresh bus / cache purge | Section 2.4; `group_cache_purge` |
| Stim x-axis empty | stim-mode rows / dual artists | Section 6; `x_mode` visibility |
| Group level wrong after n_unit switch | n_unit cache keys | Section 9.3 |
| Export missing lines | export xdata hardening | Section 13; `plot_drag.artist_xdata` |

**Rollback** (Phase 6+ only):

```sh
git log --oneline --grep='HIGH RISK'
git reset --hard a2f2dd2   # local only — confirm before push
```

Re-verify on rollback baseline: `uv run pytest src/brainwash/ -q` + Section 0.

---

## Changelog

| Date | Notes |
|------|-------|
| 2026-07-14 | Initial checklist: UI refactor 0–X, modularity 6–8, 7b extractions, drag defer, 273 pytest baseline |
| 2026-07-14 | Close-out: automated preflight PASS (272+1 skip); headless launch PASS; interactive sections pending |