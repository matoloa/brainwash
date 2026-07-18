# Plan: Publication-grade IO ANCOVA (radio-triggered only)

**Status:** APPROVED (2026-07-18) — **PR-A–D done**; next PR-E (expanded characterization / goldens)  
**Branch target:** `0.16.3-nunit` or follow-on  
**Goal:** Make Input–Output formal analysis **trigger only from the ANCOVA radio**, fix UI/engine inconsistencies, and deliver a **textbook-style ANCOVA** suitable for respectable scientific reporting (methods text, statusbar, export).

---

## 0. Problem statement (current state)

| Issue | Today |
|--------|--------|
| Trigger | Any `experiment_type == "io"` runs IO regression; ANCOVA radio is cosmetic for compute |
| Statusbar | Non-ANCOVA → warning (good); ANCOVA/None → “IO ANCOVA” from regression results |
| Naming | Config `type: "IO regression"`; UI label “IO ANCOVA”; UI call passes `test_type="ANOVA"` |
| Test sets | Shown test sets **disable** IO path (`use_implicit` only when no sets) → fall through to ordinary ANOVA |
| Method | Per-group `linregress` + OLS `y ~ x * C(group)` interaction p only; no full ANCOVA table |
| Options | `io_force0` plot-only; amp/slope/norm hardcoded in `_apply_io_regression` |
| Assumptions | No SW/Levene/homogeneity-of-slopes workflow for publication |
| Markers | Nonstandard result shape; not a clean formal-test story |

**Scientific gap:** A single interaction *p* for unequal slopes is **part** of ANCOVA practice, not a complete, citeable ANCOVA report (model, assumptions, adjusted means / slope tests with clear hypotheses).

---

## 1. Product / scientific definition (lock this first)

### 1.1 When analysis runs

**Run formal IO ANCOVA if and only if:**

1. `experiment_type == "io"`, **and**
2. `stat_test.test_type == "ANCOVA"`.

**Do not run** when:

- IO + `None` / t-test / ANOVA / Wilcoxon / …  
- non-IO experiment (ANCOVA radio inactive or shows “not applicable” / not implemented for time)

**On enter IO:** default/select ANCOVA radio (and persist).  
**On leave IO:** restore previous non-IO test type if stored, or leave user choice (prefer restore).

### 1.2 Estimand (textbook framing for ephys IO)

**Primary design for 2+ groups, continuous X (volley/stim) and Y (EPSP amp/slope):**

Use a **linear model with group and covariate**, with an explicit **homogeneity-of-slopes** step:

| Step | Model | Hypothesis (report) |
|------|--------|---------------------|
| **A. Homogeneity of slopes** | \(Y = \beta_0 + \beta_X X + \beta_G G + \beta_{XG}(X \times G) + \varepsilon\) | \(H_0: \beta_{XG} = 0\) (parallel slopes) |
| **B1. If slopes homogeneous** | \(Y = \beta_0 + \beta_X X + \beta_G G + \varepsilon\) | \(H_0: \beta_G = 0\) (group effect adjusted for X) — **classical ANCOVA** |
| **B2. If slopes differ** | Report interaction; **do not** report B1 as primary; report **per-group slopes** and interaction *p* as primary |

**Publication text (status/export must enable):**

- “We tested homogeneity of regression slopes (X×group). Where slopes did not differ, we used ANCOVA with X as covariate and group as factor. Where slopes differed, we report separate slopes and the interaction.”

**Unit of analysis:** respect `n_unit` (subject / slice / recording). One (x, y) row per unit per distinct X (after aggregation), **not** raw sweeps mixed with subjects without aggregation.

**Force-through-origin:** optional model \(Y = \beta_X X\) (+ group / interaction variants) only if `io_force0` is on; document as constrained regression, not default ANCOVA.

### 1.3 Scope non-goals (v1)

- Multivariate MANCOVA  
- Non-linear IO curves  
- Bayesian ANCOVA  
- Using time/sweep test-set * markers as primary IO UI (IO remains scatter + statusbar + optional export table)

---

## 2. Target architecture

```text
experiment_type == "io"  AND  test_type == "ANCOVA"
        │
        ▼
apply_statistical_test_if_active
        │
        ▼
_apply_io_ancova()                    # rename from _apply_io_regression
        │
        ▼
compute_statistical_comparison(
  experiment_type="io",
  test_type="ANCOVA",                 # real gate, not "ANOVA"
  ...
)
        │
        ▼
dispatcher: is_io and test_type=="ANCOVA"  (ignore empty-testset-only implicit hack)
        │
        ▼
brainwash_stats/io/ancova.py          # textbook pipeline
  build XY (n_unit) → fit models → assumptions → results + config
        │
        ▼
formal_test_results + statusbar "IO ANCOVA …" + optional print table / export
```

**Remove:** `is_io and use_implicit` as sole gate; **remove** always-on IO compute when experiment is IO.

---

## 3. Workstreams (phased PRs)

### PR-A — Trigger & UX consistency (no science change yet)

**Intent:** ANCOVA radio is the only switch; statusbar and compute agree.

1. **`_effective_test_type`**
   - Delete IO → always `"io_regression"`.
   - IO + ANCOVA → `"ANCOVA"` (or `"io_ancova"` if you want a private eff token; prefer public `"ANCOVA"` + experiment_type).

2. **`apply_statistical_test_if_active`**
   ```text
   if experiment_type == "io":
       if test_type == "ANCOVA":
           _apply_io_ancova()
       else:
           clear_formal_test_results()  # no silent regression
       return
   ```

3. **Statusbar (`app_context.compute_statusbar_result`)**
   - IO + non-ANCOVA → keep warning: *Use ANCOVA for Input-Output experiment analysis*
   - IO + ANCOVA → format ANCOVA results (or “select ≥2 groups…”)
   - IO + None → clear or short hint (“Select ANCOVA to run Input-Output analysis”) — **not** full results

4. **Enter/leave IO**
   - On enter IO: set `test_type = "ANCOVA"`, check ANCOVA radio, show ANOVA/ANCOVA sub-frame if needed, `update_test()`.
   - Optionally stash prior `test_type` on `stat_test` for restore when leaving IO.

5. **Tests:** unit tests for dispatch (IO+t-test → no results; IO+ANCOVA → calls ANCOVA path).

**Exit criterion:** Selecting t-test on IO clears formal results and only shows warning; ANCOVA runs analysis.

---

### PR-B — Dispatcher & validation clean-up

1. **`validate_comparison_inputs`**
   - Allow `test_type == "ANCOVA"` when `experiment_type == "io"`.
   - Reject ANCOVA on non-IO with clear error (or route later).

2. **`comparison_context` / early guard**
   - Replace `if is_io and use_implicit` with:
     ```text
     if is_io and test_type == "ANCOVA":
         return compute_io_ancova(...)
     ```
   - **Test sets in IO:** either  
     - **Policy 1 (recommended v1):** ignore test sets for IO ANCOVA (use all sweeps/bins; document); or  
     - **Policy 2:** if shown sets exist, restrict XY to those sweeps only (explicit feature).  
     **Do not** fall through to time-style ANOVA.

3. **Config type:** `"IO ANCOVA"` (canonical); keep reading legacy `"IO regression"` in statusbar for one release if needed.

4. **Characterization tests:** IO+ANCOVA+empty sets; IO+ANCOVA+shown sets (chosen policy); IO+ANOVA radio does not enter ANCOVA.

---

### PR-C — Textbook ANCOVA engine (`brainwash_stats/io/ancova.py`)

**Replace/extend** `_compute_io_regression_internal` (keep old as private fallback only if needed during migration).

#### C.1 Data

- Reuse/fix `_get_io_xy_pairs` so X is joined **per recording** (rec_ID + sweep), not a global sweep→X merge that can mis-align recs.
- Aggregate to `n_unit` **before** model (one row per unit × x level).
- Require finite X,Y; drop incomplete units with count in diagnostics.
- Wire **amp/slope/norm** from UI checkboxes (same as non-IO).
- Optional **force0** from `io_force0` as constrained model variant.

#### C.2 Models (statsmodels OLS)

For each active aspect (amp/slope columns):

1. Build long frame: `y, x, group` (group = group id labels).
2. **Interaction model:** `y ~ x * C(group)`  
   - Extract interaction F/p (Type II or III — **pick Type II** and document; consistent with many ephys papers).
3. **Additive ANCOVA:** `y ~ x + C(group)`  
   - Group F/p, covariate F/p, adjusted means at grand mean of X (emmeans-style or predict at \(\bar x\)).
4. Decision:
   - If interaction p ≥ α (default 0.05, optional UI later): primary = additive ANCOVA.
   - If interaction p < α: primary = interaction; flag “slopes differ; ANCOVA group main effect not interpreted.”

#### C.3 Assumptions (publication minimum)

| Check | Method | Report |
|--------|--------|--------|
| Residual normality | Shapiro–Wilk on residuals (if n allows) | p, pass/warn |
| Homogeneity of residual variance | Levene or Breusch–Pagan on residuals / by group | p, pass/warn |
| Homogeneity of slopes | interaction p | already primary gate |
| Linearity | optional residual-vs-X plot export later | v1: text note only |
| Min n | ≥2 groups; ≥2 points/group with finite XY; prefer ≥3 units/group warn | statusbar warning |

Honor existing SW/Levene checkboxes if present: when checked, append notes / fail soft-warn; do not invent new UI in v1 unless needed.

#### C.4 Result contract (for statusbar / print / export)

```python
config = {
  "type": "IO ANCOVA",
  "x_col", "y_col", "n_unit",
  "force_through_zero": bool,
  "alpha_slopes": 0.05,
  "slopes_homogeneous": bool,
  "p_interaction", "F_interaction", "df_...",
  "p_group_ancova", "F_group_ancova",   # if homogeneous
  "p_covariate", "F_covariate",
  "slope_per_group": {...},
  "r2_per_group": {...},
  "adjusted_means": {...},              # if homogeneous
  "group_ns": {...},
  "assumptions": {"sw": ..., "levene": ..., "notes": [...]},
  "primary_contrast": "group_adjusted" | "slope_interaction",
}
results = [{
  "set_id": "__io_ancova__",
  "config": config,
  "p_slope": p_interaction,             # back-compat key
  "p_group": p_group_ancova,            # new
  "group_ns": ...,
  ...
}]
```

#### C.5 Numerical quality

- Prefer `statsmodels.stats.anova.anova_lm(model, typ=2)`.
- Guard singular designs (collinear X within group).
- No silent bare `except` swallowing failures — log and return structured `error`.

---

### PR-D — Statusbar, console table, export

1. **`format_io_ancova_statusbar`** (rename/extend `format_io_regression_statusbar`):
   - Homogeneous:  
     `IO ANCOVA (G1=n, G2=n subjects) EPSP amp / volley amp: group p=… (X-adj); slopes OK (p_int=…); r²…`
   - Heterogeneous:  
     `IO ANCOVA …: slopes differ (interaction p=…); group-adj ANCOVA not applied; slopes: G1=… G2=…`
   - Assumption fail: append short `; warn: residuals…` or keep warning state if severe.

2. **Console `_print_statistical_test_table`:** ANCOVA branch with interaction + group tables.

3. **Export (optional same stack or follow-up):** methods sentence + table of F, df, p for interaction and group; per-group slopes.

4. **Markers:** v1 may keep statusbar-only for IO (no fake * on scatter) unless a clear rule exists (e.g. annotate panel). Prefer **no misleading * markers** until designed.

---

### PR-E — Tests & scientific characterization

| Test | Assert |
|------|--------|
| Synthetic parallel slopes, different intercepts | interaction n.s.; group ANCOVA p small |
| Synthetic different slopes | interaction p small; primary = interaction |
| One group | applicability warning, no crash |
| n_unit subject aggregation | n matches unique subjects |
| Force0 on/off | coefficients match constrained model |
| Legacy config `"IO regression"` | statusbar still readable one release |
| UI dispatch | only ANCOVA radio triggers compute |

Use fixed seeds and known OLS solutions where possible (hand-checked small matrices).

---

## 4. File touch map

| Area | Files |
|------|--------|
| Gate / UI | `ui_stat_test.py`, `ui.py` (`experiment_type_changed`), maybe `ui_project.applyConfigStates` |
| Statusbar | `brainwash_ui/app_context.py`, `brainwash_ui/statusbar.py` |
| Dispatcher | `brainwash_stats/dispatcher.py`, `validation.py` |
| Engine | `brainwash_stats/io/ancova.py` (new), `regression.py` (thin or deprecate), `xy_pairs.py` (rec-safe X) |
| Tests | `test_app_context.py`, `test_statistics_characterization.py`, new `test_io_ancova.py` |
| Docs | this plan; AGENTS.md one-liner when done; **not** full methods paper in-repo |

---

## 5. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Breaking projects that relied on auto-IO without ANCOVA | Default to ANCOVA on enter IO; migrate cfg `None`+io → ANCOVA once optional |
| “ANCOVA” contested if only interaction reported | Always run homogeneity step; label primary contrast explicitly |
| Type II vs III debate | Fix Type II in config; document |
| Small n ephys | Soft warnings, never crash; minimum n rules |
| XY mis-merge | Fix join key to rec+sweep before claiming publication grade |
| Scope creep | v1 = 2-group + multi-group OLS as above; no fancy post-hocs until v1.1 |

---

## 6. Implementation order (recommended)

1. **PR-A** Trigger-only ANCOVA (behavior fix users feel immediately)  
2. **PR-B** Dispatcher/validation + test-set policy  
3. **PR-C** Engine (science)  
4. **PR-D** Statusbar/export copy  
5. **PR-E** Expand tests / golden synthetic cases  

Do **not** ship PR-C without PR-A (would still run on wrong radio).

---

## 7. Definition of done

- [ ] Formal IO analysis runs **only** when ANCOVA is selected (and experiment is IO).  
- [ ] Non-ANCOVA on IO: warning statusbar, **no** formal IO results/markers.  
- [ ] Entering IO selects ANCOVA.  
- [ ] Shown test sets do not silently switch to time-ANOVA.  
- [ ] Results include interaction test + (when appropriate) covariate-adjusted group test.  
- [ ] Statusbar states primary contrast and key p-values.  
- [ ] XY per unit is scientifically defensible (rec-safe join + n_unit).  
- [ ] Characterization tests for parallel vs non-parallel synthetic data.  
- [ ] Methods-ready wording available from config/statusbar (and optionally export).

---

## 8. Open decisions (resolve before PR-C coding)

1. **IO + None:** clear only vs auto-select ANCOVA on first IO entry only?  
   **Recommendation:** auto-select ANCOVA on enter IO; None on IO after user choice → hint, no compute.  
2. **Test sets:** ignore (v1) vs filter sweeps?  
   **Recommendation:** ignore for v1; document.  
3. **α for slope homogeneity:** fixed 0.05 vs setting?  
   **Recommendation:** fixed 0.05 in v1, store in config.  
4. **≥3 groups:** omnibus group factor only vs pairwise post-hoc?  
   **Recommendation:** omnibus only in v1.  

---

## 9. Out of scope / NTH

- Forcing lowercase `pp` (see `work_plans/NTH.md`).  
- Full journal figure ANCOVA brackets.  
- Mixed-effects random intercepts per subject beyond n_unit aggregation (v2 if reviewers demand LMM).
