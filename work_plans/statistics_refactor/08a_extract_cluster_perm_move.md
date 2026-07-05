# PR-08a: Extract cluster perm (move only)

**Status**: NEXT | **Depends on**: 07 | **Max production diff**: ~205 LOC moved

## Goal

Cut/paste the cluster block into `brainwash_stats/formal_tests/cluster_perm.py`. **Keep all `print` statements** — DEBUG removal is PR-08b.

## Read (3 spans allowed — card overrides default 2-span budget)

```sh
grep -n 'elif test_type == "Cluster perm."' statistics.py   # top guard ~L226
grep -n 'is_cluster = test_type' statistics.py              # n_unit override ~L387
grep -n "Cluster permutation test" statistics.py            # branch ~L436
```

Read each hit through the minimum lines needed. Then read the full `# --- Cluster` section through its `return` (~205 lines).

## Dispatcher coupling (do not move)

1. **Top guard** `elif test_type == "Cluster perm.": pass` — stays in dispatcher; must remain before paired / 2-group guards.
2. **`n_unit` override** at ~L387–389 — stays in dispatcher. Caller passes `n_unit` already forced to `"recording"`. **Do not re-force** inside `run_cluster_permutation`.
3. **`shown_sets` re-filter** — branch rebuilds from `dd_testsets` (requires `show` + `sweeps`). Pass **`dd_testsets`**, not dispatcher-level `shown_sets`.

## Steps

1. Create `brainwash_stats/formal_tests/cluster_perm.py`.
2. Hoist nested closures to module-level privates first: `_extract_cluster_p`, `_to_matrix`.
3. Implement:

```python
def run_cluster_permutation(
    *,
    shown_groups,
    dd_testsets,
    fetch_group_testset_observations,
    n_unit,
    norm,
    amp,
    slope,
    fdr,
    test_type,
    use_implicit,
) -> dict:
```

4. Replace the inline `if test_type == "Cluster perm.":` block with:

```python
if test_type == "Cluster perm.":
    return run_cluster_permutation(
        shown_groups=shown_groups,
        dd_testsets=dd_testsets,
        fetch_group_testset_observations=fetch_group_testset_observations,
        n_unit=n_unit,
        norm=norm,
        amp=amp,
        slope=slope,
        fdr=fdr,
        test_type=test_type,
        use_implicit=use_implicit,
    )
```

5. Add **one** characterization test `test_cluster_perm_between_groups_smoke`:
   - `pytest.importorskip("mne")` at top of test
   - `make_scalar_accessor` with `per_sweep=True` (see `test_statistics_fixtures.py`)
   - 2 groups, 1 test set with ≥2 sweeps
   - Assert no `"error"` key and `config["test_type"] == "Cluster perm."` (see [CONTRACT.md](CONTRACT.md))

## Do NOT

- Remove DEBUG prints (→ 08b).
- Change cluster statistics or move `n_unit` forcing into the module.
- Normalize config to Wilcoxon/Friedman `"type"` key — cluster uses `test_type` per CONTRACT.
- Read the main t-test loop.

## Verify

[VERIFY.md](VERIFY.md) — expect **6 tests** (5 existing + 1 cluster; cluster test skips if MNE not installed).

## Next

→ [08b_extract_cluster_perm_cleanup.md](08b_extract_cluster_perm_cleanup.md)