# UI refactor contract (do not break during extraction)

## Statusbar purity split (target state after PR-04)

| Function | Pure? | May mutate `uistate`? |
|----------|-------|----------------------|
| `brainwash_ui.applicability.*` | Yes | No |
| `brainwash_ui.view_state.*` | Yes | No |
| `brainwash_ui.statusbar.format_*` | Yes | No — returns `StatusbarResult` |
| `StatTestMixin._compute_statusbar_for_current_state` | Pure compute → `StatusbarResult` | No `statusbar_state` mutation |
| `StatTestMixin._get_statusbar_for_current_state` | Text-only query | Delegates to compute; no mutation |
| `StatTestMixin.update_test` | Apply path | Sets `statusbar_state`, then `set_statusbar` |
| `StatTestMixin.set_statusbar` | No (UI) | Updates widgets |

## StatusbarResult shape (after PR-04)

```python
@dataclass(frozen=True)
class StatusbarResult:
    text: str | None
    state: Literal["info", "warning"] | None
```

## Applicability invariants

| Test type | Condition | Warning string (exact) |
|-----------|-----------|--------------------------|
| t-test unpaired | < 2 groups with data | `t-test requires 2 group(s) with data` |
| t-test paired | ≠ 2 test sets | `Paired t-test requires exactly 2 test sets` |
| Friedman | < 3 test sets | `Friedman requires ≥3 test sets for repeated-measures` |
| Any | no groups | `No groups defined for <test>` |

## View-state invariants

- `visible_group_ids`: only groups with `show` in `(True, "True", "true", 1, "1")`.
- Hidden group never appears in `visible_group_ids`.
- `visible_testset_ids`: only testsets with `show` truthy.

## IO statusbar (unchanged — stats layer)

`experiment_type="io"` + empty test sets → `config["type"] == "IO regression"` (see `work_plans/History/statistics_refactor/CONTRACT.md`). UI formatters must show `IO ANCOVA` prefix when formal result present.

## Plot invariants (Phase II)

| Invariant | Detail |
|-----------|--------|
| IO scatter labels | `{label} {raw\|norm} IO scatter` / `IO trendline` |
| PP x positions | `plot_series.pp_overlay_x_map(checkBox)` is sole source for aspect → integer x |
| PPR finite values | `ppr = v2/v1`; non-finite → `nan` |
| SI boundary | `dft` stores SI (V); `ax1` display uses mV (`* 1000`) at artist boundary only |
| `amp_zero_plot` | Mean of `rec_filter` in 2 ms window `[t_stim-0.002, t_stim-0.001)` on `dfmean` |
| Stim numbering | User-visible `stim_num = i_stim + 1` |

## Drag zone invariants (Phase V)

| Invariant | Detail |
|-----------|--------|
| Session owner | Amp/slope xy and `*_move_zone` / `*_resize_zone` live on `uistate.plot` (`PlotSession`), never on `UIstate` root |
| Amp zone | `plot_drag.amp_move_zone(x, y, x_margin, y_margin)` |
| Slope zones | `plot_drag.slope_drag_state(x, y, …)` → start/end xy + move + resize zones |
| Hit test | `plot_drag.point_in_zone(x, y, zone)` |
| Artist x/y | `plot_drag.artist_xdata` / `artist_ydata` — always `np.asarray`; never index `Series` with `[-1]` |
| Output sweep drag | `plot_drag.drag_release_line_candidates` filters `SWEEP_OUTPUT_ASPECTS` on ax1/ax2 |
| Export replay | `export_image` uses `plot_drag.artist_xdata` / `artist_ydata` for line and inset artists |

## Graph refresh bus (Phase IX)

| Invariant | Detail |
|-----------|--------|
| Entry point | `GraphCoordinatorMixin.request_graph_refresh` coalesces via `refresh_bus.merge_graph_refresh_requests` |
| Scheduling | `QTimer.singleShot(0, _flush_pending_graph_refresh)` — one draw per event-loop tick |
| `reeval` merge | OR semantics: any pending request with `reeval_formal_test=True` wins |
| `graphRefresh()` | Thin delegate to `request_graph_refresh` (all ~44 call sites dedupe without edits) |

## Recording pipeline (Phase 3b)

| Invariant | Detail |
|-----------|--------|
| `build_dft` | `find_events` + `norm_output_from/to` from line edits; empty → `None` |
| `build_dfoutput_from_inputs` | `resolve_output_filter_col` → `analysis.build_dfoutput` + volley backfill |
| Parquet migrate | `norm_EPSP_*` → `norm_output_*`; spurious `index` column dropped on read |
| Caches | `dict_ts` / `dict_outputs` remain on `DataFrameMixin` |

## Testset span invariants (Phase IV)

| Invariant | Detail |
|-----------|--------|
| Span label | `testset_span_{set_ID}` |
| Alpha | `0.08` default |
| Sweep window | `[min(sweeps), max(sweeps)+1)` on ax1 and ax2 |

## Public entrypoints (unchanged)

- `compute_statistical_comparison`, `ttest_per_sweep`, `from . import statistics as stats`
- `UIsub` signal wiring — behavior preserved via thin mixin delegates