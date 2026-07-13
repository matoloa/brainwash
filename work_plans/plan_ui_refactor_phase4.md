# UI Refactor Phase IV — Agent index

> **Status**: ✅ Complete. Branch: `ui-refactor/phase0-3`.
> Phase III: [plan_ui_refactor_phase3.md](plan_ui_refactor_phase3.md) ✅

## Goal

Finish high-ROI pure extractions and test leverage from `data_source/` without touching composition, package rename, or drag-core refactors.

## Progress

| PR | Card | Status |
|----|------|--------|
| 31 | [ui_refactor/31_recording_cache_paths.md](ui_refactor/31_recording_cache_paths.md) | ✅ done |
| 32 | [ui_refactor/32_data_source_metadata.md](ui_refactor/32_data_source_metadata.md) | ✅ done |
| 33 | [ui_refactor/33_graphrefresh_pp_labels.md](ui_refactor/33_graphrefresh_pp_labels.md) | ✅ done |
| 34 | [ui_refactor/34_testset_span_descriptors.md](ui_refactor/34_testset_span_descriptors.md) | ✅ done |
| 35 | [ui_refactor/35_export_image_plot_reuse.md](ui_refactor/35_export_image_plot_reuse.md) | ✅ done |

## Verified baseline (post Phase IV)

| Metric | Value |
|--------|-------|
| Tests | 201 passed, 1 skipped (`uv run pytest src/lib/ -q`) |
| `brainwash_ui/` | ~1.1K LOC (8 modules incl. `plot_testsets`) |
| `ui_plot.py` | ~2435 LOC |
| `export_image.py` | delegates IO labels, PP grid, PP ticks to `brainwash_ui` |
| `data_source/` | 14 candidates; pytest uses `characteristic_test_ids` (`01`, `07`, `14`) with `n_sweeps`/`n_stims` metadata |

## Deferred (Phase V+ — do not start until human approves merge)

| Item | Reason |
|------|--------|
| `src/lib` → `src/brainwash` package rename | Agent churn |
| Event bus / `graphRefresh` call dedup (~54 sites) | Needs call-graph map |
| `ui_interactive` drag-core extraction | Artist-handle coupled |
| Full `UIsub` decomposition | Low ROI vs pure-layer wins |
| Screenshot / GUI E2E | Flaky |

## Shared docs

- [ui_refactor/VERIFY.md](ui_refactor/VERIFY.md)
- [ui_refactor/CONTRACT.md](ui_refactor/CONTRACT.md)
- [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md)

## Forbidden (unchanged)

Stats dispatcher guards, public stats API renames, distribution builds, deleting `analysis_v1/v2`.