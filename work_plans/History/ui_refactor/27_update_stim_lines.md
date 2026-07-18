# PR-27: updateStimLines pure helpers

**Status**: DONE | **Depends on**: PR-26

## Goal

Extract IO scatter/trendline refresh and stim-mode suffix map into `plot_series.py`; delegate from `updateStimLines`.

## Verify

```sh
uv run pytest src/lib/test_plot_series.py src/lib/ -q
```