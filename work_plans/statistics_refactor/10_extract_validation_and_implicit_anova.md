# PR-10: Extract validation + latent implicit ANOVA

**Status**: pending | **Depends on**: 09 | **Max production diff**: ~150 LOC moved

## Goal

Move top-of-dispatcher guards and the **latent** implicit IO ANOVA block into modules. **Keep guard order identical.**

## Read

1. `compute_statistical_comparison` from signature through `if is_io and use_implicit` return (~70 lines).
2. `# Implicit ANOVA for IO` block through its early `return` (~120 lines).

## Steps

1. `brainwash_stats/validation.py`: `validate_comparison_inputs(...) -> dict | None` — returns error dict or None; caller unchanged.
2. `brainwash_stats/io/implicit_anova.py`: `run_io_implicit_anova(...) -> dict` — **dead path today** when `experiment_type=="io"`; extract as-is per [CONTRACT.md](CONTRACT.md).
3. Dispatcher becomes: validate → IO regression early return → implicit ANOVA early return → …existing extracted tests…

## Do NOT

- Activate implicit ANOVA for IO (do not swap guard order).
- Add `StatContext` / `ComparisonMode`.
- Edit `ui.py`.

## Verify

[VERIFY.md](VERIFY.md) — `test_io_empty_testsets_returns_io_regression_not_anova` must pass.

## Next

→ [11_facade_and_cleanup.md](11_facade_and_cleanup.md)