# first line: 1
@memory.cache
def importAbf(filepath, channel=0, oddeven=None):
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
