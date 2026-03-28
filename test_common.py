import pandas as pd

data = [
    {"sweep": 0.0, "stim": 1, "EPSP_amp": 0.000208},
    {"sweep": 0.0, "stim": 2, "EPSP_amp": 0.000440},
]
dfoutput = pd.DataFrame(data)

out_sweeps = dfoutput[dfoutput["sweep"].notna()]
out1 = out_sweeps[out_sweeps["stim"] == 1].set_index("sweep")
out2 = out_sweeps[out_sweeps["stim"] == 2].set_index("sweep")

common_sweeps = out1.index.intersection(out2.index).dropna()

print("common:", common_sweeps)
o1 = out1.loc[common_sweeps]
o2 = out2.loc[common_sweeps]
print(o1["EPSP_amp"].values)
print(o2["EPSP_amp"].values)
