"""Headless parse → analysis_v3 pipeline integration (no Qt)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

import analysis_v3 as analysis
from brainwash_ui import plot_stim
from parse import build_dfmean, source2dfs, zeroSweeps
from test_pipeline_fixtures import make_default_dict_t, make_sweep_df

_TEST_DATA = Path(__file__).parent / "test_data"
_GOLDEN_DFOUTPUT = _TEST_DATA / "golden" / "synthetic_dfoutput.parquet"
_ABF_1CH = _TEST_DATA / "A_21_P0701-S2" / "2022_07_01_0012.abf"


def test_synthetic_pipeline_build_dfoutput():
    df_raw = make_sweep_df()
    dfmean, i_stim = build_dfmean(df_raw)
    assert i_stim is not None
    dffilter = zeroSweeps(df_raw, i_stim=i_stim)
    dft = analysis.find_events(dfmean=dfmean, default_dict_t=make_default_dict_t(), verbose=False)
    assert dft is not None and not dft.empty
    dfoutput = analysis.build_dfoutput(dffilter=dffilter, dfmean=dfmean, dft=dft)
    assert not dfoutput.empty
    assert "sweep" in dfoutput.columns
    assert "EPSP_amp" in dfoutput.columns
    assert "index" not in dfoutput.columns


def test_parquet_roundtrip_no_spurious_index_column():
    df = pd.DataFrame(
        {
            "stim": [1, 1, 2, 2],
            "sweep": [0, 1, 0, 1],
            "EPSP_amp": [0.1, 0.2, 0.3, 0.4],
            "volley_amp": [0.05, 0.06, 0.07, 0.08],
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        path = f.name
    try:
        df.to_parquet(path, index=False)
        df2 = pd.read_parquet(path)
        df2.reset_index(drop=True, inplace=True)
        assert "index" not in df2.columns
    finally:
        os.unlink(path)


def test_golden_dfoutput_parquet_columns():
    assert _GOLDEN_DFOUTPUT.exists(), f"golden missing: {_GOLDEN_DFOUTPUT}"
    df = pd.read_parquet(_GOLDEN_DFOUTPUT)
    for col in ("stim", "sweep", "EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"):
        assert col in df.columns
    assert "index" not in df.columns


def test_golden_pipeline_event_window_non_empty():
    df_raw = make_sweep_df()
    dfmean, _i_stim = build_dfmean(df_raw)
    df_event = plot_stim.event_window_df(dfmean, t_stim=0.04, event_start=-0.01, event_end=0.02, rec_filter="prim")
    assert not df_event.empty


@pytest.mark.skipif(not _ABF_1CH.exists(), reason=f"real ABF absent: {_ABF_1CH}")
def test_real_abf_source2dfs_to_dfmean():
    dict_dfs = source2dfs(str(_ABF_1CH), gain=1.0)
    assert dict_dfs
    df_raw = next(iter(dict_dfs.values()))
    dfmean, i_stim = build_dfmean(df_raw)
    assert i_stim is not None
    for col in ("voltage", "prim", "bis", "time"):
        assert col in dfmean.columns