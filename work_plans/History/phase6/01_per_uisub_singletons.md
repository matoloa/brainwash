# Phase 6a: per-UIsub singletons (HIGH RISK)

**Risk**: HIGH — changes object lifetime for `uistate` / `uiplot` / `config`.

## Goal

Stop creating `config`, `uistate`, `UIplot` at `ui.py` import time. Instantiate in `UIsub.__init__` only.

## Before

```python
config = ui_widgets.Config()
uistate = ui_state_classes.UIstate()
uiplot = ui_plot.UIplot(uistate)

class UIsub(...):
    def __init__(self, mainwindow):
        self.uistate = uistate  # shared import-time singleton
```

## After

```python
config = uistate = uiplot = None  # module aliases; set in UIsub.__init__

class UIsub(...):
    def __init__(self, mainwindow):
        global config, uistate, uiplot
        self.config = config = ui_widgets.Config()
        self.uistate = uistate = ui_state_classes.UIstate()
        self.uiplot = uiplot = ui_plot.UIplot(self.uistate)
```

Module aliases kept temporarily for any `import ui; ui.uistate` legacy (6b removes them).

## Rollback

```sh
git revert HEAD   # if commit message contains [HIGH RISK phase6a]
```

## Verify

```sh
uv run pytest src/brainwash/ -q
```