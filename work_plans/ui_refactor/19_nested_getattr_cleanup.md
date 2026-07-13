# PR-19: nested getattr cleanup

**Status**: DONE | **Depends on**: PR-18

## Goal

Replace defensive `getattr(self.uistate.plot, …)` with direct nested access or `get_axis` / `uiplot.get_axis`.

## Verify

```sh
uv run pytest src/lib/ -q
```