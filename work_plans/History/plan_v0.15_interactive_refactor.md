# Plan: v0.015 Interactive Plot Refactoring

This document outlines the architecture and step-by-step plan to refactor `ui_interactive.py`. The goal is to eliminate "God functions" (like `outputMouseover` and `eventDragUpdate`) by utilizing the Strategy Pattern. We will introduce a `mouseover_loader` that evaluates the current UI state once and delegates execution to lean, highly specialized functions.

## Final Intended Architecture (Tree Structure)

```text
InteractivePlotMixin
│
├── Loaders & Dispatchers (State Evaluation)
│   ├── mouseover_loader()          - Evaluates uistate (IO, PP, Time, Stim) and returns the correct mouseover callback.
│   ├── drag_update_loader()        - Evaluates uistate and returns the correct drag-update callback.
│   ├── drag_release_loader()       - Evaluates uistate and returns the correct drag-release callback.
│   └── outputMouseover(event)      - The main MPL event hook. Calls `loader()(event)` to dispatch.
│
├── Specialized Mouseover Strategies (Output Graph)
│   ├── _mouseover_output_time()    - Mouseover logic specifically for Time-based x-axis.
│   ├── _mouseover_output_pp()      - Mouseover logic specifically for Paired-Pulse (PP) mode.
│   ├── _mouseover_output_io()      - Mouseover logic specifically for Input-Output (IO) mode.
│   └── _mouseover_output_stim()    - Mouseover logic specifically for Stim-based x-axis.
│
├── Specialized Drag Strategies (Event Graph)
│   ├── _drag_update_time()         - Real-time dragging logic for Time/Stim modes.
│   ├── _drag_update_pp()           - Real-time dragging logic for Paired-Pulse mode.
│   ├── _drag_update_io()           - Real-time dragging logic for Input-Output mode.
│   ├── _drag_release_time()        - Drag commit/release logic for Time/Stim modes.
│   ├── _drag_release_pp()          - Drag commit/release logic for PP mode.
│   └── _drag_release_io()          - Drag commit/release logic for IO mode.
│
├── Existing Unchanged/Simplified Core Events
│   ├── graphClicked()              - Evaluates clicks and initiates drag states.
│   ├── meanMouseover()             - Top-graph hover logic (already isolated).
│   ├── eventMouseover()            - Middle-graph hover logic (already isolated).
│   └── zoomOnScroll()              - Canvas scrolling logic.
│
└── Shared Pure Helpers (DRY Abstractions)
    ├── _get_nearest_point()        - Math: Calculates Euclidean distance to find the closest scatter/line point.
    ├── _draw_ghost_sweep()         - Drawing: Renders the grey background preview trace.
    ├── _draw_mouseover_blob()      - Drawing: Renders the colored scatter dot on hover.
    ├── _update_marker_data()       - Math/Drawing: Unified logic replacing the 4 redundant loops in `mouseoverUpdateMarkers`.
    └── exorcise()                  - Cleanup: Removes ghost sweeps and blobs.
```

---

## Implementation Steps

### Phase 1: Abstract Math and Drawing into Helpers
1. **Create `_get_nearest_point(x, y, x_array, y_array, x_range, y_range)`**: Extract the Euclidean distance formula out of `outputMouseover`.
2. **Create `_draw_ghost_sweep(self, snippet_x, snippet_y, label_text)`**: Extract the matplotlib line/text updating logic for the background sweep preview.
3. **Create `_draw_mouseover_blob(self, ax, x, y, color)`**: Extract the matplotlib scatter updating logic for the hover dots.
4. **Refactor `mouseoverUpdateMarkers` into `_update_marker_data`**: Collapse the four almost identical loops (`EPSP_slope`, `EPSP_amp`, `volley_slope`, `volley_amp`) into a single loop parameterized by the aspect string.

### Phase 2: Build the Specialized Strategies
1. **Output Mouseovers**: Split `outputMouseover` into `_mouseover_output_time`, `_mouseover_output_pp`, `_mouseover_output_io`, and `_mouseover_output_stim`. 
    * Strip out all the `if is_io` and `if is_pp` checks. Assume the mode is known.
    * Utilize the new helper functions for math and drawing.
2. **Drag Updates**: Split `eventDragUpdate` into `_drag_update_time`, `_drag_update_pp`, and `_drag_update_io`.
    * Remove the complex branching regarding norm handling, PPR calculations, and IO axes.
3. **Drag Releases**: Split `eventDragReleased` into `_drag_release_time`, `_drag_release_pp`, and `_drag_release_io`.
    * Isolate the dfoutput rewriting logic so it doesn't have to handle conflicting conditions.

### Phase 3: Implement the Loaders (Dispatchers)
1. **Create `mouseover_loader(self)`**:
    * Check `getattr(uistate, "experiment_type", "time")`.
    * If `io`, return `self._mouseover_output_io`.
    * If `PP`, return `self._mouseover_output_pp`.
    * If `uistate.x_axis == "stim"`, return `self._mouseover_output_stim`.
    * Else, return `self._mouseover_output_time`.
2. **Implement Loaders for Dragging**: Create `drag_update_loader` and `drag_release_loader` utilizing the exact same logic.

### Phase 4: Wire the API
1. Modify `outputMouseover(self, event)` to simply be:
   ```python
   def outputMouseover(self, event):
       handler = self.mouseover_loader()
       if handler:
           handler(event)
   ```
2. Modify `eventDragUpdate` and `eventDragReleased` to follow the same dynamic delegation pattern.

### Phase 5: Verification & Cleanup
1. Test switching between Time, Stim, PP, and IO views to ensure the loaders correctly pivot the active strategies.
2. Ensure ghost sweeps still clean up (`exorcise()`) when leaving the axes.
3. Verify that drag-and-drop marker persistence writes correctly to the dataframes in all experiment modes.
