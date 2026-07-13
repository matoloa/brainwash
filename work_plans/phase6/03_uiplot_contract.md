# Phase 7a: UIplot host contract (scope only — not HIGH RISK)

**Status**: scope doc | **Implementation**: deferred incremental PRs

## Problem

`ui_plot.UIplot` (~2400 LOC) is a second runtime coordinator alongside `UIsub`. Mixins call `self.uiplot.*` for all matplotlib work.

## Boundaries (do not break)

| Owner | Responsibility |
|-------|----------------|
| `UIsub` + mixins | When to plot, cache invalidation, `graphRefresh` |
| `UIplot` | Artist create/remove, axis limits, hit zones, `addRow`/`unPlot` |
| `brainwash_ui.plot_model` | Pure specs: markers, heatmap layout, axis mode |
| `brainwash_ui.plot_series` | Pure series math: PPR, aggregates |
| `brainwash_ui.plot_drag` | Drag-zone geometry, `artist_xdata` |

## Incremental extraction targets (7b+, each HIGH RISK)

1. `show_test_markers` descriptor → already uses `plot_model` — extend pattern
2. Group line specs → `plot_model` (no artist creation in pure layer)
3. `addRow` data assembly → `recording_pipeline` or `plot_series` before UIplot draws

## Forbidden in 7b PRs

- Rewriting `UIplot` as non-class module in one shot
- Moving `uistate.plot` session attrs off `PlotSession` without migration plan