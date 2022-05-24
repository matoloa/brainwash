---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.13.1
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

# Roadmap
* read abf:s
* extract EPSP/volley.mean
* display average EPSP/volley (SEM shade)





```python
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import os  # speak to OS (list dirs)
import matplotlib.pyplot as plt  # plotting
import seaborn as sns  # plotting
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw
import scipy  # peakfinder and other useful analysis tools
from tqdm.notebook import tqdm
from pathlib import Path
from sklearn import linear_model
from joblib import Memory

memory = Memory("joblib", verbose=1)
```

```python
# set some working folders
dir_project_root = Path(os.getcwd().split("notebook")[0])
dir_source_data = dir_project_root / "dataSource" / "Lactate_2022_abf"
dir_gen_data = dir_project_root / "dataGenerated"
dir_source_data
```

```python
list_folders = [i for i in os.listdir(dir_source_data) if -1 < i.find("GKO")]
list_folders
```

```python
@memory.cache
def importAbf(filepath, channel=0, oddeven=None):
    """
    import .abf and return <"odd"/"even"/"all"> sweeps from channel <0/1>
    oddeven defaults to channel-appropriate parameter
    """

    # parse abf
    abf = pyabf.ABF(filepath)

    if not channel in abf.channelList:
        raise ValueError(f"No channel {channel} in {filepath}")
    if oddeven is None:
        if channel == 0:
            oddeven = "odd"
        else:
            oddeven = "even"

    sweeps = range(abf.sweepCount)

    dfs = []
    for i in sweeps:
        # get data
        abf.setSweep(sweepNumber=i, channel=channel)
        df = pd.DataFrame({"sweepX": abf.sweepX, "sweepY": abf.sweepY})
        df["sweep_raw"] = i
        df["t0"] = abf.sweepTimesSec[i]
        dfs.append(df)

    df = pd.concat(dfs)
    df["sweep"] = df.sweep_raw  # relevant for single file imports

    # Convert to SI
    df["time"] = df.sweepX  # / abf.sampleRate
    df["voltage"] = df.sweepY / 1000

    # Absolute date and time
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (
        abf.abfDateTime - pd.to_datetime(0)
    )

    # Odd / Even sweep inclusion
    df["even"] = df.sweep_raw.apply(lambda x: x % 2 == 0)
    df["oddeven"] = df.even.apply(lambda x: "even" if x else "odd")
    df = df[df.oddeven == oddeven]  # filter rows by Boolean
    df.drop(columns=["sweepX", "sweepY", "even", "oddeven", "timens"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
```

```python
def importAbfFolder(folderpath, channel=0):
    """ """
    list_files = [
        i for i in os.listdir(folderpath) if -1 < i.find(".abf")
    ]  # [:2] # stop before item 2 [begin:end]
    # print(list_files)
    listdf = []
    maxsweep = 0
    for filename in list_files:
        df = importAbf(folderpath / filename, channel=channel)
        df["sweep"] = df.sweep_raw + maxsweep
        maxsweep = df.sweep.max()
        listdf.append(df)

    # Check first timestamp in each df, very correct sequence, raise error
    df = pd.concat(listdf)
    # df.drop(columns=['sweep_raw'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
```

# Functions to find EPSP and volley slopes

* Import returns df (FIX: more specific name!)

* build_dfmean returns dfmean with 3 columns
    1 dfmean.voltage
    2 dfmean.prim
    3 dfmean.bis

* FindStim returns t_Stim (time of stim artefact)
    IN: dfmeandiff
* Normalize returns normalized dfmean
    IN: dfmean, t_Stim=0, normpoints=20
* FindEPSP returns t_EPSP (time of WIDEST negative peak center)
    IN: dfmean, t_Stim (limit left)
* FindVEB returns t_VEB (time of notch between Volley and EPSP)
    IN: dfmeandiff, t_EPSP
* FindEPSP_slope returns (time of EPSP slope center)
    IN: t_VEB, t_EPSP? (limit right)
* FindVolley_slope returns t_Volley_slope (time of Volley slope center)
    IN: t_VEB, t_Stim

```python
def build_dfmean(df, rollingwidth=3):
    """
    dfmean.voltate(V) (a single sweep built on the mean of all time)
    dfmean.prim
    dfmean.bis

    dfabf.pivot(columns='time', index='sweep', values='voltage').mean(axis=0).plot()

    """

    # pivot is useful, learn it
    dfmean = pd.DataFrame(
        df.pivot(columns="time", index="sweep", values="voltage").mean()
    )
    dfmean.columns = ["voltage"]
    dfmean.voltage -= dfmean.voltage.median()

    # generate diffs, *5 for better visualization
    dfmean["prim"] = dfmean.voltage.diff().rolling(rollingwidth, center=True).mean() * 5
    dfmean["bis"] = dfmean.prim.diff().rolling(rollingwidth, center=True).mean() * 5

    return dfmean
```

```python
def findStim(dfmean):
    """
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returnst_Stim (index of stim artefact)
    """
    return dfmean["prim"].idxmax()
```

```python
def findEPSP(
    dfmean,
    limitleft=0,
    limitright=-1,
    param_minimum_width_of_EPSP=2,
    param_EPSP_prominence=0.00005,
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    i_peaks = scipy.signal.find_peaks(
        -dfmean["voltage"],
        width=param_minimum_width_of_EPSP,
        prominence=param_EPSP_prominence,
    )[0]
    # scipy.signal.find_peaks returns a tuple
    dfpeaks = dfmean.iloc[i_peaks]
    # dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    t_EPSP = dfpeaks.index.max()

    return t_EPSP
```

```python
def findVEB(
    dfmean,
    t_EPSP,
    param_minimum_width_of_VEB=0.0005,
    param_prim_prominence=0.00005,
    param_minimum_width_of_EPSP=0.005,
):
    """
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    """
    i_peaks = scipy.signal.find_peaks(
        dfmean.prim, width=param_minimum_width_of_VEB, prominence=param_prim_prominence
    )[0]
    # print("i_peaks:", i_peaks, len(i_peaks))
    t_peaks = dfmean.iloc[i_peaks].index
    # print("t_peaks:", t_peaks)
    max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
    # print(max_acceptable_t_for_VEB)
    possible_t_VEB = max(t_peaks[t_peaks < max_acceptable_t_for_VEB])
    t_VEB = possible_t_VEB  # setting as accepted now, maybe have verification function later

    return t_VEB, max_acceptable_t_for_VEB
```

```python
def find_t_EPSPslope(dfmean, t_VEB, t_EPSP, happy=False):
    """ """

    dftemp = dfmean.bis[t_VEB:t_EPSP]
    t_EPSPslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if 1 < len(t_EPSPslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[t_VEB: t_EPSP]:{t_EPSPslope}"
            )
        else:
            print(
                "More EPSPs than than we wanted but Im happy, so I pick one and move on."
            )
    return t_EPSPslope[0]
```

```python
def find_t_volleyslope(
    dfmean, t_Stim, t_VEB, happy=False
):  # , param_half_slope_width = 4):
    """
    returns time of volley slope center,
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    """

    dftemp = dfmean.bis[t_Stim:t_VEB]
    t_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    # print(dftemp.apply(np.sign).diff())
    # print(t_volleyslope)
    if 1 < len(t_volleyslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[t_Stim: t_VEB]:{t_volleyslope}"
            )
        else:
            print(
                "More volleys than than we wanted but Im happy, so I pick one and move on."
            )
    return t_volleyslope[-1]
```

```python
def find_t(df, param_min_time_from_t_Stim=0.0005):
    """
    runs all t-detections in the appropriate sequence,
    returns time of center for volley EPSP slopes
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    The function finds VEB, but does not currently report it

    """
    dfmean = build_dfmean(df)
    t_Stim = findStim(dfmean)
    t_EPSP = findEPSP(dfmean)
    t_VEB, max_acceptable_t_for_VEB = findVEB(dfmean, t_EPSP)
    t_EPSPslope = find_t_EPSPslope(dfmean, t_VEB, t_EPSP, happy=True)
    t_volleyslope = find_t_volleyslope(
        dfmean, (t_Stim + param_min_time_from_t_Stim), t_VEB, happy=True
    )

    return t_volleyslope, t_EPSPslope
```

```python
def measure_slopes(
    df, t_volleyslope, t_EPSPslope, halfwidth_volley=0.0002, halfwidth_EPSP=0.0004
):
    """

    INCORRECT, get-both-at-once function. Should be calling measureSlope twice

    I've figure out why not to use time as an index for this df.
    In this case, time is not a unique, but a repeated index and that's should never be done on purpose
    in my not so humble opinion. An index should always be unique when you create it on purpose.

    """
    reg = linear_model.LinearRegression()

    dicts = []
    for sweep in tqdm(df.sweep.unique()):
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[
            ((t_EPSPslope - halfwidth_EPSP) <= dftemp1.time)
            & (dftemp1.time <= (t_EPSPslope + halfwidth_EPSP))
        ]
        x = dftemp2.index.values.reshape(-1, 1)
        y = dftemp2.voltage.values.reshape(-1, 1)

        reg.fit(x, y)
        assert dftemp2.t0.nunique() == 1
        t0 = dftemp2.t0.unique()[0]
        dict_slope = {
            "sweep": sweep,
            "t0": t0,
            "EPSP_slope": reg.coef_[0][0],
            "type": "linear",
        }
        dicts.append(dict_slope)

    df_slopes_EPSP = pd.DataFrame(dicts)

    return df_slopes_EPSP
```

```python
def measure_slope(df, t_slope, halfwidth, name="EPSP"):
    """
    CORRECT, generalized function


    """
    reg = linear_model.LinearRegression()

    dicts = []
    for sweep in tqdm(df.sweep.unique()):
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[
            ((t_slope - halfwidth) <= dftemp1.time)
            & (dftemp1.time <= (t_slope + halfwidth))
        ]
        x = dftemp2.index.values.reshape(-1, 1)
        y = dftemp2.voltage.values.reshape(-1, 1)

        reg.fit(x, y)
        assert dftemp2.t0.nunique() == 1
        t0 = dftemp2.t0.unique()[0]
        dict_slope = {
            "sweep": sweep,
            "t0": t0,
            "value": reg.coef_[0][0],
            "type": name + "_slope",
            "algorithm": "linear",
        }
        dicts.append(dict_slope)

    df_slopes = pd.DataFrame(dicts)

    return df_slopes
```

```python
def loadProcessExport(importfolderpath, metadatapath, outdatapath):
    """
    create dfs and csvs from folder

    """
    dfFolder = importAbfFolder(importfolderpath)

    dfmean = build_dfmean(dfFolder)  # Added 2022-05-24, since required for find_t
    t_volleyslope, t_EPSPslope = find_t(dfFolder, param_min_time_from_t_Stim=0.0005)
    df_metadata = pd.DataFrame(
        {"t_EPSPslope": t_EPSPslope, "t_volleyslope": t_volleyslope}, index=[1]
    )
    df_metadata.to_csv(metadatapath, index=False)

    list_outdata = []
    list_outdata.append(measure_slope(dfFolder, t_EPSPslope, 0.0004, name="EPSP"))
    list_outdata.append(measure_slope(dfFolder, t_volleyslope, 0.0002, name="volley"))
    df_outdata = pd.concat(list_outdata)
    df_outdata.reset_index(drop=True, inplace=True)
    df_outdata.to_csv(outdatapath, index=False)

    return df_metadata, df_outdata


def loadMetadataORprocess(importfolderpath):
    """
    Check for metadata file
    if exists: load
    else: call loadProcessExport

    """
    outdata_path_ending = "_".join(importfolderpath.parts[-2:]) + "_outdata.csv"
    outdatapath = dir_gen_data / outdata_path_ending
    metadata_path_ending = "_".join(importfolderpath.parts[-2:]) + "_metadata.txt"
    metadatapath = dir_gen_data / metadata_path_ending

    if outdatapath.exists():
        print("Exists! Reading...")
        df_metadata = pd.read_csv(metadatapath)
        df_outdata = pd.read_csv(outdatapath)
        print("...done.")
    else:
        print("Doesn't exist! Creating...")
        df_metadata, df_outdata = loadProcessExport(
            importfolderpath, metadatapath, outdatapath
        )
        print("...done.")

    return df_metadata, df_outdata
```

```python
folder1 = dir_source_data / list_folders[1]
print(folder1)
df_metadata, df_outdata = loadMetadataORprocess(folder1)
print(df_metadata)
```

```python
dfFolder = importAbfFolder(folder1)
dfmean = build_dfmean(dfFolder)

fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y="voltage", x="time", ax=ax1, color="black")
h = sns.lineplot(data=dfmean, y="prim", x="time", ax=ax1, color="red")
i = sns.lineplot(data=dfmean, y="bis", x="time", ax=ax1, color="green")
h.axhline(0, linestyle="dotted")
ax1.set_ylim(-0.001, 0.001)
ax1.set_xlim(0.006, 0.02)
#h.axvline(t_VEB, color="orange")
# h.axvline(max_acceptable_t_for_VEB, color='yellow')
h.axvline(t_EPSPslope - 0.0004, color="red")
h.axvline(t_EPSPslope + 0.0004, color="red")
h.axvline(t_volleyslope - 0.0002, color="blue")
h.axvline(t_volleyslope + 0.0002, color="blue")
```

```python
exportpath_outdata.exists()
```

```python
outdata_pathEnding = "_".join(folder1.parts[-2:])
load_process_export(folder1, exportpath_outdata, exportpath_metadata)
```

```python
df_outdata_pivot = df_outdata.pivot(index="sweep", columns="type", values="value")
df_outdata_pivot["ratio_k_EPSP_k_volley"] = (
    df_outdata_pivot.EPSP_slope / df_outdata_pivot.volley_slope.mean()
)
df_outdata_pivot["ratio_k_EPSP_k_volley"].plot()
```

```python
df_metadata
```

```python
df_outdata_pivot[["EPSP_slope", "volley_slope"]].plot()
```

```python
sns.lineplot(data=df_outdata, x="sweep", y="value", hue="type")
```

```python
df_outdata.pivot(index="sweep", columns="type", values="value")
```

```python
"_".join(folder1.parts[-2:])
```

```python
# Obsolete reference "meta_data" -> "df_outdata"

# persist to local file matching data file
# Im generally against putting any created files in the source data folder. I prefer to put them in generated data
# that can be happily wiped and regenerated. let's discuss this later.
dir_outdata = dir_gen_data / "outdata"
dir_outdata.mkdir(parents=True, exist_ok=True)  # create the dir if it does not exist
filepath = dir_outdata / list_files[0]
filepath.with_suffix(".csv")

# def exportData(filepath, df_metadata, df_outdata):
#   df_outdata.to_csv(filepath, index=False)
#    df_metadata.to_csv(filepath, index=False)
#    print(filepath)
# exportData(filepath.with_suffix('.csv'), df_metadata)
```

# Wishlist
* Sanity check for time axis; divide by samplerate?


```python
filepath.parts[-1]
```

```python
pd.read_csv(filepath.with_suffix(".csv"))  # , squeeze = True)
```

```python
# Le SOLVE! Hämtar te...
```
