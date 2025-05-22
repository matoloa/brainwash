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
import os
import json
import sys
import pandas as pd
from pathlib import Path
import seaborn as sns
import numpy as np
from scipy.signal import savgol_filter, find_peaks
from scipy import stats
from lightgbm import LGBMRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

# Import original analytical module
reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))
import analysis

# --- Refined Analytical Module ---
def valid(num):
    return num is not None and not np.isnan(num)

def regression_line(x_data, y_data):
    slope, intercept, r_value, p_value, std_err = stats.linregress(x_data, y_data)
    x = np.linspace(x_data.min(), x_data.max(), 100)
    y = slope * x + intercept
    return {'x': x, 'y': y, 'r_value': r_value, 'p_value': p_value, 'std_err': std_err}

def addFilterSavgol(df, window_length=9, poly_order=3):
    df['savgol'] = savgol_filter(df.voltage, window_length, poly_order)
    if df['savgol'].std() < 0.5 * df['voltage'].std():
        print("Warning: Savitzky-Golay may be over-smoothing signal.")
    return df['savgol']

def find_i_stims(dfmean, threshold=0.1, min_time_difference=0.005):
    prim_max = np.argmax(dfmean['prim'].values)
    prim_max_y = dfmean['prim'].max()
    threshold *= prim_max_y
    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    filtered_indices = []
    if len(above_threshold_indices) == 0:
        print(f"No stimulus peaks found above threshold {threshold} (prim_max_y={prim_max_y})")
        return []
    max_index = above_threshold_indices[0]
    for i in range(1, len(above_threshold_indices)):
        current_index = above_threshold_indices[i]
        previous_index = above_threshold_indices[i - 1]
        if dfmean['time'].values[current_index] - dfmean['time'].values[previous_index] > min_time_difference:
            filtered_indices.append(max_index)
            max_index = current_index
        elif dfmean['prim'].values[current_index] > dfmean['prim'].values[max_index]:
            max_index = current_index
    filtered_indices.append(max_index)
    # Log detected i_stims and prim values
    for i_stim in filtered_indices:
        prim_value = dfmean['prim'].iloc[i_stim]
        time_value = dfmean['time'].iloc[i_stim]
        if i_stim < 20 or 25 < i_stim:
            print(f"Detected i_stim={i_stim}, time={time_value:.6f}s, prim={prim_value:.6f}")
    return filtered_indices

def find_i_EPSP_peak_max(
    dfmean, sampling_Hz=10000, limitleft=0, limitright=-1,
    param_EPSP_minimum_width_ms=4, param_EPSP_minimum_prominence_mV=0.0001
):
    EPSP_minimum_width_i = int(param_EPSP_minimum_width_ms * 0.001 * sampling_Hz)
    limitright = limitleft + 200 if limitright == -1 else limitright  # Hardcoded
    dfmean_sliced = dfmean[(limitleft <= dfmean.index) & (dfmean.index <= limitright)]
    i_peaks, properties = find_peaks(
        -dfmean_sliced['voltage'],
        width=EPSP_minimum_width_i,
        prominence=param_EPSP_minimum_prominence_mV / 1000
    )
    return i_peaks[properties['prominences'].argmax()] + limitleft if len(i_peaks) > 0 else np.nan

def find_i_VEB_prim_peak_max(
    dfmean, i_stim, i_EPSP, param_minimum_width_of_EPSP=5,
    param_minimum_width_of_VEB=1, param_prim_prominence=0.0001
):
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    minimum_acceptable_i_for_VEB = int(i_stim + 0.001 * sampling_Hz)
    max_acceptable_i_for_VEB = int(
        i_EPSP - np.floor((param_minimum_width_of_EPSP * 0.001 * sampling_Hz) / 2)
    ) if not np.isnan(i_EPSP) else int(i_stim + 0.01 * sampling_Hz)  # Hardcoded fallback
    prim_sample = dfmean['prim'].values[minimum_acceptable_i_for_VEB:max_acceptable_i_for_VEB]
    i_peaks, properties = find_peaks(
        prim_sample,
        width=param_minimum_width_of_VEB * 1000 / sampling_Hz,
        prominence=param_prim_prominence / 1000
    )
    i_peaks += minimum_acceptable_i_for_VEB
    if len(i_peaks) == 0:
        return np.nan, 0
    i_VEB = i_peaks[properties['prominences'].argmax()]
    veb_prominence = properties['prominences'][i_peaks.argmax()]
    return i_VEB, veb_prominence


def find_i_EPSP_slope_bis0(dfmean, i_VEB, i_EPSP, i_stim, happy=True, sampling_Hz=10000):
    if pd.isna(i_VEB) or pd.isna(i_EPSP):
        i_VEB = i_stim + int(0.002 * sampling_Hz)  # Hardcoded 2ms
        i_EPSP = i_stim + int(0.01 * sampling_Hz)  # Hardcoded 10ms
    i_VEB = int(i_VEB)
    i_EPSP = int(i_EPSP)
    if i_VEB >= i_EPSP:
        return np.nan, None
    dftemp = dfmean.bis[i_VEB:i_EPSP]
    i_EPSP_slope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if len(i_EPSP_slope) == 0:
        return i_VEB + int(0.001 * sampling_Hz), None  # Hardcoded 1ms
    first_zero_crossing = i_EPSP_slope[0] if happy else i_EPSP_slope[0]
    return first_zero_crossing, dfmean['time'].iloc[first_zero_crossing]


    


# Previous imports and unchanged functions remain here
# Showing modified function

# --- Updated find_i_volley_slope with Adjusted Window and Prominence Selection ---
def find_i_volley_slope(dfmean, i_stim, i_VEB, i_EPSP_slope=None, sweepname=None, debug_sweeps=None, happy=True):
    global debug_counter
    if 'debug_counter' not in globals():
        debug_counter = 0
    
    if pd.isna(i_stim) or pd.isna(i_VEB):
        sampling_Hz = 1 / (dfmean.time[1] - dfmean.time[0])
        return int(i_stim + 0.00157 * sampling_Hz)  # Fallback: 1.57ms post-stimulus (mean true value)
    sampling_Hz = 1 / (dfmean.time[1] - dfmean.time[0])
    start_i = max(0, int(i_stim + 0.0015 * sampling_Hz))  # 1.5ms after i_stim to avoid stim pulse
    end_i = min(len(dfmean) - 1, int(i_stim + 0.0035 * sampling_Hz))  # End 3.5ms post-stimulus
    if start_i >= end_i:  # Ensure valid range
        if pd.notna(i_EPSP_slope):
            return int(i_EPSP_slope - 0.0003 * sampling_Hz)  # Fallback: 0.3ms before EPSP slope
        return int(i_stim + 0.00157 * sampling_Hz)  # Fallback: 1.57ms post-stimulus
    dftemp = dfmean.loc[start_i:end_i, ['time', 'voltage']].copy()
    
    # Recompute prim as raw derivative in the window
    dftemp['prim'] = dftemp['voltage'].diff() * sampling_Hz  # Convert to mV/s (diff is per 0.0001s)
    dftemp['prim'] = dftemp['prim'].fillna(0)  # Handle NaNs
    
    # Debug: Limit output to the 5 worst sweeps
    should_debug = debug_sweeps is not None and sweepname in debug_sweeps and debug_counter < 5
    if should_debug:
        print(f"Debug: Window {start_i}:{end_i} (time {dftemp['time'].iloc[0]:.6f}-{dftemp['time'].iloc[-1]:.6f})")
        print(f"Debug: Voltage values: {dftemp['voltage'].values}")
        print(f"Debug: Prim values: {dftemp['prim'].values}")
        prim_variance = dftemp['prim'].var()
        voltage_std = dftemp['voltage'].std()
        print(f"Debug: prim variance={prim_variance:.6f}, voltage std={voltage_std:.6f}")
        debug_counter += 1
    
    # Dynamic search window using rolling sum of prim (window size 7)
    window_size = 7  # 0.0007s at 10kHz, wider than expected volley slope (~0.0003s)
    rolling_sum = dftemp['prim'].rolling(window_size, center=True).sum()
    rolling_sum = rolling_sum.fillna(0)  # Handle NaNs at edges
    
    # Find significant minima in rolling sum (indicating sustained downward slopes)
    prim_range = dftemp['prim'].max() - dftemp['prim'].min()
    prominence = 0.005 * prim_range if prim_range > 0 else 0.000005 / 1000  # 0.5% of prim range
    i_peaks, properties = find_peaks(-rolling_sum, prominence=prominence)
    
    # Fine search for volley slope starting from first significant minimum
    i_min = None
    if len(i_peaks) > 0:
        # Start fine search from the first significant minimum
        for peak in i_peaks:
            idx = peak + start_i
            # Ensure we can check three consecutive prim values
            if idx + 2 < len(dfmean):
                # Check for three consecutive negative prim values
                prim_vals = dfmean['prim'].iloc[idx:idx+3].values
                if all(val < 0 for val in prim_vals):
                    i_min = idx
                    break
        if should_debug:
            print(f"Debug: Detected minima in rolling sum at indices {i_peaks + start_i}, prominences {properties['prominences']}")
    
    # If no valid minimum found, fall back to mean true volley slope timing
    if i_min is None:
        i_min = int(i_stim + 0.00157 * sampling_Hz)  # 1.57ms post-stimulus
        if should_debug:
            print(f"Debug: No minima with three consecutive negative prim values found, falling back to i_stim + 1.57ms: index {i_min}, time {dfmean['time'].iloc[i_min]:.6f}")
    else:
        if should_debug:
            print(f"Debug: Selected volley slope at index {i_min}, time {dfmean['time'].iloc[i_min]:.6f}")
            print(f"Debug: Prim values at selected index {i_min} and next two: {dfmean['prim'].iloc[i_min:i_min+3].values}")
    
    return i_min
    

def find_all_i(dfmean, i_stims=None, param_min_time_from_i_stim=0.0005, sweepname=None, debug_sweeps=None):
    if i_stims is None:
        i_stims = find_i_stims(dfmean)
    if not i_stims:
        return pd.DataFrame()
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    list_dict_i = []
    for i in i_stims:
        dict_i = {
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
            "t_EPSP_slope_params": "-"
        }
        # Parallel detection
        dict_i['i_EPSP_amp'] = find_i_EPSP_peak_max(dfmean, sampling_Hz, limitleft=i)
        dict_i['i_VEB'], _ = find_i_VEB_prim_peak_max(dfmean, i_stim=i, i_EPSP=dict_i['i_EPSP_amp'])
        dict_i['i_EPSP_slope'], _ = find_i_EPSP_slope_bis0(dfmean, dict_i['i_VEB'], dict_i['i_EPSP_amp'], i, happy=True, sampling_Hz=sampling_Hz)
        dict_i['i_volley_slope'] = find_i_volley_slope(dfmean, i_stim=i, i_VEB=dict_i['i_VEB'], i_EPSP_slope=dict_i['i_EPSP_slope'], sweepname=sweepname, debug_sweeps=debug_sweeps, happy=True)
        
        # Validate i_volley_slope < i_VEB before slicing
        if not pd.isna(dict_i['i_volley_slope']) and not pd.isna(dict_i['i_VEB']):
            if dict_i['i_volley_slope'] > dict_i['i_VEB']:
                dict_i['i_volley_slope'] = int(dict_i['i_VEB'] - 0.001 * sampling_Hz)  # 1ms before i_VEB
            slice_df = dfmean.loc[dict_i['i_volley_slope']:dict_i['i_VEB'], 'voltage']
            dict_i['i_volley_amp'] = slice_df.idxmin() if not slice_df.empty else int(i + 0.001 * sampling_Hz)  # Adaptive fallback
        else:
            dict_i['i_volley_amp'] = int(i + 0.001 * sampling_Hz)  # Adaptive fallback
        
        list_dict_i.append(dict_i)
    df_i = pd.DataFrame(list_dict_i)
    df_i_numeric = df_i.select_dtypes(include=[np.number])
    list_nan = [i for i in range(len(df_i_numeric)) if df_i_numeric.iloc[i].isnull().any()]
    if list_nan:
        methods = ['t_volley_amp_method', 't_volley_slope_method', 't_EPSP_amp_method', 't_EPSP_slope_method']
        params = ['t_volley_amp_params', 't_volley_slope_params', 't_EPSP_amp_params', 't_EPSP_slope_params']
        for i in range(len(df_i_numeric)):
            if not df_i_numeric.iloc[i].isnull().any():
                i_values = df_i_numeric.iloc[i]
                i_template = {key: i_values[key] - i_stims[i] for key in i_values.keys()}
                for j in list_nan:
                    for key in df_i_numeric.columns:
                        df_i.loc[j, key] = i_stims[j] + i_template[key]
                    for key in methods:
                        df_i.loc[j, key] = "Extrapolated"
                    for key in params:
                        df_i.loc[j, key] = f"stim {i+1}"
                break
        else:
            for index, row in df_i.iterrows():
                if row.isnull().any():
                    stim = row['i_stim']
                    dict_default = {
                        "i_stim": stim,
                        "i_VEB": stim + int(0.002 * sampling_Hz),
                        "i_EPSP_amp": stim + int(0.005 * sampling_Hz),
                        "i_EPSP_slope": stim + int(0.002 * sampling_Hz),
                        "i_volley_amp": stim + int(0.0015 * sampling_Hz),
                        "i_volley_slope": stim + int(0.001 * sampling_Hz),
                        "t_volley_amp_method": "Default",
                        "t_volley_slope_method": "Default",
                        "t_EPSP_amp_method": "Default",
                        "t_EPSP_slope_method": "Default",
                        "t_volley_amp_params": "-",
                        "t_volley_slope_params": "-",
                        "t_EPSP_amp_params": "-",
                        "t_EPSP_slope_params": "-"
                    }
                    df_i.loc[index] = dict_default
    return df_i



def find_all_t(dfmean, default_dict_t, precision=None, param_min_time_from_i_stim=0.0005):
    def i2t(index, dfmean, row, precision, default_dict_t):
        time_values = dfmean['time'].values
        if precision is None:
            precision = len(str(time_values[1] - time_values[0]).split('.')[1])
        sampling_Hz = 1 / (time_values[1] - time_values[0])
        
        # Volley slope start: Find where prim becomes significantly negative
        t_volley_slope = dfmean.loc[row['i_volley_slope']].time if 'i_volley_slope' in row and row['i_volley_slope'] in dfmean.index else None
        if t_volley_slope is not None:
            window_i = int(0.0002 * sampling_Hz)  # 0.2ms window around i_volley_slope
            start_i = max(0, int(row['i_volley_slope'] - window_i))
            end_i = min(len(dfmean) - 1, int(row['i_volley_slope'] + window_i))
            dftemp = dfmean.loc[start_i:end_i, ['time', 'prim']]
            # Find where prim becomes significantly negative (threshold: 5% of min prim)
            prim_threshold = 0.05 * dftemp['prim'].min() if dftemp['prim'].min() < 0 else -0.00005 / 1000
            neg_prim = dftemp[dftemp['prim'] < prim_threshold]
            t_volley_slope_start = neg_prim['time'].iloc[0] if not neg_prim.empty else t_volley_slope - default_dict_t['t_volley_slope_halfwidth']
            t_volley_slope_end = t_volley_slope + default_dict_t['t_volley_slope_halfwidth']
        else:
            t_volley_slope_start = None
            t_volley_slope_end = None
        
        # Other features (unchanged)
        t_EPSP_slope = dfmean.loc[row['i_EPSP_slope']].time if 'i_EPSP_slope' in row and row['i_EPSP_slope'] in dfmean.index else None
        t_EPSP_amp = dfmean.loc[row['i_EPSP_amp']].time if 'i_EPSP_amp' in row and row['i_EPSP_amp'] in dfmean.index else None
        t_volley_amp = dfmean.loc[row['i_volley_amp']].time if 'i_volley_amp' in row and row['i_volley_amp'] in dfmean.index else None
        amp_zero_idx_start = row['i_stim'] - int(0.002 * sampling_Hz)  # 2ms before i_stim
        amp_zero_idx_end = row['i_stim'] - int(0.001 * sampling_Hz)  # 1ms before i_stim
        amp_zero = dfmean.loc[amp_zero_idx_start:amp_zero_idx_end].voltage.mean()
        return {
            'stim': index+1,
            'amp_zero': amp_zero,
            't_stim': round(dfmean.loc[row['i_stim']].time, precision),
            't_volley_slope_start': round(t_volley_slope_start, precision) if t_volley_slope_start is not None else None,
            't_volley_slope_end': round(t_volley_slope_end, precision) if t_volley_slope_end is not None else None,
            't_EPSP_slope_start': round(t_EPSP_slope - default_dict_t['t_EPSP_slope_halfwidth'], precision) if t_EPSP_slope is not None else None,
            't_EPSP_slope_end': round(t_EPSP_slope + default_dict_t['t_EPSP_slope_halfwidth'], precision) if t_EPSP_slope is not None else None,
            't_EPSP_amp': round(t_EPSP_amp, precision) if t_EPSP_amp is not None else None,
            't_volley_amp': round(t_volley_amp, precision) if t_volley_amp is not None else None
        }

    df_indices = find_all_i(dfmean, param_min_time_from_i_stim=0.0005)
    list_of_dict_t = []
    for index, row in df_indices.iterrows():
        result = i2t(index, dfmean, row, precision, default_dict_t)
        dict_t = default_dict_t.copy()
        dict_t.update(result)
        list_of_dict_t.append(dict_t)
    df_t = pd.DataFrame(list_of_dict_t)
    list_t_columns_in_df_indices = [col for col in df_indices.columns if col.startswith('t_')]
    for col in list_t_columns_in_df_indices:
        df_t[col] = df_indices[col]
    return df_t
    

# --- Refined ML Hybrid Module ---
def load_slice(path, sweep=1):
    df = pd.read_csv(str(path))
    df['sweep'] = sweep
    df['sweepname'] = str(path.name).split('.')[0].split('_')[-2]
    rollingwidth = 3
    df['prim'] = df.voltage.rolling(rollingwidth, center=True).mean().diff()
    df['bis'] = df.prim.rolling(rollingwidth, center=True).mean().diff()
    return df

def load_meta(path, sweep=1):
    with open(path) as file:
        df = pd.DataFrame(json.load(file), index=[sweep])
    df['sweepname'] = str(path.name).split('.')[0].split('_')[-2]
    return df

def compute_slope(df, start_time, num_points, time_step=0.0001):
    end_time = start_time + (num_points - 1) * time_step
    df_interval = df[(df['time'] >= start_time) & (df['time'] <= end_time)]
    if len(df_interval) < 2:
        return 0
    X = df_interval['time'].values.reshape(-1, 1)
    y = df_interval['voltage'].values
    reg = LinearRegression().fit(X, y)
    return reg.coef_[0]

def compute_analytical_predictions(signal, time_scale_factor=1.0):
    time = signal['time'].values
    voltage = signal['voltage'].values
    window_length = min(11, len(voltage) // 2 * 2 + 1)
    if window_length < 3:
        window_length = 3
    prim = savgol_filter(voltage, window_length, 2, deriv=1)
    bis = savgol_filter(voltage, window_length, 2, deriv=2)
    dfmean = pd.DataFrame({'time': time, 'voltage': voltage, 'prim': prim, 'bis': bis})
    df_i = find_all_i(dfmean, param_min_time_from_i_stim=0.0005)
    if df_i.empty:
        max_index = len(dfmean) - 1
        volley_start = dfmean['time'].iloc[max_index // 2]
        epsp_start = dfmean['time'].iloc[max_index // 2]
        return volley_start * time_scale_factor, epsp_start * time_scale_factor
    i_volley_slope = df_i['i_volley_slope'].iloc[0]
    i_EPSP_slope = df_i['i_EPSP_slope'].iloc[0]
    if pd.isna(i_volley_slope):
        i_volley_slope = df_i['i_stim'].iloc[0]
    if pd.isna(i_EPSP_slope):
        i_EPSP_slope = df_i['i_EPSP_amp'].iloc[0] if not pd.isna(df_i['i_EPSP_amp'].iloc[0]) else len(dfmean) - 1
    i_volley_slope = int(i_volley_slope)
    i_EPSP_slope = int(i_EPSP_slope)
    max_index = len(dfmean) - 1
    i_volley_slope = min(max(i_volley_slope, 0), max_index)
    i_EPSP_slope = min(max(i_EPSP_slope, 0), max_index)
    volley_start = dfmean['time'].iloc[i_volley_slope]
    epsp_start = dfmean['time'].iloc[i_EPSP_slope]
    return volley_start * time_scale_factor, epsp_start * time_scale_factor

def extract_features(signal, window_length=9, polyorder=2, time_scale_factor=10000):
    from scipy.fft import fft
    from scipy.stats import kurtosis, skew
    time = signal['time'].values
    voltage = signal['voltage'].values
    prim = savgol_filter(voltage, window_length, polyorder, deriv=1)
    bis = savgol_filter(voltage, window_length, polyorder, deriv=2)
    tris = savgol_filter(voltage, window_length, polyorder, deriv=3)
    voltage_norm = (voltage - voltage.mean()) / voltage.std() if voltage.std() > 0 else voltage
    dfmean = pd.DataFrame({'time': time, 'voltage': voltage, 'prim': prim, 'bis': bis, 'tris': tris})
    i_stim = find_i_stims(dfmean)[0] if find_i_stims(dfmean) else 0
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    i_EPSP_peak = find_i_EPSP_peak_max(dfmean, limitleft=i_stim)
    i_VEB, veb_prominence = find_i_VEB_prim_peak_max(dfmean, i_stim, i_EPSP_peak)
    i_EPSP_slope, first_bis_zero_time = find_i_EPSP_slope_bis0(dfmean, i_VEB, i_EPSP_peak, i_stim, happy=True, sampling_Hz=sampling_Hz)
    i_volley_slope = find_i_volley_slope(dfmean, i_stim, i_VEB)
    if pd.isna(i_volley_slope):
        i_volley_slope = i_stim + 10
    if pd.isna(i_VEB):
        i_VEB = i_volley_slope + 10
    if pd.isna(i_EPSP_peak):
        i_EPSP_peak = i_VEB + 10
    if pd.isna(i_EPSP_slope):
        i_EPSP_slope = i_EPSP_peak
    i_volley_slope = int(i_volley_slope)
    i_VEB = int(i_VEB)
    i_EPSP_peak = int(i_EPSP_peak)
    i_EPSP_slope = int(i_EPSP_slope)
    max_index = len(dfmean) - 1
    i_stim = min(max(i_stim, 0), max_index)
    i_volley_slope = min(max(i_volley_slope, 0), max_index)
    i_VEB = min(max(i_VEB, 0), max_index)
    i_EPSP_peak = min(max(i_EPSP_peak, 0), max_index)
    i_EPSP_slope = min(max(i_EPSP_slope, 0), max_index)
    time_scaled = time * time_scale_factor
    features = [
        (time_scaled[i_volley_slope] - time_scaled[i_stim]),
        (time_scaled[i_VEB] - time_scaled[i_stim]),
        (time_scaled[i_EPSP_peak] - time_scaled[i_VEB]) if i_EPSP_peak > i_VEB else 0,
        veb_prominence if veb_prominence else 0,
        (time_scaled[i_EPSP_slope] - time_scaled[i_VEB]) if i_EPSP_slope > i_VEB else 0,
        first_bis_zero_time * time_scale_factor if first_bis_zero_time is not None else 0,
        kurtosis(voltage_norm), skew(voltage_norm),
        np.mean(tris), np.std(tris),
        np.sum(np.abs(fft(voltage_norm))[:len(voltage_norm)//2][int(0 * len(voltage_norm)/2000):int(500 * len(voltage_norm)/2000)])
    ]
    return np.array(features)

def augment_signal(signal, num_augmentations=30, noise_std=0.0002, time_shift=0.0005):
    noise_std = 0.05 * signal['voltage'].std()
    augmented_signals = []
    augmented_intervals = []
    intervals = {
        'volley': (signal['t_volley_slope_start'].iloc[0] if 't_volley_slope_start' in signal else 0,
                   signal['t_volley_slope_end'].iloc[0] if 't_volley_slope_end' in signal else 0),
        'EPSP': (signal['t_EPSP_slope_start'].iloc[0] if 't_EPSP_slope_start' in signal else 0,
                 signal['t_EPSP_slope_end'].iloc[0] if 't_EPSP_slope_end' in signal else 0)
    }
    for _ in range(num_augmentations):
        signal_copy = signal.copy()
        signal_copy['voltage'] += np.random.normal(0, noise_std, len(signal))
        shift = np.random.uniform(-time_shift, time_shift)
        new_intervals = {
            'volley': (intervals['volley'][0] + shift, intervals['volley'][1] + shift),
            'EPSP': (intervals['EPSP'][0] + shift, intervals['EPSP'][1] + shift)
        }
        augmented_signals.append(signal_copy)
        augmented_intervals.append(new_intervals)
    return augmented_signals, augmented_intervals

def prepare_training_data(signals, intervals_list, augment=True, num_augmentations=30, time_scale_factor=10000):
    X_train = []
    y_train = []
    feature_names = [
        'volley_slope_relative_time', 'veb_relative_time', 'epsp_peak_relative_time',
        'veb_prominence', 'epsp_slope_relative_time', 'first_bis_zero_time',
        'kurtosis', 'skew', 'tris_mean', 'tris_std', 'freq_band_0_500'
    ]
    for signal, intervals in zip(signals, intervals_list):
        features = extract_features(signal, time_scale_factor=time_scale_factor)
        analytical_volley, analytical_epsp = compute_analytical_predictions(signal, time_scale_factor=time_scale_factor)
        true_volley = intervals['volley'][0] * time_scale_factor
        true_epsp = intervals['EPSP'][0] * time_scale_factor
        error_volley = true_volley - analytical_volley
        error_epsp = true_epsp - analytical_epsp
        X_train.append(features)
        y_train.append([error_volley, error_epsp])
        if augment:
            aug_signals, aug_intervals = augment_signal(signal, num_augmentations=num_augmentations)
            for aug_signal, aug_interval in zip(aug_signals, aug_intervals):
                features = extract_features(aug_signal, time_scale_factor=time_scale_factor)
                analytical_volley, analytical_epsp = compute_analytical_predictions(aug_signal, time_scale_factor=time_scale_factor)
                true_volley = aug_interval['volley'][0] * time_scale_factor
                true_epsp = aug_interval['EPSP'][0] * time_scale_factor
                error_volley = true_volley - analytical_volley
                error_epsp = true_epsp - analytical_epsp
                X_train.append(features)
                y_train.append([error_volley, error_epsp])
    X_train = pd.DataFrame(X_train, columns=feature_names)
    y_train = np.array(y_train)
    print("Feature variances:", np.var(X_train, axis=0))
    print("Target variances (errors):", np.var(y_train, axis=0))
    print(f"X_train.shape: {X_train.shape}, y_train.shape: {y_train.shape}")
    return X_train, y_train, feature_names

def train_model(X_train, y_train):
    lgbm = LGBMRegressor(
        n_estimators=100, learning_rate=0.05, max_depth=3, num_leaves=8,
        min_data_in_leaf=5, lambda_l1=0.1, lambda_l2=0.1, random_state=42, verbosity=-1
    )
    model = MultiOutputRegressor(lgbm)
    model.fit(X_train, y_train)
    return model

def log_prediction(signal, result, sweepname, filepath='predictions_log.csv'):
    log_entry = {
        'sweepname': sweepname,
        't_volley_slope_start': result['hybrid-t_volley_slope_start'],
        't_EPSP_slope_start': result['hybrid-t_EPSP_slope_start'],
        'timestamp': pd.Timestamp.now()
    }
    pd.DataFrame([log_entry]).to_csv(filepath, mode='a', header=not Path(filepath).exists())

def predict_intervals(signal, model, method_name="hybrid", time_scale_factor=10000, default_dict_t=None, feature_names=None):
    if method_name in ["analytical", "analytical_imp"]:
        result_df = find_all_t(signal, default_dict_t)[['t_volley_slope_start', 't_EPSP_slope_start']]
        prefix = "analytic" if method_name == "analytical_imp" else method_name
        result_df.columns = [f"{prefix}-{col}" for col in result_df.columns]
        result = result_df.to_dict(orient='records')[0]
        result.update({
            f'{prefix}-analytical_volley_start': result[f'{prefix}-t_volley_slope_start'],
            f'{prefix}-analytical_epsp_start': result[f'{prefix}-t_EPSP_slope_start']
        })
        return result
    feature_names = feature_names or [
        'volley_slope_relative_time', 'veb_relative_time', 'epsp_peak_relative_time',
        'veb_prominence', 'epsp_slope_relative_time', 'first_bis_zero_time',
        'kurtosis', 'skew', 'tris_mean', 'tris_std', 'freq_band_0_500'
    ]
    analytical_volley, analytical_epsp = compute_analytical_predictions(signal, time_scale_factor=1.0)
    analytical_volley_scaled = analytical_volley * time_scale_factor
    analytical_epsp_scaled = analytical_epsp * time_scale_factor
    features = extract_features(signal, time_scale_factor=time_scale_factor)
    features_df = pd.DataFrame(features.reshape(1, -1), columns=feature_names)
    predicted_errors = model.predict(features_df)[0]
    error_volley, error_epsp = predicted_errors
    adjusted_volley_start = (analytical_volley_scaled + error_volley) / time_scale_factor
    adjusted_epsp_start = (analytical_epsp_scaled + error_epsp) / time_scale_factor
    volley_end = adjusted_volley_start + default_dict_t['t_volley_slope_halfwidth'] * 2
    epsp_end = adjusted_epsp_start + default_dict_t['t_EPSP_slope_halfwidth'] * 2
    if adjusted_epsp_start < volley_end:
        adjusted_epsp_start = volley_end + 0.001
        epsp_end = adjusted_epsp_start + default_dict_t['t_EPSP_slope_halfwidth'] * 2
    result = {
        f'{method_name}-t_volley_slope_start': adjusted_volley_start,
        f'{method_name}-t_volley_slope_end': volley_end,
        f'{method_name}-t_EPSP_slope_start': adjusted_epsp_start,
        f'{method_name}-t_EPSP_slope_end': epsp_end,
        f'{method_name}-analytical_volley_start': analytical_volley,
        f'{method_name}-analytical_epsp_start': analytical_epsp
    }
    log_prediction(signal, result, signal['sweepname'].iloc[0])
    return result


# %%
# --- Unchanged evaluate_and_report ---
def evaluate_and_report(dfresults, meta, signals, time_scale_factor=10000, offset_thresholds=None):
    """
    Evaluate predictions and generate a formatted report with tables for multiple methods.
    Dynamically detects methods by splitting dfresults column names on "-", supporting 1 to 5 methods.
    Combines true and estimated slopes into one column in the Slope Impact Metrics table.
    
    Args:
        dfresults (pd.DataFrame): DataFrame with prediction results (columns like 'method-t_EPSP_slope_start').
        meta (pd.DataFrame): Ground truth data.
        signals (list): List of signal DataFrames.
        time_scale_factor (int): Factor to convert seconds to index points (default: 10000).
        offset_thresholds (list): List of index offset thresholds (e.g., [1, 2, 3]). Defaults to [1, 2, 3].
    
    Raises:
        ValueError: If the number of detected methods is not between 1 and 5, or if required columns are missing.
    """
    # Set default offset thresholds if none provided
    if offset_thresholds is None:
        offset_thresholds = [1, 2, 3, 5]
    
    # Define ground truth columns
    true_cols = ["t_EPSP_slope_start", "t_volley_slope_start"]
    
    # Validate ground truth columns in meta
    missing_true_cols = [col for col in true_cols if col not in meta.columns]
    if missing_true_cols:
        raise ValueError(f"Ground truth columns missing in meta: {missing_true_cols}")
    
    # Detect methods by splitting column names on "-"
    method_cols = {}
    all_columns = set(dfresults.columns)
    for col in all_columns:
        if "-" in col:
            method_name, suffix = col.split("-", 1)
            if suffix in ["t_EPSP_slope_start", "t_volley_slope_start", "analytical_volley_start", "analytical_epsp_start"]:
                if method_name not in method_cols:
                    method_cols[method_name] = []
                method_cols[method_name].append(col)
    
    # Validate methods and columns
    methods = sorted(method_cols.keys())
    if not (1 <= len(methods) <= 5):
        raise ValueError(f"Number of detected methods must be between 1 and 5, found {len(methods)}: {methods}")
    
    for method in methods:
        expected_cols = [f"{method}-t_EPSP_slope_start", f"{method}-t_volley_slope_start"]
        missing_cols = [col for col in expected_cols if col not in method_cols[method]]
        if missing_cols:
            # Check if analytical columns exist as fallback (e.g., for method "analytical")
            analytical_cols = [f"{method}-analytical_epsp_start", f"{method}-analytical_volley_start"]
            if all(col in method_cols[method] for col in analytical_cols):
                method_cols[method] = analytical_cols
            else:
                raise ValueError(f"Missing columns for method {method}: {missing_cols}")
        else:
            method_cols[method] = expected_cols
    
    print(f"Detected methods: {methods}")
    print(f"\n{'='*50}")
    print(f"Evaluation Report")
    print(f"{'='*50}\n")
    
    # Compute metrics for each method
    method_metrics = {}
    for method in methods:
        pred_cols = method_cols[method]
        # Compute index offset metrics
        diff = ((dfresults[pred_cols].rename(columns={
            pred_cols[0]: 't_EPSP_slope_start',
            pred_cols[1]: 't_volley_slope_start'
        }) - meta[true_cols]) * time_scale_factor).round(0)
        volley_offsets = [(threshold <= diff['t_volley_slope_start'].abs()).sum() / len(diff) for threshold in offset_thresholds]
        epsp_offsets = [(threshold <= diff['t_EPSP_slope_start'].abs()).sum() / len(diff) for threshold in offset_thresholds]
        
        # Compute MAE and RMSE in index points
        errors_volley = (dfresults[pred_cols[1]] - meta['t_volley_slope_start']) * time_scale_factor
        errors_epsp = (dfresults[pred_cols[0]] - meta['t_EPSP_slope_start']) * time_scale_factor
        mae_volley = errors_volley.abs().mean()
        mae_epsp = errors_epsp.abs().mean()
        rmse_volley = np.sqrt((errors_volley ** 2).mean())
        rmse_epsp = np.sqrt((errors_epsp ** 2).mean())
        
        method_metrics[method] = {
            'volley_offsets': volley_offsets,
            'epsp_offsets': epsp_offsets,
            'mae_volley': mae_volley,
            'mae_epsp': mae_epsp,
            'rmse_volley': rmse_volley,
            'rmse_epsp': rmse_epsp
        }
    
    # Compute slope-based metrics (true slopes, detected slopes, and MAPE) for each method
    slope_metrics = {}
    true_volley_slopes = []
    true_epsp_slopes = []
    for idx, signal in enumerate(signals):
        true_volley_start = meta.iloc[idx]['t_volley_slope_start']
        true_epsp_start = meta.iloc[idx]['t_EPSP_slope_start']
        
        true_volley_slope = compute_slope(signal, true_volley_start, num_points=3)
        true_epsp_slope = compute_slope(signal, true_epsp_start, num_points=7)
        
        true_volley_slopes.append(true_volley_slope)
        true_epsp_slopes.append(true_epsp_slope)
    
    # Average true slopes across all signals
    avg_true_volley_slope = np.mean(true_volley_slopes)
    avg_true_epsp_slope = np.mean(true_epsp_slopes)
    
    for method in methods:
        pred_cols = method_cols[method]
        volley_detected_slopes = []
        epsp_detected_slopes = []
        volley_mape_list = []
        epsp_mape_list = []
        
        for idx, (result, signal) in enumerate(zip(dfresults.to_dict('records'), signals)):
            true_volley_start = meta.iloc[idx]['t_volley_slope_start']
            true_epsp_start = meta.iloc[idx]['t_EPSP_slope_start']
            
            pred_volley_start = result[pred_cols[1]]
            pred_epsp_start = result[pred_cols[0]]
            
            true_volley_slope = compute_slope(signal, true_volley_start, num_points=3)
            pred_volley_slope = compute_slope(signal, pred_volley_start, num_points=3)
            true_epsp_slope = compute_slope(signal, true_epsp_start, num_points=7)
            pred_epsp_slope = compute_slope(signal, pred_epsp_start, num_points=7)
            
            volley_detected_slopes.append(pred_volley_slope)
            epsp_detected_slopes.append(pred_epsp_slope)
            
            if true_volley_slope != 0:
                pred_volley_mape = abs((pred_volley_slope - true_volley_slope) / true_volley_slope) * 100
            else:
                pred_volley_mape = 0 if pred_volley_slope == 0 else 100
            volley_mape_list.append(pred_volley_mape)
            
            if true_epsp_slope != 0:
                pred_epsp_mape = abs((pred_epsp_slope - true_epsp_slope) / true_epsp_slope) * 100
            else:
                pred_epsp_mape = 0 if pred_epsp_slope == 0 else 100
            epsp_mape_list.append(pred_epsp_mape)
        
        slope_metrics[method] = {
            'volley_detected_slope': np.mean(volley_detected_slopes),
            'epsp_detected_slope': np.mean(epsp_detected_slopes),
            'volley_mape': np.mean(volley_mape_list),
            'epsp_mape': np.mean(epsp_mape_list)
        }
    
    # Index Offset Metrics Table (Dynamic Columns, Stacked Rows)
    print("Index Offset Metrics (1 index = 0.0001 s)")
    print("-" * 50)
    
    headers = [''] + [f"{threshold}<=" for threshold in offset_thresholds]
    longest_label = max(len(f"{method} Volley Slope") for method in methods)
    col_width = max(10, longest_label, max(len(header) for header in headers) + 2)
    header_line = f"{headers[0]:<{col_width}} " + " ".join(f"{header:^{col_width}}" for header in headers[1:])
    print(header_line)
    print("-" * (col_width * len(headers) + len(headers) - 1))
    
    for method in methods:
        offsets = method_metrics[method]['volley_offsets']
        values = [f"{val:^{col_width}.3f}" for val in offsets]
        print(f"{f'{method} Volley Slope':<{col_width}} {' '.join(values)}")
    print("")
    for method in methods:
        offsets = method_metrics[method]['epsp_offsets']
        values = [f"{val:^{col_width}.3f}" for val in offsets]
        print(f"{f'{method} EPSP Slope':<{col_width}} {' '.join(values)}")
    print("\n")
    
    # Error Metrics Table (MAE and RMSE, Stacked Rows)
    print("Error Metrics (Index Points)")
    print("-" * 50)
    headers = [''] + ["MAE", "RMSE"]
    col_width = max(10, longest_label, max(len(header) for header in headers) + 2)
    header_line = f"{headers[0]:<{col_width}} " + " ".join(f"{header:^{col_width}}" for header in headers[1:])
    print(header_line)
    print("-" * (col_width * len(headers) + len(headers) - 1))
    for method in methods:
        mae = method_metrics[method]['mae_volley']
        rmse = method_metrics[method]['rmse_volley']
        print(f"{f'{method} Volley Slope':<{col_width}} {mae:^{col_width}.2f} {rmse:^{col_width}.2f}")
    print("")
    for method in methods:
        mae = method_metrics[method]['mae_epsp']
        rmse = method_metrics[method]['rmse_epsp']
        print(f"{f'{method} EPSP Slope':<{col_width}} {mae:^{col_width}.2f} {rmse:^{col_width}.2f}")
    print("\n")
    
    # Slope Impact Metrics Table (True Slope and Detected Slope in One Column, MAPE Separate)
    print("Slope Impact Metrics")
    print("-" * 50)
    headers = [''] + ["Slope (True/Estimated)", "MAPE"]
    col_width = max(10, longest_label, max(len(header) for header in headers) + 2)
    header_line = f"{headers[0]:<{col_width}} " + " ".join(f"{header:^{col_width}}" for header in headers[1:])
    print(header_line)
    print("-" * (col_width * len(headers) + len(headers) - 1))
    
    # Volley Slope Section
    print(f"{'True Volley Slope':<{col_width}} {avg_true_volley_slope:^{col_width}.4f} {'':^{col_width}}")
    for method in methods:
        detected_slope = slope_metrics[method]['volley_detected_slope']
        mape = slope_metrics[method]['volley_mape']
        print(f"{f'{method} Volley Slope':<{col_width}} {detected_slope:^{col_width}.4f} {mape:^{col_width}.2f}%")
    print("")
    
    # EPSP Slope Section
    print(f"{'True EPSP Slope':<{col_width}} {avg_true_epsp_slope:^{col_width}.4f} {'':^{col_width}}")
    for method in methods:
        detected_slope = slope_metrics[method]['epsp_detected_slope']
        mape = slope_metrics[method]['epsp_mape']
        print(f"{f'{method} EPSP Slope':<{col_width}} {detected_slope:^{col_width}.4f} {mape:^{col_width}.2f}%")
    print("\n")
    
    print(f"{'='*50}\n")


# %%
# --- Unchanged Main Script ---
if __name__ == "__main__":
    folder_talkback = Path.home() / 'Documents' / 'Brainwash Data Source' / 'talkback Lactate24SR'
    slice_filepaths = sorted(list(folder_talkback.glob('*slice*')))
    meta_filepaths = sorted(list(folder_talkback.glob('*meta*')))
    df = pd.concat([load_slice(slice_filepath, sweep) for sweep, slice_filepath in enumerate(slice_filepaths)])
    meta = pd.concat([load_meta(meta_filepath, sweep) for sweep, meta_filepath in enumerate(meta_filepaths)])
    signals = []
    intervals = []
    for i, metarow in meta.iterrows():
        sweepname = metarow['sweepname']
        signal = df[df['sweepname'] == sweepname][['time', 'voltage', 'sweepname']].copy()
        signals.append(signal)
        interval = {
            'volley': (metarow['t_volley_slope_start'], metarow['t_volley_slope_end']),
            'EPSP': (metarow['t_EPSP_slope_start'], metarow['t_EPSP_slope_end'])
        }
        intervals.append(interval)
    X_train, y_train, feature_names = prepare_training_data(signals, intervals, augment=True, num_augmentations=30)
    model = train_model(X_train, y_train)

    
    def check_sweep(sweepname, method_name):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis', 'sweepname']]
        default_dict_t = {
            't_volley_slope_halfwidth': 0.0001,
            't_EPSP_slope_halfwidth': 0.0003,
            'stim': 0,
            't_stim': 0,
            't_stim_method': 0,
            't_stim_params': 0,
            't_volley_slope_width': 0.0003,
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
            't_EPSP_slope_start': 0,
            't_EPSP_slope_end': 0,
            't_EPSP_slope_method': 'auto detect',
            't_EPSP_slope_params': 'NA',
            't_EPSP_amp': 0,
            't_EPSP_amp_halfwidth': 0,
            't_EPSP_amp_method': 'auto detect',
            't_EPSP_amp_params': 'NA',
            'norm_output_from': 0,
            'norm_output_to': 0
        }
        if method_name in ["analytic_new", "analytic_old"]:
            result_df = analysis.find_all_t(dfsweep, default_dict_t)[['t_volley_slope_start', 't_EPSP_slope_start']] if method_name == "analytic_old" else find_all_t(dfsweep, default_dict_t)[['t_volley_slope_start', 't_EPSP_slope_start']]
            result_df.columns = [f"{method_name}-{col}" for col in result_df.columns]
            result = result_df.to_dict(orient='records')[0]
        else:
            result = predict_intervals(dfsweep, model, method_name=method_name, default_dict_t=default_dict_t, feature_names=feature_names)
        result.update({'sweepname': sweepname})
        return result

    
    methods = ["hybrid", "analytic_old", "analytic_new"]
    all_results = []
    for sweepname in df.sweepname.unique():
        sweep_results = {}
        for method in methods:
            result = check_sweep(sweepname, method_name=method)
            for key, value in result.items():
                sweep_results[key] = value
        all_results.append(sweep_results)
    dfresults = pd.DataFrame(all_results)
    evaluate_and_report(dfresults, meta, signals)


# %%
def plot_volley_slope_errors(dfresults, meta, signals, time_scale_factor=10000):
    import matplotlib.pyplot as plt
    error_threshold = 1  # Mark errors ≥ 1 index
    large_error_threshold = 5  # Highlight errors ≥ 5 indices
    
    # Compute offsets for all sweeps and sort by largest error
    offsets = []
    for idx, signal in enumerate(signals):
        sweepname = signal['sweepname'].iloc[0]
        true_volley = meta.iloc[idx]['t_volley_slope_start']
        pred_volley = dfresults.iloc[idx]['analytic_new-t_volley_slope_start']
        offset = abs(pred_volley - true_volley) * time_scale_factor
        offsets.append((offset, idx, sweepname))
    offsets.sort(reverse=True)  # Sort by offset (largest first)
    num_sweeps = min(5, len(signals))  # Limit to 5 sweeps
    worst_sweeps = offsets[:num_sweeps]
    debug_sweeps = [sweep[2] for sweep in worst_sweeps]  # List of worst sweep names
    
    fig, axes = plt.subplots(num_sweeps, 1, figsize=(12, 3 * num_sweeps), sharex=True)
    if num_sweeps == 1:
        axes = [axes]  # Ensure axes is iterable for a single subplot
    
    large_errors = []
    global debug_counter
    debug_counter = 0  # Reset counter for each plot
    
    for plot_idx, (offset, idx, sweepname) in enumerate(worst_sweeps):
        signal = signals[idx]
        ax = axes[plot_idx]
        true_volley = meta.iloc[idx]['t_volley_slope_start']
        pred_volley = dfresults.iloc[idx]['analytic_new-t_volley_slope_start']
        
        # Create a temporary DataFrame with prim and bis for find_all_i
        signal_full = signal.copy()
        rollingwidth = 3
        signal_full['prim'] = signal_full['voltage'].rolling(rollingwidth, center=True).mean().diff()
        signal_full['bis'] = signal_full['prim'].rolling(rollingwidth, center=True).mean().diff()
        
        # Compute t_stim using find_all_i
        df_i = find_all_i(signal_full, sweepname=sweepname, debug_sweeps=debug_sweeps)
        i_stim = df_i['i_stim'].iloc[0] if not df_i.empty else 0  # Use first i_stim
        t_stim = signal['time'].iloc[i_stim] if i_stim < len(signal) else signal['time'].iloc[0]
        
        # Align time relative to t_stim
        time_shifted = signal['time'] - t_stim
        
        # Define window around volley and VEB (t_stim + padding to t_VEB + 0.001s)
        window_start = t_stim + 0.0005  # Pad 0.5ms to exclude stim pulse
        i_VEB = df_i['i_VEB'].iloc[0] if not df_i.empty and not pd.isna(df_i['i_VEB'].iloc[0]) else i_stim + int(0.002 * time_scale_factor)
        t_VEB = signal['time'].iloc[i_VEB] if i_VEB < len(signal) else t_stim + 0.002
        window_end = t_VEB + 0.001  # Extend 1ms past VEB
        signal_window = signal[(signal['time'] >= window_start) & (signal['time'] <= window_end)]
        
        # Compute y-limits based on signal in this window
        if not signal_window.empty:
            voltage_min = signal_window['voltage'].min()
            voltage_max = signal_window['voltage'].max()
            voltage_range = voltage_max - voltage_min
            y_min = voltage_min - 0.2 * voltage_range  # 20% padding
            y_max = voltage_max + 0.2 * voltage_range  # 20% padding
        else:
            y_min, y_max = signal['voltage'].mean() - 0.5, signal['voltage'].mean() + 0.5  # Fallback
        
        # Plot signal
        ax.plot(time_shifted, signal['voltage'], label='Signal', color='blue', alpha=0.7)
        
        # Mark true and predicted volley slope start
        true_volley_shifted = true_volley - t_stim
        pred_volley_shifted = pred_volley - t_stim
        offset = abs(pred_volley - true_volley) * time_scale_factor  # Convert to indices
        
        ax.axvline(true_volley_shifted, c='green', ls='--', label='True Volley')
        color = 'red' if offset >= large_error_threshold else 'orange' if offset >= error_threshold else 'lime'
        ax.axvline(pred_volley_shifted, c=color, label='Pred Volley')
        
        # Annotate offset
        if offset >= error_threshold:
            ax.text(pred_volley_shifted, signal['voltage'].mean(), f'{offset:.1f} idx', color=color, fontsize=8, ha='right')
        
        # Set title and labels
        ax.set_title(f'Sweep {idx} ({sweepname})')
        ax.set_ylabel('Voltage')
        ax.set_ylim(y_min, y_max)  # Apply y-limits based on volley/VEB region
        ax.legend()
        
        # Record large errors
        if offset >= large_error_threshold:
            large_errors.append((idx, sweepname, offset))
    
    plt.xlabel('Time Relative to Stimulus (s)')
    plt.tight_layout()
    plt.show()
    
    # Print large errors
    if large_errors:
        print("Sweeps with large errors (≥ 5 indices):")
        for idx, sweepname, offset in large_errors:
            print(f"Sweep {idx} ({sweepname}): Offset = {offset:.2f} indices")



# %%
plot_volley_slope_errors(dfresults, meta, signals)

# %%
meta.t_volley_slope_start.values

# %%
