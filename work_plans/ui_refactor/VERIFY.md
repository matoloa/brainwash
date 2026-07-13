# Verify after every UI refactor PR

```sh
uv run pytest src/lib/ -q
```

**PR-02+** (view state / applicability):

```sh
uv run pytest src/lib/test_view_state.py src/lib/test_applicability_characterization.py -q
```

**PR-04+** (statusbar formatters):

```sh
uv run pytest src/lib/test_statusbar_characterization.py -q
```

**PR-05+** (pipeline):

```sh
uv run pytest src/lib/test_pipeline_integration.py -q
```

**PR-13+** (plot model):

```sh
uv run pytest src/lib/test_plot_model.py -q
```

**PR-16+** (plot series):

```sh
uv run pytest src/lib/test_plot_series.py -q
```

**PR-20+** (plot stim):

```sh
uv run pytest src/lib/test_plot_stim.py -q
```

**PR-07+** (pytest-qt):

```sh
uv run pytest src/lib/test_ui_wiring.py -q
```

Optional:

```sh
uv run flake8 src/lib/brainwash_ui/ src/lib/ui_stat_test.py
```

**Do not** run distribution builds, `uv sync --group build`, or app launch unless the user asks.

## If pytest fails

1. Revert the extraction (do not "fix" golden tests without written justification).
2. Narrow the PR to fewer moved lines.
3. Check [CONTRACT.md](CONTRACT.md) for the invariant you broke.