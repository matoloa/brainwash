# PR-24: statusbar wiring tests

**Status**: DONE | **Depends on**: PR-23

## Goal

Headless `StatTestMixin` host stub + IO/warning statusbar wiring tests in `test_ui_wiring.py`.

## Verify

```sh
uv run pytest src/lib/test_ui_wiring.py src/lib/ -q
```