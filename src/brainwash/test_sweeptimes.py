"""Tests for lean samples + build_sweeptimes + sweep_hz from accessory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import parse

_TEST_ABF = Path(__file__).resolve().parent / "test_data" / "A_21_P0701-S2" / "2022_07_01_0012.abf"


def _abf_like_long(n_sweeps=4, n_tp=10, dt=0.0001, interval=2.5):
    rows = []
    origin = pd.Timestamp("2022-01-01 12:00:00")
    for sw in range(n_sweeps):
        t0 = sw * interval
        for i in range(n_tp):
            t = i * dt
            rows.append(
                {
                    "sweep": sw,
                    "time": t,
                    "voltage_raw": 0.001 * sw,
                    "t0": t0,
                    "datetime": origin + pd.Timedelta(seconds=t0 + t),
                }
            )
    return pd.DataFrame(rows)


def test_lean_samples_drops_clock():
    df = _abf_like_long()
    out = parse.lean_samples(df)
    assert list(out.columns) == ["sweep", "time", "voltage_raw"]
    assert out["sweep"].dtype == np.int32


def test_build_sweeptimes_abf_run_relative_t0():
    df = _abf_like_long()
    st = parse.build_sweeptimes(df, source_kind="abf")
    assert len(st) == 4
    assert st["t0"].tolist() == pytest.approx([0.0, 2.5, 5.0, 7.5])
    assert st["sweep_start"].notna().all()
    assert st["recording_start"].nunique() == 1
    hz = parse.compute_sweep_hz(None, sweeptimes=st)
    assert hz == pytest.approx(0.4)


def test_build_sweeptimes_ibw_derives_t0_from_absolute():
    df = _abf_like_long()
    df = df.copy()
    df["t0"] = 0.0  # IBW placeholder
    st = parse.build_sweeptimes(df, source_kind="ibw")
    assert st["t0"].tolist() == pytest.approx([0.0, 2.5, 5.0, 7.5])
    assert parse.compute_sweep_hz(None, sweeptimes=st) == pytest.approx(0.4)


def test_build_sweeptimes_null_clock():
    df = pd.DataFrame(
        {
            "sweep": [0, 0, 1, 1],
            "time": [0.0, 0.1, 0.0, 0.1],
            "voltage_raw": [0.0, 0.1, 0.0, 0.1],
            "t0": [np.nan, np.nan, np.nan, np.nan],
            "datetime": [pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        }
    )
    st = parse.build_sweeptimes(df, source_kind="atf")
    assert len(st) == 2
    assert st["t0"].isna().all()
    assert st["sweep_start"].isna().all()
    assert parse.compute_sweep_hz(None, sweeptimes=st) is None


def test_zero_sweeps_lean_columns_only():
    df = _abf_like_long(n_sweeps=2, n_tp=80)
    # stim-like peak for first_stim_index path via explicit i_stim
    df.loc[df["time"] == 0.004, "voltage_raw"] = -1.0
    z = parse.zeroSweeps(df, i_stim=40)
    assert list(z.columns) == ["sweep", "time", "voltage"]
    assert "datetime" not in z.columns
    assert "t0" not in z.columns
    assert len(z) == len(df)


def test_remap_sweeptimes_after_removal():
    df = _abf_like_long(n_sweeps=5)
    st = parse.build_sweeptimes(df, source_kind="abf")
    st2 = parse.remap_sweeptimes_after_removal(st, {1, 3})
    assert st2["sweep"].tolist() == [0, 1, 2]
    # remaining were 0,2,4 → t0 0, 5, 10 after re-base from first kept absolute
    assert len(st2) == 3


def test_metadata_uses_sweeptimes_for_hz():
    df = _abf_like_long()
    samples = parse.lean_samples(df)
    st = parse.build_sweeptimes(df, source_kind="abf")
    meta = parse.metadata(samples, sweeptimes=st)
    assert meta["nsweeps"] == 4
    assert meta["sweep_hz"] == pytest.approx(0.4)


@pytest.mark.skipif(not _TEST_ABF.exists(), reason="test ABF missing")
def test_real_abf_sweeptimes_hz():
    raw = parse.parse_abf(_TEST_ABF)
    ch0 = raw[raw["channel"] == 0].copy()
    ch0["sweep"] = ch0.groupby((ch0["time"] == 0).cumsum()).ngroup()
    st = parse.build_sweeptimes(ch0, source_kind="abf")
    hz = parse.compute_sweep_hz(None, sweeptimes=st)
    assert hz == pytest.approx(0.4)
    samples = parse.lean_samples(ch0)
    assert "datetime" not in samples.columns
    z = parse.zeroSweeps(samples, i_stim=70)
    assert list(z.columns) == ["sweep", "time", "voltage"]
