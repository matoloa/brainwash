# PR-25: hygiene + archive

**Status**: DONE | **Depends on**: PR-24

## Goal

Remove `importlib.reload(ui_plot)`, archive PR cards 00–16 to `History/ui_refactor/`, refresh evaluation doc banner.

## Verify

```sh
uv run pytest src/lib/ -q
```