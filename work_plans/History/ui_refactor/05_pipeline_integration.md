# PR-05: Pipeline integration pytest

**Status**: DONE | **Depends on**: PR-04 (can parallelize after PR-01)

## Goal

Promote `src/test_parse_click.py` headless steps into `src/lib/test_pipeline_integration.py`.

## Tasks

1. Extract step functions from `test_parse_click.py` into pytest tests
2. Use `src/lib/test_data/` fixtures (ABF/CSV minimum)
3. Skip tests gracefully when fixture files missing (`pytest.importorskip` or `xfail`)
4. Keep standalone `test_parse_click.py` as optional manual runner or thin wrapper

## Forbidden

- Requiring `~/Documents/Brainwash Projects` in CI
- Qt / QApplication

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py -q
```

## Next

→ [06_app_context_facade.md](06_app_context_facade.md)