# UI refactor — agent index

> **Status**: Active. Parent evaluation: [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md).
> Phase 0–3 cards archived under [History/ui_refactor/](History/ui_refactor/).

## Active scope

- **Pure UI-adjacent logic** → `src/lib/brainwash_ui/` (view_state, applicability, statusbar, plot_model, plot_series, plot_stim).
- **Tests** → characterization + `test_pipeline_integration.py` + `test_ui_wiring.py`.
- **CI** → `.github/workflows/test.yml`.
- **No** full `UIsub` composition rewrite. **No** package rename. **No** distribution builds unless asked.

## Progress — Phase 0–3 (archived)

| PR | Card | Status |
|----|------|--------|
| 00–16 | [History/ui_refactor/](History/ui_refactor/) | ✅ done |

## Progress — Phase II

Branch: `ui-refactor/phase0-3`. Index: [plan_ui_refactor_phase2.md](plan_ui_refactor_phase2.md).

| PR | Card | Status |
|----|------|--------|
| 17 | [ui_refactor/17_index_and_plot_contract.md](ui_refactor/17_index_and_plot_contract.md) | ✅ done |
| 18 | [ui_refactor/18_pp_overlay_dedupe.md](ui_refactor/18_pp_overlay_dedupe.md) | ✅ done |
| 19 | [ui_refactor/19_nested_getattr_cleanup.md](ui_refactor/19_nested_getattr_cleanup.md) | ✅ done |
| 20 | [ui_refactor/20_plot_stim.md](ui_refactor/20_plot_stim.md) | ✅ done |
| 21 | [ui_refactor/21_plot_series_pp_aggregate.md](ui_refactor/21_plot_series_pp_aggregate.md) | ✅ done |
| 22 | [ui_refactor/22_plot_layout.md](ui_refactor/22_plot_layout.md) | ✅ done |
| 23 | [ui_refactor/23_pipeline_goldens.md](ui_refactor/23_pipeline_goldens.md) | ✅ done |
| 24 | [ui_refactor/24_statusbar_wiring_tests.md](ui_refactor/24_statusbar_wiring_tests.md) | ✅ done |
| 25 | [ui_refactor/25_hygiene_archive.md](ui_refactor/25_hygiene_archive.md) | ✅ done |

**Phase III**: [plan_ui_refactor_phase3.md](plan_ui_refactor_phase3.md) — manual smoke PASS.

| PR | Card | Status |
|----|------|--------|
| 26 | [ui_refactor/26_ppr_dedupe_interactive.md](ui_refactor/26_ppr_dedupe_interactive.md) | ✅ done |

**NEXT (human)**: merge `ui-refactor/phase0-3` → main when ready.

## Shared docs

- [ui_refactor/VERIFY.md](ui_refactor/VERIFY.md)
- [ui_refactor/CONTRACT.md](ui_refactor/CONTRACT.md)
- [ui_refactor/README.md](ui_refactor/README.md)

## Forbidden (all UI refactor PRs)

- `StatContext`, `ComparisonMode`, `MODE_HANDLERS`
- Renaming `compute_statistical_comparison`, `ttest_per_sweep`, `from . import statistics as stats`
- Guard reordering in `brainwash_stats/dispatcher.py`
- Distribution builds unless user asks