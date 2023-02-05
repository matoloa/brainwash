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
def importabf(filepath, channel=0, oddeven=None):
    """
    import .abf and return <"odd"/"even"/"all"> sweeps from channel <0/1>
    oddeven defaults to channel-appropriate parameter
    """

    # parse abf
    abf = pyabf.ABF(filepath)

    if not channel in abf.channelList:
        raise ValueError(f"No channel {channel} in {filepath}")
    if oddeven is None:
        if channel == 0:
            oddeven = "odd"
        else:
            oddeven = "even"

    sweeps = range(abf.sweepCount)

    dfs = []
    for i in sweeps:
        # get data
        abf.setSweep(sweepNumber=i, channel=channel)
        df = pd.DataFrame({"sweepX": abf.sweepX, "sweepY": abf.sweepY})
        df["sweep_raw"] = i
        df["t0"] = abf.sweepTimesSec[i]
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

    # Odd / Even sweep inclusion
    df["even"] = df.sweep_raw.apply(lambda x: x % 2 == 0)
    df["oddeven"] = df.even.apply(lambda x: "even" if x else "odd")
    df = df[df.oddeven == oddeven]  # filter rows by Boolean
    df.drop(columns=["sweepX", "sweepY", "even", "oddeven", "timens"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def importabffolder(folderpath, channel=0):
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
        df = importabf(folderpath / filename, channel=channel)
        df["sweep"] = df.sweep_raw + maxsweep
        maxsweep = df.sweep.max()
        listdf.append(df)

    # Check first timestamp in each df, very correct sequence, raise error
    df = pd.concat(listdf)
    # df.drop(columns=['sweep_raw'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


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


def parseProjFiles(proj_folder:Path, df):
    '''
    receives a df of project data files built in ui
    checks for or creates project parsed files folder
    parses each file, that is not already parsed by name
    optional: checks if file is already parsed by checksums
    saves parsed file into project parsed files folder
    get proj_folder from ui self.project_folder

    calls builddfmean to create an average, prim and bis file
    '''
    print(f"proj folder: {proj_folder}")
    print(f"save_file_name: {df['save_file_name']}")
    print(f"path: {df['path']}")
    
    # check for files in the folder.
    path_proj_folder = Path(proj_folder)
    path_proj_folder.mkdir(exist_ok=True) # Try to make a folder, error if it exists

    #list_existingfiles = [
    #    i for i in path_proj_folder.iterdir() if -1 < i.find("_mean.csv")
    #]
    # list found files
    #print(list_existingfiles)
    # remove the found files from the parse que

    for i, row in df.iterrows():
        if verbose: print(f"row: {row}")
        if Path(row.path).is_dir():
            df2parse = importabffolder(folderpath=Path(row.path))
        else:
            df2parse = importabf(filepath=Path(row.path))
        savepath = str(Path(proj_folder) / row.save_file_name)
        df2parse.to_csv(savepath + '.csv', index=False)
        dfmean = builddfmean(df2parse)
        dfmean.to_csv(savepath + '_mean.csv', index=False)

# Path.is_dir to check if folder or file

    # start parsing the que
        

    # show progress



if __name__ == "__main__":
    print("Placeholder: standalone test")
    proj_folder = Path("C:\\Users\\Mats\\Documents\\Brainwash Projects")
    #clearTemp(Path("C:\\Users\\Mats\\Documents\\Lactate 5 LTP\\DG"))
    df = pd.DataFrame({"path": ["C:\\Users\\Mats\\Documents\\Source\\Longo Ventral.abf\\Males\\A_13_P0629-S5\\LTP",
                                "C:\\Users\\Mats\\Documents\\Source\\Longo Ventral.abf\\Males\\A_21_P0701-S2\\LTP"],
                       "save_file_name": ["A13", "A21"]})
    parseProjFiles(proj_folder=proj_folder, df=df)