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
from lightgbm import LGBMRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import LinearRegression


reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))
import analysis

# %%
# read slices and meta, this is Mats supplied true values to graphs
folder_talkback = Path.home() / 'Documents' / 'Brainwash Data Source' / 'talkback KetaDexa'
folder_talkback = Path.home() / 'Documents' / 'Brainwash Data Source' / 'talkback Lactate24SR'
slice_filepaths = sorted(list(folder_talkback.glob('*slice*')))
meta_filepaths = sorted(list(folder_talkback.glob('*meta*')))


# %%
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
#df.sort_index(inplace=True)
#assert(df.isna().sum().max() < 2)
#df = df.dropna()

# %%
meta_filepaths
def load_meta(path, sweep=1):
    with open(path) as file:
        df =  pd.DataFrame(json.load(file), index=[sweep])
    df['sweepname'] = str(path.name).split('.')[0].split('_')[-2]
    #df = pd.DataFrame(pd.read_csv(str(path)), index=[sweep])
    #df.set_index('time', inplace=True, drop=True)
    #df['sweep'] = sweep
    #print(df)
    return df

meta = pd.concat([load_meta(meta_filepath, sweep) for sweep, meta_filepath in enumerate(meta_filepaths)])
meta


# %%

# %%

# %%

# %%
# grok evaluate results
def compute_slope(df, start_time, num_points, time_step=0.0001):
    """Compute the slope over a closed interval using linear regression."""
    end_time = start_time + (num_points - 1) * time_step
    df_interval = df[(df['time'] >= start_time) & (df['time'] <= end_time)]
    if len(df_interval) < 2:
        return 0
    X = df_interval['time'].values.reshape(-1, 1)
    y = df_interval['voltage'].values
    reg = LinearRegression().fit(X, y)
    return reg.coef_[0]

def compute_slope_metrics(dfresults, signals, meta):
    volley_mape_list = []
    epsp_mape_list = []
    
    for idx, (result, signal) in enumerate(zip(dfresults.to_dict('records'), signals)):
        true_volley_start = meta.iloc[idx]['t_volley_slope_start']
        true_epsp_start = meta.iloc[idx]['t_EPSP_slope_start']
        
        pred_volley_start = result['t_volley_slope_start']
        pred_epsp_start = result['t_EPSP_slope_start']
        anal_volley_start = result['analytical_volley_start']
        anal_epsp_start = result['analytical_epsp_start']
        
        true_volley_slope = compute_slope(signal, true_volley_start, num_points=3)
        pred_volley_slope = compute_slope(signal, pred_volley_start, num_points=3)
        anal_volley_slope = compute_slope(signal, anal_volley_start, num_points=3)
        
        true_epsp_slope = compute_slope(signal, true_epsp_start, num_points=7)
        pred_epsp_slope = compute_slope(signal, pred_epsp_start, num_points=7)
        anal_epsp_slope = compute_slope(signal, anal_epsp_start, num_points=7)
        
        if true_volley_slope != 0:
            pred_volley_mape = abs((pred_volley_slope - true_volley_slope) / true_volley_slope) * 100
            anal_volley_mape = abs((anal_volley_slope - true_volley_slope) / true_volley_slope) * 100
        else:
            pred_volley_mape = 0 if pred_volley_slope == 0 else 100
            anal_volley_mape = 0 if anal_volley_slope == 0 else 100
        volley_mape_list.append((pred_volley_mape, anal_volley_mape))
        
        if true_epsp_slope != 0:
            pred_epsp_mape = abs((pred_epsp_slope - true_epsp_slope) / true_epsp_slope) * 100
            anal_epsp_mape = abs((anal_epsp_slope - true_epsp_slope) / true_epsp_slope) * 100
        else:
            pred_epsp_mape = 0 if pred_epsp_slope == 0 else 100
            anal_epsp_mape = 0 if anal_epsp_slope == 0 else 100
        epsp_mape_list.append((pred_epsp_mape, anal_epsp_mape))
    
    pred_volley_mape = np.mean([x[0] for x in volley_mape_list])
    anal_volley_mape = np.mean([x[1] for x in volley_mape_list])
    pred_epsp_mape = np.mean([x[0] for x in epsp_mape_list])
    anal_epsp_mape = np.mean([x[1] for x in epsp_mape_list])
    
    return {
        'pred_volley_mape': pred_volley_mape,
        'anal_volley_mape': anal_volley_mape,
        'pred_epsp_mape': pred_epsp_mape,
        'anal_epsp_mape': anal_epsp_mape
    }
    


# %% [markdown]
# ### def evaluate_and_report

# %%
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
def find_i_stims(dfmean, threshold=0.1, min_time_difference=0.005):
    prim_max = np.argmax(dfmean['prim'].values)
    prim_max_y = dfmean['prim'].max()
    threshold *= prim_max_y

    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    filtered_indices = []
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
    return filtered_indices

def find_i_EPSP_peak_max(
    dfmean,
    sampling_Hz=10000,
    limitleft=0,
    limitright=-1,
    param_EPSP_minimum_width_ms=4,
    param_EPSP_minimum_prominence_mV=0.0001,
    verbose=False
):
    if verbose:
        print("find_i_EPSP_peak_max:")
    EPSP_minimum_width_i = int(param_EPSP_minimum_width_ms * 0.001 * sampling_Hz)
    if verbose:
        print(" . . . EPSP must be at least", EPSP_minimum_width_i, "points wide")
    if limitright != -1:
        dfmean_sliced = dfmean[(limitleft <= dfmean.index) & (dfmean.index <= limitright)]
    else:
        dfmean_sliced = dfmean[limitleft <= dfmean.index]
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

def find_i_VEB_prim_peak_max(
    dfmean,
    i_stim,
    i_EPSP,
    param_minimum_width_of_EPSP=5,
    param_minimum_width_of_VEB=1,
    param_prim_prominence=0.0001,
    verbose=False
):
    if verbose:
        print("find_i_VEB_prim_peak_max:")
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    if verbose:
        print(f" . . . sampling_Hz: {sampling_Hz}")
    minimum_acceptable_i_for_VEB = int(i_stim + 0.001 * sampling_Hz)
    max_acceptable_i_for_VEB = int(
        i_EPSP - np.floor((param_minimum_width_of_EPSP * 0.001 * sampling_Hz) / 2)
    ) if not np.isnan(i_EPSP) else len(dfmean) - 1
    if verbose:
        print(" . . . VEB is between", minimum_acceptable_i_for_VEB, "and", max_acceptable_i_for_VEB)
    prim_sample = dfmean['prim'].values[minimum_acceptable_i_for_VEB:max_acceptable_i_for_VEB]
    i_peaks, properties = find_peaks(
        prim_sample,
        width=param_minimum_width_of_VEB * 1000 / sampling_Hz,
        prominence=param_prim_prominence / 1000,
    )
    i_peaks += minimum_acceptable_i_for_VEB
    if verbose:
        print(" . . . i_peaks:", i_peaks)
    if len(i_peaks) == 0:
        if verbose:
            print(" . . No peaks in specified interval.")
        return np.nan, 0
    if verbose:
        print(f" . . . properties:{properties}")
    i_VEB = i_peaks[properties['prominences'].argmax()]
    veb_prominence = properties['prominences'][i_peaks.argmax()] if len(i_peaks) > 0 else 0
    if verbose:
        print(f" . . . i_VEB: {i_VEB}")
    return i_VEB, veb_prominence

def find_i_EPSP_slope_bis0(dfmean, i_VEB, i_EPSP, happy=True, verbose=False):
    if i_VEB is None or i_EPSP is None or np.isnan(i_VEB) or np.isnan(i_EPSP):
        return np.nan, None
    i_VEB = int(i_VEB)
    i_EPSP = int(i_EPSP)
    if i_VEB >= i_EPSP:
        return np.nan, None
    dftemp = dfmean.bis[i_VEB:i_EPSP]
    i_EPSP_slope = dftemp[0 < dftemp.apply(np.sign).diff()].index.values
    if len(i_EPSP_slope) == 0:
        if verbose:
            print(" . . No positive zero-crossings in dfmean.bis[i_VEB: i_EPSP].")
        return np.nan, None
    if 1 < len(i_EPSP_slope):
        if not happy:
            raise ValueError(f"Found multiple positive zero-crossings in dfmean.bis[i_VEB: i_EPSP]:{i_EPSP_slope}")
        else:
            if verbose:
                print("More EPSPs than we wanted but I'm happy, so I pick the first one and move on.")
    first_zero_crossing = i_EPSP_slope[0]
    return first_zero_crossing, dfmean['time'].iloc[first_zero_crossing]

def find_i_volley_slope(dfmean, i_stim, i_VEB, happy=True):
    if i_stim is None or i_VEB is None or np.isnan(i_stim) or np.isnan(i_VEB):
        return np.nan
    i_stim = int(i_stim)
    i_VEB = int(i_VEB)
    if i_VEB <= i_stim:
        return np.nan
    dftemp = dfmean.prim[i_VEB-12:i_VEB]
    if len(dftemp) == 0:
        return np.nan
    i_volleyslope = dftemp.idxmin()
    return i_volleyslope

def find_all_i(dfmean, i_stims=None, param_min_time_from_i_stim=0.0005, verbose=False):
    if i_stims is None:
        i_stims = find_i_stims(dfmean=dfmean)
    if not i_stims:
        return pd.DataFrame()
    time_delta = dfmean.time[1] - dfmean.time[0]
    sampling_Hz = 1 / time_delta
    if verbose:
        print(f"find_i_stims: {len(i_stims)}: sampling_Hz: {sampling_Hz}")
        print(i_stims)
    list_dict_i = []
    for i in i_stims:
        if verbose: print(f"processing i_stim: {i}")
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
            "t_EPSP_slope_params": "-",
        }
        dict_i['i_EPSP_amp'] = find_i_EPSP_peak_max(dfmean=dfmean, sampling_Hz=sampling_Hz, limitleft=i, limitright=i+200, verbose=False)
        if not np.isnan(dict_i['i_EPSP_amp']):
            dict_i['i_VEB'], _ = find_i_VEB_prim_peak_max(dfmean=dfmean, i_stim=i, i_EPSP=dict_i['i_EPSP_amp'])
            if not np.isnan(dict_i['i_VEB']):
                dict_i['i_EPSP_slope'], _ = find_i_EPSP_slope_bis0(dfmean=dfmean, i_VEB=dict_i['i_VEB'], i_EPSP=dict_i['i_EPSP_amp'], happy=True)
                if not np.isnan(dict_i['i_EPSP_slope']):
                    dict_i['i_volley_slope'] = find_i_volley_slope(dfmean=dfmean, i_stim=i, i_VEB=dict_i['i_VEB'], happy=True)
                    if not np.isnan(dict_i['i_volley_slope']):
                        dict_i['i_volley_amp'] = dfmean.loc[dict_i['i_volley_slope']:dict_i['i_VEB'], 'voltage'].idxmin()
        list_dict_i.append(dict_i)
    df_i = pd.DataFrame(list_dict_i)
    df_i_numeric = df_i.select_dtypes(include=[np.number])
    list_nan = [i for i in range(len(df_i_numeric)) if df_i_numeric.iloc[i].isnull().any()]
    if list_nan:
        methods = ['t_volley_amp_method', 't_volley_slope_method', 't_EPSP_amp_method', 't_EPSP_slope_method']
        params = ['t_volley_amp_params', 't_volley_slope_params', 't_EPSP_amp_params', 't_EPSP_slope_params']
        for i in range(len(df_i_numeric)):
            if verbose: print(f"checking stim: {i}")
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

def compute_analytical_predictions(signal, time_scale_factor=1.0):
    time = signal['time'].values
    voltage = signal['voltage'].values
    window_length = min(11, len(voltage) // 2 * 2 + 1)
    if window_length < 3:
        window_length = 3
    prim = savgol_filter(voltage, window_length, 2, deriv=1)
    bis = savgol_filter(voltage, window_length, 2, deriv=2)
    
    dfmean = pd.DataFrame({'time': time, 'voltage': voltage, 'prim': prim, 'bis': bis})
    
    df_i = find_all_i(dfmean, param_min_time_from_i_stim=0.0005, verbose=False)
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

def extract_features(signal, window_length=11, polyorder=2, time_scale_factor=10000, stim_buffer_ms=1):
    time = signal['time'].values
    voltage = signal['voltage'].values
    window_length = min(window_length, len(voltage) // 2 * 2 + 1)
    if window_length < 3:
        window_length = 3
    prim = savgol_filter(voltage, window_length, polyorder, deriv=1)
    bis = savgol_filter(voltage, window_length, polyorder, deriv=2)
    
    voltage_norm = (voltage - voltage.mean()) / voltage.std() if voltage.std() > 0 else voltage
    time_scaled = time * time_scale_factor
    
    dfmean = pd.DataFrame({'time': time, 'voltage': voltage, 'prim': prim, 'bis': bis})
    
    i_stim = find_i_stims(dfmean)[0] if find_i_stims(dfmean) else 0
    i_EPSP_peak = find_i_EPSP_peak_max(dfmean, limitleft=i_stim)
    i_VEB, veb_prominence = find_i_VEB_prim_peak_max(dfmean, i_stim, i_EPSP_peak)
    i_volley_slope = find_i_volley_slope(dfmean, i_stim, i_VEB)
    i_EPSP_slope, first_bis_zero_time = find_i_EPSP_slope_bis0(dfmean, i_VEB, i_EPSP_peak, happy=True)
    
    if i_volley_slope is np.nan:
        i_volley_slope = i_stim if i_stim is not None else 0
    if i_VEB is np.nan:
        i_VEB = i_volley_slope + 1 if i_volley_slope is not None else 1
    if i_EPSP_peak is np.nan:
        i_EPSP_peak = i_VEB + 1 if i_VEB is not None else 2
    if i_EPSP_slope is np.nan:
        i_EPSP_slope = i_EPSP_peak if i_EPSP_peak is not None else i_VEB + 1 if i_VEB is not None else 2
    
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
    
    features = [
        (time_scaled[i_volley_slope] - time_scaled[i_stim]),
        (time_scaled[i_VEB] - time_scaled[i_stim]),
        (time_scaled[i_EPSP_peak] - time_scaled[i_VEB]) if i_EPSP_peak > i_VEB else 0,
        veb_prominence if veb_prominence is not None else 0,
        (time_scaled[i_EPSP_slope] - time_scaled[i_VEB]) if i_EPSP_slope > i_VEB else 0,
        first_bis_zero_time * time_scale_factor if first_bis_zero_time is not None else 0,
    ]
    
    buffer_indices = np.where(time_scaled > time_scaled[i_stim] + stim_buffer_ms)[0]
    if len(buffer_indices) == 0:
        buffer_start = len(time_scaled) - 1
    else:
        buffer_start = buffer_indices[0]
    
    prim_after_buffer = prim[buffer_start:]
    volley_region = np.where(prim_after_buffer < np.percentile(prim_after_buffer, 25))[0]
    if len(volley_region) > 0:
        volley_start = volley_region[0] + buffer_start
        volley_end = volley_region[-1] + buffer_start
    else:
        volley_start = buffer_start
        volley_end = buffer_start
    
    post_volley_start = volley_end
    prim_post_volley = prim[post_volley_start:]
    bis_post_volley = bis[post_volley_start:]
    epsp_candidates = np.where((prim_post_volley > 0) & (np.abs(bis_post_volley) < np.percentile(np.abs(bis_post_volley), 75)))[0]
    if len(epsp_candidates) > 0:
        epsp_start = epsp_candidates[0] + post_volley_start
        epsp_end = epsp_candidates[-1] + post_volley_start
    else:
        epsp_start = post_volley_start
        epsp_end = len(voltage) - 1
    
    prim_volley = prim[buffer_start:volley_end + 1]
    bis_volley = bis[buffer_start:volley_end + 1]
    prim_zero_crossings_volley = len(np.where(np.diff(np.sign(prim_volley)) != 0)[0])
    bis_zero_crossings_volley = len(np.where(np.diff(np.sign(bis_volley)) != 0)[0])
    
    prim_epsp = prim[post_volley_start:epsp_end + 1]
    bis_epsp = bis[post_volley_start:epsp_end + 1]
    prim_zero_crossings_epsp = len(np.where(np.diff(np.sign(prim_epsp)) != 0)[0])
    bis_zero_crossings_epsp = len(np.where(np.diff(np.sign(bis_epsp)) != 0)[0])
    
    voltage_after_buffer = voltage_norm[buffer_start:]
    peaks, properties = find_peaks(voltage_after_buffer, prominence=0.01)
    troughs, _ = find_peaks(-voltage_after_buffer, prominence=0.01)
    num_peaks = len(peaks)
    peak_prominence = properties['prominences'].max() if len(peaks) > 0 else 0
    
    features.extend([
        prim_zero_crossings_volley,
        bis_zero_crossings_volley,
        prim_zero_crossings_epsp,
        bis_zero_crossings_epsp,
        num_peaks,
        peak_prominence
    ])
    
    return np.array(features)

def augment_signal(signal, num_augmentations=30, noise_std=0.0002, time_shift=0.001):
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
        noise = np.random.normal(0, noise_std, len(signal))
        signal_copy['voltage'] += noise
        augmented_signals.append(signal_copy)
        
        shift = np.random.uniform(-time_shift, time_shift)
        new_intervals = {
            'volley': (intervals['volley'][0] + shift, intervals['volley'][1] + shift),
            'EPSP': (intervals['EPSP'][0] + shift, intervals['EPSP'][1] + shift)
        }
        augmented_intervals.append(new_intervals)
    
    return augmented_signals, augmented_intervals

def prepare_training_data(signals, intervals_list, augment=True, num_augmentations=30, time_scale_factor=10000):
    X_train = []
    y_train = []
    
    feature_names = [
        'volley_slope_relative_time',
        'veb_relative_time',
        'epsp_peak_relative_time',
        'veb_prominence',
        'epsp_slope_relative_time',
        'first_bis_zero_time',
        'prim_zero_crossings_volley',
        'bis_zero_crossings_volley',
        'prim_zero_crossings_epsp',
        'bis_zero_crossings_epsp',
        'num_peaks',
        'peak_prominence'
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
    return X_train, y_train

def train_model(X_train, y_train):
    lgbm = LGBMRegressor(
        n_estimators=200,
        learning_rate=0.02,
        max_depth=4,
        num_leaves=10,
        min_data_in_leaf=5,
        n_jobs=-1,
        random_state=42,
        verbosity=-1
    )
    model = MultiOutputRegressor(lgbm)
    model.fit(X_train, y_train)
    return model

def predict_intervals(signal, model, method_name="hybrid", time_scale_factor=10000, volley_slope_length=0.0002, epsp_slope_length=0.0006):
    """
    Predict intervals for a given signal using a specified method.

    Args:
        signal (pd.DataFrame): Input signal DataFrame with 'time' and 'voltage' columns.
        model: Trained model to predict errors.
        method_name (str): Name of the method to prefix output columns (default: "hybrid").
        time_scale_factor (int): Factor to convert seconds to index points (default: 10000).
        volley_slope_length (float): Length of volley slope interval (default: 0.0002 s).
        epsp_slope_length (float): Length of EPSP slope interval (default: 0.0006 s).

    Returns:
        dict: Dictionary with predicted intervals, using method-specific column names.
    """
    feature_names = [
        'volley_slope_relative_time',
        'veb_relative_time',
        'epsp_peak_relative_time',
        'veb_prominence',
        'epsp_slope_relative_time',
        'first_bis_zero_time',
        'prim_zero_crossings_volley',
        'bis_zero_crossings_volley',
        'prim_zero_crossings_epsp',
        'bis_zero_crossings_epsp',
        'num_peaks',
        'peak_prominence'
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
    
    volley_end = adjusted_volley_start + volley_slope_length
    epsp_end = adjusted_epsp_start + epsp_slope_length
    
    if adjusted_epsp_start < volley_end:
        adjusted_epsp_start = volley_end + 0.001
        epsp_end = adjusted_epsp_start + epsp_slope_length
    
    # Use method_name to prefix the output column names
    return {
        f'{method_name}-t_volley_slope_start': adjusted_volley_start,
        f'{method_name}-t_volley_slope_end': volley_end,
        f'{method_name}-t_EPSP_slope_start': adjusted_epsp_start,
        f'{method_name}-t_EPSP_slope_end': epsp_end,
        f'{method_name}-analytical_volley_start': analytical_volley,
        f'{method_name}-analytical_epsp_start': analytical_epsp
    }


# %%
# Main script
if __name__ == "__main__":
    # Simulate data with variable lengths
    signals = []
    intervals = []
    for i, metarow in meta.iterrows():
        sweepname = metarow['sweepname']
        signal = df[df['sweepname'] == sweepname][['time', 'voltage']].copy()
        signals.append(signal)
        interval = {
            'volley': (metarow['t_volley_slope_start'], metarow['t_volley_slope_end']),
            'EPSP': (metarow['t_EPSP_slope_start'], metarow['t_EPSP_slope_end'])
        }
        intervals.append(interval)

    # Prepare training data with augmentation
    X_train, y_train = prepare_training_data(signals, intervals, augment=True, num_augmentations=30)
    
    # Train model
    model = train_model(X_train, y_train)
    
    # Predict intervals using Hybrid, Analytical (from analysis.find_all_t), and Analytical_Imp methods
    def check_sweep(sweepname, method_name):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis']]
        if method_name in ["analytical", "analytical_imp"]:
            default_dict_t = {
                't_volley_slope_halfwidth': 0.0001,
                't_EPSP_slope_halfwidth': 0.0003,
            }
            result_df = analysis.find_all_t(dfsweep, default_dict_t)[['t_volley_slope_start', 't_EPSP_slope_start']]
            # Use method_name in column names to distinguish analytical and analytical_imp
            if method_name == "analytical_imp":
                result_df.columns = [f"analytic-{col}" for col in result_df.columns]
            else:
                result_df.columns = [f"{method_name}-{col}" for col in result_df.columns]
            result = result_df.to_dict(orient='records')[0]
        else:
            result = predict_intervals(dfsweep, model, method_name=method_name)
        result.update({'sweepname': sweepname})
        return result
    
    # Run predictions for all methods
    methods = ["hybrid", "analytical", "analytical_imp"]
    all_results = []
    for sweepname in df.sweepname.unique():
        sweep_results = {}
        for method in methods:
            result = check_sweep(sweepname, method_name=method)
            # Update sweep_results with method-specific columns
            for key, value in result.items():
                sweep_results[key] = value
        all_results.append(sweep_results)
    
    dfresults = pd.DataFrame(all_results)
    
    # Evaluate using the existing function
    evaluate_and_report(dfresults, meta, signals)

# %%

# %%

# %%

# %%

# %%

# %%

# %%

# %%

# %%
