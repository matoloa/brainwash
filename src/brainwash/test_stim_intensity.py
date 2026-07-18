"""Tests for brainwash_ui.stim_intensity CSV store/align."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from brainwash_ui import recording_cache, stim_intensity as si


def test_stim_intensity_csv_path():
    p = recording_cache.stim_intensity_csv_path("/proj/stim_intensity", "rec_A")
    assert p == "/proj/stim_intensity/rec_A.csv"


def test_load_missing_returns_empty(tmp_path: Path):
    df = si.load_stim_intensity_csv(tmp_path / "missing.csv")
    assert list(df.columns) == list(si.CSV_COLUMNS)
    assert df.empty


def test_roundtrip_csv(tmp_path: Path):
    path = tmp_path / "rec1.csv"
    original = pd.DataFrame({si.SWEEP_COL: [0, 1, 2], si.INTENSITY_COL: [20.0, 40.0, 60.0]})
    si.save_stim_intensity_csv(path, original)
    loaded = si.load_stim_intensity_csv(path)
    assert list(loaded[si.SWEEP_COL]) == [0, 1, 2]
    assert list(loaded[si.INTENSITY_COL]) == [20.0, 40.0, 60.0]


def test_load_coerces_bad_cells(tmp_path: Path):
    path = tmp_path / "messy.csv"
    path.write_text("sweep,stim_intensity_uA\n0,20\n1,not_a_number\n2,60\nbad,80\n")
    loaded = si.load_stim_intensity_csv(path)
    assert list(loaded[si.SWEEP_COL]) == [0, 1, 2]
    assert loaded.loc[loaded[si.SWEEP_COL] == 0, si.INTENSITY_COL].iloc[0] == 20.0
    assert pd.isna(loaded.loc[loaded[si.SWEEP_COL] == 1, si.INTENSITY_COL].iloc[0])
    assert loaded.loc[loaded[si.SWEEP_COL] == 2, si.INTENSITY_COL].iloc[0] == 60.0


def test_align_to_sweeps_pads_and_orders():
    series = {0: 10.0, 2: 30.0}
    arr = si.align_to_sweeps(series, [0, 1, 2, 3])
    assert arr.shape == (4,)
    assert arr[0] == 10.0
    assert np.isnan(arr[1])
    assert arr[2] == 30.0
    assert np.isnan(arr[3])


def test_align_to_n_sweeps_truncates_extra():
    series = {0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0, 99: 99.0}
    arr = si.align_to_n_sweeps(series, 3, sweep_start=0)
    assert list(arr) == [1.0, 2.0, 3.0]


def test_align_from_dataframe():
    df = pd.DataFrame({si.SWEEP_COL: [1, 2], si.INTENSITY_COL: [40.0, 50.0]})
    arr = si.align_to_n_sweeps(df, 3, sweep_start=1)
    assert arr[0] == 40.0
    assert arr[1] == 50.0
    assert np.isnan(arr[2])


def test_expand_bin_values_to_sweeps():
    # bin_size=2, 3 bins → sweeps 0..5
    mapping = si.expand_bin_values_to_sweeps([20.0, 40.0, 60.0], bin_size=2, n_sweeps=6)
    assert mapping == {0: 20.0, 1: 20.0, 2: 40.0, 3: 40.0, 4: 60.0, 5: 60.0}


def test_expand_bin_clips_to_n_sweeps():
    mapping = si.expand_bin_values_to_sweeps([10.0, 20.0], bin_size=3, n_sweeps=4)
    assert mapping[0] == 10.0 and mapping[1] == 10.0 and mapping[2] == 10.0
    assert mapping[3] == 20.0
    assert 4 not in mapping


def test_bin_values_from_sweep_series():
    series = {0: 20.0, 1: 20.0, 2: 40.0, 3: 42.0}
    bins = si.bin_values_from_sweep_series(series, n_bins=2, bin_size=2)
    assert bins[0] == 20.0
    assert bins[1] == 41.0  # mean of 40 and 42


def test_series_frame_roundtrip():
    series = {2: 50.0, 0: 10.0}
    df = si.frame_from_series(series)
    assert list(df[si.SWEEP_COL]) == [0, 2]
    back = si.series_from_frame(df)
    assert back == {0: 10.0, 2: 50.0}


def test_save_creates_parent_dir(tmp_path: Path):
    path = tmp_path / "stim_intensity" / "rec.csv"
    si.save_stim_intensity_csv(path, si.frame_from_series({0: 1.0}))
    assert path.is_file()
