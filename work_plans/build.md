## Build applications

- cx_freeze
- nuitka
  going with cx_freeze for now as is seems to have advantages with building appimage and more
  Nuitka on the other hand has an option of "hinted" packaging that can avoid partial modules that are unused and slim the build.
  cx_freeze can do this by manual tuning

## Slimming the build

- there is now a tool in folder tools to check what is actually running.
- manually tune what is being included in the build
- avoid intels MKL, use openblas. MKL is huge and comes with only minor performance improvement (maybe). Conda forge for linux seems to go openblas by default. Check windows, mkl is in windows and eats 750 MB in the build. Switch to openblas by: "mamba install "blas=\*=openblas", figure out a way for this to be done on env creation. WARNING: some forums from 2019 indicated that windows scipy was only compatible with mkl, but that was 4 years ago.

## Distribution builds

Note: cx_Freeze==8.2.0 is included in requirements.txt. Install via `pip install -r ../requirements.txt`.
Build from the src/ folder using build_with_cxfreeze_multiarch_setup.py, as cx_Freeze does not handle our repo structure gracefully.

### Windows

From the src/ folder, run:

```
python build_with_cxfreeze_multiarch_setup.py build_exe > cxbuild_exe.log
```

This creates dist/brainwash.exe with all libraries and dependencies -- a fully portable Windows application.

Zip the entire dist/ folder as brainwash-{version}-windows.zip for distribution.

To check folder sizes (on Windows):

```
powershell "Get-ChildItem -Recurse dist | Measure-Object -Property Length -Sum"
```

### Linux

From the src/ folder, run:

```
python build_with_cxfreeze_multiarch_setup.py bdist_appimage > cxbuild_appimage.log
```

Results in dist/brainwash-{version}-x86_64.AppImage, ready for distribution.

### AppImage Configuration (v0.16+)

`bw_cfg.yaml` (darkmode, projects_folder, last project, etc.) is now **writable and persistent**:

- **Default (XDG)**: `~/.config/brainwash/bw_cfg.yaml` (or `$XDG_CONFIG_HOME/brainwash/bw_cfg.yaml`). Created automatically on first settings change / close.
- **Portable / self-contained**: Create a sibling directory next to the `.AppImage` named `<AppImageName>.config/` (e.g. `brainwash-0.16.0-x86_64.AppImage.config/`). The app will prefer this (if the dir exists) and ignore `~/.config`.
- **Dev / normal install / Python run**: Unchanged — next to `pyproject.toml` or in source tree.

See `src/lib/ui.py:Config.__init__` (frozen logic + \_find_file doc) and `src/lib/ui_project.py:write_bw_cfg` (mkdir(parents=True) + INFO logging). Old in-squashfs configs are ignored (graceful migration to defaults).

There's a GitHub Action in .github/workflows/build_linux_appimage.yml to automate this.
