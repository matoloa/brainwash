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
    param_EPSP_minimum_width_ms=5, # width in ms
    param_EPSP_minimum_prominence_mV=0.001, # what unit? TODO: find out!
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    print("find_i_EPSP_peak_max:")

    # calculate sampling frequency
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    print(f" . . . sampling_Hz: {sampling_Hz}")

    # convert EPSP width from ms to index
    EPSP_minimum_width_i = int(param_EPSP_minimum_width_ms * 0.001 * sampling_Hz) #0.001 for ms to seconds, *sampling_Hz for seconds to recorded points
    print(" . . . EPSP is at least", EPSP_minimum_width_i, "points wide")

    # scipy.signal.find_peaks returns a tuple
    i_peaks, properties = scipy.signal.find_peaks(
        -dfmean["voltage"],
        width=EPSP_minimum_width_i,
        prominence=param_EPSP_minimum_prominence_mV / 1000,
    )
    print(f" . . . i_peaks:{i_peaks}")
    print(f" . . . properties:{properties}")
    
    dfpeaks = dfmean.iloc[i_peaks]
    # dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    print(f" . . . dfpeaks:{dfpeaks}")
    i_EPSP = i_peaks[properties["prominences"].argmax()]

    return i_EPSP


def find_i_VEB_prim_peak_max(
    dfmean,
    i_Stim,
    i_EPSP,
    param_minimum_width_of_EPSP=5,   # ms
    param_minimum_width_of_VEB=1,    # ms
    param_prim_prominence=0.0001,    # TODO: correct unit for prim?
):
    """
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    defined as largest positive peak in first order derivative between i_stim and i_EPSP
    
    """
    print("find_i_VEB_prim_peak_max:")
    # calculate sampling frequency
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    print(f" . . . sampling_Hz: {sampling_Hz}")
    
    # convert time constraints (where to look for the VEB) to indexes
    minimum_acceptable_i_for_VEB = int(i_Stim + 0.001 * sampling_Hz) # The VEB is not within a ms of the i_stim
    max_acceptable_i_for_VEB = int(i_EPSP - np.floor((param_minimum_width_of_EPSP * 0.001 * sampling_Hz)/2)) #0.001 for ms to seconds, *sampling_Hz for seconds to recorded points
    print(" . . . VEB is between", minimum_acceptable_i_for_VEB, "and", max_acceptable_i_for_VEB)
    
    # create a window to the acceptable range:
    prim_sample = dfmean["prim"].values[minimum_acceptable_i_for_VEB:max_acceptable_i_for_VEB] 
    
    # find the sufficiently wide and promintent peaks within this range
    i_peaks, properties = scipy.signal.find_peaks(
        prim_sample,
        width=param_minimum_width_of_VEB * 1000 / sampling_Hz, # *1000 for ms to seconds, / sampling_Hz for seconds to recorded points
        prominence=param_prim_prominence / 1000, # TODO: unit?
    )

    # add skipped range to found indexes
    i_peaks += minimum_acceptable_i_for_VEB
    print(" . . . i_peaks:", i_peaks)
    print(f" . . . properties:{properties}")
    
    i_VEB = i_peaks[properties["prominences"].argmax()]
    print(f" . . . i_VEB: {i_VEB}")

    return i_VEB


def find_i_EPSP_slope(dfmean, i_VEB, i_EPSP, happy=False):
    """ """

    dftemp = dfmean.bis[i_VEB:i_EPSP]
    i_EPSP_slope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if 1 < len(i_EPSP_slope):
        if not happy:
            raise ValueError(
                f"Found multiple positive zero-crossings in dfmean.bis[i_VEB: i_EPSP]:{i_EPSP_slope}"
            )
        else:
            print(
                "More EPSPs than than we wanted but Im happy, so I pick one and move on."
            )
    return i_EPSP_slope[0]


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
    returns INDEX of center for volley EPSP slopes
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    The function finds VEB, but does not currently report it
    """
    
    i_Stim = find_i_stim_prim_max(dfmean)
    if verbose: print(f"i_Stim:{i_Stim}")

    i_EPSP_amp = find_i_EPSP_peak_max(dfmean)
    if verbose: print(f"i_EPSP_amp:{i_EPSP_amp}")

    i_VEB = find_i_VEB_prim_peak_max(dfmean, i_Stim, i_EPSP_amp)
    if verbose: print(f"i_VEB:{i_VEB}")
    
    i_EPSP_slope = find_i_EPSP_slope(dfmean, i_VEB, i_EPSP_amp, happy=True)
    if verbose: print(f"i_EPSP_slope:{i_EPSP_slope}")

    """
    i_volleyslope = find_i_volleyslope(
        dfmean, (i_Stim + param_min_time_from_i_Stim), i_VEB, happy=True
    )
    print(f"i_VEB:{i_VEB}")
    print(f"max_acceptable_i_for_VEB:{max_acceptable_i_for_VEB}")
    print(f"i_EPSPslope:{i_EPSPslope}")
    print(f"i_volleyslope:{i_volleyslope}")
    """
    # TODO: change return to {}
    return {"i_Stim": i_Stim, "i_VEB": i_VEB, "i_EPSP_amp": i_EPSP_amp, "i_EPSP_slope": i_EPSP_slope}


def find_all_t(dfmean, param_min_time_from_i_Stim=0.0005, verbose=False):
    if verbose: print("find_all_t")
    dict_i = find_all_i(dfmean, param_min_time_from_i_Stim=0.0005, verbose=False)
    dict_t = {}
    for k, v in dict_i.items():
        k_new = "t" + k[1:]
        dict_t[k_new] = dfmean.loc[v].time
    if verbose: print(f"dict_t: {dict_t}")
    return dict_t


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


