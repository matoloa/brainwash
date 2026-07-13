# PR-31: recording_cache — mean/filter/timepoints paths

**Status**: NEXT | **Depends on**: PR-30

## Goal

Extend [recording_cache.py](../../src/lib/brainwash_ui/recording_cache.py) beyond `get_dfoutput` so all parquet cache key/path construction in `ui_data_frames.py` uses one pure module.

## Scope

| Pure helper | Replaces inline in `ui_data_frames` |
|-------------|-------------------------------------|
| `mean_parquet_path(cache_folder, rec)` | `{cache}/{rec}_mean.parquet` |
| `filter_parquet_path(cache_folder, rec)` | `{cache}/{rec}_filter.parquet` |
| `timepoints_parquet_path(timepoints_folder, rec)` | `{timepoints}/{rec}.parquet` |
| `group_mean_parquet_path(cache_folder, group_ID, level_suffix)` | `group_{id}{suffix}_mean.parquet` |
| `cache_key_for_artifact(name)` | `"timepoints"`, `"output"`, etc. if duplicated |

Keep mixin methods as thin delegates. **No** cache invalidation logic changes.

## Tests

- Extend [test_recording_cache.py](../../src/lib/test_recording_cache.py)

## Verify

```sh
uv run pytest src/lib/test_recording_cache.py src/lib/ -q
```

## Forbidden

Changing `build_dfoutput` / `find_events` behavior; moving caches off mixin.