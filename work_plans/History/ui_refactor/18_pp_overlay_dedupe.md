# PR-18: pp_overlay_x_map dedupe

**Status**: DONE | **Depends on**: PR-17

## Goal

Replace inline `x_val_map` in `addRow` and `updateOutLineFromDf` with `plot_series.pp_overlay_x_map`.

## Verify

```sh
uv run pytest src/lib/test_plot_series.py src/lib/ -q
```