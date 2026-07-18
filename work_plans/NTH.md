# NTH — Nice To Have

Deferred cleanups and small renames that are not urgent. Capture enough context that a later agent can act without re-discovery.

---

## Experiment type token: `"PP"` → `"pp"` (lowercase consistency)

**Status:** NTH — style-only; not a correctness bug.  
**Captured:** 2026-07-18 (branch `0.16.3-nunit` era).

### Motivation

Canonical `experiment_type` tokens are otherwise lowercase (`time`, `train`, `sweep`, `timestamp`, `io`). **`PP` is the only uppercase outlier.** UI radio **label** text `"PP"` can stay human-facing; only the **persisted/internal token** would become `"pp"`.

Helpers already use lowercase names: `is_pp`, `is_io`, `skip_pp_recording_output`, etc.

### Source of truth today

```python
# src/brainwash/ui.py — _RADIO_TO_TYPE
"radioButton_type_io": "io",
"radioButton_type_pp": "PP",   # ← rename target
```

Persisted in project `cfg.pkl` via `ExperimentConfig` / `uistate.experiment.experiment_type` (`ui_state_parts.py` + `get_state` / `apply_state_dict`).

### Scale (grep snapshot)

| Area | Rough size |
|------|------------|
| `== "PP"` / `!= "PP"` / membership checks under `src/brainwash/` | ~30–35 sites |
| Files | ~12–15 (`ui_plot`, `ui_selection`, `ui_graph`, `ui_interactive`, `export_image`, `plot_model` / `plot_series`, tests, radio maps) |
| Radio / wiring maps | `_RADIO_TO_TYPE` (+ inverse `_TYPE_TO_RADIO`), `test_ui_wiring.py` |
| Designer label `"PP"` | **keep** as display string |
| Stats package / parquet / `df_project` columns | **none** (cfg/UI token only) |
| Work plans / Archive docs | many `"PP"` mentions — non-runtime |

**LOC:** ~40–60 mechanical renames + ~10–15 migration + one load test. One focused PR.

### Risk

| Risk | Level | Notes |
|------|--------|--------|
| Existing `cfg.pkl` still stores `"PP"` | **Med without migration** | `_TYPE_TO_RADIO.get("PP")` fails → wrong radio / silent fall-through toward default `time` |
| Missed string compare | Low–med | Grep is nearly complete in `src/` |
| Data formats (ABF/parquet) | None | Not stored there |
| User-facing label | None | Keep radio text `"PP"` |

### Required if implementing

1. `_RADIO_TO_TYPE`: `"radioButton_type_pp": "pp"`.
2. Replace runtime `experiment_type == "PP"` (and peers) with `"pp"`.
3. **Load migration** in `ExperimentConfig.apply_state_dict` (or equivalent):

   ```python
   t = state.get("experiment_type", "time")
   if t == "PP":
       t = "pp"
   self.experiment_type = t
   ```

4. Facade / wiring test: old cfg with `"PP"` loads as `"pp"` and maps to `radioButton_type_pp`.

Optional one-release dual accept (`in ("pp", "PP")`) is usually unnecessary if load always normalizes.

### Out of scope (do not rename here)

- Plot/UI strings: `"PPR"`, `" IO trendline"`, aspect RGB keys.
- `test_type` values: `"ANOVA"`, `"ANCOVA"`, `"Wilcoxon"`, `"None"` (different naming domain).
- Archived plans under `work_plans/Archive/` / `History/` (leave historical).

### Verdict

**Advisable when idle** as a tiny consistency PR; **not urgent**. Prefer **token `"pp"` + label `"PP"`**. Do **not** mix into unrelated feature PRs; ship migration + tests or skip.
