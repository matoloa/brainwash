# PR-22: plot_layout — axis labels + PP grid

**Status**: DONE | **Depends on**: PR-21

## Goal

Extract `output_axis_ylabels` and `pp_reference_grid_y_values` into `plot_model.py`.

## Verify

```sh
uv run pytest src/lib/test_plot_model.py src/lib/ -q
```