# Brainwash Repository Evaluation: Modularity, UI Separation, and Automated Testing

**Date**: 2026-07-13  
**Status**: Evaluation only — no implementation  
**Scope**: Architectural assessment and recommendations for refactoring toward modularity, separating UI from domain logic, and automated UI verification for agentic development.

---

## 1. Current State

### What works well (models to extend)

**Statistics layer** is the clearest success story. Logic moved from a monolith into `brainwash_stats/`, exposed through a thin facade (`statistics.py`), guarded by characterization tests and an explicit result contract (`work_plans/History/statistics_refactor/CONTRACT.md`). Agents can change internals with pytest as a safety net.

**Parse and analysis** are largely UI-free modules with real public APIs:

- `parse.py`: `source2dfs`, `build_dfmean`, `zeroSweeps`, etc.
- `analysis_v3.py`: `find_events`, `build_dfoutput`, `find_timepoints`, etc.

`test_parse.py` provides ~108 unittest cases across many formats. That is solid domain-layer coverage.

**Mixin extraction** (Phases 0–5) reduced `ui.py` from ~5.7K to ~2.6K LOC and split concerns into 14 mixin modules. File navigability improved.

### What limits modularity and agent safety

| Issue | Evidence | Impact on agents |
|-------|----------|------------------|
| **God coordinator at runtime** | `UIsub` still composes 13 mixins; mixins call each other via `self.*` | Stack traces span 5–6 files; implicit contracts |
| **Module-level singleton injection** | 15+ modules get `uistate`, `config`, `uiplot` injected in `ui.py` | Fragile under reload, alternate entry points, tests |
| **`hasattr(self, …)` guards** | 150+ occurrences across `ui*.py` | Undocumented host requirements; agents guess dependencies |
| **Flat import layout** | Mix of `import ui_groups` and `import lib.ui_stat_test` | Path confusion; `conftest.py` hacks `sys.path` |
| **Large remaining UI files** | `ui_plot.py` (2.8K), `ui_interactive.py` (2K), `ui_data_frames.py` (1.2K), `ui_stat_test.py` (940) | High context cost per change |
| **`uistate` as mega-blob** | `ui_state_classes.py` ~871 LOC, mixes persisted config, transient plot state, test settings | Hard to reason about what a change affects |
| **Human verification still required** | `AGENTS.md` explicitly says "launch app and verify behavior" for IO/statusbar | Agents cannot self-close UI regressions |
| **Debug `print()` in production UI** | 300+ prints across `ui*.py` | Noisy logs; weak structured observability |

The project's own `work_plans/Archive/mixin_problems.md` states the core insight: **mixins partition source files, not runtime boundaries**. The statistics refactor addressed this for stats; the UI layer has not.

---

## 2. Refactoring for Modularity, Efficiency, and Agent Safety

### Tier A — Low risk, high agent payoff (extend existing patterns)

#### A1. Finish the mixin extraction plan (file organization)

`work_plans/plan_ui_mixin_extraction.md` is ~90% done. Remaining work: move thin `trigger*` / `*_changed` handlers, lifecycle helpers, and comment cleanup.

**Value:** Better grep targeting for agents.  
**Limit:** Does not fix implicit coupling; diminishing returns once `ui.py` is already ~2.6K.

#### A2. Create a single `docs/ARCHITECTURE.md` (or expand `AGENTS.md`)

`AGENTS.md` already encodes tribal knowledge. A living architecture doc should add:

- Layer diagram: `parse` → `analysis_v3` → `DataFrameService` → `PlotController` → `UIsub`
- Mixin host contract table (which mixin requires which `self.*` methods)
- Stable public APIs agents must not rename
- Test commands per layer

**Value:** Reduces agent context bloat and wrong-file edits.

#### A3. Standardize imports into a real package

Today: `src/lib/` with `sys.path` manipulation. Target: `src/brainwash/` (or `brainwash/`) with `pyproject.toml` `[tool.setuptools.packages]`.

**Value:** Eliminates stdlib `statistics` collision hacks, clarifies module boundaries, enables `from brainwash.stats import …`.

#### A4. Extract "pure" functions still embedded in UI

Candidates already identified in comments and code:

| Currently in UI | Could move to |
|-----------------|---------------|
| `DataFrameMixin.get_df*` caching logic (minus I/O side effects) | `brainwash_pipeline/` or `data_frames.py` |
| `StatTestMixin._get_statusbar_for_current_state`, `_get_stat_test_warning` | `brainwash_stats/statusbar.py` (pure string builders) |
| `V2mV`, unit-level aggregation in `DataFrameMixin` | `brainwash_stats/data.py` (already has aggregation helpers) |
| Visibility logic (`_is_rec_visible`, `_get_shown_group_ids`) | `view_state.py` (pure functions over `dd_groups` / `dd_testsets`) |

**Pattern:** Same as stats refactor — extract, characterize, keep UI as thin glue.

#### A5. Replace `print()` with structured logging behind a debug flag

Agents need observable behavior without launching the GUI. A `BRAINWASH_DEBUG` channel (partially exists in `main.py`) applied consistently would help automated diagnosis.

---

### Tier B — Medium risk, structural improvement

#### B1. Introduce a **service layer** between UI and domain

Instead of mixins calling `parse` / `analysis_v3` directly, introduce explicit services:

```
RecordingPipelineService  — parse → dfmean → dffilter → dft → dfoutput
ProjectService            — load/save project.brainwash, cache paths
StatTestService           — wraps compute_statistical_comparison + statusbar formatting
PlotStateService          — what to draw given view state (no QWidget)
```

`UIsub` and mixins become **adapters**: read widgets → call service → update widgets.

**Agent benefit:** Services are testable without Qt; agents edit services with pytest, touch UI only for wiring.

**Effort:** Incremental — start with `DataFrameMixin.get_dfoutput` chain (already mirrored in `test_parse_click.py`).

#### B2. Split `uistate` into bounded contexts

Today one `UIstate` holds axes handles, mouseover coords, experiment type, checkboxes, splitter sizes, formal test results, etc.

Proposed split:

| Object | Contents |
|--------|----------|
| `ProjectState` | persisted project fields |
| `ViewState` | show/hide groups, recs, testsets |
| `ExperimentConfig` | experiment_type, io_input/output, filter settings |
| `StatTestState` | test_type, formal_test_results, statusbar_state |
| `PlotSession` | transient axes, mouseover (never persisted) |

Inject these as attributes of a slim `AppContext` rather than one mutable blob.

**Agent benefit:** Changes to stat test state cannot accidentally break plot session; smaller blast radius.

#### B3. Replace module-level injection with constructor injection

Current pattern:

```python
ui_groups.uistate = uistate  # global mutation before UIsub()
```

Target pattern:

```python
class GroupMixin:
    def __init__(self, ctx: AppContext): ...
```

Or pass `ctx` as first argument to extracted free functions.

**Agent benefit:** Tests construct `AppContext` directly; no wiring block in `ui.py`.

**Risk:** Touches every mixin; do one mixin family per PR (same discipline as stats refactor).

#### B4. Define `Protocol` / host contracts for mixins

`StatTestMixin` already documents host requirements in a docstring — formalize this:

```python
class StatTestHost(Protocol):
    def get_group_testset_means(self, ...) -> ...: ...
    def graphRefresh(self) -> None: ...
```

Run `mypy` or static checks in CI. Agents get compile-time-ish guardrails.

---

### Tier C — Higher risk, long-term architecture

#### C1. Composition over multiple inheritance

Replace `UIsub(Mixin1, Mixin2, …)` with:

```python
class UIsub:
    def __init__(self):
        self.groups = GroupController(self, ctx)
        self.stats = StatTestController(self, ctx)
```

Controllers hold behavior; `UIsub` delegates `triggerNewGroup` → `self.groups.new()`.

**Agent benefit:** No MRO surprises, explicit dependency graph, easier mocking.  
**Cost:** Large rewrite; only justified after service layer exists.

#### C2. Event bus / command pattern for cross-cutting UI actions

Today: `group_new()` → `self.turn_heatmap_off()` → `self.apply_statistical_test_if_active()` → `self.graphRefresh()`.

An internal event bus (`GroupChanged`, `ViewChanged`) decouples producers from consumers. Handlers register once in `UIsub.__init__`.

**Agent benefit:** Adding a feature doesn't require tracing all call sites.

#### C3. Delete or quarantine legacy code

`analysis_v1.py`, `analysis_v2.py` (~1.7K LOC combined) are marked legacy. Move to `legacy/` or delete if truly unused.

**Agent benefit:** Stops agents from editing dead code or confusing v2/v3 APIs.

---

## 3. Separating UI from Other Functions

### Current separation map

```
┌─────────────────────────────────────────────────────────────┐
│  WELL SEPARATED (testable today)                            │
│  parse.py, analysis_v3.py, brainwash_stats/, export_data    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ direct imports
┌─────────────────────────────────────────────────────────────┐
│  PARTIALLY SEPARATED (domain logic + Qt side effects)       │
│  ui_data_frames.py, ui_stat_test.py, ui_parse.py            │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────┐
│  TIGHTLY COUPLED TO QT/MATPLOTLIB                           │
│  ui.py, ui_plot.py, ui_interactive.py, ui_widgets.py        │
│  ui_designer.py (generated), ui_graph.py                    │
└─────────────────────────────────────────────────────────────┘
```

### Recommended separation boundaries

| Layer | Responsibility | Qt? |
|-------|----------------|-----|
| **Domain** | Parse, detect events, build outputs, run stats | No |
| **Application** | Project lifecycle, cache paths, pipeline orchestration | No |
| **Presentation model** | "Given this state, what text goes on statusbar? What series to plot?" | No |
| **View adapters** | QWidget bindings, signal/slot wiring, canvas redraw | Yes |

### Highest-value extraction targets (ordered)

1. **Data pipeline** — Everything in `get_dft` → `get_dfoutput` → `get_dfmean` that doesn't touch widgets. `test_parse_click.py` already proves this path can run headless.

2. **Statusbar / applicability logic** — `_get_stat_test_warning`, `_get_statusbar_for_current_state`, `_format_io_regression_statusbar` are almost pure. Input: experiment type, groups, testsets, last `compute_statistical_comparison` result. Output: strings and visibility flags.

3. **Plot data preparation** — `ui_plot.py` likely mixes "compute what to draw" with "draw on canvas". Split `PlotModel` (numpy/pandas arrays, limits, colors) from `PlotView` (matplotlib artists, Qt canvas).

4. **Project persistence** — `ProjectMixin` load/save could be `project_io.py` with no Qt except file dialogs passed as callbacks.

5. **Keep in UI only** — Signal wiring, `setupUi`, focus handling, progress bars, thread lifecycle, mouse/drag handlers.

### Anti-pattern to avoid

Further mixin extraction **without** a service layer will keep producing large files (`ui_plot`, `ui_interactive`) that agents must read wholesale. File splits help humans grep; services help agents *and* tests.

---

## 4. Automatic Testing of UI Functions

### Current test landscape

| Suite | Count | Scope |
|-------|-------|-------|
| `test_parse.py` | ~108 | Domain parse pipeline |
| `test_statistics_characterization.py` | 7 | Stats contract / golden behavior |
| `test_parse_click.py` | Script (not pytest) | Headless pipeline + addRow simulation |
| UI/Qt tests | **0** | — |

There is no `pytest-qt`, `pytest-qtbot`, or snapshot testing in `pyproject.toml`.

### Testing strategy (layered — minimizes human verification)

#### Layer 1: Pure function tests (highest ROI, no Qt)

Extract and test what humans currently verify manually:

| Human check | Automated replacement |
|-------------|----------------------|
| IO switch → statusbar shows slope p, r², n | `test_statusbar_io_regression_format()` on pure formatter |
| experiment_type_changed → correct test frame visibility | `test_should_show_stat_test_frame()` |
| Group hide → plot data excludes hidden groups | `test_visible_recordings_filter()` |
| n_unit change → correct aggregation level | Extend stats fixtures + pipeline tests |

**This alone could eliminate ~60–70% of manual stat/view verification.**

#### Layer 2: Headless pipeline integration (extend `test_parse_click.py`)

Promote `test_parse_click.py` into pytest:

- Use fixtures from `src/lib/test_data/` (already documented in CONTRIBUTING)
- Parametrize over ABF/IBW/CSV samples
- Assert DataFrame shapes, column names, event detection invariants
- Add "golden" parquet snapshots for regression

No Qt required; covers the path from parse → click simulation.

#### Layer 3: Presentation model tests (still no display)

Test `PlotModel` outputs: given fixture project state, assert series count, xlim/ylim, group colors, test markers. Use `matplotlib` Agg backend (already done for frozen builds via `MPLCONFIGDIR`).

#### Layer 4: Qt widget tests with `pytest-qt`

Add `pytest-qt` to dev dependencies. Test:

| Category | Example |
|----------|---------|
| Signal wiring | `experiment_type_changed` updates `uistate.experiment_type` |
| Widget state | Radio button selection ↔ `uistate.test_type` |
| Table model | `TableMixin.tableUpdate` with mock `df_project` |
| Dialogs | `InputDialogPopup` returns expected string |

Use `qtbot` to click radios, check visibility, read `statusbar.currentMessage()` — **without a human**.

**Caveat:** Requires refactoring so handlers don't need a full loaded project. Start with widget-level tests after `AppContext` injection.

#### Layer 5: GUI smoke / screenshot regression (optional, CI-heavy)

Tools: `pytest-qt` + `QPixmap.grab`, or `pyautogui`, or dedicated visual diff.

Use sparingly for: dark mode toggle, graph layout after group plot. Flaky in CI; reserve for release gates.

#### Layer 6: End-to-end with real window (last resort)

`pytest-xvfb` on Linux for headless display. Launch `UIsub`, load fixture project, programmatically trigger actions.

Highest fidelity, highest maintenance. Only for critical paths not covered by layers 1–4.

### Recommended test infrastructure additions

```toml
# dev dependencies (conceptual)
pytest-qt
pytest-mock
# optional: pytest-xvfb for Linux CI
```

Plus:

- `tests/fixtures/minimal_project/` — tiny `.brainwash` + parquet cache
- `tests/fixtures/mock_host.py` — fake `UIsub` implementing `StatTestHost` protocol
- `tests/test_statusbar.py`, `tests/test_view_state.py`, `tests/test_pipeline_integration.py`
- CI job: `uv run pytest src/lib/ -q` (already 115 tests; would grow)

### What will still need humans (for now)

- Interactive plot drag/zoom "feel"
- Wayland/X11 platform quirks (documented in `main.py`)
- Visual aesthetics of graphs
- First-time parse of exotic file formats

These shrink as `ui_interactive` gains pure geometry helpers under test.

---

## 5. Prioritized Roadmap (Recommendation)

Phases are ordered by **agent safety ROI / risk ratio**, echoing the successful statistics refactor PR sequence.

| Phase | Work | Agent benefit | Risk |
|-------|------|---------------|------|
| **0** | Document architecture + mixin host contracts in one living doc | Orientation | None |
| **1** | Extract pure statusbar/applicability formatters + pytest | Removes manual IO/statusbar checks | Low |
| **2** | Promote `test_parse_click` → pytest; golden fixtures | Headless end-to-end safety | Low |
| **3** | Extract `RecordingPipelineService` from `DataFrameMixin` | Test pipeline without UI | Medium |
| **4** | Split `uistate` into 3–4 context objects | Smaller change blast radius | Medium |
| **5** | Add `pytest-qt` for signal/widget tests | Automated UI wiring verification | Medium |
| **6** | Package layout (`brainwash.*`) + constructor injection | Clean imports, testable wiring | Medium–high |
| **7** | Split `ui_plot` model/view | Plot regression without display | Medium–high |
| **8** | Composition controllers (optional) | Long-term maintainability | High |

**Do not** jump to Phase 8 before Phases 1–3. The stats refactor succeeded because it moved **behavior** first and kept the facade stable — not because it renamed files.

---

## 6. Summary Judgment

**Strengths:** Domain layers (`parse`, `analysis_v3`, `brainwash_stats`) are already agent-friendly. The statistics refactor is a replicable playbook. Mixin extraction improved navigability.

**Weaknesses:** UI remains a runtime monolith with global injection and implicit mixin contracts. Automated tests cover parse/stats but not statusbar, view state, or Qt wiring — which is exactly what `AGENTS.md` still asks humans to verify.

**Highest-leverage path:** Treat UI like stats — extract pure application logic into testable modules, keep `UIsub` as a thin Qt adapter, and build characterization tests for statusbar/view/pipeline before adding `pytest-qt`. That combination would make agentic development materially safer without a full rewrite.

---

## Related documents

- `work_plans/plan_ui_mixin_extraction.md` — ongoing file-level UI split
- `work_plans/Archive/mixin_problems.md` — drawbacks of current mixin pattern
- `work_plans/History/statistics_refactor/CONTRACT.md` — stats result contract (template for UI/statusbar)
- `work_plans/History/statistics_refactor/VERIFY.md` — per-PR verification discipline
- `AGENTS.md` — agent workflow and architectural guidelines