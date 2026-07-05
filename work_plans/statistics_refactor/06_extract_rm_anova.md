# PR-06: Extract repeated-measures ANOVA branch

**Status**: NEXT | **Depends on**: 05 | **Max production diff**: ~90 LOC moved

## Goal

Extract RM ANOVA omnibus block to `brainwash_stats/formal_tests/anova_rm.py`.

## Read (one branch only)

```sh
grep -n "Repeated-measures ANOVA path" statistics.py
```

Read through its `return {"results": rm_results, ...}` (~90 lines).

## Steps

1. `run_repeated_measures_anova(...) -> dict` in `anova_rm.py`.
2. Wire early `return` from `compute_statistical_comparison`.
3. Optional: add one RM ANOVA smoke test (1 group, 2 test sets) if not covered.

## Do NOT

- Extract between-groups ANOVA in the main loop (PR-09).
- Touch guard block at top (`elif test_type == "ANOVA" and len(shown_groups) == 1`).

## Verify

[VERIFY.md](VERIFY.md)

## Next

→ [07_extract_wilcoxon.md](07_extract_wilcoxon.md)