"""Tests for brainwash_ui.stim_intensity CSV store/align."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from brainwash_ui import recording_cache, stim_intensity as si


def test_stim_intensity_csv_path():
    p = recording_cache.stim_intensity_csv_path("/proj/stim_intensity", "rec_A")
    assert p == "/proj/stim_intensity/rec_A.csv"


def test_stim_intensity_csv_path_no_double_csv():
    p = recording_cache.stim_intensity_csv_path("/proj/stim_intensity", "rec_A.csv")
    assert p == "/proj/stim_intensity/rec_A.csv"
    p2 = recording_cache.stim_intensity_csv_path("/proj/stim_intensity", "rec_A.csv.csv")
    assert p2 == "/proj/stim_intensity/rec_A.csv"


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


def test_attach_stim_intensity_column():
    dfo = pd.DataFrame(
        {
            "stim": [1, 1, 1, 1],
            "sweep": [0, 1, 2, np.nan],
            "EPSP_amp": [1.0, 2.0, 3.0, 2.5],
        }
    )
    series = {0: 20.0, 2: 60.0}
    out = si.attach_stim_intensity_column(dfo, series)
    assert si.DFOUTPUT_COL in out.columns
    assert out.loc[0, si.DFOUTPUT_COL] == 20.0
    assert np.isnan(out.loc[1, si.DFOUTPUT_COL])
    assert out.loc[2, si.DFOUTPUT_COL] == 60.0
    assert np.isnan(out.loc[3, si.DFOUTPUT_COL])
    # Original not mutated
    assert si.DFOUTPUT_COL not in dfo.columns


def test_io_input_map_stim_to_stim_intensity():
    from brainwash_ui import plot_series

    assert plot_series.IO_INPUT_TO_XCOL["stim"] == "stim_intensity"
    x_col, y_col = plot_series.io_axis_columns("stim", "EPSPamp")
    assert x_col == "stim_intensity"
    assert y_col == "EPSP_amp"


def test_table_height_for_rows_caps_at_12():
    h1 = si.table_height_for_rows(1, row_height=24, header_height=24, frame_pad=4)
    h12 = si.table_height_for_rows(12, row_height=24, header_height=24, frame_pad=4)
    h13 = si.table_height_for_rows(13, row_height=24, header_height=24, frame_pad=4)
    assert h12 == h13  # cap
    assert h1 < h12
    assert h12 == 24 + 12 * 24 + 4


def test_n_bins_from_max_sweep():
    assert si.n_bins_from_max_sweep(9, 5) == 2  # sweeps 0..9, bin_size 5
    assert si.n_bins_from_max_sweep(4, 5) == 1


def test_series_for_binned_output():
    # raw sweeps with bin_size 2
    series = {0: 20.0, 1: 20.0, 2: 40.0, 3: 40.0}
    by_bin = si.series_for_binned_output(series, n_bins=2, bin_size=2)
    assert by_bin[0] == 20.0
    assert by_bin[1] == 40.0
