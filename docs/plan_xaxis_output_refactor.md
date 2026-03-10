# Output Graph X-Axis Refactor — Implementation Plan

_Created: 2026-03-08_

## Background

The output graph x-axis mode is currently handled ad hoc at every call site
via an inline ternary on `checkBox["output_per_stim"]`. This makes it
impossible to add new x-axis options (time, sweep_hz-based) without patching
every site again. In parallel, the bin cache has a correctness bug: the
in-memory dict and the disk file are never invalidated when `bin_size`
changes, so stale results are silently returned for the remainder of the
session and across sessions.

This plan adds the Qt Designer UI changes first, then fixes the bin cache,
unifies the analysis layer, completes stim mode, and finally adds proper
x-axis mode state — in that order, so each phase has stable ground beneath
it.

### Important distinction

**`checkBox_output_per_stim`** and **x-axis mode** are orthogonal concerns:

- `output_per_stim` controls *how output values are computed*: checked means
  measure each stim position against the mean waveform
  (`build_dfstimoutput`); unchecked means measure each sweep at the stim
  timepoints (`build_dfoutput`). This is a data pipeline choice. It belongs
  in `frameToolStim` and is not replaced by the x-axis radio buttons.

- **x-axis mode** controls *how the output graph's x-axis is labelled and
  scaled*: sweep index, seconds (via `sweep_hz`), or stim number in train.
  This is a display/rendering choice applied to whatever output data exists.
  It lives in the new `frameToolXscale`.

These must not be conflated. A recording with `output_per_stim` checked can
still be plotted with any x-axis mode, and vice versa.

---

## Intended final state

- `frameToolScaling` is split into `frameToolYscale` (existing y-axis
  normalisation controls) and `frameToolXscale` (new x-axis mode controls).
- x-axis mode is a string stored in `uistate.x_axis_mode`
  (`"sweep"`, `"time"`, `"stim"`), set by a `QButtonGroup` of radio buttons
  in `frameToolXscale`. `"timestamp"` is reserved but disabled.
- `"time"` mode computes x as `sweep_index / sweep_hz`, where `sweep_hz` is
  a per-recording value in `df_project` (user-adjustable; default extracted
  from inter-sweep interval at parse time; falls back to 1 Hz with a status
  warning `"default Hz"`).
- `bin_size` lives in `df_project` per recording; `NaN` means binning off.
- Each (recording × output_mode × bin_size) combination has its own cache
  file.
- A single `measure_waveform` core function handles all measurement work;
  mode-specific wrappers handle iteration and cache routing.
- Stim mode (`output_per_stim`) is fully interactive (drag, mouseover,
  release).

---

## Phase 0 — Qt Designer: new frames and widgets

All UI structure changes happen here, before any logic is touched. This
phase produces new widget names that later phases wire up.

> **Status: complete.** All steps below have been implemented in
> `ui_designer.py` and `bwmain.py`. This section is retained for reference
> and to document the actual widget names used (which differ slightly from
> the original drafts).

**0.1** ✅ `frameToolScaling` renamed to `frameToolYscale` throughout
`ui_designer.py`. `uistate.viewTools` key updated to `"frameToolYscale"`.

**0.2** ✅ `frameToolXscale` added to `verticalLayoutTools` between
`frameToolBin` and `frameToolYscale`. Added to `uistate.viewTools` as
`"frameToolXscale": ["X axis", True]`.

**0.3** ✅ `buttonGroup_x_axis` added inside `frameToolXscale` with five
`QRadioButton`s. Note: actual widget names use the `_xscale_` infix, not
`_x_` as originally drafted. There is also a fifth button not in the
original draft. The canonical names are:
- `radioButton_xscale_sweep` — "Sweep" (default, always enabled)
- `radioButton_xscale_time` — "Time" (enabled when `sweep_hz` is set)
- `radioButton_xscale_stim` — "Stim" (enabled when `stims > 1`)
- `radioButton_xscale_bin` — "Bin" (enabled when binning is active)
- `radioButton_xscale_timestamp` — "Timestamp" (always disabled — future)

**0.4** ~~Add `lineEdit_sweep_hz`, `label_sweep_hz`, and
`pushButton_sweep_hz_set_all` inside `frameToolXscale`.~~ **Dropped.**
`sweep_hz` is a rare per-recording calibration value, not a display
preference. It will be set via an Edit menu dialog (see Phase 4) rather
than a permanent widget in the toolbar panel.

**0.5** ✅ `checkBox_output_per_stim` remains in `frameToolStim`.

**0.6** ✅ `retranslateUi` updated for all new widget labels.

**0.7** ✅ Smoke-tested: frames visible and toggleable from the View menu.

---

## Phase 1 — Schema & migration

**1.1** Add `"bin_size"` column to `df_projectTemplate()` in
`ui_project.py`.
- Type: float (to hold `NaN`). Default: `NaN` (binning off).
- Comment: `# float: bin size in sweeps for output; NaN means binning
  disabled`.
- The existing backfill loop in `load_df_project` handles all existing
  project files automatically on next load — no migration script needed.

**1.2** Add `"sweep_hz"` column to `df_projectTemplate()`, placed after
`"sweep_duration"` and before `"sampling_rate"`.
- Type: float. Default: `NaN`.
- Comment: `# float: assumed inter-sweep rate in Hz for time-axis display;
  NaN triggers 1 Hz fallback with status warning`.

**1.3** Update `parse.metadata()` to extract a default `sweep_hz` estimate:
- Compute median inter-sweep interval from `t0` differences across all
  sweeps.
- `sweep_hz = 1 / median_interval`, rounded to 3 significant figures.
- If fewer than 2 sweeps exist, return `None`.
- Return value added to the `dict_meta` output.

**1.4** Update `create_row` in `create_recording` to write
`dict_meta["sweep_hz"]` (or `NaN` if absent) into the new column.

**1.5** If `sweep_hz` is `NaN` after parse, write `"default Hz"` into the
`status` field as a pipe-delimited flag (e.g. `"Read|default Hz"`). The
status field is treated as a `|`-delimited set of flags; checked with
`str.contains` rather than equality.

---

## Phase 2 — `get_dfbin` hardening

The cache filename stays `{rec}_bin.parquet` and the `dict_bins` key stays
bare `rec`. There is never more than one valid bin per recording at a time,
so encoding bin size in the filename buys nothing except disk clutter and
more complex purge logic. The correctness bug is fixed by proper invalidation
at the point of change instead.

**2.1** Change `get_dfbin` to read `bin_size` from `p_row["bin_size"]`
instead of `uistate.lineEdit["bin_size"]`.
- Add a guard at entry: if `pd.isna(p_row["bin_size"])`, raise `ValueError`
  with a clear message. Callers must not reach `get_dfbin` when binning is
  off.

**2.2** Add cache invalidation to `editBinSize`:
- After updating `uistate.lineEdit["bin_size"]`, compare the new value
  against the current `df_project["bin_size"]` for each recording where
  binning is active (i.e. `bin_size` is not `NaN`).
- For any recording whose stored `bin_size` differs from the new value,
  evict `dict_bins[rec]` and `dict_outputs[rec]` from the in-memory caches,
  and delete `{rec}_bin.parquet` from disk.
- This ensures `get_dfbin` always recomputes with the current bin size; no
  stale result can be returned from dict or disk.

**2.3** `purgeRecordingData` and the hardcoded suffix lists in
`reanalyze_recordings` and `rename_files_by_rec_name` require no changes —
they already reference `"_bin.parquet"` as a single fixed suffix, which
remains correct.

---

## Phase 3 — Bin widget wiring

`lineEdit_bin_size` is the single authoritative control for binning.
Values `0` or `1` mean binning off (stored as `NaN` in `df_project`);
values `≥2` mean binning on. `checkBox_bin` is removed entirely — it was
redundant once `df_project["bin_size"]` is the source of truth.

**3.0** Remove `checkBox_bin` and `label_bins` from `frameToolBin` in
`ui_designer.py` (and `bwmain.py`). Update `retranslateUi` accordingly.
Optionally update `label_bin_size` text to `"Bin size (0 = off)"` to make
the convention self-documenting.

**3.1** Rewrite `editBinSize`:
- If the field is empty, do nothing and return (mixed-selection sentinel —
  see 3.5).
- Parse input → `int`, clamp to `≥0`. Values `0` or `1` → derive `NaN`;
  values `≥2` → use the int as-is.
- Normalise the display: show `"0"` when the derived value is `NaN`, else
  show the int.
- Write the derived value into `df_project["bin_size"]` for all selected
  recordings (or all recordings if none selected).
- Perform cache invalidation as specified in Phase 2.2 for any recording
  whose stored `bin_size` changed.
- Call `recalculate`.

**3.2** Rewrite `trigger_set_bin_size_all`:
- If the field is empty, do nothing and return.
- Parse and derive the value the same way as `editBinSize`.
- Write the derived value into `df_project["bin_size"]` for **all**
  recordings, regardless of their current state.
- Perform cache invalidation as in Phase 2.2.
- Call `recalculate`.

**3.3** Update `get_dfoutput`:
- Replace `uistate.checkBox["bin"]` branch condition with
  `pd.notna(p_row["bin_size"])`.
- Remove all `uistate.checkBox["bin"]` reads from the data layer.

**3.4** Update `recalculate`:
- Derive `binSweeps` per row from `pd.notna(p_row["bin_size"])` rather
  than the global checkbox.
- Remove the `uistate.checkBox["bin"]` and `uistate.lineEdit["bin_size"]`
  reads at the top of `recalculate`.

**3.5** Populate `lineEdit_bin_size` in `tableProjSelectionChanged`:
- Single recording selected: show `"0"` if `bin_size` is `NaN`, else show
  the stored int.
- Multiple recordings selected with identical `bin_size` values: show the
  same representation as above.
- Multiple recordings selected with differing `bin_size` values: show `""`
  (blank). `editBinSize` treats blank as a no-op, so the field is inert
  until the user types a new value.

**3.6** Remove `checkBox_bin_changed` entirely. Remove `"bin"` from
`uistate.checkBox` and from the `viewSettingsChanged` dispatcher. Remove
`"bin"` from `uistate.viewTools` if present. Remove the
`connectUIstate` wiring for `checkBox_bin`.

---

## Phase 4 — `sweep_hz` Edit menu action

`sweep_hz` is a rare per-recording calibration value. Rather than a
permanent widget in `frameToolXscale`, it is exposed through the Edit menu
using the same `QInputDialog` pattern as "Set gain".

**4.1** Add `"Set sweep Hz"` to `menuEdit` in `ui_menus.py`, placed
alongside `actionSetGain`:
- Action text: `"Set sweep Hz"`
- Shortcut: none (rare operation).
- Connect to a new handler `triggerSetSweepHz`.

**4.2** Implement `triggerSetSweepHz`:
- Open a `QInputDialog.getDouble` (or `.getText`) pre-populated with the
  current `p_row["sweep_hz"]` (or `1.0` if `NaN`) for the first selected
  recording.
- Validate input: must be a positive float.
- On confirm, write the value into `df_project["sweep_hz"]` for **all
  selected recordings** (multi-selection applies to all, replacing the
  former `pushButton_sweep_hz_set_all` concept).
- Remove the `"default Hz"` pipe-flag from `status` for each updated row.
- Save config. Do not trigger recalculate — this is display-only.

**4.3** Surface the `"default Hz"` warning through the existing `status`
column in `tableProject`. No additional visual indicator is needed in the
toolbar panel; the status column is already the established place for
per-recording warnings of this kind.

**4.4** Enable `radioButton_xscale_time` only when `sweep_hz` is not `NaN`
for the selected recording (handled in Phase 9 radio button wiring).
A tooltip on `radioButton_xscale_time` may show the current Hz value
(e.g. `"Time (s) — 10.0 Hz"`) to give at-a-glance readability without
permanent UI real estate.

---

## Phase 5 — Analysis layer unification

All changes in `analysis_v2.py`.

**5.1** Extract `measure_waveform(df_snippet, dict_t, filter) -> dict`.
- Input: single-waveform dataframe with columns `time` and `<filter>`;
  `dict_t` with timepoint keys.
- Output: plain dict of measured values (`EPSP_amp`, `EPSP_slope`,
  `volley_amp`, `volley_slope`, and their `_norm` variants).
- No sweep or stim awareness — pure signal measurement.
- Slope path: use scalar `measureslope` (not `measureslope_vec`) since the
  snippet is a single waveform.

**5.2** Rewrite `build_dfoutput` as a sweep-mode wrapper:
- Iterate `df.groupby("sweep")`.
- For each group, call `measure_waveform`.
- Assemble result dataframe with columns `stim`, `sweep`, measured values.
- Keep `measureslope_vec` fast path for slope by passing the full df;
  restructure surrounding logic accordingly.

**5.3** Write `build_dfstimoutput` in `analysis_v2.py` as a stim-mode
wrapper:
- Input: `dfmean`, `dft`, `filter`.
- Iterate `dft` rows; for each stim slice `dfmean` around `t_stim` window.
- Call `measure_waveform` for each slice.
- Return dataframe with columns `stim` + measured values (one row per
  stim).
- Replaces the diverged copy in `analysis_v1.py`.

**5.4** Write `build_dfbinstimoutput` as the binned-train wrapper:
- Input: `dfbin`, `dft`, `filter`.
- Outer loop: `dfbin.groupby("sweep")` (each group is one bin's waveform).
- Inner loop: iterate `dft` rows (stims).
- For each (bin, stim) pair, slice the bin waveform around `t_stim` and
  call `measure_waveform`.
- Return dataframe with columns `bin`, `stim` + measured values
  (one row per bin × stim).

**5.5** Mark `build_dfstimoutput` in `analysis_v1.py` as deprecated with a
comment pointing to v2. Do not delete yet.

---

## Phase 6 — Cache key separation

`output_per_stim` is a row-level distinction within the output dataframe,
not a file-level one. When `output_per_stim` is active, `get_dfoutput`
produces additional rows (one per stim) and a `stim` counter column in the
same dataframe — it does not write a separate file. The cache therefore
splits on bin state only:

| bin_size | key            | Cache file                 |
|----------|----------------|----------------------------|
| NaN      | `"output"`     | `{rec}_output.parquet`     |
| set      | `"output_bin"` | `{rec}_output_bin.parquet` |

**6.1** Add `"output_bin"` as a recognised key in `df2file` (no other new
keys are needed). It follows the existing literal-suffix convention:
`{rec}_output_bin.parquet`.

**6.2** Update `get_dfoutput` to select the cache path based on
`p_row["bin_size"]`: use `key="output_bin"` when bin_size is not NaN,
`key="output"` otherwise. Both paths apply regardless of
`output_per_stim`.

**6.3** Update `resetCacheDicts` and `purgeRecordingData` to include
`"_output_bin.parquet"` alongside `"_output.parquet"`.

---

## Phase 7 — x-axis mode as a proper state

**7.1** Add `x_axis_mode` string field to `uistate` (persisted in config),
default `"sweep"`. Valid values: `"sweep"`, `"time"`, `"stim"`.

**7.2** Add `x_axis` as a `@property` on `UIstate` returning
`uistate.x_axis_mode`. This is the single call site for all plot-layer
x-axis decisions.

**7.3** Add `x_axis_xlabel(prow) -> str` method returning a human-readable
axis label:
- `"sweep"` → `"Sweep"`
- `"time"` → `"Time (s)"`
- `"stim"` → `"Stim"`

**7.4** Add `x_axis_xlim(prow) -> tuple` method:
- `"sweep"` → `(0, prow["sweeps"])`
- `"time"` → `(0, prow["sweeps"] / prow["sweep_hz"])`, falling back to
  `prow["sweeps"]` if `sweep_hz` is `NaN`.
- `"stim"` → `(0, int(prow["stims"]))`

**7.5** Add `x_axis_values(dfoutput, prow) -> Series` method returning the
x-values to plot for a given recording:
- `"sweep"` → `dfoutput["sweep"]`
- `"time"` → `dfoutput["sweep"] / prow["sweep_hz"]`
- `"stim"` → `dfoutput["stim"]`

**7.6** Replace all inline ternaries of the form
`"stim" if uistate.checkBox["output_per_stim"] else "sweep"` with
`uistate.x_axis`. Affected sites:
- `ui_plot.py`: `graphRefresh`, `addRow`, `update`
- `ui.py`: `eventDragUpdate`, `outputMouseover`

**7.7** Fix `zoomAuto`: replace hardcoded `(0, prow["sweeps"])` with
`uistate.x_axis_xlim(prow)`.

**7.8** Fix `graphRefresh` x-axis label: replace hardcoded string with
`uistate.x_axis_xlabel(prow)`.

**7.9** Fix `graphRefresh` tick locator: the `FixedLocator` block currently
gated on `checkBox["output_per_stim"]` should instead be gated on
`uistate.x_axis == "stim"`.

---

## Phase 8 — Stim mode completion

**8.1** Complete `outputMouseover` for stim mode:
- Remove the early `return` stub.
- Implement ghost waveform using `dfmean` sliced around the hovered stim
  (same window logic as `build_dfstimoutput`).

**8.2** Complete `eventDragUpdate` for stim mode:
- Wire up the commented-out `build_dfstimoutput` call, now that Phase 5
  provides a working v2 implementation.

**8.3** Complete `eventDragReleased` for stim mode:
- Implement the `if False:` branch for `build_dfstimoutput`.

**8.4** Smoke-test full stim-mode interaction cycle:
- Select a train recording → enable `output_per_stim` → drag timepoints →
  verify output graph updates correctly.

---

## Phase 9 — Radio button wiring (x-axis mode UI)

Only after Phases 1–8 are solid.

**9.1** Connect `buttonGroup_x_axis` (added in Phase 0) to a single handler
`x_axis_mode_changed(mode: str)`:
- Write `mode` into `uistate.x_axis_mode`.
- Save config.
- Call `graphRefresh` — no recalculate needed, x-axis mode is display-only.

**9.2** Enable/disable radio buttons based on recording state:
- `radioButton_x_stim`: enabled only when selected recording has
  `stims > 1`.
- `radioButton_x_time`: enabled only when `sweep_hz` is not `NaN`.
- `radioButton_x_timestamp`: always disabled (future).

**9.3** Populate the button group selection from `uistate.x_axis_mode` when
a recording is selected, in `tableProjSelectionChanged`.

**9.4** Note: `checkBox_output_per_stim` is unaffected by this phase. It
remains in `frameToolStim` as a data pipeline control, independent of the
x-axis display mode.

---

## Open questions

- Should `"stim"` x-axis mode be available when `output_per_stim` is
  unchecked? Semantically it could mean "show sweep-mode output but label
  x by stim number" — which is probably not useful. Consider disabling
  `radioButton_x_stim` when `output_per_stim` is unchecked, or coupling
  them so selecting stim x-axis implies enabling `output_per_stim`.
- `build_dfbinstimoutput` output has a composite key (bin × stim). The
  output graph shows one line per stim (x = bin), matching how sweep mode
  shows one line per stim today. Confirm this is the intended layout.
- For the binned-train view, should x-axis tick labels show bin number or
  sweep range (e.g. "1–10", "11–20")? The latter requires a tick formatter.
- `"timestamp"` x-axis: requires `t0` per sweep from `dffilter`. Deferred
  until parser reliably provides this for all file types.
- Status field delimiter: `|` is proposed for flag separation. Confirm no
  existing status value contains `|` before committing.