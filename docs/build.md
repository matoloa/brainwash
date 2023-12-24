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
This requires a development version of cx_freeze (v6.16):
pip install --upgrade --pre --extra-index-url https://marcelotduarte.github.io/packages/ cx_Freeze
Build from src folder [SIC], this is needed as cxfreeze does not handle our repo structure cracefully. When it does, it should be from repo root.

### Windows
> python setup.py build_exe --silent-level 2
check you build folder sizes by 
> du -shc ~/miniconda3/* | sort -rh
Then zip the folder and distribute.

### Linux
$ python setup.py bdist_appimage
Results in an appimage, ready for distribution.