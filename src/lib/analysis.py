# %%
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
from scipy.signal import savgol_filter, find_peaks
from scipy import stats # for regression_line
from sklearn import linear_model
import time



def valid(num):
    #print(f"num: {num}, type: {type(num)}")
    return num is not None and not np.isnan(num)


def regression_line(x_data, y_data):
    # Calculate linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x_data, y_data)

    # Generate x values from the min to max range of x data for plotting the regression line
    x = np.linspace(x_data.min(), x_data.max(), 100)
    y = slope * x + intercept
    
    return {
        'x': x,
        'y': y,
        'r_value': r_value,
        'p_value': p_value,
        'std_err': std_err
    }


# %%
def build_dfoutput(df, dict_t, filter='voltage', quick=False):
    # TODO: implement quick, to operate without amp_hws
    """Measures each sweep in df (e.g. from <save_file_name>.csv) at specificed times t_* 
    Args:
        df: a dataframe containing numbered sweeps, timestamps and voltage
        dict_t: a dictionary of measuring points
        lineEdit: a dictionary of user settings

    Returns:
        a dataframe. Per sweep (row): EPSP_amp, EPSP_slope, volley_amp, volley_EPSP
    """
    t0 = time.time()
    # print (f"build_dfoutput: {dict_t}")
    normFrom = dict_t['norm_output_from'] # start
    normTo = dict_t['norm_output_to'] # end
    list_col = ['stim', 'sweep']
    dfoutput = pd.DataFrame()
    dfoutput['sweep'] = df.sweep.unique() # one row per unique sweep in data file
    dfoutput['stim'] = dict_t['stim']

    # EPSP_amp
    if 't_EPSP_amp' in dict_t.keys():
        t_EPSP_amp = dict_t['t_EPSP_amp']
        if valid(t_EPSP_amp):
            amp_zero = dict_t['amp_zero']
            EPSP_hw = dict_t['t_EPSP_amp_halfwidth']
            if EPSP_hw == 0 or quick: #single point
                df_EPSP_amp = df[df['time']==t_EPSP_amp].copy() # filter out all time (from sweep start) that do not match t_EPSP_amp
                df_EPSP_amp.reset_index(inplace=True, drop=True)
                dfoutput['EPSP_amp'] = -1000 * df_EPSP_amp[filter] # invert and convert to mV
            else: # mean (SLOW)
                start_time = t_EPSP_amp - EPSP_hw
                end_time = t_EPSP_amp + EPSP_hw
                dfoutput['EPSP_amp'] = df.groupby('sweep').apply(lambda sweep_df: ((sweep_df.loc[(sweep_df['time'] >= start_time) & (sweep_df['time'] <= end_time), filter].mean() - amp_zero) * -1000)) # convert to mV for output
        else:
            dfoutput['EPSP_amp'] = np.nan
        # Normalize EPSP_amp
        selected_values = dfoutput[(dfoutput.index >= normFrom) & (dfoutput.index <= normTo)]['EPSP_amp']
        norm_mean = selected_values.mean() / 100  # divide by 100 to get percentage
        dfoutput['EPSP_amp_norm'] = dfoutput['EPSP_amp'] / norm_mean
        list_col.extend(['EPSP_amp', 'EPSP_amp_norm'])
    # EPSP_slope
    if 't_EPSP_slope_start' in dict_t.keys():
        t_EPSP_slope_start = dict_t['t_EPSP_slope_start']
        t_EPSP_slope_end = dict_t['t_EPSP_slope_end']
        if valid(t_EPSP_slope_start):
            df_EPSP_slope = measureslope_vec(df=df, filter=filter, t_start=t_EPSP_slope_start, t_end=t_EPSP_slope_end)
            dfoutput['EPSP_slope'] = -df_EPSP_slope['value'] # invert 
        else:
            dfoutput['EPSP_slope'] = np.nan
        # Normalize EPSP_slope
        selected_values = dfoutput[(dfoutput.index >= normFrom) & (dfoutput.index <= normTo)]['EPSP_slope']
        norm_mean = selected_values.mean() / 100  # divide by 100 to get percentage
        dfoutput['EPSP_slope_norm'] = dfoutput['EPSP_slope'] / norm_mean
        list_col.extend(['EPSP_slope', 'EPSP_slope_norm'])
    # volley_amp
    if 't_volley_amp' in dict_t.keys():
        t_volley_amp = dict_t['t_volley_amp']
        if valid(t_volley_amp):
            amp_zero = dict_t['amp_zero']
            volley_hw = dict_t['t_volley_amp_halfwidth']
            if volley_hw == 0 or quick: # single point
                df_volley_amp = df[df['time']==t_volley_amp].copy() # filter out all time (from sweep start) that do not match t_volley_amp
                df_volley_amp.reset_index(inplace=True, drop=True)
                dfoutput['volley_amp'] = -1000 * df_volley_amp[filter] # invert and convert to mV
            else: # mean (SLOW)
                start_time = t_volley_amp - volley_hw
                end_time = t_volley_amp + volley_hw
                dfoutput['volley_amp'] = df.groupby('sweep').apply(lambda sweep_df: ((sweep_df.loc[(sweep_df['time'] >= start_time) & (sweep_df['time'] <= end_time), filter].mean() - amp_zero) * -1000)) # convert to mV for output
        else:
            dfoutput['volley_amp'] = np.nan
        list_col.append('volley_amp')
    # volley_slope
    if 't_volley_slope_start' in dict_t.keys():
        t_volley_slope_start = dict_t['t_volley_slope_start']
        t_volley_slope_end = dict_t['t_volley_slope_end']
        if valid(t_volley_slope_start):
            df_volley_slope = measureslope_vec(df=df, filter=filter,  t_start=t_volley_slope_start, t_end=t_volley_slope_end)
            dfoutput['volley_slope'] = -df_volley_slope['value'] # invert 
        else:
            dfoutput['volley_slope'] = np.nan
        list_col.append('volley_slope')

    # print(f'build_df_output: {round((time.time()-t0)*1000)} ms, list_col: {list_col}')
    return dfoutput[list_col]


def build_dfstimoutput(df, df_t, filter='voltage'):
    t0 = time.time()
    df_stimoutput = pd.DataFrame(index=df_t.index, columns=['stim', 'bin', 'EPSP_amp', 'EPSP_amp_norm', 'EPSP_slope', 'EPSP_slope_norm', 'volley_amp', 'volley_slope'])
    # print (f"build_dfstimoutput: {df_t}")

    for i, t_row in df_t.iterrows():
        normFrom = t_row['norm_output_from'] # start
        normTo = t_row['norm_output_to'] # end
        amp_zero = t_row['amp_zero']
        EPSP_hw = t_row['t_EPSP_amp_halfwidth']
        volley_hw = t_row['t_volley_amp_halfwidth']
        df_stimoutput.at[i, 'stim'] = t_row['stim']

        # EPSP_amp
        if valid(t_row['t_EPSP_amp']):
            start_time = t_row['t_EPSP_amp'] - EPSP_hw
            end_time = t_row['t_EPSP_amp'] + EPSP_hw
            start_index = np.abs(df['time'] - start_time).idxmin()
            end_index = np.abs(df['time'] - end_time).idxmin()
            df_EPSP_amp = df.iloc[start_index:end_index+1].copy()
            df_EPSP_amp.reset_index(drop=True, inplace=True)
            df_stimoutput.at[i, 'EPSP_amp'] = (df_EPSP_amp[filter].mean() - amp_zero) * -1000 if not df_EPSP_amp.empty else np.nan
            # Normalize EPSP_amp
            selected_values = df_stimoutput['EPSP_amp'][normFrom:normTo+1]
            norm_mean = np.mean(selected_values) / 100  # divide by 100 to get percentage
            df_stimoutput.at[i, 'EPSP_amp_norm'] = df_stimoutput.at[i, 'EPSP_amp'] / norm_mean if norm_mean else np.nan
        # EPSP_slope
        if valid(t_row['t_EPSP_slope_start']) and valid(t_row['t_EPSP_slope_end']):
            slope_EPSP = measureslope(df=df, filter=filter, t_start=t_row['t_EPSP_slope_start'], t_end=t_row['t_EPSP_slope_end'])
            df_stimoutput.at[i, 'EPSP_slope'] = -slope_EPSP if slope_EPSP else np.nan
            # Normalize EPSP_slope
            selected_values = df_stimoutput['EPSP_slope'][normFrom:normTo+1]
            norm_mean = np.mean(selected_values) / 100  # divide by 100 to get percentage
            df_stimoutput.at[i, 'EPSP_slope_norm'] = df_stimoutput.at[i, 'EPSP_slope'] / norm_mean if norm_mean else np.nan
        # volley_amp
        if valid(t_row['t_volley_amp']):
            start_time = t_row['t_volley_amp'] - volley_hw
            end_time = t_row['t_volley_amp'] + volley_hw
            start_index = np.abs(df['time'] - start_time).idxmin()
            end_index = np.abs(df['time'] - end_time).idxmin()
            df_volley_amp = df.iloc[start_index:end_index+1].copy()
            df_volley_amp.reset_index(drop=True, inplace=True)
            df_stimoutput.at[i, 'volley_amp'] = (df_volley_amp[filter].mean() - amp_zero) * -1000 if not df_volley_amp.empty else np.nan
        # volley_slope
        if valid(t_row['t_volley_slope_start']) and valid(t_row['t_volley_slope_end']):
            volley_EPSP = measureslope(df=df, filter=filter, t_start=t_row['t_volley_slope_start'], t_end=t_row['t_volley_slope_end'])
            df_stimoutput.at[i, 'volley_slope'] = -volley_EPSP if volley_EPSP else np.nan

    # print(f'build_df_stimoutput: {round((time.time()-t0)*1000)} ms, columns: {df_stimoutput.columns}')
    return df_stimoutput


def addFilterSavgol(df, window_length=9, poly_order=3):
    # returns a column containing a smoothed version of the voltage column in a df; dfmean or dffilter
    df['savgol'] = savgol_filter(df.voltage, window_length=window_length, polyorder=poly_order)
    return df['savgol']


# %%
def find_i_stim_prim_max(dfmean):
    return dfmean['prim'].idxmax()


# %%
def find_i_stims(dfmean, threshold=0.1, min_time_difference=0.005, verbose=False):
    prim_max = find_i_stim_prim_max(dfmean)
    prim_max_y = dfmean.prim.max()
    threshold *= prim_max_y

    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    # Filter the indices to ensure they are more than min_time_difference apart
    filtered_indices = []
    max_index = above_threshold_indices[0]
    for i in range(1, len(above_threshold_indices)):
        current_index = above_threshold_indices[i]
        previous_index = above_threshold_indices[i - 1]
        if dfmean['time'][current_index] - dfmean['time'][previous_index] > min_time_difference:
            filtered_indices.append(max_index)
            max_index = current_index
        elif dfmean['prim'][current_index] > dfmean['prim'][max_index]:
            max_index = current_index
    filtered_indices.append(max_index)
    if verbose:
        print(f"find_i_stims: {filtered_indices}, type: {type(filtered_indices)}")
    return filtered_indices

# %%
def find_i_EPSP_peak_max(
    dfmean,
    sampling_Hz=10000,
    limitleft=0, # index - not time
    limitright=-1, # index - not time
    param_EPSP_minimum_width_ms=4,  # width in ms
    param_EPSP_minimum_prominence_mV=0.0001,  # what unit? TODO: find out!
    verbose=False
):
    """
    width and limits in index, promincence in Volt
    returns index of center of broadest negative peak on dfmean
    """
    if verbose:
        print("find_i_EPSP_peak_max:")

    # convert EPSP width from ms to index
    EPSP_minimum_width_i = int(
        param_EPSP_minimum_width_ms * 0.001 * sampling_Hz
    )  # 0.001 for ms to seconds, *sampling_Hz for seconds to recorded points
    if verbose:
        print(" . . . EPSP must be at least", EPSP_minimum_width_i, "points wide")

    # Slice dfmean according to limitleft and limitright
    if limitright != -1:
        dfmean_sliced = dfmean[(limitleft <= dfmean.index) & (dfmean.index <= limitright)]
    else:
        dfmean_sliced = dfmean[limitleft <= dfmean.index]

    # scipy.signal.find_peaks returns a tuple
    i_peaks, properties = find_peaks(
        -dfmean_sliced['voltage'],
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

    i_EPSP = i_peaks[properties['prominences'].argmax()] + limitleft
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
    i_peaks, properties = find_peaks(
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
def find_i_EPSP_slope_mindist_bis0(dfmean, i_VEB, i_EPSP, EPSP_slope_size=3, happy=False): # TODO: set rolling_width to 2(EPSP width)+1
    # Experimental: not used
    """ Look for lowest sum of deviation from straight line (= 0 bis)"""
    width = 2 * EPSP_slope_size + 1
    sertemp = dfmean.bis[i_VEB+4:i_EPSP].abs()
    sertemp = sertemp.rolling(width, center=True).mean().diff()

    i_EPSP_slope = sertemp[0 < sertemp.apply(np.sign)].index.values - 1 # compensate for diff coming after local minimas
    if 1 < len(i_EPSP_slope):
        if not happy:
            raise ValueError(f"Found multiple positive zero-crossings in dfmean.bis[i_VEB: i_EPSP]:{i_EPSP_slope}")
        else:
            print("More EPSPs than we wanted but I'm happy, so I pick the first one and move on.")
    print(f" . . . i_EPSP_slope: {i_EPSP_slope}")
    return i_EPSP_slope[0]


# %%
def find_i_volley_slope(dfmean, i_stim, i_VEB, happy=False):
    """
    returns index of volley slope center
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
def find_all_i(dfmean, i_stims=None, param_min_time_from_i_stim=0.0005, verbose=False):
    """
    Runs all index-detections in the appropriate sequence,
    The function finds VEB, but does not currently report it
    TODO: also report volley amp and slope
    Returns a DataFrame of all indices, with np.nan representing detection failure.
    """
    if i_stims is None:
        i_stims = find_i_stims(dfmean=dfmean)
    if not i_stims:
        return pd.DataFrame()

    # calculate sampling frequency
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    print(f"find_i_stims: {len(i_stims)}: sampling_Hz: {sampling_Hz}")
    print(i_stims)
    
    list_dict_i = []
    for i in i_stims:
        print(f"processing i_stim: {i}")
        dict_i = { #set default np.nan
            "i_stim": i,
            "i_VEB": np.nan,
            "i_EPSP_amp": np.nan,
            "i_EPSP_slope": np.nan,
            "i_volley_amp": np.nan,
            "i_volley_slope": np.nan,
            "t_volley_amp_method": "Auto",
            "t_volley_slope_method": "Auto",
            "t_EPSP_amp_method": "Auto",
            "t_EPSP_slope_method": "Auto",
            "t_volley_amp_params": "-",
            "t_volley_slope_params": "-",
            "t_EPSP_amp_params": "-",
            "t_EPSP_slope_params": "-",
        }
        dict_i['i_EPSP_amp'] = find_i_EPSP_peak_max(dfmean=dfmean, sampling_Hz=sampling_Hz, limitleft=i, limitright=i+200, verbose=True)
        if dict_i['i_EPSP_amp'] is not np.nan:
            dict_i['i_VEB'] = find_i_VEB_prim_peak_max(dfmean=dfmean, i_stim=i, i_EPSP=dict_i['i_EPSP_amp'])
            if dict_i['i_VEB'] is not np.nan:
                dict_i['i_EPSP_slope'] = find_i_EPSP_slope_bis0(dfmean=dfmean, i_VEB=dict_i['i_VEB'] , i_EPSP=dict_i['i_EPSP_amp'], happy=True)
                if dict_i['i_EPSP_slope'] is not np.nan:
                    dict_i['i_volley_slope'] = find_i_volley_slope(dfmean=dfmean, i_stim=i, i_VEB=dict_i['i_VEB'], happy=True)
                    if dict_i['i_volley_slope'] is not np.nan:
                        dict_i['i_volley_amp']= dfmean.loc[dict_i['i_volley_slope']:dict_i['i_VEB'], 'voltage'].idxmin() # TODO: make proper function
        list_dict_i.append(dict_i)
    df_i = pd.DataFrame(list_dict_i)
    df_i_numeric = df_i.select_dtypes(include=[np.number])
    list_nan = [i for i in range(len(df_i_numeric)) if df_i_numeric.iloc[i].isnull().any()]
    if list_nan:
        methods = ['t_volley_amp_method', 't_volley_slope_method', 't_EPSP_amp_method', 't_EPSP_slope_method']
        params = ['t_volley_amp_params', 't_volley_slope_params', 't_EPSP_amp_params', 't_EPSP_slope_params']
        # find a stim-row that has values in all columns, and use it as a template
        for i in range(len(df_i_numeric)):
            print(f"checking stim: {i}")
            if not df_i_numeric.iloc[i].isnull().any():
                # create a template for i_values based difference from i_stim
                i_values = df_i_numeric.iloc[i]
                i_template = {key: i_values[key] - i_stims[i] for key in i_values.keys()}
                # apply the template to all rows with np.nan
                for j in list_nan:
                    for key in df_i_numeric.columns:
                        df_i.loc[j, key] = i_stims[j] + i_template[key]
                    for key in methods:
                        df_i.loc[j, key] = "Extrapolated"
                    for key in params:
                        df_i.loc[j, key] = f"stim {i+1}" # user readable references are 1-indexed
                break
        else: # no stim-row with all values. Apply dodgy default values based on i_stim
            for index, row in df_i.iterrows():
                if row.isnull().any():  # if the row has any NaN value
                    stim = row['i_stim']
                    dict_default = { #set default 
                        "i_stim": stim,
                        "i_VEB": stim+20,
                        "i_EPSP_amp": stim+50,
                        "i_EPSP_slope": stim+20,
                        "i_volley_amp": stim+15,
                        "i_volley_slope": stim+10,
                        "t_volley_amp_method": "Default",
                        "t_volley_slope_method": "Default",
                        "t_EPSP_amp_method": "Default",
                        "t_EPSP_slope_method": "Default",
                        "t_volley_amp_params": "-",
                        "t_volley_slope_params": "-",
                        "t_EPSP_amp_params": "-",
                        "t_EPSP_slope_params": "-",
                    }
                    df_i.loc[index] = dict_default
                
    return df_i


# %%
def find_all_t(dfmean, default_dict_t, precision=None, param_min_time_from_i_stim=0.0005, verbose=False):
    """
    Acquires indices via find_all_i() for the provided dfmean and converts them to time values
    Returns a DataFrame of the t-values for each stim, as provided by find_all_i()
    """

    def i2t(index, dfmean, row, precision, default_dict_t):
        # Converts i (index) to t (time from start of sweep in dfmean)
        time_values = dfmean['time'].values
        if precision is None:
            precision = len(str(time_values[1] - time_values[0]).split('.')[1])
        volley_slope_halfwidth = default_dict_t['t_volley_slope_halfwidth']
        EPSP_slope_halfwidth = default_dict_t['t_EPSP_slope_halfwidth']
        t_EPSP_slope = dfmean.loc[row['i_EPSP_slope']].time if 'i_EPSP_slope' in row and row['i_EPSP_slope'] in dfmean.index else None
        t_volley_slope = dfmean.loc[row['i_volley_slope']].time if 'i_volley_slope' in row and row['i_volley_slope'] in dfmean.index else None
        t_EPSP_amp = dfmean.loc[row['i_EPSP_amp']].time if 'i_EPSP_amp' in row and row['i_EPSP_amp'] in dfmean.index else None
        t_volley_amp = dfmean.loc[row['i_volley_amp']].time if 'i_volley_amp' in row and row['i_volley_amp'] in dfmean.index else None
        amp_zero_idx_start = row['i_stim'] - 20 # TODO: fix hardcoded value
        amp_zero_idx_end = row['i_stim'] - 10 # TODO: fix hardcoded value
        amp_zero = dfmean.loc[amp_zero_idx_start:amp_zero_idx_end].voltage.mean() # TODO: fix hardcoded filter: "voltage"
        return {
            'stim': index+1,
            'amp_zero': amp_zero, # mean of dfmean.voltage 20-10 indices before i_stim, in Volts
            't_stim': round(dfmean.loc[row['i_stim']].time, precision),
            't_volley_slope_start': round(t_volley_slope - volley_slope_halfwidth, precision) if t_volley_slope is not None else None,
            't_volley_slope_end': round(t_volley_slope + volley_slope_halfwidth, precision) if t_volley_slope is not None else None,
            't_EPSP_slope_start': round(t_EPSP_slope - EPSP_slope_halfwidth, precision) if t_EPSP_slope is not None else None,
            't_EPSP_slope_end': round(t_EPSP_slope + EPSP_slope_halfwidth, precision) if t_EPSP_slope is not None else None,
            't_EPSP_amp': round(t_EPSP_amp, precision) if t_EPSP_amp is not None else None,
            't_volley_amp': round(t_volley_amp, precision) if t_volley_amp is not None else None,
        }

    df_indices = find_all_i(dfmean, param_min_time_from_i_stim=0.0005)
    print(f"df_indices: {df_indices}")

    # TODO: WIP use default_dict_t

    # Convert each index to a dictionary of t-values and add it to a list
    list_of_dict_t = []
    for index, row in df_indices.iterrows():
        result = i2t(index, dfmean, row, precision, default_dict_t)
        dict_t = default_dict_t.copy()
        dict_t.update(result)
        list_of_dict_t.append(dict_t)

    # Convert the list of dictionaries to a DataFrame
    df_t = pd.DataFrame(list_of_dict_t)

    # conserve all columns that already start with "t_"
    list_t_columns_in_df_indices = [col for col in df_indices.columns if col.startswith('t_')]
    for col in list_t_columns_in_df_indices:
        df_t[col] = df_indices[col]

    if verbose:
        print(f"df_t: {df_t}")

    return df_t


def measureslope(df, t_start, t_end, filter='voltage'):
    reg = linear_model.LinearRegression()
    # Select the data between start and end time points
    dftemp = df[(t_start <= df.time) & (df.time <= t_end)]
    x = dftemp.time.values.reshape(-1, 1)
    y = dftemp[filter].values.reshape(-1, 1)  # use the filter instead of 'voltage'
    # Fit the linear regression model and calculate the slope
    reg.fit(x, y)
    slope = reg.coef_[0][0]
    return slope


# %%
def measureslope_vec(df, t_start, t_end, name="EPSP", filter='voltage',):
    """
    vectorized measure slope
    """
    df_filtered = df[(t_start <= df.time) & (df.time <= t_end)] # NB: including start and end
    dfpivot = df_filtered.pivot(index='sweep', columns='time', values=filter)
    coefs = np.polyfit(dfpivot.columns, dfpivot.T, deg=1).T
    dfslopes = pd.DataFrame(index=dfpivot.index)
    dfslopes['type'] = name + "_slope"
    dfslopes['algorithm'] = 'linear'
    dfslopes['value'] = coefs[:, 0]
    # TODO: verify that it was the correct columns, and that values are reasonable
    return dfslopes


# %%
''' Standalone test:'''
if __name__ == "__main__":
    # Temporary default_dict_t for standalone tests
    default_dict_t = { # default values for df_t(imepoints)
        'stim': 0,
        't_stim': 0,
        't_stim_method': 0,
        't_stim_params': 0,
        't_volley_slope_width': 0.0003,
        't_volley_slope_halfwidth': 0.0001,
        't_volley_slope_start': 0,
        't_volley_slope_end': 0,
        't_volley_slope_method': 'auto detect',
        't_volley_slope_params': 'NA',
        'volley_slope_mean': 0,
        't_volley_amp': 0,
        't_volley_amp_halfwidth': 0,
        't_volley_amp_method': 'auto detect',
        't_volley_amp_params': 'NA',
        'volley_amp_mean': 0,
        't_VEB': 0,
        't_VEB_method': 0,
        't_VEB_params': 0,
        't_EPSP_slope_width': 0.0007,
        't_EPSP_slope_halfwidth': 0.0003,
        't_EPSP_slope_start': 0,
        't_EPSP_slope_end': 0,
        't_EPSP_slope_method': 'auto detect',
        't_EPSP_slope_params': 'NA',
        't_EPSP_amp': 0,
        't_EPSP_amp_halfwidth': 0,
        't_EPSP_amp_method': 'auto detect',
        't_EPSP_amp_params': 'NA',
        'norm_output_from': 0,
        'norm_output_to': 0,
    }

    from pathlib import Path
    #path_filterfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/KO_02_Ch1_a_filter.csv")
    #dffilter = pd.read_csv(str(path_filterfile)) # a persisted csv-form of the data file
    path_meanfile = Path.home() / ("Documents/Brainwash Projects/standalone_test/cache/Good recording_Ch0_a_mean.csv")
    print(f"\n\n\nRunning as main: standalone test of {str(path_meanfile)}")
    dfmean = pd.read_csv(str(path_meanfile)) # a persisted average of all sweeps in that data file
    #dfmean['tris'] = dfmean.bis.rolling(3, center=True).mean().diff()
    list_dict_t = find_all_t(dfmean, default_dict_t=default_dict_t)
    print(list_dict_t)