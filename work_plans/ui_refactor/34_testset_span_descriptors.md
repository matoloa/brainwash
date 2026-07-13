# PR-34: testset span descriptors

**Status**: pending | **Depends on**: PR-33

## Goal

Extract pure visibility/span specs from `visualize_test_sets` and `sample_overlay` in [ui_plot.py](../../src/lib/ui_plot.py) (~379–534 LOC).

## Scope

New [plot_testsets.py](../../src/lib/brainwash_ui/plot_testsets.py) (or extend `view_state.py` if <100 LOC):

| Pure API | Purpose |
|----------|---------|
| `TestsetSpanSpec` | `set_ID`, `ax_name`, `start`, `end`, `color`, `alpha` |
| `visible_testset_spans(dd_testset, visible_testset_ids)` | filter + sweep min/max |
| `sample_overlay_visible(...)` | which inset traces to show given `dd_shown_samples` |

`UIplot` keeps `ax.axvspan`, inset axes, canvas draw.

## CONTRACT

Extend [CONTRACT.md](CONTRACT.md): testset span zorder, alpha default, label pattern `testset_span_{set_ID}`.

## Tests

- [test_plot_testsets.py](../../src/lib/test_plot_testsets.py) using [test_statistics_fixtures.py](../../src/lib/test_statistics_fixtures.py) `make_dd_testsets`

## Verify

```sh
uv run pytest src/lib/test_plot_testsets.py src/lib/ -q
```