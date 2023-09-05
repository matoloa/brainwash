---
jupyter:
  jupytext:
    formats: ipynb,py
    text_representation:
      extension: .py
      format_name: python
      format_version: '1.3'
      jupytext_version: 1.13.1
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

```python
import os  # speak to OS (list dirs)
from pathlib import Path

import matplotlib.pyplot as plt  # plotting
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
import scipy  # peakfinder and other useful analysis tools
import seaborn as sns  # plotting
from neo import io  # read data files ibw
from sklearn import linear_model
from sklearn.linear_model import HuberRegressor
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
dir_project_root = Path(os.getcwd().split('notebook')[0])
dir_source_data = dir_project_root / 'dataSource'
dir_source_data
```

```python

```

```python
os.listdir(dir_source_data / 'LTP induction-20211124T114212Z-001/LTP induction/tg')
```

```python
atf = pyabf.ATF(dir_source_data / 'LTP induction-20211124T114212Z-001/LTP induction/tg/' / '042ca.atf')

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
abf = pyabf.ABF(dir_source_data / '02GKO/1a IO SR/' / '2022_01_24_0002.abf')
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
ibw = io.IgorIO(dir_source_data / 'C02-20190706D3' / '161117_slice_0_input1_001.ibw')

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



file_atf = dir_source_data / 'WT_062.atf'
file_abf = dir_source_data / '02GKO/1a IO SR' / '2022_01_24_0002.abf'
file_ibw = dir_source_data / 'C02-20190706D3' / '161117_slice_0_input1_001.ibw'
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

#fig, ax = plt.subplots(ncols=1, figsize=(10, 10)) # define the figure and axis we plot in
#g = sns.lineplot(data=df1stack, y='volt', x= 'time', hue='sweep', ax=ax) # create the plot in that axis
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
# peakfinder experiments
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
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', color='tab:blue', ax=ax)
g.axhline(0, linestyle='dotted')


ax.set_ylim(-1.8, 0.2)
```

```python
dfmean
```

```python
dfmeandiff = dfmean.diff().rolling(3, center=True).mean()
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
t_EPSP = scipy.signal.find_peaks(-dfmean.volt_normalized, width=param_minimum_width_of_EPSP, prominence=param_prominence)[0][0]
t_EPSP
```

```python
param_minimum_width_of_VEB = 5
peaks = scipy.signal.find_peaks(dfmeandiff.volt_normalized, width=param_minimum_width_of_VEB)[0]
max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
possible_t_VEB = max(peaks[peaks < max_acceptable_t_for_VEB])
t_VEB = possible_t_VEB # setting as accepted now, maybe have verification function later
```

```python
peaks
```

```python
# find 0 crossing of 2nd derivative to find straightest slope at beginning of EPSP event
dftemp = dfmean[t_VEB: t_EPSP]
# pick the first one that gets positive sign in 2nd derivative
t_to_look_for_EPSP_slope = dftemp[dftemp.volt_normalized.diff().diff().apply(np.sign)==1].iloc[0].name
param_half_slope_width = 4
slope_t_EPSP = {'begin': t_to_look_for_EPSP_slope - param_half_slope_width,
                    'end': t_to_look_for_EPSP_slope + param_half_slope_width}
#TODO: this interval is not symmetric as param half width incorrectly implies, correct.
dfplot_EPSP_slope = dfmean.loc[slope_t_EPSP['begin']: slope_t_EPSP['end']]
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
reg2.fit(x[2:-3],y[2:-3]) # only using a shorter span to see how much it affects the slope

reg.coef_, reg.intercept_
yslope = x * reg.coef_ + reg.intercept_
dffit_EPSP_slope = pd.DataFrame({'x': x.flatten(), 'yslope': yslope.flatten()})
dffit_EPSP_slope
```

```python
reg.coef_, reg.intercept_, reg2.coef_, reg2.intercept_


```

```python

```

```python
y = [i[0] for i in dfmean.loc[[t_EPSP, t_VEB]].values]
dictplot = {'x': [t_EPSP, possible_t_VEB], 'y': y}
dfplot = pd.DataFrame(dictplot)
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax, color='black')
h = sns.scatterplot(data=dfplot, x='x', y='y')
i = sns.lineplot(data=dfplot_EPSP_slope, y='volt_normalized', x='time', ax=ax, color='red')
j  = sns.lineplot(data=dffit_EPSP_slope, y='yslope', x='x', ax=ax, color='blue')


ax.set_xlim(possible_t_VEB - 30, t_EPSP + 30)
ax.set_ylim(-1, .5)

# LEFT OFF HERE.
# Found VEB by running peakfinder on first diff by moving left from EPSP valley
# Then using 2nd derivative (diff) first 0 crossing from left, find EPSP slope area.
# linear regression to get EPSP slope
```

```python
slope_t_EPSP
```

# Roadmap
* Found EPSP slope time coord
* Assume similar for all sweeps
* Calculate slope for all sweeps
* plot

```python

```

```python
# for all sweeps loop and find the sloop, store in dict and make df for plotting
reg = linear_model.LinearRegression()
#huber = HuberRegressor()
dicts = []
for sweep in tqdm(df1stack.sweep.unique()):
    dftemp1 = df1stack[df1stack.sweep == sweep]
    dftemp2 = dftemp1[(slope_t_EPSP['begin'] <= dftemp1.time) & (dftemp1.time <= slope_t_EPSP['end'])]
    
    x = dftemp2.time.values.reshape(-1, 1)
    y = dftemp2.volt.values.reshape(-1, 1)

    reg.fit(x, y)
    dict_slope = {'sweep': sweep, 'slope': reg.coef_[0][0], 'type': 'linear'}
    dicts.append(dict_slope)
    
#    huber.epsilon = 1.1
#    huber.fit(x, y.ravel())    
#    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1'}
#    dicts.append(dict_slope)
#    
#    huber.epsilon = 1.35
#    huber.fit(x, y.ravel())    
#    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1.35'}
#    dicts.append(dict_slope)
#    
#    huber.epsilon = 1.7
#    huber.fit(x, y.ravel())    
#    dict_slope = {'sweep': sweep, 'slope': huber.coef_[0], 'type': 'huber1.7'}
#    dicts.append(dict_slope)


df_slopes_EPSP = pd.DataFrame(dicts)
```

```python
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
sns.scatterplot(data=df_slopes_EPSP, x='sweep', y='slope', hue='type', ax=ax)
```

```python

```

```python

```

# wishlist
* stabilise slope
* remove noise



# roadmap
* find and calculate volley
* requirement, VEB is present and found

```python
dfmean
```

```python
# extra plot to guide visual

fig, ax1 = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax1, color='black')
h = sns.lineplot(data=dfmeandiff*5, y='volt_normalized', x='time', ax=ax1, color='red')
i = sns.lineplot(data=dfmean2diff*15, y='volt_normalized', x='time', ax=ax1, color='green')
j = sns.lineplot(data=dfmean3diff.rolling(8, center=True).mean()*50, y='volt_normalized', x='time', ax=ax1, color='blue')
h.axhline(0, linestyle='dotted')
ax1.set_ylim(-.1, 0.1)
ax1.set_xlim(t_VEB - 20, t_VEB)
ax1.grid(b=True, which='major', color='black', linewidth=0.075)
ax1.grid(b=True, which='minor', color='black', linewidth=0.075)
plt.xticks(list(range(85, 103)))

```

```python
# use VEB coord
# find min if 1st derivative in search width before VEB to calculate slope of Volley
param_search_width_volley = 10
dftemp = dfmean[t_VEB - param_search_width_volley: t_VEB]
# find min if 1st derivative
t_to_look_for_slope_Volley = dftemp.iloc[dftemp.volt_normalized.diff().argmin()].name
param_slope_half_width = 2
slope_t_Volley = {'begin': t_to_look_for_slope_Volley - param_slope_half_width,
                    'end': t_to_look_for_slope_Volley + param_slope_half_width}

dfplot_Volley_slope = dfmean.loc[slope_t_Volley['begin']: slope_t_Volley['end']]
dfplot_Volley_slope
```

```python
# get linear regression
reg = linear_model.LinearRegression()

x = dfplot_Volley_slope.index.values.reshape(-1, 1)
y = dfplot_Volley_slope.values.reshape(-1, 1)

reg.fit(x, y)

reg.coef_, reg.intercept_
yslope = x * reg.coef_ + reg.intercept_
dffit_Volley_slope = pd.DataFrame({'x': x.flatten(), 'yslope': yslope.flatten()})
dffit_Volley_slope
```

```python
reg.coef_, reg.intercept_

```

```python
y = [i[0] for i in dfmean.loc[[t_EPSP, t_VEB]].values]
dictplot = {'x': [t_EPSP, possible_t_VEB], 'y': y}
dfplot = pd.DataFrame(dictplot)
fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.lineplot(data=dfmean, y='volt_normalized', x='time', ax=ax, color='black')
h = sns.scatterplot(data=dfplot, x='x', y='y')
i = sns.lineplot(data=dfplot_EPSP_slope, y='volt_normalized', x='time', ax=ax, color='red')
j  = sns.lineplot(data=dffit_EPSP_slope, y='yslope', x='x', ax=ax, color='blue')
k = sns.lineplot(data=dfplot_Volley_slope, y='volt_normalized', x='time', ax=ax, color='red')
l  = sns.lineplot(data=dffit_Volley_slope, y='yslope', x='x', ax=ax, color='blue')



ax.set_xlim(possible_t_VEB - 30, t_EPSP + 30)
ax.set_ylim(-1, .5)

```

```python
# for all sweeps loop and find the sloop, store in dict and make df for plotting
reg = linear_model.LinearRegression()
dicts = []
for sweep in tqdm(df1stack.sweep.unique()):
    dftemp1 = df1stack[df1stack.sweep == sweep]
    dftemp2 = dftemp1[(slope_t_Volley['begin'] <= dftemp1.time) & (dftemp1.time <= slope_t_Volley['end'])]
    
    x = dftemp2.time.values.reshape(-1, 1)
    y = dftemp2.volt.values.reshape(-1, 1)

    reg.fit(x, y)
    dict_slope = {'sweep': sweep, 'slope': reg.coef_[0][0], 'type': 'linear'}
    dicts.append(dict_slope)
    

df_slopes_Volley = pd.DataFrame(dicts)
```

```python
df_df_slopes_Volley_roll = df_slopes_Volley.copy()
df_df_slopes_Volley_roll['slope'] = df_df_slopes_Volley_roll.slope.rolling(3, center=True).mean()
df_df_slopes_Volley_roll['type'] = 'Volley'
df_slopes_EPSP['type'] = 'EPSP'
df_slopes_EPSP
dfplot = pd.concat([df_df_slopes_Volley_roll, df_slopes_EPSP])



fig, ax = plt.subplots(ncols=1, figsize=(20, 10))
g = sns.scatterplot(data=dfplot, x='sweep', y='slope', hue='type', ax=ax)
g.axhline(-0.016, linestyle='dotted')

```

```python
df_slopes_Volley.mean()
```

# wishlist
* volley test, is volley same through whole experiment
* possible solutions check if windowed distributions are the same at being / end

```python
df_df_slopes_EPSP_roll = df_slopes_EPSP.copy()
df_df_slopes_EPSP_roll['slope'] = df_df_slopes_EPSP_roll.slope.rolling(10, center=True, win_type='gaussian').mean(std=10)
df_df_slopes_EPSP_roll.slope.plot()
```

```python

```
