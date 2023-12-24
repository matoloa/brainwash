# Brainwash is a software for analysing electrophysiological field recordings
Brainwash is developed for field-recordings in CA1, but also works in DG and SLM.
The program attempts to find events, such as fEPSP and fvolley amplitudes and slopes.
It visualises the data, and provides tools for correcting these events.
Output is stored as .csv-files for compatibility.

## Contact
Mats Andersson (mats.olof.andersson@gu.se). We're happy to receive feedback and suggestions, or to discuss collaborations.



## Distribution builds
se also specific build document in docs.
This requires a development version of cx_freeze (v6.16):
pip install --upgrade --pre --extra-index-url https://marcelotduarte.github.io/packages/ cx_Freeze
Build from src folder [SIC], this is needed as cxfreeze does not handle our repo structure cracefully. When it does, it should be from repo root.

### Windows
> python setup.py build_exe --silent-level 2
Then zip the folder and distribute.

### Linux
$ python setup.py bdist_appimage
Results in an appimage, ready for distribution.