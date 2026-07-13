# UI Refactor Phase III — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`. Manual smoke PASS (2026-07-13).
> Phase II: [plan_ui_refactor_phase2.md](plan_ui_refactor_phase2.md) ✅

## Progress

| PR | Card | Status |
|----|------|--------|
| 26 | [ui_refactor/26_ppr_dedupe_interactive.md](ui_refactor/26_ppr_dedupe_interactive.md) | ✅ done |
| 27 | [ui_refactor/27_update_stim_lines.md](ui_refactor/27_update_stim_lines.md) | ✅ done |
| 28 | [ui_refactor/28_recording_cache_abf_tests.md](ui_refactor/28_recording_cache_abf_tests.md) | ✅ done |

## Baseline

- Real ABF available locally as `.abf.gitkeep` (gitignored `*.abf`); `resolve_test_abf` discovers both
- `uv run pytest src/lib/ -q` — run after each PR

## Deferred

Package rename, event bus, `sample_overlay`/`ui_interactive` drag core, `export_image.py`, full `UIsub` split.