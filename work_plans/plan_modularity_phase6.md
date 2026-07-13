# Modularity Phase 6+ — Agent index

> **Status**: Active. Branch: `ui-refactor/phase0-3`.
> Phases 0–5 + 3b + 4: complete. **Human approved Phase 6+ scope 2026-07-13.**
> **Rollback guide**: [phase6/README.md](phase6/README.md) (commits `61`/`62` HIGH RISK).

## HIGH RISK commit convention

Phase 6+ commits use the message suffix **`[HIGH RISK phase6X]`** so they can be found and reverted as a block:

```sh
git log --oneline --grep='HIGH RISK'
git revert <sha>..HEAD   # or reset branch to pre-phase6 tag
```

Pre-phase6 rollback point: **`a2f2dd2`** (commit 60, before first `[HIGH RISK]`).

Rollback entire Phase 6 block:

```sh
git reset --hard a2f2dd2   # local only — confirm before push
# or revert range:
git revert 015b9d2..HEAD
```

## Scope (approved)

| Phase | Card | Risk | Scope | Rollback if |
|-------|------|------|-------|-------------|
| **6a** | [phase6/01_per_uisub_singletons.md](phase6/01_per_uisub_singletons.md) | **HIGH** | Move `config`/`uistate`/`uiplot` off `ui.py` import time → `UIsub.__init__` | App fails to start; stale state across sessions |
| **6b** | phase6/02_remove_module_aliases.md | **HIGH** | Drop deprecated `ui.uistate` module aliases (after 6a smoke) | Legacy script breaks |
| **7a** | phase6/03_uiplot_contract.md | medium | Document `UIplot` host contract + plot_model boundaries only | — |
| **7b** | TBD | **HIGH** | Extract pure plot descriptor builders from `ui_plot.py` (incremental) | Plot regressions |
| **8** | TBD | **HIGH** | Package rename `src/lib` shim removal | Import breaks |

**Out of scope (forbidden without explicit approval)**:
- Full `UIplot` rewrite in one PR
- `UIsub` composition rewrite
- `compute_statistical_comparison` / stats dispatcher changes
- Distribution builds

## Verify (after each HIGH RISK commit)

```sh
uv run pytest src/brainwash/ -q
# Manual: launch app, load project, select rec, graph refresh, IO statusbar
```

## Progress

| PR | Card | Status |
|----|------|--------|
| 6a | per-UIsub singletons | ✅ `015b9d2` [HIGH RISK phase6a] |
| 6b | remove module aliases | ✅ `284d414` [HIGH RISK phase6b] |
| 6c | bare config refs fixup | ✅ `4b032d3` [HIGH RISK phase6c] |
| 7a | UIplot contract doc | ✅ commit 84eb30d |
| 7b | group line specs → plot_model | ✅ `7aadc92` [HIGH RISK phase7b] |
| 7b | IO addRow specs → plot_series | ✅ commit 70 [HIGH RISK phase7b] |
| 7b | PP/stim aggregate addRow specs | ✅ commit 71 [HIGH RISK phase7b] |
| 7b | per-stim event loop → plot_stim | ✅ commit 72 [HIGH RISK phase7b] |
| 7b | addGroup PP/IO specs → plot_series | ✅ commit 73 [HIGH RISK phase7b] |
| 7b | graphRefresh legend/PP ticks → plot_model/series | ✅ commit 74 [HIGH RISK phase7b] |
| 7b | UIplot.update drag geometry → plot_stim | ✅ commit 75 [HIGH RISK phase7b] |
| 7b | graphRefresh axis format/PP x-ticks | ✅ commit 76 [HIGH RISK phase7b] |