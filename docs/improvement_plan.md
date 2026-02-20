# Brainwash — Detailed Stepwise Improvement Plan

---

## Phase 1: Triage & Quick Wins *(low risk, high signal)*

### Step 1.1 — Install PyQt5 stubs to clear static analysis noise

The ~400 errors in `ui.py` are overwhelmingly caused by the type checker not finding PyQt5's Qt constants (`Qt.DisplayRole`, `Qt.Horizontal`, `QItemSelectionModel.Select`, etc.). Install stubs to turn that wall of noise into a meaningful signal.

Add `PyQt5-stubs` to `requirements-dev.txt`:
```
uv add --dev PyQt5-stubs
```
After installing, re-run diagnostics. The real logic errors (buried under stubs noise) will become visible.

---

### Step 1.2 — Fix the `build_dfstimoutput` missing-function bug

This is a real runtime crash. `ui.py` L4151 calls `analysis.build_dfstimoutput(...)` where `analysis` is `analysis_v2`. That function only exists in `analysis_v1`. The code path is triggered when `checkBox["output_per_stim"]` is `True`.

**Action:** Port `build_dfstimoutput` from `analysis_v1.py` into `analysis_v2.py`. It is self-contained and uses only `valid()`, `measureslope()`, numpy, and pandas — all already imported in `v2`. Add a `TODO: consolidate with build_dfoutput` comment since the docstring in `v1` already marks it as a temporary duplicate.

---

### Step 1.3 — Rename `parse_test.py` to `parse_legacy.py`

`parse_test.py` is not a test file — it is the old implementation of the parse pipeline (containing `parseProjFiles`, `assignStimAndsweep`, `importabf`). Its name actively misleads anyone reading the repo.

**Action:** `git mv src/lib/parse_test.py src/lib/parse_legacy.py`. Add a comment block at the top:

```python
# parse_legacy.py
# This is the pre-refactor parsing pipeline (pre parse.py v2 / source2dfs API).
# Kept for reference. Do NOT import from this file in new code.
# See parse.py for the current implementation.
```

---

### Step 1.4 — Fix `test_parse.py` to test the actual `parse.py`

`test_parse.py` imports from `parse` and calls `parseProjFiles` and `assignStimAndsweep` — functions that no longer exist in `parse.py`. The tests will fail immediately.

**Action:** Rewrite `test_parse.py` tests to cover the *current* `parse.py` API: `source2dfs`, `sources2dfs`, `parse_abf`, `parse_ibwFolder`, `persistdf`, `metadata`. The existing test structure (unittest, `setUp`/`tearDown`) and test data in `src/lib/test_data/` are good — only the called functions need updating.

---

## Phase 2: Type Safety — `UIstate` *(medium effort, removes ~200 cascading errors)*

### Step 2.1 — Add `Optional[...]` type annotations to `UIstate`

Every attribute in `UIstate.reset()` is assigned `None` with no annotation. Pyright infers all of them as `type[None]` permanently, which causes `Cannot access attribute X for class None` to cascade throughout all of `ui.py`.

**Action:** In `ui_state_classes.py`, annotate the key attributes at the class level *before* `reset()` is called:

```python
from typing import Optional
import pandas as pd
import matplotlib.axes

class UIstate:
    dfv:                    Optional[pd.DataFrame]
    dft_temp:               Optional[pd.DataFrame]
    df_rec_select_data:     Optional[pd.DataFrame]
    df_rec_select_time:     Optional[pd.DataFrame]
    df_recs2plot:           Optional[pd.DataFrame]
    axm:                    Optional[matplotlib.axes.Axes]
    axe:                    Optional[matplotlib.axes.Axes]
    ax1:                    Optional[matplotlib.axes.Axes]
    ax2:                    Optional[matplotlib.axes.Axes]
```

### Step 2.2 — Add the missing `darkmode` attribute

`ui.py` reads and writes `uistate.darkmode` in multiple places (L1741, L2574, L3747, L3767, L3779, L5049), but `UIstate.reset()` has it commented out:

```python
#self.darkmode = False # set by global bw cfg
```

**Action:** Uncomment it and add `darkmode: bool` to the class-level annotations. Then trace where `darkmode` is *set* from the config (the `write_bw_cfg`/`get_bw_cfg` methods in `UIsub`) to confirm the value flows correctly.

---

## Phase 3: Parse API Consolidation *(medium effort, removes technical debt)*

There are currently two completely different parse pipelines co-existing:

| File | API | Status |
|---|---|---|
| `parse.py` | `source2dfs`, `sources2dfs`, `metadata`, `persistdf` | **Active** — used by `ui.py` |
| `parse_legacy.py` (was `parse_test.py`) | `parseProjFiles`, `assignStimAndsweep`, `importabf` | **Legacy** — only referenced by old tests |

### Step 3.1 — Audit `parse.py` vs `parse_legacy.py` for feature gaps

Before deleting the legacy file, compare functionality:
- `parseProjFiles` handles the full project-level parse loop. Verify `ui.py → parseData → parse.sources2dfs` covers all the same logic (channel splitting, stim assignment, zeroing, mean building, `persistdf`).
- `assignStimAndsweep` — check if its logic is fully covered by the sweep/stim assignment inside `source2dfs`.
- `zeroSweeps` / `build_dfmean` — these are still in `parse.py` and called from `ui.py`. Confirm both implementations agree.

### Step 3.2 — Write integration tests for the full parse→analyze pipeline

Before deleting anything, add one integration test in `test_parse.py` that:
1. Calls `parse.source2dfs(test_abf_path)`
2. Calls `parse.persistdf(...)` into a temp folder
3. Calls `analysis.find_events(...)` on the result
4. Asserts the output has expected columns and no NaN in key fields

This gives a regression safety net before the next phases.

### Step 3.3 — Delete `parse_legacy.py` once tests pass

Once the integration test above passes using only `parse.py`, remove `parse_legacy.py`.

---

## Phase 4: CI/CD — Switch to `uv` *(low effort, high reproducibility gain)*

The project has `uv.lock` and is clearly a `uv` project, but both GitHub Actions workflows use `pip install -r requirements.txt`. This means CI builds do not benefit from the lockfile.

### Step 4.1 — Update both workflow files

Replace the install step in both `.github/workflows/*.yml`:

**Before:**
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
```

**After:**
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4
  with:
    version: "latest"
- name: Install dependencies
  run: uv sync --frozen
```

### Step 4.2 — Move `cx-Freeze` out of `requirements.txt`

`cx-Freeze` is a build tool, not a runtime dependency. Create `requirements-build.txt`:

```
cx-Freeze==8.5
```

Remove it from `requirements.txt`. Update both CI workflows to install from `requirements-build.txt` only in the build step, not the general install step.

### Step 4.3 — Pin the lockfile in CI

Add `--frozen` to `uv sync` to enforce the lockfile exactly in CI, preventing drift between local dev and build environments.

---

## Phase 5: `ui.py` Decomposition *(largest effort, highest long-term value)*

`ui.py` is a single 4900-line file with a monolithic `UIsub` class of ~200 methods. The file itself contains a table-of-contents comment identifying the logical sections. The decomposition follows those natural seams.

### Step 5.1 — Extract `ui_groups.py`

Move all group-management methods out of `UIsub` into a standalone mixin class. The group methods are well-bounded:

- `group_get_dd`, `group_save_dd`, `get_groupsOfRec`
- `group_new`, `group_remove_last_empty`, `group_remove_last`, `group_remove`, `group_rename`
- `group_rec_assign`, `group_rec_ungroup`, `group_selection`
- `group_cache_purge`, `group_controls_add`, `group_controls_remove`, `group_update_dfp`

These have minimal coupling to the Qt widget tree — they mainly operate on `df_project` and emit refresh signals.

### Step 5.2 — Extract `ui_sweep_ops.py`

Move all sweep editing operations into a mixin:

- `sweepsSelect`, `sweep_selection_valid`, `sweep_removal_valid_confirmed`
- `sweep_shift_gaps`, `sweep_remove_by_ID`, `sweep_keep_selected`, `sweep_remove_selected`
- `sweep_unselect`, `sweep_split_by_selected`
- `triggerKeepSelectedSweeps`, `triggerRemoveSelectedSweeps`, `triggerSplitBySelectedSweeps`

These are among the most complex methods in the codebase and are entirely data-manipulation — no direct widget drawing.

### Step 5.3 — Extract `ui_project.py`

Move all project-level file I/O into a mixin:

- `newProject`, `openProject`, `clearProject`, `renameProject`
- `get_df_project`, `set_df_project`, `load_df_project`, `save_df_project`
- `get_bw_cfg`, `write_bw_cfg`
- `df2file`, `persistOutput`
- `loadProject`, `bootstrap`

### Step 5.4 — Extract `ui_data_frames.py`

Move the internal DataFrame computation layer:

- `get_dfv`, `get_dfmean`, `get_dft`, `get_dfoutput`, `get_dfdata`
- `get_dffilter`, `get_dfbin`, `get_dfdiff`, `get_dfgroupmean`
- `set_dft`, `set_uniformTimepoints`, `recalculate`
- `binSweeps`

This is the most self-contained section — pure data transformation with no widget dependencies.

### Step 5.5 — Implement mixins via multiple inheritance

The extracted modules should each define a mixin class (e.g. `GroupMixin`, `SweepOpsMixin`, `ProjectMixin`, `DataFrameMixin`). `UIsub` then composes them:

```python
from ui_groups import GroupMixin
from ui_sweep_ops import SweepOpsMixin
from ui_project import ProjectMixin
from ui_data_frames import DataFrameMixin

class UIsub(Ui_MainWindow, GroupMixin, SweepOpsMixin, ProjectMixin, DataFrameMixin):
    def __init__(self, MainWindow):
        ...
```

This keeps backward compatibility (all method names remain on `UIsub`) while making each concern independently readable and testable.

---

## Phase 6: Analysis Cleanup *(medium effort)*

### Step 6.1 — Remove jupytext headers from `analysis_v2.py`

`analysis_v2.py` has jupytext metadata and `# %%` cell markers at the top, plus module-level side effects:

```python
reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))
```

These run on every import and are path-sensitive (they assume CWD is the repo root). Remove them and the jupytext header. If notebook-style exploration is needed, maintain a separate `notebook/analysis_dev.py` linked via jupytext to `analysis_v2.py`.

### Step 6.2 — Resolve the duplicate `check_sweep` definitions

Both `analysis_v2.py` (L818 and L842) and `analysis_evaluation.py` (L381 and L397) define `check_sweep` twice each. Python silently uses the last definition. Decide which is canonical, name the other `check_sweep_legacy`, and add a comment explaining the difference.

### Step 6.3 — Plan `analysis_v1.py` retirement

`analysis_v1.py` is no longer imported by `ui.py` (it imports `analysis_v2 as analysis`). Audit what remains in `v1` that `v2` still lacks:
- `build_dfstimoutput` — addressed in Step 1.2
- `find_i_EPSP_peak_max`, `find_i_VEB_prim_peak_max`, `find_i_volley_slope` — check if equivalents exist in `v2`'s `find_events` / `characterize_graph`

Once all gaps are covered, delete `analysis_v1.py` and update any remaining references.

---

## Phase 7: Documentation & Developer Experience

### Step 7.1 — Add a `CONTRIBUTING.md`

Document:
- How to set up the dev environment with `uv`
- How to run tests (`uv run python -m pytest src/lib/`)
- The module layout after Phase 5 refactoring
- The analysis pipeline (parse → zero → filter → find_events → build_dfoutput)

### Step 7.2 — Migrate dependencies into `pyproject.toml`

`pyproject.toml` currently has no `[project.dependencies]` key — all deps live in `requirements.txt`. Migrate them so `uv sync` drives everything:

```toml
[project]
name = "brainwash"
version = "0.10.0"
requires-python = ">=3.12"
dependencies = [
    "pyqt5",
    "pandas",
    "numpy",
    "scipy",
    "scikit-learn",
    "matplotlib",
    "seaborn",
    "pyabf",
    "igor2",
    "joblib",
    "tqdm",
    "pyyaml",
    "toml",
    "requests",
    "pyarrow",
]

[project.optional-dependencies]
dev = [
    "jupyterlab",
    "jupytext",
    "flake8",
    "flake8-black",
    "black",
    "isort",
    "PyQt5-stubs",
    "pytest",
]
build = [
    "cx-Freeze==8.5",
]
```

### Step 7.3 — Fix empty f-strings

Search and fix all empty f-strings flagged in warnings (e.g. `f"some literal"`). These suggest interpolated variables were accidentally dropped during edits. Fix each to either remove the `f` prefix or restore the intended variable.

```
# Find them all:
grep -rn 'f"[^{]*"' src/lib/ui.py
```

---

## Execution Order Summary

| Phase | Steps | Risk | Effort |
|---|---|---|---|
| **1 – Triage** | 1.1 → 1.4 | Low | ~2–4 hrs |
| **2 – Type Safety** | 2.1 → 2.2 | Low | ~2–3 hrs |
| **3 – Parse API** | 3.1 → 3.3 | Medium | ~4–6 hrs |
| **4 – CI/CD** | 4.1 → 4.3 | Low | ~1 hr |
| **5 – ui.py Decomposition** | 5.1 → 5.5 | High | ~2–3 days |
| **6 – Analysis Cleanup** | 6.1 → 6.3 | Medium | ~4–6 hrs |
| **7 – Docs & DX** | 7.1 → 7.3 | Low | ~2–3 hrs |

**Dependency order:**
- Phases 1–4 can be executed in any order relative to each other.
- Phase 5 should follow Phases 1–2 so type errors do not create false confidence during the refactor.
- Phase 6 should follow Phase 3 (parse consolidation) to avoid accidentally resurrecting dead code paths.
- Phase 7 should follow Phase 5 so the documented module layout reflects reality.