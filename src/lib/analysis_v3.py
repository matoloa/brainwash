# analysis_v3.py
# ---------------------------------------------------------------------------
# Production analysis layer — v3.
#
# Design goals vs. v2:
#   - find_timepoints()  replaces characterize_graph() + i2t():
#       * same sequential detection logic (stim → volley → EPSP → slopes)
#       * returns only the time values needed to populate one dft row
#       * no amplitude measurements, no region tuples, no index outputs
#       * all tuning knobs are explicit params with defaults (hookable later)
#   - find_events()      thin loop: find_i_stims → find_timepoints per stim
#   - measure_waveform() pure single-waveform measurement → dict of values
#   - build_dfoutput()   unified entry point: sweep-mode rows + stim-mode rows
#   - measureslope_vec() vectorised slope for sweep-mode fast path (unchanged)
#   - valid()            scalar guard (unchanged)
#
# No plotting, no __main__, no notebook cells — see analysis_evaluation.py.
# ---------------------------------------------------------------------------

import time
from typing import Optional

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter
from scipy.stats import ttest_ind_from_stats

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def valid(*args) -> bool:
    """Return True iff every argument is a non-NaN finite number."""
    return all(isinstance(x, (int, float)) and x is not None and not np.isnan(x) for x in args)


def measureslope_vec(df, t_start, t_end, name="EPSP", filter="voltage") -> pd.DataFrame:
    """
    Vectorised linear slope across all sweeps between t_start and t_end.

    Args:
        df:      DataFrame with columns 'sweep', 'time', and <filter>.
        t_start: Start time (inclusive).
        t_end:   End time (inclusive).
        name:    Label written into the 'type' column of the result.
        filter:  Voltage column name.

    Returns:
        DataFrame indexed by sweep with columns 'type', 'algorithm', 'value'.
    """
    df_filtered = df[(t_start <= df.time) & (df.time <= t_end)]
    dfpivot = df_filtered.pivot(index="sweep", columns="time", values=filter)
    coefs = np.polyfit(dfpivot.columns, dfpivot.T, deg=1).T
    dfslopes = pd.DataFrame(index=dfpivot.index)
    dfslopes["type"] = name + "_slope"
    dfslopes["algorithm"] = "linear"
    dfslopes["value"] = coefs[:, 0]
    return dfslopes


def ttest_df(d_group_ndf, norm=False, amp=False, slope=False) -> pd.DataFrame:
    """
    Paired t-test across two groups for amp/slope columns.

    Args:
        d_group_ndf: Dict mapping group name → (n, df) where df has mean/SEM columns.
        norm:        If True, test normalised columns.
        amp:         If True, include EPSP_amp comparison.
        slope:       If True, include EPSP_slope comparison.

    Returns:
        DataFrame with columns 'sweep' and one p-value column per requested test.
    """
    keys = sorted(d_group_ndf.keys())
    k1, k2 = keys[0], keys[1]
    n1, df1 = d_group_ndf[k1]
    n2, df2 = d_group_ndf[k2]

    sweeps = df1["sweep"].values
    out: dict = {"sweep": sweeps}
    cols = []

    if amp:
        if norm:
            cols.append(("EPSP_amp_norm_mean", "EPSP_amp_norm_SEM", "p_amp_norm"))
        else:
            cols.append(("EPSP_amp_mean", "EPSP_amp_SEM", "p_amp"))
    if slope:
        if norm:
            cols.append(("EPSP_slope_norm_mean", "EPSP_slope_norm_SEM", "p_slope_norm"))
        else:
            cols.append(("EPSP_slope_mean", "EPSP_slope_SEM", "p_slope"))

    for mean_col, sem_col, outname in cols:
        pvals = []
        for i in range(len(sweeps)):
            m1 = df1.loc[i, mean_col]
            s1 = df1.loc[i, sem_col] * np.sqrt(n1)
            m2 = df2.loc[i, mean_col]
            s2 = df2.loc[i, sem_col] * np.sqrt(n2)
            _, p = ttest_ind_from_stats(
                mean1=m1,
                std1=s1,
                nobs1=n1,
                mean2=m2,
                std2=s2,
                nobs2=n2,
                equal_var=False,
            )
            pvals.append(p)
        out[outname] = pvals

    return pd.DataFrame(out)


def addFilterSavgol(df, window_length: int = 9, poly_order: int = 3) -> pd.Series:
    """
    Compute a Savitzky-Golay smoothed column from df['voltage'] and return it.
    """
    wl_target = window_length if window_length % 2 == 1 else window_length + 1

    def _apply_savgol(x):
        n = len(x)
        if n <= poly_order:
            return x
        wl = min(wl_target, n if n % 2 == 1 else n - 1)
        if wl <= poly_order:
            return x
        return savgol_filter(x, window_length=wl, polyorder=poly_order)

    if "sweep" in df.columns:
        df["savgol"] = df.groupby("sweep")["voltage"].transform(_apply_savgol)
    else:
        df["savgol"] = _apply_savgol(df["voltage"])
    return df["savgol"]


def _scalar_measureslope(df_snippet, t_start, t_end, filter="voltage") -> float:
    """
    Scalar linear slope on a single-waveform snippet between t_start and t_end.
    Used internally by measure_waveform.
    """
    dftemp = df_snippet[(t_start <= df_snippet.time) & (df_snippet.time <= t_end)]
    if len(dftemp) < 2:
        return np.nan
    x = dftemp.time.values
    y = dftemp[filter].values
    coefs = np.polyfit(x, y, 1)
    return float(coefs[0])


# ---------------------------------------------------------------------------
# Stim detection
# ---------------------------------------------------------------------------


def find_i_stims(dfmean, threshold=0.1, min_time_difference=0.005, verbose=False) -> list:
    """
    Find indices of stimulation events in dfmean using the 'prim' column.

    Args:
        dfmean:              DataFrame with 'time' and 'prim' columns.
        threshold:           Fraction of prim max used as detection threshold.
        min_time_difference: Minimum gap (seconds) between distinct stim events.
        verbose:             Print detected indices if True.

    Returns:
        List of integer indices into dfmean.
    """
    prim_max_y = dfmean.prim.max()
    thresh = threshold * prim_max_y
    above = np.where(dfmean["prim"] > thresh)[0]
    if len(above) == 0:
        return []
    filtered = []
    max_index = above[0]
    for i in range(1, len(above)):
        cur = above[i]
        prev = above[i - 1]
        if dfmean["time"].iloc[cur] - dfmean["time"].iloc[prev] > min_time_difference:
            filtered.append(max_index)
            max_index = cur
        elif dfmean["prim"].iloc[cur] > dfmean["prim"].iloc[max_index]:
            max_index = cur
    filtered.append(max_index)
    if verbose:
        print(f"find_i_stims: {filtered}")
    return filtered


# ---------------------------------------------------------------------------
# Core timepoint detection
# ---------------------------------------------------------------------------


def find_timepoints(
    df_snippet,
    default_dict_t: dict,
    filter: str = "voltage",
    stim_amp: float = 0.005,
    volley_slope_n_points: int = 3,
    epsp_slope_n_points: int = 7,
    volley_slope_search_fraction: float = 0.5,
    epsp_slope_search_fraction: float = 0.25,
    verbose: bool = False,
) -> dict:
    """
    Detect measurement timepoints from a single-stim waveform snippet.

    Runs sequential detection: stim artefact → volley M-shape → EPSP trough
    → volley slope window → EPSP slope window.  Returns only the time values
    needed to populate one dft row; no amplitude measurements or region
    metadata are included.

    Args:
        df_snippet:                   DataFrame slice around one stim with
                                      'time' and <filter> columns.
        default_dict_t:               Dict carrying width defaults
                                      ('t_EPSP_amp_width',
                                       't_volley_slope_width',
                                       't_EPSP_slope_width').
        filter:                       Voltage column name; must match the
                                      column displayed in axe so that
                                      amp_zero aligns with the plotted
                                      waveform.
        stim_amp:                     Minimum artefact amplitude for stim
                                      detection (V).
        volley_slope_n_points:        Number of consecutive samples in the
                                      volley slope fitting window.
        epsp_slope_n_points:          Number of consecutive samples in the
                                      EPSP slope fitting window.
        volley_slope_search_fraction: Fraction of the left-peak→trough region
                                      to scan for the steepest volley slope
                                      window start.
        epsp_slope_search_fraction:   Fraction of the right-peak→EPSP-min
                                      region to scan for the best-R² EPSP
                                      slope window start.
        verbose:                      Print detection progress if True.

    Returns:
        Dict with keys:
            stim, t_stim,
            t_volley_amp,        t_volley_amp_method,
            t_volley_slope_start, t_volley_slope_end, t_volley_slope_method,
            t_EPSP_amp,          t_EPSP_amp_method,
            t_EPSP_slope_start,  t_EPSP_slope_end,   t_EPSP_slope_method,
            amp_zero,
            volley_detected, epsp_detected.
        All values are scalars (float or bool); no arrays or index tuples.
    """
    voltage = df_snippet[filter].values
    times = df_snippet["time"].values
    n = len(voltage)
    dt = times[1] - times[0]

    vn = volley_slope_n_points
    en = epsp_slope_n_points

    log = []

    def _log(msg):
        if verbose:
            log.append(msg)

    # ------------------------------------------------------------------
    # 1. Stim artefact
    # ------------------------------------------------------------------
    stim_prom = stim_amp
    neg_peaks = np.array([])
    pos_peaks = np.array([])
    while (len(pos_peaks) == 0 or len(neg_peaks) == 0) and stim_prom > 1e-6:
        neg_peaks, _ = find_peaks(-voltage, prominence=stim_prom)
        pos_peaks, _ = find_peaks(voltage, prominence=stim_prom)
        stim_prom /= 2

    stim_detected = False
    i_stim_neg = None
    i_stim_pos = None

    if neg_peaks.size > 0 and pos_peaks.size > 0:
        first_neg = neg_peaks[0]
        next_pos_cands = pos_peaks[pos_peaks > first_neg]
        if next_pos_cands.size > 0:
            next_pos = next_pos_cands[0]
            if (times[next_pos] - times[first_neg]) < 0.0004:  # within 0.4 ms
                i_stim_neg = int(first_neg) - 1
                i_stim_pos = int(next_pos) + 1
                stim_detected = bool(-voltage[first_neg] > stim_amp)
                _log(f"stim detected: i_stim_neg={i_stim_neg}, i_stim_pos={i_stim_pos}")

    if not stim_detected:
        _log("stim: not detected, using index-based fallbacks")

    # t_stim: time of the negative artefact peak, or time[0] as fallback
    t_stim = float(times[int(i_stim_neg)]) if stim_detected and i_stim_neg is not None else float(times[0])

    # Baseline (pre-stim mean)
    baseline_start_idx = np.abs(times - (t_stim - 0.002)).argmin()
    baseline_end_idx = np.abs(times - (t_stim - 0.001)).argmin()
    if baseline_end_idx <= baseline_start_idx:
        baseline_end_idx = baseline_start_idx + 1
    baseline = np.mean(voltage[baseline_start_idx:baseline_end_idx])

    # amp_zero placeholder (pre-stim baseline in volts)
    amp_zero = float(baseline)

    # ------------------------------------------------------------------
    # 2. Volley (M-shape)
    # ------------------------------------------------------------------
    volley_detected = False
    i_volley_trough = None
    i_volley_left = None
    i_volley_right = None
    i_veb = None  # end-of-volley boundary for EPSP search

    volley_start = (int(i_stim_neg) + int(0.0005 / dt)) if stim_detected and i_stim_neg is not None else int(0.001 / dt)
    volley_end = min(volley_start + int(0.005 / dt), n)
    volley_region = voltage[volley_start:volley_end]

    v_prom = 0.001
    v_peaks = np.array([])
    while len(v_peaks) < 2 and v_prom > 1e-6:
        v_peaks, _ = find_peaks(volley_region, prominence=v_prom)
        v_prom /= 2
    v_troughs, _ = find_peaks(-volley_region, prominence=v_prom)

    if len(v_peaks) >= 2 and len(v_troughs) >= 1:
        # Scan from the rightmost pair leftward to find M-shape
        for k in range(len(v_peaks) - 1):
            p1 = v_peaks[len(v_peaks) - 2 - k]
            p2 = v_peaks[len(v_peaks) - 1 - k]
            between = [t for t in v_troughs if p1 < t < p2]
            if between and volley_region[p2] <= volley_region[p1]:
                volley_detected = True
                i_volley_left = p1 + volley_start
                i_volley_right = p2 + volley_start
                i_volley_trough = between[0] + volley_start
                i_veb = i_volley_right
                _log(f"volley M-shape: left={i_volley_left}, trough={i_volley_trough}, right={i_volley_right}")
                break

    # ------------------------------------------------------------------
    # 3. EPSP trough
    # ------------------------------------------------------------------
    epsp_detected = False
    i_epsp_min = None

    if volley_detected and i_veb is not None:
        epsp_start = int(i_veb)
    elif i_stim_pos is not None:
        epsp_start = int(i_stim_pos) + 2
    else:
        epsp_start = int(volley_end)

    epsp_end = min(epsp_start + int(0.02 / dt), n - 1)
    epsp_region = voltage[epsp_start:epsp_end]

    if len(epsp_region) > 0:
        e_prom = 0.01
        e_peaks = np.array([])
        while len(e_peaks) < 1 and e_prom > 1e-6:
            e_peaks, _ = find_peaks(-epsp_region, prominence=e_prom)
            e_prom /= 2
        if len(e_peaks):
            i_epsp_min = int(e_peaks[0]) + epsp_start
            epsp_depth = baseline - voltage[i_epsp_min]
            epsp_detected = bool(epsp_depth > 0.0001)
            _log(f"EPSP min: i={i_epsp_min}, t={times[i_epsp_min]:.5f}, depth={epsp_depth:.5f}")
        else:
            _log("EPSP: no trough found")

    # ------------------------------------------------------------------
    # 4. Volley slope window (steepest vn-point interval)
    # ------------------------------------------------------------------
    t_volley_slope_start = None
    t_volley_slope_method = "default"

    if volley_detected and i_volley_trough is not None and i_volley_left is not None:
        left = int(i_volley_left)
        trough = int(i_volley_trough)
        region_len = trough - left
        if region_len >= vn:
            search_len = max(1, int(region_len * volley_slope_search_fraction))
            # Savgol smooth with window = vn (odd; shrink if region too small)
            savgol_win = vn if vn % 2 == 1 else vn - 1
            savgol_win = max(savgol_win, 3)
            pad = vn
            raw = voltage[left : trough + pad]
            smoothed = np.asarray(
                savgol_filter(raw, window_length=min(savgol_win, len(raw)), polyorder=0),
                dtype=float,
            )
            t_raw = np.asarray(times[left : trough + pad], dtype=float)
            slopes = []
            for i in range(min(search_len, len(smoothed) - vn + 1)):
                x = t_raw[i : i + vn]
                y = smoothed[i : i + vn]
                coefs = np.polyfit(x, y, 1)
                slopes.append((i, float(coefs[0])))
            if slopes:
                best_i, _ = min(slopes, key=lambda s: s[1])
                t_volley_slope_start = float(times[best_i + left])
                t_volley_slope_method = "auto detect"
                _log(f"volley slope start: t={t_volley_slope_start:.5f}")
        else:
            _log(f"volley slope: region too small ({region_len} < {vn})")

    if t_volley_slope_start is None:
        t_volley_slope_start = t_stim + 0.001  # 1 ms after stim
        _log(f"volley slope: using default t={t_volley_slope_start:.5f}")

    t_volley_slope_end = round(t_volley_slope_start + default_dict_t.get("t_volley_slope_width", 0.0003), 6)

    # ------------------------------------------------------------------
    # 5. EPSP slope window (best-R² en-point interval)
    # ------------------------------------------------------------------
    t_EPSP_slope_start = None
    t_EPSP_slope_method = "default"

    if epsp_detected and i_volley_right is not None and i_epsp_min is not None:
        right = int(i_volley_right)
        epsp_min = int(i_epsp_min)
        region_len = epsp_min - right
        if region_len >= en:
            search_len = max(1, int(region_len * epsp_slope_search_fraction))
            savgol_win = en if en % 2 == 1 else en - 1
            savgol_win = max(savgol_win, 3)
            pad = en
            raw = voltage[right : epsp_min + pad]
            smoothed = np.asarray(
                savgol_filter(raw, window_length=min(savgol_win, len(raw)), polyorder=1),
                dtype=float,
            )
            t_raw = np.asarray(times[right : epsp_min + pad], dtype=float)
            r2_values = []
            for i in range(min(search_len, len(smoothed) - en + 1)):
                x = t_raw[i : i + en]
                y = smoothed[i : i + en]
                coefs = np.polyfit(x, y, 1)
                y_pred = np.polyval(coefs, x)
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r2 = 1.0 - ss_res / ss_tot if ss_tot != 0 else 0.0
                r2_values.append((i, r2))
            if r2_values:
                best_i, _ = max(r2_values, key=lambda r: r[1])
                t_EPSP_slope_start = float(times[best_i + right])
                t_EPSP_slope_method = "auto detect"
                _log(f"EPSP slope start: t={t_EPSP_slope_start:.5f}")
        else:
            _log(f"EPSP slope: region too small ({region_len} < {en})")

    if t_EPSP_slope_start is None:
        t_EPSP_slope_start = t_stim + 0.002  # 2 ms after stim
        _log(f"EPSP slope: using default t={t_EPSP_slope_start:.5f}")

    t_EPSP_slope_end = round(t_EPSP_slope_start + default_dict_t.get("t_EPSP_slope_width", 0.0007), 6)

    # ------------------------------------------------------------------
    # 6. Amp timepoints (trough times, or fixed offsets as fallback)
    # ------------------------------------------------------------------
    if volley_detected and i_volley_trough is not None:
        t_volley_amp = float(times[i_volley_trough])
        t_volley_amp_method = "auto detect"
    else:
        t_volley_amp = t_stim + 0.0007
        t_volley_amp_method = "default"

    if epsp_detected and i_epsp_min is not None:
        t_EPSP_amp = float(times[i_epsp_min])
        t_EPSP_amp_method = "auto detect"
    else:
        t_EPSP_amp = t_stim + 0.005
        t_EPSP_amp_method = "default"

    if verbose:
        print("\n".join(log))

    return {
        # identity
        "t_stim": t_stim,
        "amp_zero": amp_zero,
        # volley amplitude
        "t_volley_amp": t_volley_amp,
        "t_volley_amp_method": t_volley_amp_method,
        # volley slope
        "t_volley_slope_start": t_volley_slope_start,
        "t_volley_slope_end": t_volley_slope_end,
        "t_volley_slope_method": t_volley_slope_method,
        # EPSP amplitude
        "t_EPSP_amp": t_EPSP_amp,
        "t_EPSP_amp_method": t_EPSP_amp_method,
        # EPSP slope
        "t_EPSP_slope_start": t_EPSP_slope_start,
        "t_EPSP_slope_end": t_EPSP_slope_end,
        "t_EPSP_slope_method": t_EPSP_slope_method,
        # detection flags (retained for callers that want to branch on them)
        "volley_detected": volley_detected,
        "epsp_detected": epsp_detected,
    }


# ---------------------------------------------------------------------------
# Event discovery: stim loop → dft
# ---------------------------------------------------------------------------


def find_events(
    dfmean,
    default_dict_t: dict,
    filter: str = "voltage",
    i_stims: Optional[list] = None,
    stim_amp: float = 0.005,
    precision: Optional[int] = None,
    volley_slope_n_points: int = 3,
    epsp_slope_n_points: int = 7,
    volley_slope_search_fraction: float = 0.5,
    epsp_slope_search_fraction: float = 0.25,
    verbose: bool = False,
) -> pd.DataFrame:
    """
    Detect all stims in dfmean and return a dft DataFrame (one row per stim).

    Args:
        dfmean:                       DataFrame with 'time', <filter>, 'prim'.
        default_dict_t:               Default timepoint dict; width keys are
                                      forwarded to find_timepoints.
        filter:                       Voltage column name; forwarded to
                                      find_timepoints so amp_zero is computed
                                      from the same column shown in axe.
        i_stims:                      Pre-computed stim indices; auto-detected
                                      from 'prim' if None.
        stim_amp:                     Forwarded to find_timepoints.
        precision:                    Decimal places for rounding; inferred
                                      from time resolution if None.
        volley_slope_n_points:        Forwarded to find_timepoints.
        epsp_slope_n_points:          Forwarded to find_timepoints.
        volley_slope_search_fraction: Forwarded to find_timepoints.
        epsp_slope_search_fraction:   Forwarded to find_timepoints.
        verbose:                      Forwarded to find_timepoints.

    Note:
        find_i_stims still uses 'prim' for stim detection (unaffected by
        filter).  Only the amp_zero baseline computation inside
        find_timepoints uses <filter>.

    Returns:
        DataFrame with one row per stim, columns matching default_dict_t plus
        all keys returned by find_timepoints.  Empty DataFrame if no stims
        found.
    """
    if i_stims is None:
        i_stims = find_i_stims(dfmean=dfmean, verbose=verbose)
    if not i_stims:
        print("find_events: no stims found, returning empty DataFrame.")
        return pd.DataFrame()

    time_values = dfmean["time"].values
    if precision is None:
        raw_delta = str(float(time_values[1]) - float(time_values[0]))
        precision = len(raw_delta.split(".")[1]) if "." in raw_delta else 6
    precision = int(precision)

    margin_before = 5
    min_interval_samples = 200  # 20 ms at 10 kHz — avoids overlap in 50 Hz trains

    rows = []
    for stim_nr, i_stim in enumerate(i_stims, start=1):
        # Slice a window around this stim
        start = max(i_stim - margin_before, 0)
        if stim_nr < len(i_stims):
            stop = min(i_stim + min_interval_samples, i_stims[stim_nr])
        else:
            stop = i_stim + min_interval_samples
        df_snippet = dfmean.iloc[start:stop].reset_index(drop=True)

        tp = find_timepoints(
            df_snippet=df_snippet,
            default_dict_t=default_dict_t,
            filter=filter,
            stim_amp=stim_amp,
            volley_slope_n_points=volley_slope_n_points,
            epsp_slope_n_points=epsp_slope_n_points,
            volley_slope_search_fraction=volley_slope_search_fraction,
            epsp_slope_search_fraction=epsp_slope_search_fraction,
            verbose=verbose,
        )

        # Round all float timepoints to match recording resolution
        for key, val in tp.items():
            if isinstance(val, float) and key.startswith("t_"):
                tp[key] = round(val, precision)

        row = default_dict_t.copy()
        row["stim"] = stim_nr
        row.update(tp)
        rows.append(row)

        if verbose:
            print(
                f"find_events: stim {stim_nr} → t_stim={tp['t_stim']}, "
                f"volley={'auto' if tp['volley_detected'] else 'default'}, "
                f"epsp={'auto' if tp['epsp_detected'] else 'default'}"
            )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Single-waveform measurement
# ---------------------------------------------------------------------------


def measure_waveform(df_snippet, dict_t: dict, filter: str = "voltage") -> dict:
    """
    Measure all output values from a single waveform snippet.

    No sweep or stim awareness — pure signal measurement at the timepoints
    defined in dict_t.  Slope is computed with the scalar path (_scalar_measureslope)
    since the snippet is a single waveform.

    Args:
        df_snippet: DataFrame with 'time' and <filter> columns (one waveform).
        dict_t:     Timepoint dict (one dft row as a dict).
        filter:     Voltage column name.

    Returns:
        Dict with keys: EPSP_amp, EPSP_slope, volley_amp, volley_slope
        (and their _norm variants where a normalization range is available).
        Missing or invalid timepoints produce np.nan for that measurement.
    """
    result = {}

    t_stim = dict_t.get("t_stim", 0.0)
    _pre_stim = df_snippet[(df_snippet["time"] >= t_stim - 0.002) & (df_snippet["time"] < t_stim - 0.001)]
    amp_zero = _pre_stim[filter].mean()
    if pd.isna(amp_zero):
        amp_zero = dict_t.get("amp_zero", 0.0)
    norm_from = dict_t.get("norm_output_from", None)
    norm_to = dict_t.get("norm_output_to", None)

    # -- EPSP amplitude --
    t_EPSP_amp = dict_t.get("t_EPSP_amp", np.nan)
    t_EPSP_w = dict_t.get("t_EPSP_amp_width", 2 * dict_t.get("t_EPSP_amp_halfwidth", 0))
    if valid(t_EPSP_amp):
        if t_EPSP_w == 0:
            row = df_snippet[df_snippet["time"] == t_EPSP_amp]
            val = -(row[filter].iloc[0] - amp_zero) if not row.empty else np.nan
        else:
            mask = (df_snippet["time"] >= t_EPSP_amp - t_EPSP_w / 2) & (df_snippet["time"] <= t_EPSP_amp + t_EPSP_w / 2)
            mean_v = df_snippet.loc[mask, filter].mean()
            val = -(mean_v - amp_zero) if not np.isnan(mean_v) else np.nan
        result["EPSP_amp"] = val
    else:
        result["EPSP_amp"] = np.nan

    # -- EPSP slope --
    t_EPSP_s = dict_t.get("t_EPSP_slope_start", np.nan)
    t_EPSP_e = dict_t.get("t_EPSP_slope_end", np.nan)
    if valid(t_EPSP_s, t_EPSP_e) and t_EPSP_s < t_EPSP_e:
        slope = _scalar_measureslope(df_snippet, t_EPSP_s, t_EPSP_e, filter)
        result["EPSP_slope"] = -slope if not np.isnan(slope) else np.nan
    else:
        result["EPSP_slope"] = np.nan

    # -- Volley amplitude --
    t_volley_amp = dict_t.get("t_volley_amp", np.nan)
    t_volley_w = dict_t.get("t_volley_amp_width", 2 * dict_t.get("t_volley_amp_halfwidth", 0))
    if valid(t_volley_amp):
        if t_volley_w == 0:
            row = df_snippet[df_snippet["time"] == t_volley_amp]
            val = -(row[filter].iloc[0] - amp_zero) if not row.empty else np.nan
        else:
            mask = (df_snippet["time"] >= t_volley_amp - t_volley_w / 2) & (df_snippet["time"] <= t_volley_amp + t_volley_w / 2)
            mean_v = df_snippet.loc[mask, filter].mean()
            val = -(mean_v - amp_zero) if not np.isnan(mean_v) else np.nan
        result["volley_amp"] = val
    else:
        result["volley_amp"] = np.nan

    # -- Volley slope --
    t_volley_s = dict_t.get("t_volley_slope_start", np.nan)
    t_volley_e = dict_t.get("t_volley_slope_end", np.nan)
    if valid(t_volley_s, t_volley_e) and t_volley_s < t_volley_e:
        slope = _scalar_measureslope(df_snippet, t_volley_s, t_volley_e, filter)
        result["volley_slope"] = -slope if not np.isnan(slope) else np.nan
    else:
        result["volley_slope"] = np.nan

    return result


def _normalize_column(series: pd.Series, norm_from, norm_to) -> pd.Series:
    """
    Normalize a Series to percentage of the mean of rows norm_from..norm_to
    (index-based, inclusive).  Returns a Series of NaN if the baseline mean
    is zero or the range is invalid.
    """
    if norm_from is None or norm_to is None or pd.isna(norm_from) or pd.isna(norm_to):
        return pd.Series(np.nan, index=series.index)
    norm_from, norm_to = int(norm_from), int(norm_to)
    selected = series.iloc[norm_from : norm_to + 1]
    norm_mean = selected.mean()
    if norm_mean == 0 or np.isnan(norm_mean):
        return pd.Series(np.nan, index=series.index)
    return series / (norm_mean / 100)


# ---------------------------------------------------------------------------
# Unified output computation
# ---------------------------------------------------------------------------


# Window before t_stim used to compute per-sweep amp_zero (seconds)
_AMP_ZERO_WINDOW = 0.002  # 2 ms pre-stim


def _measure_amp_at_time_per_sweep(
    dffilter: pd.DataFrame,
    t_target: float,
    amp_zero_per_sweep: pd.Series,
    filter: str,
) -> pd.Series:
    """
    For each sweep, find the single sample nearest to t_target and return
    -(voltage - amp_zero) (V, positive = depolarisation).

    Uses nearest-sample lookup instead of exact equality so that sources
    with floating-point time accumulation (ATF, IBW) never produce an
    empty selection.  Returns a Series aligned to the sweep order in
    dffilter.
    """
    sweeps = dffilter["sweep"].unique()
    idx = (dffilter["time"] - t_target).abs().groupby(dffilter["sweep"]).idxmin()
    idx = idx.loc[sweeps]
    v = dffilter.loc[idx, filter].values
    az = amp_zero_per_sweep.loc[sweeps].values
    values = -(v - az)
    return pd.Series(values, index=range(len(sweeps)))


def _compute_amp_zero_per_sweep(dffilter, t_stim: float, filter: str) -> pd.Series:
    """
    Compute per-sweep amp_zero as the mean of <filter> in the window
    [-0.002, -0.001] relative to t_stim for each sweep.

    Returns a Series indexed by sweep value.  Falls back to 0.0 for any sweep
    where the pre-stim window contains no samples.
    """
    t_start = t_stim - 0.002
    t_end = t_stim - 0.001
    pre_stim = dffilter[(dffilter["time"] >= t_start) & (dffilter["time"] < t_end)]
    per_sweep = pre_stim.groupby("sweep")[filter].mean()
    # Fill missing sweeps with 0.0 so downstream arithmetic never sees NaN
    all_sweeps = pd.Series(dffilter["sweep"].unique())
    result = per_sweep.reindex(all_sweeps.values).fillna(0.0)
    result.index = all_sweeps.values
    return result


def build_dfoutput(
    dffilter,
    dfmean,
    dft: pd.DataFrame,
    filter: str = "voltage",
    quick: bool = False,
) -> pd.DataFrame:
    """
    Compute the unified output DataFrame for one recording.

    Always produces sweep-mode rows (one per sweep × stim).
    Also produces stim-mode rows (sweep=NaN, one per stim) when len(dft) > 1,
    by measuring dfmean sliced around each stim window.

    Args:
        dffilter: Filtered multi-sweep DataFrame with 'sweep', 'time', <filter>.
        dfmean:   Single mean waveform DataFrame with 'time', <filter>.
        dft:      Timepoints DataFrame (one row per stim).
        filter:   Voltage column name.
        quick:    If True, skip halfwidth averaging (single-point amp only).

    Returns:
        DataFrame with columns: stim, sweep, EPSP_amp, EPSP_amp_norm,
        EPSP_slope, EPSP_slope_norm, volley_amp, volley_slope.
        Stim-mode rows have sweep=NaN.
    """
    t0 = time.time()
    print(f"build_dfoutput: entered, dffilter.shape={dffilter.shape}, nsweeps={dffilter['sweep'].nunique()}, nstims={len(dft)}")

    all_rows = []

    # ------------------------------------------------------------------
    # Sweep-mode rows: iterate stims, then use measureslope_vec fast path
    # ------------------------------------------------------------------
    for _, t_row in dft.iterrows():
        dict_t = t_row.to_dict()
        stim_nr = dict_t["stim"]
        t_stim = float(dict_t.get("t_stim", 0.0))
        norm_from = dict_t.get("norm_output_from")  # noqa: F841 — used in _normalize_column calls below
        norm_to = dict_t.get("norm_output_to")  # noqa: F841 — used in _normalize_column calls below

        sweeps = dffilter["sweep"].unique()
        dfblock = pd.DataFrame({"sweep": sweeps, "stim": stim_nr})

        # Per-sweep amp_zero: mean of dffilter[filter] in the [-0.002, -0.001] window before t_stim.
        # Indexed by sweep value in the same order as dfblock["sweep"].
        amp_zero_per_sweep = _compute_amp_zero_per_sweep(dffilter, t_stim, filter)

        # EPSP_amp
        t_EPSP_amp = dict_t.get("t_EPSP_amp", np.nan)
        t_EPSP_w = dict_t.get("t_EPSP_amp_width", 2 * dict_t.get("t_EPSP_amp_halfwidth", 0))
        if valid(t_EPSP_amp):
            t_EPSP_amp_f = float(t_EPSP_amp)
            if t_EPSP_w == 0 or quick:
                dfblock["EPSP_amp"] = _measure_amp_at_time_per_sweep(dffilter, t_EPSP_amp_f, amp_zero_per_sweep, filter).values
            else:
                half = float(t_EPSP_w) / 2
                amp_by_sweep = dffilter.groupby("sweep").apply(
                    lambda s: (
                        -(
                            s.loc[
                                (s["time"] >= t_EPSP_amp_f - half) & (s["time"] <= t_EPSP_amp_f + half),
                                filter,
                            ].mean()
                            - amp_zero_per_sweep.get(s.name, 0.0)
                        )
                    )
                )
                dfblock["EPSP_amp"] = pd.Series(amp_by_sweep.values, index=dfblock.index)
            dfblock["EPSP_amp_norm"] = _normalize_column(pd.Series(dfblock["EPSP_amp"].values, dtype=float), norm_from, norm_to).values
        else:
            dfblock["EPSP_amp"] = np.nan
            dfblock["EPSP_amp_norm"] = np.nan

        # EPSP_slope (vectorised fast path)
        t_EPSP_s = dict_t.get("t_EPSP_slope_start", np.nan)
        t_EPSP_e = dict_t.get("t_EPSP_slope_end", np.nan)
        if valid(t_EPSP_s, t_EPSP_e) and t_EPSP_s < t_EPSP_e:
            df_slopes = measureslope_vec(dffilter, t_EPSP_s, t_EPSP_e, filter=filter)
            dfblock["EPSP_slope"] = -df_slopes["value"].values  # type: ignore[operator]
            dfblock["EPSP_slope_norm"] = _normalize_column(pd.Series(dfblock["EPSP_slope"].values, dtype=float), norm_from, norm_to).values
        else:
            dfblock["EPSP_slope"] = np.nan
            dfblock["EPSP_slope_norm"] = np.nan

        # Volley_amp
        t_volley_amp = dict_t.get("t_volley_amp", np.nan)
        t_volley_w = dict_t.get("t_volley_amp_width", 2 * dict_t.get("t_volley_amp_halfwidth", 0))
        if valid(t_volley_amp):
            t_volley_amp_f = float(t_volley_amp)
            if t_volley_w == 0 or quick:
                dfblock["volley_amp"] = _measure_amp_at_time_per_sweep(dffilter, t_volley_amp_f, amp_zero_per_sweep, filter).values
            else:
                half = float(t_volley_w) / 2
                volley_by_sweep = dffilter.groupby("sweep").apply(
                    lambda s: (
                        -(
                            s.loc[
                                (s["time"] >= t_volley_amp_f - half) & (s["time"] <= t_volley_amp_f + half),
                                filter,
                            ].mean()
                            - amp_zero_per_sweep.get(s.name, 0.0)
                        )
                    )
                )
                dfblock["volley_amp"] = pd.Series(volley_by_sweep.values, index=dfblock.index)
        else:
            dfblock["volley_amp"] = np.nan

        # Volley_slope (vectorised fast path)
        t_volley_s = dict_t.get("t_volley_slope_start", np.nan)
        t_volley_e = dict_t.get("t_volley_slope_end", np.nan)
        if valid(t_volley_s, t_volley_e) and t_volley_s < t_volley_e:
            df_slopes = measureslope_vec(dffilter, t_volley_s, t_volley_e, filter=filter)
            dfblock["volley_slope"] = -df_slopes["value"].values  # type: ignore[operator]
        else:
            dfblock["volley_slope"] = np.nan

        all_rows.append(dfblock)
        print(f"build_dfoutput: stim {stim_nr} sweep-mode done ({round((time.time() - t0) * 1000)}ms)")

    # ------------------------------------------------------------------
    # Stim-mode rows: measure dfmean sliced around each stim window
    # (only when there are multiple stims)
    # ------------------------------------------------------------------
    if len(dft) > 1:
        stim_rows = []
        for _, t_row in dft.iterrows():
            dict_t = t_row.to_dict()
            stim_nr = dict_t["stim"]
            t_stim = dict_t.get("t_stim", np.nan)

            # Window: from just before stim to just after EPSP region
            # Use t_EPSP_slope_end as a reasonable right boundary, with fallback
            t_win_start = t_stim - 0.002
            t_win_end = dict_t.get("t_EPSP_amp", t_stim + 0.01) + dict_t.get("t_EPSP_amp_width", 2 * dict_t.get("t_EPSP_amp_halfwidth", 0.001))
            snippet = dfmean[(dfmean["time"] >= t_win_start) & (dfmean["time"] <= t_win_end)].copy().reset_index(drop=True)

            measured = measure_waveform(snippet, dict_t, filter=filter)
            stim_row = {"stim": stim_nr, "sweep": np.nan}
            stim_row.update(measured)
            # _norm variants are not meaningful for single stim-mean rows
            stim_row["EPSP_amp_norm"] = np.nan
            stim_row["EPSP_slope_norm"] = np.nan
            stim_rows.append(stim_row)

        all_rows.append(pd.DataFrame(stim_rows))
        print(f"build_dfoutput: stim-mode rows done ({round((time.time() - t0) * 1000)}ms)")

    # ------------------------------------------------------------------
    # Assemble and enforce column order
    # ------------------------------------------------------------------
    dfoutput: pd.DataFrame = pd.concat(all_rows, ignore_index=True)  # type: ignore[assignment, arg-type]
    col_order = [
        "stim",
        "sweep",
        "EPSP_amp",
        "EPSP_amp_norm",
        "EPSP_slope",
        "EPSP_slope_norm",
        "volley_amp",
        "volley_slope",
    ]
    for col in col_order:
        if col not in dfoutput.columns:
            dfoutput[col] = np.nan
    dfoutput = dfoutput[col_order]  # type: ignore[assignment]

    print(f"build_dfoutput: done {round((time.time() - t0) * 1000)}ms, shape={dfoutput.shape}")
    return dfoutput


# ---------------------------------------------------------------------------
# Binned-train output
# ---------------------------------------------------------------------------


def build_dfbinstimoutput(
    dfbin,
    dft: pd.DataFrame,
    filter: str = "voltage",
) -> pd.DataFrame:
    """
    Compute output for a binned multi-stim recording.

    Outer loop: bins (dfbin.groupby("sweep"), where each group is one bin's
    mean waveform).  Inner loop: stims (dft rows).  For each (bin, stim) pair
    the bin waveform is sliced around t_stim and passed to measure_waveform.

    Args:
        dfbin:  Binned DataFrame with 'sweep' (bin index), 'time', <filter>.
        dft:    Timepoints DataFrame (one row per stim).
        filter: Voltage column name.

    Returns:
        DataFrame with columns: bin, stim, EPSP_amp, EPSP_slope,
        volley_amp, volley_slope (one row per bin × stim).
        _norm variants are not included here; callers may add them.
    """
    rows = []
    for bin_nr, bin_df in dfbin.groupby("sweep"):
        bin_df = bin_df.reset_index(drop=True)
        for _, t_row in dft.iterrows():
            dict_t = t_row.to_dict()
            stim_nr = dict_t["stim"]
            t_stim = dict_t.get("t_stim", np.nan)

            t_win_start = t_stim - 0.002
            t_win_end = dict_t.get("t_EPSP_amp", t_stim + 0.01) + dict_t.get("t_EPSP_amp_width", 2 * dict_t.get("t_EPSP_amp_halfwidth", 0.001))
            snippet = bin_df[(bin_df["time"] >= t_win_start) & (bin_df["time"] <= t_win_end)].copy().reset_index(drop=True)

            measured = measure_waveform(snippet, dict_t, filter=filter)
            row = {"bin": bin_nr, "stim": stim_nr}
            row.update(measured)
            rows.append(row)

    if not rows:
        return pd.DataFrame(
            columns=[
                "bin",
                "stim",
                "EPSP_amp",
                "EPSP_slope",
                "volley_amp",
                "volley_slope",
            ]
        )
    dfout: pd.DataFrame = pd.DataFrame(rows)
    col_order = ["bin", "stim", "EPSP_amp", "EPSP_slope", "volley_amp", "volley_slope"]
    for col in col_order:
        if col not in dfout.columns:
            dfout[col] = np.nan
    return dfout[col_order]  # type: ignore[return-value]
