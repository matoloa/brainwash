import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def _ylim_from_artists(axis, pad=0.10, min_span=1e-9, x_min=None, x_max=None, ymin=None):
    all_y = []
    for line in axis.get_lines():
        if not line.get_visible():
            continue
        if line.get_transform() != axis.transData:
            continue
        xdata = np.asarray(line.get_xdata(), dtype=float).ravel()
        ydata = np.asarray(line.get_ydata(), dtype=float).ravel()
        mask = np.isfinite(ydata)
        if x_min is not None:
            mask &= xdata >= x_min
        if x_max is not None:
            mask &= xdata <= x_max
        finite = ydata[mask]
        if finite.size == 0:
            continue
        if finite.size == 1 and "marker" in line.get_label():
            continue
        all_y.append(finite)
    if not all_y:
        return None
    yall = np.concatenate(all_y)
    lo, hi = float(yall.min()), float(yall.max())
    span = hi - lo
    if span < min_span:
        span = max(abs(hi), min_span)
        lo, hi = hi - span, hi + span
    if ymin is not None:
        lo = ymin
    else:
        lo = lo - pad * span
    hi = hi + pad * span
    return (lo, hi)

fig, ax = plt.subplots()
(line,) = ax.plot([0.0], [121.5], marker="o", label="rec_name PPR EPSP_amp raw")
res = _ylim_from_artists(ax, pad=0.1, x_min=0, x_max=1)
print("ylim:", res)
