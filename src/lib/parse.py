# %%
import os  # speak to OS (list dirs)
from pathlib import Path

import numpy as np
import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
import igor2 as igor # read data files ibw

from tqdm import tqdm
#from joblib import Memory
from joblib import Parallel, delayed
import time

#memory = Memory("../cache", verbose=1)

verbose = True

# set some working folders
# TODO: set as globals?
# TODO: get project root. this will not work now
dir_project_root = Path(os.getcwd().split("notebook")[0])
dir_source_data = dir_project_root / "dataSource" / "Lactate_2022_abf"
dir_gen_data = dir_project_root / "dataGenerated"


# %%
def build_experimentcsv(dir_gen_data):
    """
    Generate overview file of all csv:s
    Assumes no such file exists
    Add later: functions to check for not-included-folders, convert those

    # Read groups and assigment from metadata.txt
    # Later: read applied algorithm from metadata.txt into df
    """
    list_metadatafiles = [i for i in os.listdir(dir_gen_data) if -1 < i.find("_metadata.txt")]
    dfmetadata = pd.concat([pd.read_csv(dir_gen_data / i) for i in list_metadatafiles])
    dfmetadata.reset_index(drop=True, inplace=True)
    return dfmetadata


# %%
def build_dfmean(dfdata, rollingwidth=3):
    print("build_dfmean")
    if False:
        dfmean = dfdata.copy()
        dfmean.drop(columns=['datetime', 'sweep_raw', 'sweep'], inplace=True)
        dfmean.rename(columns={'voltage_raw': 'voltage'}, inplace=True)
        # Aggregate rows with identical 'time' values by computing the mean
        dfmean = dfmean.groupby('time').mean().reset_index()

        # leftovers:
        # Ensure aggregation over 'sweep' and 'time' removes all duplicates
        dfdata = dfdata.groupby(['sweep', 'time'], as_index=False)['voltage_raw'].mean()
        print("aggregation finished.")

        # Check for duplicates after aggregation (for debugging purposes)
        if dfdata.duplicated(['sweep', 'time']).any():
            print("Warning: Still duplicates present after aggregation.")

    dfmean = pd.pivot_table(dfdata, values='voltage_raw', index='sweep', columns='time', aggfunc='mean').mean().to_frame(name='voltage')
    dfmean['prim'] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
    dfmean['bis'] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()
    dfmean.reset_index(inplace=True)
    i_stim = first_stim_index(dfmean)
    baseline_mean = dfmean.iloc[i_stim-20:i_stim-10]['voltage'].mean()  # Adjusted for potential NaNs
    dfmean['voltage'] = dfmean['voltage'] - baseline_mean
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
    duplicates = df_zeroed.duplicated(subset=['sweep', 'time'], keep=False)
    if duplicates.any():
        print("Warning: Duplicates found before zeroing.")
        print(df_zeroed[duplicates])
        df_zeroed = df_zeroed.groupby(['sweep', 'time']).agg({'voltage_raw': 'mean'}).reset_index()
        print("Duplicates removed.")
        print(df_zeroed)
    
    dfpivot = df_zeroed.pivot(index='sweep', columns='time', values='voltage_raw')  # Reshape df_zeroed to have one row per 'sweep' and one column per 'time'
    ser_mean = dfpivot.iloc[:, i_stim-20:i_stim-10].mean(axis=1)  # Calculate the mean of 'voltage_raw' values from the 20th to the 10th column before i_stim for each 'sweep'
    dfpivot = dfpivot.subtract(ser_mean, axis='rows')  # Subtract the calculated means from dfpivot
    
    # handle the reassignment to 'voltage' to ensure length matches
    df_zeroed = df_zeroed.drop(columns=['voltage_raw'])
    df_stacked = dfpivot.stack().reset_index(name='voltage')
    # Merge back with df_zeroed to ensure correct length and alignment
    df_zeroed = df_zeroed.merge(df_stacked, on=['sweep', 'time'], how='left')
    
    print(f"zeroSweeps: {df_zeroed}")
    return df_zeroed

def first_stim_index(dfmean, threshold_factor=0.75, min_time_difference=0.005):
    # returns the index of the first peak in the prim column of dfmean
    y_max_stim = dfmean.prim.max()
    threshold = y_max_stim * threshold_factor
    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    if above_threshold_indices.size == 0:
        return None
    max_index = above_threshold_indices[0]
    for i in range(1, len(above_threshold_indices)):
        current_index = above_threshold_indices[i]
        previous_index = above_threshold_indices[i - 1]
        if dfmean['time'][current_index] - dfmean['time'][previous_index] > min_time_difference:
            break
        if dfmean['prim'][current_index] > dfmean['prim'][max_index]:
            max_index = current_index
    return max_index


def persistdf(file_base, dict_folders, dfdata=None, dfmean=None, dffilter=None):
    if dfdata is not None:
        dict_folders['data'].mkdir(exist_ok=True)
        str_data_path = f"{dict_folders['data']}/{file_base}.csv"
        dfdata.to_csv(str_data_path, index=False)
    if dfmean is not None:
        dict_folders['cache'].mkdir(exist_ok=True)
        str_mean_path = f"{dict_folders['cache']}/{file_base}_mean.csv"
        dfmean.to_csv(str_mean_path, index=False)
    if dffilter is not None:
        dict_folders['cache'].mkdir(exist_ok=True)
        str_mean_path = f"{dict_folders['cache']}/{file_base}_filter.csv"
        dffilter.to_csv(str_mean_path, index=False)


def metaData(source_path, sweep=0, force_sample=False):
    """
    WIP
    Usage: called by parse.metaData from ui.py
    * Returns a dict of statistics from metadata if available, otherwise as measured from a sweep in the source
        source_path: Path to source file or folder
        sweep: use this sweep to create metadata, if available
        force_sample: analyze the first sweep in the source, regardless of metadata
    """

    def sampler(source_path):
        df = None
        if verbose:
            print(f" - parser, source_path: {source_path}")
        if False: #Path(source_path).is_dir(): # TODO: 
            # check contents of folder: .ibw or .abf
            list_files = [i for i in os.listdir(source_path) if -1 < i.find(".ibw") or -1 < i.find(".abf")]
            filetype = None
            if -1 < list_files[0].find(".abf"):
                filetype = "abf"
            elif -1 < list_files[0].find(".ibw"):
                filetype = "ibw"
            if filetype is None:
                raise ValueError(f" - - no supported files found in {source_path}")

            if filetype == "abf":
                df = parse_abfFolder(folderpath=Path(source_path))
            elif filetype == "ibw":
                df = parse_ibwFolder(folder=Path(source_path))#, dev=True)
        else:
            # set filetype to last 3 letters of filename
            filetype = source_path[-3:]
            if filetype == "csv":
                df = pd.read_csv(source_path)
                dict_metadata = {
                    'nsweeps': df['sweep'].nunique(),
                    # channel is what comes after the last Ch in the filename, and ends before the first _
                    'channel': source_path.split("Ch")[-1].split("_")[0],
                    # stim is the last letter in the filename, before the .csv
                    'stim': source_path.split("_")[-1].split(".")[0],
                    # sweep_duration is the difference between the highest and the lowest time in the file
                    'sweep_duration': df['time'].max() - df['time'].min(),}
                # TODO: Add checks for csv files; must be brainwash formatted!
                return dict_metadata
            elif filetype == "abf":
                dict_metadata = sample_abf(source_path)
                return dict_metadata
            elif filetype == "ibw":
                df = parse_ibw(filepath=Path(source_path))
            if df is None:
                raise ValueError(f" - - no supported files found in {source_path}")
            # make a df first, then sample it
            dict_metadata = {"nsweeps": None,
                            "channels": None,
                            "stims": None, 
                            "sweep_duration": None,}
            return dict_metadata

    dict_metadata = sampler(source_path=source_path)
    return dict_metadata


def ibw_read(file):
    ibw = igor.binarywave.load(file)
    timestamp = ibw['wave']['wave_header']['creationDate']
    meta_sfA = ibw['wave']['wave_header']['sfA']
    array = ibw['wave']['wData']
    return {'timestamp': timestamp, 'meta_sfA': meta_sfA, 'array': array}


def parse_ibwFolder(folder, dev=False): # igor2, para
    files = sorted(list(folder.glob('*.ibw')))
    if dev:
        files = files[:100]
    results = Parallel(n_jobs=-1)(delayed(ibw_read)(file) for file in tqdm(files))
    keys = results[0].keys()
    res = {}
    for key in keys:
        res[key] = [i[key] for i in results]
    timesteps = res['meta_sfA']
    arrays = np.vstack(res['array'])
    timestamps = res['timestamp']       

    seconds = (pd.to_datetime("1970-01-01") - pd.to_datetime("1900-01-01")).total_seconds()
    timestamp_array = (np.array(timestamps)-seconds)
    measurement_start = min(timestamp_array)
    timestamp_array -= measurement_start
    voltage_raw = np.vstack(arrays)
    df = pd.DataFrame(data=voltage_raw, index=timestamp_array)
    timestep = timesteps[0][0]
    num_columns = voltage_raw.shape[1]
    df.columns = np.round(np.arange(num_columns) * timestep, int(-np.log(timestep))).tolist()
    df = df.stack().reset_index()
    df.columns = ['t0', 'time', 'voltage_raw']
    df.t0 = df.t0.astype("float64")
    df.time = df.time.astype("float64")
    df['datetime'] = pd.to_datetime((measurement_start + df.t0 + df.time), unit="s").round("us")
    df['channel'] = 0

    return df


def parse_ibw(filepath, dev=False): # igor2, para
    files = [Path(filepath)] # TODO: EVERY attempt to read just one filepath, without what should be superfluous lists, has failed due to unresolvable mismatch errors
    for file in files:
        if not file.exists():
            raise FileNotFoundError(f"No such file: '{file}'")
    results = Parallel(n_jobs=-1)(delayed(ibw_read)(file) for file in tqdm(files))
    keys = results[0].keys()
    res = {}
    for key in keys:
        res[key] = [i[key] for i in results]
    timesteps = res['meta_sfA']
    arrays = np.vstack(res['array'])
    timestamps = res['timestamp']       

    seconds = (pd.to_datetime("1970-01-01") - pd.to_datetime("1900-01-01")).total_seconds()
    timestamp_array = (np.array(timestamps)-seconds)
    measurement_start = min(timestamp_array)
    timestamp_array -= measurement_start
    voltage_raw = np.vstack(arrays)
    df = pd.DataFrame(data=voltage_raw, index=timestamp_array)
    timestep = timesteps[0][0]
    num_columns = voltage_raw.shape[1]
    df.columns = np.round(np.arange(num_columns) * timestep, int(-np.log(timestep))).tolist()
    df = df.stack().reset_index()
    df.columns = ['t0', 'time', 'voltage_raw']
    df.t0 = df.t0.astype("float64")
    df.time = df.time.astype("float64")
    df['datetime'] = pd.to_datetime((measurement_start + df.t0 + df.time), unit="s").round("us")
    df['channel'] = 0

    return df


def parse_csv(source_path, recording_name=None, keep_non_stim_data=False):
    """
        WIP: called by dataFile, assumes a Brainwash formatted csv file for now
        It is therefore currently the only parser that does not return a raw dataframe
    """
    if recording_name is None:
        recording_name = os.path.basename(os.path.dirname(source_path))

    df = pd.read_csv(source_path)
    dict_meta = {
        'recording_name': recording_name,
        'nsweeps': df['sweep'].nunique(),
        # channel is what comes after the last Ch in the filename, and ends before the first _
        'channel': source_path.split("Ch")[-1].split("_")[0],
        # stim is the last letter in the filename, before the .csv
        'stim': source_path.split("_")[-1].split(".")[0],
        # sweep_duration is the difference between the highest and the lowest time in the file
        'sweep_duration': df['time'].max() - df['time'].min(),
        # recorded y:s per second
        'sampling_rate': (df['time'].nunique() - 1) / (df['time'].max() - df['time'].min()),
        # reset is the first sweep number after every sweep_raw reset: finds recording breaks for display purposes
        'resets': df[(df['sweep_raw'] == df['sweep_raw'].min()) & (df['time'] == 0)]['sweep'].tolist()[1:],
    }
    return [(dict_meta, df)]


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
        "sample_rate": sample_rate, # TODO: implement sample_rate, for listing in df_project
        "sweep_duration": sweep_duration
    }
    return dict_metadata


# %%
def parse_abfFolder(folderpath):
    """
    Read, sort (by filename) and concatenate all .abf files in folderpath to a single df
    """
    list_files = sorted([i for i in os.listdir(folderpath) if -1 < i.find(".abf")])  # [:2] # stop before item 2 [begin:end]
    if verbose:
        print(f"list_files: {list_files}")
    listdf = []
    for filename in list_files:
        df = parse_abf(folderpath / filename)
        listdf.append(df)
    df = pd.concat(listdf)
    df.reset_index(drop=True, inplace=True)
    # Check first timestamp in each df, verify correct sequence, raise error
    df['datetime'] = pd.to_datetime(df.datetime)
    return df


def parse_abf(filepath, recording_name=None, keep_non_stim_data=False):
    """
    reads a .abf 
    returns a list of tuples: [(dict_meta, df_raw), ...]
    WIP: There is considerable postprocessing in the original code - channels and stims - which is not yet implemented here
        df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
        df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
    """
    if recording_name is None:
        recording_name = os.path.basename(os.path.dirname(filepath))
    abf = pyabf.ABF(filepath)
    if False: # DEBUG
        print(f"abf: {abf}")
        for key, value in vars(abf).items():
            print(f"{key}: {value}")
    sweeps = abf.sweepCount
    channels = abf.channelList

    # 1) build one big concatenated dataframe
    dfs = []
    for j in channels:
        sweepX = np.tile(abf.getAllXs(j)[:abf.sweepPointCount], abf.sweepCount)
        t0 = np.repeat(abf.sweepTimesSec, len(sweepX) // abf.sweepCount)
        sweepY = abf.getAllYs(j)
        df = pd.DataFrame({"sweepX": sweepX, "sweepY": sweepY, "t0": t0})
        df['channel'] = j
        dfs.append(df)
    df = pd.concat(dfs)
    # 2) Convert to SI, absolute date and time
    df['time'] = df.sweepX  # time in seconds from start of sweep recording
    df['voltage_raw'] = df.sweepY / 1000  # mv to V
    df['timens'] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df['datetime'] = df.timens.astype("datetime64[ns]") + (abf.abfDateTime - pd.to_datetime(0))
    df.drop(columns=['sweepX', 'sweepY', 'timens'], inplace=True)
    # 3) Assumptions: 2 stims, for now
    list_stims = ["a", "b"]
    nstims = len(list_stims)
    nchannels = df.channel.nunique()
    sweep_duration = df.time.nunique()
    df.sort_values(by=['datetime', 'channel'], inplace=True, ignore_index=True)
    df['sweep_raw'] = df.index // (sweep_duration * nchannels)
    # 4) split by channel and stim
    list_tuple_data = []
    for channel in df.channel.unique():
        print(f" - channel: {channel} (nchannels: {nchannels}), nstims: {nstims}, sweep_duration: {sweep_duration}")
        if keep_non_stim_data:
            df_ch = df # TODO NOT TESTED!
        else:
            df_ch = df[df.channel==channel]
        for i, stim in enumerate(list_stims):
            full_recording_name = f"{recording_name}_Ch{channel}_{stim}"
            df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
            df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
        df_raw = df
        dict_meta = {
            "recording_name": full_recording_name,
            "channels": channels,
            "nsweeps": sweeps,
            "sweep_duration": len(abf.getAllXs()) / abf.sampleRate,
            "sampling_rate": abf.sampleRate,
            "resets": [],
        }
        # 4a) add tuple to list
        list_tuple_data.append((dict_meta, df_raw))
    return list_tuple_data



def parseProjFiles(dict_folders, df=None, recording_name=None, source_path=None, single_stim=False):
    """
    WIP: Still operational, called from ui.py - TO BE REPLACED BY dataFile.
    * receives a df of project data file paths built in ui
        files that are already parsed are to be overwritten (ui.py passes filitered list of unparsed files)
    * creates a datafile by unique source file/channel/stim combination
    * Stim defaults to a and b
    * saves two files:
        dict_folders['data']<recording_name>_Ch<Ch>_<Stim>.csv
        dict_folders['cache']<recording_name>_Ch<Ch>_<Stim>_dfmean.csv
    
    returns a list of <recording_name>_Ch<Ch>_<Stim> for updating df_project recording names
    calls build_dfmean() to create an average, prim and bis file, per channel-stim combo
    """
    def parser(dict_folders, recording_name, source_path):
        df = None
        dict_data = {}
        if verbose:
            print(f" - parser, source_path: {source_path}")
        if Path(source_path).is_dir():
            # check contents of folder: .ibw or .abf
            list_files = [i for i in os.listdir(source_path) if -1 < i.find(".ibw") or -1 < i.find(".abf")]
            filetype = None
            if -1 < list_files[0].find(".abf"):
                filetype = "abf"
            elif -1 < list_files[0].find(".ibw"):
                filetype = "ibw"
            if filetype is None:
                raise ValueError(f" - - no supported files found in {source_path}")

            if filetype == "abf":
                df = parse_abfFolder(folderpath=Path(source_path))
            elif filetype == "ibw":
                df = parse_ibwFolder(folder=Path(source_path))#, dev=True)
        else:
            # set filetype to last 3 letters of filename
            filetype = source_path[-3:]
            if filetype == "csv":
                df = pd.read_csv(source_path)
                file_base = os.path.splitext(os.path.basename(source_path))[0].replace('.', '_')
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=df)
                dict_sub = {
                    'nsweeps': df['sweep'].nunique(),
                    # channel is what comes after the last Ch in the filename, and ends before the first _
                    'channel': source_path.split("Ch")[-1].split("_")[0],
                    # stim is the last letter in the filename, before the .csv
                    'stim': source_path.split("_")[-1].split(".")[0],
                    # sweep_duration is the difference between the highest and the lowest time in the file
                    'sweep_duration': df['time'].max() - df['time'].min(),
                    # reset is the first sweep number after every sweep_raw reset: finds recording breaks for display purposes
                    'resets': df[(df['sweep_raw'] == df['sweep_raw'].min()) & (df['time'] == 0)]['sweep'].tolist()[1:]
                    }
                # TODO: Add checks for csv files; must be brainwash formatted!
                dict_data[file_base] = dict_sub
                return dict_data
            elif filetype == "abf":
                df = parse_abf(filepath=Path(source_path))
            elif filetype == "ibw":
                df = parse_ibw(filepath=Path(source_path))
        if df is None:
            raise ValueError(f" - - no supported files found in {source_path}")
        df = df.sort_values(by='datetime').reset_index(drop=True)
        # sort df2parse in channels and stims (a and b)
        if single_stim:
            if verbose:
                print(" - - user set single_stim=True")
                list_stims=["a"]
        else: #default to 2 stims 
            if verbose:
                print(" - - default: two stims per channel")
                list_stims=["a", "b"]
        nstims = len(list_stims)
        nchannels = df.channel.nunique()
        sweep_duration = df.time.nunique()

        print(f" - - nchannels: {nchannels}, nstims: {nstims}, sweep_duration: {sweep_duration}")

        # TODO: Why is this copied?
        dfcopy = df.copy()
        dfcopy = dfcopy.sort_values(by=['datetime', 'channel']).reset_index(drop=True)
        dfcopy['sweep_raw'] = dfcopy.index.to_numpy() // (sweep_duration * nchannels)
        print (f" - - dfcopy: {dfcopy}")
        for channel in dfcopy.channel.unique():
            df_ch = dfcopy[dfcopy.channel==channel]
            for i, stim in enumerate(list_stims):
                file_base = f"{recording_name}_Ch{channel}_{stim}"
                print(f"file_base: {file_base}")
                if filetype == "abf": # split df by % nstims
                    df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
                    df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
                elif filetype == "ibw":
                    if False: # split df; time < 0.5 is stim a, time >= 0.5 is stim b
                        # TODO: This is a stupid approach; don't split the data before the stims are placed!
                        if stim == "a":
                            df_ch_st = dfcopy.loc[dfcopy.time < 0.25].copy()
                        if stim == "b":
                            df_ch_st = dfcopy.loc[dfcopy.time >= 0.5].copy()  
                    else:
                        df_ch_st = dfcopy.copy()
                    df_ch_st['sweep'] = df_ch_st.sweep_raw
                df_ch_st.drop(columns=['channel'], inplace=True)
                print(f"nunique: {df_ch_st['sweep'].nunique()}")
                dfmean, i_stim = build_dfmean(df_ch_st)
                dffilter = zeroSweeps(dfdata=df_ch_st, i_stim=i_stim)
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=df_ch_st, dfmean=dfmean, dffilter=dffilter)
                # Build dict: keys are datafile names, values are a dict of nsweeps, channels, stim, and reset (the first sweep number after every sweep_raw reset: finds recording breaks for display purposes)
                dict_sub = {
                    'nsweeps': df_ch_st['sweep'].nunique(),
                    'channel': channel,
                    'stim': stim,
                    'sweep_duration': df_ch_st['time'].max() - df_ch_st['time'].min(),
                    'resets': df_ch_st[(df_ch_st['sweep_raw'] == df_ch_st['sweep_raw'].min()) & (df_ch_st['time'] == 0)]['sweep'].tolist()[1:]
                }
                dict_data[f"{recording_name}_Ch{channel}_{stim}"] = dict_sub
        return dict_data

    if verbose:
        print(f"proj folder: {dict_folders['project']}")
        if source_path is not None:
            print(f"recording_name: {recording_name}")
            print(f"source_path: {source_path}")
        if df is not None:
            print(f"recording_name: {df['recording_name']}")
            print(f"path: {df['path']}")

    if recording_name is not None:
        list_data = parser(dict_folders=dict_folders, recording_name=recording_name, source_path=source_path)
        return list_data

    if df is not None:
        df_unique_names = df.drop_duplicates(subset='recording_name')
        for i, row in df_unique_names.iterrows():
            recording_name = row['recording_name']
            source_path = row['path']
            list_data = parser(dict_folders=dict_folders, recording_name=recording_name, source_path=source_path)
        return list_data



def source2meta_df(source_path, recording_name=None):
    """
    Usage: called by parse.source2meta_df from ui.py
    Identifies type of file(s), and calls the appropriate parser
    * source_path: Path to source file or folder
    * recording_name: use to force a recording name
    Returns a tuples: (dict_meta, df_raw)
    dict_meta: {
        "recording_name": "<recording_name>"
        "nsweeps": number of sweeps in the recording
        "sweep_duration": duration of a sweep in seconds
        "sampling_rate": sampling rate in Hz
        }
        df_raw is the data from the source file(s)
    """
    path = Path(source_path)
    
    if recording_name is None: # default to the name of the source file or folder
        recording_name = Path(source_path).resolve().stem if Path(source_path).is_file() \
                        else Path(source_path).resolve().name

    #placeholder for metadata
    dict_meta = {
        'recording_name': recording_name,
        'nsweeps': 0,
        'sweep_duration': 1.032, #time in seconds
        'sampling_rate': 10000,  #Hz
        }

    # Source_path is a folder
    if path.is_dir(): # TODO: currently reads only one type of file:
        print(f" - parse.dataFile: source_path is a folder: {source_path}")
        files = [f for f in path.iterdir() if f.is_file()]
        # if there are .abf files, parse and return those.
        abf_files = [f for f in files if f.suffix.lstrip(".").lower() == "abf"]
        if abf_files:
            df = parse_abfFolder(path)
        # elif there are .ibw files, parse and return those.
        ibw_files = [f for f in files if f.suffix.lstrip(".").lower() == "ibw"]
        if ibw_files:
            df = parse_ibwFolder(path)
        # TODO elif there are .csv files, parse and return those.
        csv_files = [f for f in files if f.suffix.lstrip(".").lower() == "csv"]
        #if csv_files:
        #    return parse_csvFolder(path, recording_name=recording_name)
        if not (abf_files or ibw_files or csv_files):
            raise ValueError(f"No valid files found in {source_path}")
        return (dict_meta, df)
    
    # source_path is not a folder - parse as a single file
    PARSERS = {
        "csv": parse_csv,
        "abf": parse_abf,
        "ibw": parse_ibw,
    }
    filetype = path.suffix.lstrip(".").lower()
    if filetype not in PARSERS:
        raise ValueError(f"Unsupported file type: {filetype}")
    df = PARSERS[filetype](source_path, recording_name=recording_name, keep_non_stim_data=keep_non_stim_data)
    return (dict_meta, df)



# %%
if __name__ == "__main__":
    source_folder = Path.home() / "Documents/Brainwash Data Source/"
    dict_folders = {'project': Path.home() / "Documents/Brainwash Projects/standalone_test"}
    dict_folders['data'] = dict_folders['project'] / "data"
    dict_folders['cache'] = dict_folders['project'] / "cache"
    dict_folders['project'].mkdir(parents=True, exist_ok=True)
    
    list_sources = [r"C:\Users\xandmz\Documents\data\Rong Samples\Good recording"
                    #r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_a.csv",
                    #r"C:\Users\xandmz\Documents\data\A_21_P0701-S2_Ch0_b.csv",
                    ]
    # list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2"),
    #                 str(source_folder / "abf 1 channel/A_24_P0630-D4"),
    #                 str(source_folder / "abf 1 channel/B_22_P0701-D3"),
    #                 str(source_folder / "abf 1 channel/B_23_P0630-D3"),                    
    #                ]
    #list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"), str(source_folder / "abf 2 channel/KO_02/2022_01_24_0020.abf")]
    #list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"), str(source_folder / "abf 2 channel/KO_02/2022_01_24_0020.abf")]
    #list_sources = [str(source_folder / "abf 1 channel/A_24_P0630-D4")]
    #list_sources = [str(source_folder / "abf Ca trains/03 PT 10nM TTX varied Stim/2.8MB - PT/2023_07_18_0006.abf")]
    #list_sources = [r"K:\Brainwash Data Source\Rong Samples\SameTime"]
    #list_sources = [
    #                r"K:\Brainwash Data Source\csv\A_21_P0701-S2_Ch0_a.csv",
    #                r"K:\Brainwash Data Source\Rong Samples\Good recording\W100x1_1_1.ibw",
    #                r"K:\Brainwash Data Source\Rong Samples\Good recording\W100x1_1_2.ibw",
    #                r"K:\Brainwash Data Source\Rong Samples\Good recording\W100x1_1_25.ibw",
    #                r"K:\Brainwash Data Source\abf 1 channel\A_21_P0701-S2\2022_07_01_0012.abf",
    #                ]

        
    for _ in range(3):
        print()
    print("", "*** parse.py standalone test: ***")
    t0 = time.time()
    
    for item in tqdm(list_sources):
        if Path(item).is_dir():
            recording_name = os.path.basename(item)
        else:
            recording_name = os.path.basename(os.path.dirname(item))
        print(" - processing", item, "as recording_name", recording_name)
        dict_meta, df_raw = source2meta_df(item)
        for key, value in dict_meta.items():
            print(f" - - {key}: {value}")
    t1 = time.time()
    print(f'time elapsed: {t1-t0} seconds')
    print()
# %%
