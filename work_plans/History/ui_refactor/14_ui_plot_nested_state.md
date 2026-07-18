# PR-14: ui_plot nested uistate cleanup

**Status**: DONE | **Depends on**: PR-13

## Goal

Remove flat `getattr(self.uistate, "experiment_type", …)` fallbacks in `ui_plot.py`; use nested `experiment` / `stat_test` / `plot` paths.

## Verify

```sh
uv run pytest src/lib/ -q
```