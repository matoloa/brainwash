# PR-08: StatTestMixin instance injection

**Status**: DONE | **Depends on**: PR-07

## Goal

Remove module-level `uistate` / `uiplot` injection from `ui_stat_test.py`. `StatTestMixin` uses `self.uistate` and `self.uiplot` set on `UIsub` at construction.

## Tasks

1. `UIsub.__init__`: assign `self.uistate`, `self.config`, `self.uiplot` from app singletons
2. Replace all module-level `uistate` / `uiplot` refs in `StatTestMixin` with `self.*`
3. Delete `ui_stat_test.uistate = …` wiring block in `ui.py`

## Forbidden

- Changing stat test behavior or dispatcher
- Migrating other mixins in this PR

## Verify

```sh
uv run pytest src/lib/test_statusbar_characterization.py src/lib/test_applicability_characterization.py src/lib/ -q
```

## Next

→ [09_selection_injection.md](09_selection_injection.md)