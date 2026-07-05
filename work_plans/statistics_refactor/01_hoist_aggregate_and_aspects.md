# PR-01: Hoist aggregate + aspect columns (in-place)

**Status**: NEXT | **Depends on**: 00 | **Max production diff**: ~80 LOC

## Goal

Move nested `_aggregate_to_unit_level` and duplicated aspect-column tuples to **module level** in `statistics.py`. No renames yet except `_aspect_measurement_columns`. No new package.

## Read (grep only — do not read whole file)

```sh
# In statistics.py only:
grep -n "_aggregate_to_unit_level\|aspects.append\|EPSP_amp_norm" statistics.py
```

Read spans: nested `def _aggregate_to_unit_level` (~20 lines) + one `aspects.append` block (~10 lines).

## Steps

1. Copy nested `_aggregate_to_unit_level` to module level (below `_bh_fdr`, above `ttest_per_sweep`). Keep same body.
2. Add `_aspect_measurement_columns(amp, slope, norm) -> list[tuple[str, str]]` returning `[("amp", col), ("slope", col), ...]`.
3. Replace **one** duplicate aspect block with a call to `_aspect_measurement_columns` (pick IO implicit ANOVA branch first).
4. Delete the nested `def _aggregate_to_unit_level` inside `compute_statistical_comparison`.
5. Call module-level `_aggregate_to_unit_level` from places that already used the nested name.

## Do NOT

- Rename `_get_obs` (PR-02).
- Create `brainwash_stats/`.
- Touch `ui.py` or test golden values.
- Reorder guards in `compute_statistical_comparison`.

## Verify

[VERIFY.md](VERIFY.md)

## Done when

- [ ] Single module-level `_aggregate_to_unit_level`
- [ ] `_aspect_measurement_columns` exists and used in ≥1 branch
- [ ] 5 pytest smokes green

## Next

→ [02_unify_observation_fetcher.md](02_unify_observation_fetcher.md)