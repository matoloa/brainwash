# first line: 1
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
    if verbose: print(f"abf.channelCount: {channels}")
    if verbose: print(f"abf.sweepCount): {sweeps}")
    if verbose: print(f"abf.sampleRate): {sampling_Hz}")
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
    df["voltage"] = df.sweepY / 1000 # mv to V

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
