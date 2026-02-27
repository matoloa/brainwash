# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # analysis_dev.py
#
# Development / exploration notebook for `analysis_v2`.
#
# This file is the **only** place that carries jupytext cell markers and
# notebook-style side-effect path manipulation.  `analysis_v2.py` is a plain
# importable module — keep it that way.
#
# Typical workflow:
# 1. `jupytext --sync notebook/analysis_dev.py` to open as a Jupyter notebook.
# 2. Edit exploratory cells here; promote stable helpers into `analysis_v2.py`.

# %%
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

# Make src/lib importable when running from the notebook directory or repo root.
_reporoot = Path(os.getcwd())
# Walk up until we find src/lib or hit the filesystem root.
for _candidate in [_reporoot, _reporoot.parent, _reporoot.parent.parent]:
    if (_candidate / "src" / "lib").exists():
        _reporoot = _candidate
        break
sys.path.insert(0, str(_reporoot / "src" / "lib"))

import analysis_v2

# %% [markdown]
# ## Load data

# %%
# Adjust folder_talkback to point at your local data directory.
folder_talkback = (
    Path.home() / "Documents" / "Brainwash Data Source" / "talkback KetaDexa"
)
# folder_talkback = Path.home() / "Documents" / "Brainwash Data Source" / "talkback Lactate24SR"

slice_filepaths = sorted(folder_talkback.glob("*slice*"))
meta_filepaths = sorted(folder_talkback.glob("*meta*"))

print(f"Found {len(slice_filepaths)} slices and {len(meta_filepaths)} meta files.")


# %%
def load_slice(path, sweep=1):
    df = pd.read_csv(str(path))
    df["sweep"] = sweep
    df["sweepname"] = Path(path).stem.split("_")[-2]
    rollingwidth = 3
    df["prim"] = df.voltage.rolling(rollingwidth, center=True).mean().diff()
    df["bis"] = df.prim.rolling(rollingwidth, center=True).mean().diff()
    return df


def load_meta(path, sweep=1):
    with open(path) as f:
        df = pd.DataFrame(json.load(f), index=[sweep])
    df["sweepname"] = Path(path).stem.split("_")[-2]
    return df


df = pd.concat([load_slice(p, i) for i, p in enumerate(slice_filepaths)]).reset_index(
    drop=True
)

meta = pd.concat([load_meta(p, i) for i, p in enumerate(meta_filepaths)]).reset_index(
    drop=True
)

print(f"df shape: {df.shape},  meta shape: {meta.shape}")

# %% [markdown]
# ## Single-sweep exploration

# %%
# Pick a sweep and run characterize_graph with verbose + plot output.
sweepname = df.sweepname.unique()[0]
# sweepname = "d1fdaa03-6a4a-4e32-9691-ad4ef09a1e1c"  # known-hard sweep

dfsweep = df.loc[df.sweepname == sweepname, ["time", "voltage"]]
result = analysis_v2.characterize_graph(
    dfsweep, stim_amp=0.005, verbose=True, plot=True
)
result

# %% [markdown]
# ## Batch evaluation


# %%
def check_sweep(sweepname):
    """Run characterize_graph on a single sweep; return result dict + sweepname."""
    dfsweep = df.loc[df.sweepname == sweepname, ["time", "voltage", "prim", "bis"]]
    result = analysis_v2.characterize_graph(
        dfsweep, stim_amp=0.005, verbose=False, plot=False
    )
    result.update({"sweepname": sweepname})
    return result


results = [check_sweep(sw) for sw in df.sweepname.unique()]
signals = [
    df.loc[df.sweepname == sw, ["time", "voltage"]].copy()
    for sw in df.sweepname.unique()
]

dfresults = pd.DataFrame(results)
t_cols = [c for c in dfresults.columns if c.startswith("t_")]
print(dfresults[t_cols + ["sweepname"]].head())

# %% [markdown]
# ## Compare v2 results against ground-truth meta

# %%
# Quick offset check (in index points, 1 point ≈ 0.0001 s).
TIME_SCALE = 10000

if "t_EPSP_slope_start" in meta.columns and "t_volley_slope_start" in meta.columns:
    dfdiff = pd.DataFrame({"sweepname": dfresults["sweepname"]})
    for col in ["t_EPSP_slope_start", "t_volley_slope_start"]:
        if col in dfresults.columns:
            dfdiff[f"delta_{col}"] = (
                (dfresults[col].values - meta[col].values) * TIME_SCALE
            ).round(1)
    display(dfdiff)  # type: ignore[name-defined]  # noqa: F821
else:
    print("meta does not contain ground-truth slope columns — skipping diff.")

# %% [markdown]
# ## Worst-offender plots

# %%
# Identify the sweeps with the largest EPSP slope start offset and plot them.
if "delta_t_EPSP_slope_start" in dfdiff.columns:
    worst = dfdiff.nlargest(5, "delta_t_EPSP_slope_start")["sweepname"].tolist()
    for sw in worst:
        dfsweep = df.loc[df.sweepname == sw, ["time", "voltage"]]
        print(f"--- {sw} ---")
        analysis_v2.characterize_graph(
            dfsweep, stim_amp=0.005, verbose=False, plot=True, multiplots=True
        )
