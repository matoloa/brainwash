# AGENTS.md — Guidelines for Grok / AI Agents Working on Brainwash

This file provides instructions for AI agents (Grok, Claude, etc.) and human contributors using agentic tools.

## Core Principles for Agentic Efficiency

1. **Prefer Tools Over Manual Reading**
   - Use `grep`, `read_file` (with targeted `offset`/`limit`), `list_dir`, and subagents (`explore`, `plan`, `general-purpose`) for discovery.
   - **Never** re-read the same plan files or execution traces multiple times. Archive outdated plans.
   - Use `enter_plan_mode` for tasks with architectural ambiguity (multiple approaches, unclear requirements, high-impact changes). Explore, propose plan, `exit_plan_mode`, get approval.
   - Use `check-work` skill (or `/check-work`) after every significant edit to verify diffs, tests, and correctness.
   - Use `best-of-n` skill when multiple implementations are viable ("try N approaches").

2. **Minimize Context Bloat**
   - **Do not accumulate plan files**. Consolidate into this `AGENTS.md` or a single living document (`docs/ARCHITECTURE.md`).
   - Delete or move to `work_plans/History/` any `plan_*.md`, `debug_plan_*.md` older than the current milestone.
   - Keep comments minimal and current. Remove "Phase X", "v0.16_n_stats_IO", "Option B" legacy markers once resolved.
   - Avoid excessive `print("DEBUG: ...")` statements. Use a `debug` flag or structured logging.

3. **Architectural Guidelines (Especially for UI/Stats Layer)**
   - **Experiment Type & Test Handling**:
     - `experiment_type="io"` is first-class. Use it directly rather than `"ANCOVA"` sentinel leaking into `compute_statistical_comparison`.
     - IO regression (`_compute_io_regression_internal`) must be reachable without test_type guard bypasses. Hoist IO check early in `statistics.py:compute_statistical_comparison` (before L458 guard).
     - `_get_stat_test_warning` and `_refresh_test_statusbar` must remain pure (no side effects, no recursion). Statusbar state lives in `uistate`.
     - Prefer explicit parameter passing over `getattr(uistate, "...")` fallbacks or bound-method `__self__` recovery.
   - **State & Singletons**: `uistate` (from `ui_state_classes.py`) is the source of truth. Module-level injection in mixins is acceptable but document it.
   - **compute_statistical_comparison**: Keep as thin dispatcher where possible. Avoid 1000+ LOC god function growth. Extract helpers for new modes (IO, PP, etc.).
   - **Statusbar**: One source of truth via `_get_statusbar_for_current_state()` or equivalent. IO regression must produce `{"config": {"type": "IO regression", ...}}` reliably.

4. **Naming (human-readable, conservative renames encouraged)**
   - Prefer names understandable to a new contributor without deep context (verb phrases for functions, domain nouns for modules).
   - Rename **conservatively** when names cause confusion or bugs — especially stdlib collisions, duplicate nested helpers, cryptic abbreviations (`_get_obs`). **One rename family per PR**; keep public API stable unless the user approves.
   - **Stable stats public API**: `compute_statistical_comparison`, `ttest_per_sweep`, `ui.py` import `from . import statistics as stats`.
   - **Tests**: never `from statistics import …` (stdlib); use `load_brainwash_statistics.load_brainwash_statistics_module()`.
   - Rename map for the active refactor: `.grok/rules/naming-and-stats-refactor.md` and `plan_statistics_refactor.md` START HERE.

5. **Code Style & Conventions (Extends CONTRIBUTING.md)**
   - Follow Black (`line-length=150`), isort, flake8.
   - **No gold-plating**: Do not add features, docstrings, type hints, error handling, or abstractions beyond the exact request.
   - **Edits**: Use `search_replace` (after `read_file`). Prefer editing existing files over creating new ones. Never create documentation unless explicitly asked.
   - **Verification**: Before marking task complete, run relevant tests (`uv run pytest`), launch app, and verify behavior (e.g. IO switch → correct statusbar with slope p, r², n_report).
   - **Comments**: Only for why (not what). Reference plans only if active. Use `file:line` pattern when referencing code.
   - **Security/Quality**: Avoid injection risks. Trust framework guarantees inside boundaries.

6. **Active work: statistics refactor only**
   - **Index** (~25 lines): `work_plans/plan_statistics_refactor.md` — find **NEXT** PR in table.
   - **One card per session**: `work_plans/statistics_refactor/NN_*.md` only (~40 lines each). Never read `_archive_full_spec.md` unless stuck.
   - **Scope**: `statistics.py` → `brainwash_stats/`. **No** `ui.py`. Cancelled: `History/plan_statusbar_ui.md`.
   - **Forbidden**: `StatContext`, `ComparisonMode`, `MODE_HANDLERS`, guard reordering.
   - **Verify**: [VERIFY.md](work_plans/statistics_refactor/VERIFY.md) — pytest only unless user asks more.
   - Naming: `.grok/rules/naming-and-stats-refactor.md`

7. **Workflow for Common Tasks**
   - **Bug Fix**: `grep` for related code → read key functions → propose minimal change → edit → `check-work` → test.
   - **New Feature**: `enter_plan_mode` → explore with subagent → `exit_plan_mode` for approval → implement.
   - **Refactor**: Use `plan` subagent for architecture, then implement in isolated worktree if high risk (`best-of-n`).
   - **IO/Stats Changes**: Always validate with project containing ≥2 groups + sweep data. Check statusbar on `experiment_type_changed`, `io_input_changed`, graph refresh.
   - **When Stuck**: Use `ask_user_question` for narrow clarification. Do not default to full plan mode.

8. **On-Demand Only: Builds & Autodiagnose**
   - **Never** run distribution builds or environment autodiagnose unless the user explicitly asks (e.g. "build", "run the build", "check if patchelf is installed").
   - **Builds** include: `uv sync --group build`, cx_Freeze (`build_exe`, `bdist_appimage`, `build_with_cxfreeze_multiarch_setup.py`), `build-appimage.sh`, `build-devcontainer.sh`, and installing build deps (`patchelf`, etc.).
   - **Autodiagnose** means proactive environment/setup probing: checking tool versions, verifying `.venv`/deps, `which`/`apt-get install`/`uv sync` solely to assess readiness — not reads/greps needed to understand or edit code for the current task.
   - When the user says "build" or similar, run the build — do not preflight with autodiagnose unless they asked for that too.
   - Do not run builds or autodiagnose as part of verification, bug-fix wrap-up, or `/check-work` unless explicitly requested.

9. **Project Structure Highlights** (from CONTRIBUTING.md)
   - `src/lib/ui.py`: Largest file (UIsub + mixins). Statusbar, test dispatch, experiment_type logic lives here.
   - `src/lib/statistics.py`: `compute_statistical_comparison` + IO regression helpers (`_compute_io_regression_internal`, `_get_io_xy_pairs`).
   - `src/lib/ui_state_classes.py`: `uistate` singleton.
   - Plans are in `work_plans/` (move outdated to `History/`).
   - See full layout in CONTRIBUTING.md.
