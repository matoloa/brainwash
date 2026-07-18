# PR-28: recording_cache + real ABF pipeline tests

**Status**: DONE | **Depends on**: PR-27

## Goal

- `brainwash_ui/recording_cache.py` for `get_dfoutput` paths
- `resolve_test_abf` for local `.abf` / `.abf.gitkeep` fixtures
- Full pipeline characterization when ABF present

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py src/lib/test_recording_cache.py src/lib/ -q
```