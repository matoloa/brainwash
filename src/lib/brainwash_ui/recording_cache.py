"""Pure output cache key/path helpers for get_dfoutput (no Qt)."""

from __future__ import annotations


def output_cache_key(*, bin_active: bool) -> str:
    return "output_bin" if bin_active else "output"


def output_parquet_suffix(*, bin_active: bool) -> str:
    return "_output_bin" if bin_active else "_output"


def output_parquet_path(cache_folder: str, recording_name: str, *, bin_active: bool) -> str:
    return f"{cache_folder}/{recording_name}{output_parquet_suffix(bin_active=bin_active)}.parquet"