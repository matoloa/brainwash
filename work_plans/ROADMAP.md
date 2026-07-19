# Brainwash roadmap (1.x)

Living priority map across milestones. **Execution** is on GitHub issues when a milestone is active or next; **design detail** lives in focused `plan_*.md` files.

| Rule | Practice |
|------|----------|
| Active work | GitHub issue + optional `plan_*.md` |
| Future milestones | Bullets here until that milestone starts |
| Done | Link release/tag; archive plans to `work_plans/History/` |
| One roadmap | This file — do not spawn per-milestone roadmap clones |

**Branch policy:** `main` freezes the last shipped line (currently **0.16.3** at the `0.16.3-nunit` merge). Development for the next major line is on **`1.0.0`**. Tag `v0.16.3` on that freeze point if not already tagged.

---

## 1.0.0 — in progress

**Milestone:** [1.0.0](https://github.com/matoloa/brainwash/milestone/1)  
**Theme:** Format floor for recording data + core UI polish. Pre-1.0 working-copy parquets are not a product compat surface (re-parse from raw).

### Filed issues

| # | Title | Notes |
|---|--------|--------|
| [#10](https://github.com/matoloa/brainwash/issues/10) | Lean data + `_sweeptimes.parquet` | **Done** — [`plan_data_sweeptimes_format.md`](plan_data_sweeptimes_format.md) |
| [#1](https://github.com/matoloa/brainwash/issues/1) | UI Groups overhaul | **Done** — digit create/assign, clear-all, header, rename/legend |
| [#2](https://github.com/matoloa/brainwash/issues/2) | Output line appearance UI | **Done** — Results display Dots/Line |
| [#3](https://github.com/matoloa/brainwash/issues/3) | Default aspect color palette | **Done** — EPSP blue / volley green; stim indigo→violet; legacy magenta migrate |
| [#4](https://github.com/matoloa/brainwash/issues/4) | UI Test Sets overhaul | **Done** — full-width rows, × remove, header, clear-all menu; create via Tag button |
| [#5](https://github.com/matoloa/brainwash/issues/5) | Blind / unblind rec names | **Done** — display-only random `Rec n` episodes; strip × unblind; always-blind-new in `bw_cfg` |
| [#6](https://github.com/matoloa/brainwash/issues/6) | Color events by Rec \| Stim \| Group | **Done** — [`plan_color_events_by.md`](plan_color_events_by.md); 1×1 defaults; axe/axm overlay |
| [#7](https://github.com/matoloa/brainwash/issues/7) | Reconnect Talkback | **Done** — Data-menu toggle (default off); quiet `usage.yaml`; title suffix when on |
| [#8](https://github.com/matoloa/brainwash/issues/8) | Audit mixin arrangement | **Done** — [`audit_mixin_arrangement.md`](audit_mixin_arrangement.md); no moves |
| [#9](https://github.com/matoloa/brainwash/issues/9) | Clean sweep: Experimental + TODOs | **Done** — [`todo_triage_1.0.0.md`](todo_triage_1.0.0.md); dead flag/menu removed; remaining TODOs → 1.0.1+ |

### Suggested focus order

1. ~~**#10** format~~ **done**  
2. ~~**#1** Groups~~ **done**  
3. ~~**#2** line style~~ **done** · ~~**#3** palette~~ **done**  
4. ~~**#4** test sets~~ **done** · ~~**#5** blind~~ **done**  
5. ~~**#6**–**#9**~~ **done** (color events, talkback, mixin audit, TODO/Experimental hygiene)  

### Capacity note

**1.0.0 filed issues #1–#10 are complete.** Next work is ship/tag and/or **1.0.1** bullets below (file milestone when ready).

---

## 1.0.1 — not filed yet

**Theme:** Bugs + small UX after 1.0.0; establish **forward** migrator habit from the 1.0.0 floor (not dual-read of pre-#10 data parquets).

### Bugs

- Samples from removed test sets linger as persisted files  
- Analysis method in `dft` not correctly updating  
- `dfp` rec states not correctly updating  
- `dft` timepoints listed with inconsistent precision  
- PP: x-axis labels not aligning properly  

### Small UX

- Highlight recordings in group on mouseover of group widget  
- Output indication of odd/even sweep selection  
- Darkmode-sensitive popups  
- Consistent toolFrame size / margins  
- When `tableProj` is active, left/right arrow keys change stim number  
- **Export project table (`dfp`)** to `.csv` / `.xls` (former dead “Copy project summary” menu — re-add only when implemented)  

### Interactive / cross-cut

- Better slope drag display: linest + vertical markers while mouse down  
- Hook long-running tasks to the progress bar (inventory + top N call sites; not unbounded)  

### Process

- Project/format **forward** BC pattern after 1.0.0 (version-aware load / pure migrators for *new* fields). Data parquet dual-stack for old shapes is **out** (handled by #10 + re-parse policy).
- **Customizable / user-persisted color schemes** (aspect RGBs, stim ramp, group palette) — defaults ship in 1.0.0 (#3); full UI + per-project/global schemes later.

### Folded into 1.0.0 (do not re-file)

- Statusbar update on group rename → **#1**

### When to file

When 1.0.0 is nearly done or shipped: create GitHub milestone **1.0.1**, one issue per bullet (merge only if natural), link from this section.

---

## 1.1 — not filed yet

**Theme:** Analysis affordances and subject/slice hierarchy UX.

- Volley compensation (by slope, amp, means); respect bins  
- Radio: number key assigns **group | subject | slice** (after Groups #1 patterns exist)  
- Indicate related slices by n-level at selection (color-match slice/subject cells in project table)  
- Enhance paired data handling (e.g. pair identical subjects across groups)  
- Automatically add measure points to manually added stims  
- Train: output reporting options and stats  
- PP: extrapolate (rounded) ms from data, store in metadata? *(still soft — spike or drop when filing)*  

### Open decisions

- Number-key mode (group/subject/slice): hold to 1.1 with n-level coloring, or early 1.0.1 after #1?  
- Train stats: same milestone as volley compensation, or later?

---

## 1.2 — not filed yet

**Theme:** Larger analysis tool surface (optional separate milestone).

- Frame with tools to break chronology in timecourse / sweeps: compare sweeps after X minutes (regardless of stims), or by sweep number (regardless of time)  

**Decision:** keep as **1.2**, or fold into **1.1** if fewer milestones preferred.

---

## Parse / interchange — not filed yet

**Suggested milestone name when created:** `parse-interop` or `1.3` (not 1.0.1).

| Item | Relation to #10 |
|------|------------------|
| Compatible with published / external data formats | Separate epic |
| Rational datetime / sequence start / delay for **internal** working copy | **#10** (`_sweeptimes`) |
| Backward-compat converters for **pre-#10** data parquets | **Out** — re-parse from raw |
| Migrators for **post-1.0.0** schema changes | 1.0.1+ BC habit |

Do not re-file “sequence start times” as a second internal-clock project unless scope is import/export interchange beyond #10.

---

## Deferred (NTH / not a milestone)

See [`NTH.md`](NTH.md) for small style items (e.g. experiment type token `"PP"` → `"pp"`).

---

## How to use this file

1. **Starting a milestone:** file issues from that section; set GitHub milestone; replace bullets with issue links.  
2. **Hard design:** add `work_plans/plan_<topic>.md`, link from the issue and here.  
3. **Finishing a milestone:** mark section done + release/tag; move detailed plans to `History/`.  
4. **Personal placeholder lists:** merge into this file, then delete the placeholder.

---

## Changelog (roadmap only)

| Date | Change |
|------|--------|
| 2026-07-19 | Initial draft from 1.0.0 issue set + placeholder triage discussion |
| 2026-07-19 | #5 blind/unblind marked **done** (`2bce475`); focus order → #6–#9 |
| 2026-07-19 | #6 retargeted to color **events** (Rec/Stim preference + Group mode); [`plan_color_events_by.md`](plan_color_events_by.md) |
| 2026-07-19 | Post-#1–#10 hardening: identity dual-path cleanup, stim-id heal-once + `stim_id_heal_log`, [`manual_smokes_1.0.0.md`](manual_smokes_1.0.0.md) |
