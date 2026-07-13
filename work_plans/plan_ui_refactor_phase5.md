# UI Refactor Phase V — Agent index

> **Status**: ✅ Complete (PR-36). Branch: `ui-refactor/phase0-3`.
> Phase IV: [plan_ui_refactor_phase4.md](plan_ui_refactor_phase4.md) ✅

## Goal

Low-risk pure extractions around event-plot interaction geometry and regression guards. No package rename, event bus, or full `UIsub` split.

## Progress

| PR | Card | Status |
|----|------|--------|
| 36 | [ui_refactor/36_plot_drag_zones.md](ui_refactor/36_plot_drag_zones.md) | ✅ done |

## Verified baseline (post Phase IV + commit 35)

| Metric | Value |
|--------|-------|
| Tests | 204 passed, 1 skipped |
| `brainwash_ui/` | 9 modules (incl. `plot_drag`) |
| Bugfix | `eventMouseover` uses `uistate.plot` for drag zones (commit 35) |

## Deferred (Phase VI+)

| Item | Reason |
|------|--------|
| `src/brainwash` → `src/brainwash` package rename | Agent churn |
| Event bus / `graphRefresh` dedup | Needs call-graph map |
| Full `ui_interactive` drag-core extraction | Artist-handle coupled |
| Full `UIsub` decomposition | Low ROI |

## Forbidden (unchanged)

Stats dispatcher guards, public stats API renames, distribution builds, deleting `analysis_v1/v2`.