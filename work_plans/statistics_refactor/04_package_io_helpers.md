# PR-04: Package — IO helpers

**Status**: pending | **Depends on**: 03 | **Max production diff**: ~200 LOC moved

## Goal

Move top-of-file IO functions into `brainwash_stats/io/`. Preserve `config["type"] == "IO regression"` contract ([CONTRACT.md](CONTRACT.md)).

## Read

- `_get_io_xy_pairs` (full function)
- `_compute_io_regression_internal` (full function)
- Early IO guard in `compute_statistical_comparison` (`if is_io and use_implicit`) — **10 lines only**

## Steps

1. Create `brainwash_stats/io/xy_pairs.py` — move `_get_io_xy_pairs`.
2. Create `brainwash_stats/io/regression.py` — move `_compute_io_regression_internal`; import xy helper from same package.
3. Re-import both into `statistics.py` (same private names for minimal diff).
4. Confirm early IO guard still calls `_compute_io_regression_internal` **before** implicit ANOVA block.

## Do NOT

- Reorder L504-style IO guard vs implicit ANOVA.
- Pass `uistate` refactors in `ui.py`.
- Extract implicit ANOVA branch (PR-10).

## Verify

[VERIFY.md](VERIFY.md) — IO smoke test must stay green.

## Done when

- [ ] IO regression test passes
- [ ] No IO logic left at top of `statistics.py` except imports + guard call

## Next

→ [05_extract_friedman.md](05_extract_friedman.md)