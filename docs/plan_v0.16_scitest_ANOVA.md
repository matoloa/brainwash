# Implementation Plan: Add ANOVA Test Option (v0.16 extension)

## Context

The original v0.16 plan (docs/plan_v0.16_scitest.md) left ANOVA as a future extension point ("leave clean hooks", "not yet implemented" message). The user now wants to activate the existing ANOVA radio button. A new toolframe for ANOVA (with assumption test checkboxes for Normality/Homogeneity, one-way vs repeated-measures logic based on # test sets, effect size in statusbar, dynamic test label) was proposed. This was assessed as not sensible for immediate implementation because it requires UI changes that would violate the "NEVER alter ui_designer.py" rule and adds significant new analysis/UI scope beyond "implement ANOVA test option".

**Current user update**: The ANOVA UI frame has now been added (presumably via designer or dynamic means, object name likely `frameToolTest_anova` or similar per the attached ui_designer.py outline). The immediate task is to make this frame hide when ANOVA is not selected, mirroring the existing `frameToolTest_t` behavior for t-test (which is shown only when `test_type == "t-test"`).

This fits the minimal activation path while accommodating the new frame. Assumption tests, repeated-measures logic, effect size, and dynamic label can be addressed in follow-up work (after the core ANOVA computation is enabled).

The session plan file was repeatedly crashing on `exit_plan_mode`; per user instruction we are now working exclusively from this stable copy in `docs/plan_v0.16_scitest_ANOVA.md`.

## Recommended Approach

Extend the existing visibility logic in `src/lib/ui.py` (without touching ui_designer.py):

- Identify the exact object name of the new frame (via grep or read_file on ui_designer.py or runtime inspection; current outline shows the class but not the specific frame name for the new ANOVA panel).
- In `test_type_changed()` and the restore/visibility methods (`update_experiment_type_radio_buttons`, `update_tool_visibility` ~3017, and cfg restore ~3301), add conditional visibility for the new frame (e.g. `self.frameToolTest_anova.setVisible(test_type == "ANOVA")`).
- This reuses the exact pattern used for the t-test sub-panel (`frameToolTest_t.setVisible(test_type == "t-test")` in `test_type_changed`, `update_experiment_type_radio_buttons`, and restore logic).
- As a follow-on, remove the "not implemented" guard in `apply_statistical_test_if_active()` and `_get_stat_test_warning()` so ANOVA becomes a valid test type (full computation in analysis_v3.py is the next logical step).

**Critical files to modify**: `src/lib/ui.py` (visibility, test_type_changed, warning/applicator logic). `docs/plan_v0.16_scitest_ANOVA.md` (this plan).

**Existing utilities to reuse** (with paths):

- `frameToolTest_t.setVisible(...)` + `test_type_changed()` pattern (ui.py:2607-2608, 3022, 3314).
- `update_experiment_type_radio_buttons()` and cfg restore logic for radio buttons (~2629, 3301-3314).
- `apply_statistical_test_if_active()` and `_get_stat_test_warning()` (ui.py:1718, 1620) — generalize the t-test specific guards.
- `_RADIO_TO_TEST` dict already includes ANOVA (ui.py:2534).

**No changes**: ui_designer.py, analysis_v3.py (until next phase), new assumption tests.

## Verification

- Select t-test → t-subpanel shows, ANOVA frame hides.
- Select ANOVA → ANOVA frame shows, t-subpanel hides.
- Select None → both frames hidden.
- Restart / load cfg → visibility matches saved `test_type`.
- No regression on t-test visibility or statusbar behavior.

This is the smallest change that makes the new ANOVA frame behave like the t-test panel. Full ANOVA computation (f_oneway in analysis_v3.py, statusbar effect size, assumption tests) is the logical next step once visibility is working.

**Next**: After approval, implement visibility toggle first (identify exact frame name via read-only tools), then extend compute path.
