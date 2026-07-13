# UI Refactor Phase III — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`. Manual smoke PASS (2026-07-13).
> Phase II: [plan_ui_refactor_phase2.md](plan_ui_refactor_phase2.md) ✅

## Progress

| PR | Card | Status |
|----|------|--------|
| 26 | [ui_refactor/26_ppr_dedupe_interactive.md](ui_refactor/26_ppr_dedupe_interactive.md) | ✅ done |
| 27 | [ui_refactor/27_update_stim_lines.md](ui_refactor/27_update_stim_lines.md) | ✅ done |
| 28 | [ui_refactor/28_recording_cache_abf_tests.md](ui_refactor/28_recording_cache_abf_tests.md) | ✅ done |
| 29 | [ui_refactor/29_abf_golden_parquet.md](ui_refactor/29_abf_golden_parquet.md) | ✅ done |
| 30 | [ui_refactor/30_data_source_candidates.md](ui_refactor/30_data_source_candidates.md) | ✅ done |

## Baseline

- `data_source/manifest.json` — 14 Concatenate000.abf candidates (local; `*.abf` gitignored)
- Legacy `test_data` `.abf.gitkeep` still supported via `abf_path_for_parse`
- `uv run pytest src/lib/ -q` — run after each PR

## Deferred

Package rename, event bus, `sample_overlay`/`ui_interactive` drag core, `export_image.py`, full `UIsub` split.