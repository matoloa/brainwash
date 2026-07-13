# PR-10: DataFrameMixin instance injection

**Status**: DONE | **Depends on**: PR-09

## Goal

Remove module-level singleton injection from `ui_data_frames.py`. `DataFrameMixin` uses `self.uistate`, `self.config`, `self.uiplot`.

## Tasks

1. Replace module-level refs in `DataFrameMixin` with `self.*`
2. Delete `ui_data_frames.uistate = …` wiring block in `ui.py`

## Forbidden

- Changing pipeline / cache behavior
- Migrating remaining mixins in this PR

## Verify

```sh
uv run pytest src/lib/test_pipeline_integration.py src/lib/ -q
```

## Next

→ [11_host_protocols.md](11_host_protocols.md)