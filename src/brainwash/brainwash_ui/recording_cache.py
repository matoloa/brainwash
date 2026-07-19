"""Pure recording cache key/path helpers for ui_data_frames (no Qt)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

TIMEPOINTS_CACHE_KEY = "timepoints"

# Role suffix for the samples working copy under data/ (bare stem).
SAMPLE_DATA_SUFFIX = ".parquet"
# Sweep clock accessory next to samples (same lifetime as data/, not cache).
SWEEPTIMES_SUFFIX = "_sweeptimes.parquet"


def output_cache_key(*, bin_active: bool) -> str:
    return "output_bin" if bin_active else "output"


def output_parquet_suffix(*, bin_active: bool) -> str:
    return "_output_bin" if bin_active else "_output"


def output_parquet_path(cache_folder: str, recording_name: str, *, bin_active: bool) -> str:
    return f"{cache_folder}/{recording_name}{output_parquet_suffix(bin_active=bin_active)}.parquet"


def mean_parquet_path(cache_folder: str, recording_name: str) -> str:
    return f"{cache_folder}/{recording_name}_mean.parquet"


def filter_parquet_path(cache_folder: str, recording_name: str) -> str:
    return f"{cache_folder}/{recording_name}_filter.parquet"


def timepoints_parquet_path(timepoints_folder: str, recording_name: str) -> str:
    return f"{timepoints_folder}/{recording_name}.parquet"


def stim_intensity_csv_path(stim_intensity_folder: str, recording_name: str) -> str:
    """Per-recording user-owned stim strength CSV (µA).

    Idempotent: if ``recording_name`` already ends with ``.csv``, do not double it.
    """
    name = str(recording_name).strip()
    # Avoid "rec.csv.csv" when callers pass a name that already includes the suffix
    # or when rename glue does base + ".csv" on a path that already ends in .csv.
    while name.lower().endswith(".csv"):
        name = name[: -len(".csv")]
    return f"{stim_intensity_folder}/{name}.csv"


def data_parquet_path(data_folder: str, recording_name: str) -> str:
    return f"{data_folder}/{recording_name}.parquet"


def sweeptimes_parquet_path(data_folder: str, recording_name: str) -> str:
    """Absolute-ish path string for data/{rec}_sweeptimes.parquet."""
    return f"{data_folder}/{recording_name}{SWEEPTIMES_SUFFIX}"


def group_mean_parquet_path(cache_folder: str, group_id, *, level_suffix: str = "") -> str:
    return f"{cache_folder}/group_{group_id}{level_suffix}_mean.parquet"


def recording_disk_paths(dict_folders: Mapping[str, Any], recording_name: str) -> list[Path]:
    """All on-disk artifacts for a recording (samples, sweeptimes, timepoints, caches).

    Single source of truth for rename / purge / duplicate. Stim intensity is
    handled separately (name normalization via :func:`stim_intensity_csv_path`).
    """
    rec = str(recording_name)
    data = Path(dict_folders["data"])
    timepoints = Path(dict_folders["timepoints"])
    cache = Path(dict_folders["cache"])
    return [
        data / f"{rec}{SAMPLE_DATA_SUFFIX}",
        data / f"{rec}{SWEEPTIMES_SUFFIX}",
        timepoints / f"{rec}.parquet",
        cache / f"{rec}_mean.parquet",
        cache / f"{rec}_filter.parquet",
        cache / f"{rec}_bin.parquet",
        cache / f"{rec}_output.parquet",
    ]


def iter_recording_disk_files(dict_folders: Mapping[str, Any], recording_name: str) -> Iterable[Path]:
    """Yield paths from :func:`recording_disk_paths`."""
    yield from recording_disk_paths(dict_folders, recording_name)


def cache_and_timepoints_paths(dict_folders: Mapping[str, Any], recording_name: str) -> list[Path]:
    """Disposable analysis products only (not data/ or sweeptimes)."""
    rec = str(recording_name)
    timepoints = Path(dict_folders["timepoints"])
    cache = Path(dict_folders["cache"])
    return [
        timepoints / f"{rec}.parquet",
        cache / f"{rec}_mean.parquet",
        cache / f"{rec}_filter.parquet",
        cache / f"{rec}_bin.parquet",
        cache / f"{rec}_output.parquet",
    ]
