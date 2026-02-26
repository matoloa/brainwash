import math
import os
import time
from pathlib import Path

import igor2 as igor
import numpy as np
import pandas as pd
import pyabf
from joblib import Parallel, delayed
from tqdm import tqdm

verbose = True


def build_dfmean(dfdata, rollingwidth=3):
    print("build_dfmean")
    dfmean = (
        pd.pivot_table(
            dfdata, values="voltage_raw", index="sweep", columns="time", aggfunc="mean"
        )
        .mean()
        .to_frame(name="voltage")
    )
    dfmean["prim"] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
    dfmean["bis"] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()
    dfmean.reset_index(inplace=True)
    i_stim = first_stim_index(dfmean)
    baseline_mean = dfmean.iloc[i_stim - 20 : i_stim - 10][
        "voltage"
    ].mean()  # Adjusted for potential NaNs
    dfmean["voltage"] = dfmean["voltage"] - baseline_mean
    return dfmean, i_stim


def zeroSweeps(dfdata, i_stim=None, dfmean=None):
    # returns dfdata with sweeps zeroed to the mean of the 20th to 10th column before i_stim
    if i_stim is None:
        if dfmean is None:
            print("zeroSweeps: calling dfmean to get i_stim.")
            _, i_stim = build_dfmean(dfdata)
        else:
            i_stim = first_stim_index(dfmean)
    print(f"i_stim: {i_stim}, df_data: {dfdata}")
    df_zeroed = dfdata.copy()  # Copy dfdata to avoid modifying the original DataFrame
    # Check for duplicates based on 'sweep' and 'time'
    duplicates = df_zeroed.duplicated(subset=["sweep", "time"], keep=False)
    if duplicates.any():
        print("Warning: Duplicates found before zeroing.")
        print(df_zeroed[duplicates])
        df_zeroed = (
            df_zeroed.groupby(["sweep", "time"])
            .agg({"voltage_raw": "mean"})
            .reset_index()
        )
        print("Duplicates removed.")
        print(df_zeroed)

    dfpivot = df_zeroed.pivot(
        index="sweep", columns="time", values="voltage_raw"
    )  # Reshape df_zeroed to have one row per 'sweep' and one column per 'time'
    ser_mean = dfpivot.iloc[
        :, i_stim - 20 : i_stim - 10
    ].mean(
        axis=1
    )  # Calculate the mean of 'voltage_raw' values from the 20th to the 10th column before i_stim for each 'sweep'
    dfpivot = dfpivot.subtract(
        ser_mean, axis="rows"
    )  # Subtract the calculated means from dfpivot

    # handle the reassignment to 'voltage' to ensure length matches
    df_zeroed = df_zeroed.drop(columns=["voltage_raw"])
    df_stacked = dfpivot.stack().reset_index(name="voltage")
    # Merge back with df_zeroed to ensure correct length and alignment
    df_zeroed = df_zeroed.merge(df_stacked, on=["sweep", "time"], how="left")

    print(f"zeroSweeps: {df_zeroed}")
    return df_zeroed


def first_stim_index(dfmean, threshold_factor=0.75, min_time_difference=0.005):
    # returns the index of the first peak in the prim column of dfmean
    y_max_stim = dfmean.prim.max()
    threshold = y_max_stim * threshold_factor
    above_threshold_indices = np.where(dfmean["prim"] > threshold)[0]
    if above_threshold_indices.size == 0:
        return None
    max_index = above_threshold_indices[0]
    for i in range(1, len(above_threshold_indices)):
        current_index = above_threshold_indices[i]
        previous_index = above_threshold_indices[i - 1]
        if (
            dfmean["time"][current_index] - dfmean["time"][previous_index]
            > min_time_difference
        ):
            break
        if dfmean["prim"][current_index] > dfmean["prim"][max_index]:
            max_index = current_index
    return max_index


def ibw_read(file):
    ibw = igor.binarywave.load(file)
    timestamp = ibw["wave"]["wave_header"]["creationDate"]
    meta_sfA = ibw["wave"]["wave_header"]["sfA"]
    array = ibw["wave"]["wData"]
    return {"timestamp": timestamp, "meta_sfA": meta_sfA, "array": array}


def _ibw_results_to_df(results, gain=1.0):
    """
    Shared helper: converts a list of ibw_read() dicts into a tidy DataFrame.

    Each element of `results` corresponds to one .ibw file (= one sweep).
    Returns a DataFrame with columns: t0, time, voltage_raw, datetime, channel.

    Each .ibw file is treated as an independent sweep: t0 is always 0 (the
    sweep starts at its own t=0), and datetime is the absolute wall-clock time
    derived from the file's creation timestamp. Sweeps are not assumed to be
    continuous or evenly spaced; inter-sweep timing lives in datetime only.

    gain: multiplicative scale factor applied to voltage_raw after reading.
          IBW files may store voltage in V or mV depending on the recording
          setup, and may not be correctly labelled. Use gain=1e-3 to convert
          mV → V (SI). Defaults to 1.0 (no conversion).
    """
    keys = results[0].keys()
    res = {key: [r[key] for r in results] for key in keys}

    timesteps = res["meta_sfA"]
    voltage_raw = np.vstack(res["array"]) * gain  # apply manual gain (V or mV → V)
    timestamps = res["timestamp"]

    # Convert Mac HFS+ epoch (1904-01-01) to Unix epoch (1970-01-01).
    seconds = (
        pd.to_datetime("1970-01-01") - pd.to_datetime("1900-01-01")
    ).total_seconds()
    unix_timestamps = np.array(timestamps) - seconds  # absolute Unix time per sweep

    timestep = timesteps[0][0]
    num_columns = voltage_raw.shape[1]
    print(
        f"_ibw_results_to_df: timestep={timestep:.6g} s | "
        f"sampling rate={round(1 / timestep)} Hz | "
        f"{num_columns} samples/sweep"
    )
    time_columns = np.round(
        np.arange(num_columns) * timestep, math.ceil(-np.log10(timestep))
    ).tolist()

    df = pd.DataFrame(data=voltage_raw, columns=time_columns)
    df = df.stack().reset_index()
    df.columns = ["sweep_idx", "time", "voltage_raw"]

    # t0 = 0 for every row: each .ibw file is its own independent sweep.
    df["t0"] = 0.0

    # datetime = absolute creation time of that file + within-sweep time.
    sweep_unix = unix_timestamps[df["sweep_idx"].to_numpy(dtype=int)]
    df["datetime"] = pd.to_datetime(sweep_unix + df["time"].to_numpy(), unit="s")
    df["datetime"] = df["datetime"].dt.round("us")

    df.drop(columns=["sweep_idx"], inplace=True)
    df["time"] = df["time"].astype("float64")
    df["channel"] = 0

    return df


def parse_ibwFolder(folder, dev=False, gain=1.0):  # igor2, para
    files = sorted(list(folder.glob("*.ibw")))
    if dev:
        files = files[:100]

    results = Parallel(n_jobs=-1)(delayed(ibw_read)(file) for file in tqdm(files))

    # Sweep length check: all .ibw files in the folder must have the same shape.
    sweep_shapes = [r["array"].shape for r in results]
    unique_shapes = set(sweep_shapes)
    if len(unique_shapes) != 1:
        raise ValueError(f"Inconsistent sweep shapes detected: {unique_shapes}")

    return _ibw_results_to_df(results, gain=gain)


def parse_ibw(filepath, dev=False, gain=1.0):
    """
    Read a single .ibw file. Mirrors parse_abf: one file in, one sweep out.
    For reading a whole folder of sweeps, use parse_ibwFolder instead.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"No such file: '{filepath}'")
    results = [ibw_read(filepath)]
    return _ibw_results_to_df(results, gain=gain)


def parse_csv(source_path):
    """
    WIP: called by dataFile, assumes a Brainwash formatted csv file for now
    It is therefore currently the only parser that does not return a raw dataframe
    """
    df = pd.read_csv(source_path)
    return df


def sample_abf(filepath):
    """
    Extracts channelCount, sweepCount and sweep duration from an .abf file
    """
    filepath = Path(filepath)
    abf = pyabf.ABF(filepath)
    channel_count = abf.channelCount
    sweep_count = abf.sweepCount
    sample_rate = abf.sampleRate
    sweep_duration = len(abf.getAllXs()) / sample_rate  # duration in seconds
    dict_metadata = {
        "channel_count": channel_count,
        "sweep_count": sweep_count,
        "sample_rate": sample_rate,  # TODO: implement sample_rate, for listing in df_project
        "sweep_duration": sweep_duration,
    }
    return dict_metadata


# %%
def parse_abfFolder(folderpath, dev=False):
    """
    Read, sort (by filename) and concatenate all .abf files in folderpath to a single df
    """
    list_files = sorted(
        [i for i in os.listdir(folderpath) if -1 < i.find(".abf")]
    )  # [:2] # stop before item 2 [begin:end]
    if verbose:
        print(f"list_files: {list_files}")
    listdf = []
    for filename in list_files:
        df = parse_abf(folderpath / filename)
        listdf.append(df)
    df = pd.concat(listdf)
    df.reset_index(drop=True, inplace=True)
    # Check first timestamp in each df, verify correct sequence, raise error
    df["datetime"] = pd.to_datetime(df.datetime)
    return df


def parse_abf(filepath):
    """
    reads an .abf
    """
    abf = pyabf.ABF(filepath)
    if False:  # DEBUG
        print(f"abf: {abf}")
        for key, value in vars(abf).items():
            print(f"{key}: {value}")
    channels = abf.channelList

    # 1) build one big concatenated dataframe
    dfs = []
    for j in channels:
        sweepX = np.tile(abf.getAllXs(j)[: abf.sweepPointCount], abf.sweepCount)
        t0 = np.repeat(abf.sweepTimesSec, len(sweepX) // abf.sweepCount)
        sweepY = abf.getAllYs(j)
        df = pd.DataFrame({"sweepX": sweepX, "sweepY": sweepY, "t0": t0})
        df["channel"] = j
        dfs.append(df)
    df = pd.concat(dfs)
    # 2) Convert to SI, absolute date and time
    df["time"] = df.sweepX  # time in seconds from start of sweep recording
    df["voltage_raw"] = df.sweepY / 1000  # mv to V
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (
        abf.abfDateTime - pd.to_datetime(0)
    )
    df.drop(columns=["sweepX", "sweepY", "timens"], inplace=True)
    return df


def metadata(df):
    """
    Usage: called by parse.metadata(df) from ui.py
    returns a dict with metadata from the df:
    dict_meta: {    "nsweeps": number of sweeps in the recording
                    "sweep_duration": duration of a sweep in seconds
                    "sampling_rate": sampling rate in Hz        }
    """
    # Number of unique sweeps, by number of 'time'==0
    nsweeps = df["time"].value_counts().get(0, 0)
    # Duration of one sweep: max time within a sweep (assume uniform: varied sweep length should throw exception at parsing)
    first_sweep = df[df["sweep"] == df["sweep"].iloc[0]]
    time_diffs = first_sweep["time"].diff().dropna()
    dt = time_diffs.mode().iloc[0]  # Sample interval
    sweep_duration = round(first_sweep["time"].max() + dt, 6)
    # Sampling rate: 1 / interval between time samples (assume uniform)
    time_diffs = first_sweep["time"].diff().dropna()
    sampling_rate = int(round(1 / time_diffs.mode().iloc[0]))
    dict_meta = {
        "nsweeps": nsweeps,  # number of sweeps in the recording
        "sweep_duration": sweep_duration,  # time in seconds
        "sampling_rate": sampling_rate,  # Hz
    }
    print(
        f"metadata: {nsweeps} sweeps | "
        f"{sampling_rate} Hz (dt={dt:.6g} s) | "
        f"sweep duration {sweep_duration:.6g} s"
    )
    return dict_meta


""" the old dict_sub metadata was:
                dict_sub = {
                    'nsweeps': df_ch_st['sweep'].nunique(),
                    'channel': channel,
                    'stim': stim,
                    'sweep_duration': df_ch_st['time'].max() - df_ch_st['time'].min(),
                    'resets': df_ch_st[(df_ch_st['sweep_raw'] == df_ch_st['sweep_raw'].min()) & (df_ch_st['time'] == 0)]['sweep'].tolist()[1:]
                }"""


def source2dfs(source, dev=False, gain=1.0):
    """
    Identifies type of file(s), and calls the appropriate parser.
    - source (str): Path to source file or folder
    - gain (float): multiplicative voltage scale factor, passed to IBW parsers only.
                    Use gain=1e-3 when IBW files are stored in mV and V (SI) is needed.
                    Has no effect on ABF files (pyabf handles unit conversion internally).
    Returns: a dict {channel:DataFrame} of Raw (unprocessed) output from the appropriate parser
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"source2df: No such file or folder: '{source}'")
    # if source_path is a folder
    if path.is_dir():  # TODO: currently reads only one type of file:
        files = [f for f in path.iterdir() if f.is_file()]
        abf_files = [f for f in files if f.suffix.lstrip(".").lower() == "abf"]
        ibw_files = [f for f in files if f.suffix.lstrip(".").lower() == "ibw"]
        csv_files = [f for f in files if f.suffix.lstrip(".").lower() == "csv"]
        print(f" - {source} is a folder with {len(files)} files:")
        print(
            f" - - {len(abf_files)} abf files, {len(ibw_files)} ibw files, and {len(csv_files)} csv files."
        )
        if csv_files:
            # TODO: implement CSV parsing - check for correct column names
            raise ValueError(".csv from folders are not supported yet.")
        elif abf_files:
            try:
                df = parse_abfFolder(path, dev=dev)
            except Exception as e:
                raise ValueError(f"Error parsing abf files in folder {path}: {e}")
        elif ibw_files:
            try:
                df = parse_ibwFolder(path, dev=dev, gain=gain)
            except Exception as e:
                raise ValueError(f"Error parsing ibw files in folder {path}: {e}")
        else:
            print(f"No valid files found.")
            return {}
    # if source_path is not a folder - parse as a single file
    else:
        filetype = path.suffix.lstrip(".").lower()
        if filetype == "csv":
            df = parse_csv(source)
        elif filetype == "abf":
            df = parse_abf(source)
        elif filetype == "ibw":
            df = parse_ibw(source, gain=gain)
        else:
            raise ValueError(f"Unsupported file type: {filetype}")

    dict_channeldfs = {}
    # if df has a 'sweep' column, it's from a prepared .csv - skip this cleanup
    if "sweep" in df.columns:
        print(" - - Detected 'sweep' column, skipping cleanup.")
        # TODO: extract channel from filename; "*_ch0"
        dict_channeldfs[0] = df
        return dict_channeldfs

    # split by channel
    for channel in df["channel"].unique():
        dict_channeldfs[channel] = df[df["channel"] == channel]
    # sort df by datetime

    for channel, df in dict_channeldfs.items():
        # Group rows into sweeps by detecting time resets (time == 0 starts a new sweep).
        sweep_groups = (df["time"] == 0).cumsum()
        # Check that each sweep's start datetime is monotonically increasing.
        sweep_start_dt = df.groupby(sweep_groups)["datetime"].first()
        if not sweep_start_dt.is_monotonic_increasing:
            print(
                " - - Warning: sweep start datetimes not monotonic increasing, sorting sweeps."
            )
            sweep_order = sweep_start_dt.sort_values().index
            sorted_pieces = [df[sweep_groups == grp] for grp in sweep_order]
            dict_channeldfs[channel] = pd.concat(sorted_pieces).reset_index(drop=True)
    # generate 'sweep' column and drop channel column
    for df in dict_channeldfs.values():
        df["sweep"] = df.groupby((df["time"] == 0).cumsum()).ngroup()
        df.drop(columns=["channel"], inplace=True)

    # reorder columns
    column_order = ["sweep", "time", "voltage_raw", "t0", "datetime"]
    for channel, df in dict_channeldfs.items():
        df_cols = [col for col in column_order if col in df.columns]
        dict_channeldfs[channel] = df[
            df_cols + [col for col in df.columns if col not in df_cols]
        ]

    return dict_channeldfs


#############################################################
#                  Standalone testing                       #
#############################################################


def sources2dfs(list_sources, dev=False, gain=1.0):
    """
    Converts a list of source file paths to a list of raw DataFrames.
    - gain (float): multiplicative voltage scale factor, forwarded to source2dfs.
                    See source2dfs for details.
    """
    list_dicts = []
    for source in list_sources:
        print(f"Processing source: {source}")
        dict_dfs = source2dfs(source, dev=dev, gain=gain)
        list_dicts.append(dict_dfs)
    return list_dicts


def persistdf(file_base, dict_folders, dfdata=None, dfmean=None, dffilter=None):
    if dfdata is not None:
        dict_folders["data"].mkdir(exist_ok=True)
        str_data_path = f"{dict_folders['data']}/{file_base}.csv"
        dfdata.to_csv(str_data_path, index=False)
    if dfmean is not None:
        dict_folders["cache"].mkdir(exist_ok=True)
        str_mean_path = f"{dict_folders['cache']}/{file_base}_mean.csv"
        dfmean.to_csv(str_mean_path, index=False)
    if dffilter is not None:
        dict_folders["cache"].mkdir(exist_ok=True)
        str_mean_path = f"{dict_folders['cache']}/{file_base}_filter.csv"
        dffilter.to_csv(str_mean_path, index=False)


# %%
if __name__ == "__main__":
    dev = False
    source_folder = Path.home() / "Documents/Brainwash Data Source/"
    dict_folders = {
        "project": Path.home() / "Documents/Brainwash Projects/standalone_test"
    }
    dict_folders["data"] = dict_folders["project"] / "data"
    dict_folders["cache"] = dict_folders["project"] / "cache"
    dict_folders["project"].mkdir(parents=True, exist_ok=True)

    list_sources = [  # r"C:\Users\xandmz\Documents\data\Rong Samples\Good recording"
        # r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_a.csv",
        # r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_b.csv",
        # list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2"),
        #                 str(source_folder / "abf 1 channel/A_24_P0630-D4"),
        #                 str(source_folder / "abf 1 channel/B_22_P0701-D3"),
        #                 str(source_folder / "abf 1 channel/B_23_P0630-D3"),
        #                ]
        # list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"), str(source_folder / "abf 2 channel/KO_02/2022_01_24_0020.abf")]
        # list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"), str(source_folder / "abf 2 channel/KO_02/2022_01_24_0020.abf")]
        # list_sources = [str(source_folder / "abf 1 channel/A_24_P0630-D4")]
        # list_sources = [str(source_folder / "abf Ca trains/03 PT 10nM TTX varied Stim/2.8MB - PT/2023_07_18_0006.abf")]
        # list_sources = [r"K:\Brainwash Data Source\Rong Samples\SameTime"]
        # list_sources = [
        #                r"K:\Brainwash Data Source\csv\A_21_P0701-S2_Ch0_a.csv",
        r"K:\Brainwash Data Source\Rong Samples\Good recording",
        #                r"K:\Brainwash Data Source\abf 2 channel\KO_02",
        #                r"K:\Brainwash Data Source\Rong Samples\Good recording\W100x1_1_2.ibw",
        #                r"K:\Brainwash Data Source\Rong Samples\Good recording\W100x1_1_25.ibw",
        #                r"K:\Brainwash Data Source\abf 1 channel\A_21_P0701-S2\2022_07_01_0012.abf",
    ]

    for _ in range(3):
        print()
    print("", "*** parse.py standalone test: ***")

    # read sources
    t0 = time.time()
    try:
        list_dicts = sources2dfs(list_sources, dev=dev)
    except Exception as e:
        print(f"Error processing: {e}")
    t1 = time.time()
    print(f"time to parse into {len(list_dicts)} dataframe(s): {t1 - t0} seconds")
    for dict_dfs in list_dicts:
        for channel, df in dict_dfs.items():
            print(f" - channel {channel} df{df.shape}, columns: {df.columns.tolist()}")
    print()

    # report post-processed metadata
    list_metas = []
    t0 = time.time()
    for dict_dfs in list_dicts:
        for channel, df in tqdm(dict_dfs.items()):
            print(f" - Processing channel: {channel}")
            list_metas.append(metadata(df))
    for meta in list_metas:
        for key, value in meta.items():
            tqdm.write(f" - - {key}: {value}")
    t1 = time.time()
    print(f"time to process metadata: {t1 - t0} seconds")
    print()

    print(f"{len(list_dicts)} dataframe(s) processed.")
    print()

    # testing persistence
    print(f"Testing persistence in {dict_folders['data']}")
    # make sure dict_folders exist
    for folder in dict_folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    for dict_df in list_dicts:
        for channel, df in dict_df.items():
            print(f" - channel {channel} df{df.shape}")
            t0 = time.time()
            df.to_parquet(
                str(dict_folders["data"] / f"df_{channel}.parquet"), index=False
            )
            t1 = time.time()
            print(f" - df_{channel}.parquet saved: {t1 - t0:.2f} seconds")
            t0 = time.time()
            df.to_csv(str(dict_folders["data"] / f"df_{channel}.csv"), index=False)
            t1 = time.time()
            print(f" - df_{channel}.csv saved: {t1 - t0:.2f} seconds")
            t0 = time.time()
            # reading formats back to _df
            df_read_parquet = pd.read_parquet(
                str(dict_folders["data"] / f"df_{channel}.parquet")
            )
            t1 = time.time()
            print(f" - df_{channel}.parquet read: {t1 - t0:.2f} seconds")
            t0 = time.time()
            df_read_csv = pd.read_csv(str(dict_folders["data"] / f"df_{channel}.csv"))
            t1 = time.time()
            print(f" - df_{channel}.csv read: {t1 - t0:.2f} seconds")
        print()
