# PR-08: Extract Cluster permutation branch

**Status**: NEXT | **Depends on**: 07 | **Max production diff**: ~200 LOC moved

## Goal

Move cluster perm block to `brainwash_stats/formal_tests/cluster_perm.py`. **Remove DEBUG `print` statements** during move (only allowed cleanup).

## Read (one branch only)

```sh
grep -n "Cluster permutation test" statistics.py
```

Read entire `# --- Cluster` section through its `return` (~200 lines).

## Steps

1. `run_cluster_permutation(...) -> dict`.
2. Delete `print(f"DEBUG compute_statistical_comparison...` lines in moved code.
3. `pytest.importorskip("mne")` in any new cluster test.
4. Optional: cluster smoke test marked skip if no mne.

## Do NOT

- Change cluster statistics or `n_unit` forcing logic.
- Read main t-test loop.

## Verify

[VERIFY.md](VERIFY.md)

## Next

→ [09_extract_ttest_main_loop.md](09_extract_ttest_main_loop.md)