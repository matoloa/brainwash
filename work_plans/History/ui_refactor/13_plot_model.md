# PR-13: UIplot model/view split (phase 1)

**Status**: DONE | **Depends on**: PR-12

## Goal

Extract pure plot descriptors to `brainwash_ui/plot_model.py`. `UIplot` view methods render specs (matplotlib/Qt unchanged for now).

## Scope

- `TestMarkerSpec` + `build_test_marker_specs` (formal test */ns markers)
- `p_value_color_alpha` (heatmap dots)
- `level_storage_key` / `display_label_from_key` (group artist keys)
- `test_plot_model.py` characterization tests
- `show_test_markers` delegates to plot_model; uses nested `uistate.stat_test`

## Deferred

- Full `addRow` / `graphRefresh` model extraction
- Agg-backend render integration test

## Verify

```sh
uv run pytest src/lib/test_plot_model.py src/lib/ -q
```

## Next

Human review: further `ui_plot.py` decomposition or real `.abf` CI fixtures.