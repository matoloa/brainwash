# tests for parse.py — the current (v2) parsing pipeline
#
# Covered:
#   - first_stim_index    (pure logic, synthetic data)
#   - metadata            (pure logic, synthetic data)
#   - build_dfmean        (pure logic, synthetic data)
#   - zeroSweeps          (pure logic, synthetic data)
#   - persistdf           (I/O, temp directory)
#   - source2dfs          (file I/O — skipped when real ABFs are absent)
#   - sources2dfs         (file I/O — skipped when real ABFs are absent)
#   - parse_abf / folder  (file I/O — skipped when real ABFs are absent)
#
# Real test-data ABF files are not committed to the repo. Place them at:
#   src/lib/test_data/A_21_P0701-S2/2022_07_01_0012.abf  (1-channel)
#   src/lib/test_data/KO_02/2022_01_24_0000.abf           (2-channel)
# and the file-I/O tests will run automatically.

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from parse import (
    build_dfmean,
    first_stim_index,
    metadata,
    parse_abf,
    parse_abfFolder,
    persistdf,
    source2dfs,
    sources2dfs,
    zeroSweeps,
)

# ---------------------------------------------------------------------------
# Paths to optional real test data
# ---------------------------------------------------------------------------
_TEST_DATA = Path(__file__).parent / "test_data"
_ABF_1CH = _TEST_DATA / "A_21_P0701-S2" / "2022_07_01_0012.abf"
_ABF_2CH = _TEST_DATA / "KO_02" / "2022_01_24_0000.abf"

_skip_no_1ch = unittest.skipUnless(_ABF_1CH.exists(), f"real ABF absent: {_ABF_1CH}")
_skip_no_2ch = unittest.skipUnless(_ABF_2CH.exists(), f"real ABF absent: {_ABF_2CH}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_sweep_df(
    n_sweeps: int = 5,
    n_timepoints: int = 100,
    dt: float = 0.001,  # 1 kHz
    stim_index: int = 40,
    step_size: float = 0.001,  # 1 mV step at stim
) -> pd.DataFrame:
    """
    Build a minimal synthetic sweep DataFrame compatible with parse.py functions.

    Columns: sweep, time, voltage_raw, t0, datetime
    The voltage is flat before stim_index and steps up by step_size afterwards.
    """
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


# ---------------------------------------------------------------------------
# Tests: first_stim_index
# ---------------------------------------------------------------------------


class TestFirstStimIndex(unittest.TestCase):
    def _dfmean_from_voltage(
        self, voltage: np.ndarray, dt: float = 0.001
    ) -> pd.DataFrame:
        """Compute a minimal dfmean directly from a voltage array."""
        times = np.round(np.arange(len(voltage)) * dt, 6)
        dfmean = pd.DataFrame({"time": times, "voltage": voltage})
        dfmean["prim"] = dfmean["voltage"].rolling(3, center=True).mean().diff()
        dfmean["bis"] = dfmean["prim"].rolling(3, center=True).mean().diff()
        return dfmean

    def test_detects_step_peak(self):
        """first_stim_index should find the derivative peak close to the step."""
        stim_i = 40
        voltage = np.zeros(100)
        voltage[stim_i:] = 0.001
        dfmean = self._dfmean_from_voltage(voltage)

        i = first_stim_index(dfmean)

        self.assertIsNotNone(i)
        # Rolling windows may shift the peak by a few samples — allow ±3
        self.assertAlmostEqual(i, stim_i, delta=3)

    def test_returns_none_for_flat_signal(self):
        """first_stim_index should return None when prim is all-zero."""
        dfmean = pd.DataFrame(
            {
                "time": np.linspace(0, 0.1, 100),
                "voltage": np.zeros(100),
                "prim": np.zeros(100),
                "bis": np.zeros(100),
            }
        )
        self.assertIsNone(first_stim_index(dfmean))

    def test_peak_near_end(self):
        """Stim near the end of the sweep should still be detected."""
        stim_i = 85
        voltage = np.zeros(100)
        voltage[stim_i:] = 0.002
        dfmean = self._dfmean_from_voltage(voltage)

        i = first_stim_index(dfmean)

        self.assertIsNotNone(i)
        self.assertAlmostEqual(i, stim_i, delta=3)


# ---------------------------------------------------------------------------
# Tests: metadata
# ---------------------------------------------------------------------------


class TestMetadata(unittest.TestCase):
    def setUp(self) -> None:
        self.n_sweeps = 3
        self.n_timepoints = 100
        self.dt = 0.001  # 1 kHz → 100 ms sweeps
        self.df = _make_sweep_df(
            n_sweeps=self.n_sweeps,
            n_timepoints=self.n_timepoints,
            dt=self.dt,
        )

    def tearDown(self) -> None:
        pass

    def test_nsweeps(self):
        """metadata should count the correct number of sweeps."""
        meta = metadata(self.df)
        self.assertEqual(meta["nsweeps"], self.n_sweeps)

    def test_sweep_duration(self):
        """metadata sweep_duration should equal n_timepoints * dt."""
        meta = metadata(self.df)
        expected = round(self.n_timepoints * self.dt, 4)
        self.assertAlmostEqual(meta["sweep_duration"], expected, places=4)

    def test_sampling_rate(self):
        """metadata should recover the 1 kHz sampling rate."""
        meta = metadata(self.df)
        self.assertEqual(meta["sampling_rate"], 1000)

    def test_returns_dict_with_required_keys(self):
        meta = metadata(self.df)
        for key in ("nsweeps", "sweep_duration", "sampling_rate"):
            self.assertIn(key, meta)


# ---------------------------------------------------------------------------
# Tests: build_dfmean
# ---------------------------------------------------------------------------


class TestBuildDfmean(unittest.TestCase):
    def setUp(self) -> None:
        self.n_sweeps = 10
        self.stim_index = 40
        self.df = _make_sweep_df(
            n_sweeps=self.n_sweeps,
            n_timepoints=100,
            stim_index=self.stim_index,
        )

    def tearDown(self) -> None:
        pass

    def test_output_has_required_columns(self):
        dfmean, _ = build_dfmean(self.df)
        for col in ("voltage", "prim", "bis", "time"):
            self.assertIn(col, dfmean.columns)

    def test_i_stim_is_near_step(self):
        """build_dfmean should detect the stim near the voltage step."""
        _, i_stim = build_dfmean(self.df)
        self.assertIsNotNone(i_stim)
        self.assertAlmostEqual(i_stim, self.stim_index, delta=5)

    def test_baseline_region_is_zeroed(self):
        """The 20–10 samples before i_stim should average to ~0 after build_dfmean."""
        dfmean, i_stim = build_dfmean(self.df)
        if i_stim is None or i_stim < 20:
            self.skipTest("i_stim too small to test baseline region")
        baseline = dfmean.iloc[i_stim - 20 : i_stim - 10]["voltage"].mean()
        self.assertAlmostEqual(baseline, 0.0, places=6)

    def test_output_length_matches_timepoints(self):
        """dfmean should have one row per unique time point."""
        dfmean, _ = build_dfmean(self.df)
        n_unique_times = self.df["time"].nunique()
        self.assertEqual(len(dfmean), n_unique_times)


# ---------------------------------------------------------------------------
# Tests: zeroSweeps
# ---------------------------------------------------------------------------


class TestZeroSweeps(unittest.TestCase):
    def setUp(self) -> None:
        self.stim_index = 40
        self.df = _make_sweep_df(
            n_sweeps=5,
            n_timepoints=100,
            stim_index=self.stim_index,
        )

    def tearDown(self) -> None:
        pass

    def test_output_has_voltage_column(self):
        df_zeroed = zeroSweeps(self.df, i_stim=self.stim_index)
        self.assertIn("voltage", df_zeroed.columns)

    def test_baseline_is_zero_per_sweep(self):
        """After zeroing, baseline region of every sweep should average to ~0."""
        i = self.stim_index
        df_zeroed = zeroSweeps(self.df, i_stim=i)
        for sweep in df_zeroed["sweep"].unique():
            sw = df_zeroed[df_zeroed["sweep"] == sweep]
            baseline = sw.iloc[i - 20 : i - 10]["voltage"].mean()
            self.assertAlmostEqual(
                baseline, 0.0, places=6, msg=f"Sweep {sweep} baseline not zeroed"
            )

    def test_row_count_preserved(self):
        """zeroSweeps should not add or drop rows."""
        df_zeroed = zeroSweeps(self.df, i_stim=self.stim_index)
        self.assertEqual(len(df_zeroed), len(self.df))

    def test_original_df_not_mutated(self):
        """zeroSweeps should operate on a copy and leave the input unchanged."""
        original_col_sum = self.df["voltage_raw"].sum()
        zeroSweeps(self.df, i_stim=self.stim_index)
        self.assertAlmostEqual(self.df["voltage_raw"].sum(), original_col_sum)


# ---------------------------------------------------------------------------
# Tests: persistdf
# ---------------------------------------------------------------------------


class TestPersistdf(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self.dict_folders = {
            "data": tmp / "data",
            "cache": tmp / "cache",
        }
        self.df = _make_sweep_df(n_sweeps=3, n_timepoints=50)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_writes_data_csv(self):
        persistdf("rec01", self.dict_folders, dfdata=self.df)
        out = self.dict_folders["data"] / "rec01.csv"
        self.assertTrue(out.exists(), f"Expected data file not found: {out}")

    def test_data_csv_roundtrip(self):
        """CSV written by persistdf should be readable and have the same length."""
        persistdf("rec01", self.dict_folders, dfdata=self.df)
        df_read = pd.read_csv(self.dict_folders["data"] / "rec01.csv")
        self.assertEqual(len(df_read), len(self.df))

    def test_writes_mean_csv(self):
        dfmean, _ = build_dfmean(self.df)
        persistdf("rec01", self.dict_folders, dfmean=dfmean)
        out = self.dict_folders["cache"] / "rec01_mean.csv"
        self.assertTrue(out.exists(), f"Expected mean file not found: {out}")

    def test_writes_filter_csv(self):
        df_filter = zeroSweeps(self.df, i_stim=40)
        persistdf("rec01", self.dict_folders, dffilter=df_filter)
        out = self.dict_folders["cache"] / "rec01_filter.csv"
        self.assertTrue(out.exists(), f"Expected filter file not found: {out}")

    def test_creates_subfolders_if_absent(self):
        """persistdf should mkdir data/ and cache/ automatically."""
        self.assertFalse(self.dict_folders["data"].exists())
        persistdf("rec01", self.dict_folders, dfdata=self.df)
        self.assertTrue(self.dict_folders["data"].exists())


# ---------------------------------------------------------------------------
# Tests: source2dfs  (skipped when real ABF files are absent)
# ---------------------------------------------------------------------------


class TestSource2dfs(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_missing_path_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            source2dfs("/nonexistent/path/to/file.abf")

    def test_unsupported_extension_raises_value_error(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            tmp_path = f.name
        try:
            with self.assertRaises(ValueError):
                source2dfs(tmp_path)
        finally:
            os.unlink(tmp_path)

    @_skip_no_1ch
    def test_single_channel_abf_returns_dict(self):
        result = source2dfs(str(_ABF_1CH))
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    @_skip_no_1ch
    def test_single_channel_abf_has_required_columns(self):
        result = source2dfs(str(_ABF_1CH))
        df = next(iter(result.values()))
        for col in ("sweep", "time", "voltage_raw"):
            self.assertIn(col, df.columns)

    @_skip_no_1ch
    def test_single_channel_abf_no_nans_in_key_columns(self):
        result = source2dfs(str(_ABF_1CH))
        df = next(iter(result.values()))
        for col in ("sweep", "time", "voltage_raw"):
            self.assertFalse(df[col].isna().any(), f"NaNs found in column '{col}'")

    @_skip_no_2ch
    def test_two_channel_abf_returns_two_entries(self):
        result = source2dfs(str(_ABF_2CH))
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 2)

    @_skip_no_1ch
    def test_abf_folder_returns_dict(self):
        """source2dfs on a folder of ABF files should work via parse_abfFolder."""
        result = source2dfs(str(_ABF_1CH.parent))
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)


# ---------------------------------------------------------------------------
# Tests: sources2dfs
# ---------------------------------------------------------------------------


class TestSources2dfs(unittest.TestCase):
    def test_empty_list_returns_empty_list(self):
        result = sources2dfs([])
        self.assertEqual(result, [])

    @_skip_no_1ch
    def test_single_source_returns_list_of_one_dict(self):
        result = sources2dfs([str(_ABF_1CH)])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], dict)

    @_skip_no_1ch
    @_skip_no_2ch
    def test_two_sources_returns_list_of_two_dicts(self):
        result = sources2dfs([str(_ABF_1CH), str(_ABF_2CH)])
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIsInstance(item, dict)


# ---------------------------------------------------------------------------
# Tests: parse_abf (direct)
# ---------------------------------------------------------------------------


class TestParseAbf(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    @_skip_no_1ch
    def test_parse_abf_returns_dataframe(self):
        df = parse_abf(_ABF_1CH)
        self.assertIsInstance(df, pd.DataFrame)

    @_skip_no_1ch
    def test_parse_abf_has_expected_columns(self):
        df = parse_abf(_ABF_1CH)
        for col in ("time", "voltage_raw", "t0", "datetime", "channel"):
            self.assertIn(col, df.columns)

    @_skip_no_1ch
    def test_parse_abf_no_nans(self):
        df = parse_abf(_ABF_1CH)
        for col in ("time", "voltage_raw"):
            self.assertFalse(df[col].isna().any(), f"NaNs in '{col}'")

    @_skip_no_1ch
    def test_parse_abf_folder_returns_dataframe(self):
        df = parse_abfFolder(_ABF_1CH.parent)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
