# Output Graph X-Axis Refactor — Implementation Plan

_Created: 2026-03-08_

## Background

The output graph x-axis mode is currently driven by a boolean checkbox
(`checkBox["output_per_stim"]`), with the mode resolved ad hoc at every
call site via an inline ternary. This makes it impossible to add new x-axis
options (time, timestamp) without patching every site again. In parallel,
the bin cache has a correctness bug: it encodes no bin-size information, so
stale files are silently returned when `bin_size` changes.

This plan fixes the bin cache, unifies the analysis layer, completes the
stim mode, and then replaces the checkbox with a proper radio-button mode
selector — in that order, so each phase has stable ground beneath it.

---

## Intended final state

- x-axis mode is a string stored in `uistate` (`"sweep"`, `"stim"`,
  `"time"`, `"timestamp"`), set by a radio-button group in the UI.
- `"time"` and `"timestamp"` are present but disabled until implemented.
- `bin_size` lives in `df_project` per recording; `NaN` means binning off.
- Each (recording × mode × bin_size) combination has its own cache file.
- A single `measure_waveform` core function handles all measurement work;
  mode-specific wrappers handle iteration and cache routing.
- Stim mode is fully interactive (drag, mouseover, release).

---

## Phase 1 — Schema & migration

**1.1** Add `"bin_size"` column to `df_projectTemplate()` in `ui_project.py`.
- Type: float (to hold `NaN`). Default: `NaN` (binning off).
- Comment: `# float: bin size used for output; NaN means binning disabled`.
- The existing backfill loop in `load_df_project` handles all existing
  project files automatically on next load — no migration script needed.

**1.2** Cosmetic: verify comment style on new column is consistent with
neighbours in `df_projectTemplate`.

---

## Phase 2 — `get_dfbin` hardening

**2.1** Change `get_dfbin` to read `bin_size` from `p_row["bin_size"]`
instead of `uistate.lineEdit["bin_size"]`.
- Add a guard at entry: if `pd.isna(p_row["bin_size"])`, raise `ValueError`
  with a clear message. Callers must not reach `get_dfbin` when binning is
  off.

**2.2** Change the cache filename to `{rec}_bin{N}.parquet` where
`N = int(p_row["bin_size"])`.
- Update the `df2file` call to use the new key.
- Update the in-memory cache dict lookup (`dict_bins`) to use the same key,
  e.g. `f"{rec}_bin{N}"` as the dict key rather than bare `rec`.

**2.3** Update `purgeRecordingData` to glob and delete all
`{rec}_bin*.parquet` files for a recording, since there may now be more
than one on disk.

---

## Phase 3 — Checkbox & widget wiring

**3.1** Rewrite `checkBox_bin_changed`:
- On check: write `uistate.lineEdit["bin_size"]` into
  `df_project["bin_size"]` for all selected recordings (or all recordings
  if none selected), then call `recalculate`.
- On uncheck: write `NaN` into `df_project["bin_size"]` for the same
  scope, then call `recalculate`.

**3.2** Rewrite `trigger_set_bin_size_all`:
- Write the current `lineEdit` value into `df_project["bin_size"]` for all
  recordings where `bin_size` is not already `NaN` (only affect recordings
  where binning is already active).
- If no recordings have binning active, enable all (matches current intent).
- Call `recalculate`.

**3.3** Rewrite `editBinSize`:
- Update `uistate.lineEdit["bin_size"]` as before.
- Also update `df_project["bin_size"]` for any recording where it is not
  `NaN` (i.e. binning is currently active for that recording).
- Call `recalculate`.

**3.4** Update `get_dfoutput`:
- Replace `uistate.checkBox["bin"]` branch condition with
  `pd.notna(p_row["bin_size"])`.
- Remove all `uistate.checkBox["bin"]` reads from the data layer.

**3.5** Update `recalculate`:
- Derive `binSweeps` per row from `p_row["bin_size"]` rather than the
  global checkbox.

**3.6** `uistate.checkBox["bin"]` is kept as a pure UI display state
(drives the checkbox visual) but is no longer authoritative for data
routing. Document this with a comment.

---

## Phase 4 — Analysis layer unification

All changes in `analysis_v2.py`.

**4.1** Extract `measure_waveform(df_snippet, dict_t, filter) -> dict`.
- Input: single-waveform dataframe with columns `time` and `<filter>`;
  `dict_t` with timepoint keys.
- Output: plain dict of measured values (EPSP_amp, EPSP_slope,
  volley_amp, volley_slope, and their _norm variants).
- No sweep or stim awareness — pure signal measurement.
- Slope path: use scalar `measureslope` (not `measureslope_vec`) since the
  snippet is a single waveform.

**4.2** Rewrite `build_dfoutput` as a sweep-mode wrapper:
- Iterate `df.groupby("sweep")`.
- For each group, call `measure_waveform`.
- Assemble result dataframe with columns `stim`, `sweep`, measured values.
- Keep `measureslope_vec` fast path for the slope calculation by passing
  the full df; restructure surrounding logic accordingly.

**4.3** Write `build_dfstimoutput` in `analysis_v2.py` as a stim-mode
wrapper:
- Input: `dfmean`, `dft`, `filter`.
- Iterate `dft` rows; for each stim slice `dfmean` around `t_stim` window.
- Call `measure_waveform` for each slice.
- Return dataframe with columns `stim` + measured values (one row per stim).
- Replaces the diverged copy in `analysis_v1.py`.

**4.4** Write `build_dfbinstimoutput` as the binned-train wrapper:
- Input: `dfbin`, `dft`, `filter`.
- Outer loop: `dfbin.groupby("sweep")` (each group is one bin's waveform).
- Inner loop: iterate `dft` rows (stims).
- For each (bin, stim) pair, slice the bin waveform around `t_stim` and
  call `measure_waveform`.
- Return dataframe with columns `bin`, `stim` + measured values
  (one row per bin × stim).

**4.5** Mark `build_dfstimoutput` in `analysis_v1.py` as deprecated with a
comment pointing to v2. Do not delete yet.

---

## Phase 5 — Cache key separation

**5.1** Add new recognised keys to `df2file` / cache path builder:
- `"output_stim"` → `{rec}_output_stim.parquet`
- `"output_bin{N}"` → `{rec}_output_bin{N}.parquet`
- `"output_stim_bin{N}"` → `{rec}_output_stim_bin{N}.parquet`

**5.2** Update `get_dfoutput` to select the correct cache path based on
`p_row["bin_size"]` and x-axis mode:

| Mode        | bin_size | Cache file                      |
|-------------|----------|---------------------------------|
| sweep       | NaN      | `{rec}_output.parquet`          |
| sweep       | N        | `{rec}_output_bin{N}.parquet`   |
| stim        | NaN      | `{rec}_output_stim.parquet`     |
| stim        | N        | `{rec}_output_stim_bin{N}.parquet` |

**5.3** Update `resetCacheDicts` and `purgeRecordingData` to cover all new
cache keys and file patterns.

---

## Phase 6 — x-axis mode as a proper state

**6.1** Add `x_axis` as a `@property` on `UIstate`:
- Returns a string: `"sweep"` or `"stim"` (initially).
- Derived from `checkBox["output_per_stim"]` for now — same semantics,
  but centralised. Will be rerouted in Phase 8.

**6.2** Add `x_axis_xlim(prow) -> tuple` method on `UIstate`:
- Returns `(0, int(prow["stims"]))` in stim mode.
- Returns `(0, prow["sweeps"])` in sweep mode.

**6.3** Replace all inline ternaries of the form
`"stim" if uistate.checkBox["output_per_stim"] else "sweep"` with
`uistate.x_axis`. Affected sites:
- `ui_plot.py`: `graphRefresh`, `addRow`, `update`
- `ui.py`: `eventDragUpdate`, `outputMouseover`

**6.4** Fix `zoomAuto`: replace hardcoded `(0, prow["sweeps"])` with
`uistate.x_axis_xlim(prow)`.

---

## Phase 7 — Stim mode completion

**7.1** Complete `outputMouseover` for stim mode:
- Remove the early `return` stub.
- Implement ghost waveform using `dfmean` sliced around the hovered stim
  (same window logic as `build_dfstimoutput`).

**7.2** Complete `eventDragUpdate` for stim mode:
- Wire up the commented-out `build_dfstimoutput` call, now that Phase 4
  provides a working v2 implementation.

**7.3** Complete `eventDragReleased` for stim mode:
- Implement the `if False:` branch for `build_dfstimoutput`.

**7.4** Smoke-test full stim-mode interaction cycle:
- Select a train recording → switch to stim mode → drag timepoints →
  verify output graph updates correctly.

---

## Phase 8 — Radio buttons (x-axis mode UI)

Only after Phases 1–7 are solid.

**8.1** In Qt Designer (`bwmain.ui` / `ui_designer.py`), replace
`checkBox_output_per_stim` with a `QButtonGroup` of `QRadioButton`s:
- `sweep` (default, always enabled)
- `stim` (enabled when stims > 1)
- `time` (present, disabled — future)
- `timestamp` (present, disabled — future)

**8.2** Connect the button group to a single handler
`x_axis_mode_changed(mode: str)`:
- Write `mode` to `uistate` (new field, e.g. `uistate.x_axis_mode`).
- Invalidate output cache for affected recordings (set `reset=True` path).
- Call `recalculate`.

**8.3** Update `UIstate.x_axis` property to read from `uistate.x_axis_mode`
instead of `checkBox["output_per_stim"]`.

**8.4** Remove `checkBox["output_per_stim"]` from `uistate.checkBox`. It
is fully superseded by `uistate.x_axis_mode`.

---

## Open questions

- Should `"time"` mode compute x as `sweep_index × sweep_duration`, or
  account for inter-sweep gaps? (Gaps require timestamp data from the
  parser.)
- Should `"timestamp"` require parser support first, or can it be stubbed
  in the UI and enabled once parse provides the data?
- For the binned-train view, should the x-axis label say "bin" or show the
  sweep range (e.g. "1–10", "11–20")? The latter requires a tick formatter.
- `build_dfbinstimoutput` output has a composite key (bin × stim). Should
  the output graph show one line per stim (x = bin) or one line per bin
  (x = stim)? Decided: bin number on x-axis, separate lines per stim —
  matching how sweep mode shows one line per stim today.