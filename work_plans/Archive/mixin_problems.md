# Mixin Problems in Brainwash UI Layer

**Date**: 2026-07-12  
**Context**: Discussion following observation that `src/lib/ui.py` is 5720 lines with a 172-method `UIsub` class, despite prior refactoring.

## Current Approach

The project uses **multiple inheritance with Mixins** to partition behavior out of the main `UIsub` class:

```python
class UIsub(
    ui_designer.Ui_mainWindow,
    ui_groups.GroupMixin,
    ui_sweep_ops.SweepOpsMixin,
    ui_project.ProjectMixin,
    ui_data_frames.DataFrameMixin,
    ui_menus.MenuMixin,
    export_data.ExportMixin,
    ui_interactive.InteractivePlotMixin,
):
```

### Key Implementation Patterns

- **Module-level singleton injection**:
  ```python
  # ui.py (after creating singletons)
  ui_groups.uistate = uistate
  ui_groups.config = config
  ui_groups.uiplot = uiplot
  # ... repeated for each mixin module
  ```

- Each mixin module declares:
  ```python
  uistate = None
  config = None
  uiplot = None
  # (sometimes additional objects like CustomCheckBox, InputDialogPopup)
  ```

- Mixins are **not self-contained**. They assume:
  - A rich host instance (`self`) providing many attributes (`self.dd_groups`, `self.dict_folders`, `self.canvasOutput`, etc.)
  - Methods defined in `UIsub` or *other* mixins (`self.update_show()`, `self.graphRefresh()`, `self.turn_heatmap_off()`, etc.)
  - Direct access to module-level singletons in addition to `self.`

This pattern successfully moved large chunks of code out of `ui.py`, but `UIsub` remains a de-facto god object.

## Major Drawbacks

### 1. Implicit Contracts and Hidden Dependencies
Mixins make strong, undocumented assumptions about the host class and sibling mixins.

**Examples**:
- `GroupMixin.group_new()` calls `self.turn_heatmap_off()`, `self.apply_statistical_test_if_active()`, `self.graphRefresh()`.
- `DataFrameMixin` calls `self.turn_heatmap_off()` and `self.update_show()`.
- `InteractivePlotMixin` assumes `self.canvas*` widgets and mixes module `uistate` with instance attributes.
- `hasattr(self, "...")` guards appear in places because a mixin cannot reliably know what else is mixed in.

There is no explicit interface or "required host capabilities" documentation.

### 2. Module-Level Singleton Injection Is a Hack
The injection pattern is timing-sensitive and uses mutable module globals.

**Problems**:
- Injection must occur in a precise order *after* singletons exist but *before* any `UIsub()` instantiation.
- Creates global mutable state (`uistate = None` at module level, then mutated).
- Fragile under `importlib.reload`, testing, or alternative entry points.
- Some imports are deliberately delayed in `ui.py` just to control injection timing.
- Methods use the injected module globals (`uistate.colors[...]`) mixed with `self.` attributes inconsistently.

This requires the prominent "Mixin wiring" comment block in `ui.py`.

### 3. Multiple Inheritance Complexity
Combining `Ui_mainWindow` + 7+ mixins leads to classic MI issues:

- Name collision risk across mixins.
- `super()` is rarely usable safely.
- Initialization and attribute availability order is implicit.
- `hasattr` workarounds and defensive checks proliferate.

### 4. Poor Discoverability
Even with comments in `ui.py` pointing to mixins ("Data Group handling functions → GroupMixin"), locating behavior is difficult:

- Searching for `self.update_show()` or `self.graphRefresh()` requires checking multiple files.
- The mental model of "what lives where" must be learned and maintained.
- `UIsub` still presents 172 methods at runtime, making `dir()`, `help()`, or introspection overwhelming.

### 5. Testing Is Painful
Isolating a mixin for unit tests requires:
- Constructing a fake host class with the right inheritance + every expected attribute/method.
- Manually performing module-level injections.
- Often pulling in Qt objects or heavy shared state.

Result: almost no isolated testing of UI behavior.

### 6. Does Not Reduce the God Object
At runtime, `UIsub` is still a single massive object that:
- Coordinates everything.
- Owns or directly references nearly all widgets and state.
- Serves as the common bus for cross-cutting calls (groups → graphs → stats → UI updates).

Mixins only partition *source code*, not runtime responsibilities or boundaries.

### 7. High Refactoring and Maintenance Tax
Moving code between mixins or out of `UIsub` requires:
- Updating the inheritance list.
- Updating the injection block.
- Updating documentation comments.
- Risk of breaking implicit dependencies.

Legacy "WIP section: TODO: move to appropriate header" comments remain.

### 8. Degraded Debugging Experience
- Stack traces routinely cross 5–6 files for a single user action.
- Hard to answer "which component is responsible?"
- Monkey-patching or development-time inspection is more confusing than with composition.

## What the Approach Solves Well (for balance)

- Successfully split one monolithic file without a full architectural rewrite.
- Reuses the existing `UIsub` instance as a natural "host" (no parameter explosion).
- Provided a relatively low-risk extraction path during large features (n_unit, formal tests, etc.).
- Consistent with the project's incremental refactoring history.

## Summary

The mixin + module-injection style is primarily a **file-organization technique**, not a robust modular architecture. It trades the problem of "one huge file" for problems of implicit coupling, global state, and a still-monolithic coordinator object.

This explains why `ui.py` continues to feel large and difficult despite previous extraction efforts.

---

*Persisted from discussion on 2026-07-12.*