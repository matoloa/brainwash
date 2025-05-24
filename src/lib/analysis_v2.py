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
import seaborn as sns
from sklearn.linear_model import LinearRegression


reporoot = Path(os.getcwd()).parent
sys.path.append(str(reporoot / 'src/lib/'))
import analysis_v1


# %% [markdown]
# # func: characterize_graph

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
    time = df['time'].values
    dt = time[1] - time[0]  # Assumes uniform sampling
    
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
    stim_neg_idx = None
    stim_pos_idx = None
    verboses = f"function: characterize_graph_class_a\n"
    if neg_peaks.size > 0 and pos_peaks.size > 0:
        verboses += f"stim: found possible peaks.\n {neg_peaks}, {neg_props}, {pos_peaks}, {pos_props}\n"
        first_neg = neg_peaks[0]
        next_pos_candidates = pos_peaks[pos_peaks > first_neg]
        next_pos = next_pos_candidates[0] if next_pos_candidates.size > 0 else None
        if next_pos is not None:
            verboses += f"stim length: {(time[next_pos] - time[first_neg])}\n"
            if (time[next_pos] - time[first_neg]) < 0.0004:  # Within 0.4 ms               
                stim_amplitude = -voltage[first_neg]
                stim_neg_idx = int(first_neg) - 1 # yes I hardcoded these 1 step adjustments. Hope it stays that way
                stim_pos_idx = int(next_pos) + 1 # yes I hardcoded these 1 step adjustments. Hope it stays that way
                stim_detected = bool(stim_amplitude > stim_amp)
                verboses += f"{stim_detected=}\n"
    else:
        verboses += f"stim: did not find useful peaks.\n {neg_peaks}, {neg_props}, {pos_peaks}, {pos_props}\n"

    # Baseline: Mean voltage before stimulation (or first 10% of data)
    if stim_detected:
        baseline_end = stim_neg_idx - 2
    else:
        baseline_end = int(0.1 * len(voltage))
    baseline = np.mean(voltage[:baseline_end])

    # 2. Volley (M-Shape)
    volley_detected = False
    m_shape = False
    volley_start = stim_neg_idx + int(0.0005 / dt) if stim_detected else int(0.001 / dt)
    volley_end = min(volley_start + int(0.005 / dt), len(voltage))  # Clamp to array length
    volley_region = voltage[volley_start:volley_end]
    verboses += f"volley: search region {volley_start}, {volley_end}\n"
    v_prom = 0.001
    v_peaks = []
    while len(v_peaks) < 2 and v_prom > 1e-6: # iterative volley search until at least 2 prominent peaks are found
        v_peaks, v_peak_props = find_peaks(volley_region, prominence=v_prom)
        v_prom /= 2
    v_troughs, _ = find_peaks(-volley_region, prominence=v_prom) # using same v_prom for peak and trough. seems to work but could change
    volley_peaks_idx = [p + volley_start for p in v_peaks if p + volley_start < len(voltage)]
    volley_troughs_idx = [t + volley_start for t in v_troughs if t + volley_start < len(voltage)]
    if len(v_peaks) >= 2 and len(v_troughs) >= 1:
        volley_detected = True
        for i in range(len(v_peaks) - 1):
            p1, p2 = v_peaks[len(v_peaks) - 2 - i], v_peaks[len(v_peaks) - 1 - i]
            troughs_between = [t for t in v_troughs if p1 < t < p2]
            if troughs_between and volley_region[p2] <= volley_region[p1]:
                m_shape = True
                veb_idx = p2 + volley_start
                volley_peaks_idx = [p1 + volley_start, p2 + volley_start]
                volley_trough_idx = troughs_between[0] + volley_start
                #TODO: speak with Mats, maybe select trough in the middle of the peaks here?
                break

    # 3. EPSP
    epsp_detected = False
    epsp_depth = 0
    epsp_min_idx = None
    epsp_start = veb_idx if volley_detected else stim_pos_idx + 2
    epsp_end = min(epsp_start + int(0.02 / dt), len(voltage)-1)  # Clamp to array length
    verboses += f"epsp region: {epsp_start}:{epsp_end}, time={time[epsp_start]}:{time[epsp_end]}\n"
    epsp_region = voltage[epsp_start:epsp_end] #TODO: could be useful to savgol this for robustness
    if len(epsp_region) > 0:
        epsp_min_idx_rel = np.argmin(epsp_region)
        e_prom = 0.01
        e_peaks = []
        while len(e_peaks) < 1 and e_prom > 1e-6: # iterative epsp search
            e_peaks, e_peak_props = find_peaks( - epsp_region, prominence=e_prom)
            e_prom /= 2
        if len(e_peaks):
            epsp_min_idx = e_peaks[0] + epsp_start # just choosing the leftmost now. with normal curves that should be it, unless noise is very bad
            verboses += f"epsp min: {epsp_min_idx=}, time={time[epsp_min_idx]}\n"
            if epsp_min_idx < len(voltage):
                epsp_depth = baseline - voltage[epsp_min_idx]
                epsp_detected = bool(epsp_depth > 0.0001)
        else:
            verboses += f"epsp min: no peak found\n"

    # 4. Noise Level
    chatter_start = stim_pos_idx + 3 if stim_detected else int(0.05 * len(voltage))
    chatter_end = min(int(0.2 * len(voltage)), len(voltage))
    chatter_region = voltage[chatter_start:chatter_end]
    noise_level = np.std(chatter_region) if len(chatter_region) > 0 else 0

    # 5. Volley Slope (steepest 3-point interval between left volley peak and volley trough, limit search to first half and see what happens)
    volley_slope_start = None
    volley_slope_end = None
    volley_slope_value = None
    if m_shape and 'volley_trough_idx' in locals():
        left_peak = volley_peaks_idx[0]
        trough = volley_trough_idx
        if trough - left_peak >= 2:
            slopes = []
            win_length = min((trough + 1 - left_peak) // 2, 3) # set savgol window length
            pad = 3
            voltage_slope = savgol_filter(voltage[left_peak: trough + pad], window_length=win_length, polyorder=0)
            time_slope = time[left_peak: trough + pad]
            for i in range(len(voltage_slope) - pad): # first half
                x = time_slope[i:i+3]
                y = voltage_slope[i:i+3]
                model = LinearRegression()
                model.fit(x.reshape(-1, 1), y.reshape(-1, 1))
                #coeffs = model.coef_
                coeffs = np.polyfit(x, y, 1)
                slopes.append((i, coeffs[0]))
            if slopes:
                min_slope_i, volley_slope_value = min(slopes, key=lambda x: x[1])
                volley_slope_start = min_slope_i + left_peak
                volley_slope_end = min_slope_i + 2 + left_peak
                verboses += f"volley slope: start={time[volley_slope_start]}, end={time[volley_slope_end]}, slope={volley_slope_value}\n"
            else:
                verboses += "volley slope: not found\n"
        else:
            verboses += "volley slope: region too small\n"

    # 6. EPSP Slope (straightest 7-point interval between right volley peak and EPSP min)
    epsp_slope_start = None
    epsp_slope_end = None
    epsp_slope_value = None
    if epsp_detected and len(volley_peaks_idx) >= 2 and epsp_min_idx is not None:
        right_peak = volley_peaks_idx[1]
        epsp_min = epsp_min_idx
        if epsp_min - right_peak >= 6:
            r2_values = []
            win_length = min((epsp_min + 1 - right_peak) // 2, 6) # set savgol window length
            pad = 7
            voltage_slope = savgol_filter(voltage[right_peak: epsp_min + pad], window_length=win_length, polyorder=1)
            time_slope = time[right_peak: epsp_min + pad]
            for i in range((len(voltage_slope) - pad)//4): # first fourth for slope start
                x = time_slope[i:i+7]
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
                epsp_slope_start = max_r2_i + right_peak
                epsp_slope_end = max_r2_i + 6 + right_peak
                verboses += f"epsp slope: start={time[epsp_slope_start]}, end={time[epsp_slope_end]}, slope={epsp_slope_value}\n"
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
        'stim_neg_idx': stim_neg_idx,
        'stim_pos_idx': stim_pos_idx,
        'volley_detected': volley_detected,
        'm_shape_confirmed': m_shape,
        'volley_region': (volley_start, volley_end),
        'volley_peaks_idx': volley_peaks_idx,
        'volley_trough_idx': volley_trough_idx if 'volley_trough_idx' in locals() else None,
        'epsp_detected': epsp_detected,
        'epsp_depth': epsp_depth,
        'epsp_region': (epsp_start, epsp_end),
        'epsp_min_idx': epsp_min_idx,
        'noise_level': noise_level,
        'chatter_region': (chatter_start, chatter_end),
        'baseline_region': (0, baseline_end),
        'standard_structure': stim_detected and volley_detected and m_shape and epsp_detected,
        'volley_slope_start': volley_slope_start,
        't_volley_slope_start': time[volley_slope_start],
        'volley_slope_end': volley_slope_end,
        'volley_slope_value': volley_slope_value,
        'epsp_slope_start': epsp_slope_start,
        't_EPSP_slope_start': time[epsp_slope_start],
        'epsp_slope_end': epsp_slope_end,
        'epsp_slope_value': epsp_slope_value
    }

    # Plotting if requested
    if plot:            
        plt.figure(figsize=(12, 9) if not multiplots else (6, 1))
        plt.plot(time, voltage, label='Voltage', color='black')
        
        # Plot baseline
        plt.axhline(y=baseline, color='gray', linestyle='--', label='Baseline')
        
        # Volley region and features
        if volley_start < len(time) and volley_end <= len(time):
            volley_start_time = time[volley_start]
            volley_end_time = time[min(volley_end - 1, len(time) - 1)]
            plt.axvspan(volley_start_time, volley_end_time, color='yellow', alpha=0.2, label='Volley Region')
            for idx in volley_peaks_idx:
                if idx < len(time):
                    plt.plot(time[idx], voltage[idx], 'go', label='Volley Peak' if 'Volley Peak' not in plt.gca().get_legend_handles_labels()[1] else "")
            idx = volley_trough_idx if 'volley_trough_idx' in locals() else None
            if idx is not None and idx < len(time):
                plt.plot(time[idx], voltage[idx], 'mo', label='Volley Trough' if 'Volley Trough' not in plt.gca().get_legend_handles_labels()[1] else "")
        
        # EPSP region and minimum
        if epsp_start is not None and epsp_end is not None and epsp_start < len(time) and epsp_end <= len(time):
            epsp_start_time = time[epsp_start]
            epsp_end_time = time[min(epsp_end - 1, len(time) - 1)]
            plt.axvspan(epsp_start_time, epsp_end_time, color='cyan', alpha=0.2, label='EPSP Region')
            if epsp_min_idx is not None and epsp_min_idx < len(time):
                plt.plot(time[epsp_min_idx], voltage[epsp_min_idx], 'ko', label='EPSP Min')
        
        # Chatter region
        if chatter_start < len(time) and chatter_end <= len(time):
            chatter_start_time = time[chatter_start]
            chatter_end_time = time[min(chatter_end - 1, len(time) - 1)]
            plt.axvspan(chatter_start_time, chatter_end_time, color='orange', alpha=0.2, label='Chatter Region')
        
        # Mark stimulation baseline crossings
        if stim_detected:
            plt.plot(time[stim_neg_idx], baseline, 'ro', label='Stim peaks time')
            plt.plot(time[stim_pos_idx], baseline, 'ro')
        
        # Plot volley slope
        if volley_slope_start is not None and volley_slope_end is not None:
            plt.plot(time[volley_slope_start:volley_slope_end+1], voltage[volley_slope_start:volley_slope_end+1], 'r-', linewidth=2, label='Volley Slope')
        
        # Plot EPSP slope
        if epsp_slope_start is not None and epsp_slope_end is not None:
            plt.plot(time[epsp_slope_start:epsp_slope_end+1], voltage[epsp_slope_start:epsp_slope_end+1], 'r-', linewidth=2, label='EPSP Slope')
        
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


# %% [markdown]
# # inmodule test and development

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

# %% [markdown]
# # evaluation

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

# %% [markdown]
# # find and plot the worst errors

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

# %%

# %%
