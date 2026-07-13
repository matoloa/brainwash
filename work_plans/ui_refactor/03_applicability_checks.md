# PR-03: Applicability checks extraction

**Status**: pending | **Depends on**: PR-02

## Goal

Move `_check_ttest_applicability`, `_check_anova_applicability`, `_check_friedman_applicability`, `_check_cluster_applicability` to pure functions in `brainwash_ui/applicability.py`.

## Tasks

1. `brainwash_ui/applicability.py` — functions take `dd_groups`, `dd_testsets`, variant; return `str | None` warning
2. `ui_stat_test.py` — mixin methods delegate; keep `print()` on warning only in mixin (not in pure layer)
3. `get_stat_test_warning` logic can call `applicability.warning_for_test_type(...)` 
4. `src/lib/test_applicability_characterization.py` — lock warning strings from [CONTRACT.md](CONTRACT.md)

## Forbidden

- Changing warning message text (characterization tests)
- Stats dispatcher / `compute_statistical_comparison` edits

## Verify

```sh
uv run pytest src/lib/test_applicability_characterization.py src/lib/test_view_state.py -q
```

## Next

→ [04_statusbar_formatters.md](04_statusbar_formatters.md)