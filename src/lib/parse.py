# %%
import numpy as np  # numeric calculations module
import pandas as pd  # dataframe module, think excel, but good
import os  # speak to OS (list dirs)
import matplotlib.pyplot as plt  # plotting
import seaborn as sns  # plotting
import pyabf  # read data files atf, abf
from neo import io  # read data files ibw
import scipy  # peakfinder and other useful analysis tools
from tqdm.notebook import tqdm
from pathlib import Path
from sklearn import linear_model
from joblib import Memory

memory = Memory("../cache", verbose=1)

verbose = True

# set some working folders
#TODO: set as globals?
#TODO: get project root. this will not work now
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
    list_metadatafiles = [
        i for i in os.listdir(dir_gen_data) if -1 < i.find("_metadata.txt")
    ]
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
    if verbose: print(f"abf.channelCount: {channels}")
    if verbose: print(f"abf.sweepCount): {sweeps}")
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
    df["time"] = df.sweepX  # / abf.sampleRate
    df["voltage"] = df.sweepY / 1000

    # Absolute date and time
    df["timens"] = (df.t0 + df.time) * 1_000_000_000  # to nanoseconds
    df["datetime"] = df.timens.astype("datetime64[ns]") + (
        abf.abfDateTime - pd.to_datetime(0)
    )
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

    # Create and return one df per channel
    df.drop(columns=["sweepX", "sweepY", "timens"], inplace=True)

    return df

# %%
def importabffolder(folderpath):
    """
    Read and concatenate all .abf files in folderpath to a single df
    """
    list_files = [
        i for i in os.listdir(folderpath) if -1 < i.find(".abf")
    ]  # [:2] # stop before item 2 [begin:end]
    # print(list_files)
    listdf = []
    maxsweep = 0
    for filename in list_files:
        df = importabf(folderpath / filename)
        df["sweep"] = df.sweep_raw + maxsweep + 1
        maxsweep = df.sweep.max()
        listdf.append(df)

    # Check first timestamp in each df, very correct sequence, raise error
    df = pd.concat(listdf)
    # df.drop(columns=['sweep_raw'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
# %%

def builddfmean(df, rollingwidth=3):
    """
    dfmean.voltate(V) (a single sweep built on the mean of all time)
    dfmean.prim
    dfmean.bis

    dfabf.pivot(columns='time', index='sweep', values='voltage').mean(axis=0).plot()

    """

    # pivot is useful, learn it
    dfmean = pd.DataFrame(
        df.pivot(columns="time", index="sweep", values="voltage").mean()
    )
    dfmean.columns = ["voltage"]
    dfmean.voltage -= dfmean.voltage.median()

    # generate diffs, *5 for better visualization
    dfmean["prim"] = dfmean.voltage.diff().rolling(rollingwidth, center=True).mean() * 5
    dfmean["bis"] = dfmean.prim.diff().rolling(rollingwidth, center=True).mean() * 5

    return dfmean


def parseProjFiles(proj_folder:Path, df=None, row=None):
    '''
    receives a df of project data files built in ui
    checks for or creates project parsed files folder
    parses each file, that is not already parsed by name
    optional: checks if file is already parsed by checksums
    saves parsed file into project parsed files folder
    get proj_folder from ui self.project_folder

    calls builddfmean to create an average, prim and bis file
    '''
    def parser(proj_folder, row):
        if verbose: print(f"row: {row}")
        if Path(row.path).is_dir():
            df2parse = importabffolder(folderpath=Path(row.path))
        else:
            df2parse = importabf(filepath=Path(row.path))
        
        if verbose: print(f"df2parse['channel'].nunique(): {df2parse['channel'].nunique()}")

        for i in df2parse['channel'].unique():
            # Create unique filename for current channel, if there are more than one
            if(df2parse['channel'].nunique() == 1):
                save_file_name = row.save_file_name
                savepath = str(Path(proj_folder) / save_file_name)
                df = df2parse
            else:
                save_file_name_channel = row.save_file_name + "_ch_" + str(i)
                savepath = str(Path(proj_folder) / save_file_name_channel)
                # save ONLY active channel as filename
                df = df2parse[df2parse.channel==i]
            df.to_csv(savepath + '.csv', index=False)
            # df.drop(columns=["channel"]).to_csv(savepath + '.csv', index=False) # use after verification
            if verbose:
                print(f"df2parse: {df2parse}")
                print(f"df: {df}")
            dfmean = builddfmean(df)
            dfmean.to_csv(savepath + '_mean.csv', index=False)
            if verbose:
                print(f"frame has channel: {i}")
                print(f"df: {df}")
                print(f"df['sweep'].values[-1]: {df['sweep'].values[-1]}")
        return df['sweep'].values[-1]
    
    if verbose: print(f"proj folder: {proj_folder}")
    if row is not None:
        print(f"save_file_name: {row['save_file_name']}")
        print(f"path: {row['path']}")
    if df is not None:
        print(f"save_file_name: {df['save_file_name']}")
        print(f"path: {df['path']}")
    
    # check for files in the folder.
    path_proj_folder = Path(proj_folder)
    path_proj_folder.mkdir(exist_ok=True) # Try to make a folder

    #list_existingfiles = [
    #    i for i in path_proj_folder.iterdir() if -1 < i.find("_mean.csv")
    #]
    # list found files
    #print(list_existingfiles)
    # remove the found files from the parse que
    if row is not None:
        nSweeps = parser(proj_folder, row)
        return {'nSweeps': nSweeps}

    if df is not None:
        for i, row in df.iterrows():
            nSweeps = parser(proj_folder, row)

    

# Path.is_dir to check if folder or file
    # start parsing the que
    # show progress



if __name__ == "__main__": #hardcoded testbed to work with Brainwash Data Source 2023-05-12 on Linux
    # Single channel .abf test
    standalone_test_source = "/home/matolo/Documents/Brainwash Data Source/abf 1 channel/A_21_P0701-S2"
    standalone_test_output = "A_21"
    # dual channel .abf test
    # standalone_test_source = "/home/matolo/Documents/Brainwash Data Source/abf 2 channel/KO_02"
    # standalone_test_output = "KO_02"
    proj_folder = Path.home()/"Documents/Brainwash Projects/standalone_test"
    print("Placeholder: standalone test, processing", standalone_test_source, "as save_file_name", standalone_test_output)
    
    dffiles = pd.DataFrame({"path": [standalone_test_source], "save_file_name": [standalone_test_output]})
    parseProjFiles(proj_folder=proj_folder, df=dffiles)

# %%
