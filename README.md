## Brainwash is a software for analysing electrophysiological field recordings
Brainwash is developed for field-recordings in CA1, but also works in DG and SLM.
The program attempts to find events, such as fEPSP and fvolley amplitudes and slopes.
It visualises the data, and provides tools for correcting these events.
Output is stored as .csv-files for compatibility.

### Contact
Mats Andersson (mats.olof.andersson@gu.se). We're happy to receive feedback and suggestions, or to discuss collaborations.



### Windows builds
This requires a development version of cx_freeze:
pip install --upgrade --pre --extra-index-url https://marcelotduarte.github.io/packages/ cx_Freeze
Build from src folder [SIC]; there's a copy of pyproject.toml in there for that purpose
Build syntax: python setup.py build_exe
