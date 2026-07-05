# PR-02: Unify observation fetcher (in-place)

**Status**: ✅ DONE | **Depends on**: 01 | **Max production diff**: ~100 LOC

## Goal

Replace **two** nested `_get_obs` closures with one module-level accessor factory. Human-readable names.

## Read (grep only)

```sh
grep -n "def _get_obs" statistics.py
```

Read both nested definitions (~8 lines each) and their call sites in the same branch.

## Steps

1. Add `_make_group_testset_observation_accessor(get_group_testset_means_fn, use_implicit)` returning a callable.
2. Add thin wrapper `_fetch_group_testset_observations(accessor, g, tset, col, per_sweep=False)` if it clarifies call sites.
3. At start of `compute_statistical_comparison` body (after `use_implicit` is known), build **one** accessor; pass it into branches.
4. Delete both nested `def _get_obs`.
5. Replace remaining `aspects.append` blocks with `_aspect_measurement_columns` where still duplicated (optional in this PR if ≤3 sites).

## Renames (this PR only)

| Old | New |
|-----|-----|
| nested `_get_obs` | via `_make_group_testset_observation_accessor` |
| (optional) inline lambda calls | `_fetch_group_testset_observations` |

## Do NOT

- Move code to `brainwash_stats/` (PR-03).
- Change `get_group_testset_means_fn` signature.
- Extract test-type branches.

## Verify

[VERIFY.md](VERIFY.md)

## Done when

- [ ] Zero nested `def _get_obs` in `statistics.py`
- [ ] 5 pytest smokes green

## Next

→ [03_package_data_and_fdr.md](03_package_data_and_fdr.md)