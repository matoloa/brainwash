# Step 3.1 Audit — `parse.py` vs `parse_legacy.py` Feature Gap Analysis

**Status:** Complete — no blocking gaps found. `parse_legacy.py` is safe to delete once Step 3.2 integration tests pass.

**Changes implemented** (applied directly to `parse.py` as part of this step):
- Removed jupytext `# %%` header and dead module-level globals (`dir_project_root`, `dir_source_data`, `dir_gen_data`)
- Removed dead `build_experimentcsv` function
- Fixed `parse_ibw`: changed `int(-np.log(timestep))` → `int(-np.log10(timestep))` (matches the fix already applied to `parse_ibwFolder`)
- Fixed `parse_ibw`: removed `index=timestamp_array` from `pd.DataFrame(data=voltage_raw)` (matches the fix already applied to `parse_ibwFolder`)
- General quote/whitespace normalisation throughout

---

## Audit scope

The three questions from the plan:

1. Does `ui.py → parseData → parse.source2dfs` cover the same logic as `parseProjFiles`?
2. Is `assignStimAndsweep`'s logic covered by the sweep assignment inside `source2dfs`?
3. Do `zeroSweeps` / `build_dfmean` agree between the two files?

---

## 1. `parseProjFiles` vs the current pipeline

`parseProjFiles` was a single monolithic function that did all of the following in one call:

| Step | Legacy (`parseProjFiles`) | Current |
|---|---|---|
| Route by file type (abf/ibw/csv) | ✅ inside `parseProjFiles` | ✅ `parse.source2dfs()` |
| Split by channel | ✅ `for channel in dfcopy.channel.unique()` | ✅ `source2dfs` returns `{channel: df}` |
| **Split by stim (a/b) at parse time** | ✅ `df_ch.loc[df_ch.sweep_raw % nstims == i]` | ❌ **Intentionally removed** — see §1.1 |
| Assign `sweep` column | ✅ via `sweep_raw` arithmetic | ✅ `source2dfs` uses `(time==0).cumsum().ngroup()` |
| `build_dfmean` per channel/stim | ✅ inside loop | ✅ `create_recording()` in `ui.py` |
| `zeroSweeps` per channel/stim | ✅ inside loop | ✅ `create_recording()` in `ui.py` |
| Persist data / mean / filter files | ✅ `persistdf(...)` | ✅ `create_recording()` via `df2file(...)` |
| Return metadata dict | ✅ `dict_sub` | ✅ `parse.metadata(df)` in `create_recording()` |

### 1.1 Stim splitting — intentionally redesigned, not a gap

In the legacy pipeline, stims were split at parse time using a crude alternating-sweep heuristic:
```
# legacy parseProjFiles (ABF)
df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
```
and a time-window heuristic for IBW:
```
# legacy parseProjFiles (IBW)
if stim == "a": df_ch_st = dfcopy.loc[dfcopy.time < 0.25]
if stim == "b": df_ch_st = dfcopy.loc[dfcopy.time >= 0.5]
```
(The IBW approach was already self-labelled "a stupid approach" in the snippet.)

In the current pipeline, stim detection is deferred to **`stimDetect()`** (the "Detect" button in the UI), which calls `analysis.find_events(dfmean)`. This detects stim positions from the mean waveform shape rather than by positional heuristics. The results are stored per-recording in `dft` (the stim-timepoints table).

**This is a better design.** Stims are now detected from actual signal content, not assumed from file structure. The `checkBox_force1stim` ("Single stim") checkbox and `checkBox_timepoints_per_stim` still give the user control over the output behaviour.

**Verdict: Not a gap. Intentional redesign.**

### 1.2 `sweep_raw` column

Legacy `parseProjFiles` created a `sweep_raw` column tracking the original sweep index before stim splitting. `source2dfs` does not create `sweep_raw` — it generates `sweep` directly. Since stim splitting no longer happens at parse time, `sweep_raw` has no purpose in the current pipeline.

**Verdict: Not a gap.**

### 1.3 `build_experimentcsv`

Present in both files. Not called anywhere in the active codebase (`ui.py`, `analysis_v2.py`, or any test). It reads `_metadata.txt` files from a generated data folder. This was early scaffolding, predating the `df_project` approach.

**Verdict: Dead code in both files. ✅ Removed from `parse.py`. Drop from `parse_legacy.py` when deleting that file in Step 3.3.**

---

## 2. `assignStimAndsweep`

The improvement plan mentioned `assignStimAndsweep` as a function in `parse_legacy.py`. It does not exist in the file — the plan was written against an even older revision. The sweep/stim assignment logic that existed was entirely inside the `parser()` inner function of `parseProjFiles`.

That logic is now split across two places:
- **Sweep assignment**: `source2dfs` — `df["sweep"] = (df.groupby((df["time"] == 0).cumsum()).ngroup())`
- **Stim assignment**: `stimDetect()` in `ui.py` via `analysis.find_events()`

**Verdict: No gap. Function never existed in the file being audited.**

---

## 3. `zeroSweeps` and `build_dfmean` implementations

### `zeroSweeps`

The implementations in `parse.py` and `parse_legacy.py` are **word-for-word identical** in their actual logic (duplicate detection, pivot, subtract per-row mean, stack back, merge). The only differences are whitespace and quote style (black formatting).

**Verdict: Agree. ✅**

### `build_dfmean`

The `parse.py` version is functionally identical to `parse_legacy.py`. The only difference is that `parse.py` removes the dead `if False:` block that was left in the legacy file during debugging. The actual pivot-table → rolling → baseline-subtract computation is identical.

**Verdict: Agree. ✅**

### `first_stim_index`

Identical in both files.

**Verdict: Agree. ✅**

### `persistdf`

Identical in both files.

**Verdict: Agree. ✅**

---

## 4. Improvements in `parse.py` over `parse_legacy.py`

These are improvements in the active file that the legacy file lacks. Recorded here for completeness.

| Function | Improvement |
|---|---|
| `parse_ibwFolder` | Sweep shape consistency check added: raises `ValueError` on inconsistent shapes |
| `parse_ibwFolder` | Bug fix: `pd.DataFrame(data=voltage_raw)` without `index=timestamp_array` — avoids a length-mismatch error that existed in the legacy version |
| `parse_ibwFolder` | `int(-np.log10(timestep))` instead of `int(-np.log(timestep))` — correct base-10 log for decimal-place rounding |
| `parse_ibw` | ✅ Same two fixes now applied here too: removed `index=timestamp_array`; changed `np.log` → `np.log10` |
| `parse_abf` | Uses `abf.channelList` instead of `range(abf.channelCount)` — handles non-contiguous channel indices correctly |
| `parse_abf` | Removes the `verbose` print block; no `reset_index` at the end (cleaner) |
| (new) `metadata()` | Not in legacy; extracts `nsweeps`, `sweep_duration`, `sampling_rate` from a parsed df |
| (new) `sample_abf()` | Not in legacy; lightweight metadata probe without full parse |
| (new) `parse_csv()` | Not in legacy; stub for reading Brainwash-formatted CSV files |
| (new) `source2dfs()` | Replaces `parseProjFiles` routing with a clean dispatcher; returns `{channel: df}` |
| (new) `sources2dfs()` | Batch wrapper over `source2dfs` |

---

## Summary

| Question | Answer |
|---|---|
| Does the current pipeline cover `parseProjFiles`? | Yes. Channel split, sweep assignment, mean, zeroing, persist, and metadata are all covered. Stim splitting was intentionally moved to a post-parse UI step. |
| Is `assignStimAndsweep` covered? | It never existed in `parse_legacy.py`; plan was based on an older revision. Sweep assignment is in `source2dfs`; stim assignment is in `stimDetect`. |
| Do `zeroSweeps` / `build_dfmean` agree? | Yes, implementations are identical. |

**`parse_legacy.py` contains no logic that is missing from the active codebase. It is safe to delete once the Step 3.2 integration tests pass.**