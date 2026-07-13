# PR-33: graphRefresh PP group label helpers (narrow)

**Status**: pending | **Depends on**: PR-32

## Goal

Extract **pure** label assembly from `graphRefresh` PP group-tick block (~907–938 in [ui_plot.py](../../src/lib/ui_plot.py)). Bar `patches` introspection stays in view.

## Scope

Add to [plot_model.py](../../src/lib/brainwash_ui/plot_model.py) or [plot_series.py](../../src/lib/brainwash_ui/plot_series.py):

| Pure API | Purpose |
|----------|---------|
| `pp_group_tick_from_bar_center(x_center, bar_width)` | `round(x_center)` integer tick |
| `pp_group_legend_map(entries)` | `(group_name, x_int)` list from pre-collected bar metadata |

`UIplot.graphRefresh` collects bar centers from artists → calls pure helper → sets xticks.

**Out of scope:** moving `ax.axhline` grid drawing; PP recording-view ticks (already in `plot_series`).

## Tests

- [test_plot_model.py](../../src/lib/test_plot_model.py) or new `test_pp_group_labels.py`

## Verify

```sh
uv run pytest src/lib/test_plot_model.py src/lib/ -q
```