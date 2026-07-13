# UI refactor — agent index

> **Status**: Active. Parent evaluation: [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md).

## Active scope

- **Pure UI-adjacent logic** → `src/lib/brainwash_ui/` (view state, applicability, statusbar formatters).
- **Tests** → `test_view_state.py`, `test_applicability_characterization.py`, `test_statusbar_characterization.py`, `test_pipeline_integration.py`.
- **CI** → `.github/workflows/test.yml`.
- **Thin wiring** in `ui_stat_test.py` (and later `ui_selection.py`, `ui_data_frames.py`).
- **No** full `UIsub` composition rewrite. **No** package rename. **No** distribution builds unless asked.

## Progress

| PR | Card | Status |
|----|------|--------|
| — | [plan_modularity_ui_testing_evaluation.md](plan_modularity_ui_testing_evaluation.md) | ✅ done (evaluation) |
| 00 | [ui_refactor/00_DONE_evaluation.md](ui_refactor/00_DONE_evaluation.md) | ✅ done |
| 01 | [ui_refactor/01_ci_and_agents_hygiene.md](ui_refactor/01_ci_and_agents_hygiene.md) | ✅ done |
| 02 | [ui_refactor/02_view_state.md](ui_refactor/02_view_state.md) | ✅ done |
| 03 | [ui_refactor/03_applicability_checks.md](ui_refactor/03_applicability_checks.md) | ✅ done |
| 04 | [ui_refactor/04_statusbar_formatters.md](ui_refactor/04_statusbar_formatters.md) | ✅ done |
| 05 | [ui_refactor/05_pipeline_integration.md](ui_refactor/05_pipeline_integration.md) | ✅ done |
| 06 | [ui_refactor/06_app_context_facade.md](ui_refactor/06_app_context_facade.md) | ✅ done |
| 07 | [ui_refactor/07_pytest_qt_smoke.md](ui_refactor/07_pytest_qt_smoke.md) | ✅ done |
| 08 | [ui_refactor/08_stat_test_injection.md](ui_refactor/08_stat_test_injection.md) | ✅ done |
| 09 | [ui_refactor/09_selection_injection.md](ui_refactor/09_selection_injection.md) | ✅ done |
| 10 | [ui_refactor/10_data_frames_injection.md](ui_refactor/10_data_frames_injection.md) | ✅ done |
| 11 | [ui_refactor/11_host_protocols.md](ui_refactor/11_host_protocols.md) | ✅ done |
| 12 | [ui_refactor/12_remaining_injection.md](ui_refactor/12_remaining_injection.md) | ✅ done |
| 13 | [ui_refactor/13_plot_model.md](ui_refactor/13_plot_model.md) | ✅ done |

After each PR: mark card ✅ in this table, set **NEXT** on the following row.

## Shared docs (read on demand)

- [ui_refactor/VERIFY.md](ui_refactor/VERIFY.md) — commands after every PR
- [ui_refactor/CONTRACT.md](ui_refactor/CONTRACT.md) — statusbar/view invariants
- [ui_refactor/README.md](ui_refactor/README.md) — micro-plan table
- [Archive/mixin_problems.md](Archive/mixin_problems.md) — why mixins ≠ modularity

## Session rule

**One card = one session = one PR.** Extract behavior first; keep mixin methods as thin delegates. Do not reorder `brainwash_stats/dispatcher.py` guards.

## Forbidden (all UI refactor PRs)

- `StatContext`, `ComparisonMode`, `MODE_HANDLERS`
- Renaming `compute_statistical_comparison`, `ttest_per_sweep`, `from . import statistics as stats`
- Guard reordering in `brainwash_stats/dispatcher.py`
- Distribution builds / `uv sync --group build` unless user asks