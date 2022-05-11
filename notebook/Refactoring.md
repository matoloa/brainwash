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
abf.sampleRate
```

```python
abf.sweepTimesSec
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
        df['t0'] = abf.sweepTimesSec[i]
        dfs.append(df)
    df = pd.concat(dfs)
    
    # Convert to SI
    df['time'] = df.sweepX # / abf.sampleRate
    df['voltage'] = df.sweepY / 1000
    
    df['even'] = df.sweep.apply(lambda x: x % 2 == 0)
    df['oddeven'] = df.even.apply(lambda x: 'even' if x else 'odd')
    df = df[df.oddeven == oddeven] # filter rows by Boolean
    df.drop(columns=['sweepX', 'sweepY', 'even', 'oddeven'], inplace=True)
    df.reset_index(drop=True, inplace=True)    
    return df
```

```python
filepath = dir_source_data / folder1 / list_files[0]
dfabf = importAbf(filepath, channel=0)
```

```python
df
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
def build_dfmean(df, rollingwidth=4):
    '''
    dfmean.voltate(V) (a single sweep built on the mean of all time)
    dfmean.prim
    dfmean.bis    

    dfabf.pivot(columns='time', index='sweep', values='voltage').mean(axis=0).plot()
        
    '''
    
    # More elegant method; can't get it to work (retains all sweeps - not just mean)
    dfmean = pd.DataFrame(df.pivot(columns='time', index='sweep', values='voltage').mean())
    dfmean.columns = ['voltage']
    dfmean.voltage -= dfmean.voltage.median()
    
    # generate diffs, *5 for better visualization
    dfmean['prim'] = dfmean.voltage.diff().rolling(rollingwidth, center=True).mean() * 5
    dfmean['bis'] = dfmean.prim.diff().rolling(rollingwidth, center=True).mean() * 5
    
    return dfmean
```

```python
dfmean = build_dfmean(df)
```

```python
fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='voltage', x='time', ax=ax1, color='black')
h = sns.lineplot(data=dfmean, y='prim', x='time', ax=ax1, color='red')
i = sns.lineplot(data=dfmean, y='bis', x='time', ax=ax1, color='green')
h.axhline(0, linestyle='dotted')
ax1.set_ylim(-0.001, 0.001)
ax1.set_xlim(0.006, 0.03)
```

```python
def findStim(dfmean):
    '''
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returnst_Stim (index of stim artefact)
    '''
    return dfmean['voltage'].idxmax()
```

```python
t_Stim = findStim(dfmean)
print(t_Stim)
dfmean
```

```python
def findEPSP(dfmean, limitleft=0, limitright=-1, param_minimum_width_of_EPSP=2, param_EPSP_prominence=0.00005):
    '''
    width and limits in index, promincence in Volt 
    returns index of center of broadest negative peak on dfmean
    '''
    i_peaks = scipy.signal.find_peaks(-dfmean['voltage'], width=param_minimum_width_of_EPSP, prominence=param_EPSP_prominence)[0]
    # scipy.signal.find_peaks returns a tuple
    dfpeaks = dfmean.iloc[i_peaks]
    #dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    t_EPSP = dfpeaks.index.max()
    
    return t_EPSP
```

```python
t_EPSP = findEPSP(dfmean)#, limitleft=t_Stim)
t_EPSP
```

```python
def findVEB(dfmean, t_EPSP, param_minimum_width_of_VEB=0.0005, param_prim_prominence=0.00005,
            param_minimum_width_of_EPSP=0.005):
    '''
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    '''
    i_peaks = scipy.signal.find_peaks(dfmean.prim, width=param_minimum_width_of_VEB, prominence=param_prim_prominence)[0]
    #print("i_peaks:", i_peaks, len(i_peaks))
    t_peaks = dfmean.iloc[i_peaks].index
    #print("t_peaks:", t_peaks)
    max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
    #print(max_acceptable_t_for_VEB)
    possible_t_VEB = max(t_peaks[t_peaks < max_acceptable_t_for_VEB])
    t_VEB = possible_t_VEB # setting as accepted now, maybe have verification function later
    
    return t_VEB, max_acceptable_t_for_VEB
```

```python
t_VEB, max_acceptable_t_for_VEB = findVEB(dfmean, 0.0132)

```

```python

```

```python
def find_t_EPSPslope(dfmean, t_VEB, t_EPSP):
    '''
    
    '''
    
    dftemp = dfmean.bis[t_VEB: t_EPSP]
    t_EPSPslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if 1 < len(t_EPSPslope):
        raise ValueError("Found multiple positive zero-crossings in dfmean.bis[t_VEB: t_EPSP]")

    return t_EPSPslope[0]
```

```python
t_EPSPslope = find_t_EPSPslope(dfmean,t_VEB, t_EPSP)
t_EPSPslope
```

```python
def find_t_volleyslope(dfmean, t_Stim, t_VEB):#, param_half_slope_width = 4):
    '''
    
    '''
    
    dftemp = dfmean.bis[t_Stim: t_VEB]
    t_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    #print(dftemp.apply(np.sign).diff())
    #print(t_volleyslope)
    if 1 < len(t_volleyslope):
        raise ValueError("Found multiple positive zero-crossings in dfmean.bis[t_Stim: t_VEB]")

    return t_volleyslope[0]
```

```python
t_volleyslope = 0.0084#find_t_volleyslope(dfmean, (t_Stim+0.0005), t_VEB)
```

```python
filepath = dir_source_data / folder1 / list_files[0]
def readraw(filepath=filepath, channel=0):
    df = importAbf(filepath, channel)
    dfmean = build_dfmean(df)
    t_Stim = findStim(dfmean)
    t_EPSP = findEPSP(dfmean)
    t_VEB, max_acceptable_t_for_VEB = findVEB(dfmean, t_EPSP)
    t_EPSPslope = find_t_EPSPslope(dfmean,t_VEB, t_EPSP)
    t_volleyslope = 0.0084#find_t_volleyslope(dfmean, (t_Stim+0.0005), t_VEB)
    
    print(t_volleyslope, t_EPSPslope)
    
    
    return
```

```python
readraw()
```

```python
fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='voltage', x='time', ax=ax1, color='black')
h = sns.lineplot(data=dfmean, y='prim', x='time', ax=ax1, color='red')
i = sns.lineplot(data=dfmean, y='bis', x='time', ax=ax1, color='green')
h.axhline(0, linestyle='dotted')
ax1.set_ylim(-0.001, 0.001)
ax1.set_xlim(0.006, 0.02)
h.axvline(t_VEB, color='orange')
#h.axvline(max_acceptable_t_for_VEB, color='yellow')
h.axvline(t_EPSPslope-0.0004, color='red')
h.axvline(t_EPSPslope+0.0004, color='red')
h.axvline(t_volleyslope-0.0002, color='blue')
h.axvline(t_volleyslope+0.0002, color='blue')
```

```python
def calculate(df, t_volleyslope, halfwidth_volley, t_EPSPslope, halfwidth_EPSP):
    '''
    
    
    '''
    reg = linear_model.LinearRegression()

    dicts = []
    for sweep in tqdm(df.sweep.unique()):
        dftemp1 = df[df.sweep == sweep]
        print(dftemp1)
        dftemp2 = dftemp1[((t_EPSPslope - halfwidth_EPSP) <= dftemp1.index) & (dftemp1.index <= (t_EPSPslope + halfwidth_EPSP))]
        print(dftemp2)
        x = dftemp2.index.values.reshape(-1, 1)
        y = dftemp2.voltage.values.reshape(-1, 1)

        reg.fit(x, y)
        dict_slope = {'sweep': sweep, 'slope': reg.coef_[0][0], 'type': 'linear'}
        dicts.append(dict_slope)

    df_slopes_EPSP = pd.DataFrame(dicts)

    return df_slopes_EPSP
    
```

```python
outdata = calculate(df, 0.0084, 0.0002, 0.0105, 0.0004)
#outdata = calculate(df, t_volleyslope, 0.0002, t_EPSPslope, 0.0004)
outdata
    
```

# Wishlist
* Sanity check for time axis; divide by samplerate?


```python

```
