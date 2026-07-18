# PR-20: plot_stim — per-stim descriptors

**Status**: DONE | **Depends on**: PR-19

## Goal

Extract per-stim position math from `addRow` stim loop into `brainwash_ui/plot_stim.py`.

## Verify

```sh
uv run pytest src/lib/test_plot_stim.py src/lib/test_plot_series.py src/lib/ -q
```