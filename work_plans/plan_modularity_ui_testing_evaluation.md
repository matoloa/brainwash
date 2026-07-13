# Brainwash: Modularity, UI Separation, and Automated Testing

**Date**: 2026-07-13 (revised)  
**Status**: Phase 0–X complete on `ui-refactor/phase0-3` (PR-44). **218** pytest tests in `src/brainwash/` (incl. pytest-qt wiring + refresh-bus coalesce). CI test workflow active. Section 1 metrics are a 2026-07-13 snapshot — refresh before planning new work.  
**Audience**: Human maintainers and agentic contributors  
**Goal**: Make UI/stat/view changes safe for agents without a full rewrite, reusing the statistics refactor playbook.

---

## Executive summary

Brainwash already has **three strong domain layers** (`parse`, `analysis_v3`, `brainwash_stats`) with automated tests. The UI layer is **file-split but not modular at runtime**: `UIsub` + 12 mixins + the `UIplot` singleton still form implicit, globally-wired coordinators.

The highest-leverage path is **not** more mixin file moves. It is:

1. Extract **pure application logic** (statusbar text, view filters, recording pipeline) into testable modules.
2. Add **characterization tests + contracts** (mirror `brainwash_stats/CONTRACT.md`).
3. Promote **`test_parse_click.py`** into pytest for headless integration.
4. ~~Add a **CI test job**~~ — done (`.github/workflows/test.yml`).
5. Defer composition/controllers and package rename until services and tests exist.

---

## 1. Verified baseline (2026-07-13)

Numbers below were checked against the repo; use this table as the ground truth for planning.

| Metric | Value | Notes |
|--------|-------|-------|
| `ui.py` LOC | 2,584 | Down from ~5,720 pre-mixin extraction |
| Methods still on `UIsub` in `ui.py` | **89** | Down from 172; mostly wiring, triggers, experiment-type handlers |
| Mixin classes | **12** | Plus `ui_designer.Ui_mainWindow` as 13th base |
| Modules with singleton injection | **13** | `uistate` / `config` / `uiplot` assigned in `ui.py` wiring block |
| `ui_plot.UIplot` LOC | **2,797** | Separate god object; **248** `uistate.` references |
| `ui_interactive.py` LOC | **2,015** | Largest mixin; mouse/drag orchestration |
| `ui_data_frames.py` LOC | **1,193** | Pipeline + cache + `uistate.lineEdit` reads |
| `ui_state_classes.UIstate` LOC | **871** | Persisted + transient + plot handles in one class |
| `hasattr(self, …)` in `ui*.py` | **171** | Implicit host contracts |
| `print()` in `ui*.py` | **375** | Weak structured observability |
| Cross-mixin refresh calls | **~54** | `graphRefresh` / `update_show` / `turn_heatmap_off` / `apply_statistical_test_if_active` |
| pytest tests (`src/brainwash/`) | **218** collected | incl. statusbar, view_state, pipeline integration, pytest-qt wiring |
| UI/Qt pytest tests | **9+** | `test_ui_wiring.py`, `test_refresh_bus_qt.py`, etc. |
| `test_parse_click.py` | Promoted | Core steps in `test_pipeline_integration.py` |
| GitHub Actions | Build + **pytest** | `.github/workflows/test.yml` on push/PR |
| Legacy analysis | `analysis_v1.py` + `analysis_v2.py` (~1,721 LOC) | Still imported by `analysis_evaluation.py` |

### What already works (extend these patterns)

| Layer | Location | Tests | Agent-friendly? |
|-------|----------|-------|-----------------|
| Parse | `parse.py` (776 LOC) | 108 `test_*` methods | Yes |
| Analysis | `analysis_v3.py` (1,012 LOC) | Via parse + `test_parse_click` | Yes |
| Statistics | `brainwash_stats/` + `statistics.py` facade | 7 characterization tests + `CONTRACT.md` | **Yes — template** |
| Mixin file split | `ui_*.py` (16 files) | None for UI behavior | Partial (navigation only) |

### Core diagnosis

`work_plans/Archive/mixin_problems.md` remains accurate: **mixins partition source files, not runtime boundaries**. At runtime:

- `UIsub` is still the bus (~89 methods + all mixin methods on one object).
- `UIplot` is a second monolith accessed via global `uiplot`.
- Module-level injection (`ui_groups.uistate = uistate`) is timing-sensitive and hard to test.

---

## 2. Doc / implementation gaps (fix before large refactors)

These confuse agents and should be resolved in early PRs:

| Gap | Detail | Recommendation |
|-----|--------|----------------|
| **Statusbar “purity”** | ~~`_get_statusbar_for_current_state` mutated in query path~~ | Fixed: `_compute_statusbar_for_current_state` (pure) + `update_test` apply path | — |
| **Stale symbol** | `AGENTS.md` references `_refresh_test_statusbar` | Symbol **does not exist** in codebase | Update `AGENTS.md` to `set_statusbar` / `_get_statusbar_for_current_state` or add thin alias |
| **Import inconsistency** | `import ui_groups` vs `import lib.ui_stat_test` | `conftest.py` prepends `src/lib` to `sys.path` | Document canonical import style; package rename is optional later |
| **`importlib.reload(ui_plot)`** | In `ui.py` startup | Suggests fragile import/injection ordering | Remove when injection is replaced or document why it stays |

---

## 3. Target architecture

### Layer model

```
┌──────────────────────────────────────────────────────────────────┐
│  VIEW (Qt + matplotlib widgets, signals, threads)                │
│  UIsub, ui_designer, ui_widgets, ui_interactive, ui_graph        │
└───────────────────────────────┬──────────────────────────────────┘
                                │ reads/writes
┌───────────────────────────────▼──────────────────────────────────┐
│  PRESENTATION (pure: strings, visibility, plot descriptors)      │
│  statusbar_format, view_state, plot_model                        │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│  APPLICATION (orchestration, caches, project paths)              │
│  recording_pipeline, project_io, stat_test_coordinator           │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│  DOMAIN (already strong)                                         │
│  parse, analysis_v3, brainwash_stats                               │
└──────────────────────────────────────────────────────────────────┘
```

### Separation rules

| Belongs in domain/application | Belongs in view only |
|------------------------------|----------------------|
| DataFrame transforms, cache keys | `QWidget`, `QThread`, signal connect |
| Statusbar **text** and warning logic | `_set_statusbar_appearance`, QLabel colors |
| Which recs/groups are visible | Checkbox/radio widget sync |
| What series/limits to plot | `FigureCanvas`, artist creation |
| `compute_statistical_comparison` | Formal test radio wiring |

### Second monolith: `UIplot`

Mixin extraction did not address `ui_plot.UIplot` (2,797 LOC). It holds drawing, `addRow`, group plotting, and heavy `uistate` mutation. **Plot model/view split** (Phase 7) is as important as further `ui.py` trimming.

### Modules partially separated today

| Module | Qt imports? | Domain imports? | Issue |
|--------|-------------|-----------------|-------|
| `ui_data_frames.py` | No | `parse`, `analysis_v3` | Reads `uistate.lineEdit`, `uistate.default_dict_t`; uses `self.dict_folders`, `self.df2file` |
| `ui_stat_test.py` | Yes (`QtWidgets`) | `statistics` | Formatters mixed with `set_statusbar` / widget side effects |
| `ui_parse.py` | Yes | `parse` | Progress bar + thread callbacks |
| `export_data.py` | Yes | pandas | Export mixin — reasonable view adapter |
| `export_image.py` (848 LOC) | Yes | matplotlib | Not in evaluation v1; same plot coupling risk |

---

## 4. Refactoring tiers (revised priorities)

### Tier A — Low risk, highest agent ROI

#### A1. Statusbar + applicability extraction (do first)

**Source**: `ui_stat_test.py` — functions that are *almost* pure today:

| Function | Pure today? | Blocker |
|----------|-------------|---------|
| `_format_io_regression_statusbar` | No | Writes `uistate.statusbar_state`; reads `self.dd_groups` |
| `_format_non_io_stat_test_statusbar` | No | Same |
| `_get_stat_test_warning` | Mostly | Calls `_check_*_applicability`; reads `uistate`, `self.dd_*` |
| `_should_show_stat_test_frame` | Mostly | Reads `uistate.viewTools` |
| `_check_ttest_applicability` (+ anova, wilcoxon, friedman, cluster) | **Yes** | Only needs counts/flags as inputs |

**Target**: `brainwash_stats/statusbar.py` or `brainwash_ui/statusbar.py` (name TBD):

```python
# Pure — no uistate mutation
def format_io_regression_statusbar(formal, dd_groups, n_unit) -> StatusbarResult: ...
def format_non_io_statusbar(formal, test_type, ...) -> StatusbarResult: ...
def get_stat_test_warning(test_type, groups, testsets, ...) -> str | None: ...
```

`StatusbarResult`: `text: str | None`, `state: Literal["info", "warning", None]`.

**UI mixin** becomes: `result = format_…(...); uistate.statusbar_state = result.state; self.set_statusbar(result.state, result.text)`.

**Tests**: `test_statusbar_characterization.py` — mirror stats contract; include IO regression golden strings (slope p, r², n_report).

#### A2. View-state extraction

**Source**: `ui_selection.py`, `ui_stat_test.py`, `ui.py`

| Logic | Target API |
|-------|------------|
| `_get_shown_group_ids`, `_get_shown_testsets` | `visible_groups(dd_groups) -> list[str]` |
| `_is_rec_visible`, `_is_group_visible` | `is_recording_visible(row, dd_groups, view_state) -> bool` |
| Experiment-type → test frame visibility | `should_show_stat_test_frame(experiment_type, view_tools) -> bool` |

**Tests**: `test_view_state.py` with fixture `dd_groups` / `dd_testsets` dicts (same style as `test_statistics_fixtures.py`).

#### A3. Headless pipeline service (incremental)

**Source**: `ui_data_frames.py` `get_dfmean` → `get_dft` → `get_dfoutput` chain.

**Evidence it works headless**: `src/test_parse_click.py` runs parse → events → output → addRow simulation without Qt.

**Target**: `recording_pipeline.py` with explicit inputs:

```python
def build_dft(dfmean, default_dict_t, filter, line_edits) -> pd.DataFrame: ...
def build_dfoutput_cached(row, folders, caches, ...) -> pd.DataFrame: ...
```

Start by extracting **logic only**; keep `self.dict_*` caches on mixin calling the service. One recording per PR.

**Dependency**: Needs path helpers from `ProjectMixin` (`dict_folders`) — extract `project_paths.py` first or pass `folders: dict` explicitly.

#### A4. Characterization contracts (parallel to stats)

Add `work_plans/ui_refactor/CONTRACT.md` (when implementation starts):

| Contract | Invariant |
|----------|-----------|
| IO statusbar | `experiment_type="io"` + valid formal result → text contains `IO ANCOVA`, slope p, r² when finite |
| Non-IO warning | Inapplicable t-test → warning string, no crash |
| View filter | Hidden group → excluded from `visible_groups` |
| Pipeline | `get_dft` equivalent → columns include `norm_output_from`, `norm_output_to` |

Add `VERIFY.md`: `uv run pytest src/lib/test_statusbar_characterization.py src/lib/test_view_state.py -q`

#### A5. CI test job

Minimal `.github/workflows/test.yml`:

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { python-version: "3.12" }
      - run: uv sync --frozen --group dev
      - run: uv run pytest src/lib/ -q
```

**Agent benefit**: Regressions caught before human review. No build/AppImage required.

#### A6. Logging instead of `print()` (gradual)

Replace `print()` in modules touched by A1–A3 with `logger.debug(...)` gated on `BRAINWASH_DEBUG` (already used in `main.py`). Do not drive-by the full 375 prints in one PR.

### Tier B — Medium risk (after Tier A tests exist)

#### B1. `AppContext` replaces mega-`uistate`

Split `UIstate` (871 LOC) into:

| Object | Examples |
|--------|----------|
| `ProjectState` | version, colors, splitter, persisted checkboxes |
| `ExperimentConfig` | `experiment_type`, `io_input`, `io_output`, filter mode |
| `StatTestState` | `test_type`, `formal_test_results`, `statusbar_state` |
| `PlotSession` | axes, mouseover coords, `dict_heatmap` (never pickled) |

`UIstate` can remain a **facade** delegating to sub-objects for backward compatibility during migration.

#### B2. Constructor injection (one mixin family per PR)

Replace:

```python
ui_groups.uistate = uistate
```

With `AppContext` passed into extracted services; mixins call `self._ctx` or module functions `(ctx, ...)`.

**Order**: `ui_stat_test` → `ui_selection` → `ui_data_frames` → others.

#### B3. `Protocol` host contracts

`StatTestMixin` already lists host requirements in its docstring. Promote to `protocols.py`:

```python
class StatTestHost(Protocol):
    dd_groups: dict
    dd_testsets: dict
    def get_group_testset_means(self, ...) -> ...: ...
    def graphRefresh(self, *, reeval_formal_test: bool = ...) -> None: ...
```

Optional: `flake8` / manual checklist per PR until `mypy` is adopted.

#### B4. Plot model / view split (`UIplot`)

| `PlotModel` (pure) | `PlotView` (matplotlib) |
|--------------------|-------------------------|
| Series data, colors, xlim/ylim | `ax.plot`, `addRow` artists |
| Group layout descriptors | Canvas flush |
| Test marker positions | Heatmap rendering |

Test model with Agg backend + fixture DataFrames.

#### B5. Package layout (`brainwash.*`)

Move `src/lib/` → `src/brainwash/` with compatibility shims:

```python
# statistics.py shim at old path — temporary
```

**Defer** until Tier A modules exist. High churn for agents during transition.

### Tier C — High risk (only after B is stable)

| Item | When | Why wait |
|------|------|----------|
| Composition controllers | After services + tests | Avoid second rewrite |
| Event bus | After call graph is mapped | 54+ refresh call sites |
| Quarantine `analysis_v1/v2` to `legacy/` | **Never delete** — required for scientific reproduction via `analysis_evaluation.py` | Moved; shims preserve imports |
| Full `UIsub` decomposition | Optional long-term | Mixin extraction already gave 80% of file-split benefit |

### Tier D — Deprioritized (diminishing returns)

| Item | Reason |
|------|--------|
| Finish remaining mixin moves in `plan_ui_mixin_extraction.md` | `ui.py` already at target ~2.6K; moving `trigger*` handlers does not improve testability |
| `docs/ARCHITECTURE.md` | Useful but optional if this plan + `AGENTS.md` host contracts are kept current |
| Screenshot/GUI E2E | Flaky; use only after Layers 1–4 |

---

## 5. Automated testing strategy (revised)

### Design principle

**Test behavior contracts, not widgets**, until pure layers exist. Mirrors statistics refactor: golden outputs, not implementation details.

### Layer 1 — Pure characterization (no Qt) — **~70% manual check replacement**

| Today (human) | Automated target |
|---------------|------------------|
| IO switch → statusbar slope p, r², n | `test_io_regression_statusbar_text` on `format_io_regression_statusbar` |
| Wrong t-test variant → warning | `test_ttest_applicability_warning` |
| Hide group → plot excludes it | `test_visible_groups_excludes_hidden` |
| `experiment_type="io"` → no implicit ANOVA | Already covered: `test_io_empty_testsets_returns_io_regression_not_anova` |

### Layer 2 — Headless pipeline (no Qt)

Promote `test_parse_click.py` → `test_pipeline_integration.py`:

- Run under pytest with `src/lib/test_data/` fixtures (per `CONTRIBUTING.md`)
- Parametrize: ABF, IBW folder, CSV, ATF
- Assert: column names, `norm_output_*` migration, `addRow` window non-empty
- Optional: small committed parquet goldens (keep < 500 KB total)

### Layer 3 — Plot model (Agg backend, no display)

Given fixture `df_project` row + pipeline outputs:

- Assert series count, group colors, xlim/ylim tuples
- No `QApplication`

### Layer 4 — `pytest-qt` (after `AppContext` / fixture project)

Add to dev group: `pytest-qt`, `pytest-mock`.

| Test type | Example |
|-----------|---------|
| Signal → state | `qtbot.mouseClick(io_radio)` → `uistate.experiment_type == "io"` |
| Statusbar widget | After mock formal result, `statusbar.currentMessage()` matches contract |
| Table | `tableUpdate` with minimal `df_project` fixture |

**Fixture**: `tests/fixtures/minimal_project/` — tiny `project.brainwash` + 1 parquet set.

### Layer 5–6 — Visual / full E2E (last)

- Screenshot diff: dark mode, group plot layout — release gate only
- `pytest-xvfb` + full `UIsub`: only for gaps in 1–4

### Test inventory target

| File | Tests (target) |
|------|----------------|
| `test_statusbar_characterization.py` | 10–15 |
| `test_view_state.py` | 8–12 |
| `test_pipeline_integration.py` | 5–10 (from parse_click) |
| `test_plot_model.py` | 5+ (after UIplot split) |
| `test_ui_wiring.py` | 5+ (pytest-qt, later) |

**Still human**: drag/zoom feel, Wayland/X11 quirks (`main.py`), aesthetic graph layout, novel file formats.

---

## 6. Execution roadmap (PR-sized)

Modeled on `work_plans/History/statistics_refactor/` — one concern per PR, verify after each.

### Phase 0 — Hygiene (1 PR)

- Fix `AGENTS.md` stale `_refresh_test_statusbar` reference
- Add GitHub Actions `test.yml`
- Add `work_plans/ui_refactor/README.md` index (when implementation starts)

**Verify**: `uv run pytest src/lib/ -q` (115 tests green)

### Phase 1 — Statusbar pure layer (2–3 PRs)

| PR | Scope | Forbidden |
|----|-------|-----------|
| 1a | Extract `_check_*_applicability` → pure functions + tests | No `ui.py` behavior change |
| 1b | Extract formatters → `StatusbarResult`; mixin calls + tests | No guard reorder in stats dispatcher |
| 1c | Fix purity: `_get_statusbar_for_current_state` stops mutating `uistate` in query path | — |

**Verify**: `uv run pytest src/lib/test_statusbar_characterization.py -q` + full suite

### Phase 2 — View state (1 PR)

- Extract `visible_groups`, `is_recording_visible`, `should_show_stat_test_frame`
- `test_view_state.py`

### Phase 3 — Pipeline integration (2 PRs)

| PR | Scope |
|----|-------|
| 3a | Promote `test_parse_click` core steps to pytest |
| 3b | Extract `build_dft` / output path from `get_dfoutput` (caches stay on mixin) | ✅ `recording_pipeline.py` |

### Phase 4 — `AppContext` facade (2+ PRs)

- Split `UIstate` with backward-compatible properties — ✅ PR-06 sub-objects
- Migrate `ui_stat_test` to read `ctx.stat_test` first — ✅
- `app_context.compute_statusbar_result` + snapshots — ✅ commit 59

### Phase 5 — `pytest-qt` smoke (1 PR)

- Minimal `QApplication` fixture
- 3–5 wiring tests for experiment type + statusbar

### Phase 6+ — Injection removal, UIplot split, package rename

Only when Phases 1–5 are green in CI.

### Forbidden (all UI refactor PRs)

- Reordering guards in `brainwash_stats/dispatcher.py`
- Introducing `StatContext` / `MODE_HANDLERS` patterns
- Drive-by rename of `compute_statistical_comparison`, `UIsub`, or `from . import statistics as stats`
- Distribution builds unless explicitly requested

---

## 7. Immediate next steps (recommended order)

1. **CI pytest job** — zero code risk, immediate agent safety.
2. **Statusbar pure formatters + characterization tests** — removes the #1 human verification loop from `AGENTS.md`.
3. **Promote `test_parse_click` to pytest** — headless integration without Qt investment.
4. **View-state pure functions** — unlocks plot visibility tests.
5. **Defer** further mixin extraction and package rename.

---

## 8. Success criteria

| Milestone | Measurable outcome |
|-----------|-------------------|
| Agent self-verify stats/view | `uv run pytest src/lib/ -q` covers statusbar + view + pipeline; **no app launch** for IO/statusbar PRs |
| CI enforcement | Test workflow on every push/PR |
| Smaller blast radius | Statusbar/view changes touch 1–2 non-UI modules |
| Honest architecture | No docstring claims "pure" on functions that mutate `uistate` |
| UIplot addressable | Plot model tests exist OR `UIplot` LOC stable and scoped |

---

## 9. Summary judgment

**Strengths**: Domain and stats layers are production-grade for agentic work. Mixin extraction achieved its **file size** goal. `test_parse_click.py` proves the pipeline can run headless.

**Weaknesses**: Runtime architecture is still monolithic (`UIsub` + `UIplot` + global injection). Statusbar code contradicts `AGENTS.md` purity rules. **No CI tests**. UI changes still require human app verification for the cases agents touch most often.

**Strategy**: Copy the statistics refactor — **behavior extraction + contract tests + thin facade**, not file shuffling. Treat `UIplot` and the recording pipeline as first-class extraction targets equal to statusbar. Composition and package rename are **Phase 6+**, not prerequisites.

---

## Related documents

| Document | Role |
|----------|------|
| `work_plans/plan_ui_mixin_extraction.md` | File-level split (mostly complete; low remaining ROI) |
| `work_plans/Archive/mixin_problems.md` | Why mixins ≠ modularity |
| `work_plans/History/statistics_refactor/CONTRACT.md` | Template for UI/statusbar contracts |
| `work_plans/History/statistics_refactor/VERIFY.md` | Per-PR verify discipline |
| `work_plans/History/statistics_refactor/README.md` | Micro-PR session brief pattern |
| `AGENTS.md` | Agent workflow (needs statusbar symbol fix) |
| `src/test_parse_click.py` | Headless integration prototype |