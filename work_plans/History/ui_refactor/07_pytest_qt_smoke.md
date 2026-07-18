# PR-07: pytest-qt smoke tests

**Status**: DONE | **Depends on**: PR-06 (or PR-04 minimum)

## Goal

Add `pytest-qt` dev dependency and 3–5 wiring tests for experiment type + statusbar widget.

## Tasks

1. `uv add --group dev pytest-qt`
2. `conftest.py` — `qapp` session fixture
3. `test_ui_wiring.py` — minimal `UIsub` or widget subset with fixture project
4. Document in [VERIFY.md](VERIFY.md)

## Forbidden

- Full E2E with real data paths in CI
- Screenshot regression in default CI job

## Verify

```sh
uv run pytest src/lib/test_ui_wiring.py -q
```

## Next

Human review: decide on injection removal / UIplot model-view split (see parent evaluation Phase 6+).