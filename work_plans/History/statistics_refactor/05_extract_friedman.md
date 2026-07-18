# PR-05: Extract Friedman branch

**Status**: ✅ DONE | **Depends on**: 04 | **Max production diff**: ~80 LOC moved

## Goal

Cut/paste the Friedman omnibus block into `brainwash_stats/formal_tests/friedman.py`. Wire with early `return` from dispatcher.

## Read (one branch only)

```sh
grep -n "Friedman chi-square" statistics.py
```

Read from `# --- Friedman` through its `return {"results": fm_results, ...}` (~80 lines).

Also read: imports used in that span only.

## Steps

1. Create `brainwash_stats/formal_tests/friedman.py` with `run_friedman_omnibus(...) -> dict` — **same logic**, explicit parameters (no dataclass).
2. Pass in: `shown_groups`, `shown_sets`, `g1`, accessor, `n_unit`, `norm`, `amp`, `slope`, `fdr`, `get_group_testset_means_fn`, `use_implicit`.
3. Replace inline block with `return run_friedman_omnibus(...)`.
4. Add **one** characterization test only if PR fails without coverage (paired fixture: 1 group, 3 test sets).

## Do NOT

- Read Wilcoxon / Cluster / t-test branches.
- Change Friedman statistics.
- Use a dispatch registry.

## Verify

[VERIFY.md](VERIFY.md)

## Done when

- [ ] Friedman block gone from dispatcher
- [ ] Pytest green (5+ tests if you added one)

## Next

→ [06_extract_rm_anova.md](06_extract_rm_anova.md)