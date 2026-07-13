# PR-29: real ABF golden parquet

**Status**: DONE | **Depends on**: PR-28

## Goal

Committed `test_data/golden/abf_1ch_dfoutput.parquet` from local 1-ch ABF pipeline for headless CI without parsing ABF each run.

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py -q
```