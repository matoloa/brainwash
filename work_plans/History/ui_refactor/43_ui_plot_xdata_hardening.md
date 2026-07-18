# PR-43: ui_plot artist xdata hardening

**Status**: ✅ done | **Depends on**: PR-42

## Goal

Use `plot_drag.artist_xdata` / `artist_ydata` in remaining `ui_plot.py` paths (PPR aggregate, updateOutLine, updateOutMean).

## Verify

```sh
uv run pytest src/brainwash/ -q
```