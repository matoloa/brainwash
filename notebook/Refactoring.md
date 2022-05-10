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
df = importAbf(filepath, channel=0)
```

```python
#dftemp = df[df.sweep % 10 == 0]
#dftemp.nunique()
```

```python
#fig, ax = plt.subplots(ncols=1, figsize=(10, 10)) # define the figure and axis we plot in
#g = sns.lineplot(data=dftemp, y='voltage(V)', x= 'time(s)', hue='sweep', ax=ax) # create the plot in that axis
```

```python
df
```

<!-- #region -->
# Functions to find EPSP and volley slopes
* INCOSISTENT NAMING: t or time(s) used when code works on INDEX


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
<!-- #endregion -->

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
    
    # Placeholder noob-loop
    dicts = []
    for i in df['time(s)'].unique():
        voltsAtTime = df[['voltage(V)', 'time(s)']].copy() # fresh copy
        voltsAtTime = voltsAtTime[voltsAtTime['time(s)'] == i] # keep only relevant time
        volt = voltsAtTime['voltage(V)'].mean() - firstmean # mean for that time
        dicts.append({'time(s)': i, 'meanVolt': volt}) # add to dict
    dfmean = pd.DataFrame(dicts) # dataframe from dict
    
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
ax1.set_xlim(0.006, 0.02)
```

```python
def findStim(dfmean):
    '''
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returns t_Stim (index of stim artefact)
    '''
    return dfmean[['meanVolt']].idxmax()
```

```python
t_Stim = findStim(dfmean)
t_Stim
```

```python
def findEPSP(dfmean, limitleft=0, limitright=-1, param_minimum_width_of_EPSP=50, param_EPSP_prominence=0.0005):
    '''
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    '''
    peaks = scipy.signal.find_peaks(-dfmean.meanVolt, width=param_minimum_width_of_EPSP, prominence=param_EPSP_prominence)[0]#[0]
    # scipy.signal.find_peaks returns a tuple
    # peaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    # peaks = peaks[peaks[0] > limitleft] # ERROR - won't work
    # Can't get stuck - just return the one with the highest index, for now.
    t_EPSP = peaks.max()
    return t_EPSP
```

```python
t_EPSP = findEPSP(dfmean, limitleft=t_Stim)
t_EPSP
```

```python
def findVEB(dfmean, t_EPSP, param_minimum_width_of_VEB=5, param_minimum_width_of_EPSP=50):
    '''
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    '''
    peaks = scipy.signal.find_peaks(dfmean.prim, width=param_minimum_width_of_VEB)[0]
    print(peaks)
    max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
    print(max_acceptable_t_for_VEB)
    possible_t_VEB = max(peaks[peaks < max_acceptable_t_for_VEB])
    t_VEB = possible_t_VEB # setting as accepted now, maybe have verification function later
    return t_VEB
```

```python
t_VEB = findVEB(dfmean, t_EPSP)
t_VEB
```

```python
def findEPSPslope(dfmean, t_VEB, t_EPSP, param_t_VEB_margin=3, param_half_slope_width = 4):
    dftemp = dfmean[t_VEB+param_t_VEB_margin: t_EPSP]
    '''
    # Presumably better method that I do not understand:
    t_to_look_for_EPSP_slope = dftemp[dftemp.bis.apply(np.sign)==1].iloc[0].name
    slope_t_EPSP = {'begin': t_to_look_for_EPSP_slope - param_half_slope_width,
                        'end': t_to_look_for_EPSP_slope + param_half_slope_width}
    dfplot_EPSP_slope = dfmean.bis.loc[slope_t_EPSP['begin']: slope_t_EPSP['end']]
    EPSPslope = dfplot_EPSP_slope
    
    # TODO: fix DYSFUNCTIONAL
    return EPSPslope
    #return EPSPslope.index[param_half_slope_width]
    '''
    
    # Placeholder loop returns index of first positive bis within range, or -1 if none is found 
    for i in dftemp.index:
        if dftemp.bis[i] > 0:
            return i
    return -1
```

```python
EPSPslope = findEPSPslope(dfmean, t_VEB, t_EPSP)
EPSPslope
```

# Wishlist
* Sanity check for time axis; divide by samplerate?

