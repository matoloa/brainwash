# PR-15: Plot model phase 2 (legend + heatmap + axis layout)

**Status**: DONE | **Depends on**: PR-14

## Goal

Extract more `UIplot` layout logic into `brainwash_ui/plot_model.py`; expand pytest-qt wiring tests.

## Scope

- `output_legend_locations`, heatmap column/position helpers, `significant_heatmap_points`
- `output_axis_y_visibility`, `slope_yaxis_on_left` for `oneAxisLeft`
- `test_plot_model.py` + `test_ui_wiring.py` updates

## Verify

```sh
uv run pytest src/lib/test_plot_model.py src/lib/test_ui_wiring.py src/lib/ -q
```