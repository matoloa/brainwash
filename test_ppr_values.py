import pandas as pd
import numpy as np

data = [
    {"recording_name": "rec", "gain": 1.0, "stim": 1, "sweep": 0.0, "EPSP_slope": 0.143, "EPSP_amp": 0.000208},
    {"recording_name": "rec", "gain": 1.0, "stim": 2, "sweep": 0.0, "EPSP_slope": 0.236, "EPSP_amp": 0.000440},
    {"recording_name": "rec", "gain": 1.0, "stim": 1, "sweep": np.nan, "EPSP_slope": 0.143, "EPSP_amp": 0.000208},
    {"recording_name": "rec", "gain": 1.0, "stim": 2, "sweep": np.nan, "EPSP_slope": 0.236, "EPSP_amp": 0.000440},
]
dfoutput = pd.DataFrame(data)

out_sweeps = dfoutput[dfoutput["sweep"].notna()]
out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")
common_sweeps = out1.index.intersection(out2.index).dropna()
o1 = out1.loc[common_sweeps]
o2 = out2.loc[common_sweeps]

v1 = o1["EPSP_amp"].values.astype(float)
v2 = o2["EPSP_amp"].values.astype(float)

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    ppr = (v2 / v1) * 100
    ppr[~np.isfinite(ppr)] = np.nan

print("common:", common_sweeps)
print("ppr:", ppr)
