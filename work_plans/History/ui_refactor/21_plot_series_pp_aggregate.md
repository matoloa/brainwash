# PR-21: plot_series PP PPR + stim aggregate

**Status**: DONE | **Depends on**: PR-20

## Goal

Extract PP recording PPR and stim aggregate descriptors into `plot_series.py`.

## Verify

```sh
uv run pytest src/lib/test_plot_series.py src/lib/ -q
```