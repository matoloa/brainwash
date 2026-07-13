"""Headless parse → analysis_v3 pipeline integration (no Qt)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

import analysis_v3 as analysis
from parse import build_dfmean, source2dfs, zeroSweeps
from test_pipeline_fixtures import make_default_dict_t, make_sweep_df

_TEST_DATA = Path(__file__).parent / "test_data"
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


@pytest.mark.skipif(not _ABF_1CH.exists(), reason=f"real ABF absent: {_ABF_1CH}")
def test_real_abf_source2dfs_to_dfmean():
    dict_dfs = source2dfs(str(_ABF_1CH), gain=1.0)
    assert dict_dfs
    df_raw = next(iter(dict_dfs.values()))
    dfmean, i_stim = build_dfmean(df_raw)
    assert i_stim is not None
    for col in ("voltage", "prim", "bis", "time"):
        assert col in dfmean.columns