# PR-08b: Cluster perm — remove DEBUG prints

**Status**: ✅ DONE | **Depends on**: 08a | **Max production diff**: ~10 LOC deleted

## Goal

Remove DEBUG `print` statements from `brainwash_stats/formal_tests/cluster_perm.py` only. This is the **only allowed cleanup** during the refactor.

## Read (one file only)

`brainwash_stats/formal_tests/cluster_perm.py`

## Steps

1. Delete the six DEBUG lines (patterns):
   - `print(f"DEBUG compute_statistical_comparison: entered Cluster perm. ...`
   - `print("DEBUG: MNE imported successfully")`
   - `print("DEBUG: MNE ImportError")`
   - `print(f"DEBUG: MNE import failed: ...`
   - `print(f"DEBUG compute: shown_sets=...`
   - `print(f"DEBUG cluster between ...`
2. **Keep** error-path prints (`Cluster between error on`, `Cluster paired error on`) and `warnings.warn` calls — out of scope unless user asks.

## Do NOT

- Change logic, signatures, dispatcher wiring, or config shape.
- Touch `statistics.py` except if a stray DEBUG print was left behind (should not happen after 08a).

## Verify

[VERIFY.md](VERIFY.md)

## Next

→ [09_extract_ttest_main_loop.md](09_extract_ttest_main_loop.md)