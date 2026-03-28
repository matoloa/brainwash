import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

fig, ax = plt.subplots()
(line,) = ax.plot(pd.Index([0.0], dtype='float64', name='sweep'), [211.53846154], marker="o")
print(line.get_xdata())
print(line.get_ydata())
print("Visible?", line.get_visible())

fig.savefig("test_plot.png")
