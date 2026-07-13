# PR-06: AppContext / UIstate facade

**Status**: DONE | **Depends on**: PR-04

## Goal

Split `UIstate` into nested sub-objects (`project`, `experiment`, `stat_test`, `plot`) — no flat-attribute facade.

## Tasks

1. Define sub-state classes in `ui_state_classes.py`
2. `UIstate` properties delegate to sub-objects (no widget code changes in PR-06)
3. Migrate `brainwash_ui` formatters to accept explicit dataclasses instead of full `uistate` where easy

## Forbidden

- Constructor injection across all mixins (that's PR-07+ / separate effort)
- Breaking project pickle/cfg persistence without migration

## Verify

```sh
uv run pytest src/lib/ -q
```

## Next

→ [07_pytest_qt_smoke.md](07_pytest_qt_smoke.md)