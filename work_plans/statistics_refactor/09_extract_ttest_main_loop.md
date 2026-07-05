# PR-09: Extract main t-test / between-groups loop

**Status**: pending | **Depends on**: 08b | **Max production diff**: ~250 LOC moved

## Goal

Move the main `for sid, tset in shown_sets` loop (unpaired/paired t-test, between-groups ANOVA, assumption tests tail) to `brainwash_stats/formal_tests/ttest_and_between.py`.

## Read

```sh
grep -n "Collect raw p values per family" statistics.py
grep -n "_apply_assumption_tests\|shapiro\|levene" statistics.py
```

Read from `alt = {"two-sided"` through final `return {"results": out_results, "config": config}`.

If Shapiro/Levene block is still inline, extract `_apply_assumption_tests` to `brainwash_stats/assumptions.py` **in this PR** only.

## Steps

1. Extract assumption helper if still inline.
2. `run_main_test_set_loop(...) -> dict` with same parameters as today uses locally.
3. Leave `compute_statistical_comparison` as: validate → early returns → delegate to extracted modules.
4. Add smoke test for paired t-test only if missing.

## Do NOT

- Change t-test / ANOVA math.
- Introduce `MODE_HANDLERS` registry.

## Verify

[VERIFY.md](VERIFY.md)

## Next

→ [10_extract_validation_and_implicit_anova.md](10_extract_validation_and_implicit_anova.md)