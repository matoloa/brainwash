import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.DataFrame({"sweep": [0.0], "stim": [1], "val": [2.5]})
out = df.set_index("sweep")
x = out.index
y = [10.5]

fig, ax = plt.subplots()
(line,) = ax.plot(x, y, marker="o")
print(line.get_xdata())
