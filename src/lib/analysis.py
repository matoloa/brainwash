# %%
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import scipy  # peakfinder and other useful analysis tools
from scipy.signal import savgol_filter
from sklearn import linear_model
from tqdm import tqdm
import time


# %%
from joblib import Memory

# %%
memory = Memory("joblib", verbose=1)


# %%
def build_dfoutput(df, filter='voltage', t_EPSP_amp=None, t_EPSP_slope=None, t_EPSP_slope_size=None, t_volley_amp=None, t_volley_slope=None, t_volley_slope_size=None):
    """Measures each sweep in df (e.g. from <save_file_name>.csv) at specificed times t_* 
    Args:
        df: a dataframe containing numbered sweeps, timestamps and voltage
        t_EPSP_amp: time of lowest point of EPSP
        t_EPSP_slope: time of centre of EPSP_slope
        t_EPSP_slope_size: width of EPSP slope (radius)
        t_volley_amp: time of lowest point of volley
        t_volley_slope: time of centre of volley_slope
        t_volley_slope_size: width of volley slope (radius)
    Returns:
        a dataframe. Per sweep (row): EPSP_amp, EPSP_slope, volley_amp, volley_EPSP
    """
    t0 = time.time()
    list_col = ['sweep']
    dfoutput = pd.DataFrame()
    dfoutput['sweep'] = df.sweep.unique() # one row per unique sweep in data file
    # EPSP_amp
    if t_EPSP_amp is not None:
        if t_EPSP_amp is not np.nan:
            df_EPSP_amp = df[df['time']==t_EPSP_amp].copy() # filter out all time (from sweep start) that do not match t_EPSP_amp
            df_EPSP_amp.reset_index(inplace=True, drop=True)
            dfoutput['EPSP_amp'] = -1000 * df_EPSP_amp[filter] # invert and convert to mV
        else:
            dfoutput['EPSP_amp'] = np.nan
        list_col.append('EPSP_amp')
    # EPSP_slope
    if t_EPSP_slope is not None and t_EPSP_slope_size is not None:
        if t_EPSP_slope is not np.nan:
            df_EPSP_slope = measureslope_vec(df=df, filter=filter, t_slope=t_EPSP_slope, halfwidth=t_EPSP_slope_size)
            dfoutput['EPSP_slope'] = -df_EPSP_slope['value'] # invert 
        else:
            dfoutput['EPSP_slope'] = np.nan
        list_col.append('EPSP_slope')
    # volley_amp
    if t_volley_amp is not None:
        if t_volley_amp is not np.nan:
            df_volley_amp = df[df['time']==t_volley_amp].copy() # filter out all time (from sweep start) that do not match t_volley_amp
            df_volley_amp.reset_index(inplace=True, drop=True)
            dfoutput['volley_amp'] = -1000 * df_volley_amp[filter] # invert and convert to mV
        else:
            dfoutput['volley_amp'] = np.nan
        list_col.append('volley_amp')
    # volley_slope
    if t_volley_slope is not None and t_volley_slope_size is not None:
        if t_volley_slope is not np.nan:
            df_volley_slope = measureslope_vec(df=df, filter=filter, t_slope=t_volley_slope, halfwidth=t_volley_slope_size)
            dfoutput['volley_slope'] = -df_volley_slope['value'] # invert 
        else:
            dfoutput['volley_slope'] = np.nan
        list_col.append('volley_slope')
    t1 = time.time()
    print(f'build_dfoutput: {t1-t0} seconds, list_col: {list_col}')
    return dfoutput[list_col]


def addFilterSavgol(df, window_length=9, poly_order=3):
    # returns a column containing a smoothed version of the voltage column in a df; dfmean or dffilter
    df['savgol'] = savgol_filter(df.voltage, window_length=window_length, polyorder=poly_order)
    return df['savgol']


# %%
def find_i_stim_prim_max(dfmean):
    # TODO: return an index of sufficiently separated over-threshold x:es instead
    return dfmean['prim'].idxmax()


# %%
def find_i_EPSP_peak_max(
    dfmean,
    limitleft=0,
    limitright=-1,
    param_EPSP_minimum_width_ms=5,  # width in ms
    param_EPSP_minimum_prominence_mV=0.001,  # what unit? TODO: find out!
    verbose=False
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    if verbose:
        print("find_i_EPSP_peak_max:")

    # calculate sampling frequency
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    if verbose:
        print(f" . . . sampling_Hz: {sampling_Hz}")

    # convert EPSP width from ms to index
    EPSP_minimum_width_i = int(
        param_EPSP_minimum_width_ms * 0.001 * sampling_Hz
    )  # 0.001 for ms to seconds, *sampling_Hz for seconds to recorded points
    if verbose:
        print(" . . . EPSP is at least", EPSP_minimum_width_i, "points wide")

    # scipy.signal.find_peaks returns a tuple
    i_peaks, properties = scipy.signal.find_peaks(
        -dfmean['voltage'],
        width=EPSP_minimum_width_i,
        prominence=param_EPSP_minimum_prominence_mV / 1000,
    )
    if verbose:
        print(f" . . . i_peaks:{i_peaks}")
    if len(i_peaks) == 0:
        if verbose:
            print(" . . No peaks in specified interval.")
        return np.nan
    if verbose:
        print(f" . . . properties:{properties}")

    dfpeaks = dfmean.iloc[i_peaks]
    # dfpeaks = pd.DataFrame(peaks[0]) # Convert to dataframe in order to select only > limitleft
    dfpeaks = dfpeaks[limitleft < dfpeaks.index]
    if verbose:
        print(f" . . . dfpeaks:{dfpeaks}")

    i_EPSP = i_peaks[properties['prominences'].argmax()]
    return i_EPSP


# %%
def find_i_VEB_prim_peak_max(
    dfmean,
    i_stim,
    i_EPSP,
    param_minimum_width_of_EPSP=5,  # ms
    param_minimum_width_of_VEB=1,  # ms
    param_prim_prominence=0.0001,  # TODO: correct unit for prim?
    verbose=False
):
    """
    returns index for VEB (Volley-EPSP Bump - notch between volley and EPSP)
    defined as largest positive peak in first order derivative between i_stim and i_EPSP

    """
    if verbose:
        print("find_i_VEB_prim_peak_max:")
    # calculate sampling frequency
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    if verbose:
        print(f" . . . sampling_Hz: {sampling_Hz}")

    # convert time constraints (where to look for the VEB) to indexes
    minimum_acceptable_i_for_VEB = int(i_stim + 0.001 * sampling_Hz)  # The VEB is not within a ms of the i_stim
    max_acceptable_i_for_VEB = int(
        i_EPSP - np.floor((param_minimum_width_of_EPSP * 0.001 * sampling_Hz) / 2)
    )  # 0.001 for ms to seconds, *sampling_Hz for seconds to recorded points
    if verbose:
        print(" . . . VEB is between", minimum_acceptable_i_for_VEB, "and", max_acceptable_i_for_VEB)

    # create a window to the acceptable range:
    prim_sample = dfmean['prim'].values[minimum_acceptable_i_for_VEB:max_acceptable_i_for_VEB]

    # find the sufficiently wide and promintent peaks within this range
    i_peaks, properties = scipy.signal.find_peaks(
        prim_sample,
        width=param_minimum_width_of_VEB * 1000 / sampling_Hz,  # *1000 for ms to seconds, / sampling_Hz for seconds to recorded points
        prominence=param_prim_prominence / 1000,  # TODO: unit?
    )

    # add skipped range to found indexes
    i_peaks += minimum_acceptable_i_for_VEB
    if verbose:
        print(" . . . i_peaks:", i_peaks)
    if len(i_peaks) == 0:
        print(" . . No peaks in specified interval.")
        return np.nan
    # print(f" . . . prim_sample:{list(prim_sample)}")
    # import matplotlib.pyplot as plt
    # plt.plot(prim_sample)
    if verbose:
        print(f" . . . properties:{properties}")

    i_VEB = i_peaks[properties['prominences'].argmax()]
    if verbose:
        print(f" . . . i_VEB: {i_VEB}")

    return i_VEB


# %%
def find_i_EPSP_slope_bis0(dfmean, i_VEB, i_EPSP, happy=False):
    """ """

    dftemp = dfmean.bis[i_VEB:i_EPSP]
    i_EPSP_slope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values

    if len(i_EPSP_slope) == 0:
        print(" . . No positive zero-crossings in dfmean.bis[i_VEB: i_EPSP].")
        return np.nan
    if 1 < len(i_EPSP_slope):
        if not happy:
            raise ValueError(f"Found multiple positive zero-crossings in dfmean.bis[i_VEB: i_EPSP]:{i_EPSP_slope}")
        else:
            print("More EPSPs than we wanted but I'm happy, so I pick the first one and move on.")
    return i_EPSP_slope[0]


# %%
def find_i_volley_slope(dfmean, i_stim, i_VEB, happy=False):
    """
    returns time of volley slope center,
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    """
    dftemp = dfmean.prim[i_VEB-12:i_VEB]
    i_volleyslope = dftemp.idxmin()

    # dftemp = dfmean.bis[i_VEB-15:i_VEB]
    # i_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    # print(dftemp.apply(np.sign).diff())
    # print(i_volleyslope)
    # if 1 < len(i_volleyslope):
    #     if not happy:
    #         raise ValueError(f"Found multiple positive zero-crossings in dfmean.bis[i_stim: i_VEB]:{i_volleyslope}")
    #     else:
    #         print("More volleys than than we wanted but Im happy, so I pick one and move on.")
    return i_volleyslope#[0]


# %%
def find_all_i(dfmean, param_min_time_from_i_stim=0.0005, verbose=False):
    """
    runs all index-detections in the appropriate sequence,
    The function finds VEB, but does not currently report it
    TODO: also report volley amp and slope
    Returns a dict of all indices, with np.nan representing detection failure.
    """
    dict_i = { #set default np.nan
        "i_stim": np.nan,
        "i_VEB": np.nan,
        "i_EPSP_amp": np.nan,
        "i_EPSP_slope": np.nan,
        "i_volley_amp": np.nan,
        "i_volley_slope": np.nan,
        }
    dict_i['i_stim'] = find_i_stim_prim_max(dfmean=dfmean,)
    if dict_i['i_stim'] is np.nan: # TODO: will not happen in current configuration
        return dict_i
    dict_i['i_EPSP_amp'] = find_i_EPSP_peak_max(dfmean=dfmean, verbose=True)
    if dict_i['i_EPSP_amp'] is np.nan: # TODO: will not happen in current configuration
        return dict_i
    dict_i['i_VEB'] = find_i_VEB_prim_peak_max(dfmean=dfmean, i_stim=dict_i['i_stim'], i_EPSP=dict_i['i_EPSP_amp'])
    if dict_i['i_VEB'] is np.nan:
        return dict_i
    dict_i['i_EPSP_slope'] = find_i_EPSP_slope_bis0(dfmean=dfmean, i_VEB=dict_i['i_VEB'] , i_EPSP=dict_i['i_EPSP_amp'], happy=True)
    if dict_i['i_EPSP_slope'] is np.nan:
        return dict_i
    dict_i['i_volley_slope'] = find_i_volley_slope(dfmean=dfmean, i_stim=dict_i['i_stim'], i_VEB=dict_i['i_VEB'], happy=True)
    if dict_i['i_volley_slope'] is np.nan:
        return dict_i
    dict_i['i_volley_amp']= dfmean.loc[dict_i['i_volley_slope']:dict_i['i_VEB'], 'voltage'].idxmin() # TODO: make proper function
    return dict_i


# %%
def i2t(dfmean, dict_i, verbose=False):
    # Converts dict_i (index) to dict_t (time from start of sweep in dfmean)
    dict_t = {}
    for k, v in dict_i.items():
        k_new = "t" + k[1:]
        dict_t[k_new] = np.nan if v is np.nan else dfmean.loc[v].time
    return dict_t


# %%
def find_all_t(dfmean, param_min_time_from_i_stim=0.0005, verbose=False):
    """
    Acquires indices via find_all_t() for the provided dfmean and converts them to time values
    Returns a dict of all t-values provided by find_all_t()
    """
    if verbose:
        print("find_all_t")
    #print(f' . dfmean: {dfmean}')
    dict_i = find_all_i(dfmean, param_min_time_from_i_stim=0.0005)
    print (f"dict_i: {dict_i}")
    dict_t = i2t(dfmean, dict_i)
    if verbose:
        print(f"dict_t: {dict_t}")
    return dict_t


# %%
def measureslope(df, t_slope, halfwidth, name="EPSP"):
    """
    Generalized function
    """
    
    print(f'measureslope(df: {df}, t_slope: {t_slope}, halfwidth: {halfwidth}, name="EPSP"):')

    reg = linear_model.LinearRegression()
    dicts = []
    for sweep in tqdm(df.sweep.unique()): # this is just a progress indicator!
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[((t_slope - halfwidth) <= dftemp1.time) & (dftemp1.time <= (t_slope + halfwidth))]
        x = dftemp2.index.values.reshape(-1, 1)
        y = dftemp2.voltage.values.reshape(-1, 1)

        reg.fit(x, y)
        dict_slope = {
            "sweep": sweep,
            "value": reg.coef_[0][0],
            "type": name + "_slope",
            "algorithm": "linear",
        }
        dicts.append(dict_slope)

    df_slopes = pd.DataFrame(dicts)

    return df_slopes


# %%
def measureslope_vec(df, t_slope, halfwidth, name="EPSP", filter='voltage',):
    """
    vectorized measure slope
    """

    #print(f'measureslope(df: {df}, t_slope: {t_slope}, halfwidth: {halfwidth}, name="EPSP"):')

    df_filtered = df[((t_slope - halfwidth) <= df.time) & (df.time <= (t_slope + halfwidth))]
    #print(f"df before pivot:{df_filtered.shape}")
    dfpivot = df_filtered.pivot(index='sweep', columns='time', values=filter)
    coefs = np.polyfit(dfpivot.columns, dfpivot.T, deg=1).T
    dfslopes = pd.DataFrame(index=dfpivot.index)
    dfslopes['type'] = name + "_slope"
    dfslopes['algorithm'] = 'linear'
    dfslopes['value'] = coefs[:, 0]  # TODO: verify that it was the correct columns, and that values are reasonable

    return dfslopes


# %%
''' Standalone test:'''
if __name__ == "__main__":
    from pathlib import Path
    import matplotlib.pyplot as plt
    print()
    print()
    print("Running as main: standalone test")
    #path_filterfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_Ch1_a_filter.csv")
    #dffilter = pd.read_csv(str(path_filterfile)) # a persisted csv-form of the data file
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_21_P0701-S2_Ch0_a_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_21_P0701-S2_Ch0_b_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_24_P0630-D4_Ch0_a_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_24_P0630-D4_Ch0_b_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/B_22_P0701-D3_Ch0_a_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/B_22_P0701-D3_Ch0_b_mean.csv")
    #path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/B_23_P0630-D3_Ch0_a_mean.csv")
    path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/B_23_P0630-D3_Ch0_b_mean.csv")
    
    dfmean = pd.read_csv(str(path_meanfile)) # a persisted average of all sweeps in that data file
    dfmean['tris'] = dfmean.bis.rolling(3, center=True).mean().diff()
    dict_t = find_all_t(dfmean) # use the average all sweeps to determine where all events are located (noise reduction)
    t_EPSP_slope = dict_t['t_EPSP_slope']
    fig, ax = plt.subplots(figsize=(20,10))
    plt.plot(dfmean['time'], dfmean['prim']*10, color='red')
    plt.plot(dfmean['time'], dfmean['bis']*25, color='green')
    plt.plot(dfmean['time'], dfmean['tris']*25, color='blue')
    dfmean['bis_roll'] = dfmean['bis'].rolling(9, center=True, win_type='blackman').mean()
    #plt.plot(dfmean['time'], dfmean['bis_roll']*25, color='blue')
    plt.axhline(y=0, linestyle='dashed', color='gray')
    #t_EPSP_slope = 0.0103
    plt.axvline(x=t_EPSP_slope, linestyle='dashed', color='gray')
    plt.axvline(x=t_EPSP_slope-0.0003, linestyle='dashed', color='gray')
    plt.axvline(x=t_EPSP_slope+0.0003, linestyle='dashed', color='gray')
    plt.plot(dfmean['time'], dfmean['voltage'], color='black')
    mean_ylim = (-0.0006, 0.0005)
    mean_xlim = (0.006, 0.020)
    plt.xlim(mean_xlim)
    plt.ylim(mean_ylim)
    print(dict_t)