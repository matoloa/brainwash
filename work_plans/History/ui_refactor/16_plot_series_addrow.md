# PR-16: plot_series — addRow / addGroup / graphRefresh extraction

**Status**: DONE | **Depends on**: PR-15

## Goal

Extract IO regression, group mean series, and PP bar layout from `ui_plot.py` into `brainwash_ui/plot_series.py`.

## Scope

- `io_axis_columns`, `compute_io_regression`, `extract_group_mean_series`
- `pp_bar_layout`, `pp_recording_view_ticks`, `group_mean_plots_for_df`
- `addRow` IO path, `addGroup` IO/PP/sweep means, `plot_group_lines`, `graphRefresh` PP ticks
- `test_plot_series.py` (+ Agg render smoke)

## Verify

```sh
uv run pytest src/lib/test_plot_series.py src/lib/ -q
```