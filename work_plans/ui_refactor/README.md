# UI refactor — micro-plans

Each `NN_*.md` file is a **complete session brief**. Agents read **only** the current **NEXT** card from [../plan_ui_refactor.md](../plan_ui_refactor.md).

| File | ~lines | Purpose |
|------|--------|---------|
| `00_DONE_evaluation.md` | 15 | Evaluation landed (parent plan) |
| `01_ci_and_agents_hygiene.md` | 35 | GitHub Actions pytest + `AGENTS.md` fix |
| `02_view_state.md` | 45 | `brainwash_ui/view_state.py` + tests |
| `03_applicability_checks.md` | 50 | Pure `_check_*` extraction + tests |
| `04_statusbar_formatters.md` | 55 | `StatusbarResult` formatters + purity split |
| `05_pipeline_integration.md` | 50 | Promote `test_parse_click` → pytest |
| `06_app_context_facade.md` | 45 | Split `UIstate` with backward-compat facade |
| `07_pytest_qt_smoke.md` | 40 | `pytest-qt` wiring smoke tests |
| `08_stat_test_injection.md` | 35 | `StatTestMixin` → `self.uistate` |
| `09_selection_injection.md` | 35 | `SelectionMixin` → `self.uistate` |
| `10_data_frames_injection.md` | 35 | `DataFrameMixin` → `self.uistate` |
| `11_host_protocols.md` | 40 | `Protocol` host contracts |
| `12_remaining_injection.md` | 40 | Batch migrate remaining mixins |
| `13_plot_model.md` | 45 | Pure `plot_model` + test marker specs |
| `15_plot_model_phase2.md` | 40 | Legend/heatmap/axis layout helpers |
| `16_plot_series_addrow.md` | 50 | `plot_series` addRow/addGroup extraction |
| `VERIFY.md` | 20 | Post-PR commands |
| `CONTRACT.md` | 40 | Statusbar/view invariants |

**Forbidden in all PRs**: full `UIsub` rewrite, package rename, stats dispatcher guard reorder, public stats API renames.