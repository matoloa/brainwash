"""Shared synthetic fixtures for headless pipeline integration tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def data_source_root() -> Path:
    return repo_root() / "data_source"


def load_data_source_manifest() -> list[dict]:
    manifest_path = data_source_root() / "manifest.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text())
        return list(data.get("candidates", []))
    root = data_source_root()
    if not root.is_dir():
        return []
    return [
        {"id": d.name, "file": "Concatenate000.abf"}
        for d in sorted(root.iterdir())
        if d.is_dir() and d.name.isdigit()
    ]


def data_source_abf_path(candidate_id: str, *, filename: str = "Concatenate000.abf") -> Path | None:
    path = data_source_root() / candidate_id / filename
    return path if path.is_file() else None


def discover_data_source_abfs() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for entry in load_data_source_manifest():
        cid = entry["id"]
        fname = entry.get("file", "Concatenate000.abf")
        path = data_source_abf_path(cid, filename=fname)
        if path is not None:
            found.append((cid, path))
    return found


def resolve_test_abf(directory: Path, stem: str) -> Path | None:
    """Return local ABF path (.abf or .abf.gitkeep) without requiring git commit."""
    abf = directory / f"{stem}.abf"
    if abf.is_file():
        return abf
    gitkeep = directory / f"{stem}.abf.gitkeep"
    if gitkeep.is_file():
        return gitkeep
    return None


def abf_path_for_parse(directory: Path, stem: str) -> Path | None:
    """Path suitable for parse.source2dfs (must end with .abf)."""
    src = resolve_test_abf(directory, stem)
    if src is None:
        return None
    if src.suffix == ".abf":
        return src
    dest = directory / f"{stem}.abf"
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest


def make_default_dict_t() -> dict:
    t_volley_slope_width = 0.0003
    t_epsp_slope_width = 0.0007
    resolution = 0.0001

    def floor_to(v, r):
        return (v // r) * r

    return {
        "t_volley_slope_width": t_volley_slope_width,
        "t_EPSP_slope_width": t_epsp_slope_width,
        "stim": 0,
        "t_stim": 0,
        "amp_zero": 0,
        "norm_output_from": 0,
        "norm_output_to": 0,
    }


def make_sweep_df(
    n_sweeps: int = 5,
    n_timepoints: int = 100,
    dt: float = 0.001,
    stim_index: int = 40,
    step_size: float = 0.001,
) -> pd.DataFrame:
    times = np.round(np.arange(n_timepoints) * dt, 6)
    voltage = np.zeros(n_timepoints)
    voltage[stim_index:] = step_size
    t0_per_sweep = np.arange(n_sweeps) * (n_timepoints * dt)
    sweeps_col = np.repeat(np.arange(n_sweeps), n_timepoints)
    times_col = np.tile(times, n_sweeps)
    voltage_col = np.tile(voltage, n_sweeps)
    t0_col = np.repeat(t0_per_sweep, n_timepoints)
    datetime_col = pd.to_datetime(t0_col + times_col, unit="s")
    return pd.DataFrame(
        {
            "sweep": sweeps_col,
            "time": times_col,
            "voltage_raw": voltage_col,
            "t0": t0_col,
            "datetime": datetime_col,
        }
    )