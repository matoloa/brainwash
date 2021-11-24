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

```
