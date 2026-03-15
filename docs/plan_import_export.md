# Brainwash — Import / Export & Publishable Image Plan

---

## Background

Brainwash already has skeletal scaffolding for import/export:

- `parse.py` has a `parse_csv` stub (L189–195) that reads a CSV and returns a DataFrame, but it has no column validation, version detection, or integration with the full `source2dfs` pipeline.
- `ui_export.py` (ExportMixin) has trigger methods for every export action, but all are `pass` / `TODO`.
- `ui_menus.py` (MenuMixin) has the Export menu fully wired up: Copy section, Sweeps section (CSV, XLS, IBW), Output section (CSV, XLS), and an Image section.
- The internal data model is now parquet-backed (`data/<rec>.parquet`, `cache/<rec>_output.parquet`), but the legacy data layer used CSV everywhere — both for raw sweep data and for computed output.

The work in this plan fills in all the `TODO: implement` stubs and adds the publishable-image workflow end-to-end.

---

## Data model recap (for context)

| What | Current on-disk format | Human-readable equivalent |
|---|---|---|
| Raw sweep data | `data/<rec>.parquet` | columns: `sweep`, `time`, `voltage_raw`, `t0`, `datetime` |
| Filtered/mean sweep | `cache/<rec>_mean.csv`, `cache/<rec>_filter.csv` (legacy) | same schema |
| Output (per-sweep events) | `cache/<rec>_output.parquet` | columns: `stim`, `sweep`, `EPSP_slope`, `EPSP_slope_norm`, `EPSP_amp`, `EPSP_amp_norm`, `volley_amp`, `volley_slope` |
| Output (binned) | `cache/<rec>_output_bin.parquet` | same columns, `sweep` = bin index |
| Project registry | `<project>.bwp` (YAML) | `df_project` rows: one per recording |

---

## Phase 1 — CSV Import from previous Brainwash versions

### Background

Previous versions of Brainwash wrote raw sweep data as CSV with columns matching the current `data/<rec>.parquet` schema (`sweep`, `time`, `voltage_raw`, and optionally `t0`, `datetime`). `parse_csv` in `parse.py` currently just calls `pd.read_csv` and returns — it does no validation and returns a plain DataFrame rather than the `{channel: DataFrame}` dict that `source2dfs` callers expect.

Git history confirms that `voltage_raw` has been the column name in all CSV-writing code throughout the entire history of the project. The bare `voltage` column name only ever appeared in derived/computed intermediates (`dfmean`, `dffilter`), never in the raw data CSVs written by `persistdf`. There are therefore no data files in the wild with a legacy `voltage` column — only `voltage_raw`.

Only raw sweep data CSVs need to be supported for import. Output CSVs (per-sweep event tables from old `persistOutput`) are out of scope.

### Step 1.1 — Define a BW CSV version schema

Add a module-level constant in `parse.py`:

```python
# Minimum required columns for a Brainwash raw sweep CSV.
_BW_CSV_SWEEP_COLS = {"sweep", "time", "voltage_raw"}
```

Add a helper `detect_bw_csv_type(df) -> str | None` that returns `"sweep"` if `_BW_CSV_SWEEP_COLS` is a subset of `df.columns`, or `None` (unknown/unsupported).

Use a **subset check** (`_BW_CSV_SWEEP_COLS.issubset(df.columns)`) rather than exact equality so that files with additional columns (e.g. extra annotation columns) are still accepted.

### Step 1.2 — Upgrade `parse_csv`

Replace the current three-line body of `parse_csv` with:

1. Read with `pd.read_csv(source_path)`.
2. Call `detect_bw_csv_type(df)`.
3. **If `"sweep"`**: validate columns, add missing optional columns (`t0`, `datetime`) as `pd.NaT` / `None` so downstream code does not crash. Return a `{0: df}` dict (channel 0), matching `parse_ibwFolder` / `parse_abfFolder` conventions. The caller (`source2dfs`) will then run the normal sweep-numbering cleanup via the existing `"sweep" in df.columns` fast-path.
4. **If `None`**: raise `ValueError` with a message listing the required columns (`_BW_CSV_SWEEP_COLS`).

### Step 1.3 — Folder of CSVs

`source2dfs` already handles folder inputs for ABF and IBW. Extend the folder branch:

```python
if csv_files:
    # Previously raised ValueError — now supported.
    df = parse_csvFolder(path)
```

Add `parse_csvFolder(folder_path)` to `parse.py`:
- Validate that all CSVs pass `detect_bw_csv_type` as `"sweep"`. If any file fails, raise `ValueError` with a clear message identifying the offending file.
- Treat each file as one recording (one channel per file), stack them into a `{stem: df}` dict.

### Step 1.4 — UI wiring for CSV import

`triggerAddData` already opens a file dialog. Add `*.csv` to the filter string. No other UI changes are needed.

---

## Phase 1b — ATF Import

### Background

ATF (Axon Text Format) is a tab-delimited text format produced by pCLAMP and older Axon software. It is structurally similar to ABF in that it contains multi-channel, multi-sweep voltage traces with a time axis, but it is human-readable ASCII. `pyabf` includes an `ATF` class that reads ATF files and exposes the same sweep-oriented interface as `pyabf.ABF` (`setSweep()`, `sweepX`, `sweepY`, `sweepCount`, `channelCount`, `dataRate`, `sweepLengthSec`, `channelList`). No new dependencies are required.

The wiring mirrors the ABF mechanism exactly: `parse_atf` → `parse_atfFolder` → `source2dfs` dispatch.

### Step 1b.1 — Add `parse_atf(filepath)`

Add to `parse.py`, alongside `parse_abf`. Use `pyabf.ATF` as the backend — the same pattern as `parse_abf` uses `pyabf.ABF`:

```python
def parse_atf(filepath):
    """
    Read a single Axon Text Format (.atf) file using pyabf.ATF.
    Returns a raw DataFrame with columns: time, voltage_raw, channel, t0, datetime.
    """
    atf = pyabf.ATF(filepath)
    channels = atf.channelList
    dfs = []
    for ch in channels:
        sweep_dfs = []
        for sweep in atf.sweepList:
            atf.setSweep(sweep, channel=ch)
            df_sweep = pd.DataFrame({
                "time": atf.sweepX.astype(np.float64),
                "voltage_raw": atf.sweepY.astype(np.float64) / 1000,  # mV → V
                "channel": ch,
                "t0": np.nan,
                "datetime": pd.NaT,
            })
            sweep_dfs.append(df_sweep)
        dfs.append(pd.concat(sweep_dfs))
    return pd.concat(dfs).reset_index(drop=True)
```

> **Note:** ATF files do not embed an absolute timestamp, so `t0` and `datetime` are left as `NaN`/`NaT`. `pyabf.ATF` exposes `sweepX` starting from 0 for each sweep, so the sweep-splitting logic in `source2dfs` (detecting `time == 0` resets) works correctly without any special handling.

### Step 1b.2 — Add `parse_atfFolder(folderpath)`

Mirror `parse_abfFolder` exactly:

```python
def parse_atfFolder(folderpath, dev=False):
    """
    Read, sort (by filename) and concatenate all .atf files in folderpath.
    """
    list_files = sorted([f for f in os.listdir(folderpath) if f.lower().endswith(".atf")])
    listdf = []
    for filename in list_files:
        df = parse_atf(Path(folderpath) / filename)
        listdf.append(df)
    df = pd.concat(listdf).reset_index(drop=True)
    return df
```

### Step 1b.3 — Wire into `source2dfs`

In the folder-dispatch block, add ATF detection alongside `abf_files` and `ibw_files`:

```python
atf_files = [f for f in files if f.suffix.lstrip(".").lower() == "atf"]
print(f" - - {len(atf_files)} atf files ...")
...
elif atf_files:
    df = parse_atfFolder(path)
```

In the single-file dispatch block:

```python
elif filetype == "atf":
    df = parse_atf(source)
```

### Step 1b.4 — `sample_atf` metadata helper

Add a lightweight `sample_atf(filepath)` alongside `sample_abf`, returning the same `dict_metadata` shape. Because `pyabf.ATF` already exposes all the needed attributes, this is a direct mirror of `sample_abf`:

```python
def sample_atf(filepath):
    """
    Extracts channelCount, sweepCount and sweep duration from an .atf file.
    """
    atf = pyabf.ATF(filepath, loadData=False)
    dict_metadata = {
        "channel_count": atf.channelCount,
        "sweep_count": atf.sweepCount,
        "sample_rate": atf.dataRate,
        "sweep_duration": atf.sweepLengthSec,
    }
    return dict_metadata
```

> **Note:** `loadData=False` was originally intended as a fast header-only probe, but `dataRate` and `sweepLengthSec` are only populated after the data array is parsed — they are absent in header-only mode. ATF files are small ASCII text, so a full load (`loadData=True`, the default) is inexpensive and is what the implementation uses.

### Step 1b.5 — UI wiring

`triggerAddData` uses `Filetreesub`, a file-tree widget rather than a filter-string dialog, so no filter string needs updating. No UI changes are needed — `source2dfs` handles dispatch automatically once the ATF parsers are wired in.

---

## Phase 2 — Export to .csv

Implements four menu commands in `ui_export.py` (wired in `ui_menus.py`):

- **Export menu → Sweeps section:** `triggerExportSweepsCsv`
- **Export menu → Output section:** `triggerExportOutputCsv`

"Sweeps" means the raw electrophysiology data files (the `data/<rec>.parquet` content). "Output" means the computed per-sweep analysis results (the `cache/<rec>_output.parquet` content). Filters, means, and other cached derivatives are not exported here.

Exported data is written to an Export directory (might have to be created) in the project directory: 'Brainwash Projects', same file name but with `.csv` extension instead of `.parquet`.

### Step 2.1 — Sweep CSV export (`triggerExportSweepsCsv`)

Exports raw sweep data (voltage trace + time axis) for the selected recording(s).

1. Determine the selected recording(s) from `uistate`.
2. Write each recording's sweep data to a recording-specific CSV file with `index=False`.

The exported columns are those of the raw data parquet schema: `sweep`, `time`, `voltage_raw`, `t0`, `datetime`.

### Step 2.2 — Output CSV export (`triggerExportOutputCsv`)

Exports computed analysis output for the selected recording(s).

1. Load output data for each selected recording.
2. Write each recording's output data to a recording-specific CSV file with `index=False`.

Column order matches the output parquet schema: `stim`, `sweep`, `EPSP_slope`, `EPSP_slope_norm`, `EPSP_amp`, `EPSP_amp_norm`, `volley_amp`, `volley_slope`.

---

## CANCELLED Phase 3 — Export to .ibw (Igor Binary Wave)
Discontinued: Igor2 cannot write IBW files natively.

---

## Phase 4 — Publishable Image Export

### Background

The UI currently has four matplotlib axes:
- `ax1` — Output: amplitude (EPSP_amp or EPSP_amp_norm vs. x-axis).
- `ax2` — Output: slope (EPSP_slope or EPSP_slope_norm vs. x-axis).

The goal is to produce a standalone, publication-quality figure from ax1 and ax2 of selected groups. NOT recordings. The key requirement is **decoupling the export figure from the interactive UI figure** — the exported figure must have journal-appropriate formatting (font sizes, linewidths, no toolbar artefacts, correct figure dimensions) without altering the live display.

### Step 4.1 — Journal template dataclass

Add `src/lib/ui_output_image.py` (new file). Define:

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class JournalTemplate:
    name: str
    # Figure dimensions in mm (converted to inches for matplotlib)
    width_mm: float
    height_mm: float
    # Font
    font_family: str = "Arial"
    font_size_axis_label: float = 7.0
    font_size_tick_label: float = 6.0
    font_size_legend: float = 6.0
    # Line widths in points
    linewidth_data: float = 0.75
    linewidth_axes: float = 0.5
    # DPI for raster outputs
    dpi: int = 600
    # Which panels to include
    panels: list[Literal["event", "amp", "slope", "mean"]] = field(
        default_factory=lambda: ["event", "amp", "slope"]
    )
    # Layout: "vertical" (stacked) or "horizontal" (side by side)
    layout: Literal["vertical", "horizontal"] = "vertical"
```

### Step 4.2 — Built-in templates for relevant journals

Add a `JOURNAL_TEMPLATES: dict[str, JournalTemplate]` dict in `ui_image_export.py` with the following presets. All dimensions follow the respective journal's author guidelines for single-column and double-column figures.

| Key | Journal | Width (mm) | Height (mm) | Notes | Updated |
|---|---|---|---|---|---|
| `"jneurosci_1col"` | Journal of Neuroscience | 85 | 60 | Single column | 2026-03-15 |
| `"jneurosci_2col"` | Journal of Neuroscience | 174 | 120 | Full width | 2026-03-15 |
| `"jphysiol_1col"` | Journal of Physiology | 85 | 65 | Single column | 2026-03-15 |
| `"jphysiol_2col"` | Journal of Physiology | 174 | 130 | Full width | 2026-03-15 |
| `"nature_1col"` | Nature family | 89 | 65 | Single column | 2026-03-15 |
| `"nature_2col"` | Nature family | 183 | 130 | Full width | 2026-03-15 |

> **Caveat:** Journal specifications change. The implementer should verify current guidelines at implementation time. These values are based on guidelines current as of 2025.

### Step 4.3 — Menu addition

Add to `MenuMixin.setupMenus` in `ui_menus.py`, under the Image section:
Replace the existing `actionExportOutputImage` with one export command per template: `Groups to <template>`

### Step 4.4 — Figure renderer

Add `render_publication_figure(uistate, uiplot, template: JournalTemplate, selected_recs: list[str]) -> matplotlib.figure.Figure` to `ui_image_export.py`.

Algorithm:

1. **Create a fresh figure** (do not reuse the interactive figure):
   ```python
   fig = matplotlib.figure.Figure(
       figsize=(template.width_mm / 25.4, template.height_mm / 25.4),
       dpi=template.dpi,
   )
   ```
2. **Add subplots** according to `template.panels` and `template.layout`.
3. **Re-plot the data** from scratch onto the new axes:
   - Operate on selected groups - not recs.
   - Apply `template` styling (font sizes, linewidths) using `matplotlib.rcParams` within a `matplotlib.rc_context({...})` context manager so the interactive display is not altered.
   - Mirror the same colour logic as `UIplot` (`uistate.settings["rgb_EPSP_amp"]`, etc.).

5. Return the figure without displaying it.
