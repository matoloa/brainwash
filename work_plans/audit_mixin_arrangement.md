# Audit: mixin arrangement (#8)

**Date:** 2026-07-19  
**Branch:** `1.0.0`  
**Scope:** Ownership map + misplaced methods. **No large moves** in 1.0.0 unless noted as optional follow-up.  
**Supersedes (partially):** `work_plans/Archive/mixin_problems.md` (2026-07-12) — module-level singleton injection is **gone**; host is `self.uistate` / `self.config` / `self.uiplot`.

---

## Verdict

| Question | Answer |
|----------|--------|
| Is layout broken? | **No.** Extraction is complete enough for 1.0.0. |
| Blocking issues? | **None.** |
| Safe moves this milestone? | **None required.** Optional renames/docs only. |
| Biggest residual smells | (1) `GroupMixin` owns test sets; (2) `ui.py` still holds many thin triggers + some UI glue; (3) `protocols.py` incomplete vs mixins. |

**Recommendation:** Close #8 as **audit complete — no code moves**. File 1.0.1+ follow-ups only if desired.

---

## Host MRO (`UIsub`)

Order in `ui.py` (leftmost wins for name clashes):

```text
Ui_mainWindow          # QtDesigner widgets
GroupMixin             # groups + test sets + sample cache + toolstrip rows
SweepOpsMixin          # keep/remove/split sweeps & time
ProjectMixin           # project I/O, bw_cfg, blind, talkback, hierarchy, connectUIstate
DataFrameMixin         # dict_* caches, get_df*, group means / n_unit helpers
MenuMixin              # setupMenus only
ExportMixin            # CSV/clipboard/image export triggers
InteractivePlotMixin   # mouse, drag, ghost, mouseover
TableMixin             # project + stim tables
SelectionMixin         # update_show, event colors, stim µA table, toolframe visibility
GraphCoordinatorMixin  # graphRefresh bus, preload, zoom, splitters
ParseMixin             # import / parse pipeline UI
StatTestMixin          # formal tests, statusbar compute, n_unit radios
```

**Non-mixin gravity wells (not on MRO but critical):**

| Module | ~LOC | Role |
|--------|------|------|
| `ui_plot.py` (`UIplot`) | 2480 | Artist create/update; held as `self.uiplot` |
| `ui.py` (`UIsub` body) | 2110 | Init, freeze/thaw, talkback, many `trigger*`, radio handlers, stim add/remove |
| `export_image.py` | 1580 | Journal figure export (called from ExportMixin / host) |
| `ui_designer.py` | 1180 | Generated UI |

---

## Ownership map

| Mixin / module | Owns | Key state on host |
|----------------|------|-------------------|
| **GroupMixin** | Group CRUD, digit assign, membership, group cache purge, group toolstrip; **test-set** CRUD, test-set toolstrip, sample refresh hooks | `dd_groups`, `dd_testsets`, `dd_group_samples` |
| **SweepOpsMixin** | Sweep/time selection ops that mutate recordings | uses project/df caches |
| **ProjectMixin** | Bootstrap/load/save project, folders, `bw_cfg`, blind episode, talkback menu, hierarchy line edits, rename files | `df_project`, `dict_folders`, `projects_folder` |
| **DataFrameMixin** | Internal DataFrame pipeline + caches | `dict_ts`, `dict_outputs`, `dict_means`, … |
| **MenuMixin** | Wire QActions → host methods | — |
| **ExportMixin** | Export menu actions | — |
| **InteractivePlotMixin** | Event/mean/output mouseover & drag | plot drag state on `uistate.plot` |
| **TableMixin** | `tableProj` / `tableStim` format & selection | selection lists on plot state |
| **SelectionMixin** | Visibility (`update_show`), color-events apply, IO stim-strength table | — |
| **GraphCoordinatorMixin** | Refresh bus, axes setup, preload, zoom, splitter capture | canvases on host |
| **ParseMixin** | Parse/import UI flow | — |
| **StatTestMixin** | Test type radios, formal run, statusbar text/state | `uistate.stat_test` |
| **UIsub (`ui.py`)** | App lifecycle, freeze/thaw, heatmap toggle, darkmode, **talkback usage**, stim add/remove, bulk lineEdits, **thin menu triggers** that call into mixins, filter/experiment/type radios, group/testset checkbox handlers | `config`, `uistate`, `uiplot` |

### Cross-cutting “hub” methods (intentionally shared)

Any mixin may call these; they are the glue, not misplacement:

- `graphRefresh` / `request_graph_refresh` → GraphCoordinatorMixin  
- `update_show` → SelectionMixin  
- `mouseoverUpdate` → InteractivePlotMixin  
- `usage` / `talkback` → UIsub  
- `get_df*` / `set_dft` → DataFrameMixin  
- `apply_statistical_test_if_active` / statusbar → StatTestMixin  
- `group_save_dd` / `testset_save_dd` → GroupMixin  

---

## Misplaced / awkward (with recommendation)

| Item | Where | Issue | 1.0.0 action | Later? |
|------|--------|--------|--------------|--------|
| **Test sets live in GroupMixin** | `ui_groups.py` | Name implies groups only; ~1/3 of file is testset + shared list-header patterns | **Keep.** Coupling is real (same toolstrip UX, shared refresh/sample invalidation). | Optional: rename to `GroupTestsetMixin` or extract `TestSetMixin` **as pure cut-paste** in 1.0.1 with smoke |
| **group/testset checkbox + thin triggers** | `ui.py` | `groupCheckboxChanged`, `testsetCheckboxChanged`, `triggerClearAllGroups`, … sit next to app shell | **Keep for 1.0.0.** They are UI event adapters; logic is already in GroupMixin. | Move adapters next to GroupMixin if desired |
| **groupControlsRefresh / testsetControlsRefresh** | Defined on **UIsub** (`ui.py`), not GroupMixin | GroupMixin has `testsetControlsRefresh` in history/duplicate risk — host overrides with `update_anova_label` side effect | **Keep on host** (stat-test coupling). Do not delete without checking MRO. | Document “host owns refresh orchestration” |
| **Stim intensity (µA) table** | SelectionMixin | Not really “selection”; domain is IO experiment | **Keep.** Works; moving is churn. | Optional IO-focused mixin later |
| **Stim add/remove, stimDetect** | `ui.py` | Large, domain-heavy | **Keep.** Not blocking. | Could join InteractivePlot or a StimMixin post-1.0 |
| **Talkback** | ProjectMixin (menu/cfg) + UIsub (usage/setup/slice) | Split is OK: global cfg vs host logging | **Keep.** | — |
| **Blind** | ProjectMixin | Correct home | **Keep.** | — |
| **protocols.py** | Only 3 hosts | Incomplete vs real mixins | **No code required.** | Expand protocols when typing efforts resume |
| **ui_plot size** | 2.5k LOC | Not a mixin arrangement bug | Out of #8 | plot_identity / plot_stim already peels pure logic |
| **Archived mixin_problems.md** | History | Documents **removed** singleton injection | Treat as historical | Do not re-apply |

---

## What improved since modularity (vs archive)

- Mixins use **`self.uistate` / `self.config` / `self.uiplot`** set on the host — no module-level injection block.  
- Pure helpers live under `brainwash_ui/` (`view_state`, `color_events`, `plot_stim`, `recording_pipeline`, …).  
- Stats implementation is in `brainwash_stats/`, not a UI mixin.  
- Host is still large, but **behavior is partitioned** enough to navigate by domain.

---

## Optional follow-ups (not 1.0.0 blockers)

1. **Rename** `GroupMixin` → `GroupTestsetMixin` (or document in module docstring only — cheaper).  
2. **1.0.1:** Extract `TestSetMixin` only as mechanical move + manual smoke (digits, set CRUD, formal test, samples).  
3. Expand `protocols.py` when someone needs typing, not as a cleanup drive.  
4. Do **not** start “shrink `ui.py`” without characterization tests for triggers.

---

## Acceptance criteria check (#8)

- [x] Ownership map written  
- [x] Misplaced methods listed with recommended home  
- [x] Small safe moves: **none** chosen for 1.0.0 (risk free)  
- [x] No behavior regressions (no code change)  
- [x] Host contracts: noted incomplete; optional later  

---

## Suggested issue resolution

Close #8 with: *Audit complete; no moves in 1.0.0. See `work_plans/audit_mixin_arrangement.md`.*
