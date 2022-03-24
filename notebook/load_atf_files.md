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
import numpy as np              # numeric calculations module
import pandas as pd             # dataframe module, think excel, but good
import os                       # speak to OS (list dirs)
import matplotlib.pyplot as plt # plotting
import seaborn as sns           # plotting
import pyabf                    # read data files atf, abf
from neo import io              # read data files ibw
import scipy                    # peanfinder and other useful analysis tools
```

# Roadmap
* parse atf och abf
* load data into DataFrame structure
* normalize sweeps
* find important metadata from raw data

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



file_atf = dir_source_data + '/LTP induction-20211124T114212Z-001/LTP induction/tg/' + '042ca.atf'
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
df1 = dfatf.iloc[:100, :]
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
g = sns.scatterplot(data=df1stackjoin, y='volt_normalized', x= 'time', color='y', ax=ax)
g = sns.lineplot(data=dfmean+dfstd, y='volt_normalized', x= 'time', color='tab:orange', ax=ax)
g = sns.lineplot(data=dfmean-dfstd, y='volt_normalized', x= 'time', color='tab:orange', ax=ax)
g = sns.lineplot(data=dfmean, y='volt_normalized', x= 'time', ax=ax)

ax.set_ylim(-1, 0.2)
```

```python

```
