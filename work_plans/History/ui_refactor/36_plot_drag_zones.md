# PR-36: plot_drag zone geometry

**Status**: ✅ done | **Depends on**: PR-35

## Goal

Extract amp/slope drag-zone math from `UIstate.updateAmpZone` / `updateSlopeZone` into pure `brainwash_ui/plot_drag.py`.

## Scope

- `amp_move_zone`, `slope_drag_state`, `point_in_zone`
- Delegate `ui_state_classes.py` zone updates
- Use `point_in_zone` in `ui_interactive.eventMouseover`

## Tests

- [test_plot_drag.py](../../src/lib/test_plot_drag.py)

## Verify

```sh
uv run pytest src/lib/ -q
```

## Forbidden

Matplotlib artist creation; drag event handler rewrites.