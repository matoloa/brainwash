# PR-37: Output sweep drag selection fix

**Status**: ✅ done (commit 38) | **Depends on**: PR-36

## Goal

Fix `KeyError: -1` when click-drag selecting sweeps on Output canvas.

## Root cause

`connectDragRelease` used `line.get_xdata()[-1]` on pandas Series x-data and included non-sweep artists (fills, markers).

## Fix

Filter `SWEEP_OUTPUT_ASPECTS`, prefer `dict_rec_show`, coerce via `np.asarray`.

## Verify

Manual: click-drag sweep range on Output. `uv run pytest src/lib/ -q`