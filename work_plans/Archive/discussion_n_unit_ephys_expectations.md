# Discussion: n_unit Handling (subject / slice / recording) and Electrophysiologist Expectations

**Context**  
This note summarizes the analysis of how Brainwash currently supports different statistical units (`n_unit`) for formal tests (t-test, ANOVA, etc.) and whether the design aligns with expectations from electrophysiologists (particularly in slice physiology / patch-clamp work).

The discussion was prompted by:  
> "t-test of rec is straightforward. How does the data currently handle slice- and subject settings?"

Followed by evaluation against the project's own `statistical_protocol.md`.

## Current Data + Stats Handling (Summary)

### Fetch Layer (Always Recording-Level)
- `get_group_testset_means` / `get_group_obs_for_sweeps` (ui_data_frames.py) always returns **one row per recording**.
- Computes mean value over the test set's sweeps for the chosen aspect.
- Joins `subject` and `slice` columns from `df_project` (using ID → rec_ID).
- Result: per-recording observations + hierarchy tags. This is independent of the selected `n_unit`.

### Aggregation Layer
- Performed in `_aggregate_to_unit_level(obs_df, n_unit)` (brainwash_stats/data.py), called from formal test implementations (ttest_and_between.py, etc.).
- Logic:
  - `"recording"`: pass-through (identity). One value per recording.
  - `"subject"`: `groupby(["subject"]).mean()` → one value per unique subject.
  - `"slice"`: `groupby(["subject", "slice"]).mean()` → one value per unique (subject, slice) pair.
- The unit-level values (and count of units) are then used for the actual statistical test and for `n1`/`n2` in results.
- `n` reported = number of units after aggregation.
- Cluster permutation forces `"recording"`.
- Old projects without subject/slice columns trigger warnings and fall back to recording-level.

### UI + Reporting
- Radios for `n_unit`: subject (default), slice, recording.
- Statusbar (non-IO formatter) reports chosen units with labels, e.g.:
  - `(SAL=3, KETA=2 subjects)`
  - Or equivalent for slices.
- `n_unit` is stored in results config and affects statusbar n_report and usage logging.
- Hierarchy can be edited per selected recordings and triggers `update_test()`.

### Paired / Within-Subject Cases
- Aggregation happens first.
- Paired t-test/Wilcoxon then takes finite unit-level arrays and pairs by position (min-n prefix). Relies on consistent ordering from rec list + groupby appearance order.

## Project's Stated Statistical Protocol (statistical_protocol.md)

Key excerpts:
- "Subject (animal) is the **only** independent experimental unit."
- "Subject defines the biological sample size (n)."
- "Slice and Recording are nested repeated measurements and **must never increase n**."
- "Never compare groups using recordings or slices as independent observations."
- Recommended approach (when mixed models unavailable):
  1. One summary value per recording.
  2. Average recordings within each subject.
  3. Perform stats using subject means.
- Always report full hierarchy: "n = X subjects, Y slices, Z recordings."
- Prefers mixed-effects models with random effects for Subject / Slice / Recording.

## Does the Current Implementation Match Electrophysiologist Expectations?

### Strengths (What Would Generally Please Ephys Users)
- Explicit support for the biological hierarchy instead of hard-coding cell-level n.
- Correct mean-aggregation logic for the chosen unit.
- Transparent statusbar reporting of what "n" actually represents (subjects vs slices).
- Default to "subject" in many places.
- Recording-level is straightforward for per-cell questions (when justified).
- Flexibility allows users to match their specific experimental design.

### Weaknesses and Mismatches
- **Direct conflict with the project's own protocol**: The code makes `"slice"` and `"recording"` first-class, equally accessible choices with no strong enforcement or warnings. The protocol explicitly states these levels "must never increase n."
- **Pseudoreplication risk**: Allowing easy t-tests/ANOVA with n = recordings or n = slices is exactly the practice that careful reviewers and statisticians in the field criticize (inflated sample sizes, false positives).
- **No guardrails**: UI radios present all options neutrally. No prominent warnings when choosing non-subject units. No requirement to acknowledge the hierarchy in reports.
- **Lack of recommended methods**: The protocol advocates mixed-effects models. Current implementation uses classical tests on collapsed data only.
- **Paired logic**: Order-based pairing after aggregation can be fragile for subject- or slice-level paired designs (biological pairing is usually within-cell or within-animal).
- **Reporting**: While statusbar shows the chosen n, it does not automatically produce the full "subjects / slices / recordings" breakdown that the protocol requires.
- **Cultural reality in ephys**:
  - Pragmatic users often publish with n = cells or n = slices (especially in certain subfields or older papers).
  - Strict/best-practice electrophysiologists (and journal reviewers) expect n = animals as the default, with full hierarchy reporting and justification for anything else.
  - Providing powerful "wrong" options without friction can be viewed as enabling poor statistical practice.

### Overall Verdict
The implementation is **technically competent** at supporting different units and does the aggregation correctly. It offers welcome flexibility compared to tools that silently use cell-level n.

However, it **does not fully match the expectations** of a careful electrophysiologist who follows modern standards or the project's own `statistical_protocol.md`. It provides the *means* to do the right thing (subject-level) but also makes it trivially easy to do the discouraged thing (slice- or rec-level) without guidance or warnings.

A rigorous ephys user would likely appreciate the hierarchy support and transparency, but would want:
- Stronger defaults and warnings favoring subject-level.
- Better automatic hierarchy reporting.
- Ideally a path toward mixed-effects models.
- Clearer separation between "allowed for exploration" vs "recommended for publication."

## Related Files
- `statistical_protocol.md` (the project's stated rules)
- `src/lib/brainwash_stats/data.py` (`_aggregate_to_unit_level`)
- `src/lib/ui_data_frames.py` (fetch + hierarchy join)
- `src/lib/brainwash_stats/formal_tests/*.py` (usage in t-test etc.)
- `src/lib/ui.py` (n_unit radios, statusbar formatting, n_unit_changed)

---

*This file created to archive the discussion for future reference / planning.*
