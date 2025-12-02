# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter, find_peaks
import os
import json
import sys
from pathlib import Path
from sklearn.linear_model import LinearRegression
import time


reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))



# %%
def valid(*args):
    return all(isinstance(x, (int, float)) and x is not None and not np.isnan(x) for x in args)


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


def build_dfoutput(df, dict_t, filter='voltage', quick=False):
    print(f"{dict_t=}")
    # TODO: check amps width calculations
    # TODO: implement quick, to operate without amp_hws
    """Measures each sweep in df (e.g. from <save_file_name>.csv) at specificed times t_* 
    Args:
        df: a dataframe containing numbered sweeps, timestamps and voltage
        dict_t: a dictionary of measuring points

    Returns:
        a dataframe. Per sweep (row): EPSP_amp, EPSP_slope, volley_amp, volley_EPSP
    """
    t0 = time.time()
    print(f"build_dfoutput: {dict_t}")
    normFrom = dict_t['norm_output_from'] # start
    normTo = dict_t['norm_output_to'] # end
    list_col = ['stim', 'sweep']
    dfoutput = pd.DataFrame()
    dfoutput['sweep'] = df.sweep.unique() # one row per unique sweep in data file
    dfoutput['stim'] = dict_t['stim']

    # EPSP_amp
    if 't_EPSP_amp' in dict_t.keys():
        list_col.extend(['EPSP_amp', 'EPSP_amp_norm'])
        t_EPSP_amp = dict_t['t_EPSP_amp']
        if valid(t_EPSP_amp):
            amp_zero = dict_t['amp_zero']
            EPSP_w = dict_t['t_EPSP_amp_width'] if 't_EPSP_amp_width' in dict_t.keys() else 2 * dict_t['t_EPSP_amp_halfwidth']
            if EPSP_w == 0 or quick: #single point
                df_EPSP_amp = df[df['time']==t_EPSP_amp].copy() # filter out all time (from sweep start) that do not match t_EPSP_amp
                df_EPSP_amp.reset_index(inplace=True, drop=True)
                dfoutput['EPSP_amp'] = -1000 * df_EPSP_amp[filter] # invert and convert to mV
            else: # mean (SLOW)
                start_time = t_EPSP_amp - EPSP_w
                end_time = t_EPSP_amp + EPSP_w
                dfoutput['EPSP_amp'] = df.groupby('sweep').apply(lambda sweep_df: ((sweep_df.loc[(sweep_df['time'] >= start_time) & (sweep_df['time'] <= end_time), filter].mean() - amp_zero) * -1000)) # convert to mV for output
            # Normalize EPSP_amp
            selected_values = dfoutput[(dfoutput.index >= normFrom) & (dfoutput.index <= normTo)]['EPSP_amp']
            norm_mean = selected_values.mean() / 100  # divide by 100 to get percentage
            dfoutput['EPSP_amp_norm'] = dfoutput['EPSP_amp'] / norm_mean
        else:
            dfoutput['EPSP_amp'] = np.nan

    # EPSP_slope
    if 't_EPSP_slope_start' in dict_t.keys():
        list_col.extend(['EPSP_slope', 'EPSP_slope_norm'])
        t_EPSP_slope_start = dict_t['t_EPSP_slope_start']
        t_EPSP_slope_end = dict_t['t_EPSP_slope_end']
        if valid(t_EPSP_slope_start, t_EPSP_slope_end) and t_EPSP_slope_start < t_EPSP_slope_end:
            df_EPSP_slope = measureslope_vec(df=df, filter=filter, t_start=t_EPSP_slope_start, t_end=t_EPSP_slope_end)
            dfoutput['EPSP_slope'] = -df_EPSP_slope['value'] # invert 
            # Normalize EPSP_slope
            selected_values = dfoutput[(dfoutput.index >= normFrom) & (dfoutput.index <= normTo)]['EPSP_slope']
            norm_mean = selected_values.mean() / 100  # divide by 100 to get percentage
            dfoutput['EPSP_slope_norm'] = dfoutput['EPSP_slope'] / norm_mean
        else:
            dfoutput['EPSP_slope'] = np.nan
            dfoutput['EPSP_slope_norm'] = np.nan

    # volley_amp
    if 't_volley_amp' in dict_t.keys():
        list_col.append('volley_amp')
        t_volley_amp = dict_t['t_volley_amp']
        if valid(t_volley_amp):
            amp_zero = dict_t['amp_zero']
            volley_w = dict_t['t_volley_amp_width'] if 't_volley_amp_width' in dict_t.keys() else 2 * dict_t['t_volley_amp_halfwidth']
            if volley_w == 0 or quick: # single point
                df_volley_amp = df[df['time']==t_volley_amp].copy() # filter out all time (from sweep start) that do not match t_volley_amp
                df_volley_amp.reset_index(inplace=True, drop=True)
                dfoutput['volley_amp'] = -1000 * df_volley_amp[filter] # invert and convert to mV
            else: # mean (SLOW)
                start_time = t_volley_amp - volley_w
                end_time = t_volley_amp + volley_w
                dfoutput['volley_amp'] = df.groupby('sweep').apply(lambda sweep_df: ((sweep_df.loc[(sweep_df['time'] >= start_time) & (sweep_df['time'] <= end_time), filter].mean() - amp_zero) * -1000)) # convert to mV for output
        else:
            dfoutput['volley_amp'] = np.nan
    # volley_slope
    if 't_volley_slope_start' in dict_t.keys():
        list_col.append('volley_slope')
        t_volley_slope_start = dict_t['t_volley_slope_start']
        t_volley_slope_end = dict_t['t_volley_slope_end']
        if valid(t_volley_slope_start, t_volley_slope_end) and t_volley_slope_start < t_volley_slope_end:
            df_volley_slope = measureslope_vec(df=df, filter=filter,  t_start=t_volley_slope_start, t_end=t_volley_slope_end)
            dfoutput['volley_slope'] = -df_volley_slope['value'] # invert 
        else:
            dfoutput['volley_slope'] = np.nan

    print(f'build_df_output: {round((time.time()-t0)*1000)} ms, list_col: {list_col}')
    return dfoutput[list_col]



def addFilterSavgol(df, window_length=9, poly_order=3):
    # returns a column containing a smoothed version of the voltage column in a df; dfmean or dffilter
    df['savgol'] = savgol_filter(df.voltage, window_length=window_length, polyorder=poly_order)
    return df['savgol']


def find_i_stims(dfmean, threshold=0.1, min_time_difference=0.005, verbose=False):
    # Finds indices of stimulation events in a DataFrame based on the 'prim' column.
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


def find_events(dfmean, default_dict_t, i_stims=None, stim_amp=0.005, precision=None, verbose=False):
    """
    This function replaces the deprecated find_all_i and find_all_t
    1) Finds stims, if not provided
    2) Acquires i and t from characterize_graph() for the provided dfmean and converts index to time values
    3) Returns a DataFrame of the t-values for each stim
    """
    # i_stims: list of indices of stimulation artefacts in dfmean. If None, autodetects using find_i_stims.
    if i_stims is None:
        i_stims = find_i_stims(dfmean=dfmean)
    if not i_stims:
        print("find_events: no stimulation artefacts found. Returning empty DataFrame.")
        return pd.DataFrame()
    
    # calculate time delta and sampling frequency
    time_values = dfmean['time'].values
    time_delta = time_values[1] - time_values[0]
    sampling_Hz = 1 / time_delta

    if precision is None:
        precision = len(str(time_values[1] - time_values[0]).split('.')[1])

    if verbose:
        print(f"find_i_stims: {len(i_stims)}: sampling_Hz: {sampling_Hz}")
        print(i_stims)

    def unwrap(v):
        if isinstance(v, pd.Series):
            if len(v) == 1:
                return v.iloc[0]
            else:
                raise ValueError(f"Expected scalar or single-element Series, got Series with {len(v)} elements: {v}")
        return v
            
    def i2t(stim_nr, i_stim, df_event_range, time_delta, stim_char, precision, default_dict_t):
        # Converts i (index) to t (time from start of sweep in dfmean)
        t_stim = round(df_event_range.loc[i_stim].time, precision)
        # amp_zero_idx_start = df_event_range.loc[i_stim] - 20 # TODO: fix hardcoded value
        # amp_zero_idx_end = df_event_range.loc[i_stim] - 10 # TODO: fix hardcoded value
        # amp_zero = df_event_range.loc[amp_zero_idx_start:amp_zero_idx_end].voltage.mean() # TODO: fix hardcoded filter: "voltage"
        amp_zero = 0 # TODO: placeholder for debugging, remove when amp_zero is implemented

        # Volley
        if stim_char.get('volley_detected'):
            i_trough = stim_char['i_volley_trough']
            t_volley_amp = df_event_range.iloc[i_trough]['time'] if i_trough is not None else t_stim + 0.0007
            t_volley_slope_start = stim_char.get('t_volley_slope_start', t_stim + 0.001)
            if isinstance(t_volley_slope_start, np.ndarray):
                t_volley_slope_start = t_volley_slope_start[0][0]
            else:
                print("--- t_volley_slope_start NOT <numpy.ndarray> (check characterize_graph for consistency)")
            t_volley_amp_method = t_volley_slope_method = 'auto detect'
        else:
            t_volley_amp = t_stim + 0.0007 # default to 0.7 ms after stim
            t_volley_slope_start = t_stim + 0.001 # default to 1 ms after stim
            t_volley_amp_method = t_volley_slope_method = 'default'

        # EPSP
        if stim_char.get('epsp_detected'):
            i_epsp_min = stim_char['i_epsp_min']
            t_EPSP_amp = df_event_range.iloc[i_epsp_min]['time'] if i_epsp_min is not None else t_stim + 0.005
            # if t_EPSP_slope_start is type numpy.ndarray, pick the first element
            t_EPSP_slope_start = stim_char.get('t_EPSP_slope_start', t_stim + 0.002)
            if isinstance(t_EPSP_slope_start, np.ndarray):
                t_EPSP_slope_start = t_EPSP_slope_start[0][0]
            else:
                print("--- t_EPSP_slope_start NOT <numpy.ndarray> (check characterize_graph for consistency)")
            t_EPSP_amp_method = t_EPSP_slope_method = 'auto detect'
        else:
            t_EPSP_amp = t_stim + 0.005 # default to 5 ms after stim
            t_EPSP_slope_start = t_stim + 0.002 # default to 2 ms after stim
            t_EPSP_amp_method = t_EPSP_slope_method = 'default'
        # Calculate the end times for volley and EPSP slopes
        t_volley_slope_end = 0#round(t_volley_slope_start + default_dict_t['t_volley_slope_width'], precision)
        t_EPSP_slope_end = round(t_EPSP_slope_start + default_dict_t['t_EPSP_slope_width'], precision)

        result = {
            'stim': stim_nr,
            'amp_zero': amp_zero, # mean of dfmean.voltage 20-10 indices before i_stim, in Volts
            't_stim': t_stim,
            't_volley_slope_start': t_volley_slope_start,
            't_volley_slope_end': t_volley_slope_end,
            't_volley_slope_method': t_volley_slope_method,
            't_volley_amp': t_volley_amp,
            't_volley_amp_method': t_volley_amp_method,
            't_EPSP_slope_start': t_EPSP_slope_start,
            't_EPSP_slope_end': t_EPSP_slope_end,
            't_EPSP_slope_method': t_EPSP_slope_method,
            't_EPSP_amp': t_EPSP_amp,
            't_EPSP_amp_method': t_EPSP_amp_method,
        }
        return result

    # Convert each index to a dictionary of t-values and add it to a list
    list_of_dict_t = []
    margin_before = 5
    min_interval_samples = 200  # 20 ms at 10 kHz to ensure no overlap in up to 50Hz trains
    for stim_nr, i_stim in enumerate(i_stims, start=1):
        dict_t = default_dict_t.copy()
        # Define stop index, avoiding overlap with next stim
        if stim_nr < len(i_stims):
            next_stim = i_stims[stim_nr]
            stop = min(i_stim + min_interval_samples, next_stim)
        else:
            stop = i_stim + min_interval_samples
        # Define start index, with margin
        start = max(i_stim - margin_before, 0)
        df_event_range = dfmean.iloc[start:stop]
        stim_characteristics = characterize_graph(df_event_range, verbose=verbose)
        print(f"stim_characteristics: {stim_characteristics}")

        result = i2t(
            stim_nr=stim_nr,
            i_stim=i_stim,
            df_event_range=df_event_range,
            time_delta=time_delta,
            stim_char=stim_characteristics,
            precision=precision,
            default_dict_t=dict_t
        )
        # Unwrap any Panda Series to scalars
        print(f"find_events result: {result}")
        sanitized_result = {k: unwrap(v) for k, v in result.items()}
        dict_t.update(sanitized_result)

        list_of_dict_t.append(dict_t)

    # Create DataFrame from sanitized list of dictionaries
    df_t = pd.DataFrame(list_of_dict_t)

    if verbose:
        print(f"df_t: {df_t}")

    return df_t

    

# %%
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

def characterize_graph(df, stim_amp=0.005, verbose=False, plot=False, multiplots=False):
    """
    Characterize a graph based on feature prominence and shape consistency.
    Verbose messages are not completely built, add when needed to trouble shoot parts of the search algorithm
    If a specific feature search lacks verbose, it has worked well for the training set so far.

    Args:
        df (pd.DataFrame): DataFrame with 'time' and 'voltage' columns.
        stim_amp (float): Minimum amplitude for stimulation detection.
        verbose (bool): If True, print debugging information.
        plot (bool): If True, generate a plot with marked features.
        multiplot (bool): if True, use for plotting many plots compact without decorations
    Returns:
        dict: Characterization results with feature properties and indices.
    """
    voltage = df['voltage'].values
    times = df['time'].values
    dt = times[1] - times[0]  # Assumes uniform sampling
    
    # 1. Stimulation Pulse
    neg_peaks = []
    pos_peaks = []
    stim_prom = stim_amp
    while (len(pos_peaks) == 0 or len(neg_peaks) == 0) and stim_prom > 1e-6: # iterative stim search until at least 2 prominent peaks are found
        neg_peaks, neg_props = find_peaks(-voltage, prominence=stim_prom)
        pos_peaks, pos_props = find_peaks(voltage, prominence=stim_prom)
        stim_prom /= 2
    stim_detected = False
    stim_amplitude = 0
    i_stim_neg = None
    i_stim_pos = None
    verboses = f"function: characterize_graph_class_a\n"
    if neg_peaks.size > 0 and pos_peaks.size > 0:
        verboses += f"stim: found possible peaks.\n {neg_peaks}, {neg_props}, {pos_peaks}, {pos_props}\n"
        first_neg = neg_peaks[0]
        next_pos_candidates = pos_peaks[pos_peaks > first_neg]
        next_pos = next_pos_candidates[0] if next_pos_candidates.size > 0 else None
        if next_pos is not None:
            verboses += f"stim length: {(times[next_pos] - times[first_neg])}\n"
            if (times[next_pos] - times[first_neg]) < 0.0004:  # Within 0.4 ms               
                stim_amplitude = -voltage[first_neg]
                i_stim_neg = int(first_neg) - 1 # yes I hardcoded these 1 step adjustments. Hope it stays that way
                i_stim_pos = int(next_pos) + 1 # yes I hardcoded these 1 step adjustments. Hope it stays that way
                stim_detected = bool(stim_amplitude > stim_amp)
                verboses += f"{stim_detected=}\n"
    else:
        verboses += f"stim: did not find useful peaks.\n {neg_peaks}, {neg_props}, {pos_peaks}, {pos_props}\n"

    # Baseline: Mean voltage before stimulation (or first 10% of data)
    if stim_detected:
        baseline_end = i_stim_neg - 2
    else:
        baseline_end = int(0.1 * len(voltage))
    baseline = np.mean(voltage[:baseline_end])

    # 2. Volley (M-Shape)
    volley_detected = False
    m_shape = False
    volley_start = i_stim_neg + int(0.0005 / dt) if stim_detected else int(0.001 / dt)
    volley_end = min(volley_start + int(0.005 / dt), len(voltage))  # Clamp to array length
    volley_region = voltage[volley_start:volley_end]
    verboses += f"volley: search region {volley_start}, {volley_end}\n"
    v_prom = 0.001
    v_peaks = []
    while len(v_peaks) < 2 and v_prom > 1e-6: # iterative volley search until at least 2 prominent peaks are found
        v_peaks, v_peak_props = find_peaks(volley_region, prominence=v_prom)
        v_prom /= 2
    v_troughs, _ = find_peaks(-volley_region, prominence=v_prom) # using same v_prom for peak and trough. seems to work but could change
    i_volley_peaks = [p + volley_start for p in v_peaks if p + volley_start < len(voltage)]
    i_volley_troughs = [t + volley_start for t in v_troughs if t + volley_start < len(voltage)]
    if len(v_peaks) >= 2 and len(v_troughs) >= 1:
        volley_detected = True
        for i in range(len(v_peaks) - 1):
            p1, p2 = v_peaks[len(v_peaks) - 2 - i], v_peaks[len(v_peaks) - 1 - i]
            troughs_between = [t for t in v_troughs if p1 < t < p2]
            if troughs_between and volley_region[p2] <= volley_region[p1]:
                m_shape = True
                i_veb = p2 + volley_start
                i_volley_peaks = [p1 + volley_start, p2 + volley_start]
                i_volley_trough = troughs_between[0] + volley_start
                #TODO: speak with Mats, maybe select trough in the middle of the peaks here?
                break

    # 3. EPSP
    epsp_detected = False
    epsp_depth = 0
    i_epsp_min = None
    epsp_start = i_veb if volley_detected else i_stim_pos + 2
    epsp_end = min(epsp_start + int(0.02 / dt), len(voltage)-1)  # Clamp to array length
    verboses += f"epsp region: {epsp_start}:{epsp_end}, times={times[epsp_start]}:{times[epsp_end]}\n"
    epsp_region = voltage[epsp_start:epsp_end] #TODO: could be useful to savgol this for robustness
    if len(epsp_region) > 0:
        i_epsp_min_rel = np.argmin(epsp_region)
        e_prom = 0.01
        e_peaks = []
        while len(e_peaks) < 1 and e_prom > 1e-6: # iterative epsp search
            e_peaks, e_peak_props = find_peaks( - epsp_region, prominence=e_prom)
            e_prom /= 2
        if len(e_peaks):
            i_epsp_min = e_peaks[0] + epsp_start # just choosing the leftmost now. with normal curves that should be it, unless noise is very bad
            verboses += f"epsp min: {i_epsp_min=}, times={times[i_epsp_min]}\n"
            if i_epsp_min < len(voltage):
                epsp_depth = baseline - voltage[i_epsp_min]
                epsp_detected = bool(epsp_depth > 0.0001)
        else:
            verboses += f"epsp min: no peak found\n"

    # 4. Noise Level
    chatter_start = i_stim_pos + 3 if stim_detected else int(0.05 * len(voltage))
    chatter_end = min(int(0.2 * len(voltage)), len(voltage))
    chatter_region = voltage[chatter_start:chatter_end]
    noise_level = np.std(chatter_region) if len(chatter_region) > 0 else 0

    # 5. Volley Slope (steepest 3-point interval between left volley peak and volley trough, limit search to first half and see what happens)
    i_volley_slope_start = None
    i_volley_slope_end = None
    volley_slope_value = None
    if m_shape and 'i_volley_trough' in locals():
        left_peak = i_volley_peaks[0]
        trough = i_volley_trough
        if trough - left_peak >= 2:
            slopes = []
            win_length = min((trough + 1 - left_peak) // 2, 3) # set savgol window length
            pad = 3
            voltage_slope = savgol_filter(voltage[left_peak: trough + pad], window_length=win_length, polyorder=0)
            times_slope = times[left_peak: trough + pad]
            for i in range(len(voltage_slope) - pad): # first half
                x = times_slope[i:i+3]
                y = voltage_slope[i:i+3]
                model = LinearRegression()
                model.fit(x.reshape(-1, 1), y.reshape(-1, 1))
                #coeffs = model.coef_
                coeffs = np.polyfit(x, y, 1)
                slopes.append((i, coeffs[0]))
            if slopes:
                min_slope_i, volley_slope_value = min(slopes, key=lambda x: x[1])
                i_volley_slope_start = min_slope_i + left_peak
                i_volley_slope_end = min_slope_i + 2 + left_peak
                verboses += f"volley slope: start={times[i_volley_slope_start]}, end={times[i_volley_slope_end]}, slope={volley_slope_value}\n"
            else:
                verboses += "volley slope: not found\n"
        else:
            verboses += "volley slope: region too small\n"

    # 6. EPSP Slope (straightest 7-point interval between right volley peak and EPSP min)
    i_epsp_slope_start = None
    i_epsp_slope_end = None
    epsp_slope_value = None
    if epsp_detected and len(i_volley_peaks) >= 2 and i_epsp_min is not None:
        right_peak = i_volley_peaks[1]
        epsp_min = i_epsp_min
        if epsp_min - right_peak >= 6:
            r2_values = []
            win_length = min((epsp_min + 1 - right_peak) // 2, 6) # set savgol window length
            pad = 7
            voltage_slope = savgol_filter(voltage[right_peak: epsp_min + pad], window_length=win_length, polyorder=1)
            times_slope = times[right_peak: epsp_min + pad]
            for i in range((len(voltage_slope) - pad)//4): # first fourth for slope start
                x = times_slope[i:i+7]
                y = voltage_slope[i:i+7]
                model = LinearRegression()
                model.fit(x.reshape(-1, 1), y.reshape(-1, 1))
                coeffs = model.coef_
                coeffs = np.polyfit(x, y, 1)
                y_pred = np.polyval(coeffs, x)
                ss_res = np.sum((y - y_pred)**2)
                ss_tot = np.sum((y - np.mean(y))**2)
                r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
                r2_values.append((i, r2, coeffs[0]))
            if r2_values:
                max_r2_i, max_r2, epsp_slope_value = max(r2_values, key=lambda x: x[1])
                i_epsp_slope_start = max_r2_i + right_peak
                i_epsp_slope_end = max_r2_i + 6 + right_peak
                verboses += f"epsp slope: start={times[i_epsp_slope_start]}, end={times[i_epsp_slope_end]}, slope={epsp_slope_value}\n"
            else:
                verboses += "epsp slope: not found\n"
        else:
            verboses += "epsp slope: region too small\n"

    if verbose:
        print(verboses)

    # Characterization results
    result = {
        'stimulation_detected': stim_detected,
        'stim_amplitude': stim_amplitude,
        'i_stim_neg': i_stim_neg,
        'i_stim_pos': i_stim_pos,
        'volley_detected': volley_detected,
        'm_shape_confirmed': m_shape,
        'volley_region': (volley_start, volley_end),
        'i_volley_peaks': i_volley_peaks,
        'i_volley_trough': i_volley_trough if 'i_volley_trough' in locals() else None,
        'epsp_detected': epsp_detected,
        'epsp_depth': epsp_depth,
        'epsp_region': (epsp_start, epsp_end),
        'i_epsp_min': i_epsp_min,
        'noise_level': noise_level,
        'chatter_region': (chatter_start, chatter_end),
        'baseline_region': (0, baseline_end),
        'standard_structure': stim_detected and volley_detected and m_shape and epsp_detected,
        'i_volley_slope_start': i_volley_slope_start,
        't_volley_slope_start': times[i_volley_slope_start],
        'i_volley_slope_end': i_volley_slope_end,
        'volley_slope_value': volley_slope_value,
        'i_epsp_slope_start': i_epsp_slope_start,
        't_EPSP_slope_start': times[i_epsp_slope_start],
        'i_epsp_slope_end': i_epsp_slope_end,
        'epsp_slope_value': epsp_slope_value
    }

    # Plotting if requested
    if plot:            
        plt.figure(figsize=(12, 9) if not multiplots else (6, 1))
        plt.plot(times, voltage, label='Voltage', color='black')
        
        # Plot baseline
        plt.axhline(y=baseline, color='gray', linestyle='--', label='Baseline')
        
        # Volley region and features
        if volley_start < len(times) and volley_end <= len(times):
            t_volley_start = times[volley_start]
            t_volley_end = times[min(volley_end - 1, len(times) - 1)]
            plt.axvspan(t_volley_start, t_volley_end, color='yellow', alpha=0.2, label='Volley Region')
            for i in i_volley_peaks:
                if i < len(times):
                    plt.plot(times[i], voltage[i], 'go', label='Volley Peak' if 'Volley Peak' not in plt.gca().get_legend_handles_labels()[1] else "")
            i = i_volley_trough if 'i_volley_trough' in locals() else None
            if i is not None and i < len(times):
                plt.plot(times[i], voltage[i], 'mo', label='Volley Trough' if 'Volley Trough' not in plt.gca().get_legend_handles_labels()[1] else "")
        
        # EPSP region and minimum
        if epsp_start is not None and epsp_end is not None and epsp_start < len(times) and epsp_end <= len(times):
            t_epsp_start = times[epsp_start]
            t_epsp_end = times[min(epsp_end - 1, len(times) - 1)]
            plt.axvspan(t_epsp_start, t_epsp_end, color='cyan', alpha=0.2, label='EPSP Region')
            if i_epsp_min is not None and i_epsp_min < len(times):
                plt.plot(times[i_epsp_min], voltage[i_epsp_min], 'ko', label='EPSP Min')
        
        # Chatter region
        if chatter_start < len(times) and chatter_end <= len(times):
            t_chatter_start = times[chatter_start]
            t_chatter_end = times[min(chatter_end - 1, len(times) - 1)]
            plt.axvspan(t_chatter_start, t_chatter_end, color='orange', alpha=0.2, label='Chatter Region')
        
        # Mark stimulation baseline crossings
        if stim_detected:
            plt.plot(times[i_stim_neg], baseline, 'ro', label='Stim peaks time')
            plt.plot(times[i_stim_pos], baseline, 'ro')
        
        # Plot volley slope
        if i_volley_slope_start is not None and i_volley_slope_end is not None:
            plt.plot(times[i_volley_slope_start:i_volley_slope_end+1], voltage[i_volley_slope_start:i_volley_slope_end+1], 'r-', linewidth=2, label='Volley Slope')
        
        # Plot EPSP slope
        if i_epsp_slope_start is not None and i_epsp_slope_end is not None:
            plt.plot(times[i_epsp_slope_start:i_epsp_slope_end+1], voltage[i_epsp_slope_start:i_epsp_slope_end+1], 'r-', linewidth=2, label='EPSP Slope')
        
        # Calculate y-axis limits based on features
        if volley_detected:
            volley_min = voltage[volley_start:volley_end].min()
            volley_max = voltage[volley_start:volley_end].max()
        else:
            volley_min = baseline
            volley_max = baseline
        
        if epsp_detected:
            epsp_min = voltage[epsp_start:epsp_end].min()
            epsp_max = voltage[epsp_start:epsp_end].max()
        else:
            epsp_min = baseline
            epsp_max = baseline
        
        feature_min = min(volley_min, epsp_min)
        feature_max = max(volley_max, epsp_max)
        
        # Add padding and ensure baseline is included
        padding = 0.1 * (feature_max - feature_min) if feature_max != feature_min else 0.001
        y_min = min(feature_min - padding, baseline - padding)
        y_max = max(feature_max + padding, baseline + padding)
        plt.ylim(y_min, y_max)
        
        if not multiplots:
            plt.xlabel('Time (s)')
            plt.ylabel('Voltage')
            plt.title('Graph Characterization Features')
            plt.legend()
            plt.grid(True)
        plt.show()
        
    return result

if __name__ == "__main__":
    import parse
    import ui_state_classes as ui

    # Test find_events:  with a sample DataFrame
    list_sources = [r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_a.csv",
                    r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_b.csv",
                    #r"C:\Users\xandmz\Documents\data\A_24_P0630-D4_Ch0_a.csv",
                    #r"C:\Users\xandmz\Documents\data\A_24_P0630-D4_Ch0_b.csv",
                    #r"C:\Users\xandmz\Documents\data\B_22_P0701-D3_Ch0_a.csv",
                    #r"C:\Users\xandmz\Documents\data\B_22_P0701-D3_Ch0_b.csv",
                    #r"C:\Users\xandmz\Documents\data\B_23_P0630-D3_Ch0_a.csv",
                    #r"C:\Users\xandmz\Documents\data\B_23_P0630-D3_Ch0_b.csv",
                    
                    #r"K:\Samples - pilot\cA24.csv",  # Works with ui.py
                    #r"K:\Samples - pilot\cB22.csv", # Doesn't Work with ui.py
    ]
    t_volley_slope_width = 0.0003 # default width for volley slope, in seconds
    t_EPSP_slope_width = 0.0007 # default width for EPSP, in seconds
    t_volley_slope_halfwidth = 0.0001
    t_EPSP_slope_halfwidth = 0.0003
    default_dict_t = { # default values for df_t(imepoints)
            'stim': 0,
            't_stim': 0,
            't_stim_method': 'max prim',
            't_stim_params': 'NA',
            'amp_zero': 0,
            't_volley_slope_width': t_volley_slope_width,
            't_volley_slope_halfwidth': t_volley_slope_halfwidth,
            't_volley_slope_start': 0,
            't_volley_slope_end': 0,
            't_volley_slope_method': 'default',
            't_volley_slope_params': 'NA',
            'volley_slope_mean': 0,
            't_volley_amp': 0,
            't_volley_amp_method': 'default',
            't_volley_amp_params': 'NA',
            'volley_amp_mean': 0,
            't_EPSP_slope_width': t_EPSP_slope_width,
            't_EPSP_slope_halfwidth': t_EPSP_slope_halfwidth,
            't_EPSP_slope_start': 0,
            't_EPSP_slope_end': 0,
            't_EPSP_slope_method': 'default',
            't_EPSP_slope_params': 'NA',
            't_EPSP_amp': 0,
            't_EPSP_amp_method': 'default',
            't_EPSP_amp_params': 'NA',
            'norm_output_from': 0,
            'norm_output_to': 0,
        }
    for _ in range(3):
        print()
    print("", "*** analysis_v2.py standalone test: ***")
    # Assumes single stim for now
    list_event_summary = []
    for source in list_sources:
        for _ in range(2):
            print()
        t0 = time.time()
        df = pd.read_csv(source)
        print(f"Loaded {source} with shape {df.shape}")
        dfmean, i_stim = parse.build_dfmean(df)
        print(f"DataFrame mean shape: {dfmean.shape}, i_stim: {i_stim}")
        dict_events = find_events(dfmean, default_dict_t, verbose=True)
        dict_t = default_dict_t.copy()  # Create a copy of the default dictionary
        if dict_events.shape[0] == 1:
            dict_t.update(dict_events.iloc[0].to_dict()) # find_events returns a DataFrame
        else:
            raise ValueError("Expected exactly one event in find_events result.")
        df_t = pd.DataFrame([dict_t])
        print()
        print(f"*** dict_t: {dict_t}")
        # print time rounded to 3 decimal places
        print(f"Time taken: {round(time.time() - t0, 3)} seconds")
        print()
        list_event_summary.append({
            'source': source,
            't_stim': df_t['t_stim'].values[0],
            't_volley_slope_start': df_t['t_volley_slope_start'].values[0],
            't_volley_slope_end': df_t['t_volley_slope_end'].values[0],
            't_volley_slope_method': df_t['t_volley_slope_method'].values[0],
            't_EPSP_slope_start': df_t['t_EPSP_slope_start'].values[0],
            't_EPSP_slope_end': df_t['t_EPSP_slope_end'].values[0],
            't_EPSP_slope_method': df_t['t_EPSP_slope_method'].values[0],
            't_volley_amp': df_t['t_volley_amp'].values[0],
            't_EPSP_amp': df_t['t_EPSP_amp'].values[0],
        })
    print("Event Summary:")
    for event in list_event_summary:
        print(f"t_stim: {event['t_stim']}, vS:{event['t_volley_slope_method']}, ES: {event['t_EPSP_slope_method']}, "
              f"t_volley_slope: {event['t_volley_slope_start']} - {event['t_volley_slope_end']}, t_volley_amp: {event['t_volley_amp']}, "
              f"t_EPSP_slope: {event['t_EPSP_slope_start']} - {event['t_EPSP_slope_end']}, t_EPSP_amp: {event['t_EPSP_amp']}")
              




'''
# Jupyter Notebook testers

# %%
if __name__ == "__main__":
    # read slices and meta
    folder_talkback = Path.home() / 'Documents' / 'Brainwash Data Source' / 'talkback KetaDexa'
    folder_talkback = Path.home() / 'Documents' / 'Brainwash Data Source' / 'talkback Lactate24SR'
    slice_filepaths = sorted(list(folder_talkback.glob('*slice*')))
    meta_filepaths = sorted(list(folder_talkback.glob('*meta*')))

    def load_meta(path, sweep=1):
        with open(path) as file:
            df =  pd.DataFrame(json.load(file), index=[sweep])
        df['sweepname'] = str(path.name).split('.')[0].split('_')[-2]
        return df

    meta = pd.concat([load_meta(meta_filepath, sweep) for sweep, meta_filepath in enumerate(meta_filepaths)])

    def load_slice(path, sweep=1):
        df = pd.read_csv(str(path))
        #df.set_index('time', inplace=True, drop=True)
        df['sweep'] = sweep
        df['sweepname'] = str(path.name).split('.')[0].split('_')[-2]
        rollingwidth=3
        df['prim'] = df.voltage.rolling(rollingwidth, center=True).mean().diff()
        df['bis'] = df.prim.rolling(rollingwidth, center=True).mean().diff()
        return df
    
    df = pd.concat([load_slice(slice_filepath, sweep) for sweep, slice_filepath in enumerate(slice_filepaths)])


# %%
if __name__ == "__main__":
    sweepname = df.sweepname.unique()[0]
    sweepname = 'd1fdaa03-6a4a-4e32-9691-ad4ef09a1e1c'
    dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage']]
    characterize_graph(dfsweep, stim_amp=0.005, verbose=True, plot=True)

# %%
# calculate and report test set
if __name__ == "__main__":
    from analysis_evaluation import evaluate_and_report

    def check_sweep(sweepname):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis']]
        result = characterize_graph(dfsweep, stim_amp=0.005, verbose=False, plot=False)
        result.update({'sweepname': sweepname})
        return result
    
    results = []
    signals = []
    for sweepname in df.sweepname.unique():
        result = check_sweep(sweepname)
        results.append(result)
        signal = df[df['sweepname'] == sweepname][['time', 'voltage']].copy()
        signals.append(signal)
    dfresults_av2 = pd.DataFrame(results)
    dfresults_av2 = dfresults_av2[[col for col in dfresults_av2 if col.startswith('t_')] + ["sweepname"]]
    dfresults_av2.columns = ["analytic_v2-" + col if col.startswith('t_') else col for col in dfresults_av2.columns]
    dfresults_av2
  
    
    evaluate_and_report(dfresults_av2, meta, signals, offset_thresholds=[1, 2, 3, 5, 10])

# %%
# find worst offenders
if __name__ == "__main__":
    def check_sweep(sweepname):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis']]
        result = characterize_graph(dfsweep, stim_amp=0.005, verbose=False, plot=False, multiplots=True)
        result.update({'sweepname': sweepname})
        return result
    
    results = []
    signals = []
    for sweepname in df.sweepname.unique():
        result = check_sweep(sweepname)
        results.append(result)
        signal = df[df['sweepname'] == sweepname][['time', 'voltage']].copy()
        signals.append(signal)
    dfresults = pd.DataFrame(results)
    dfresults = dfresults[[col for col in dfresults if col.startswith('t_')] + ['sweepname']]
    dfdiff = dfresults - meta[['t_EPSP_slope_start', 't_volley_slope_start']]
    dfdiff['sweepname'] = dfresults.sweepname
    worst_list = dfdiff.loc[dfdiff.t_EPSP_slope_start.abs().nlargest(5).index].sweepname.values.tolist()
    display(dfdiff.loc[dfdiff.t_EPSP_slope_start.abs().nlargest(5).index])    

# %%
# plot worst offenders
if __name__ == "__main__":
    results = []
    for sweepname in worst_list:
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage']]
        result = characterize_graph(dfsweep, stim_amp=0.005, verbose=False, plot=True, multiplots=True) # multiplot=False for big plots
        result.update({'sweepname': sweepname})
        results.append(result)
    dfresults = pd.DataFrame(results)
    #dfresults
'''