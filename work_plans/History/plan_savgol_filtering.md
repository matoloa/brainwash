# Implementation Plan: Savitzky-Golay Filtering

This document outlines the steps to integrate Savitzky-Golay filtering into the analysis pipeline, connecting the recently added UI controls to the `analysis_v3.py` backend.

## 1. UI State (`ui_state_classes.py`)
Add default state tracking for the new UI controls in the `UIstate` class.
- In `UIstate.reset()`, add the corresponding keys to `self.lineEdit` for the window and polynomial parameters.
  ```python
  self.lineEdit.update({
      "savgol_window": 9,  # Default window length
      "savgol_poly": 3,    # Default polynomial order
  })
  ```
- Ensure the `radioButton_filter_*` state maps to `self.settings["filter"]`, which currently exists as `None` by default. When the `radioButton_filter_savgol` is selected, this should be updated to `"savgol"`.

## 2. Signal Wiring (`ui.py`)
Hook up the Qt signals to respond to user interaction.
- In `UIsub.connectUIstate()`:
  - Wire the `buttonGroup_filter` (or the individual `radioButton_filter_none` and `radioButton_filter_savgol` buttons) to a method that updates `uistate.settings["filter"]` and triggers a recalculation.
  - Wire `lineEdit_savgol_window` and `lineEdit_savgol_poly` (e.g., via `editingFinished`) to update `uistate.lineEdit` and trigger a recalculation.
- When applying config states (`applyConfigStates`), ensure the line edits and radio buttons correctly reflect the values saved in `uistate`.

## 3. Data Processing & DataFrames (`ui_data_frames.py`)
Translate the UI state into the actual dataframe columns before measurement.
- Update `get_dffilter` and `get_dfmean`:
  - If `row["filter"] == "savgol"`, extract `window_length` and `poly_order` from `row["filter_params"]` (which gets populated from `uistate.lineEdit`).
  - Call `analysis.addFilterSavgol(df, window_length, poly_order)` to create the `"savgol"` column. (This logic partially exists but needs to ensure it correctly interfaces with the `analysis_v3.py` API).
- Update `get_dfoutput`:
  - When calling `analysis.build_dfoutput(...)`, pass the `filter` keyword argument based on the current state (e.g., `filter="savgol"` if the SavGol filter is active, otherwise `filter="voltage"`).

## 4. Analysis Hookup (`analysis_v3.py`)
Leverage the functions in `analysis_v3.py` to calculate measurements on the filtered signal.
- **`addFilterSavgol` (Lines 119-126)**:
  - Used by the DataFrame mixin to populate the `'savgol'` column on the raw voltage data (`dffilter` / `dfmean`).
- **`build_dfoutput` (Lines 777-987)**:
  - `build_dfoutput` already uses the parameterized `filter` variable (e.g., `dffilter[filter].mean()`).
  - By passing `filter="savgol"` into this function from the UI layer, all amplitude, slope, and half-width calculations will automatically be performed on the smoothed Savitzky-Golay trace instead of the noisy raw `"voltage"` trace.

## 5. Plotting Updates (`ui_plot.py`)
Ensure the visualizations reflect the filtered data.
- When drawing the event and mean graphs, the plotting routine should read `uistate.settings["filter"]`. If it equals `"savgol"`, it should plot the `"savgol"` column on the Y-axis so the user can visually verify the effect of their chosen window and polynomial parameters.