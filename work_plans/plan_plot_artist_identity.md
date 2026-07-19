# Plan: Plot artist identity (storage key ≠ display label)

**Branch:** `1.0.0`  
**Unblocks:** [#5](https://github.com/matoloa/brainwash/issues/5) blind/unblind (display-only) without ad-hoc legend hacks  
**Related smell:** stringly-typed keys in `dict_rec_labels` / `dict_group_labels` — human `recording_name` prefixes double as primary keys and legend text  

---

## Problem

Artist registries are `dict[str, meta + line]`. Keys look like:

```text
"slice07 - stim 1 EPSP amp"
"mean slice07 - stim 1 marker"
"slice07 EPSP amp"
```

Those strings are used as:

1. **Dict keys** (`dict_rec_labels[…]`)
2. **Matplotlib `label=` / legend text** (recs: keys verbatim in `output_axis_legend_map`)
3. **Reconstructed lookup targets** after drag (`drag_update_label_core(rec_name, …)`)

Metadata already carries stable identity (`rec_ID`, `group_ID`, `aspect`, `stim`, `axis`, `variant`, `x_mode`, `level`) — visibility (`update_show`) is largely metadata-first. Drag/update/refresh still rebuild name strings.

**Consequences:**

- Rename rec / change filter → key rebuild paths desync  
- Blind display cannot change legend text without either leaking real names in keys or rewriting every key  
- `startswith(rec_name)` fails for `name (filter)` labels  

**Decision:** Fix identity **before** shipping #5 blinding. Do not paper over with legend-only stem replace as the long-term design (acceptable only as a temporary hack if forced).

---

## Goal

| Concern | Source of truth |
|--------|------------------|
| Which artist | Stable **storage key** or metadata query (`rec_ID` + role + …) |
| What user sees | **`display_label`** (from real name today; later blind alias) |
| Disk / cache / `df_project` | Unchanged `recording_name` / `path` |

Blinding (#5) then becomes: change `display_label` only → table DisplayRole + legend map. No key churn.

---

## Target model

### 1. Role enum (explicit, not suffix parsing)

Add a small vocabulary (module: `brainwash_ui/plot_identity.py` or extend `plot_model.py`):

```text
role ∈ {
  mean_trace, event_trace, stim_marker, stim_selection,
  aspect_marker, amp_width, amp_x, amp_y, amp_zero,
  series, series_norm, series_mean_hline, shade,
  io_scatter, io_trend, ppr, axe_mean_overlay,
  ref_hline, …
}
```

Store `role` on every `rec_label_entry` / group entry (extend factories).

### 2. Storage key (stable, non-display)

**Preferred (Option A — opaque composite):**

```text
rec|{rec_ID}|{axis}|{role}|s{stim or -}|{aspect or -}|{variant}|{x_mode}
grp|{group_ID}|{axis}|{role}|{aspect}|{variant}|{level}|{x_mode}[|u{unit_id}]
sys|{name}    # Events y zero, 100% markers, axe mean selected sweeps
```

Rules:

- No `recording_name` / `group_name` in storage key  
- Filter channel is **not** in the key (it is display-only; one active filter per rec at a time)  
- Deterministic string for dict uniqueness; optional tuple form later  

**Rejected for target:** keeping name in the key (“minimal `id::suffix`”) — still couples rename/blind.

### 3. Display label (presentation)

On each entry (or computed at legend time):

```python
display_label: str  # e.g. "slice07 - stim 1 EPSP amp" or "Rec 3 - stim 1 EPSP amp"
```

- Set when creating artists (from current `recording_plot_label` / group name helpers)  
- Matplotlib `label=` uses **display_label**, not storage key  
- `output_axis_legend_map` uses **display_label** (or recomputes from `rec_ID` + display_name fn)  

### 4. Lookup API (no string rebuild from names)

```python
def find_rec_entries(
    store: dict,
    *,
    rec_ID,
    stim=None,
    aspect=None,
    role=None,
    axis=None,
    variant=None,
) -> list[tuple[str, dict]]:
    """Filter by metadata on values; O(n) fine for current sizes."""

def require_one(...) -> dict:  # raises / logs if 0 or >1
```

Secondary index later if needed:

```python
index[(rec_ID, stim, aspect, role)] -> storage_key
```

Migrate **all** drag/update paths to this API:

| Old | New |
|-----|-----|
| `dict_rec_labels[f"{core} marker"]` | `require_one(…, role="aspect_marker")` |
| `key.startswith(rec_name)` | filter `rec_ID` |
| `label.split(" - stim ")[0]` | `entry["rec_ID"]` + project lookup for name |

### 5. Spec builders stay pure

`build_stim_event_plot_specs`, PP/IO builders produce:

```python
@dataclass
class ArtistSpec:
    storage_key: str
    display_label: str
    # geometry + color + aspect/stim/…
```

`ui_plot.plot_*` registers under `storage_key`, sets artist label to `display_label`.

---

## Non-goals

- Blinding UI itself (toggle, aliases) — **follow-up #5** once this lands  
- Changing parquet / `recording_name` on disk  
- Redesigning group digit UX  
- Full typed registry object (can stay `dict` + helpers for v1)  

---

## PR sequence (small, testable)

Follow “one rename family per PR” spirit; each PR green on pytest.

### PR-1 — Inventory + helpers (no behavior change) — **done**

- `brainwash_ui/plot_identity.py`: roles, `storage_key_*`, `find_rec_entries` / `require_one`  
- Unit tests in `test_plot_identity.py`  

### PR-2 — Metadata completeness — **done**

- `rec_label_entry` / group factories take `role` + `display_label`  
- All `ui_plot.plot_*` registrations set role (explicit or `infer_rec_role`) and `display_label`  
- Storage keys still legacy name strings until PR-3  

### PR-3 — Rec storage keys + display_label (create path) — **done**

- `ui_plot.plot_*` register under `storage_key_rec(...)`; `display_label` keeps human strings  
- `output_axis_legend_map` prefers `display_label` over storage key  
- Lookups that still rebuild display strings resolve via `find_entry_by_display_label`  

### PR-4 — Drag / update lookups — **partial (with PR-3)**

- `updateAmpMarker` / `updateLine` / `updateOutLine*` / `updateStimLines` / drag start / mean hover / mouseover zones use display_label or metadata  
- Remaining: drag plans still emit display strings (OK via display_label bridge); full identity tokens optional cleanup  

### PR-5 — Groups align — **done**

- Group mean/norm, IO group, PP box/point use `storage_key_group` when `group_ID` set  
- Display labels remain human names; legend already prefers `display_label`  
- Export PP + `x_axis_xlim` / PPR extractors use role/metadata instead of name-split keys  

### PR-6 — Cleanup

- Remove `startswith(rec_name)`, deprecated `updateEPSPout` name lists if dead  
- Docs: short note in `AGENTS.md` or `brainwash_ui` docstring: *keys are identity; display_label is presentation*  
- Unlock #5 design: `display_recording_name(rec_ID)` feeds display_label only  

---

## #5 after this (sketch only)

1. `uistate.project.blind_names` + alias map `rec_ID → "Rec n"`  
2. Table `DisplayRole` for `recording_name` / `path`  
3. On toggle: recompute display_labels for visible entries **or** legend map calls `display_recording_name` live + `tableUpdate` + `graphRefresh` legends only  
4. **No** `dict_rec_labels` key changes  

---

## Risk & mitigation

| Risk | Mitigation |
|------|------------|
| Drag misses artists after key change | PR-4 tests with synthetic store; manual smoke drag amp/slope |
| Missed call site still uses old string | Grep CI / test for forbidden patterns: `f"{rec_name} - stim` in lookup contexts |
| Legend duplicates / empty | Legend tests on `output_axis_legend_map` with display_label |
| Performance O(n) find | n small; index only if measured slow |
| Mid-session mixed old/new keys | Full replot on upgrade; no pickle of dict_rec_labels (session-only) |

---

## Validation

**Automated**

```sh
uv run pytest src/brainwash/test_plot_stim.py src/brainwash/test_plot_series.py \
  src/brainwash/test_plot_model.py src/brainwash/test_plot_drag.py -q
# plus new test_plot_identity.py
```

**Manual smoke** (`manual_smokes_after_refactor.md` drag + multi-rec legend)

1. Preload multi-rec project → legends show real names  
2. Drag EPSP/volley amp & slope → markers/series update  
3. Stim-mode + time-mode  
4. Rename recording (if UI allows) → after this plan, plots should not break (regression target)  
5. Group means + n_unit level switch  

---

## Effort / risk

| | Estimate |
|--|----------|
| Effort | **L** (PR-1…6 over several sessions; not one afternoon) |
| Risk | **Med–high** during PR-3/4; **low** after green + smokes |
| Issue #5 alone without this | Lower effort, higher long-term cost |

---

## Recommended decision

1. **Approve** this plan as prerequisite to #5  
2. Start **PR-1** (helpers + tests only) on `1.0.0`  
3. File or retitle a tracking issue: e.g. “Plot artist identity: storage key ≠ display” (optional; can live as plan in `work_plans/` if preferred)  
4. #5 stays open until identity PRs land  

---

## Open choices (defaults proposed)

| Choice | Default |
|--------|---------|
| Key format | Opaque `rec|…` strings (Option A) |
| Lookup | Metadata filter helpers first; index if needed |
| Group keys | Same scheme in PR-5 (or with PR-3 if cheap) |
| Blind in same milestone | After PR-6 only |

If you prefer a **faster** path that still improves architecture: PR-1 + PR-4 only (metadata lookup, keep name keys) — unlocks safer drag/rename partially but **does not** fully unlock clean blinding of legends without display_label separation. Full Option A remains the right end state.
