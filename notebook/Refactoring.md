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
import numpy as np              # numeric calculations module
import pandas as pd             # dataframe module, think excel, but good
import os                       # speak to OS (list dirs)
import matplotlib.pyplot as plt # plotting
import seaborn as sns           # plotting
import pyabf                    # read data files atf, abf
from neo import io              # read data files ibw
import scipy                    # peakfinder and other useful analysis tools
from tqdm.notebook import tqdm
from pathlib import Path
from sklearn import linear_model
```

```python
# set some working folders
dir_project_root = Path(os.getcwd().split('notebook')[0])
dir_source_data = dir_project_root / 'dataSource'
dir_source_data
```

```python
list_folders = [i for i in os.listdir(dir_source_data) if -1<i.find("LTP_")]
list_folders
```

```python
folder1 = dir_source_data / list_folders[0]
folder1
```

```python
list_files = [i for i in os.listdir(folder1) if -1<i.find(".abf")]
list_files
```

```python
# parse abf
abf = pyabf.ABF(dir_source_data / folder1 / list_files[0])
abf
```

```python
abf.setSweep(sweepNumber=239)#, channel=1)
plt.plot(abf.sweepX, abf.sweepY)
plt.show()
```

```python
abf.channelCount
```

```python
abf.channelList
```

```python
abf.data.shape
```

```python
abf.sweepCount
```

```python
abf.sweepChannel
```

```python
abf.sweepX.shape
```

```python

```

```python
channels = abf.channelList
sweeps = range(abf.sweepCount)

dfs = []
for i in channels:
    for j in sweeps:
        # get data
        abf.setSweep(sweepNumber=j, channel=i)
        df = pd.DataFrame({'sweepX': abf.sweepX, 'sweepY': abf.sweepY})
        df['channel'] = i
        df['sweep'] = j
        dfs.append(df)
df = pd.concat(dfs)
df
```

```python
df['even'] = df.sweep.apply(lambda x: x % 2 == 0)
df.reset_index(drop=True, inplace=True)
df
```

```python
dftemp = df[(df.channel == 0) & (df.even == False) & (df.sweep < 10)]
fig, ax = plt.subplots(ncols=1, figsize=(10, 10)) # define the figure and axis we plot in
g = sns.lineplot(data=dftemp, y='sweepY', x= 'sweepX', hue='sweep', ax=ax) # create the plot in that axis
```

```python
def importAbf(filepath, channel=0, oddeven=None):
    '''
    import .abf and return <"odd"/"even"/"all"> sweeps from channel <0/1>
    oddeven defaults to channel-appropriate parameter
    '''
    
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
        df = pd.DataFrame({'sweepX': abf.sweepX, 'sweepY': abf.sweepY})
        df['sweep'] = i
        dfs.append(df)
    df = pd.concat(dfs)
    
    # Convert to SI
    df['time(s)'] = df.sweepX # / abf.sampleRate
    df['voltage(V)'] = df.sweepY / 1000
    
    df['even'] = df.sweep.apply(lambda x: x % 2 == 0)
    df['oddeven'] = df.even.apply(lambda x: 'even' if x else 'odd')
    df = df[df.oddeven == oddeven] # filter rows by Boolean
    df.drop(columns=['sweepX', 'sweepY', 'even', 'oddeven'], inplace=True)
    df.reset_index(drop=True, inplace=True)    
    return df
```

```python
filepath = dir_source_data / folder1 / list_files[0]
df = importAbf(filepath, channel=1)
```

```python
dftemp = df[df.sweep % 10 == 0]
dftemp.nunique()
```

```python
fig, ax = plt.subplots(ncols=1, figsize=(10, 10)) # define the figure and axis we plot in
g = sns.lineplot(data=dftemp, y='voltage(V)', x= 'time(s)', hue='sweep', ax=ax) # create the plot in that axis
```

```python
df
```

# Functions to find EPSP and volley slopes
* Import returns df

* build_dfmean returns dfmean with 3 columns
    1 dfmean (SLOW!)
    2 dfmeandiff
    3 dfmean2diff

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
    '''
    create columns
    dfmean (a single sweep built on the mean of all time(s))
    dfmean.prim
    dfmean.bis    
    
    '''
   
    # Extract mean of time 0 for rough normalization
    voltsAtTime = df[['voltage(V)', 'time(s)']].copy() # fresh copy
    voltsAtTime = voltsAtTime[voltsAtTime['time(s)'] == 0] # keep only 0
    firstmean = voltsAtTime['voltage(V)'].mean() # mean for 0
    
    # Placeholder primitive noob-loop
    dicts = []
    for i in df['time(s)'].unique():
        voltsAtTime = df[['voltage(V)', 'time(s)']].copy() # fresh copy
        voltsAtTime = voltsAtTime[voltsAtTime['time(s)'] == i] # keep only relevant time
        volt = voltsAtTime['voltage(V)'].mean() - firstmean # mean for that time
        dicts.append({'time(s)': i, 'meanVolt': volt})
    dfmean = pd.DataFrame(dicts)
    
    # TODO: Normalize mean - demand Stim-artefact location parameter?
        
    # generate diffs
    dfmean['prim'] = dfmean.meanVolt.diff().rolling(rollingwidth, center=True).mean() * 5
    dfmean['bis'] = dfmean.prim.diff().rolling(rollingwidth, center=True).mean() *5
    
    return dfmean
```

```python
dfmean = build_dfmean(df)
```

```python
dfmean
```

```python
fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='meanVolt', x='time(s)', ax=ax1, color='black')
h = sns.lineplot(data=dfmean, y='prim', x='time(s)', ax=ax1, color='red')
i = sns.lineplot(data=dfmean, y='bis', x='time(s)', ax=ax1, color='green')
h.axhline(0, linestyle='dotted')
ax1.set_ylim(-0.001, 0.001)
ax1.set_xlim(0.0050, 0.02)
```

```python
def findStim(dfmean):
    '''
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returns t_Stim (time of stim artefact)
    '''
    return t_Stim
```

```python
def findEPSP(dfmean, limitleft=0)
    '''
    accepts dfmean, t_Stim (for limit left)
    broadest negative peak on dfmean
    returns t_EPSP (time of WIDEST negative peak center)
    '''
    return t_EPSP
```

```python
def findVEB(dfmean, t_EPSP, param_minimum_width_of_VEB=5):
    '''
    peak of 
    returns x-value (t) for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    '''
    dfmeandiff = dfmean.diff().rolling(3, center=True).mean()

    peaks = scipy.signal.find_peaks(dfmeandiff.volt_normalized, width=param_minimum_width_of_VEB)[0]
    max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
    possible_t_VEB = max(peaks[peaks < max_acceptable_t_for_VEB])
    t_VEB = possible_t_VEB # setting as accepted now, maybe have verification function later
    return t_VEB
```

```python
abf.sampleRate
```

```python
print(dftemp)
```

# Wishlist
* Sanity check for time axis; divide by samplerate?

