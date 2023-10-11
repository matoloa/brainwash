# %%
import os  # speak to OS (list dirs)
from pathlib import Path

import numpy as np
import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw

from tqdm import tqdm
from joblib import Memory

memory = Memory("../cache", verbose=1)

verbose = True

# set some working folders
# TODO: set as globals?
# TODO: get project root. this will not work now
dir_project_root = Path(os.getcwd().split("notebook")[0])
dir_source_data = dir_project_root / "dataSource" / "Lactate_2022_abf"
dir_gen_data = dir_project_root / "dataGenerated"


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


@memory.cache
def parse_abf(filepath):
    """
    read .abf and return dataframe with proper SI units
    """
    # parse abf
    abf = pyabf.ABF(filepath)

    channels = range(abf.channelCount)
    sweeps = range(abf.sweepCount)
    sampling_Hz = abf.sampleRate
    if verbose:
        print(f"abf.channelCount: {channels}")
        print(f"abf.sweepCount): {sweeps}")
        print(f"abf.sampleRate): {sampling_Hz}")
    dfs = []
    for j in channels:
        for i in sweeps:
            # get data
            abf.setSweep(sweepNumber=i, channel=j)
            df = pd.DataFrame({"sweepX": abf.sweepX, "sweepY": abf.sweepY})
            #df["sweep_raw"] = i #TODO: do we need this?
            df["t0"] = abf.sweepTimesSec[i]
            df["channel"] = j
            dfs.append(df)
    df = pd.concat(dfs)
    # Convert to SI
    df["time"] = df.sweepX  # time in seconds from start of sweep recording
    df["voltage_raw"] = df.sweepY / 1000  # mv to V
    # Absolute date and time
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (abf.abfDateTime - pd.to_datetime(0))
    df.drop(columns=["sweepX", "sweepY", "timens"], inplace=True)
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

# %%
def build_dfmean(dfdata, rollingwidth=3):
    # TODO: is rollingwidth "radius" or "diameter"?
    dfmean = pd.DataFrame(dfdata.pivot(columns='time', index='sweep', values='voltage_raw').mean())
    dfmean.columns = ['voltage']
    # generate diffs
    dfmean["prim"] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
    dfmean["bis"] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()
    # find index of stimulus artifact (this requires and index)
    dfmean.reset_index(inplace=True)
    i_stim = dfmean.prim.idxmax()
    median = dfmean['voltage'].iloc[i_stim-20:i_stim-5].median() # TODO: hardcoded 20 and 5
    #print(f"median: {median}")
    #print(f"dfmean BEFORE subtract: {dfmean}")
    dfmean['voltage'] = dfmean['voltage'] - median
    #print(f"dfmean AFTER subtract: {dfmean}")
    return dfmean

def zeroSweeps(dfdata, dfmean):
    #print(f"dfdata BEFORE subtract: {dfdata}")
    i_stim = dfmean.prim.idxmax()
    dfpivot = dfdata.pivot(index='sweep', columns='time', values='voltage_raw')
    sermedians = dfpivot.iloc[:, i_stim-20:i_stim-5].median(axis=1) # TODO: hardcoded 20 and 5
    #print(f"sermedians: {sermedians}")
    dfpivot = dfpivot.subtract(sermedians, axis='rows')
    dfdata['voltage'] = dfpivot.stack().reset_index().sort_values(by=['sweep', 'time'])[0].values
    #print(f"dfdata AFTER subtract: {dfdata}")
    df_zeroed = dfdata
    return df_zeroed

def persistdf(file_base, dict_folders, dfdata=None, dfmean=None):
    if dfdata is not None:
        dict_folders['data'].mkdir(exist_ok=True)
        str_data_path = f"{dict_folders['data']}/{file_base}.csv"
        dfdata.to_csv(str_data_path, index=False)
    if dfmean is not None:
        dict_folders['cache'].mkdir(exist_ok=True)
        str_mean_path = f"{dict_folders['cache']}/{file_base}_mean.csv"
        dfmean.to_csv(str_mean_path, index=False)


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
            df = parse_abfFolder(folderpath=Path(source_path))
        else:
            df = parse_abf(filepath=Path(source_path))
        if verbose:
            print(f" - - df['channel'].nunique(): {df['channel'].nunique()}")

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
        dfcopy = df.copy()
        dfcopy = dfcopy.sort_values(by=['datetime', 'channel']).reset_index(drop=True)
        dfcopy['sweep_raw'] = dfcopy.index.to_numpy() // (sweeplength * nchannels)
        dict_data_nsweeps = {}
        for channel in dfcopy.channel.unique():
            df_ch = dfcopy[dfcopy.channel==channel]
            for i, stim in enumerate(list_stims):
                file_base = f"{recording_name}_Ch{channel}_{stim}"
                print(f"file_base: {file_base}")
                df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
                df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
                dfmean = build_dfmean(df_ch_st)
                dfdata = zeroSweeps(dfdata=df_ch_st, dfmean=dfmean)
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=dfdata, dfmean=dfmean)
                dict_data_nsweeps[f"{recording_name}_Ch{channel}_{stim}"] = dfdata.sweep.nunique()
        return dict_data_nsweeps

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
    list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2"),
                    str(source_folder / "abf 2 channel/KO_02")]
#    list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"),
#                    str(source_folder / "abf 2 channel/KO_02/2022_01_24_0000.abf")]
    for _ in range(3):
        print()
    print("", "*** parse.py standalone test: ***")
    for item in tqdm(list_sources):
        if Path(item).is_dir():
            recording_name = os.path.basename(item)
        else:
            recording_name = os.path.basename(os.path.dirname(item))
        print(" - processing", item, "as recording_name", recording_name)
        df_files = pd.DataFrame({"path": [item], "recording_name": [recording_name]})
        dict_data_nsweeps = parseProjFiles(dict_folders=dict_folders, df=df_files)
        print(f" - dict_data_nsweeps: {dict_data_nsweeps}") # what the parsed file turned into
        print()

'''

# %%
if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux

    item = list_sources[0]
    recording_name = os.path.basename(os.path.dirname(item))
    df = pd.read_csv(str(proj_folder / (recording_name + '.csv')))
    repo_root = Path.home() / "code/brainwash"
    source_folder = repo_root / "src/lib/test_data"
    list_sources = [str(source_folder / "A_21_P0701-S2/2022_07_01_0012.abf.gitkeep"), str(source_folder / "KO_02/2022_01_24_0000.abf.gitkeep")]


# %%
if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux

    df = parse_abf(filepath=Path(list_sources[1]))
    sweeplength = df.time.nunique()
    df.index.to_numpy()
    dfss = assignStimAndSweep(df, list_stims=['a', 'b', 'c', 'd'])
    print(dfss)

# %%Import_x should be parse, not “import”.
if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux

    dfvc = dfss[['stim', 'sweepraw']].value_counts()
    dfvc.sort_index(inplace=True)
    print(dfvc)
'''
