# ARCHIVE — do not read in normal sessions

> Full pre-chop spec kept for forensics only. Use micro-plans 01–11 instead.

`statsmodels` is **not** in `pyproject.toml` dependencies (verified: `ModuleNotFoundError` in clean venv). Used lazily for:

- IO regression OLS slope test (`_compute_io_regression_internal` L167–169) — has scipy RSS fallback L187–210
- FDR via `multipletests` in 6+ branches — silently `except: pass` on import failure

Phase 0 must record whether FDR q-values are produced with/without statsmodels. Phase 1 FDR unification requires explicit parity tests (`_bh_fdr` vs `multipletests` with `p→1.0` NaN replacement) before deleting `multipletests` calls.

**Decision gate (Phase 0 exit)**: Either add `statsmodels` to `[dependency-groups] dev` for characterization tests, or accept `_bh_fdr`-only path and document that FDR without statsmodels is the supported behavior.

### 4. Line numbers drift — use symbol anchors

All phase tasks reference **function names and branch comments**, not line numbers. Before each PR, agent runs:

```sh
uv run python -c "from src.lib.statistics import compute_statistical_comparison; print('import ok')"
```

---

## Design Principles

Aligned with `AGENTS.md`:

1. **Thin dispatcher** — `compute_statistical_comparison` becomes ~80–120 LOC: validate → build context → dispatch → return.
2. **One module per test family** — agents edit `stats/tests/wilcoxon.py`, not a 1500-line file.
3. **Shared helpers extracted first** — lowest risk; eliminates duplication before moving branches.
4. **Explicit dispatch registry** — deferred to **Phase 4 only**; Phase 3 keeps ordered `if` chain mirroring current guard order to avoid half-migrated registry bugs.
5. **Stable result contract** — document `{"results": [...], "config": {...}}` + error shapes; no shape changes in refactor.
6. **No behavior changes** — refactor only; statistical bug fixes and dead-path activation deferred unless blocking extraction.
7. **Facade compatibility** — keep `src/lib/statistics.py` as thin re-export so `ui.py` import path unchanged.
8. **Characterization before motion** — no production file moves until Phase 0 greens.

---

## Target Module Layout

```
src/lib/
  statistics.py              # FACADE: re-exports public API (≤30 LOC)
  stats/
    __init__.py              # optional internal exports for tests
    types.py                 # StatContext, ComparisonMode (Phase 2+)
    validation.py            # input guards, shown_groups/sets, hierarchy check
    data.py                  # get_obs, aggregate_to_unit_level, aspect_columns
    fdr.py                   # bh_fdr, apply_fdr_to_results
    assumptions.py           # Shapiro-Wilk, Levene
    io/
      __init__.py
      xy_pairs.py            # _get_io_xy_pairs
      regression.py          # _compute_io_regression_internal
      implicit_anova.py      # L518–636 (latent / dead today)
    tests/
      __init__.py
      anova.py
      ttest.py
      wilcoxon.py
      friedman.py
      cluster_perm.py
    per_sweep.py             # ttest_per_sweep
    dispatcher.py            # compute_statistical_comparison body
  test_statistics_fixtures.py
  test_statistics_characterization.py
```

### File size targets

| Module                 | Target LOC   | Rationale                                       |
| ---------------------- | ------------ | ----------------------------------------------- |
| `dispatcher.py`        | 80–120       | Agent reads entire dispatch logic in one screen |
| Each `tests/*.py`      | 150–250      | One test type, one file                         |
| `data.py`, `fdr.py`    | 80–150       | Pure helpers, easy to unit test                 |
| `io/*.py`              | 100–200 each | IO semi-isolated (top of `statistics.py`)       |
| Facade `statistics.py` | ≤30          | Zero logic                                      |

### Dependency graph (no cycles)

```
types.py
  ↓
validation.py, data.py, fdr.py, assumptions.py
  ↓
io/*, tests/*, per_sweep.py
  ↓
dispatcher.py
  ↓
statistics.py (facade)
```

---

## Core Abstractions

Introduce **only in Phase 2** after helpers are extracted and characterized. Phase 0–1 use plain functions and existing parameter lists.

### 1. `StatContext` (dataclass in `types.py`, Phase 2+)

Replace repeated parameter threading and closure-captured locals (`shown_groups`, `use_implicit`, `g1`, `g2`, etc.).

```python
@dataclass
class StatContext:
    groups: list
    dd_groups: dict
    dd_testsets: dict
    get_group_testset_means_fn: Callable
    test_type: str
    variant: str
    tails: str
    fdr: bool
    norm: bool
    amp: bool
    slope: bool
    ref: float
    n_unit: str
    experiment_type: str
    uistate: Any | None

    # Resolved after validation (set by build_context)
    shown_groups: list = field(default_factory=list)
    shown_sets: list = field(default_factory=list)  # [(sid, tset), ...]
    use_implicit: bool = False
    g1: str | None = None
    g2: str | None = None
    mode: ComparisonMode = ComparisonMode.UNPAIRED_TWO_GROUP
```

Handlers receive `(ctx: StatContext) -> dict`. Accessors:

- `ctx.get_obs(g, tset, col, per_sweep=False)` — single implementation in `data.py`, bound on context
- `ctx.aspects()` — returns `[("amp", "EPSP_amp"), ...]` from `data.aspect_columns(ctx)`

### 2. `ComparisonMode` enum (`types.py`, Phase 2+)

Extract order-sensitive guard block (L464–488 + early IO guards) into explicit mode resolution.

| Mode                 | Conditions                                              | Notes                                   |
| -------------------- | ------------------------------------------------------- | --------------------------------------- |
| `ONE_SAMPLE`         | `variant == "one-sample"`                               |                                         |
| `RM_ANOVA`           | `test_type == "ANOVA"` and 1 group, ≥2 test sets        |                                         |
| `RM_FRIEDMAN`        | `test_type == "Friedman"` and 1 group, ≥3 test sets     |                                         |
| `CLUSTER`            | `test_type == "Cluster perm."`                          | Before paired guard                     |
| `PAIRED`             | `variant == "paired"` (1 group, 2 test sets)            |                                         |
| `IO_REGRESSION`      | `experiment_type == "io"` and `use_implicit`            | **Wins over** `IO_IMPLICIT_ANOVA` today |
| `IO_IMPLICIT_ANOVA`  | `test_type == "ANOVA"` and `use_implicit` and ≥2 groups | Latent unless L504 guard changes        |
| `UNPAIRED_TWO_GROUP` | default (≥2 groups)                                     |                                         |
| `UNPAIRED_ANOVA`     | `test_type == "ANOVA"` with ≥2 groups (main loop)       |                                         |

`validation.resolve_mode(ctx) -> ComparisonMode` must be backed by **executable precedence tests** (table below), not prose alone.

#### Mode precedence test vectors (Phase 0.5 — add before any extraction)

| #   | test_type     | variant    | experiment_type | shown_groups | shown_sets | Expected mode (current code)              |
| --- | ------------- | ---------- | --------------- | ------------ | ---------- | ----------------------------------------- |
| 1   | t-test        | unpaired   | time            | 2            | 1          | UNPAIRED_TWO_GROUP                        |
| 2   | t-test        | paired     | time            | 1            | 2          | PAIRED                                    |
| 3   | t-test        | one-sample | time            | 1            | 1          | ONE_SAMPLE                                |
| 4   | ANOVA         | unpaired   | time            | 1            | 2          | RM_ANOVA                                  |
| 5   | Friedman      | unpaired   | time            | 1            | 3          | RM_FRIEDMAN                               |
| 6   | Cluster perm. | unpaired   | time            | 2            | 1          | CLUSTER                                   |
| 7   | Cluster perm. | paired     | time            | 1            | 2          | CLUSTER (not PAIRED)                      |
| 8   | ANOVA         | unpaired   | io              | 2            | 0          | **IO_REGRESSION** (not IO_IMPLICIT_ANOVA) |
| 9   | t-test        | unpaired   | io              | 2            | 0          | IO_REGRESSION                             |
| 10  | ANOVA         | unpaired   | time            | 0            | —          | error: no shown groups                    |
| 11  | t-test        | unpaired   | time            | 2            | 0          | error: no shown test sets                 |

Implement as `test_resolve_mode_vectors` once `resolve_mode` exists; until then, as direct `compute_statistical_comparison` smoke calls checking `config["type"]` / `error` keys.

### 3. Unified FDR helper (`fdr.py`, Phase 1b+)

Two patterns today:

- **Omnibus row** (single result dict): IO ANOVA, RM ANOVA, Friedman
- **Per test-set index** (tuple `(res_idx, p_key)`): Wilcoxon, main t-test loop
- **Raw float list** (Cluster perm.)

```python
def apply_fdr(
    results: list[dict],
    p_keys: list[str] | list[tuple[int, str]],
    *,
    method: str = "bh",
) -> None:  # mutates results in place
```

**Parity requirement**: Before replacing `multipletests`, add tests comparing q-values on fixed p-vector including `nan` inputs (note: multipletests replaces non-finite with `1.0`; `_bh_fdr` does not — document chosen behavior, do not silently change).

### 4. Dispatch registry (`dispatcher.py`, Phase 4 only)

```python
MODE_HANDLERS: dict[ComparisonMode, Callable[[StatContext], dict]] = { ... }
```

Phase 3 PRs wire handlers via **ordered early returns** identical to current `if` chain. Registry conversion is a single final PR with zero logic change (characterization tests must pass unchanged).

---

## Result Contract (do not change)

Document in `types.py` module docstring for agent reference:

### Success

```python
{"results": [result_row, ...], "config": {..., "n_unit": str, ...}}
```

### Errors (existing keys)

```python
{"error": str, "results": []}
{"not_implemented": str, "results": []}
# hierarchy missing (L658–663):
{"error": "subject not assigned...", "results": [], "config": {"n_unit": str}}
```

### Key `config` shapes (statusbar depends on these)

| Path                       | `config["type"]` or `config["test_type"]` | Critical fields                                                             |
| -------------------------- | ----------------------------------------- | --------------------------------------------------------------------------- |
| IO regression              | `"IO regression"`                         | `x_col`, `y_col`, `group_ns`, `slope_p`, `r2_per_group`, `implicit_testset` |
| IO implicit ANOVA (latent) | `"ANOVA"`                                 | `implicit_testset`, `n_unit`                                                |
| Cluster                    | `test_type: "Cluster perm."`              | `note`, `n_unit: "recording"`                                               |
| Others                     | `type` or `test_type`                     | `variant`, `tails`, `fdr`, `norm`, `amp`, `slope`                           |

### Key `result_row` fields

- Per test set: `set_id`, `set_name`, `sweeps`, `group1`, `group2`, `n1`, `n2`, `p_amp`, `p_slope`, `stat_*`, `q_*`, `eta2`, `group_ns`, `anova_note`
- IO sentinels: `set_id` in `("__io_regression_implicit__", "__io_anova_implicit__", "__anova_rm_omnibus__", "__friedman_rm_omnibus__")`

### Golden snapshot normalization rules

When serializing characterization expected outputs:

- Sort dict keys alphabetically at each level
- Round floats to 8 decimal places (`pytest.approx` rel=1e-6)
- Replace non-deterministic cluster perm. p-values with `"__CLUSTER_SKIP__"` when MNE absent
- Strip keys that are always `nan` in fixtures (document omissions in fixture module)

---

## Implementation Phases (Safety-First)

Each phase is a separate PR. **No phase may merge without passing characterization tests.**  
Max diff per PR: **≤400 LOC moved** (excluding test files); split if larger.  
After final phase merge: move this file to `work_plans/History/plan_statistics_refactor.md`.

### Phase 0 — Characterization tests (no production code moves)

**Goal**: Lock current behavior before any file split.

**Agent steps**:

1. Read `compute_statistical_comparison` signature (L413–450) and result-return paths only — do not read entire file.
2. Create `src/lib/test_statistics_fixtures.py`:
   - `make_mock_accessor(...)` returning DataFrames with `rec_ID`, `subject`, `slice`, `value`
   - `make_dd_groups(...)`, `make_dd_testsets(...)` matching UI shape (`show`, `rec_IDs`, `sweeps`)
   - `MinimalUistate` stub with `io_input`, `io_output` for IO tests
   - `BoundMethodAccessor` wrapping mock with `__self__` for IO `__self__` recovery path
3. Create `src/lib/test_statistics_characterization.py` with golden tests for:
   - Unpaired t-test (2 groups, 1 test set, amp only)
   - Paired t-test (1 group, 2 test sets)
   - One-sample t-test
   - Between-groups ANOVA (≥2 groups)
   - RM ANOVA (1 group, ≥2 test sets)
   - Friedman (1 group, ≥3 test sets)
   - Wilcoxon paired + one-sample
   - Cluster perm. between + paired — `pytest.importorskip("mne")`
   - IO regression (`experiment_type="io"`, empty test sets) → assert `config["type"] == "IO regression"`
   - IO+ANOVA+empty test sets → **same as IO regression** (documents dead implicit ANOVA)
   - Error paths: no groups, no test sets (non-IO), `not_implemented`, missing hierarchy
   - FDR on/off for one t-test case (record actual q behavior given statsmodels presence)
4. Optional: one-shot baseline capture script `snippets/capture_stats_golden.py` (delete after Phase 0 merge)

**Exit criteria**:

- ≥12 characterization tests green on current `statistics.py`
- Import smoke: `uv run python -c "from src.lib import statistics"`
- `uv run pytest src/lib/test_statistics_characterization.py -q`

### Phase 0.5 — Precedence smoke tests (no production moves)

Add `test_mode_precedence_smoke` implementing the 11-vector table above using direct `compute_statistical_comparison` calls. These tests are the safety net for Phase 2 `resolve_mode` and Phase 3 handler extraction.

**Exit criteria**: All 11 vectors pass; documented in test docstring.

### Phase 1a — Extract pure helpers in-place (`statistics.py` only)

**No new package, no dataclasses, no enums.** Lowest-risk duplication removal.

Extract as **module-level private functions** at top of `statistics.py` (below existing IO helpers):

| Extract                    | From                 | To (same file)                          |
| -------------------------- | -------------------- | --------------------------------------- |
| `_aggregate_to_unit_level` | nested L667          | module-level `_aggregate_to_unit_level` |
| `_get_obs` factory         | L530/L720 duplicates | `_make_get_obs(use_implicit, fn)`       |
| Aspect builder             | scattered            | `_aspect_columns(amp, slope, norm)`     |
| Shapiro/Levene block       | L1400–1442           | `_apply_assumption_tests(...)`          |

Delete duplicate `_get_obs` at L530; implicit IO ANOVA uses shared factory.

**Exit criteria**: Phase 0 + 0.5 green; `statistics.py` shrinks ~150 LOC; zero import path changes.

### Phase 1b — Move helpers to `stats/` package (re-import facade)

Move Phase 1a helpers + existing top-of-file symbols to package modules; **re-import into `statistics.py`** so `from . import statistics` unchanged:

| Extract                                                        | To                       |
| -------------------------------------------------------------- | ------------------------ |
| `_bh_fdr`                                                      | `stats/fdr.py`           |
| `_aggregate_to_unit_level`, `_make_get_obs`, `_aspect_columns` | `stats/data.py`          |
| Shapiro/Levene                                                 | `stats/assumptions.py`   |
| `_get_io_xy_pairs`                                             | `stats/io/xy_pairs.py`   |
| `_compute_io_regression_internal`                              | `stats/io/regression.py` |
| `ttest_per_sweep`                                              | `stats/per_sweep.py`     |

Implement `apply_fdr` in `stats/fdr.py` only after parity tests from Phase 0 FDR cases pass.

**Exit criteria**: All tests green; `statistics.py` shrinks ~350 LOC total vs baseline; `uv run flake8 src/lib/statistics.py src/lib/stats/`.

### Phase 2 — Extract IO implicit ANOVA + validation + `StatContext`

| Extract                        | To                                                                                    |
| ------------------------------ | ------------------------------------------------------------------------------------- |
| Early IO ANOVA branch L518–636 | `stats/io/implicit_anova.py` → `run_io_implicit_anova(ctx)`                           |
| Top guards L451–516            | `stats/validation.py` → `validate_and_build_context(**kwargs) -> StatContext \| dict` |

Introduce `StatContext` + `ComparisonMode` + `resolve_mode` with precedence table tests wired to enum.

**Critical**: Preserve L504 before implicit ANOVA in dispatcher — extraction must not reorder guards.

**Exit criteria**: Phase 0–0.5 green; vector #8 still returns IO regression.

### Phase 3 — Extract test handlers (one PR per test type)

Order by isolation (least coupled first). Each PR: cut/paste branch → `run_*(ctx) -> dict`; wire via **ordered early return** (not registry).

1. `friedman.py`
2. `anova.py` (RM omnibus only)
3. `wilcoxon.py`
4. `cluster_perm.py` — remove DEBUG prints during move (only cleanup allowed)
5. `ttest.py` (main loop; largest)

**Per-PR agent budget**: Read only the target branch + `validation.py` + `data.py`. Do not read other test handlers.

**Exit criteria**: `compute_statistical_comparison` body ≤120 LOC; all characterization tests green.

### Phase 4 — Facade + registry + cleanup

1. Move dispatcher body to `stats/dispatcher.py`
2. Replace `statistics.py` body with re-exports:

```python
from .stats.dispatcher import compute_statistical_comparison
from .stats.per_sweep import ttest_per_sweep
from .stats.fdr import bh_fdr as _bh_fdr
```

3. Convert ordered `if` chain → `MODE_HANDLERS` registry (no logic change — run full suite before/after)
4. Remove dead comments ("Phase 0", "v0.16_n_stats", DEBUG prints)
5. Update `AGENTS.md` module layout bullet: `src/lib/stats/` package

**Exit criteria**: `uv run pytest src/lib/test_statistics_characterization.py -q`; manual smoke (below).

---

## Verification Checklist (per phase — mandatory)

### Automated (run after every PR)

```sh
uv run python -c "from src.lib import statistics; from src.lib.statistics import compute_statistical_comparison; print('ok')"
uv run pytest src/lib/test_statistics_characterization.py -q
uv run flake8 src/lib/stats/ src/lib/statistics.py
```

### Agent self-check (`/check-work` or review skill)

After each phase, run check-work against the PR diff:

- No `compute_statistical_comparison` signature change
- No new `getattr(uistate, ...)` in stats layer
- No statusbar / UI imports inside `stats/`
- Guard order preserved (compare precedence vector tests)
- Diff ≤400 LOC production code (excluding tests)

### Manual smoke (project with ≥2 groups + sweep data)

- [ ] Time experiment: unpaired t-test → statusbar shows p, n_report
- [ ] Switch `n_unit` subject/slice/recording → n updates
- [ ] IO mode: no test sets → IO regression statusbar (`slope_p`, `r²`, `group_ns`) — **not** implicit ANOVA
- [ ] Cluster perm. → recording-level note in config
- [ ] Old project (no subject/slice) → hierarchy warning string unchanged

---

## Agentic Development Guidelines

### Session rules (one agent, one PR)

1. **Read budget**: Max 3 production files per session (`statistics.py` section + 1–2 target modules). Use `grep` for discovery; never read full `ui.py`.
2. **Edit budget**: One handler or helper family per PR. No drive-by fixes in `ui.py`.
3. **Tooling**: `search_replace` after targeted `read_file(offset/limit)`. No whole-file rewrites of `statistics.py` until Phase 4.
4. **Verification order**: import smoke → characterization pytest → flake8 → `/check-work` → manual smoke only for IO/statusbar phases.
5. **Stuck protocol**: If characterization test fails after extraction, **revert the extraction** and narrow scope; do not patch golden tests to match drift unless audit proves old test was wrong.

### Post-refactor task routing

| Task               | Read first                                                                   | Edit                                            |
| ------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------- |
| Wilcoxon bug       | `stats/tests/wilcoxon.py`                                                    | same                                            |
| FDR wrong q        | `stats/fdr.py`                                                               | same                                            |
| IO statusbar shape | `stats/io/regression.py`, result contract above                              | same                                            |
| New test type      | Phase 0-style characterization test in `test_statistics_characterization.py` | new `stats/tests/<name>.py` + dispatcher wiring |

### Anti-patterns to avoid

- Re-expanding `dispatcher.py` with inline test logic
- New `getattr(uistate, ...)` fallbacks in stats layer (pass via `StatContext.uistate` explicitly)
- Multiple `_get_obs` definitions "for early return"
- Mixing statusbar formatting into stats (stays in `ui.py`)
- Introducing `MODE_HANDLERS` before all handlers extracted
- Creating `tests/` top-level directory without updating `pyproject.toml`
- "Fixing" dead IO implicit ANOVA path during refactor (behavior change)
- Updating golden tests without written audit justification

### Parallel PRs (Phase 3 only)

Use isolated git worktrees (`best-of-n` / worktree skill) for `friedman`, `wilcoxon`, `cluster_perm` — they touch disjoint branch bodies. **Do not** parallelize Phase 1–2 (shared helper surface).

---

## Risk Register

| Risk                                       | Mitigation                                                                               |
| ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Silent numeric drift                       | Golden characterization tests + fixed-seed mock data                                     |
| Import cycles                              | Enforce DAG; `types.py` has no stats imports                                             |
| Order-dependent guards broken              | Precedence vector tests (Phase 0.5) + no registry until Phase 4                          |
| MNE optional dep                           | `pytest.importorskip("mne")` in cluster tests                                            |
| statsmodels absent                         | Document FDR behavior; parity tests before unification; dev dep decision at Phase 0 exit |
| `__self__` mixin recovery for IO           | `BoundMethodAccessor` in fixtures; keep in `xy_pairs.py`; document coupling              |
| Large Phase 3 PR                           | One test type per PR; ≤400 LOC moved                                                     |
| Dead IO ANOVA extraction breaks future fix | Extract as-is; mark latent in module docstring; precedence test #8                       |
| Line number drift                          | Symbol anchors only in task descriptions                                                 |
| Agent context bloat                        | Per-PR read budget; archive this plan after merge                                        |

---

## Out of Scope (this refactor)

- Fixing statistical methodology (RM-ANOVA sphericity, key-based paired alignment, one-sided `ttest_ind_from_stats`)
- Activating IO implicit ANOVA path (reordering L504 vs L518) — separate product decision
- UI/statusbar refactor (`work_plans/plan.md` experiment-type work)
- Moving `ttest_df` from `analysis_v3.py`
- Adding type hints across entire package (only `StatContext` dataclass)
- New test types (PP, LMM)

---

## Success Metrics

| Metric                               | Before    | After               |
| ------------------------------------ | --------- | ------------------- |
| `statistics.py` LOC                  | ~1498     | ≤30 (facade)        |
| `compute_statistical_comparison` LOC | ~1080     | ≤120                |
| Longest module LOC                   | 1498      | ≤250                |
| `_get_obs` definitions               | 3         | 1                   |
| FDR implementations                  | ~8 inline | 1 helper            |
| Stats characterization tests         | 0         | ≥12 + 11 precedence |
| `ui.py` import changes               | —         | 0                   |

---

## PR Stack (suggested)

1. `stats-phase0-characterization-tests`
2. `stats-phase0.5-precedence-smoke`
3. `stats-phase1a-inplace-helpers`
4. `stats-phase1b-extract-helper-package`
5. `stats-phase2-io-validation-context`
6. `stats-phase3a-friedman-anova` (parallel-safe)
7. `stats-phase3b-wilcoxon` (parallel-safe)
8. `stats-phase3c-cluster-perm` (parallel-safe)
9. `stats-phase3d-ttest-main-loop` (sequential — largest)
10. `stats-phase4-facade-registry-cleanup`

Each PR description: **"Refactor only; behavior locked by characterization + precedence tests."**

### PR template for agents

```markdown
## Scope

- Phase: <N>
- Files touched: <list>
- LOC moved: <n> (max 400 production)

## Pre-read (offset/limit)

- statistics.py: <symbol> only
- ...

## Verification

- [ ] import smoke
- [ ] pytest src/lib/test_statistics_characterization.py
- [ ] precedence vectors (if Phase ≥2)
- [ ] flake8
- [ ] /check-work
```

---

## References

- `AGENTS.md` — thin dispatcher, IO early guard, statusbar config contract
- `CONTRIBUTING.md` — tests live in `src/lib/`, `uv run pytest src/lib/`
- `work_plans/Archive/plan_v0.16_n_stats.md` — n_unit / aggregation semantics
- `work_plans/plan.md` — UI experiment_type architecture (orthogonal)
- `src/lib/ui.py:1791–1824` — IO regression call site
- `src/lib/ui.py:1977–1985` — IO UI never hits implicit ANOVA branch
- `src/lib/ui.py:2105–2124` — non-IO test call site
