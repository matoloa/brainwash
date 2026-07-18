# PR-17: Index + plot CONTRACT

**Status**: DONE | **Depends on**: PR-16

## Goal

Add Phase II index and plot invariants to CONTRACT.md. Zero behavior change.

## Scope

- [plan_ui_refactor_phase2.md](../plan_ui_refactor_phase2.md)
- Update [plan_ui_refactor.md](../plan_ui_refactor.md) PRs 17–25
- Extend [CONTRACT.md](CONTRACT.md) plot invariants

## Verify

```sh
uv run pytest src/lib/ -q
```