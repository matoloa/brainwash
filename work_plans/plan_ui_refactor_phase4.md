# UI Refactor Phase IV — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`.
> Phase III: [plan_ui_refactor_phase3.md](plan_ui_refactor_phase3.md) ✅

## Goal

Finish high-ROI pure extractions and test leverage from `data_source/` without touching composition, package rename, or drag-core refactors.

## Progress

| PR | Card | Status |
|----|------|--------|
| 31 | [ui_refactor/31_recording_cache_paths.md](ui_refactor/31_recording_cache_paths.md) | **NEXT** |
| 32 | [ui_refactor/32_data_source_metadata.md](ui_refactor/32_data_source_metadata.md) | pending |
| 33 | [ui_refactor/33_graphrefresh_pp_labels.md](ui_refactor/33_graphrefresh_pp_labels.md) | pending |
| 34 | [ui_refactor/34_testset_span_descriptors.md](ui_refactor/34_testset_span_descriptors.md) | pending |
| 35 | [ui_refactor/35_export_image_plot_reuse.md](ui_refactor/35_export_image_plot_reuse.md) | pending |

After each PR: mark ✅ here and in [plan_ui_refactor.md](plan_ui_refactor.md); set **NEXT** on following row.

## Verified baseline (post Phase III)

| Metric | Value |
|--------|-------|
| Tests | 193 passed, 1 skipped (`uv run pytest src/lib/ -q`) |
| `brainwash_ui/` | ~1K LOC (7 modules) |
| `ui_plot.py` | ~2433 LOC |
| `ui_interactive.py` | ~2004 LOC |
| `data_source/` | 14 candidates; pytest uses `characteristic_test_ids` (`01`, `07`, `14`) |

## Execution order (strict default)

```
31 (recording_cache paths) → 32 (data_source metadata) → 33 (PP labels) → 34 (testset spans) → 35 (export_image)
```

PR-32 can run after PR-31 in parallel only on a separate branch; default sequential.

## Success criteria (Phase IV complete)

| Milestone | Target |
|-----------|--------|
| `recording_cache.py` | Covers output, mean, filter, timepoints, group-mean paths used by `ui_data_frames` |
| `data_source/manifest.json` | Metadata per candidate; characteristic tests assert sweep/stim counts |
| `ui_plot.py` LOC | <2350 after PR-33+34 |
| Agent self-verify | No app launch for PR-31–34; `uv run pytest src/lib/ -q` green |

## Deferred (Phase V+ — do not start until IV green)

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