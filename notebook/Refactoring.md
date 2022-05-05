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
abf.setSweep(sweepNumber=239, channel=1)
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
def importFunction(filename, oddeven=None, channel=None):
    
    # I HAVE CHANGED IT!
    
    
    
    return df

df = importFunction(filename)

```
