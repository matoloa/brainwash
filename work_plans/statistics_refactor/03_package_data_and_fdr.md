# PR-03: Package — data + FDR helpers

**Status**: ✅ DONE | **Depends on**: 02 | **Max production diff**: ~120 LOC moved

## Goal

Create `src/lib/brainwash_stats/` and move pure helpers. `statistics.py` re-imports them — **zero** `ui.py` import changes.

## Read

- Module-level helpers in `statistics.py`: `_aggregate_to_unit_level`, `_aspect_measurement_columns`, `_make_group_testset_observation_accessor`, `_bh_fdr`
- Do **not** read `compute_statistical_comparison` branches.

## Steps

1. Create `brainwash_stats/__init__.py` (empty or docstring only).
2. Move to `brainwash_stats/data.py`: aggregate + aspect + observation accessor helpers (keep names).
3. Move to `brainwash_stats/fdr.py`: `_bh_fdr` (export as `bh_fdr` internally; re-export as `_bh_fdr` from facade).
4. In `statistics.py`: `from .brainwash_stats.data import ...` and `from .brainwash_stats.fdr import _bh_fdr` (or alias).
5. Delete moved bodies from `statistics.py`.

## Do NOT

- Move IO helpers yet (PR-04).
- Move test branches.
- Add `StatContext` or enums.

## Verify

[VERIFY.md](VERIFY.md) + flake8 on `brainwash_stats/`

## Done when

- [ ] `brainwash_stats/data.py` and `fdr.py` exist
- [ ] `statistics.py` imports helpers; behavior unchanged
- [ ] 5 pytest smokes green

## Next

→ [04_package_io_helpers.md](04_package_io_helpers.md)