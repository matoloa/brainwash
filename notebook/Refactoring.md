---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.13.8
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

# Roadmap
* Groups: folders can belong to one, two or more Groups.
* Array of Include-in-group Booleans, method (manual / “basic”)
    * Metadata generation obsolete - leave for now
    * Experiment.csv
    * updatemetadata(folder) metadata.csv
        * Folder, t_EPSP, method, ok,  t_volley, method, ok, t_VEB
* Function to display average EPSP/volley (SEM shade) of all folders in a Group
* Function to display mean of Group1 vs mean of Group2
* Function to display all outdata (EPSP, volley or EPSP/volley) in a Group, superimposed
* Function to display Sample sweeps from first 10 and last 10 of each source file, superimposed, reading points indicated

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
list_folders = [i for i in os.listdir(dir_source_data) if -1 < i.find("")]
list_folders
```

```python
def buildexperimentcsv(dir_gen_data):
    """
    Generate overview file of all csv:s
    Assumes no such file exists
    Add later: functions to check for not-included-folders, convert those

    """
    list_metadatafiles = [i for i in os.listdir(dir_gen_data) if -1 < i.find("_metadata.txt")]
    # Read groups and assigment from metadata.txt
    # Later: read applied algorithm from metadata.txt into df
    
    
    dfmetadata = pd.read_csv(metadatapath)
    
    
```

```python
list_metadatafiles = [i for i in os.listdir(dir_gen_data) if -1 < i.find("_metadata.txt")]
list_metadatafiles
```

```python

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
    DOES NOT USE WIDTH! decided by rolling, earlier?
    
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
    return t_volleyslope[0]
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

    return t_volleyslope, t_EPSPslope, dfmean
```

```python
def measure_slope(df, t_slope, halfwidth, name="EPSP"):
    """
    Generalized function


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
def ProcessExport(importfolderpath, meandatapath, metadatapath, outdatapath):
    """
    create dfs and csvs from folder
    
    metadata.txt contents
        Folderpath
        Exclude (boolean)
        List of Algorithms
        Chosen Algorithm
        Groups (list)
        
        t_EPSPslope
        t_volleyslope

    

    """
    dfFolder = importAbfFolder(importfolderpath)
    t_volleyslope, t_EPSPslope, dfmean = find_t(dfFolder, param_min_time_from_t_Stim=0.0005)
    dfmetadata = pd.DataFrame(
        {"Folderpath": importfolderpath,
         "Exclude": False,
         "Applied algorithms": None,
         "Chosen algorithm": None,
         "Groups": None,
         "t_EPSPslope": t_EPSPslope,
         "t_volleyslope": t_volleyslope
        }, index=[1]
    )

    list_outdata = []
    list_outdata.append(measure_slope(dfFolder, t_EPSPslope, 0.0004, name="EPSP"))
    list_outdata.append(measure_slope(dfFolder, t_volleyslope, 0.0002, name="volley"))
    dfoutdata = pd.concat(list_outdata)
    dfoutdata.reset_index(drop=True, inplace=True)
    
    dfmean.to_csv(meandatapath)
    dfmetadata.to_csv(metadatapath, index=False)
    dfoutdata.to_csv(outdatapath, index=False)

    return dfmean, dfmetadata, dfoutdata


def loadMetadataORprocess(importfolderpath):
    """
    Check for metadata file
    if exists: load
    else: call ProcessExport

    """
    meandata_path_ending = "_".join(importfolderpath.parts[-2:]) + "_meandata.csv"
    meandatapath = dir_gen_data / meandata_path_ending
    metadata_path_ending = "_".join(importfolderpath.parts[-2:]) + "_metadata.txt"
    metadatapath = dir_gen_data / metadata_path_ending
    outdata_path_ending = "_".join(importfolderpath.parts[-2:]) + "_outdata.csv"
    outdatapath = dir_gen_data / outdata_path_ending

    
    if meandatapath.exists():
        print("Found", outdata_path_ending, "- Reading...")
        dfmean = pd.read_csv(meandatapath)
        dfmetadata = pd.read_csv(metadatapath)
        dfoutdata = pd.read_csv(outdatapath)
        #print("...done.")
    else:
        print("No", outdata_path_ending, "- Creating...")
        dfmean, dfmetadata, dfoutdata = ProcessExport(
            importfolderpath, meandatapath, metadatapath, outdatapath
        )
        #print("...done.")

    return dfmean, dfmetadata, dfoutdata
```

```python
def plotmean(dfmean_in, t, title=None, t_VEB=None):
    '''
    
    '''
    dfmean = dfmean_in.copy() # Create local copy to make sure original is untouched
    dfmean.reset_index(inplace=True) # Reset index in local copy to make graphs happy
    t_EPSPslope = t['t_EPSPslope']
    t_volleyslope = t['t_volleyslope']

    fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
    g = sns.lineplot(data=dfmean, y='voltage', x='time', ax=ax1, color='black')
    h = sns.lineplot(data=dfmean, y='prim', x='time', ax=ax1, color='red')
    i = sns.lineplot(data=dfmean, y='bis', x='time', ax=ax1, color='green')
    h.axhline(0, linestyle='dotted')
    if not title is None:
        ax1.set_title(title)
    ax1.set_ylim(-0.001, 0.001)
    ax1.set_xlim(0.006, 0.02)
    if not t_VEB is None:
        h.axvline(t_VEB, color='orange')
        #h.axvline(max_acceptable_t_for_VEB, color='yellow')
    h.axvline(t_EPSPslope-0.0004, color='purple')
    h.axvline(t_EPSPslope, color='purple')
    h.axvline(t_EPSPslope+0.0004, color='purple')
    h.axvline(t_volleyslope-0.0001, color='blue')
    h.axvline(t_volleyslope, color='blue')
    h.axvline(t_volleyslope+0.0001, color='blue')
```

```python
print(list_folders)
for i in list_folders:
    folder1 = dir_source_data / i
    dfmean, dfmetadata, dfoutdata = loadMetadataORprocess(folder1)
    t = dfmetadata.iloc[0].to_dict()
    #print(dfmean)
    plotmean(dfmean, t, title=i)
```

```python
dfoutdata
#dfmean
```

```python
print(list_folders)
```

```python
#list_folders = [i for i in os.listdir(dir_source_data) if -1 < i.find("")]
list_GKO = [i for i in list_folders if -1 < i.find("GKO")]
list_WT = [i for i in list_folders if -1 < i.find("WT")]
```

```python
print(dir_source_data)
dir_source_data.__str__().split('\\')
```

```python
list_WT, list_GKO
```

```python
t
```

```python
sns.lineplot(data=dfoutdata, x = 'sweep', y = 'value', hue = 'type')
```

```python
def getgroupdata(pathfolders:list):
    """
    loadMetadtaORprocess all <pathfolders>
    return concatenated df : outdata with added 'name' = (last two folder levels)
    """
    dfoutdatas = []
    #print(pathfolders)
    for i in pathfolders:
        name = '/'.join(i.__str__().split('\\')[-2:])
        dfmean, dfmetadata, dfoutdata = loadMetadataORprocess(i)
        dfoutdata['name'] = name
        dfoutdatas.append(dfoutdata)
        print(i, "NAME", name)
        #plotmean(dfmean, t, title=i)
    dfoutdata = pd.concat(dfoutdatas)
    dfoutdata.reset_index(drop=True, inplace=True)
    return dfoutdata
```

```python
listpathWT = [dir_source_data /i for i in os.listdir(dir_source_data) if -1 < i.find("WT")]
dfoutdataWT = getgroupdata(listpathWT)
print(dfoutdataWT)
sns.lineplot(data=dfoutdataWT, x = 'sweep', y = 'value', hue = 'type')
listpathGKO = [dir_source_data /i for i in os.listdir(dir_source_data) if -1 < i.find("GKO")]
dfoutdataGKO = getgroupdata(listpathGKO)
sns.lineplot(data=dfoutdataGKO, x = 'sweep', y = 'value', hue = 'type')
```

```python
dfoutdataWT['group'] = 'WT'
dfoutdataGKO['group'] = 'GKO'
dfoutdata = pd.concat([dfoutdataWT, dfoutdataGKO]).reset_index(drop=True)
sns.lineplot(data=dfoutdata, x = 'sweep', y = 'value', hue = 'group', style = 'type')
```

```python
dfoutdata.head()
```

```python

```
