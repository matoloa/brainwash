# PR-04: Statusbar formatters + purity split

**Status**: DONE | **Depends on**: PR-03

## Goal

Extract `_format_io_regression_statusbar` and `_format_non_io_stat_test_statusbar` to pure functions returning `StatusbarResult`. Stop mutating `uistate.statusbar_state` inside query/format paths.

## Tasks

1. `brainwash_ui/statusbar.py` — `StatusbarResult`, `format_io_regression_statusbar`, `format_non_io_stat_test_statusbar`
2. `ui_stat_test.py` — `_get_statusbar_for_current_state` calls formatters, then sets `uistate.statusbar_state` once before `set_statusbar`
3. `src/lib/test_statusbar_characterization.py` — IO ANCOVA text, non-IO compact reports
4. Align [CONTRACT.md](CONTRACT.md) with implementation

## Forbidden

- Changing IO statusbar user-visible format without updating golden tests
- Recursion in statusbar query path

## Verify

```sh
uv run pytest src/lib/test_statusbar_characterization.py src/lib/test_statistics_characterization.py -q
```

## Next

→ [05_pipeline_integration.md](05_pipeline_integration.md)