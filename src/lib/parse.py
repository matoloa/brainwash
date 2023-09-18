# %%
import os  # speak to OS (list dirs)
from pathlib import Path

import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw

from tqdm.notebook import tqdm
from joblib import Memory

memory = Memory("../cache", verbose=1)

verbose = True

# set some working folders
# TODO: set as globals?
# TODO: get project root. this will not work now
dir_project_root = Path(os.getcwd().split("notebook")[0])
dir_source_data = dir_project_root / "dataSource" / "Lactate_2022_abf"
dir_gen_data = dir_project_root / "dataGenerated"


def buildexperimentcsv(dir_gen_data):
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
def importabf(filepath):
    """
    import .abf and return dataframe with proper SI units
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
    df["voltage"] = df.sweepY / 1000  # mv to V
    # Absolute date and time
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (abf.abfDateTime - pd.to_datetime(0))
    df.drop(columns=["sweepX", "sweepY", "timens"], inplace=True)
    return df


# %%
def importabffolder(folderpath):
    """
    Read, sort (by filename) and concatenate all .abf files in folderpath to a single df
    """
    list_files = sorted([i for i in os.listdir(folderpath) if -1 < i.find(".abf")])  # [:2] # stop before item 2 [begin:end]
    if verbose:
        print(f"list_files: {list_files}")
    listdf = []
    for filename in list_files:
        df = importabf(folderpath / filename)
        listdf.append(df)
    df = pd.concat(listdf)
    df.reset_index(drop=True, inplace=True)
    # Check first timestamp in each df, verify correct sequence, raise error
    df['datetime'] = pd.to_datetime(df.datetime)
    return df


# %%
def builddfmean(df, rollingwidth=3):
    # TODO: is rollingwidth "radius" or "diameter"?
    """
    dfmean.voltate(V) (a single sweep built on the mean of all time)
    dfmean.prim
    dfmean.bis

    dfabf.pivot(columns='time', index='sweep', values='voltage').mean(axis=0).plot()

    """
    dfs = []
    for channel in df.channel.unique():
        for stim in df.stim.unique():
            # pivot is useful, learn it
            dfmean = pd.DataFrame(df[(df.channel == 0) & (df.stim == 'a')].pivot(columns="time", index="sweep", values="voltage").mean())
            dfmean.columns = ["voltage"]
            dfmean.voltage -= dfmean.voltage.median()
        
            # generate diffs
            dfmean["prim"] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
            dfmean["bis"] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()
            # tag
            dfmean['channel'] = channel
            dfmean['stim'] = stim
            dfs.append(dfmean)
    dfmean = pd.concat(dfs).reset_index(drop=True)
    return dfmean


def assignStimAndsweep(df_data, list_stims):
    # sets stim-column, sorts df_data and builds new dfmean
    if verbose:
        print(f" - assignStimAndsweep, channels:{df_data.channel.unique()}, list_stims: {list_stims}")
    dfs = []
    for channel in df_data.channel.unique():
        df = df_data[df_data.channel==channel].copy()
        nstims = len(list_stims)
        '''
        if nstims == 1:
            for i, t0 in enumerate(df.t0.unique()):
                idf = df[df.t0 == t0].copy() #iterating df
                idf['sweep'] = i
                idf['stim'] = list_stims[0]
                dfs.append(idf)
            df = pd.concat(dfs).reset_index(drop=True)
            return df
        else:
        '''
        df['stim'] = ''
        sweeplength = df.time.nunique()
        df['sweep'] = df.index.to_numpy() // sweeplength
        for i, stim in enumerate(list_stims):
            df.loc[df.index % nstims == i, 'stim'] = stim
        dfs.append(df)
    df_assigned = pd.concat(dfs).reset_index(drop=True)
    return df_assigned


def persistdf(recording_name, proj_folder, dfdata=None, dfmean=None):
    savepath = str(Path(proj_folder) / recording_name)
    if dfdata is not None:
        dfdata.to_csv(savepath + ".csv", index=False)
    if dfmean is not None:
        dfmean.to_csv(savepath + "_mean.csv", index=False)


def parseProjFiles(proj_folder: Path, df=None, recording_name=None, source_path=None, single_stim=False):
    """
    * receives a df of project data file paths built in ui
        files that are already parsed are to be overwritten (ui.py passes filitered list of unparsed files)
    * checks for or creates project parsed files folder
    * parses each file by source path
    * adds columns: channel, stim (default a and b), sweep (0-max for each channel-stim combo)
    * fetches proj_folder from ui self.project_folder
    * saves a parsed file into project parsed files folder as .csv
    
    returns a dict of channels and stims, used by ui.py to split a single file with multiple channels

    NTH: checks if file is already parsed by checksums
    calls builddfmean() to create an average, prim and bis file, per channel-stim combo
    """

    def parser(proj_folder, recording_name, source_path):
        if verbose:
            print(f" - parser, source_path: {source_path}")
        if Path(source_path).is_dir():
            df = importabffolder(folderpath=Path(source_path))
        else:
            df = importabf(filepath=Path(source_path))
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

        df = assignStimAndsweep(df_data = df, list_stims=list_stims)
        dfmean = builddfmean(df)
        persistdf(recording_name, proj_folder, dfdata=df, dfmean=dfmean)

        # TODO: every channel:stim combo counts sweeps from 0 to max
        # TODO: is the above done? MATS?
        dictmeta = {'channel': df.channel.unique(), 'stim': df.stim.unique(), 'nsweeps': df.sweep.nunique()}
        return dictmeta

    if verbose:
        print(f"proj folder: {proj_folder}")
    if source_path is not None:
        print(f"recording_name: {recording_name}")
        print(f"source_path: {source_path}")
    if df is not None:
        print(f"recording_name: {df['recording_name']}")
        print(f"path: {df['path']}")

    # check for files in the folder.
    path_proj_folder = Path(proj_folder)
    path_proj_folder.mkdir(exist_ok=True)  # Try to make a folder

    # list_existingfiles = [
    #    i for i in path_proj_folder.iterdir() if -1 < i.find("_mean.csv")
    # ]
    # list found files
    # print(list_existingfiles)
    # remove the found files from the parse que
    if recording_name is not None:
        dictmeta = parser(proj_folder, recording_name=recording_name, source_path=source_path)
        return dictmeta

    if df is not None:
        df_unique_names = df.drop_duplicates(subset='recording_name')
        for i, row in df_unique_names.iterrows():
            recording_name = row['recording_name']
            source_path = row['path']
            dictmeta = parser(proj_folder, recording_name=recording_name, source_path=source_path)
        return dictmeta

# Path.is_dir to check if folder or file
# start parsing the queue
# show progress


# %%
if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux

    source_folder = Path.home() / "Documents/Brainwash Data Source/"
    proj_folder = Path.home() / "Documents/Brainwash Projects/standalone_test"
    list_sources = [str(source_folder / "abf 1 channel/A_21_P0701-S2/2022_07_01_0012.abf"),
                    str(source_folder / "abf 2 channel/KO_02/2022_01_24_0000.abf")]
    for _ in range(3):
        print()
    print("", "*** parse.py standalone test: ***")
    for item in list_sources:
        recording_name = os.path.basename(os.path.dirname(item))
        print(" - processing", item, "as recording_name", recording_name)
        df_files = pd.DataFrame({"path": [item], "recording_name": [recording_name]})
        dictmeta = parseProjFiles(proj_folder=proj_folder, df=df_files)
        print(f" - dictmeta: {dictmeta}")
        print()