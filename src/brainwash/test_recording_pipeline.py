"""Characterization tests for brainwash_ui.recording_pipeline."""

from __future__ import annotations

import analysis_v3 as analysis
import pandas as pd
from parse import build_dfmean, zeroSweeps

from brainwash_ui import recording_pipeline
from test_pipeline_fixtures import make_default_dict_t, make_sweep_df


def test_resolve_output_filter_col():
    assert recording_pipeline.resolve_output_filter_col("savgol") == "savgol"
    assert recording_pipeline.resolve_output_filter_col(None) == "voltage"
    assert recording_pipeline.resolve_output_filter_col("none") == "voltage"
    assert recording_pipeline.resolve_output_filter_col(float("nan")) == "voltage"


def test_is_recording_parsed():
    assert recording_pipeline.is_recording_parsed({"sweeps": "..."}) is False
    assert recording_pipeline.is_recording_parsed({"sweeps": "[0, 1]"}) is True


def test_migrate_dft_column_names():
    dft = pd.DataFrame({"stim": [1], "norm_EPSP_from": [0.0], "norm_EPSP_to": [1.0]})
    assert recording_pipeline.migrate_dft_column_names(dft) is True
    assert list(dft.columns) == ["stim", "norm_output_from", "norm_output_to"]
    assert recording_pipeline.migrate_dft_column_names(dft) is False


def test_build_dft_from_synthetic_mean():
    df_raw = make_sweep_df()
    dfmean, _ = build_dfmean(df_raw)
    dft = recording_pipeline.build_dft(
        dfmean,
        default_dict_t=make_default_dict_t(),
        filter="voltage",
        norm_output_from=0.01,
        norm_output_to=0.02,
    )
    assert dft is not None and not dft.empty
    assert dft["norm_output_from"].iloc[0] == 0.01
    assert dft["norm_output_to"].iloc[0] == 0.02


def test_build_dfoutput_from_inputs_matches_analysis():
    df_raw = make_sweep_df()
    dfmean, i_stim = build_dfmean(df_raw)
    dffilter = zeroSweeps(df_raw, i_stim=i_stim)
    dft = analysis.find_events(dfmean=dfmean, default_dict_t=make_default_dict_t(), verbose=False)
    direct = analysis.build_dfoutput(dffilter=dffilter, dfmean=dfmean, dft=dft)
    via_pipeline = recording_pipeline.build_dfoutput_from_inputs(
        dffilter, dfmean, dft.copy(), filter_val="voltage"
    )
    assert "index" not in via_pipeline.columns
    assert set(direct.columns) == set(via_pipeline.columns)
    assert len(via_pipeline) == len(direct)


def test_backfill_volley_means_into_dft():
    dft = pd.DataFrame({"stim": [1, 2], "volley_amp_mean": [pd.NA, pd.NA], "volley_slope_mean": [pd.NA, pd.NA]})
    dfoutput = pd.DataFrame(
        {
            "stim": [1, 1, 2, 2],
            "sweep": [0, 1, 0, 1],
            "volley_amp": [0.1, 0.3, 0.5, 0.7],
            "volley_slope": [0.01, 0.03, 0.05, 0.07],
        }
    )
    recording_pipeline.backfill_volley_means_into_dft(dft, dfoutput)
    assert dft.at[0, "volley_amp_mean"] == 0.2
    assert dft.at[1, "volley_amp_mean"] == 0.6


def test_clean_dfoutput_from_parquet_drops_index():
    df = pd.DataFrame({"stim": [1], "sweep": [0], "index": [99]})
    cleaned, repersist = recording_pipeline.clean_dfoutput_from_parquet(df)
    assert repersist is True
    assert "index" not in cleaned.columns