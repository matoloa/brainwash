# Statistics refactor — micro-plans

Each `NN_*.md` file is a **complete session brief**. Agents read **only** the current `NEXT` card from [../plan_statistics_refactor.md](../plan_statistics_refactor.md).

| File | ~lines | Purpose |
|------|--------|---------|
| `00_DONE_bootstrap.md` | 20 | Tests landed |
| `01`–`02` | 40 each | In-place helper hoist (no new package) |
| `03`–`04` | 50 each | Create `brainwash_stats/` package |
| `05`–`09` | 45 each | One statistical test branch per PR |
| `10`–`11` | 50 each | Validation + facade |
| `VERIFY.md` | 15 | Post-PR commands |
| `CONTRACT.md` | 35 | Output shape invariants |
| `_archive_full_spec.md` | 600+ | Legacy detail — **blocked by default** |

**Forbidden in all PRs**: `StatContext`, `ComparisonMode`, `MODE_HANDLERS`, `ui.py` edits, guard reordering.