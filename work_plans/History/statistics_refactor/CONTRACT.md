# Result contract (do not change during refactor)

## Success shape

```python
{"results": [result_row, ...], "config": {...}}
```

## Error shapes

```python
{"error": str, "results": []}
{"not_implemented": str, "results": []}
```

## Critical invariant (IO)

`experiment_type="io"` + empty test sets → early return with `config["type"] == "IO regression"` (never implicit ANOVA today). Test: `test_io_empty_testsets_returns_io_regression_not_anova`.

## config keys UI may read

| Case | `config["type"]` or `config["test_type"]` |
|------|---------------------------------------------|
| IO regression | `"IO regression"` + `x_col`, `y_col`, `group_ns`, `implicit_testset` |
| Main tests | `"t-test"` / `"ANOVA"` / etc. via `type` or `test_type` |
| Cluster | `test_type: "Cluster perm."`, `note`, `n_unit: "recording"` |

## Public entrypoints (unchanged)

- `compute_statistical_comparison(...)` — same signature
- `ttest_per_sweep(...)`
- `ui.py`: `from . import statistics as stats`