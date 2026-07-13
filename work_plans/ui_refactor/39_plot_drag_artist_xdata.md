# PR-39: plot_drag artist x/y helpers

**Status**: ✅ done | **Depends on**: PR-37

## Goal

Centralize matplotlib artist x/y coercion in `plot_drag` and use everywhere sweep/mouseover code indexes coordinates.

## Scope

- `artist_xdata`, `artist_ydata`, `artist_xy_first`, `drag_release_line_candidates` in `plot_drag.py`
- Wire `ui_interactive` (mouseoverUpdate, outputMouseover, connectDragRelease, event drag)
- Wire `ui_state_classes.updateDragZones`

## Tests

Extend [test_plot_drag.py](../../src/lib/test_plot_drag.py); remove `test_ui_interactive_drag.py`.

## Verify

```sh
uv run pytest src/lib/ -q
```