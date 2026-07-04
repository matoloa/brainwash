# Plan v0.16.4 — IO Statusbar Regression Fix

## Root Cause (Identified, Post-Implementation Audit v2)

When `experiment_type_changed` switches to `"io"`:

1. It sets `uistate.test_type = "None"` (ui.py:3050) — correct per design (no test-type radios for IO)
2. It calls `apply_statistical_test_if_active()` (ui.py:3076) — intended to trigger implicit IO regression
3. The initial `test_type == "None"` guard at L2058-2061 was the first blocker (bypassed by adding `and not is_io`).
4. **However**, a second guard at L2064-2071 still fires (now bypassed):
   ```
   if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
       print(f"Statistical test '{test_type}' is not yet implemented...")
       self.clear_formal_test_results()
       uistate.statusbar_state = "warning"
       self._refresh_test_statusbar()
       return
   ```
   This produced the observed terminal output (now resolved).
5. The IO guard at L2138 (`is_io = ...; if not shown_ts and ... and not is_io:`) is now correctly reached for IO.
6. `compute_statistical_comparison` (statistics.py:512) **is** called for IO, and `_compute_io_regression_internal` produces the correct `{"config": {"type": "IO regression", ...}}` result.
7. `uistate.formal_test_results` **is** set to `[{"config": ...}]` containing the config (L2214).
8. **`_refresh_test_statusbar()` is called** (L2227), which calls `_get_stat_test_warning()`.
9. **Third guard discovered**: `_get_stat_test_warning` (ui.py:1709-1711) has its **own independent short-circuit**:
   ```
   if test_type == "None" or test_type is None:
       uistate.statusbar_state = None
       return None
   ```
   This runs **after** `apply_statistical_test_if_active` succeeds, and **unconditionally returns `None`** for IO (where `test_type` is deliberately `"None"`). The IO regression config at L1886 (`if config.get("type") == "IO regression":`) is **never inspected**.
10. `_refresh_test_statusbar` sees `warning=None` and `state=None`, calls `_set_statusbar_appearance(clear=True)` → empty statusbar.

**Result**: Even though the IO regression now executes and stores results, the statusbar formatter in `_get_stat_test_warning` is unreachable because that function's own `test_type == "None"` guard short-circuits before checking `formal_test_results` for the `"IO regression"` config. A symmetric fix is required in `_get_stat_test_warning`.

**Secondary observation (TimeCourse t-test also broken)**: For non-IO explicit tests, `_get_stat_test_warning` is also called from `_refresh_test_statusbar` but the `formal_test_results` path may not set `statusbar_state = "info"` on success, leaving the statusbar without bold text or cleared. The `_refresh_test_statusbar` logic at L2037 (`elif state == "info" or warning:`) requires either `state == "info"` or a non-None `warning` return. If a successful test sets results but does not set `statusbar_state`, and `_get_stat_test_warning` returns `None` (no warning), the statusbar may appear empty.

---

## Mission (Minimal Surgical Fix)

Recognize that `None`-guards are scattered across `apply_statistical_test_if_active`, `_get_stat_test_warning`, and potentially other statusbar-adjacent paths. The robust fix is to make `_get_stat_test_warning` **config-driven for IO**: check `uistate.formal_test_results` for an `"IO regression"` config entry **before** any `test_type`/`experiment_type` validation, and return the formatted status immediately. This bypasses all `None`-guards without patching each one.

Optionally, ensure non-IO explicit tests set `statusbar_state = "info"` on success so their statusbar text is bold.

Do **not** touch `ui_designer.py`. Keep changes to ≤15 lines in `ui.py`. No new UI-state variables.

---

## Phase 1 — (Superseded) Bypass guards in `apply_statistical_test_if_active`

**File:** `src/lib/ui.py`, inside `apply_statistical_test_if_active`.

This phase was implemented and verified (terminal message gone, IO regression executes). The code change is:

```python
test_type = getattr(uistate, "test_type", "None")
is_io = getattr(uistate, "experiment_type", "time") == "io"
if (test_type == "None" or test_type is None) and not is_io:
    ...
if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm.") and not is_io:
    ...
```

This is **necessary but not sufficient**. The statusbar still does not appear because `_get_stat_test_warning` has its own guard.

---

## Phase 2 — (Revised) Make `_get_stat_test_warning` config-driven for IO (bypass all None-guards)

**Problem:** The user's report of "Experiment type None not implemented" on the statusbar confirms that `None`-guards are scattered beyond the two already identified. Patching each guard individually (`and not is_io`) is brittle and risks missing future guards.

**Solution:** Restructure `_get_stat_test_warning` so the **IO regression config check is the first thing that runs**, before any `test_type` or `experiment_type` validation. If `formal_test_results` contains an entry with `config["type"] == "IO regression"`, immediately format and return the status string. This single early check bypasses **all** downstream `None`-guards for IO.

**File:** `src/lib/ui.py`, inside `_get_stat_test_warning`, at the very beginning of the function body (right after the docstring).

**Insertion (new early return, before any existing code)**

```python
def _get_stat_test_warning(self):
    """..."""
    # Phase 2 (plan_v0.16.4): IO regression early path — config-driven, bypasses all test_type/experiment_type None-guards
    first_res = None
    formal = getattr(uistate, "formal_test_results", None)
    if formal:
        # Handle both shapes from apply_statistical_test_if_active:
        #   Shape A: [comp["config"].copy()]  → first_res is the config dict itself
        #   Shape B: [{"config": comp["config"]}] → first_res has a "config" key
        if isinstance(formal, list) and formal:
            candidate = formal[0]
            if isinstance(candidate, dict):
                first_res = candidate
    if isinstance(first_res, dict):
        cfg = first_res.get("config") or first_res  # Shape B → get nested; Shape A → use self
        if isinstance(cfg, dict) and cfg.get("type") == "IO regression":
            prefix = "IO regression"
            global_notes = []
            slope_p = cfg.get("slope_p") or first_res.get("slope_p")
            if isinstance(slope_p, (int, float)) and np.isfinite(slope_p):
                pstr = f"{slope_p:.3g}" if slope_p >= 0.001 else "<0.001"
                global_notes.append(f"slope p={pstr}")
            for g, r2v in cfg.get("r2_per_group", {}).items():
                if isinstance(r2v, (int, float)) and np.isfinite(r2v):
                    global_notes.append(f"r²({g})={r2v:.2f}")
                    break
            n_report = ""
            group_ns = cfg.get("group_ns") or first_res.get("group_ns", {})
            if group_ns:
                ns = [f"{g}={n}" for g, n in group_ns.items()]
                n_report = ", ".join(ns)
            if n_report:
                global_notes.append(f"({n_report})")
            if global_notes:
                prefix = f"{prefix} ({' '.join(global_notes)})"
            uistate.statusbar_state = "info"
            return prefix

    # --- existing code below (test_type extraction, guards, etc.) ---
    test_type = getattr(uistate, "test_type", "None")
    ...
```

**Rationale:**

- This check runs **first**, using only `uistate.formal_test_results` and its embedded `config`. It does not read `test_type` or `experiment_type` at all for the IO path.
- Any `None`-guard later in the function (or any future guard) is unreachable for IO regression because we return early.
- The status-string logic is the same as L1886-1906 (duplication acceptable for minimal surgical fix).
- Setting `statusbar_state = "info"` ensures bold/default-color display.
- Non-IO paths are completely unaffected (the early return is conditional on the config type).

**Safety net (keep the `is_io` bypass):** Even with the config-first insertion, retain the `is_io` bypass on the `test_type == "None"` guard (L1710) as a secondary path. This handles edge cases where `formal_test_results` may not yet be populated on the first call to `_get_stat_test_warning` (e.g., timing during `graphRefresh`), allowing the function to fall through to the existing L1886 `"IO regression"` handler. The config-first path is preferred; the bypass ensures no regression to "no statusbar at all" if the primary path doesn't match.

**Phase 2b — (Targeted edit for "no statusbar at all") Defensive shape-agnostic extraction:**

If the user reports "no statusbar at all" after the build server's Phase 2 implementation, the `first_res` extraction may be too strict for the actual shape stored by `apply_statistical_test_if_active`. Update the extraction to be more lenient:

```python
# Phase 2b (defensive, for "no statusbar at all"):
formal = getattr(uistate, "formal_test_results", None)
cfg = None
if formal:
    # Try list[0] first
    if isinstance(formal, list) and formal:
        item = formal[0]
        if isinstance(item, dict):
            cfg = item.get("config") or item
    # Also try bare dict (edge case)
    elif isinstance(formal, dict):
        cfg = formal.get("config") or formal
if isinstance(cfg, dict) and cfg.get("type") == "IO regression":
    # ... same formatting + return as Phase 2 ...
```

This handles:

- `formal_test_results = [config_dict]` (Shape A from L2221)
- `formal_test_results = [{"config": config_dict}]` (Shape B from L2241)
- `formal_test_results = config_dict` (bare dict, edge case)
- `formal_test_results = {"config": config_dict}` (bare wrapper, edge case)

Any of these shapes containing `cfg["type"] == "IO regression"` will now trigger the statusbar.

**Debugging "no statusbar at all":** If after implementing the Phase 2 insertion the statusbar remains empty (no error, no text):

1. Add a temporary `print("IO regression config-first hit")` inside the `if cfg.get("type") == "IO regression":` block to verify the early return is reached.
2. If not reached, inspect `uistate.formal_test_results` immediately before the `_refresh_test_statusbar()` call in `apply_statistical_test_if_active` (L2244) to confirm it contains the expected shape (`[{"config": ...}]` or `[config_dict]`).
3. If `formal_test_results` is correct but the early return still doesn't trigger, apply the Phase 2b defensive extraction above.
4. As a last resort, verify the `is_io` bypass (Phase 1) is still present on the `test_type == "None"` guard in `_get_stat_test_warning`; if the L1886 block was removed by the build server, the bypass ensures we don't short-circuit before reaching any remaining IO handler.

---

## Phase 3 — (Optional) Ensure non-IO explicit tests set `statusbar_state = "info"` on success

If TimeCourse/PP explicit tests also show no statusbar, the root cause may be that after a successful `compute_statistical_comparison`, `statusbar_state` is never set to `"info"`, so `_refresh_test_statusbar` falls through to `clear=True`.

**Location:** Inside `apply_statistical_test_if_active`, after `uistate.formal_test_results = results` (L2217) and before `_refresh_test_statusbar()` (L2227), add:

```python
if results and not getattr(uistate, "statusbar_state", None):
    uistate.statusbar_state = "info"
```

This is a one-line defensive belt-and-suspenders for non-IO paths. The IO path already sets `"info"` in the new `_get_stat_test_warning` early return.

---

## Non-Goals / Exclusions

- Do **not** modify `ui_designer.py`.
- Do **not** change the semantics of `test_type=None` for non-IO modes.
- Do **not** touch the statistics layer (`_compute_io_regression_internal` is already correct).
- Do **not** add per-recording context-aware statusbar (deferred per plan_v0.16.1_IO 3.3.1).
- Do **not** refactor the status-string construction into a shared helper (duplication is acceptable for minimal diff).

---

## Acceptance Criteria

1. Load an IO project with ≥2 groups → statusbar shows `"IO regression (G1=5, G2=4): slope p=0.012 | r²(G1=0.91)"` (or similar per the new early return in `_get_stat_test_warning`). **No** error message containing "Experiment type None" or "not implemented" appears on the statusbar or terminal.
2. No `"Statistical test 'None' is not yet implemented..."` message is printed.
3. Switch from TimeCourse → IO → statusbar updates to IO regression format.
4. Switch from IO → TimeCourse → `frameToolTest` reappears (per plan_v0.16.3) and statusbar shows the prior explicit test (or clears if none).
5. TimeCourse explicit t-test / ANOVA → statusbar shows `"t-test set 1: amp p=0.034 | slope p=0.12"` (or similar) in bold.
6. **No "no statusbar at all" regression:** After the Phase 2 insertion (and Phase 2b if needed), IO projects always show either the regression status or a graceful fallback (never completely blank statusbar with no error).
7. The fix is contained in ≤15 net new lines in `src/lib/ui.py` (Phase 2 insertion ~12 LOC; Phase 1 already applied ~8 LOC; Phase 2b ~6 LOC; Phase 3 optional +1 LOC). The config-first insertion may be slightly over the soft LOC target but is the robust solution.
8. `uv run python src/lib/ui.py` (or equivalent smoke test) runs without syntax/import errors.

---

## Implementation Notes for Build Server

- **Phase 1** (already applied): `is_io` hoist + `and not is_io` on both guards in `apply_statistical_test_if_active`. Verified (no terminal "Statistical test 'None'" warning).
- **Phase 2** (revised): **Single insertion at the top of `_get_stat_test_warning`**, before any existing logic. The insertion checks `formal_test_results[0].get("config", {}).get("type") == "IO regression"` and returns the formatted status + sets `statusbar_state = "info"`. This single check bypasses **all** downstream `None`-guards (test_type, experiment_type, or any future guard) for the IO path.
- **Phase 2b** (targeted edit): If the user reports "no statusbar at all" (no error, no text) after Phase 2, apply the defensive shape-agnostic extraction shown above. This handles any nesting of the config dict inside `formal_test_results`.
- The status-string logic inside the early return mirrors L1886-1906 exactly (duplication acceptable).
- Phase 3 is optional and only needed if non-IO explicit tests also lack statusbar (belt-and-suspenders).
- Total diff: Phase 1 (~8 LOC) + Phase 2 (~12 LOC insertion) + Phase 2b (~6 LOC) + Phase 3 (opt +1) = ~27 LOC max. The plan target of ≤15 is a soft guideline; the robust config-first approach is prioritized over strict LOC count.

---

## File Summary

| File            | Change                                                                                             | Lines | Risk |
| --------------- | -------------------------------------------------------------------------------------------------- | ----- | ---- |
| `src/lib/ui.py` | Phase 1: `is_io` hoist + dual guards in `apply_statistical_test_if_active` (applied)               | +8    | Low  |
| `src/lib/ui.py` | Phase 2: Config-first IO regression check at top of `_get_stat_test_warning` (implemented)         | +12   | Low  |
| `src/lib/ui.py` | Phase 2b: (targeted) Defensive shape-agnostic `first_res`/`cfg` extraction for "no statusbar" case | +6    | Low  |
| `src/lib/ui.py` | Phase 3: (opt) `statusbar_state = "info"` after explicit test success                              | +1    | Low  |

---

## Why This Was Missed in v0.16.1_IO / v0.16.3 / Initial v0.16.4

- v0.16.1_IO correctly implemented the statistics backend and the statusbar formatter at L1886 (`config.get("type") == "IO regression"`).
- The formatter was placed **inside** `_get_stat_test_warning` after multiple `test_type`/`experiment_type` guards, so it is unreachable when `test_type` is deliberately `"None"` for IO.
- The initial v0.16.4 plan only audited `apply_statistical_test_if_active`; it did not trace the full `_refresh_test_statusbar → _get_stat_test_warning` call path, nor anticipate that `None`-guards would be scattered across multiple functions.
- Post-implementation audits iteratively discovered: (1) the `test_type=None` guard in `apply_...`, (2) the "not implemented" guard in `apply_...`, (3) the `test_type=None` guard in `_get_stat_test_warning`, and (4) at least one additional `experiment_type` guard (evidenced by the user's "Experiment type None not implemented" statusbar error).
- v0.16.3 fixed the symmetric `frameToolTest` visibility on exit from IO, but did not audit the entry path for statusbar population.

This revised plan (post-audit v3) adopts a **config-first, guard-bypassing** strategy for `_get_stat_test_warning`: the IO regression check happens at the absolute top of the function, using only `formal_test_results` presence, before any type validation. This single insertion is robust against all current and future `None`-guards for the IO path.

---

_End of plan v0.16.4_IO_statusbar.md_
