# PR-12: Remaining mixin instance injection (batch)

**Status**: DONE | **Depends on**: PR-11

## Goal

Remove all remaining module-level `uistate` / `config` / `uiplot` injection. Every mixin and `UIsub` method uses `self.uistate`, `self.config`, `self.uiplot`.

## Scope (one PR)

- `ui_graph`, `ui_parse`, `ui_project`, `ui_groups`, `ui_table`, `ui_sweep_ops`, `ui_interactive`, `ui_menus`, `export_data`
- `ui.py` UIsub methods + delete mixin wiring block
- `ui_widgets` threads: `ParseDataThread` uses `self.uisub.uistate`; direct imports for `confirm`, `CustomCheckBox`, `InputDialogPopup`

## Verify

```sh
uv run pytest src/lib/ -q
```

## Next

→ UIplot model/view split (evaluation Tier B4) or further `UIsub` decomposition.