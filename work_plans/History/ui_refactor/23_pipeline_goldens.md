# PR-23: pipeline goldens

**Status**: DONE | **Depends on**: PR-22

## Goal

Committed parquet golden + pipeline/plot_stim integration tests (synthetic; no real ABF).

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py src/lib/ -q
```