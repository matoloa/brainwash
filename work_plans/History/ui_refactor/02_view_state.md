# PR-02: View-state pure functions

**Status**: DONE | **Depends on**: PR-01

## Goal

Extract group/testset visibility helpers from `StatTestMixin` / `SelectionMixin` into testable pure functions.

## Tasks

1. Create `src/lib/brainwash_ui/__init__.py`, `view_state.py`:
   - `visible_group_ids(dd_groups) -> list[str]`
   - `visible_testset_ids(dd_testsets) -> list[str]`
   - `groups_with_recordings(dd_groups, group_ids) -> list[str]`
2. `ui_stat_test.py`: `_get_shown_group_ids` / `_get_shown_testsets` delegate to `brainwash_ui.view_state`
3. Add `src/lib/test_view_state.py` (8–10 cases)
4. Update [CONTRACT.md](CONTRACT.md) if needed

## Forbidden

- Changing visibility semantics (golden tests lock current behavior)
- `ui.py` edits unless required for import path

## Verify

```sh
uv run pytest src/lib/test_view_state.py src/lib/ -q
```

## Next

→ [03_applicability_checks.md](03_applicability_checks.md)