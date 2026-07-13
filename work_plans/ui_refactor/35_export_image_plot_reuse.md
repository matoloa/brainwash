# PR-35: export_image plot reuse

**Status**: pending | **Depends on**: PR-34

## Goal

Deduplicate layout/series logic in [export_image.py](../../src/lib/export_image.py) (848 LOC) by delegating to existing `brainwash_ui` helpers where duplicated.

## Scope

Audit `export_image.py` for duplicates of:

- `plot_model.output_axis_ylabels`, `output_legend_locations`
- `plot_series.compute_ppr`, `pp_overlay_x_map`, `group_mean_plots_for_df`
- IO regression via `plot_series.io_*`

Replace inline copies with imports; **no** export format or dialog behavior changes.

## Tests

- Extend existing export tests if any; otherwise add minimal pure-helper smoke in [test_plot_series.py](../../src/lib/test_plot_series.py) for any new shared extraction
- Manual smoke only if user requests (image pixel diff not in CI)

## Verify

```sh
uv run pytest src/lib/ -q
```

## Forbidden

Screenshot golden tests; new export formats.