import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import os  # speak to OS (list dirs)
import matplotlib.pyplot as plt  # plotting
import seaborn as sns  # plotting
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw
import scipy  # peakfinder and other useful analysis tools
from tqdm.notebook import tqdm
from pathlib import Path
from sklearn import linear_model
from joblib import Memory

memory = Memory("joblib", verbose=1)


def find_i_stim_prim_max(dfmean):
    """
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returnsi_Stim (index of stim artefact)
    """
    return dfmean["prim"].idxmax()


def find_i_EPSP_peak_max(
    dfmean,
    limitleft=0,
    limitright=-1,
    param_EPSP_minimum_width_ms=50, # width in ms
    param_EPSP_minimum_prominence_mV=0.01, # in WHAT TODO: find out!
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    print(f"dfmean.time:{dfmean.time}")
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    print(f"sampling_Hz:{sampling_Hz}")
    i_peaks, properties = scipy.signal.find_peaks(
        -dfmean["voltage"],
        width=param_EPSP_minimum_width_ms * 1000 / sampling_Hz,
        prominence=param_EPSP_minimum_prominence_mV / 1000,
    )
    print(f"i_peaks:{i_peaks}")
    print(f"properties:{properties}")
    # scipy.signal.find_peaks returns a tuple
    dfpeaks = dfmean.iloc[i_peaks]
    # dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    print(f"dfpeaks:{dfpeaks}")
    i_EPSP = i_peaks[properties["prominences"].argmax()]

    return i_EPSP


def find_i_VEB_peak_max(
    dfmean,
    i_EPSP,
    param_minimum_width_of_VEB=0.0005,
    param_prim_prominence=0.00005,
    param_minimum_width_of_EPSP=0.005,
):
    """
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    """
    i_peaks = scipy.signal.find_peaks(
        dfmean.prim, width=param_minimum_width_of_VEB, prominence=param_prim_prominence
    )[0]
    # print("i_peaks:", i_peaks, len(i_peaks))
    i_peaks = dfmean.iloc[i_peaks].index
    # print("i_peaks:", i_peaks)
    max_acceptable_i_for_VEB = i_EPSP - param_minimum_width_of_EPSP / 2
    # print(max_acceptable_i_for_VEB)
    possible_i_VEB = max(i_peaks[i_peaks < max_acceptable_i_for_VEB])
    i_VEB = possible_i_VEB  # setting as accepted now, maybe have verification function later

    return i_VEB, max_acceptable_i_for_VEB


def find_i_EPSPslope(dfmean, i_VEB, i_EPSP, happy=False):
    """ """

    dftemp = dfmean.bis[i_VEB:i_EPSP]
    i_EPSPslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if 1 < len(i_EPSPslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[i_VEB: i_EPSP]:{i_EPSPslope}"
            )
        else:
            print(
                "More EPSPs than than we wanted but Im happy, so I pick one and move on."
            )
    return i_EPSPslope[0]


def find_i_volleyslope(
    dfmean, i_Stim, i_VEB, happy=False
):  # , param_half_slope_width = 4):
    """
    DOES NOT USE WIDTH! decided by rolling, earlier?

    returns time of volley slope center,
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    """

    dftemp = dfmean.bis[i_Stim:i_VEB]
    i_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    # print(dftemp.apply(np.sign).diff())
    # print(i_volleyslope)
    if 1 < len(i_volleyslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[i_Stim: i_VEB]:{i_volleyslope}"
            )
        else:
            print(
                "More volleys than than we wanted but Im happy, so I pick one and move on."
            )
    return i_volleyslope[0]


def find_all_i(dfmean, param_min_time_from_i_Stim=0.0005, verbose=False):
    """
    runs all t-detections in the appropriate sequence,
    returns time of center for volley EPSP slopes
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    The function finds VEB, but does not currently report it
    """
    
    i_Stim = find_i_stim_prim_max(dfmean)
    if verbose: print(f"i_Stim:{i_Stim}")

    i_EPSP = find_i_EPSP_peak_max(dfmean)
    print(f"i_EPSP:{i_EPSP}")
    """
    i_VEB, max_acceptable_i_for_VEB = find_i_VEB_peak_max(dfmean, i_EPSP)
    i_EPSPslope = find_i_EPSPslope(dfmean, i_VEB, i_EPSP, happy=True)
    i_volleyslope = find_i_volleyslope(
        dfmean, (i_Stim + param_min_time_from_i_Stim), i_VEB, happy=True
    )
    print(f"i_VEB:{i_VEB}")
    print(f"max_acceptable_i_for_VEB:{max_acceptable_i_for_VEB}")
    print(f"i_EPSPslope:{i_EPSPslope}")
    print(f"i_volleyslope:{i_volleyslope}")
    """
    return i_Stim #i_volleyslope, i_EPSPslope


def measureslope(df, i_slope, halfwidth, name="EPSP"):
    """
    Generalized function


    """
    reg = linear_model.LinearRegression()

    dicts = []
    for sweep in tqdm(df.sweep.unique()):
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[
            ((i_slope - halfwidth) <= dftemp1.time)
            & (dftemp1.time <= (i_slope + halfwidth))
        ]
        x = dftemp2.index.values.reshape(-1, 1)
        y = dftemp2.voltage.values.reshape(-1, 1)

        reg.fit(x, y)
        assert dftemp2.t0.nunique() == 1
        t0 = dftemp2.t0.unique()[0]
        dict_slope = {
            "sweep": sweep,
            "t0": t0,
            "value": reg.coef_[0][0],
            "type": name + "_slope",
            "algorithm": "linear",
        }
        dicts.append(dict_slope)

    df_slopes = pd.DataFrame(dicts)

    return df_slopes


