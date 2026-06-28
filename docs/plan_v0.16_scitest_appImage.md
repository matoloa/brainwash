# Plan v0.16: AppImage `bw_cfg.yaml` Fix (Config File Location)

## Problem Summary

When running as a Linux AppImage, Brainwash crashes or fails to persist settings because `bw_cfg.yaml` is placed inside the read-only squashfs image (next to the frozen executable or discovered via `sys.path`).

The AppImage runtime extracts the payload to a temporary mount; any write to that location is either impossible or ephemeral.

- Normal desktop use / dev → next to `pyproject.toml` or source tree.
- Portable / self-contained mode → `<AppImageName>.AppImage.config/bw_cfg.yaml` (sibling dir next to the `.AppImage`).
- Standard desktop → `~/.config/brainwash/bw_cfg.yaml` (or `$XDG_CONFIG_HOME`).

## Root Cause Location

- `src/lib/ui.py:Config.__init__` (lines ~94-142) — `_find_file("bw_cfg.yaml")` + fallback always resolves inside squashfs for frozen builds. `self.dev_mode` / `getattr(sys, "frozen", False)` is detected but not used for writable config path.
- `src/lib/ui_project.py:ProjectMixin.get_bw_cfg` / `write_bw_cfg` (lines 200-239) — blindly uses `config.bw_cfg_yaml` (string) for `Path.open("w+")` with no parent `mkdir` or frozen awareness.
- Build: `build_with_cxfreeze_multiarch_setup.py` copies only `pyproject.toml` (readonly); no config handling.

## Goal

Make `bw_cfg.yaml` (darkmode, projects_folder, last project, etc.) **writable and persistent** for AppImage users. Preserve **exact** current behavior for `python -m brainwash`, normal installs, and non-frozen runs. Single source of truth in `Config`.

## Required Changes (Optimized for Agentic Implementation)

### 1. `src/lib/ui.py` — `Config` class (centralize location logic, ~35 LOC)

**Update `Config.__init__` and `_find_file` (now clearly readonly-only for `pyproject.toml` + initial lookup).**

After the existing `_find_file("bw_cfg.yaml")` block and fallback (around lines 129-136, after `logger.debug("Config: bw_cfg.yaml found at...")`), **replace the bwcfg_path assignment** with frozen-aware logic that sets the _final writable_ path:

```python
# After toml_path resolution and initial bwcfg_path lookup (~lines 124-136)
if getattr(sys, "frozen", False):
    # Frozen/AppImage: NEVER write inside squashfs. Priority:
    # 1. Portable sibling: MyApp.AppImage.config/ (standard, AppImage runtime respects for XDG)
    # 2. XDG: ~/.config/brainwash/ (or $XDG_CONFIG_HOME/brainwash/)
    appimage_exe = Path(sys.executable)
    portable_dir = appimage_exe.with_name(appimage_exe.name + ".config")
    if portable_dir.is_dir():
        cfg_dir = portable_dir
        logger.info("Config: using portable .config sibling: %s", cfg_dir)
    else:
        xdg_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        cfg_dir = xdg_base / self.program_name.lower()  # "brainwash"
        logger.info("Config: using XDG config dir (will create on write): %s", cfg_dir)
    bwcfg_path = cfg_dir / "bw_cfg.yaml"
    logger.debug("Config: frozen – final writable bw_cfg_yaml=%s", bwcfg_path)
# else: dev/normal keeps existing _find_file / toml_path.parent fallback (unchanged)

self.bw_cfg_yaml = str(bwcfg_path)  # remains str for ui_project.py compatibility
```

**Additional updates**:

- Rename or heavily document `_find_file` (lines ~101-122) → clarify it is **readonly-only** for `pyproject.toml` (version) and initial `bw_cfg.yaml` probe. Update leading docstring (lines ~94-100) with new 4-step search order.
- Ensure `logger.info` (not debug) for user-visible path on first frozen run.
- No change to `self.dev_mode`, `program_name`, `version`, or `pyproject.toml` loading.

This makes `Config` the **single source of truth** (agent-friendly: all priorities in one method).

### 2. `src/lib/ui_project.py` — `ProjectMixin.write_bw_cfg` (robust writes, ~10 LOC)

**Add directory creation + improved logging (keep `self.bw_cfg_yaml` as Path where possible).**

Update `write_bw_cfg` (lines 226-239):

```python
def write_bw_cfg(self):  # Save global program settings
    if config.transient or self.bw_cfg_yaml is None:
        return
    cfg = { ... }  # unchanged
    path = Path(self.bw_cfg_yaml)  # ensure Path
    path.parent.mkdir(parents=True, exist_ok=True)  # critical for XDG/portable first-run
    with path.open("w+") as file:
        yaml.safe_dump(cfg, file)
    logger.info("Wrote bw_cfg.yaml → %s (darkmode=%s, projects_folder=%s)",
                path, cfg.get("darkmode"), cfg.get("projects_folder"))
```

- Update method and class docstrings (top of file + line 86) to reference new `Config` policy.
- `get_bw_cfg` (lines 200-224): **No functional change**. It already handles missing files by setting defaults and assigns `self.bw_cfg_yaml = Path(config.bw_cfg_yaml)`. New path from `Config` makes it writable.
- Minor: Prefer `Path` internally for `self.bw_cfg_yaml` (string remains on `config`).

### 3. Documentation & Build (docs only)

- **Update `docs/build.md`** (add "**AppImage Configuration (v0.16+)**" section):
  - Document supported locations, how to enable portable mode (create `.config` sibling), default XDG behavior.
  - Reference the build command.
- **Update `.github/workflows/build_linux_appimage.yml`** (comments only): Note config expectations post-v0.16.
- Update this plan file with the refined version above.
- No changes to `build_with_cxfreeze_multiarch_setup.py`, `.desktop`, or icons.

### 4. Testing Checklist (agent-verifiable)

Use after implementation (run via terminal or `/check-work`):

1. Dev: `cd src; python -m brainwash` → `bw_cfg.yaml` still next to source/`pyproject.toml` (unchanged). Toggle darkmode → persists.
2. Build: `cd src; uv run python build_with_cxfreeze_multiarch_setup.py bdist_appimage`.
3. Run AppImage (e.g. from `~/Applications/`): On first close/darkmode toggle, confirm `~/.config/brainwash/bw_cfg.yaml` created. Restart → settings survive.
4. Portable: `mkdir <AppImage>.config`; restart → uses sibling dir (ignores `~/.config`); log confirms path.
5. Edges: `XDG_CONFIG_HOME` override, `transient=True`, missing parents (mkdir succeeds), old in-image config (migrates gracefully to defaults).
6. Verify logs show correct INFO paths. Check no writes inside AppImage mount.

## Migration / Backwards Compatibility

- Old in-squashfs `bw_cfg.yaml` (pre-v0.16 AppImages) is ignored; first launch creates new XDG/portable file with defaults. Acceptable (UI prefs + last project only).
- No impact on per-project `cfg.pkl`, `project.brainwash`, or data files.
- Existing `~/.config` users unaffected.

## References

- `src/lib/ui.py:Config.__init__` (frozen detection, `_find_file`, `bw_cfg_yaml`).
- `src/lib/ui_project.py:ProjectMixin.get_bw_cfg`, `write_bw_cfg`, `bootstrap`.
- `build_with_cxfreeze_multiarch_setup.py:38` (pyproject.toml copy).
- `docs/build.md`, GitHub workflow.
- Original plan attached for context.

**Why Actionable for Agents**: Single source of truth in `Config`, minimal changes (localized methods), explicit code snippets with line numbers, clear test commands, no new abstractions, defensive `mkdir`/logging. Ready for precise `search_replace` + verification. Do not implement yet.
