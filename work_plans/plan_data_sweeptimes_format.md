# Plan: Lean recording data + `_sweeptimes.parquet`

**Status:** NEXT (pre-1.0.0 format work)  
**Branch context:** `1.0.0` / pre-1.0.0  
**Goal:** Stop storing per-sample absolute timestamps; put sweep clock in a small accessory file; keep disposable caches waveform-only; unify on-disk file roles for rename/purge/duplicate.

---

## Problem

Working-copy parquets under `data/{rec}.parquet` store, per sample:

| Column | Role today |
|--------|------------|
| `sweep`, `time`, `voltage_raw` | Waveform (needed) |
| `t0` | ABF: run-relative sweep start (repeated per sample). IBW: always `0` (useless) |
| `datetime` | Absolute time **per sample** — algebraically redundant; dominates size |

Measured (test ABF, ~248k samples, 1 ch):

| Artifact | Size |
|----------|------|
| Full data (with `datetime`) | ~2.2 MB |
| Data without `datetime` | ~0.44 MB |
| Filter **with** leaked `t0`/`datetime` | ~2.5 MB |
| Filter lean (`sweep, time, voltage`) | ~0.69 MB |

**ABF** (`parse_abf`): `datetime = abf.abfDateTime + t0 + time` (one run origin).  
**IBW** (`_ibw_results_to_df`): one file per sweep; `t0 ≡ 0`; inter-sweep timing only in absolute `datetime` (file creation + within-sweep time).

`zeroSweeps` currently `copy()`s full `dfdata` and merges `voltage` back without dropping clock columns, so **`_filter` accidentally retains the huge `datetime`** even though no consumer needs it.

Cache/`_filter` are juggled heavily; splitting them into their own timing sidecars is **not** worthwhile (duplicate of data clock, more rename blast radius).

---

## Product / compatibility policy

- **Pre-1.0.0:** No support for old `data/*.parquet` shapes. Source of truth is raw ABF/IBW/CSV/ATF (`df_project["path"]`). Working copies are disposable rebuilds.
- **No `data_format=1` / format-2 dual stack.** This *is* the recording on-disk layout going forward until 1.0.0 freezes it.
- **After 1.0.0:** any further schema change needs real migrators from this layout.
- **Not in scope:** published interchange formats; pickle→JSON for groups/cfg; wide/matrix time grids; filter-side meta files.

---

## Target layout

```text
data/{rec}.parquet                 # samples only
data/{rec}_sweeptimes.parquet      # one row per sweep (clock)

cache/{rec}_filter.parquet         # sweep, time, voltage[, savgol]  — no clock
cache/{rec}_bin.parquet            # same grain, no clock
cache/{rec}_mean.parquet           # unchanged role (mean waveform)
cache/{rec}_output.parquet         # unchanged role (measures)
timepoints/{rec}.parquet           # dft — unchanged role
```

### Samples: `data/{rec}.parquet`

| Column | dtype (guidance) |
|--------|------------------|
| `sweep` | int32 preferred |
| `time` | float64 (within-sweep seconds) |
| `voltage_raw` | float32 OK (already common from ABF path) |

No `t0`, no `datetime`, no `channel` once split to per-recording frames (today’s post-`source2dfs` contract).

### Accessory: `data/{rec}_sweeptimes.parquet`

Name rationale: role is **sweep clock**, not generic “meta”. Same lifetime as samples (`data/`), not disposable cache.

| Column | dtype | Meaning |
|--------|--------|---------|
| `sweep` | int32/int64 | Join key to samples |
| `t0` | float64 or NaN | Seconds from `recording_start` to this sweep’s start (**always run-relative when clock exists**) |
| `sweep_start` | datetime64[ns] or NaT | Absolute start of sweep (`time == 0`) |
| `recording_start` | datetime64[ns] or NaT | Repeated scalar OK: absolute start of first sweep / run origin |
| `source_kind` | str (optional, repeated) | `abf` \| `ibw` \| `csv` \| `atf` |

**Invariants when clock present:**

```text
recording_start = sweep_start of first sweep (after sort)
t0[s] = (sweep_start[s] - recording_start).total_seconds()
sample_datetime (if ever needed) = sweep_start[s] + time
```

**Clockless** (ATF, incomplete CSV): NaT/NaN columns still present so callers don’t branch on “file missing.”

### Filter / bin (disposable)

```text
sweep, time, voltage[, savgol]
```

No `_filter_sweeptimes`. If wall-clock ever needed while viewing filtered traces: join `sweep` → `_sweeptimes`.

---

## Builder: unified from ABF and IBW

Build **after** channel split, sweep sort, and `sweep` assignment (same stage as today’s post-`source2dfs` long DF), then drop sample clock columns.

Suggested pure API (names flexible):

```text
build_sweeptimes(df_long, *, source_kind: str) -> pd.DataFrame
```

### Fill rules

| Source | How to fill |
|--------|-------------|
| **ABF** | `t0` already run-relative; `recording_start` from origin (`abf.abfDateTime` / first `datetime - time` at t0); `sweep_start = recording_start + t0` (or first datetime per sweep at `time≈0`) |
| **IBW** | Ignore sample `t0` (always 0). `sweep_start[s] = first(datetime)` per sweep (= file creation when time starts at 0). `recording_start = min(sweep_start)`. **Derive** run-relative `t0` from that |
| **CSV** | Aggregate present `datetime` / `t0` if any; else null clock |
| **ATF** | Null clock |

Single helper — do **not** leave IBW with a different meaning of `t0` on disk.

### Write path

On create/parse (`create_recording` / `df2file`):

1. Write samples (lean).  
2. Write `_sweeptimes` beside them.  
3. Invalidate/rebuild filter/mean/output as today when data changes.

Prefer a small paired writer over scattering two `df2file` calls without a contract:

```text
write_recording_samples_and_sweeptimes(rec, samples_df, sweeptimes_df, folders)
```

Or `df2file(..., key="data")` always accompanied by `key="sweeptimes"` from one call site.

### Read path

| Need | Read |
|------|------|
| Waveform plot / zero / measure | samples only |
| `compute_sweep_hz`, `_backfill_sweep_hz` | **`_sweeptimes` only** (no full data scan) |
| Export absolute times (optional) | reconstruct from samples + sweeptimes |
| Rename / purge / duplicate | both files (see roles table) |

---

## Disk roles: single source of truth

Today the same suffix list is duplicated in:

- `ProjectMixin.rename_files_by_rec_name`
- `ParseMixin.purgeRecordingData`
- `ParseMixin.duplicate_recording`

(and partial lists in sweep-ops cache clears).

**Do first or in the same PR as `_sweeptimes`:** centralize in `brainwash_ui/recording_cache.py` (or sibling), e.g.:

```text
sweeptimes_parquet_path(data_folder, recording_name)
  → "{data}/{rec}_sweeptimes.parquet"

iter_recording_disk_files(dict_folders, recording_name) -> Iterable[Path]
  data/{rec}.parquet
  data/{rec}_sweeptimes.parquet
  timepoints/{rec}.parquet
  cache/{rec}_mean.parquet
  cache/{rec}_filter.parquet
  cache/{rec}_bin.parquet
  cache/{rec}_output.parquet
  (+ stim_intensity via existing helper)
```

Wire rename / purge / duplicate to that iterator only.

**Note:** `_clear_rec_cache` stays **cache + timepoints only** (does not delete `data/`). Sweep prune/split that rewrites data must **rebuild** samples + sweeptimes for surviving/new recs, not only rename a stale full sweeptimes table.

Optional: reject `recording_name` ending in `_sweeptimes` (parallel to the existing `_mean.parquet` name guard).

---

## Implementation phases

### Phase 0 — Path plumbing (no behavior change yet)

1. Add `sweeptimes_parquet_path` + `iter_recording_disk_files` (include current files only first).  
2. Refactor rename / purge / duplicate onto the iterator.  
3. Tests: path helpers; rename moves the full set when files exist.

**Exit:** no new files yet; less duplication.

### Phase 1 — Lean filter/bin (can ship alone or with Phase 2)

1. `zeroSweeps` returns only `["sweep", "time", "voltage"]` (explicit select; no clock leak).  
2. Ensure bin aggregation never expects `datetime`/`t0`.  
3. Tests: column set after `zeroSweeps`; optional size smoke.  
4. Drop noisy full-DF `print`s in `zeroSweeps` while touching it (hygiene).

**Exit:** new filter caches lean; old fat filters replaced on next rebuild/purge.

### Phase 2 — `build_sweeptimes` + lean samples

1. Implement `build_sweeptimes` with ABF/IBW/CSV/ATF rules (unit tests with synthetic frames + real ABF fixture).  
2. After parse / `create_recording`: write lean samples + `_sweeptimes`.  
3. Stop writing `t0`/`datetime` on samples.  
4. Point `compute_sweep_hz` / `_backfill_sweep_hz` at sweeptimes.  
5. Export path: export lean columns; reconstruct absolute times only if product still wants them.  
6. Sweep structure edits (prune, crop, split, join): rewrite samples **and** sweeptimes; invalidate caches as today.  
7. Add `_sweeptimes` to the disk-file iterator.

**Exit:** re-parse of ABF/IBW projects works end-to-end; `sweep_hz` correct; disk sizes match expectations.

### Phase 3 — Optional polish (same release if cheap)

- `sweep` as int32 on write.  
- Groups/test sets `show` as real bool (not `"True"` string) — only if already touching those writers.  
- **Skip:** float32 `time`, exotic parquet codecs, shared time-axis matrices.

### Phase 4 — Verify

- Unit: `build_sweeptimes` ABF-like vs IBW-like synthetic; null clock; `compute_sweep_hz` from accessory.  
- Integration: parse test ABFs → lean data + sweeptimes; `zeroSweeps` columns; rename moves both data files.  
- Manual: open project, parse ABF + IBW if available, plot, change filter, rename rec, split/prune if used.  
- Confirm analysis/output paths unchanged (they never needed sample `datetime`).

---

## Key call sites (checklist)

| Area | File(s) |
|------|---------|
| Parse / zero / metadata / sweep_hz | `parse.py` |
| Create recording, purge, duplicate | `ui_parse.py` |
| `df2file`, load, `_backfill_sweep_hz`, rename | `ui_project.py` |
| get_dfdata / get_dffilter / get_dfbin | `ui_data_frames.py` |
| Path helpers + tests | `brainwash_ui/recording_cache.py`, `test_recording_cache.py` |
| Sweep prune/split/cache clear | `ui_sweep_ops.py` |
| Export raw columns | `export_data.py` |
| Parse / pipeline tests | `test_parse.py`, `test_pipeline_*` |

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| IBW relative times wrong if `t0` left as 0 | Always derive `t0` in `build_sweeptimes` from absolute starts |
| Rename orphans `_sweeptimes` | Single iterator for all rec files |
| Split renames then overwrites data without new sweeptimes | Rebuild sweeptimes whenever samples rewritten |
| Callers assume `datetime` on samples | Grep: parse, backfill, export, tests — analysis core does not use it |
| In-progress projects with only working parquet | Re-parse from `path`; no migrator product pre-1.0 |
| Scope creep into UI 1.0.0 Groups issues | Keep this plan **format-only**; separate from GitHub #1–#9 UX |

---

## Explicit non-goals

- Supporting or converting pre-change data parquets as a product feature.  
- Filter/bin timing sidecars.  
- `data_format=1` dual-read.  
- Published data format compatibility.  
- Changing `groups.pkl` / `cfg.pkl` / timepoints schema (except incidental bool polish).  
- Storing one shared time grid for all sweeps (wide layout).

---

## Success criteria

1. New parses write `data/{rec}.parquet` without `datetime`/`t0` and write `data/{rec}_sweeptimes.parquet`.  
2. ABF and IBW both produce consistent run-relative `t0` + absolute `sweep_start` when source has a clock.  
3. `sweep_hz` matches pre-change behavior on ABF fixtures (within rounding).  
4. `_filter` on disk has no `datetime`/`t0`; size drop is obvious on large recs.  
5. Rename / purge / duplicate keep data + sweeptimes in sync.  
6. No analysis/regression failures on existing unit/integration tests (update fixtures as needed).

---

## Suggested PR split

| PR | Content |
|----|---------|
| **A** | Path iterator + rename/purge/duplicate refactor (+ tests) |
| **B** | Lean `zeroSweeps` / filter columns (+ tests) |
| **C** | `build_sweeptimes` + parse/create write path + sweep_hz/backfill + export + sweep-ops rewrite |

A → B → C is safest; B can parallel A if needed. C depends on A for the new file role.

---

## References (session findings)

- Generation: `parse.source2dfs` → `create_recording` → `df2file(..., key="data")`.  
- ABF clock: `parse_abf`; IBW clock: `_ibw_results_to_df`.  
- Filter leak: `zeroSweeps` merge preserves non-voltage columns.  
- Filter is disposable (`get_dffilter`); do not pair with its own meta file.  
- Related product note: after 1.0.0, forward migrators apply; this work is the floor.
