# Phase 6b: remove module aliases (HIGH RISK)

**Risk**: HIGH — breaks any code using `from brainwash.ui import uistate`.

## Goal

Drop `config` / `uistate` / `uiplot` module-level names from `brainwash.ui`. Only `UIsub` instance attributes remain.

## Rollback

```sh
git revert HEAD   # commit tagged [HIGH RISK phase6b]
# Or revert entire phase6 block:
git revert 015b9d2..HEAD
```

## Verify

```sh
uv run pytest src/brainwash/ -q
```