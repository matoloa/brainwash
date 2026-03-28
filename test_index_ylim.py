import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

fig, ax = plt.subplots()
(line,) = ax.plot(pd.Index([0.0], dtype='float64', name='sweep'), np.array([121.5]), marker="o", label="rec_name PPR EPSP_amp raw")
xdata = np.asarray(line.get_xdata(), dtype=float).ravel()
print("xdata:", xdata)
