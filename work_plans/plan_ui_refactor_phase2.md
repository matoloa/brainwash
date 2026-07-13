# UI Refactor Phase II — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`. **Do not merge to main** until human says so.
> Parent: [plan_ui_refactor.md](plan_ui_refactor.md) (PRs 00–16 ✅).

## Progress

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

After each PR: mark ✅ here and in [plan_ui_refactor.md](plan_ui_refactor.md); set **NEXT** on following row.

## Verified baseline (2026-07-13)

- `uv run pytest src/lib/ -q` → 148 passed, 13 skipped
- `ui_plot.py` 2572 LOC; `brainwash_ui/` ~720 LOC; 26 `plot_model`/`plot_series` delegations in `ui_plot`
- `test_data/*.abf` → gitkeep only (pipeline ABF tests skip)
- `pp_overlay_x_map` exists but `addRow` / `updateOutLineFromDf` still duplicate inline `x_val_map`

## Execution order

```
17 (docs) → 18 (dedupe) → 19 (getattr) → 20 (plot_stim) → 21 (PP/aggregate) → 22 (layout) → 23 (goldens) → 24 (wiring tests) → 25 (hygiene)
```

## Shared docs

- [ui_refactor/VERIFY.md](ui_refactor/VERIFY.md)
- [ui_refactor/CONTRACT.md](ui_refactor/CONTRACT.md) — plot invariants added in PR-17
- [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md) — Tier B4 plot split

## Forbidden (unchanged)

Stats dispatcher guards, public stats API renames, distribution builds, deleting `analysis_v1/v2`, full `UIsub` rewrite, package rename.