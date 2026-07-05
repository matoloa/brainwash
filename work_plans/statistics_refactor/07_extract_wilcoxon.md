# PR-07: Extract Wilcoxon branch

**Status**: pending | **Depends on**: 06 | **Max production diff**: ~120 LOC moved

## Goal

Move Wilcoxon paired + one-sample paths to `brainwash_stats/formal_tests/wilcoxon.py`.

## Read (one branch only)

```sh
grep -n "Wilcoxon signed-rank path" statistics.py
```

Read through the branch's final `return` (~120 lines).

## Steps

1. `run_wilcoxon_tests(...) -> dict` — preserve paired vs one-sample split inside module.
2. Replace inline block with `return run_wilcoxon_tests(...)`.
3. Optional smoke test: 1 group, 2 test sets, paired.

## Do NOT

- Read cluster or main t-test loop.
- Unify FDR implementations (later optional PR).

## Verify

[VERIFY.md](VERIFY.md)

## Next

→ [08_extract_cluster_perm.md](08_extract_cluster_perm.md)