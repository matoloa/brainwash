# %%
import os  # speak to OS (list dirs)
from pathlib import Path

import numpy as np
import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
import igor2 as igor # read data files ibw

from tqdm import tqdm
from joblib import Memory
from joblib import Parallel, delayed
import time

memory = Memory("../cache", verbose=1)

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


def parse_abf(filepath):
    """
    read .abf and return dataframe with proper SI units
    """
    # parse abf
    abf = pyabf.ABF(filepath)
    #with open(filepath, "r+b") as f:
    #    mmap_file=mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    #    abf = pyabf.ABF(mmap_file)
    channels = range(abf.channelCount)
    sweeps = range(abf.sweepCount)
    sampling_Hz = abf.sampleRate
    n_rows_in_channel = len(abf.getAllXs()) # defaults to 0
    if verbose:
        print(f"abf.channelCount: {channels}")
        print(f"abf.sweepCount): {sweeps}")
        print(f"abf.sampleRate): {sampling_Hz}")
        print (f"n_rows_in_channel {n_rows_in_channel}")

    # build df
    dfs = []
    for j in channels:
        sweepX = np.tile(abf.getAllXs(j)[:abf.sweepPointCount], abf.sweepCount)
        t0 = np.repeat(abf.sweepTimesSec, len(sweepX) // abf.sweepCount)
        sweepY = abf.getAllYs(j)
        df = pd.DataFrame({"sweepX": sweepX, "sweepY": sweepY, "t0": t0})
        df['channel'] = j
        dfs.append(df)
    df = pd.concat(dfs)
    # Convert to SI
    df['time'] = df.sweepX  # time in seconds from start of sweep recording
    df['voltage_raw'] = df.sweepY / 1000  # mv to V
    # Absolute date and time
    df['timens'] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df['datetime'] = df.timens.astype("datetime64[ns]") + (abf.abfDateTime - pd.to_datetime(0))
    df.drop(columns=['sweepX', 'sweepY', 'timens'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


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
    df.columns = np.round(np.arange(7500) * timestep, int(-np.log(timestep))).tolist()
    df = df.stack().reset_index()
    df.columns = ['t0', 'time', 'voltage_raw']
    df.t0 = df.t0.astype("float64")
    df.time = df.time.astype("float64")
    df['datetime'] = pd.to_datetime((measurement_start + df.t0 + df.time), unit="s").round("us")
    df['channel'] = 0

    return df


# %%
def build_dfmean(dfdata, rollingwidth=3):
    # TODO: is rollingwidth "radius" or "diameter"?
    dfmean = pd.DataFrame(dfdata.pivot(columns='time', index='sweep', values='voltage_raw').mean())
    dfmean.columns = ['voltage']
    # generate diffs
    dfmean['prim'] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
    dfmean['bis'] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()
    # find index of stimulus artifact (this requires and index)
    dfmean.reset_index(inplace=True)
    i_stim = dfmean.prim.idxmax()
    y_stim = dfmean.prim.max()
    threshold = y_stim*0.9
    min_time_difference = 0.005  # Minimum time difference 5ms TODO: hardcoded
    # Find the indices where 'prim' is above the threshold
    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    # Filter the indices to ensure they are more than min_time_difference apart
    filtered_indices = [above_threshold_indices[0]]
    for i in range(1, len(above_threshold_indices)):
        if dfmean['time'][above_threshold_indices[i]] - dfmean['time'][above_threshold_indices[i - 1]] > min_time_difference:
            filtered_indices.append(above_threshold_indices[i])
    n_stim = len(filtered_indices)
    print(f"build_dfmean found {len(above_threshold_indices)} above_threshold_indices in {n_stim} unique stims.")
    if n_stim == 1:
        # subtract median of 20-5 samples before stimulus artifact
        median = dfmean['voltage'].iloc[i_stim-20:i_stim-5].median() # TODO: hardcoded 20 and 5
        #print(f"dfmean BEFORE subtract: {dfmean}")
        dfmean['voltage'] = dfmean['voltage'] - median
        #print(f"dfmean AFTER subtract: {dfmean}")
    else:
        raise ValueError(f"build_dfmean found {n_stim} stimulus artifacts. Expected 1.")
    return dfmean

def zeroSweeps(dfdata, dfmean):
    #print(f"dfdata BEFORE subtract: {dfdata}")
    i_stim = dfmean.prim.idxmax()
    df_zeroed = dfdata.copy()
    dfpivot = df_zeroed.pivot(index='sweep', columns='time', values='voltage_raw')
    sermedians = dfpivot.iloc[:, i_stim-20:i_stim-5].median(axis=1) # TODO: hardcoded 20 and 5
    dfpivot = dfpivot.subtract(sermedians, axis='rows')
    df_zeroed['voltage'] = dfpivot.stack().reset_index().sort_values(by=['sweep', 'time'])[0].values
    df_zeroed.drop(columns=['voltage_raw', 'sweep_raw', 't0', 'datetime'], inplace=True)
    return df_zeroed

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


def parseProjFiles(dict_folders, df=None, recording_name=None, source_path=None, single_stim=False):
    """
    * receives a df of project data file paths built in ui
        files that are already parsed are to be overwritten (ui.py passes filitered list of unparsed files)
    * checks for or creates project parsed files folder
    * creates a datafile by unique source file/channel/stim combination
    * Stim defaults to a and b
    * saves two files:
        dict_folders['data']<recording_name>_Ch<Ch>_<Stim>.csv
        dict_folders['cache']<recording_name>_Ch<Ch>_<Stim>_dfmean.csv
    
    returns a list of <recording_name>_Ch<Ch>_<Stim> for updating df_project recording names

    NTH: checks if file is already parsed by checksums
    calls build_dfmean() to create an average, prim and bis file, per channel-stim combo
    """
    def parser(dict_folders, recording_name, source_path):
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
        sweeplength = df.time.nunique()

        # TODO: Why is this copied?
        dfcopy = df.copy()
        dfcopy = dfcopy.sort_values(by=['datetime', 'channel']).reset_index(drop=True)
        dfcopy['sweep_raw'] = dfcopy.index.to_numpy() // (sweeplength * nchannels)
        dict_data = {}

        for channel in dfcopy.channel.unique():
            df_ch = dfcopy[dfcopy.channel==channel]
            for i, stim in enumerate(list_stims):
                file_base = f"{recording_name}_Ch{channel}_{stim}"
                print(f"file_base: {file_base}")
                if filetype == "abf": # split df by % nstims
                    df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
                    df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
                elif filetype == "ibw": # split df; time < 0.5 is stim a, time >= 0.5 is stim b
                    if stim == "a":
                        df_ch_st = dfcopy.loc[dfcopy.time < 0.25].copy()
                    if stim == "b":
                        df_ch_st = dfcopy.loc[dfcopy.time >= 0.5].copy()  
                    df_ch_st['sweep'] = df_ch_st.sweep_raw
                df_ch_st.drop(columns=['channel'], inplace=True)
                print(f"nunique: {df_ch_st['sweep'].nunique()}")
                dfmean = build_dfmean(df_ch_st)
                dffilter = zeroSweeps(dfdata=df_ch_st, dfmean=dfmean)
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=df_ch_st, dfmean=dfmean, dffilter=dffilter)
                # Build dict: keys are datafile names, values are a dict of nsweeps, channels, stim, and reset (the first sweep number after every sweep_raw reset: finds recording breaks for display purposes)
                dict_sub = {
                    'nsweeps': df_ch_st['sweep'].nunique(),
                    'channel': channel,
                    'stim': stim,
                    'reset': df_ch_st[(df_ch_st['sweep_raw'] == df_ch_st['sweep_raw'].min()) & (df_ch_st['time'] == 0)]['sweep'].tolist()[1:]
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


# %%
if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux

    source_folder = Path.home() / "Documents/Brainwash Data Source/"
    dict_folders = {'project': Path.home() / "Documents/Brainwash Projects/standalone_test"}
    dict_folders['data'] = dict_folders['project'] / "data"
    dict_folders['cache'] = dict_folders['project'] / "cache"
    dict_folders['project'].mkdir(exist_ok=True)
    #list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2"), str(source_folder / "abf 2 channel/KO_02")]
    #list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"), str(source_folder / "abf 2 channel/KO_02/2022_01_24_0020.abf")]
    list_sources = [str(source_folder / "ibw 2 events/L11S2")]
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
        df_files = pd.DataFrame({"path": [item], "recording_name": [recording_name]})
        dict_data_nsweeps = parseProjFiles(dict_folders=dict_folders, df=df_files)
        print(f" - dict_data_nsweeps: {dict_data_nsweeps}") # what the parsed file turned into
    t1 = time.time()
    print(f'time elapsed: {t1-t0} seconds')
    print()