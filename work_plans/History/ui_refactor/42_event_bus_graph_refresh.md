# PR-42: event bus — graphRefresh coalescing

**Status**: ✅ done | **Depends on**: PR-40

## Goal

Deduplicate `graphRefresh` calls within the same Qt event-loop tick without editing ~44 call sites.

## Scope

- `brainwash_ui/refresh_bus.py` — `GraphRefreshRequest`, `merge_graph_refresh_requests`
- `ui_graph.py` — `request_graph_refresh`, `_flush_pending_graph_refresh`, `_graph_refresh_impl`
- `graphRefresh()` delegates to bus

## Tests

- [test_refresh_bus.py](../../src/brainwash/test_refresh_bus.py)

## Verify

```sh
uv run pytest src/brainwash/ -q
```