# Brainwash is a software for analysing electrophysiological field recordings
Brainwash is developed for field-recordings in CA1, but also works in DG and SLM.
The program attempts to find events, such as fEPSP and fvolley amplitudes and slopes.
It visualises the data, and provides tools for correcting these events.
Output is stored as .csv-files for compatibility.

## Contact
Mats Andersson (mats.olof.andersson@gu.se). We're happy to receive feedback and suggestions, or to discuss collaborations.

# Installation
Provided files in "release"
* Linux - Appimage, tested for ubuntu compatibility
* Windows - installer

## Build: github
There is automated workflows to build on github with ubuntu 22.04 and windows

## Build: manual distribution builds
se also specific build document in docs.
Build from src folder [SIC], this is needed as cxfreeze does not handle our repo structure gracefully. When it does, it should be from repo root.

### Linux AppImage
./build-appimage.sh

### Windows
> python setup.py build_exe --silent-level 2
Then zip the folder and distribute.
