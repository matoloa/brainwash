# PR-26: PPR dedupe in ui_interactive + ui export

**Status**: DONE | **Depends on**: PR-25

## Goal

Wire `ui_interactive` PP drag overlay and `ui.py` clipboard export to `plot_series.compute_ppr` / `pp_overlay_x_map`.

## Verify

```sh
uv run pytest src/lib/test_plot_series.py src/lib/ -q
```