# Plan: Paired Pulse (PP) Mode Feature

## Objective

When the "PP" experiment type is selected (`experiment_type == "PP"`), the output graphs (`ax1` / `ax2`) must display the Paired Pulse Ratio (PPR) instead of individual stimulus responses. PPR is calculated as `(Stim 2 / Stim 1) * 100`. The X-axis typically remains Sweep or Time, allowing the user to track how the paired pulse ratio evolves over the course of the recording.

Because this is a fundamental change to the Y-axis data and meaning, switching into or out of PP mode will clear and redraw the output graph artists from scratch (similar to I-O mode).

## Phase 0: UI Prerequisites & Validation

- **Radio Button Enabling**: Visibly disable the `radioButton_type_PP` if the active recording(s) do not have exactly two stims.
- **Display Guard**: If a recording with just one stim, or more than two stims, is selected while already in PP mode, bypass the plotting logic and do not display any output at all for it.

## Phase 1: Data Calculation & Data Mapping

- **Extraction**: For a given recording in `dfoutput`, isolate rows where `stim == 1` and `stim == 2`.
- **Join/Align**: Merge or align these two sets of rows based on the `sweep` column.
- **PPR Calculation**: Calculate `(Value_Stim_2 / Value_Stim_1) * 100` for `EPSP_amp`, `EPSP_slope`, `volley_amp`, and `volley_slope`.
- **Safety**: Implement safe division to handle cases where `Stim 1` is zero or missing, resulting in `NaN` rather than an exception or infinity.
- **Conditionals**: If a recording has fewer than 2 stimuli, return an empty series/array and do not plot PPR lines.

## Phase 2: Plotting Engine (`ui_plot.py`)

- **Branching in `addRow`**:
  - Add logic to check `if getattr(self.uistate, "experiment_type", "time") == "PP":`.
  - Suppress the standard output line generation (which loops over `stim` and plots absolute values).
  - Compute the PPR arrays (Phase 1).
  - Plot the PPR arrays against `sweep` or `time` using standard `Line2D` objects.
  - Store the resulting artists in `self.uistate.dict_rec_labels` with a unique label (e.g., `f"{label} PPR {aspect}"`) and tag them with `x_mode=uistate.x_axis`.
- **Target Axes**: Plot `EPSP_amp` and `volley_amp` PPR on `ax1`. Plot `EPSP_slope` and `volley_slope` PPR on `ax2`.
- **Norm Variant**: For the initial implementation, if `variant == "norm"` is requested, it might be best to ignore it and always plot raw PPR (since PPR is already a relative percentage), or calculate `PPR / baseline_PPR` if double-normalization is required.

## Phase 3: Toggling Mode & UI Updates (`ui.py`)

- **`experiment_type_changed`**:
  - Add `"PP"` to the list of modes that trigger a complete graph rebuild.
  - Ensure `uiplot.unPlot()` is called when switching into or out of `"PP"`, followed by `graphUpdate()`.
- **Axis Labels**:
  - When in PP mode, update the Y-axis labels of `ax1` and `ax2` to indicate "PPR (%)" or similar, overriding the standard "Amplitude (mV)" / "Slope" labels.

## Phase 4: Groups in PP Mode

- **Group Calculations**: In `ui_plot.py -> addGroup` (or equivalent layout logic), intercept `experiment_type == "PP"`.
- Instead of a time-series line, calculate the overall mean of the PPRs across all constituent recordings for each group.
- Calculate the SEM of the PPRs across the recordings.
- **Visual Representation**: Render a Bar plot with overlaid points.
  - Draw a Bar representing the mean PPR.
  - Add Error bars representing the SEM.
  - Overlay individual data points (the PPRs of each individual recording within the group).
- **Layout**: Groups will each occupy one distinct space on the X-axis, labeled with the group's name. No legend is required.
