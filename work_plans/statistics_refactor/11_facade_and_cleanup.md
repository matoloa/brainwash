# PR-11: Facade + cleanup

**Status**: pending | **Depends on**: 10 | **Max production diff**: ~100 LOC

## Goal

`statistics.py` becomes a thin facade (≤40 LOC). Dispatcher body lives in `brainwash_stats/dispatcher.py`.

## Read

- Current `compute_statistical_comparison` after PR-10 (should be ~150 LOC).
- `ui.py` line 62 only: `from . import statistics as stats` — confirm unchanged.

## Steps

1. Move remaining `compute_statistical_comparison` body to `brainwash_stats/dispatcher.py`.
2. Replace `statistics.py` with re-exports:

```python
from .brainwash_stats.dispatcher import compute_statistical_comparison
from .brainwash_stats.per_sweep import ttest_per_sweep  # if moved in PR-03/04
from .brainwash_stats.fdr import bh_fdr as _bh_fdr
```

3. Strip legacy comments (`Phase 0`, `v0.16_n_stats`, plan references) from moved modules.
4. Update progress table in [plan_statistics_refactor.md](../plan_statistics_refactor.md) — all ✅.
5. Move [plan_statistics_refactor.md](../plan_statistics_refactor.md) + this folder's cards to `History/` when done.

## Do NOT

- Convert to `MODE_HANDLERS` registry (ordered `if` chain is fine).
- Change public signatures.

## Verify

[VERIFY.md](VERIFY.md)

## Done when

- [ ] `statistics.py` ≤40 LOC
- [ ] All characterization tests green
- [ ] `ui.py` import path unchanged