# Contributing to Brainwash

Thank you for your interest in contributing! This document covers everything you need to get a working development environment, run the tests, and understand how the codebase is structured.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Dev Environment Setup](#dev-environment-setup)
3. [Running Tests](#running-tests)
4. [Module Layout](#module-layout)
5. [Analysis Pipeline](#analysis-pipeline)
6. [Code Style](#code-style)
7. [Dependency Management](#dependency-management)

---

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — the project's dependency and environment manager

Install `uv` if you don't have it:

```sh
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Dev Environment Setup

1. **Clone the repository:**

   ```sh
   git clone <repo-url>
   cd brainwash
   ```

2. **Install all dependencies (runtime + dev) from the lockfile:**

   ```sh
   uv sync --all-groups
   ```

   This creates a `.venv` in the project root and installs every dependency pinned in `uv.lock`, including the dev-only tools (`pytest`, `black`, `isort`, `flake8`, `jupyterlab`, `jupytext`, `PyQt5-stubs`).

3. **Verify the install:**

   ```sh
   uv run python -c "import PyQt5; import pandas; import numpy; print('OK')"
   ```

4. **Run the application:**

   ```sh
   uv run python src/main.py
   ```

> **Note:** The project targets Python 3.12. Using a different version may cause subtle issues with PyQt5 and the pinned scientific stack.

---

## Running Tests

Tests live alongside the source in `src/lib/` and are discovered by `pytest`.

**Run the full test suite:**

```sh
uv run python -m pytest src/lib/
```

**Run a specific test file:**

```sh
uv run python -m pytest src/lib/test_parse.py -v
```

**Run with output captured off (useful when tests print a lot):**

```sh
uv run python -m pytest src/lib/ -s
```

Test data fixtures are kept in `src/lib/test_data/`. When writing new tests, add small representative `.abf` or `.ibw` files there rather than generating data synthetically — the parse pipeline is sensitive to real file structure.

---

## Module Layout

The source code lives entirely under `src/lib/`. Below is an annotated map.

```
src/
├── main.py                  Entry point. Creates the QApplication and launches UIsub.
└── lib/
    ├── ui.py                Top-level UI class (UIsub). Composes all mixins.
    │                        Still the largest file; see the mixin modules below for
    │                        the extracted concerns.
    │
    ├── ui_groups.py         GroupMixin — group management (create, rename, remove,
    │                        assign recordings, purge cache).
    │
    ├── ui_sweep_ops.py      SweepOpsMixin — sweep selection and editing operations
    │                        (select even/odd, remove, keep, split by selection).
    │
    ├── ui_project.py        ProjectMixin — project lifecycle (new, open, save, load),
    │                        global config (bw_cfg), file persistence (df2file,
    │                        persistOutput), and startup bootstrapping.
    │
    ├── ui_data_frames.py    DataFrameMixin — all internal DataFrame caching and
    │                        transformation: dfv, dfmean, dft, dfoutput, dffilter,
    │                        dfbin, dfdiff, dfgroupmean, uniform timepoints.
    │
    ├── ui_plot.py           Plotting helpers (figure/axes construction, graph update
    │                        callbacks, dark-mode toggling).
    │
    ├── ui_state_classes.py  UIstate dataclass and related state containers. Holds
    │                        all transient UI state (selected recordings, checkboxes,
    │                        cached DataFrames, axes references, etc.).
    │
    ├── parse.py             Active parse pipeline. Public API:
    │                          source2dfs(path)  →  (dfdata, dfmean, metadata_dict)
    │                          sources2dfs(paths) →  combined DataFrame
    │                          parse_abf(path)
    │                          parse_ibwFolder(path)
    │                          persistdf(df, folder)
    │                          metadata(path)
    │
    ├── analysis_v2.py       Active analysis engine. Public API:
    │                          find_events(dfmean, dfdata, config)
    │                          build_dfoutput(dfdata, events, config)
    │                          characterize_graph(dfmean, config)
    │                          valid(value, lo, hi)
    │                          measureslope(dfmean, i_start, i_end)
    │
    ├── analysis_evaluation.py  Evaluation helpers used alongside analysis_v2.
    │
    ├── analysis_v1.py       Legacy analysis engine — kept for reference only.
    │                        Not imported by ui.py. Do not add new code here.
    │
    └── test_parse.py        pytest test suite for the parse pipeline.
```

### Mixin composition

`UIsub` inherits from all mixin classes plus the Qt-generated `Ui_MainWindow`:

```python
class UIsub(Ui_MainWindow, GroupMixin, SweepOpsMixin, ProjectMixin, DataFrameMixin):
    ...
```

All methods therefore remain available as `self.<method>()` throughout the class, preserving full backward compatibility while allowing each concern to be read and tested in isolation.

**Module-level singleton injection** — because the mixin files are plain Python modules (not packages), they receive the shared singletons (`uistate`, `config`, `uiplot`, …) through module-level assignment performed by `ui.py` at startup, before any `UIsub` instance is created:

```python
import ui_groups
ui_groups.uistate = uistate
ui_groups.config  = config
# …and so on for each mixin module
```

This avoids circular imports while keeping the singletons accessible everywhere.

---

## Analysis Pipeline

The core data flow from raw file to output CSV is:

```
Raw file(s)  (.abf / .ibw folder)
     │
     ▼
parse.source2dfs(path)
     │
     ├──▶  dfdata   — long-form DataFrame of raw voltage traces
     │               columns: sweep, time, voltage_raw, stim, channel, …
     │
     └──▶  dfmean   — mean trace across sweeps, with first/second derivatives
                      columns: time, voltage, prim, bis
     │
     ▼
parse.zeroSweeps(dfdata, i_stim)
     │
     ▶  dfdata with per-sweep baseline removed (mean of 20–10 samples before stim)
     │
     ▼
UIstate / DataFrameMixin caching layer
     │  (get_dft, get_dfmean, get_dffilter, get_dfbin, get_dfdiff, …)
     │
     ▼
analysis_v2.find_events(dfmean, config)
     │
     ▶  events dict  — detected fEPSP slope, amplitude, volley, latency, …
     │
     ▼
analysis_v2.build_dfoutput(dfdata, events, config)
     │
     ▶  dfoutput  — one row per sweep with all measured event values
     │
     ▼
UIsub.persistOutput / df2file
     │
     ▶  .csv  (one per recording or per group, depending on settings)
```

Key configuration that shapes the pipeline lives in `brainwash.yaml` and is loaded into the `config` dict at startup. The UI checkboxes in `uistate.checkBox` gate optional pipeline branches (e.g. `paired_stims`, `output_per_stim`, `bin`).

---

## Code Style

The project uses **Black** for formatting and **isort** for import ordering, both configured in `pyproject.toml`.

**Format a file:**

```sh
uv run black src/lib/ui.py
uv run isort src/lib/ui.py
```

**Lint:**

```sh
uv run flake8 src/lib/
```

Flake8 configuration is in `.flake8` at the repo root. The line-length limit is **150** (matching the Black config).

---

## Dependency Management

All dependencies are declared in `pyproject.toml` and locked in `uv.lock`.

| Group | Purpose | Install command |
|---|---|---|
| *(default)* | Runtime — everything needed to run the app | `uv sync` |
| `dev` | Dev tools — linting, formatting, stubs, testing, notebooks | `uv sync --group dev` |
| `build` | Packaging only — `cx-Freeze` for producing distributables | `uv sync --group build` |

**Add a runtime dependency:**

```sh
uv add <package>
```

**Add a dev-only dependency:**

```sh
uv add --group dev <package>
```

**Add a build-only dependency:**

```sh
uv add --group build <package>
```

Do **not** edit `requirements.txt` — it is kept solely for legacy tooling compatibility and explicitly documents that `pyproject.toml` is the source of truth.