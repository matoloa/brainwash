"""Pure recording cache key/path helpers for ui_data_frames (no Qt)."""

from __future__ import annotations

TIMEPOINTS_CACHE_KEY = "timepoints"


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


def data_parquet_path(data_folder: str, recording_name: str) -> str:
    return f"{data_folder}/{recording_name}.parquet"


def group_mean_parquet_path(cache_folder: str, group_id, *, level_suffix: str = "") -> str:
    return f"{cache_folder}/group_{group_id}{level_suffix}_mean.parquet"