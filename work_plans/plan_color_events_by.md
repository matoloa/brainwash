# Plan: Color events by Rec | Stim | Group (#6)

**Issue:** [#6](https://github.com/matoloa/brainwash/issues/6)  
**Branch:** `1.0.0`  
**Status:** Implemented (pending manual smoke / issue close)
**Related:** Results display toolframe (Designer: Rec / Group / Stim nr); stim gradient `UIplot.get_dict_gradient`; groups `dd_groups` colors / `show`

---

## Goal

When several **recordings** are selected, event traces (**axe**) and related stim markers (**axm**) are superimposed. Same colors make them hard to tell apart.

Provide **Color events by** modes that disambiguate overlays using:

- **Rec** — indigo→violet gradient over selected recordings  
- **Stim** — same gradient family over stim indices (existing behavior)  
- **Group** — strict group palette coloring (no gradients)

**Not in scope:** output-series coloring (ax1/ax2); nested rec×stim dual gradients.

---

## UI (Designer — may already be partially present)

| Control | Role |
|---------|------|
| Label | **Color events by** |
| `radioButton_display_color_rec` | Preference: Rec |
| `radioButton_display_color_group` | Mode: Group |
| `radioButton_display_color_stim_number` | Preference: Stim |
| `buttonGroup_display_color` | Exclusive group |

**Default checked radio: Rec.**

Persist preference in project cfg (e.g. `uistate.project.color_events_by` ∈ `rec` | `stim` | `group`), default `rec`.

---

## Mode semantics (locked)

### Group mode (`radio = Group`)

Throws **rec and stim gradients out entirely**.

- Every selected rec (and all its stims on axe/axm) is colored **strictly by group membership**.
- Membership considers only groups with **`show == True`**. Hidden groups are ignored (as if the rec were not in them).
- Exactly **one** shown group → that group’s `color`.
- **Zero** shown groups, or **two or more** shown groups → **black**.
- Rec/stim selection counts and radio Rec/Stim preferences **do not apply**.

### Rec / Stim modes (`radio = Rec` or `Stim`)

These radios are **not** “always color by X.” They are **preference selectors** used only when **both** several recordings **and** several stims are selected.

| Selection | Effective encoding |
|-----------|-------------------|
| 1 rec, many stims | **Stim** gradient (preference ignored) |
| Many recs, 1 stim | **Rec** gradient (preference ignored) |
| Many recs, many stims | **Radio preference** (Rec or Stim) |
| 1 rec, 1 stim | Single color (either scheme collapses) |

---

## Effective mode algorithm (pure; unit-test)

```text
function effective_color_events_mode(radio, n_rec_selected, n_stim_selected):
    if radio == "group":
        return "group"
    # radio is "rec" or "stim"
    if n_rec_selected == 1 and n_stim_selected > 1:
        return "stim"
    if n_rec_selected > 1 and n_stim_selected == 1:
        return "rec"
    if n_rec_selected > 1 and n_stim_selected > 1:
        return radio   # "rec" or "stim"
    return radio       # 0/1×0/1: preference or single color
```

`n_stim_selected`: count of stims relevant to the current event view (typically stims present in selected recs’ dft / selected stims in timetable — define as **union of stim numbers on selected recs that are shown on axe**, usually all stims in dft for those recs unless a narrower stim selection exists; implement against existing stim-selection semantics).

---

## Gradient keys

### Stim

- Domain = **all detected stims** on selected recs (union from artists/dft), **not** only field-selected stims.
- Index = rank in sorted full domain → same hue for blob and event of stim *k*.
- `get_dict_gradient(len(domain))` (indigo→violet).

### Rec

- Domain = **full table display order** (all rows), not only selected.
- Selected recs take the hue for their rank in that list (stable when selection shrinks).
- Resorting the table reassigns ranks (intentional).
- Storage / identity always **`rec_ID`**.

```text
display_order = [row.ID for row in tablemodel._data]  # full list
color[rec_id] = gradient[rank_in_display_order]
stim_domain = union of detected stims on selected recs
color[stim_k] = gradient[rank_in_stim_domain]
```

### Group

- No gradient.
- Shown-group membership → group color or black (see above).

---

## What artists to recolor

**In v1:**

- **axe** event lines (per rec × stim)  
- **axm** stim markers / selection vlines that currently use stim gradient  

**Out v1:**

- Output ax1/ax2 series recoloring  
- Group mean series (already group-colored)  
- Mean full-trace on axm (stays black)

---

## Refresh triggers

Recompute colors when any of:

- Color-events radio change  
- Project table selection change  
- Project table sort / `tableUpdate` (display order)  
- Stim selection change (if it affects `n_stim` or stim set)  
- Group show/hide, group color rename, group membership change  

Prefer `set_color` on existing artists when possible; full replot only if simpler and cheap enough.

---

## Identity / blinding

- Color keys use **`rec_ID` only**.  
- `rec_ID` is never user-facing outside debug.  
- Blind `Rec n` labels do not drive hue; table display order under blind still drives **rec** gradient position.

---

## Tests

Pure helpers (no Qt if possible):

1. `effective_color_events_mode` matrix (radio × n_rec × n_stim).  
2. Rec gradient assignment follows a given display-order list of IDs.  
3. Group color: one shown group → color; zero / multi shown → black; hidden group ignored.  
4. Regression: single-rec multi-stim → stim gradient regardless of radio=rec.

Manual smoke:

- Multi-rec select → Rec preference / auto rec colors; sort table → colors reorder.  
- Multi-stim single rec → stim colors.  
- Group mode + multi membership → black; single group → group color; hide group → membership updates.

---

## Implementation sketch (not binding)

| Piece | Place |
|-------|--------|
| Pure mode + color resolve | `brainwash_ui/` (e.g. `view_state` or small `color_events.py`) |
| Wire radios + persist | `ui_project` / `ui_selection` / `connectUIstate` |
| Apply colors | `ui_plot` show/refresh + selection path |
| Designer default Stim→Rec | Ensure `radioButton_display_color_rec` checked if not already |

---

## Acceptance criteria

- [ ] Default radio **Rec**; persisted across project load  
- [ ] Group mode: only group colors / black; no rec/stim gradients; shown groups only  
- [ ] Rec/Stim radios: preference only for multi-rec **and** multi-stim; auto overrides as table above  
- [ ] Rec gradient follows **table display order** among selected; sort reapplies  
- [ ] Stim gradient monotonic as today  
- [ ] Multi-group or ungrouped (shown) → black in group mode  
- [ ] Unit tests for effective mode + group membership + display-order keys  
- [ ] Manual multi-rec event overlay is distinguishable  

---

## Out of scope / later

- Nested gradient (rec base + stim shade)  
- Gray vs black for ambiguous group (v1 = **black** as specified)  
- Export-specific color policy beyond “same artists as interactive”

---

## Roadmap / issue hygiene

- #6 + ROADMAP already point at this plan (events Rec|Stim|Group).

---

## Changelog (plan)

| Date | Note |
|------|------|
| 2026-07-19 | Design locked from discussion; plan filed for implement |
| 2026-07-19 | Drop aspect/output-mode residue from plan wording |
| 2026-07-19 | Implementation: `color_events.py`, radios, `apply_event_colors` |
