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


def parseProjFiles(proj_folder:str, df):
    '''
    receives a df of project data files built in ui
    checks for or creates project parsed files folder
    parses each file, that is not already parsed by name
    optional: checks if file is already parsed by checksums
    saves parsed file into project parsed files folder
    get proj_folder from ui self.project_folder
    '''
    print(f"proj folder: {proj_folder}")
    
    # check for files in the folder.
    list_metadatafiles = [
        i for i in os.listdir(dir_gen_data) if -1 < i.find("_mean.csv")
    ]
    
    # list found files
    print(list_metadatafiles)
    
    # remove the found files from the parse que
    
    # start parsing the que
    
    # show progress
        