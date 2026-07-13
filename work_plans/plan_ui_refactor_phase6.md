# UI Refactor Phase VI — Agent index

> **Status**: ✅ Complete (PR-37, PR-39). Branch: `ui-refactor/phase0-3`.
> Phase V: [plan_ui_refactor_phase5.md](plan_ui_refactor_phase5.md) ✅

## Goal

Harden matplotlib/pandas artist indexing and consolidate drag helpers in `plot_drag`.

## Progress

| PR | Card | Status |
|----|------|--------|
| 37 | [ui_refactor/37_output_sweep_drag_fix.md](ui_refactor/37_output_sweep_drag_fix.md) | ✅ done (commit 38) |
| 39 | [ui_refactor/39_plot_drag_artist_xdata.md](ui_refactor/39_plot_drag_artist_xdata.md) | ✅ done |

## Verified baseline

| Metric | Value |
|--------|-------|
| Tests | 207 passed, 1 skipped |
| Bugfixes | drag zones on `uistate.plot` (35); sweep drag KeyError (38) |

## Deferred

Package rename, event bus, full drag-core, `UIsub` split — unchanged from Phase V.