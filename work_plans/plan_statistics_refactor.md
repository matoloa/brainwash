# Statistics refactor — agent index

> **Read this file only** (~25 lines). Then open **one** micro-plan below. Never load the archive spec in the same session.

## Active scope

- **Only** `src/lib/statistics.py` → `src/lib/brainwash_stats/` (+ tests).
- **No** `ui.py`. **No** statusbar plan (`History/plan_statusbar_ui.md` cancelled).
- **Public API frozen**: `compute_statistical_comparison`, `ttest_per_sweep`, `from . import statistics as stats`.

## Progress

| PR | Card | Status |
|----|------|--------|
| 00 | [00_DONE_bootstrap.md](statistics_refactor/00_DONE_bootstrap.md) | ✅ done |
| 01 | [01_hoist_aggregate_and_aspects.md](statistics_refactor/01_hoist_aggregate_and_aspects.md) | ✅ done |
| 02 | [02_unify_observation_fetcher.md](statistics_refactor/02_unify_observation_fetcher.md) | ✅ done |
| 03 | [03_package_data_and_fdr.md](statistics_refactor/03_package_data_and_fdr.md) | ✅ done |
| 04 | [04_package_io_helpers.md](statistics_refactor/04_package_io_helpers.md) | ✅ done |
| 05 | [05_extract_friedman.md](statistics_refactor/05_extract_friedman.md) | ✅ done |
| 06 | [06_extract_rm_anova.md](statistics_refactor/06_extract_rm_anova.md) | ✅ done |
| 07 | [07_extract_wilcoxon.md](statistics_refactor/07_extract_wilcoxon.md) | ✅ done |
| 08a | [08a_extract_cluster_perm_move.md](statistics_refactor/08a_extract_cluster_perm_move.md) | **NEXT** |
| 08b | [08b_extract_cluster_perm_cleanup.md](statistics_refactor/08b_extract_cluster_perm_cleanup.md) | pending |
| 09 | [09_extract_ttest_main_loop.md](statistics_refactor/09_extract_ttest_main_loop.md) | pending |
| 10 | [10_extract_validation_and_implicit_anova.md](statistics_refactor/10_extract_validation_and_implicit_anova.md) | pending |
| 11 | [11_facade_and_cleanup.md](statistics_refactor/11_facade_and_cleanup.md) | pending |

After each PR: mark card ✅ in this table, set **NEXT** on the following row.

## Shared docs (read on demand)

- [VERIFY.md](statistics_refactor/VERIFY.md) — commands after every PR
- [CONTRACT.md](statistics_refactor/CONTRACT.md) — result shapes agents must not break (~30 lines)
- `.grok/rules/naming-and-stats-refactor.md` — rename map
- [_archive_full_spec.md](statistics_refactor/_archive_full_spec.md) — **do not read** unless stuck; old 600-line spec

## Session rule

**One card = one session = one PR.** Max 2 `grep`/`read` spans in `statistics.py` unless the card says otherwise (08a allows 3).