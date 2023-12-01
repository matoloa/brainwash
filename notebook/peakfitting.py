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

# %%
# peak fit subtraction experiment
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

import sys
import os

folder_path = Path(os.path.abspath("")).parent
sys.path.append(str(folder_path / 'src/lib'))  # append src/lib to import modules from it
import analysis


# %%

#path_filterfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_Ch1_a_filter.csv")
#dffilter = pd.read_csv(str(path_filterfile)) # a persisted csv-form of the data file
path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_Ch0_b_mean.csv")
dfmean = pd.read_csv(str(path_meanfile)) # a persisted average of all sweeps in that data file
dict_t = analysis.find_all_t(dfmean) # use the average all sweeps to determine where all events are located (noise reduction)
t_VEB = dict_t['t_VEB']
fig, ax = plt.subplots(figsize=(20, 10), layout="constrained")
#ax.plot(dfmean['time'], dfmean['voltage'], color='black')
#ax.plot(dfmean['time'], dfmean['prim']*10, color='red')
#ax.plot(dfmean['time'], dfmean['bis']*25, color='green')
#dfmean['bis_roll'] = dfmean['bis'].rolling(9, center=True, win_type='blackman').mean()
#plt.plot(dfmean['time'], dfmean['bis_roll']*25, color='blue')
#plt.axhline(y=0, linestyle='dashed', color='gray')
#plt.axvline(x=t_VEB, linestyle='dashed', color='gray')
#mean_ylim = (-0.0006, 0.0005)
#mean_xlim = (0.006, 0.020)
#plt.xlim(mean_xlim)
#plt.ylim(mean_ylim)

import longscurvefitting
dffit = dfmean[['time', 'voltage']][(0.008 < dfmean.time) & (dfmean.time < 0.040)]
ax.plot(dffit.time.values, dffit.voltage.values)
print(f"dffit shape: {dffit.shape}")


# %%
# dynamic function builder with correct args signature
import inspect 
from types import FunctionType

def get_combined_model(models_in_model):  # use as: models_in_model = [_pearson3, _gaussian]
    models_str = "+".join([i.__name__ + str(inspect.signature(i)) for i in models_in_model])
    models_params = [inspect.signature(i) for i in models_in_model]
    print(models_params)
    args = []
    _ = [args.append(i) for j in models_params for i in j.parameters.keys() if i not in args]  # remove duplicates
    model_code = compile(f"def foo({', '.join(args)}): return {models_str}", "<string>", "exec")
    model = FunctionType(model_code.co_consts[0], globals(), "foo")
    params = inspect.signature(model).parameters 
    print(params)
    return model


# %%
# possible approx functions
# "gaussian(x, p0_0, p0_1, p0_2) + pearson3(x, p1_0, p1_1, p1_2, p1_3)"
# "logistic(x, p0_0, p0_1, p0_2) + logistic(x, p1_0, p1_1, p1_2)"
from numpy import exp, loadtxt, pi, sqrt
from scipy.stats import pearson3, lognorm
from lmfit import Model
dffit = dfmean[['time', 'voltage']][((t_VEB - 0.002) < dfmean.time) & (dfmean.time < 0.050)]
dffit = dfmean[['time', 'voltage']][((t_VEB - 0.0005) < dfmean.time) & (dfmean.time < (0.04))]

ax.plot(dffit.time.values, dffit.voltage.values)
print(f"dffit shape: {dffit.shape}")
x, y = dffit.time.values, dffit.voltage.values
fig, ax = plt.subplots(figsize=(20, 10), layout="constrained")

def _gaussian(x, amp, wid):
    # center = t_VEB
    """1-d gaussian: gaussian(x, amp, cen, wid)"""
    return (amp / (sqrt(2*pi) * wid)) * exp(-(x-t_VEB+0.0002)**2 / (2*wid**2))


def _pearson3(x, a, b, c, d):
    '''General Pearson Type 3 function, the probability density function (PDF) of Pearson type III distribution.
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearson3.html
    Parameters:
        x: independent variable
        a, b, c, d: parameters for function
    returns:
        y: dependent variable
    '''
    y = a * pearson3.pdf(x, skew=b, loc=c, scale=d)
    return y


def _lognorm(x, e, f, g, s):
    return e * lognorm.pdf(x/f, s)

def fwrap(x, const, a, b, c, d, amp, wid, e, f, g, s):
    return const + 0.0 * _pearson3(x, a, b, c, d) + _gaussian(x, amp, wid) + _lognorm(x, e, f, g, s) 


gmodel = Model(fwrap)
gmodel = Model(model)
#   result = gmodel.fit(y, x=x, const=-0.005, a=0.001, b=1, c=0.001, d=1, amp=0.0008, wid=0.01, e=-0.01, f=0.013, g=0.14, s=0.24)
result = gmodel.fit(y, x=x, a=0.001, b=1, c=0.001, d=1, amp=0.0008, wid=0.01)


print(result.fit_report())

plt.plot(x, y, 'o')
#plt.plot(x, result.init_fit, '--', label='initial fit')
plt.plot(x, result.best_fit, '-', label='best fit')
plt.legend()
plt.show()

# %%
