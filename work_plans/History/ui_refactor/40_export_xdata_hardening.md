# PR-40: export_image + x_axis xdata hardening

**Status**: ✅ done | **Depends on**: package rename (phase 7)

## Goal

Use `plot_drag.artist_xdata` / `artist_ydata` in remaining export and xlim paths that still call `get_xdata()` directly.

## Scope

- `export_image.py` group line replay + sample inset
- `ui_state_classes.py` PP rec xlim + IO xlim

## Tests

Existing `test_plot_drag.py`; full suite green.

## Verify

```sh
uv run pytest src/brainwash/ -q
```