# UI Plot Debug Plan

The following issues were found in `ui.py` and `ui_plot.py` and require attention:

### 1. The Matplotlib Scatterplot Blindness (Zooming)

- **The Bug:** `ui_plot.py`'s `_xlim_from_artists` and `_ylim_from_artists` natively search for `Line2D` objects using `.get_xdata()`. Scatterplots (`ax.scatter`) create `PathCollection` objects.
- **The Gotcha:** The auto-zoomer will be completely blind to your I-O scatterplot and default to a `[0, 1]` zoom scale. You **must** add `isinstance(coll, mcoll.PathCollection)` to the zoomer and extract the points using `coll.get_offsets()`. Furthermore, scatter plots use `get_offset_transform()` rather than `get_transform()`, so standard axis-validation checks will skip them.
- **Status:** Resolved. `PathCollection` point extraction is implemented (`get_offsets()`), and the `coll.get_offset_transform() != axis.transData` check has been added.

### 2. The Missing Blob / NaN Desync

- **The Bug:** If your data contains invalid measurements (e.g., `NaN` in a specific bin), `ax.scatter` silently skips drawing that dot.
- **The Gotcha:** If you have 9 sweeps but 1 is `NaN`, Matplotlib only draws 8 blobs. If your mouseover logic uses array indexing to find the nearest point, hovering over the 6th blob will accidentally fetch the 7th sweep's data. You **must** run `df.dropna(subset=[x_col, y_col])` _before_ mapping your hover distances to your dataframe sweeps.
- **Status:** Already perfectly implemented in `ui.py`'s `outputMouseover` (`df_sweeps = df_sweeps.dropna(subset=[x_col, y_col])`).

### 3. Euclidean Mouseover Distance

- **The Bug:** The existing `outputMouseover` uses `np.abs(x_data - x).argmin()` to find the nearest sweep.
- **The Gotcha:** In a scatterplot, sweeps are no longer evenly spaced along the X-axis. You **must** calculate the 2D Euclidean distance to the mouse cursor `((dx)**2 + (dy)**2)` to snap to the correct blob. Because X and Y axes have wildly different scales (e.g., 0-1 vs 0-100), you must divide `dx` and `dy` by the axis ranges (`ax.get_xlim()` / `ax.get_ylim()`) before calculating the distance, otherwise the hover targeting will be heavily squashed/skewed.
- **Status:** Already successfully implemented in `ui.py`'s `outputMouseover`.

### 4. Binned Amplitude Crosses (Event Graph)

- **The Bug:** The visual cross drawn on `axe` uses `out["EPSP_amp"].mean()` as a fallback when calculating its Y-height.
- **The Gotcha:** If the data is binned, `.mean()` averages the bins, which is mathematically different from the raw `dfmean` trace on the screen. The cross will float above or below the line. You must specifically query the stim aggregate row (`out[out["sweep"].isna()]`) or physically slice `dfmean` to get the true height.
- **Status:** The visual cross fallback for `EPSP_amp` in `ui_plot.py` is correctly slicing `df_event` instead of taking the binned mean.

### 5. Pandas `pd.NA` Ambiguity (`editBinSize` crash)

- **The Bug:** In `ui.py`, comparing missing nullable pandas types using standard Python operators (e.g. `math.isnan(derived) and pd.isna(old) and old != derived`) throws `TypeError: boolean value of NA is ambiguous`.
- **The Gotcha:** You must strictly use `pd.isna()` for both sides of the comparison before attempting an `!=` evaluation.
- **Status:** `editBinSize` in `ui.py` already implements the strict `pd.isna()` comparisons.
