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
     - `experiment_type="io"` is first-class. Formal IO analysis runs **only** when `stat_test.test_type == "ANCOVA"` (radio-gated). Entering IO selects ANCOVA; non-ANCOVA on IO → warning statusbar, no formal results.
     - Textbook IO ANCOVA: `brainwash_stats/io/ancova.py` (`compute_io_ancova`) — homogeneity of slopes then (if OK) group-adjusted ANCOVA; config type `"IO ANCOVA"` (legacy `"IO regression"` still readable). Shown test sets ignored for v1 IO path.
     - IO guard stays early in `brainwash_stats/dispatcher.py:compute_statistical_comparison` (before implicit ANOVA). Thin delegate: `regression.py` → `ancova`.
     - Applicability, statusbar, and plot descriptors live in `brainwash_ui/` (pure; no widget side effects). `UIplot` renders `plot_model` / `plot_series` specs; stats wiring delegates to `brainwash_ui.applicability` / `statusbar`.
     - Prefer explicit parameter passing over `getattr(uistate, "...")` fallbacks or bound-method `__self__` recovery.
   - **State & Singletons**: `uistate` (from `ui_state_classes.py`) is the source of truth. `UIsub` sets `self.uistate` / `self.config` / `self.uiplot`; all mixins use `self.*` — no module-level singleton injection.
   - **compute_statistical_comparison**: Keep as thin dispatcher where possible. Avoid 1000+ LOC god function growth. Extract helpers for new modes (IO, PP, etc.).
   - **Statusbar**: One source of truth via `_get_statusbar_for_current_state()` or equivalent. IO ANCOVA must produce `{"config": {"type": "IO ANCOVA", ...}}` (accept legacy `"IO regression"`).
   - **Plot artist identity**: `dict_rec_labels` / `dict_group_labels` keys are **opaque identity** (`rec|…` / `grp|…` via `brainwash_ui.plot_identity`), not legend text. Human names live in `entry["display_label"]`. Lookups: `rec_ID` + `role` (`find_rec_entries`, `entry_io_role`, `entry_matches_rec_name`) or `find_entry_by_display_label`. Do **not** match artists via `key.startswith(rec_name)` or `endswith(" IO scatter|trendline")` outside `plot_identity` (legacy parse only). Guard: `test_identity_lookup_patterns.py`. Plan (done): `work_plans/plan_plot_artist_identity.md`. Blinding (#5): presentation only (`display_recording_name` / DisplayRole), never keys or `df_project`.
   - **Disk mutation on load**: Healers/migrators that rewrite project files must be **observable and once-per-session** (or explicit user save). Stim id repair: always fix in memory; persist at most once per rec via `should_persist_stim_id_heal` + `stim_id_heal_log` in cfg — never thrash `get_dft` rewrites. Do not dual-read pre-#10 data parquets (re-parse from raw).
   - **Mixin layout**: Extraction is complete enough for 1.0.0 (`work_plans/audit_mixin_arrangement.md`). Do **not** re-extract mixins unless a characterization suite exists for the moved triggers.

4. **Naming (human-readable, conservative renames encouraged)**
   - Prefer names understandable to a new contributor without deep context (verb phrases for functions, domain nouns for modules).
   - Rename **conservatively** when names cause confusion or bugs — especially stdlib collisions, duplicate nested helpers, cryptic abbreviations (`_get_obs`). **One rename family per PR**; keep public API stable unless the user approves.
   - **Stable stats public API**: `compute_statistical_comparison`, `ttest_per_sweep`, `ui.py` import `from . import statistics as stats`.
   - **Tests**: never `from statistics import …` (stdlib); use `load_brainwash_statistics.load_brainwash_statistics_module()`.
   - Stats package layout: `src/brainwash/brainwash_stats/`; facade `src/brainwash/statistics.py`. Naming notes: `.grok/rules/naming-and-stats-refactor.md`.

5. **Code Style & Conventions (Extends CONTRIBUTING.md)**
   - Follow Black (`line-length=150`), isort, flake8.
   - **No gold-plating**: Do not add features, docstrings, type hints, error handling, or abstractions beyond the exact request.
   - **Edits**: Use `search_replace` (after `read_file`). Prefer editing existing files over creating new ones. Never create documentation unless explicitly asked.
   - **Verification**: Before marking task complete, run relevant tests (`uv run pytest`), launch app, and verify behavior (e.g. IO + ANCOVA → statusbar with group/interaction p, r², n_unit; non-ANCOVA on IO → warning only).
   - **Comments**: Only for why (not what). Reference plans only if active. Use `file:line` pattern when referencing code.
   - **Security/Quality**: Avoid injection risks. Trust framework guarantees inside boundaries.

6. **Statistics layer** (refactor complete — PRs 00–11)
   - **Facade**: `src/brainwash/statistics.py` re-exports `compute_statistical_comparison`, `ttest_per_sweep`, `_bh_fdr`.
   - **Implementation**: `src/brainwash/brainwash_stats/` (`dispatcher.py`, `validation.py`, `formal_tests/`, `io/`, etc.).
   - **Tests**: `uv run pytest src/brainwash/test_statistics_characterization.py src/brainwash/test_io_ancova.py -q`; use `load_brainwash_statistics.py` in tests (never stdlib `statistics`).
   - **Archived plans**: `work_plans/History/plan_statistics_refactor.md` + `statistics_refactor/`; `work_plans/History/plan_io_ancova_publication.md` (PR-A–E complete).
   - **Forbidden** (still): `StatContext`, `ComparisonMode`, `MODE_HANDLERS`, guard reordering in dispatcher.

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
   - `src/brainwash/ui.py`: Largest file (UIsub + mixins). Statusbar, test dispatch, experiment_type logic lives here.
   - `src/brainwash/statistics.py`: thin facade; stats logic in `src/brainwash/brainwash_stats/`.
   - `src/brainwash/brainwash_ui/`: pure view/statusbar/applicability logic (testable without Qt).
   - `src/brainwash/legacy/`: **retain** `analysis_v1.py` / `analysis_v2.py` for scientific reproduction — do not delete; shims at `src/brainwash/analysis_v1.py` etc.
   - `src/brainwash/ui_state_classes.py`: `UIstate` per `UIsub` — use `self.uistate.project`, `.experiment`, `.stat_test`, `.plot` (no flat attrs; no import-time `ui.uistate`).
   - Plans are in `work_plans/` (move outdated to `History/`). Active: `ROADMAP.md`, `manual_smokes_1.0.0.md`, `manual_smokes_after_refactor.md`, `NTH.md`. Completed: UI refactor / modularity / IO ANCOVA / plot identity (STATUS done) → archive after tag.
   - **Modularity Phases 6–8 + 7b** + UI refactor 0–X: complete (tag `ui-refactor/phase0-3-done`). Active product line: **`1.0.0`** (issues #1–#10 done; tag when smokes pass).
   - See full layout in CONTRIBUTING.md.
