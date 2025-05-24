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
'''
purpose
pull all Mats (and later user feedback) supplied graphs with manual labels
push them through analysis modules, collect results and evaluate

'''

# %%
import os
import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path
import seaborn as sns
from sklearn.linear_model import LinearRegression

reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))
import analysis_v1
import analysis_v2

# %% [markdown]
# # loaders

# %%
# read slices and meta
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
#meta

# %% [markdown]
# # evaluators

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
        offset_thresholds = [1, 2, 3, 5, 10]
    
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

# %% [markdown]
# # estimation

# %%

# %%
if __name__ == "__main__":
    default_dict_t = { # default values for df_t(imepoints)
        't_volley_slope_width': 0.0001,
        't_EPSP_slope_width': 0.0003,
    }
    
    def check_sweep(sweepname):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis']]
        result = analysis_v1.find_all_t(dfsweep, default_dict_t)[['t_volley_slope_start', 't_EPSP_slope_start']]
        result.columns = [f"analytic_v1-{i}" for i in result.columns]
        result['sweepname'] = sweepname
        return result
    
    results = []
    signals = []
    for sweepname in df.sweepname.unique():
        result = check_sweep(sweepname)
        results.append(result)
        signal = df[df['sweepname'] == sweepname][['time', 'voltage']].copy()
        signals.append(signal)
    dfresults_av1 = pd.concat(results).reset_index(drop=True)

    def check_sweep(sweepname):
        dfsweep = df.loc[df.sweepname == sweepname, ['time', 'voltage', 'prim', 'bis']]
        result = analysis_v2.characterize_graph(dfsweep, stim_amp=0.005, verbose=False, plot=False)
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

    dfresults = pd.merge(dfresults_av1, dfresults_av2, right_on='sweepname', left_on='sweepname')
    
    
    evaluate_and_report(dfresults, meta, signals)

# %%
if __name__ == "__main__":
    tcols = ['t_volley_slope_start', 't_EPSP_slope_start']
    dfdiff = dfresults[['sweepname']].copy()
    for col in dfresults.columns:
        try:
            col_end = col.split('-')[1] if col.endswith('_start') else ''
        except:
            col_end = ''
        if col_end in tcols:
            dfdiff[col] = round(10000 * (dfresults[col] - meta[col_end]))
    display(dfdiff)

# %%
#dfdiff.select_dtypes('number').abs().sum()

# %%
