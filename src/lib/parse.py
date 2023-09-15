# %%
import os  # speak to OS (list dirs)
from pathlib import Path

import pandas as pd  # dataframe module, think excel, but good
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw

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
    import .abf and return dataframe wiht proper SI units
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
            df["sweep_raw"] = i
            df["t0"] = abf.sweepTimesSec[i]
            df["channel"] = j
            dfs.append(df)
    df = pd.concat(dfs)
    df["sweep"] = df.sweep_raw  # relevant for single file imports
    # Convert to SI
    df["time"] = df.sweepX  # time in seconds from start of sweep recording
    df["voltage"] = df.sweepY / 1000  # mv to V
    # Absolute date and time
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (abf.abfDateTime - pd.to_datetime(0))
    """
    if not channel in abf.channelList:
        raise ValueError(f"No channel {channel} in {filepath}")
    if oddeven is None:
        if channel == 0:
            oddeven = "odd"
        else:
            oddeven = "even"

    # Odd / Even sweep inclusion
    df["even"] = df.sweep_raw.apply(lambda x: x % 2 == 0)
    df["oddeven"] = df.even.apply(lambda x: "even" if x else "odd")
    df = df[df.oddeven == oddeven]  # filter rows by Boolean
    df.drop(columns=["sweepX", "sweepY", "even", "oddeven", "timens"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    """

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
    maxsweep = 0
    for filename in list_files:
        df = importabf(folderpath / filename)
        df["sweep"] = df.sweep_raw + maxsweep + 1
        maxsweep = df.sweep.max()
        listdf.append(df)
    df = pd.concat(listdf)
    df.reset_index(drop=True, inplace=True)
    # Check first timestamp in each df, verify correct sequence, raise error
    df['datetime'] = pd.to_datetime(df.datetime)
    if df.datetime.is_monotonic_increasing:
        if verbose:
            print(f"Datetime check: {df.datetime.is_monotonic_increasing}")
    else:
        raise Exception("importabffolder: files not concatenated in chronological order.")
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

    # pivot is useful, learn it
    dfmean = pd.DataFrame(df.pivot(columns="time", index="sweep", values="voltage").mean())
    dfmean.columns = ["voltage"]
    dfmean.voltage -= dfmean.voltage.median()

    # generate diffs
    dfmean["prim"] = dfmean.voltage.rolling(rollingwidth, center=True).mean().diff()
    dfmean["bis"] = dfmean.prim.rolling(rollingwidth, center=True).mean().diff()

    return dfmean


def parseProjFiles(proj_folder: Path, df=None, recording_name=None, source_path=None):
    """
    receives a df of project data files built in ui
    checks for or creates project parsed files folder
    parses each file, that is not already parsed by name
    saves parsed file into project parsed files folder
    get proj_folder from ui self.project_folder
    returns a dict of channels, used by ui to split a single file with multiple channels

    NTH: checks if file is already parsed by checksums

    calls builddfmean to create an average, prim and bis file
    """

    def parser(proj_folder, recording_name, source_path):
        if verbose:
            print(f"parser, source_path: {source_path}")
        if Path(source_path).is_dir():
            df2parse = importabffolder(folderpath=Path(source_path))
        else:
            df2parse = importabf(filepath=Path(source_path))

        if verbose:
            print(f"df2parse['channel'].nunique(): {df2parse['channel'].nunique()}")

        dict_channels = {}
        for i in df2parse["channel"].unique():
            # Create unique filename for current channel, if there are more than one
            if df2parse["channel"].nunique() == 1:
                savepath = str(Path(proj_folder) / recording_name)
                df = df2parse
            else:
                recording_name_channel = recording_name + "_ch_" + str(i)
                savepath = str(Path(proj_folder) / recording_name_channel)
                # save ONLY active channel as filename
                df = df2parse[df2parse.channel == i]
            df.to_csv(savepath + ".csv", index=False)
            # df.drop(columns=["channel"]).to_csv(savepath + '.csv', index=False) # use after verification
            #if verbose:
                #print(f"df2parse: {df2parse}")
                #print(f"df: {df}")
            dfmean = builddfmean(df)
            dfmean.reset_index().to_csv(savepath + "_mean.csv", index=False)
            dict_channels[str(i)] = df["sweep"].nunique()
            # dict_channels[str(i)] = df['sweep'].values[-1]
            if verbose:
                print(f"frame has channel: {i}")
                #print(f"df: {df}")
                print(f"dict_channels: {dict_channels}")
        return dict_channels
        # return df['sweep'].values[-1] # rendered obsolete by dict return for multi-channel recordings

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
        nSweeps = parser(proj_folder, recording_name=recording_name, source_path=source_path)
        return nSweeps

    if df is not None:
        df_unique_names = df.drop_duplicates(subset='recording_name')
        for i, row in df_unique_names.iterrows():
            recording_name = row['recording_name']
            source_path = row['path']
            nSweeps = parser(proj_folder, recording_name=recording_name, source_path=source_path)
# Path.is_dir to check if folder or file
# start parsing the que
# show progress


if __name__ == "__main__":  # hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux
    # Single channel .abf test
    # standalone_test_source = "/home/matolo/Documents/Brainwash Data Source/abf 1 channel/A_21_P0701-S2"
    # standalone_test_output = "A_21"
    # dual channel .abf test
    standalone_test_source = str(Path.home() / "Documents/Brainwash Data Source/abf 1 channel/A_21_P0701-S2")
    standalone_test_output = "A_21"
    proj_folder = Path.home() / "Documents/Brainwash Projects/standalone_test"
    print("Placeholder: standalone test, processing", standalone_test_source, "as recording_name", standalone_test_output)
    
    dffiles = pd.DataFrame({"path": [standalone_test_source], "recording_name": [standalone_test_output]})
    parseProjFiles(proj_folder=proj_folder, df=dffiles)

