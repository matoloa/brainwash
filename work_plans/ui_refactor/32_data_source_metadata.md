# PR-32: data_source manifest metadata + assertions

**Status**: ✅ done | **Depends on**: PR-31

## Goal

Enrich [data_source/manifest.json](../../data_source/manifest.json) with per-candidate metadata and assert it in characteristic pipeline tests — without running all 14 ABFs.

## Scope

Add optional fields per candidate (populate for `01`, `07`, `14` first; others `null` until characterized):

| Field | Example | Test assertion |
|-------|---------|----------------|
| `n_sweeps` | `1080` | `df_raw["sweep"].nunique()` when ABF present |
| `n_stims` | `1` | `dft` row count after `find_events` |
| `notes` | free text | documentation only |

- `characteristic_test_ids` unchanged (`01`, `07`, `14`)
- Extend [test_pipeline_integration.py](../../src/lib/test_pipeline_integration.py): when metadata present + ABF local, assert counts match
- CI without ABF: metadata test reads JSON only; golden parquet tests unchanged

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py src/lib/test_data_source_manifest.py -q
```