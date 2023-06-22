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


def find_t_stim_prim_max(dfmean):
    """
    accepts first order derivative of dfmean
    finds x of max(y): the steepest incline
    returnst_Stim (index of stim artefact)
    """
    return dfmean["prim"].idxmax()


def find_t_EPSP_peak_max(
    dfmean,
    limitleft=0,
    limitright=-1,
    param_minimum_width_of_EPSP=2,
    param_EPSP_prominence=0.00005,
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    i_peaks = scipy.signal.find_peaks(
        -dfmean["voltage"],
        width=param_minimum_width_of_EPSP,
        prominence=param_EPSP_prominence,
    )[0]
    # scipy.signal.find_peaks returns a tuple
    dfpeaks = dfmean.iloc[i_peaks]
    # dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    t_EPSP = dfpeaks.index.max()

    return t_EPSP


def find_t_VEB_peak_max(
    dfmean,
    t_EPSP,
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
    t_peaks = dfmean.iloc[i_peaks].index
    # print("t_peaks:", t_peaks)
    max_acceptable_t_for_VEB = t_EPSP - param_minimum_width_of_EPSP / 2
    # print(max_acceptable_t_for_VEB)
    possible_t_VEB = max(t_peaks[t_peaks < max_acceptable_t_for_VEB])
    t_VEB = possible_t_VEB  # setting as accepted now, maybe have verification function later

    return t_VEB, max_acceptable_t_for_VEB


def find_t_EPSPslope(dfmean, t_VEB, t_EPSP, happy=False):
    """ """

    dftemp = dfmean.bis[t_VEB:t_EPSP]
    t_EPSPslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if 1 < len(t_EPSPslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[t_VEB: t_EPSP]:{t_EPSPslope}"
            )
        else:
            print(
                "More EPSPs than than we wanted but Im happy, so I pick one and move on."
            )
    return t_EPSPslope[0]


def find_t_volleyslope(
    dfmean, t_Stim, t_VEB, happy=False
):  # , param_half_slope_width = 4):
    """
    DOES NOT USE WIDTH! decided by rolling, earlier?

    returns time of volley slope center,
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    """

    dftemp = dfmean.bis[t_Stim:t_VEB]
    t_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    # print(dftemp.apply(np.sign).diff())
    # print(t_volleyslope)
    if 1 < len(t_volleyslope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[t_Stim: t_VEB]:{t_volleyslope}"
            )
        else:
            print(
                "More volleys than than we wanted but Im happy, so I pick one and move on."
            )
    return t_volleyslope[0]


def find_ts(df, param_min_time_from_t_Stim=0.0005):
    """
    runs all t-detections in the appropriate sequence,
    returns time of center for volley EPSP slopes
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    The function finds VEB, but does not currently report it

    dfmean = builddfmean(df)
    t_Stim = findstim(dfmean)
    t_EPSP = findEPSP(dfmean)
    t_VEB, max_acceptable_t_for_VEB = findVEB(dfmean, t_EPSP)
    t_EPSPslope = find_t_EPSPslope(dfmean, t_VEB, t_EPSP, happy=True)
    t_volleyslope = find_t_volleyslope(
        dfmean, (t_Stim + param_min_time_from_t_Stim), t_VEB, happy=True
    )

    return t_volleyslope, t_EPSPslope, dfmean
    """


def measureslope(df, t_slope, halfwidth, name="EPSP"):
    """
    Generalized function


    """
    reg = linear_model.LinearRegression()

    dicts = []
    for sweep in tqdm(df.sweep.unique()):
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[
            ((t_slope - halfwidth) <= dftemp1.time)
            & (dftemp1.time <= (t_slope + halfwidth))
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


