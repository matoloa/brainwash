# PR-09: SelectionMixin instance injection

**Status**: DONE | **Depends on**: PR-08

## Goal

Remove module-level singleton injection from `ui_selection.py`. `SelectionMixin` uses `self.uistate`, `self.config`, `self.uiplot`.

## Tasks

1. Replace module-level refs in `SelectionMixin` with `self.*`
2. Delete `ui_selection.uistate = …` wiring block in `ui.py`

## Forbidden

- Changing selection / visibility behavior
- Migrating other mixins in this PR

## Verify

```sh
uv run pytest src/lib/test_view_state.py src/lib/ -q
```

## Next

→ [10_data_frames_injection.md](10_data_frames_injection.md)