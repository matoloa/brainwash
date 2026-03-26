# Plan: Stim-mode SEM Shading

## Objective

When the X-axis mode is set to "Stim" (`radioButton_xscale_stim`), calculate the Standard Error of the Mean (SEM) for the displayed measurements across all sweeps for each Stim. Display this SEM as a shaded region around the aggregate stim lines (similar to group SEM shades). When the mode is switched away from "Stim", cleanly hide these shaded regions.

## 1. Calculation of SEM (Stateless Approach)

- **Source Data:** The measurements exist in `dfoutput`. Sweeps have a numeric `sweep` value, whereas the aggregate stim row has `sweep` as `NaN`.
- **Logic:**
  1. Isolate sweep rows: `df_sweeps = dfoutput[dfoutput["sweep"].notna()]`.
  2. Group by `stim` and compute SEM: `df_sem = df_sweeps.groupby("stim").sem()`.
  3. Extract SEM for the required aspect (e.g., `EPSP_amp`, `EPSP_slope`, `EPSP_amp_norm`, etc.).
  4. Match these SEM values to the X-coordinates (`stim` numbers) and Y-coordinates (aggregate means from `out_stim`).
- **Caching Strategy:** We do **not** persist `df_sem` in a dictionary for fast lookup. Instead, we use the generated Matplotlib artist (the shaded polygon itself) as our cache. Calculating the SEM takes fractions of a millisecond and is only performed when a plot needs to be explicitly created or refreshed (e.g., when a recording is loaded or data is modified). For all other fast-toggling operations, we simply toggle the visibility of the pre-rendered artist.

## 2. Plotting the Shade (`ui_plot.py`)

- Integrate the SEM calculation and plotting directly into the existing stim-mode plotting block in `addRow` (around line 1060).
- Create a helper function in `UIplot`, e.g., `plot_stim_shade(...)`, to encapsulate the `fill_between` logic.
- Use Matplotlib's `fill_between` to draw the shade:
  ```python
  fill = axis.fill_between(x, y_mean - sem, y_mean + sem, alpha=0.3, color=color, zorder=0)
  ```
- **Storage:** Store the resulting `PolyCollection` artist in `self.uistate.dict_rec_labels` under a new tracking dictionary or directly associate it with the stim-mode line's properties. To hook into the existing visibility toggling system in `ui.py`, we will save these under their own unique label names (e.g., `f"{label} EPSP amp shade"`) and tag them with `x_mode="stim"`.

## 3. Dynamic Visibility & Cleanup (`ui.py`)

To adhere to "When 'stim' is not selected, clean it out", we leverage the existing `update_show` logic.

- **Toggling via X-Axis Mode:** In `ui.py` -> `x_axis_mode_changed`, the user swaps between "sweep", "time", and "stim". This immediately triggers `update_show()`.
- **Visibility Control:** `update_show()` iterates through `uistate.dict_rec_labels`. Since our newly plotted shades will be tagged with `x_mode="stim"`, the existing `_is_rec_visible` helper will automatically hide them when the user is in "sweep" or "time" mode, and show them when in "stim" mode.
- No special dictionary cleanup loop is required when toggling modes; hiding the artists perfectly solves the requirement visually while keeping the application snappy.

## 4. Handling Data Updates (e.g., Event Dragging)

- In `UIsub.eventDragReleased`, when data for a stim is modified, the underlying `dfoutput` changes. The existing code calls `uiplot.updateStimLines` to refresh the Y-data of the aggregate stim lines.
- **Shade Replacement:** `PolyCollection` objects (the shades from `fill_between`) cannot have their Y-data updated in place as easily as `Line2D` objects.
- Modify `updateStimLines` to recalculate the SEM from the newly passed `dfoutput`.
- Locate the old fill artist in `uistate.dict_rec_labels`, call `.remove()` to clear it from the canvas, generate a new `fill_between` artist, and slot the new artist back into `uistate.dict_rec_labels`.
