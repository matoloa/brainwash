# UI Refactor Phase III — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`. Manual smoke PASS (2026-07-13).
> Phase II: [plan_ui_refactor_phase2.md](plan_ui_refactor_phase2.md) ✅

## Progress

| PR | Card | Status |
|----|------|--------|
| 26 | [ui_refactor/26_ppr_dedupe_interactive.md](ui_refactor/26_ppr_dedupe_interactive.md) | ✅ done |
| 27 | pending — `updateStimLines` position helpers | pending |
| 28 | pending — `ui_data_frames` output path pure helpers | pending |

## Baseline (post Phase II + smoke)

- `uv run pytest src/lib/ -q` → 166 passed, 13 skipped
- `ui_plot.py` 2462 LOC; `brainwash_ui/` ~947 LOC
- No real `.abf` in repo (synthetic + golden parquet only)

## Deferred

Package rename, event bus, `sample_overlay`/`ui_interactive` drag core, `export_image.py`, full `UIsub` split.