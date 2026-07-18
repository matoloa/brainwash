# PR-44: refresh bus pytest-qt coalesce test

**Status**: ✅ done | **Depends on**: PR-42

## Goal

Characterize event-loop coalescing with `test_refresh_bus_qt.py` (spy mixin + `qtbot.wait`).

## Verify

```sh
uv run pytest src/brainwash/test_refresh_bus_qt.py -q
```