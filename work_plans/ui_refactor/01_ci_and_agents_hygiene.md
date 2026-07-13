# PR-01: CI pytest + AGENTS.md hygiene

**Status**: DONE | **Depends on**: PR-00

## Goal

Run `pytest src/lib/` on every push/PR. Fix stale statusbar symbol in `AGENTS.md`.

## Tasks

1. Add `.github/workflows/test.yml` — `uv sync --frozen --group dev`, `uv run pytest src/lib/ -q`
2. `AGENTS.md`: replace `_refresh_test_statusbar` with `set_statusbar` / `_get_statusbar_for_current_state`; clarify purity target (formatters → `brainwash_ui`, mixin applies)
3. Mark PR-01 ✅ in `plan_ui_refactor.md`, set **NEXT** → PR-02

## Files

- `.github/workflows/test.yml` (new)
- `AGENTS.md`

## Forbidden

- App launch, build groups, stats dispatcher changes

## Verify

```sh
uv run pytest src/lib/ -q
```

Expect **115** tests (baseline before PR-02 adds more).

## Next

→ [02_view_state.md](02_view_state.md)