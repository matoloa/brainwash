## Build applications
* cx_freeze
* nuitka
going with cx_freeze for now as is seems to have advantages with building appimage and more
Nuitka on the other hand has an option of "hinted" packaging that can avoid partial modules that are unused and slim the build.
cx_freeze can do this by manual tuning

## Slimming the build
* there is now a tool in folder tools to check what is actually running.
* manually tune what is being included in the build
* avoid intels MKL, use openblas. MKL is huge and comes with only minor performance improvement (maybe).  Conda forge for linux seems to go openblas by default. Check windows, mkl is in windows and eats 750 MB in the build. Switch to openblas by: "mamba install "blas=*=openblas", figure out a way for this to be done on env creation. WARNING: some forums from 2019 indicated that windows scipy was only compatible with mkl, but that was 4 years ago.

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

There's a GitHub Action in .github/workflows/build_linux_appimage.yml to automate this.