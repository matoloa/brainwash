# PP formal stats — plan (observation layer only)

**Status:** COMPLETE — archived  
**Branch:** `0.16.3-nunit`  
**Goal:** Formal tests on PP use **mean PPR (stim2/stim1)** per unit, matching the plot, without changing time/train/IO engines.

## Principle

| Layer | Change |
|--------|--------|
| Test engines (t / Wilcoxon / ANOVA / Friedman / cluster) | **No** math changes |
| IO ANCOVA path | **No** |
| Layout gates | **No** |
| Observation when `experiment_type=="PP"` | **Yes** → PPR |
| Statusbar / methods wording | **Yes** (quantity = PPR) |

## PR checklist

| PR | Content | Done |
|----|---------|------|
| **1** | Pure `ppr_by_sweep_from_dfoutput`; `get_group_obs_for_sweeps` PP branch; mean PPR via existing mean-over-sweeps | done |
| **2** | Methods text PPR; config `quantity`; one-sample ref 1.0 when PP and stored ref is 0 | done |
| **2b** | PP without test sets: implicit all-sweeps window for unpaired / one-sample / multi-group ANOVA | done |
| **3** | PP applicability copy + statusbar shows PPR quantity / aspect labels | done |
| **4** | Manual smokes (below) | user |
| **5** | Figure-text PPR/box wording; switch to PP defaults unpaired t (not paired) | done |

**Tests:** `test_pp_stats_obs.py`, `test_plot_series` PPR helpers, `test_statistics_characterization`, `test_figure_text_md`.

## Manual smokes (PR4)

1. **PP, no test sets, 2 groups, unpaired t, n_unit=subject** — statusbar shows `· PPR`, p for amp/slope; hierarchy assigned; no “subject not assigned”.
2. **PP + paired** without 2 test sets — warning steers to unpaired / one-sample (not a blank graph).
3. **PP one-sample** — ref defaults toward 1; p vs facilitation null.
4. **Time/train** unpaired t with test sets — same numbers as before PP work.
5. **Export figure text** on PP — caption mentions box plots + PPR, not mean±SEM vs time.

## Non-goals

- No Mann–Whitney, no new test types  
- No cluster algorithm rewrite  
- No MODE_HANDLERS / dispatcher god-function growth  

## Risk control

- Gate: `experiment_type == "PP"` only  
- Reuse plot PPR formula (`compute_ppr`)  
- Existing `test_statistics_characterization` must stay green  
