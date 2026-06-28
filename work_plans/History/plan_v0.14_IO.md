# Plan: Input-Output (I-O) Mode Feature

## Objective

When the "I-O" experiment type is selected (`experiment_type == "io"`), the output graph (`ax1` / `ax2`) must fundamentally change its behavior. Instead of plotting a measurement (Y) against Time/Sweep/Stim (X), it will render a **scatterplot** where each sweep is a point.
Because this is a fundamental layout change and toggling is rare, we will _not_ pre-render and hide these plots. Instead, switching into or out of I-O mode will completely wipe the existing output graph artists and redraw them from scratch.

## 1. Data Mapping

Map the radio button states to their exact column names in `dfoutput`:

- **Input (X-axis)** (`uistate.io_input`):
  - `vamp` -> `volley_amp`
  - `vslope` -> `volley_slope`
  - _(Note: `stim` input is temporarily disabled and will be handled in a later phase)._
- **Output (Y-axis)** (`uistate.io_output`):
  - `EPSPamp` -> `EPSP_amp`
  - `EPSPslope` -> `EPSP_slope`

## 2. Plotting Engine (`ui_plot.py`)

Adopt a redraw-from-scratch architecture:

- **Branching in `addRow`**: Check `self.uistate.experiment_type`.
  - If `"io"`: Bypass the standard line generation. Extract the X and Y arrays from `dfoutput` (excluding aggregate rows where `sweep=NaN`) based on the active `io_input` and `io_output` mappings. Create a scatterplot using `ax.scatter(x, y)` and store the `PathCollection` artist.
  - **Binning Verification**: Ensure that if the recording data is binned (e.g., `p_row["bin_size"]` is valid), the plotting logic uses the appropriately binned outputs for both X and Y axes instead of the raw unbinned sweeps.
  - If not `"io"`: Proceed with the normal `sweep` and `stim` mode line generation.
- **Axis Targeting**: Determine whether to plot this on `ax1` or `ax2` (or monopolize `ax1` and hide `ax2`) based on standard I-O visual practices.

## 3. Toggling Mode (`ui.py`)

- **`experiment_type_changed`**: When the user switches into or out of "I-O" mode, the UI should forcibly purge the graphs and rebuild them.
- Call `uiplot.unPlot()` to clear all current artists from memory and the canvas, followed by `self.graphUpdate()` to trigger a fresh `addRow` sequence under the new mode's rules.

## 4. Axes & Auto-Scaling (`ui_state_classes.py`)

- **X-Axis Scaling (`x_axis_xlim`)**: When `experiment_type == "io"`, the X-axis must scale dynamically based on the minimum and maximum values of the selected _Input_ column across active recordings, rather than sweep counts or time.
- **X-Axis Labels (`x_axis_xlabel`)**: The X-axis label must dynamically change to reflect the active input (e.g., "Volley Amplitude" or "Volley Slope").

## 5. Interactivity (`ui.py`)

- **Disable Mouseover**: For the initial implementation, hovering over the output graph in I-O mode will do nothing.
- In `outputMouseover`, add an early return: `if uistate.experiment_type == "io": return`. This safely bypasses the distance calculation and prevents crashes without needing to immediately build Euclidean 2D snapping.

## 6. Data Groups in I-O Mode

When recordings are assigned to groups, `ui_plot.py -> addGroup` calculates cross-recording means and plots them with SEM shading. In I-O mode, a traditional time-series mean line is conceptually invalid.

- **Group Visuals**: We must define how a group is represented in I-O mode. Standard biological approaches include:
  1. A linear regression line (line of best fit) calculated across the pooled scatter points of all recordings in the group.
  2. Binned centroids (Mean X, Mean Y) with SEM error bars spanning both the X and Y axes.
- **Implementation**: In `addGroup`, add branching logic (`if uistate.experiment_type == "io":`). Bypass the standard `plot_group_lines` call. Extract the combined X and Y data for the group, calculate the regression or centroids, and plot the resulting artist(s). Store them under a unique `x_mode="io"` tag in `uistate.dict_group_labels`.

## Identified Gaps (Post-Implementation Review)

Since initial implementation began, the following gaps in the original plan have been identified and must be addressed:

1. **Normalization Handling (`variant="norm"`)**: The data mapping strictly points `EPSPamp` to `EPSP_amp`. However, if the user toggles the "Relative" (Norm) checkbox in the Y-scaling tool, the plotting engine must dynamically map the Y-axis to `EPSP_amp_norm` (and potentially normalize the X-axis input as well, depending on the required scientific convention).
2. **Axis Targeting & Aspect Visibility**: The plan deferred the decision on whether to use `ax1` or `ax2`. In the initial pass, it was hardcoded to `ax1`. This causes conflicts if the user toggles the "Aspect" checkboxes (e.g., hiding `EPSP_amp` while trying to view a Volley vs. Slope I-O curve). The logic must map the I-O scatter to the correct logical axis (`ax1` for amps, `ax2` for slopes) and ensure `_is_rec_visible` respects the correct aspect.
3. **Y-Axis Auto-scaling (`_ylim_from_artists`)**: While X-axis auto-scaling was addressed, `_ylim_from_artists` natively expects `Line2D` objects. It must be verified and potentially updated to correctly read bounding boxes or Y-data from `PathCollection` (scatter) offsets to ensure the dots don't clip off the top or bottom of the screen.
