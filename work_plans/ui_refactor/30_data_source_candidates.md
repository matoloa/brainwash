# PR-30: data_source test candidates

**Status**: DONE | **Depends on**: PR-29

## Goal

Wire `data_source/{01..14}/Concatenate000.abf` via `manifest.json`; parametrized smoke runs **characteristic** ids only (`01`, `07`, `14`); golden parquet for `01`.

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py -q
```