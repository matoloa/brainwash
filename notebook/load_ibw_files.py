# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
import os  # speak to OS (list dirs)
from pathlib import Path

# %%
import matplotlib.pyplot as plt  # plotting
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
import scipy  # peakfinder and other useful analysis tools
import seaborn as sns  # plotting
#from neo import io  # bypassing neo for now, igor2 reads ibw by itself
import igor2 as igor
from sklearn import linear_model
from sklearn.linear_model import HuberRegressor
from tqdm.notebook import tqdm
from joblib import Parallel, delayed
#from datetime import datetime, timedelta

# %%
dir_project_root = Path(os.getcwd().split('notebook')[0])
dir_source_data = Path.home() / "Documents/Brainwash Data Source"
dir_ibw = list(dir_source_data.glob('ibw*'))[0]
ibw_folder0 = list(dir_ibw.glob('*'))[0]
ibw_folder0

# %%
list(dir_ibw.glob('*'))

# %%
#ibw = io.IgorIO(list(ibw_folder0.glob('*'))[0])
ibw = igor.binarywave.load(list(ibw_folder0.glob('*'))[0])

# %%
#ibw.read_analogsignal()


# %%
#ibw.read_block()

# %%
#ibw.read_segment()

# %%
#signal = ibw.read_analogsignal()
#signal.as_array()

# %%
#ibw = io.IgorIO(ibw_folder0.glob('*'))


# %%
ibw = igor.binarywave.load(list(ibw_folder0.glob('*'))[0])

# %%
ibw['wave']


# %%
def ibw_read(file):
    ibw = igor.binarywave.load(file)
    timestamp = ibw['wave']['wave_header']['creationDate']
    meta_sfA = ibw['wave']['wave_header']['sfA']
    array = ibw['wave']['wData']
    return {'timestamp': timestamp, 'meta_sfA': meta_sfA, 'array': array}


def parse_ibw_igor2(folder, dev=True):
    files = sorted(list(folder.glob('*')))
    if dev:
        files = files[:100]


    meta_sfAs = []
    timestamps = []
    arrays = []
    for file in tqdm(files):
        ibw = igor.binarywave.load(file)
        timestamps.append(ibw['wave']['wave_header']['creationDate'])
        meta_sfAs.append(ibw['wave']['wave_header']['sfA'])
        arrays.append(ibw['wave']['wData'])
    return (timestamps, arrays)
    
#timestamps, arrays = parse_ibw_igor2(folder=ibw_folder0, dev=False)

# %%
def parse_ibw_igor2_para(folder, dev=True):
    files = sorted(list(folder.glob('*.ibw')))
    if dev:
        files = files[:100]
    results = Parallel(n_jobs=-1)(delayed(ibw_read)(file) for file in tqdm(files))
    keys = results[0].keys()
    res = {}
    for key in keys:
        res[key] = [i[key] for i in results]
    return res['timestamp'], res['meta_sfA'], res['array']
    
timestamps, timesteps, arrays = parse_ibw_igor2_para(folder=ibw_folder0)

# %%
seconds = (pd.to_datetime("1970-01-01") - pd.to_datetime("1900-01-01")).total_seconds()

timestamp_array = (np.array(timestamps)-seconds)
measurement_start = min(timestamp_array)
timestamp_array -= measurement_start
voltage_raw = np.vstack(arrays)

df = pd.DataFrame(data=voltage_raw, index=timestamp_array)

timestep = timesteps[0][0]
df.columns = np.round(np.arange(7500) * timestep, int(-np.log(timestep))).tolist()
df = df.stack().reset_index()
df.columns = ["t0", "time", "voltage_raw"]
df.t0 = df.t0.astype("float32")
df.time = df.time.astype("float32")
df['datetime'] = pd.to_datetime((measurement_start + df.t0 + df.time) * 1_000_000_000)
df

# %%
sns.heatmap(np.vstack(arrays))

# %%
len(timestamps)

# %%
timestamps

# %%
