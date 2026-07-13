# Phase 6 — HIGH RISK commits (singleton lifetime)

Branch: `ui-refactor/phase0-3`

These commits change when `config`, `uistate`, and `uiplot` are created. Before Phase 6 they were built at `brainwash.ui` import time and shared globally. After Phase 6 each `UIsub` owns its own instances.

## Commits

| Commit | Message | What changed |
|--------|---------|--------------|
| `a2f2dd2` | grok build auto commit 60 | **Rollback point** — last commit before Phase 6 |
| `015b9d2` | grok build auto commit 61 `[HIGH RISK phase6a]` | Instantiate `config` / `uistate` / `uiplot` in `UIsub.__init__`; temporary module aliases |
| `284d414` | grok build auto commit 62 `[HIGH RISK phase6b]` | Remove `brainwash.ui` module aliases (`uistate`, `uiplot`, `config`) |

Later commits (`63`–`64`) are plan/docs only — not HIGH RISK.

## Find HIGH RISK commits

```sh
git log --oneline --grep='HIGH RISK'
```

## Rollback

### Revert Phase 6 only (keeps history)

```sh
git revert 284d414 015b9d2
```

Revert newest first (`6b` then `6a`).

### Reset branch to pre-Phase 6

```sh
git reset --hard a2f2dd2
```

Use only on a local branch or after confirming no one else depends on the Phase 6 commits.

## Verify after rollback or before merge

```sh
uv run pytest src/brainwash/ -q
```

Manual smoke (required for Phase 6):

- Launch app (`src/main.py` or your usual entry)
- Load / open project
- Select recording, graph refresh
- IO experiment type + statusbar text
- Close and reopen (fresh `UIsub` should not leak stale state)

## If something breaks

Symptoms might include: app fails at startup, wrong project state after new/open, plots not updating, statusbar stuck.

1. Note which step failed.
2. Roll back using one of the commands above.
3. Re-run pytest + manual smoke on `a2f2dd2` to confirm baseline.

## Code reference

- Before: `config` / `uistate` / `uiplot` at bottom of `src/brainwash/ui.py` at import time.
- After: `UIsub.__init__` in `src/brainwash/ui.py` only.
- Test: `src/brainwash/test_ui_singletons.py`
- Index: [plan_modularity_phase6.md](../plan_modularity_phase6.md)

## Next (not in these commits)

Phase **7b** (`UIplot` incremental extraction) is separate and will use its own `[HIGH RISK phase7b]` tags. Do not start until manual smoke on Phase 6 passes.