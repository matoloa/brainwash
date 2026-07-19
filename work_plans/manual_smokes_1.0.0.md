# Manual smokes — 1.0.0 product surface

**Branch:** `1.0.0`  
**Date:** 2026-07-19  
**Scope:** Post-refactor product issues #1–#10 (not the UI modularity suite).  
**Companion:** [manual_smokes_after_refactor.md](manual_smokes_after_refactor.md) for graph/stats/mixin regression.

Mark each item **PASS** / **FAIL** / **SKIP**.

---

## Automated preflight

```sh
uv run pytest src/brainwash/ -q
```

Targeted (identity / heal / color / sweeptimes):

```sh
uv run pytest src/brainwash/test_plot_identity.py \
  src/brainwash/test_identity_lookup_patterns.py \
  src/brainwash/test_color_events.py \
  src/brainwash/test_sweeptimes.py \
  src/brainwash/test_recording_pipeline_stim_ids.py \
  src/brainwash/test_splitter_proportions.py -q
```

---

## #10 Lean data + sweeptimes

| # | Step | Result |
|---|------|--------|
| 10.1 | Open/import a project; confirm `data/{rec}.parquet` is lean (no clock columns) and `data/{rec}_sweeptimes.parquet` exists after parse | |
| 10.2 | Time-mode x-axis and export still show sensible time | |
| 10.3 | Re-open project without re-parse; plots load | |

---

## #1 Groups overhaul

| # | Step | Result |
|---|------|--------|
| 1.1 | Select recs → digit **1** creates/assigns group 1; **2** assigns group 2 | |
| 1.2 | Digit keys do not fire while focus is in a text field (e.g. stim µA) | |
| 1.3 | Double-click **×** on a group row removes it; hover shows attention statusbar | |
| 1.4 | Clear-all groups from menu | |
| 1.5 | Rename group → legend label updates | |

---

## #4 Test sets (parity with groups)

| # | Step | Result |
|---|------|--------|
| 4.1 | Create test set via Tag; full-width row + × remove | |
| 4.2 | Clear-all test sets menu | |
| 4.3 | Formal t-test still sees shown sets | |

---

## #5 Blind / unblind

| # | Step | Result |
|---|------|--------|
| 5.1 | Data → Blind recordings → table shows `Rec n`; paths on disk unchanged | |
| 5.2 | Legend / mouseover use blind names; storage keys still opaque (`rec|…` not blind text) | |
| 5.3 | Tool strip **Blinded** × unblinds; aliases reshuffled on next Blind | |
| 5.4 | Optional: Always blind new projects in prefs | |

---

## #6 Color events by Rec \| Stim \| Group

| # | Step | Result |
|---|------|--------|
| 6.1 | Single rec + single stim: default aspect/event colors; axe mouseover works | |
| 6.2 | Multi-rec: color-by Rec distinguishes traces | |
| 6.3 | Multi-stim (1 rec): color-by Stim | |
| 6.4 | Color-by Group uses group colors; ambiguous → black | |

---

## #2 / #3 Results display + palette

| # | Step | Result |
|---|------|--------|
| 2.1 | Results display: Dots vs Line for output series | |
| 3.1 | Default EPSP blue / volley green / stim indigo→violet on new project | |

---

## Stim table + heal-once policy

| # | Step | Result |
|---|------|--------|
| S.1 | No rec selected → stim table headers only (no bloated empty body) | |
| S.2 | Multi-rec selection → common stims only, stim column only | |
| S.3 | Project with invalid/NA stim ids: first open repairs, console logs **once**, `cfg.pkl` gains `stim_id_heal_log` entry | |
| S.4 | Re-select same rec in same session: no second timepoints rewrite storm | |
| S.5 | h_splitterMaster proportions stable (dft pane not bloating) | |

---

## #7 Talkback / #9 hygiene

| # | Step | Result |
|---|------|--------|
| 7.1 | Talkback default off; enable via Data menu → quiet usage file + title suffix | |
| 9.1 | No Experimental flag/menu; Export has no silent “Copy project summary” | |

---

## Preview / drag (identity)

| # | Step | Result |
|---|------|--------|
| D.1 | Preview checkbox on: live output aspect update while dragging axe markers | |
| D.2 | Preview off: no live output spam; release still commits | |
| D.3 | Drag amp/slope zones still hit correct artists after identity keys | |

---

## Failure triage

- Blind leaks real names in legend → check `display_label` sync / `display_recording_name`.
- Drag misses artists → identity lookup (`find_rec_entries` / `find_entry_by_display_label`); run `test_identity_lookup_patterns`.
- Stim ids thrash disk → session heal set / `stim_id_heal_log`; only `set_dft` should always write.
