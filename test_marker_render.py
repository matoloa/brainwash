import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([0.0], [121.5], marker="o")
ax.set_ylim(100, 150)
fig.savefig("test_marker.png")
