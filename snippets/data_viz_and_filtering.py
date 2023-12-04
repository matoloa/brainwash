# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # roadmap
# ## analyse signal and noise
# ## try fft on each sweep, low pass filtering
# ## put all data in one sweep to better understand noise, probably ruins signal in fft but not noise
# ## smoothing inbetween sweeps
# ## detect regime shifts in time development of features, separate interpolation in regions
# ## anticorrelate noise?
#

# %%
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

folder_path = os.path.abspath('')
folder_path = str(Path(os.path.abspath('')).parent / 'src/lib')
sys.path.append(folder_path)

from analysis import find_all_t

import seaborn as sns
import matplotlib.pyplot as plt

# %%
folder_path

# %%
path_datafile = Path.home() / ("Documents/Brainwash Projects/standalone_test/data/KO_02_Ch1_a.csv")
path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_Ch1_a_mean.csv")
# path_datafile = Path.home() / ("Documents/Brainwash Projects/standalone_test/data/A_21_P0701-S2.csv")
# path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_21_P0701-S2_mean.csv")
dfdata = pd.read_csv(str(path_datafile)) # a persisted csv-form of the data file
df_mean = pd.read_csv(str(path_meanfile)) # a persisted average of all sweeps in that data file
# dfdata_a = dfdata[(dfdata['stim']=='a')] # select stim 'a' only in data file
# df_mean_a = df_mean[(df_mean['stim']=='a')] # select stim 'a' only in mean file
dict_t = find_all_t(df_mean) # use the average all sweeps to determine where all events are located (noise reduction)
t_EPSP_amp = dict_t['t_EPSP_amp']
t_EPSP_slope = dict_t['t_EPSP_slope']

# %%
dfpivot = dfdata.pivot(index='sweep', columns='time', values='voltage')
dfpivot.iloc[:, :].plot(legend=False)

# %%
sns.heatmap(data=dfpivot.values, vmin=-0.0001, vmax=0.0001)

# %%
from scipy.fft import fft2


# %%
sns.heatmap(data=np.real(fft2(dfpivot.values)))

# %%
from scipy.fft import rfft, irfft

# %%
# original sweep
xstimcutoff = 74
sweep = dfpivot.iloc[100, xstimcutoff:].values

plt.plot(sweep)  # cutoff stim. problematic for fft

# %%
fftsweep = rfft(sweep)
plt.plot(abs(fftsweep))  # abs for norm of component, don't care about phase

# %%
fftwidth = 1000
fftcleaned = fftsweep[:fftwidth]
# also kill off the worst offenders
fftcleaned[idx_worst_noise_freq] = 0
sweepcleaned = irfft(fftcleaned)
plt.plot(sweepcleaned)

# %%
# establish shape of typical noise
# original sweep
xstimcutoff = 0
basesweeps = dfpivot.iloc[:100, xstimcutoff:]

sns.heatmap(data=basesweeps.values, vmin=-0.0001, vmax=0.0001)


# %%
meansweep = basesweeps.mean(axis=0)
plt.plot(meansweep.values)

# %%
noise = basesweeps - meansweep

# %%
sns.heatmap(data=noise.values, vmin=-0.0001, vmax=0.0001)

# %%
ffts = []
for sweep in range(noise.shape[0]):
    fftsweep = rfft(noise.iloc[sweep, :].values)
    ffts.append(fftsweep)
ffts = pd.DataFrame(ffts)
ffts

# %%
# noise distribution
from scipy.stats import norm
data = noise.values.reshape(-1, 1)
# Fit a normal distribution to the data:
mu, std = norm.fit(data)

# Plot the histogram.
plt.hist(data, bins=100, density=True, alpha=0.6, color='g')

# Plot the PDF.
xmin, xmax = plt.xlim()
x = np.linspace(xmin, xmax, 100)
p = norm.pdf(x, mu, std)
plt.plot(x, p, 'k', linewidth=2)
title = "Fit results: mu = %.5f,  std = %.5f" % (mu, std)
plt.title(title)

plt.show()

# %%
# noise fft plot
sns.heatmap(data=abs(ffts), vmin=0, vmax=0.01)

# %%
plt.plot(abs(ffts).mean())

# %%
# noisezero
noisezero = noise.subtract(noise.mean(axis=1), axis='rows')
sns.heatmap(data=noisezero.values, vmin=-0.0001, vmax=0.0001)

# %%
fftsz = []
for sweep in range(noisezero.shape[0]):
    fftsweep = rfft(noisezero.iloc[sweep, :].values)
    fftsz.append(fftsweep)
fftsz = pd.DataFrame(fftsz)
fftsz

# %%
sns.heatmap(data=abs(fftsz), vmin=0, vmax=0.01)

# %%
plt.plot(abs(fftsz).mean())

# %%
# identify top 5 noise frequencies
noisepow = abs(fftsz).mean()

# %%
plt.plot(noisepow.sort_values(ascending=False).values)

# %%
idx_worst_noise_freq = noisepow.sort_values(ascending=False).index[:40]   # find the 10 worst over 50 lag
idx_worst_noise_freq = idx_worst_noise_freq[50 < idx_worst_noise_freq][:10]
idx_worst_noise_freq

# %%
# fft transform, kill off noise freq, recover signal
data = []
for isweep in range(basesweeps.shape[0]):
    fftsweep = rfft(basesweeps.iloc[isweep, :].values)

    # try just zero freq components
    fftsweep[idx_worst_noise_freq] = 0
    
    signal = irfft(fftsweep)
    data.append(signal)
data = pd.DataFrame(data)

plt.plot(data.mean())  # abs for norm of component, don't care about phase
sns.heatmap(data=data, vmin=-0.001, vmax=0.001)

# %%
plt.plot(data.mean())  # abs for norm of component, don't care about phase


# %%
# Simple vertical smoothing test, will lag response 1-s sweeps
# fft transform, kill off noise freq, recover signal
smoothz = 10
data = []
for isweep in range(basesweeps.shape[0]):
    signal = basesweeps.iloc[-smoothz + isweep: isweep, :].mean()
    data.append(signal)
data = pd.DataFrame(data)

plt.plot(data.mean())  # abs for norm of component, don't care about phase
fig, axes = plt.subplots(1, 2, figsize=(20, 10))
f = sns.heatmap(data=data, vmin=-0.0001, vmax=0.0001, ax=axes[0])
g = sns.heatmap(data=basesweeps, vmin=-0.0001, vmax=0.0001, ax=axes[1])

# %%
fig, axes = plt.subplots(1, 2, figsize=(20, 10))
axes[0].plot(basesweeps.iloc[50, :]) 
axes[1].plot(data.iloc[50, :])  

# %%
# all data in one sweeep to better figure out noise
plt.plot(dfdata.voltage[:5000])

# %%
cfft = rfft(dfdata.voltage.values)

# %%
plt.plot(abs(cfft[:5000]))
plt.ylim(0, 50)

# %%
# kill all cfft above some freq and backtransform
cfft = rfft(dfdata.voltage.values)
print(f"n fourier c: {len(cfft)}")
thrfreq = 300000
cfft[thrfreq:] = 0
lpasssignal = irfft(cfft)
plt.plot(lpasssignal[:5000])

# %%
# try the same for the noise
plt.plot(noisezero.values.reshape(-1, 1)[:1000])
#plt.ylim(0, 50)

# %%
cfft = rfft(noisezero.values.reshape(-1, 1))
plt.plot(abs(cfft[:2000]))

# %%
dfdelta = dfdata.voltage - dfdata.voltage.shift()
dfdelta.hist(bins=100, range=(-0.0002, 0.0002))

# %%
from pandas.plotting import autocorrelation_plot

# %%
autocorrelation_plot(dfdata.voltage[:5000])

# %%
autocorrelation_plot(dfdata.voltage[:1024])

# %%
fig = autocorrelation_plot(dfdata.voltage[:10024])
fig.set_ylim(-.05, .05)
fig.set_xlim(0, 400)

# %%
# filtering tests
from scipy.signal import savgol_filter
start = 65
cutoff = 1024
yhat = savgol_filter(dfdata.voltage[start:cutoff], window_length=10, polyorder=2)

fig, axes = plt.subplots(1, 2, figsize=(20, 10))
axes[0].plot(yhat), axes[1].plot(dfdata.voltage[start:cutoff])
axes[0].set_ylim(-0.0005, 0.001), axes[1].set_ylim(-0.0005, 0.001)
axes[0].set_xlim(0, 200), axes[1].set_xlim(0, 200)

# %%
start = 65
cutoff = 1024
yhat = savgol_filter(dfdata.voltage[start:cutoff], window_length=10, polyorder=2)

fig, ax1 = plt.subplots(figsize=(10, 5))
ax2 = ax1.twinx()

# Plot the filtered data on the left y-axis (ax1)
ax1.plot(yhat, color='blue', label='Filtered Data')
ax1.set_ylabel('Filtered Data', color='blue')
ax1.set_ylim(-0.0005, 0.001)
ax1.set_xlim(0, 200)

# Plot the original data on the right y-axis (ax2)
ax2.plot(dfdata.voltage[start:cutoff], color='red', label='Original Data')
ax2.set_ylabel('Original Data', color='red')
ax2.set_ylim(-0.0005, 0.001)

# Common x-axis label
ax1.set_xlabel('X-axis')

# Show legends for both plots
ax1.legend(loc='upper left')
ax2.legend(loc='upper right')

# Show the plot
plt.show()

# %%
strtest = "param__key1_value1__key2_value2"
strsplit = strtest.split("__")
print(f"strsplit: {strsplit}")

# %%
autocorrelation_plot(yhat)

# %%

# %%
