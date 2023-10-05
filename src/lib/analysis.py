# %%
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import scipy  # peakfinder and other useful analysis tools
from sklearn import linear_model
from tqdm import tqdm
import time

# %%
from joblib import Memory

# %%
memory = Memory("joblib", verbose=1)


# %%
def build_dfoutput(dfdata, t_EPSP_amp, t_EPSP_slope):#, t_volley_amp, t_volley_slope, t_volley_slope_size, output_path):
    # Incomplete function: only resolves EPSP_amp for now
    """Measures each sweep in df (e.g. from <save_file_name>.csv) at specificed times t_* 
    Args:
        df: a dataframe containing numbered sweeps, timestamps and voltage
        t_EPSP_amp: time of lowest point of EPSP
        t_EPSP_slope: time of centre of EPSP_slope
        t_EPSP_slope_size: width of EPSP slope
        t_volley_amp: time of lowest point of volley
        t_volley_slope: time of centre of volley_slope
        t_volley_slope_size: width of volley slope
        Optional
            output_path: if present, store results to this path (csv)
    Returns:
        a dataframe. Per sweep (row): EPSP_amp, EPSP_slope, volley_amp, volley_EPSP
    """
    t0 = time.time()
    dfoutput = pd.DataFrame()
    dfoutput['sweep'] = dfdata.sweep.unique() # one row per unique sweep in data file
    # EPSP_amp
    if t_EPSP_amp is not np.nan:
        df_EPSP_amp = dfdata[dfdata['time']==t_EPSP_amp].copy() # filter out all time (from sweep start) that do not match t_EPSP_amp
        df_EPSP_amp.reset_index(inplace=True)
        dfoutput['EPSP_amp'] = df_EPSP_amp['voltage'] # add the voltage of selected times to dfoutput
    else:
        dfoutput['EPSP_amp'] = np.nan
    # EPSP_slope
    if t_EPSP_slope is not np.nan:
        df_EPSP_slope = measureslope(df=dfdata, t_slope=t_EPSP_slope, halfwidth=0.0004)
        dfoutput['EPSP_slope'] = df_EPSP_slope['value']
    else:
        dfoutput['EPSP_slope'] = np.nan
    t1 = time.time()
    print(f'time elapsed: {t1-t0} seconds')
    return dfoutput


# %%
def find_i_stim_prim_max(dfmean):
    # TODO: return an index of sufficiently separated over-threshold x:es instead
    return dfmean["prim"].idxmax()


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
        -dfmean["voltage"],
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

    i_EPSP = i_peaks[properties["prominences"].argmax()]
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
    prim_sample = dfmean["prim"].values[minimum_acceptable_i_for_VEB:max_acceptable_i_for_VEB]

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

    i_VEB = i_peaks[properties["prominences"].argmax()]
    if verbose:
        print(f" . . . i_VEB: {i_VEB}")

    return i_VEB


# %%
def find_i_EPSP_slope(dfmean, i_VEB, i_EPSP, happy=False):
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
def find_i_volleyslope(dfmean, i_stim, i_VEB, happy=False):  # , param_half_slope_width = 4):
    """
    DOES NOT USE WIDTH! decided by rolling, earlier?

    returns time of volley slope center,
        as identified by positive zero-crossings in the second order derivative
        if several are found, it returns the latest one
    """

    dftemp = dfmean.bis[i_stim:i_VEB]
    i_volleyslope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    # print(dftemp.apply(np.sign).diff())
    # print(i_volleyslope)
    if 1 < len(i_volleyslope):
        if not happy:
            raise ValueError(f"Found multiple positive zero-crossings in dfmean.bis[i_stim: i_VEB]:{i_volleyslope}")
        else:
            print("More volleys than than we wanted but Im happy, so I pick one and move on.")
    return i_volleyslope[0]


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
        "i_EPSP_slope": np.nan}
    dict_i['i_stim'] = find_i_stim_prim_max(dfmean=dfmean,)
    if dict_i['i_stim'] is np.nan: # TODO: will not happen in current configuration
        return dict_i
    dict_i['i_EPSP_amp'] = find_i_EPSP_peak_max(dfmean=dfmean, verbose=True)
    if dict_i['i_EPSP_amp'] is np.nan: # TODO: will not happen in current configuration
        return dict_i
    dict_i['i_VEB'] = find_i_VEB_prim_peak_max(dfmean=dfmean, i_stim=dict_i['i_stim'], i_EPSP=dict_i['i_EPSP_amp'])
    if dict_i['i_VEB'] is np.nan:
        return dict_i
    dict_i['i_EPSP_slope'] = find_i_EPSP_slope(dfmean=dfmean, i_VEB=dict_i['i_VEB'] , i_EPSP=dict_i['i_EPSP_amp'], happy=True)
    """
    i_volleyslope = find_i_volleyslope(
        dfmean, (i_stim + param_min_time_from_i_stim), i_VEB, happy=True)
    """
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

    # off-challenge: this is what crashes it!
    t_slope = 0.001

    reg = linear_model.LinearRegression()
    dicts = []
    for sweep in tqdm(df.sweep.unique()): # this is just a progress indicator!
        dftemp1 = df[df.sweep == sweep]
        dftemp2 = dftemp1[((t_slope - halfwidth) <= dftemp1.time) & (dftemp1.time <= (t_slope + halfwidth))]
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

# %%
''' Standalone test:'''
if __name__ == "__main__":
    print()
    print()
    print("Running as main: standalone test")
    from pathlib import Path
    path_datafile = Path.home() / ("Documents/Brainwash Projects/standalone_test/data/KO_02.csv")
    path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_mean.csv")
    # path_datafile = Path.home() / ("Documents/Brainwash Projects/standalone_test/data/A_21_P0701-S2.csv")
    # path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/A_21_P0701-S2_mean.csv")
    dfdata = pd.read_csv(str(path_datafile)) # a persisted csv-form of the data file
    df_mean = pd.read_csv(str(path_meanfile)) # a persisted average of all sweeps in that data file
    # dfdata_a = dfdata[(dfdata['stim']=='a')] # select stim 'a' only in data file
    # df_mean_a = df_mean[(df_mean['stim']=='a')] # select stim 'a' only in mean file
    dfdata_a = dfdata[(dfdata['channel']==0) & (dfdata['stim']=='b')] # select stim 'a' only in data file
    df_mean_a = df_mean[(df_mean['channel']==0) & (df_mean['stim']=='b')] # select stim 'a' only in mean file
    df_mean_a.reset_index(inplace=True)
    dict_t = find_all_t(df_mean_a) # use the average all sweeps to determine where all events are located (noise reduction)
    t_EPSP_amp = dict_t['t_EPSP_amp']
    t_EPSP_slope = dict_t['t_EPSP_slope']
    dfoutput = build_dfoutput(dfdata=dfdata_a,
                              t_EPSP_amp=t_EPSP_amp,
                              t_EPSP_slope=t_EPSP_slope)
    print(dfoutput)



# The following section is for rapid prototyping in jupyter lab

'''

# %%
if __name__ == "__main__":
    print("Running as main")
    import parse
    from pathlib import Path
    path_datafile = Path.home() / ("Documents/Brainwash Projects/standalone_test/A_21_P0701-S2.csv")
    #path_datafile = Path("/home/matolo/Documents/Brainwash Projects/My Project/A_21_P0701-S2_2022_07_01_0000.abf.csv")
    dfdata = pd.read_csv(str(path_datafile))
    t_EPSP_amp = 0.0128
    buildResultFile(df=dfdata, t_EPSP_amp=t_EPSP_amp)
    print(dfdata)

# %%
if __name__ == "__main__":
    test = dfdata[dfdata.time == t_EPSP_amp]
    dfpivot = dfdata[['sweep', 'voltage', 'time']].pivot_table(values='voltage', columns = 'time', index = 'sweep')
    ser_startmedian = dfpivot.iloc[:,:20].median(axis=1)
    df_calibrated = dfpivot.subtract(ser_startmedian, axis = 'rows')
    df_calibrated = df_calibrated.stack().reset_index()
    df_calibrated.rename(columns = {0: 'volt_cal'}, inplace=True)
    df_calibrated.sort_values(by=['sweep', 'time'], inplace=True)
    df['volt_cal'] = df_calibrated.volt_cal

# %%
import matplotlib.pyplot as plt
if __name__ == "__main__":
    width = 0.005
    dfplot = df.copy()
    dfplot = dfplot[(0.0128-width < dfplot.time) & (dfplot.time < 0.0128+width)]
    dfplot['odd'] = dfplot.sweep %2 == 0
    print(dfplot.odd.sum()/dfplot.shape[0])
    plt.scatter(dfplot[~dfplot.odd]['time'], dfplot[~dfplot.odd]['volt_cal'])
    plt.scatter(dfplot[dfplot.odd]['time'], dfplot[dfplot.odd]['volt_cal'])
    #plt.hist(dfplot[~dfplot.odd]['volt_cal'], bins=100)
    #plt.hist(dfplot[dfplot.odd]['volt_cal'], bins=100)

# %%
if __name__ == "__main__":
    df_sample = df[df.sweep.isin([0,1,120,121,240,241,300,301,700,701])]
    df_sample.plot(x = 'time', y='volt_cal', ylim = (-0.001, 0.0001))

# %%
if __name__ == "__main__":
    df['datetime'] = pd.to_datetime(df.datetime)
    print(df.datetime.dtype)
    df.sort_values('datetime').datetime.is_monotonic_increasing
    print(df.datetime.is_monotonic_increasing)

# %%
if __name__ == "__main__":
    import seaborn as sns
    #dfplot = df.copy()
    #dfplot = dfplot[(0.01 < dfplot.time) & (dfplot.time < 0.02)]
    #dfplot['odd'] = dfplot.sweep %2 == 0
    sns.histplot(data=dfplot, x='volt_cal', hue='odd')

# %%
if __name__ == "__main__":
    dfplot[~dfplot.odd].volt_cal.std() / dfplot[dfplot.odd].volt_cal.std()
    #dfplot[~dfplot.odd].volt_cal.quantile(0.0001) / dfplot[dfplot.odd].volt_cal.quantile(0.0001)

# %%
if __name__ == "__main__":
    grouping = df[['sweep', 'voltage']].groupby(['sweep']).mean().plot()#x = 'sweep', y='voltage')#, ylim = (-0.001, 0.001))
    #print(grouping)

# %%
if __name__ == "__main__":
    result = dfplot[(dfplot.time == t_EPSP_amp)][['volt_cal','sweep', 'odd']]
    print(result)
    #result.plot(x = 'sweep')
    #result['c_odd'] = '1' if result.odd else '0'
    sns.lineplot(data = result, x = 'sweep', y = 'volt_cal', hue = 'odd')

# %%
if __name__ == "__main__":
    result = df[df.time == 0.001][['sweep', 'volt_cal']]
    g = result.plot(x = 'sweep')
    g.hlines(y=[-0.0001, 0.0001], xmin=0, xmax=1000)

# %%
if __name__ == "__main__":
    path_meanfile = Path("/home/matolo/Documents/Brainwash Projects/standalone_test/A_21_P0701-S2_mean.csv")
    df_mean = pd.read_csv(str(path_meanfile))
    print(df_mean.shape)
    print(df_mean)
    sns.lineplot(data = df_mean, x = 'time', y = 'voltage')
    plt.ylim(-0.0003,0.0001)
    plt.xlim(0.005,0.04)
    #sns.set_ylim(ui.graph_ylim)

    #df_mean.plot(x = 'time', y = 'voltage', ymin = -0.001, ymax = 0.0001)

# %%
if __name__ == "__main__":
    width = 0.0005
    result = df[(df.time - width < t_EPSP_amp) & (t_EPSP_amp < df.time + width)][['sweep', 'voltage']]
    print(result)
    result.pivot_table(index='sweep', aggfunc='median').plot()
    #result.pivot_table(index='sweep', aggfunc='median').rolling(50).median().plot()

# %%
if __name__ == "__main__":
    df_calibrated.sort_values(by=['sweep', 'time'], inplace=True)
    print(df_calibrated)

# %%
'''