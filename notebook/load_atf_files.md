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

```python

```

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

```

# Roadmap
* parse atf och abf
* load data into DataFrame structure
* normalize sweeps
* find important metadata from raw data

* identify and measure VEB, EPSP
* remove noise
* find volley


```python
# set some working folders
dir_project_root = os.getcwd().split('notebook')[0]
dir_source_data = dir_project_root + 'dataSource'
```

```python

```

```python
os.listdir(dir_source_data + '/LTP induction-20211124T114212Z-001/LTP induction/tg')
```

```python
atf = pyabf.ATF(dir_source_data + '/LTP induction-20211124T114212Z-001/LTP induction/tg/' + '042ca.atf')

```

```python
# check the atf objects builtin command for string representation (all modules should have __str__() and __repr__())
atf.__str__()
```

```python
print(atf.header) # display header information in the console

```

```python
atf.setSweep(1)
```

```python
# test, use builtin object setSweep function and plot
atf.setSweep(20)
plt.plot(atf.sweepX, atf.sweepY)
plt.show()
```

```python
# make DataFrame of sweep data
df_sweep = pd.DataFrame(atf.sweepY, columns=['y'])
df_sweep['x'] = atf.sweepX
df_sweep
```

```python
# parse abf
abf = pyabf.ABF(dir_source_data + '/02GKO/1a IO SR/' + '2022_01_24_0002.abf')
```

```python
abf.__repr__()
```

```python
print(abf)
```

```python
abf.setSweep(17)
plt.plot(abf.sweepX, abf.sweepY)
plt.show()
```

```python

```

```python
ibw = io.IgorIO(dir_source_data + '/C02-20190706D3/' + '161117_slice_0_input1_001.ibw')

```

```python
ibw.readable_objects
```

```python
ibw.read_block()
```

```python
ibw.read_segment()
```

```python
ibw.read_analogsignal()
```

```python
signal = ibw.read_analogsignal()
plt.plot(signal.times, signal.as_array())
```

```python
# define experimenta convenience functions to read metadata from files and put in overview structure

def splitFileNamePath(path):
    folders, filename = os.path.split(path)
    return folders, filename


def collectMetadataAbf(file):
    abf = pyabf.ABF(file)                                     # load file into object
    out = pd.Series(dtype='object')                           # create empty series
    out['info'] = abf.__str__()                               # put object info into series
    out['folders'], out['filename'] = splitFileNamePath(file) # put file info into series
    return out
    

def collectMetadataAtf(file):
    atf = pyabf.ATF(file)
    out = pd.Series(dtype='object')
    out['info'] = atf.__str__()
    out['folders'], out['filename'] = splitFileNamePath(file)
    return out



file_atf = dir_source_data + '/WT_062.atf'
file_abf = dir_source_data + '/02GKO/1a IO SR/' + '2022_01_24_0002.abf'
file_ibw = dir_source_data + '/C02-20190706D3/' + '161117_slice_0_input1_001.ibw'
out1 = collectMetadataAtf(file_atf)
out2 = collectMetadataAbf(file_abf)
```

```python
out1
```

```python
# test to put individual info series together in overview dataframe
pd.concat([out1, out2], axis=1).transpose()
```

# Start experiments with loading, analyzing and visualizing data

```python
atf = pyabf.ATF(file_atf)        # load data file
dfatf = pd.DataFrame(atf.data)   # put data from object in dataframe
dfatf
```

```python
# make smaller development dataframe, faster prototyping
df1 = dfatf.iloc[:2000, :]
df1
```

```python
# reshape the dataframe to a more convenient shape
df1stack = pd.DataFrame(df1.stack())
df1stack.reset_index(inplace=True)
df1stack.columns = ['sweep', 'time', 'volt'] # put names on the columns
df1stack
```

```python
# quick vis to know what we have
fig, ax = plt.subplots(ncols=1, figsize=(10, 10)) # define the figure and axis we plot in
g = sns.lineplot(data=df1stack, y='volt', x= 'time', hue='sweep', ax=ax) # create the plot in that axis
```

```python
'''
Notes: what we are after here
lutning hos stora bumpens leading edge (on little bump 8 point freq)
slope of first little bump maybe 4 points mean
amplitude of bumps from baseline
only tickle the synapsis, but not trigger
use only beginning for normalizing
autodetect stim artefact
'''

```

```python

```

```python

```

```python

```

```python

```

```python
# peadnfinder experiments
df = df1stack[df1stack.sweep==0]
index = scipy.signal.find_peaks(df.volt, height=2)
dfvolt = df.iloc[index[0]]
```

```python
# find the stim artefact by max diff
df = df1stack[df1stack.sweep==0].copy()
df['voltdiff'] = df.volt.diff()
idxmax = df.voltdiff.idxmax()
dfvolt = pd.DataFrame({'time': idxmax, 'volt': df.iloc[idxmax].volt}, index=[1])
```

```python
# visualize peak finding results
fig, ax = plt.subplots(ncols=1, figsize=(5, 5))
g = sns.scatterplot(data=df, x='time', y='volt', ax=ax)
g = sns.scatterplot(data=dfvolt, x='time', y='volt', ax=ax)
```

```python
# loop through all the sweeps one by one and find the median of the voltage up to 5 points before stim
dicts = []
for sweep in df1stack.sweep.unique():
    df = df1stack[df1stack.sweep == sweep].copy()
    df.sort_values('time', inplace=True)
    volt_start = df.volt[:idxmax-5].median()
    dicts.append({'sweep': sweep, 'volt_start': volt_start})
df = pd.DataFrame(dicts)
df
```

```python
# join in the found start voltages into the big df, similar to SQL join.
df1stackjoin = df1stack.join(df, on='sweep', lsuffix='', rsuffix='_r')
```

```python
df1stackjoin['volt_normalized'] = df1stackjoin.volt - df1stackjoin.volt_start
```

```python
dfmean = df1stackjoin.groupby('time').volt_normalized.std()
```

```python
# find mean of all measurements
dfmean = df1stackjoin.groupby('time').volt_normalized.mean() # gives a series with the mean values
dfmean = pd.DataFrame(dfmean) # need a dataframe for plotting, i think
dfstd = df1stackjoin.groupby('time').volt_normalized.std()
dfstd = pd.DataFrame(dfstd) # need a dataframe for plotting, i think
dfstd
```

```python
# visualise all measurement point and overlay the calculated mean
# downsample before or after analysis and vis?
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.scatterplot(data=df1stackjoin, y='volt_normalized', x='time', color='y', ax=ax, s=50, alpha=0.02)
g = sns.lineplot(data=dfmean+dfstd, y='volt_normalized', x='time', color='tab:orange', ax=ax)
g = sns.lineplot(data=dfmean-dfstd, y='volt_normalized', x='time', color='tab:orange', ax=ax)
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax)
g.axhline(0, linestyle='dotted')


ax.set_ylim(-1.8, 0.2)
```

```python
dfmeandiff = dfmean.diff().rolling(4, center=True).mean()
dfmean2diff = dfmeandiff.diff()
dfmean3diff = dfmean2diff.diff()


fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax1, color='black')
h = sns.lineplot(data=dfmeandiff*5, y='volt_normalized', x='time', ax=ax1, color='red')
i = sns.lineplot(data=dfmean2diff*15, y='volt_normalized', x='time', ax=ax1, color='green')
j = sns.lineplot(data=dfmean3diff.rolling(8, center=True).mean()*50, y='volt_normalized', x='time', ax=ax1, color='blue')
h.axhline(0, linestyle='dotted')
ax1.set_ylim(-1.2, 0.5)
ax1.set_xlim(50, 300)
```

```python
dfmeandiff.rolling(8).mean()
```

```python
# find Excitatorisk PostSynaptisk Potential (EPSP)
# as close to Volley EPSP Bump, but not with the rounding
# assume that EPSP is the biggest bump

fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax1, color='black')

```

```python
param_minimum_width_of_EPSP = 50
param_prominence = .5
scipy.signal.find_peaks(-dfmean.volt_normalized, width=param_minimum_width_of_EPSP, prominence=param_prominence)
```

```python
param_minimum_width_of_EPSP = 50
param_prominence = .5
time_coord_of_EPSP = scipy.signal.find_peaks(-dfmean.volt_normalized, width=param_minimum_width_of_EPSP, prominence=param_prominence)[0][0]
time_coord_of_EPSP
```

```python
param_minimum_width_of_VEB = 5
peaks = scipy.signal.find_peaks(dfmeandiff.volt_normalized, width=param_minimum_width_of_VEB)[0]
max_acceptable_coord_for_VEB = time_coord_of_EPSP - param_minimum_width_of_EPSP / 2
possible_VEB_coord = max(peaks[peaks < max_acceptable_coord_for_VEB])
possible_VEB_coord
```

```python
peaks
```

```python
# find 0 crossing of 2nd derivative to find straightest slope at beginning of EPSP event
dftemp = dfmean[possible_VEB_coord: time_coord_of_EPSP]
# pick the first one that gets positive sign in 2nd derivative
coord_to_look_for_EPSP_slope = dftemp[dftemp.volt_normalized.diff().diff().apply(np.sign)==1].iloc[0].name
param_half_slope_width = 4
coord_EPSP_slope = {'begin': coord_to_look_for_EPSP_slope - param_half_slope_width,
                    'end': coord_to_look_for_EPSP_slope + param_half_slope_width}

dfplot_EPSP_slope = dfmean.loc[coord_EPSP_slope['begin']: coord_EPSP_slope['end']]
dfplot_EPSP_slope
```

```python
# get linear regression
from sklearn import linear_model
reg = linear_model.LinearRegression()
reg2 = linear_model.LinearRegression()

x = dfplot_EPSP_slope.index.values.reshape(-1, 1)
y = dfplot_EPSP_slope.values.reshape(-1, 1)

reg.fit(x, y)
reg2.fit(x[2:-3],y[2:-3])

reg.coef_, reg.intercept_
yslope = x * reg.coef_ + reg.intercept_
dffitslope = pd.DataFrame({'x': x.flatten(), 'yslope': yslope.flatten()})
dffitslope
```

```python
reg.coef_, reg.intercept_, reg2.coef_, reg2.intercept_


```

```python
y = [i[0] for i in dfmean.loc[[time_coord_of_EPSP, possible_VEB_coord]].values]
dictplot = {'x': [time_coord_of_EPSP, possible_VEB_coord], 'y': y}
dfplot = pd.DataFrame(dictplot)
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax, color='black')
h = sns.scatterplot(data=dfplot, x='x', y='y')
i = sns.lineplot(data=dfplot_EPSP_slope, y='volt_normalized', x='time', ax=ax, color='red')
j  = sns.lineplot(data=dffitslope, y='yslope', x='x', ax=ax, color='blue')


ax.set_xlim(possible_VEB_coord - 30, time_coord_of_EPSP + 30)
ax.set_ylim(-1, .5)

# LEFT OFF HERE.
# Found VEB by running peakfinder on first diff by moving left from EPSP valley
# Then using 2nd derivative (diff) first 0 crossing from left, find EPSP slope area.
# linear regression to get EPSP slope
```

```python
coord_EPSP_slope
```

# Roadmap
* Found EPSP slope time coord
* Assume similar for all sweeps
* Calculate slope for all sweeps
* plot

```python
from sklearn.linear_model import HuberRegressor
huber = HuberRegressor()
```

```python
dicts = []
for sweep in tqdm(df1stack.sweep.unique()):
    dftemp1 = df1stack[df1stack.sweep == sweep]
    dftemp2 = dftemp1[(coord_EPSP_slope['begin'] <= dftemp1.time) & (dftemp1.time <= coord_EPSP_slope['end'])]
    
    x = dftemp2.time.values.reshape(-1, 1)
    y = dftemp2.volt.values.reshape(-1, 1)

    reg.fit(x, y)
    dict_slope = {'sweep': sweep, 'slope': reg.coef_[0][0], 'type': 'linear'}
    dicts.append(dict_slope)
    
    huber.epsilon = 1.1
    huber.fit(x, y.ravel())    
    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1'}
    dicts.append(dict_slope)
    
    huber.epsilon = 1.35
    huber.fit(x, y.ravel())    
    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1.35'}
    dicts.append(dict_slope)
    
    huber.epsilon = 1.7
    huber.fit(x, y.ravel())    
    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1.7'}
    dicts.append(dict_slope)


df_slopes = pd.DataFrame(dicts)
```

```python
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
sns.scatterplot(data=df_slopes, x='sweep', y='slope', hue='type', ax=ax)
```

```python

```

```python

```

# wishlist
* stabilise slope
* remove noise


```python

```
