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
import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
```

# Roadmap
* parse atf och abf


```python
dir_project_root = os.getcwd().split('notebook')[0]
dir_source_data = dir_project_root + 'dataSource'
```

```python
import pyabf
```

```python
os.listdir(dir_source_data + '/LTP induction-20211124T114212Z-001/LTP induction/tg')
```

```python
atf = pyabf.ATF(dir_source_data + '/LTP induction-20211124T114212Z-001/LTP induction/tg/' + '042ca.atf')

```

```python
atf
```

```python
print(atf.header) # display header information in the console

```

```python
atf.setSweep(1)
```

```python
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
# parse atf
abf = pyabf.ABF(dir_source_data + '/02GKO/1a IO SR/' + '2022_01_24_0002.abf')
```

```python
abf
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
# parse ibw
from neo import io
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

```
