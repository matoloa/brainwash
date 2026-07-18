# Naming and statistics refactor (project rules)

## Human-readable names (default)

- Prefer names a lab scientist or new contributor understands without reading 500 lines of context.
- Rename **conservatively** when confusion causes bugs (stdlib collisions, duplicate nested helpers, cryptic abbreviations). One rename family per PR.
- **Stable public API** (do not rename without explicit user approval): `compute_statistical_comparison`, `ttest_per_sweep`, `from . import statistics as stats` in `ui.py`.
- **Safe to rename** during refactor: private helpers (`_get_obs`, nested closures), internal package paths, test-only loaders.

## Statistics refactor scope

- **Index**: `work_plans/plan_statistics_refactor.md` (table only).
- **Session brief**: one file `work_plans/statistics_refactor/NN_*.md` marked **NEXT**.
- **Blocked**: `work_plans/statistics_refactor/_archive_full_spec.md` unless pytest fails after revert.
- **Cancelled**: statusbar / `ui.py` (`History/plan_statusbar_ui.md`).
- **Never** `from statistics import …` in tests — use `load_brainwash_statistics.load_brainwash_statistics_module()`.

## Target renames (apply during refactor PRs)

| Current | Preferred | PR |
|---------|-----------|-----|
| `_get_obs` (nested ×2) | `_fetch_group_testset_observations` | 1 |
| `_make_get_obs` | `_make_group_testset_observation_accessor` | 1 |
| `_aggregate_to_unit_level` | keep (already clear) | — |
| aspect `("amp", col)` blocks | `_aspect_measurement_columns` | 1 |
| package dir `stats/` | `brainwash_stats/` (avoids confusion with scipy/stats) | 2 |
| importlib hack inline in tests | `load_brainwash_statistics.py` | done |

## Naming style

- Functions: verb phrases (`fetch_`, `aggregate_`, `compute_`, `run_`).
- Modules: domain nouns (`brainwash_stats`, `formal_tests`, `io_regression`).
- Avoid: single-letter closures, `internal`, `helper2`, plan phase names in identifiers.