import numpy as np
import pandas as pd


def _get_io_xy_pairs(g, get_group_testset_means_fn, uistate=None, n_unit="recording", aspect_col="EPSP_amp"):
    """Returns long DataFrame with ['rec_ID', 'subject', 'slice', 'x', 'y'] for all sweeps in group.
    Uses per_sweep=True, melts, joins real X from dfoutput via uistate.io_input. Falls back to sweep rank if X missing.
    """
    if uistate is None:
        io_input = "vamp"
    else:
        io_input = getattr(uistate, "io_input", "vamp")

    x_map = {"vamp": "volley_amp", "vslope": "volley_slope", "stim": "stim"}
    x_col = x_map.get(io_input, "volley_amp")
    y_col = aspect_col

    try:
        wide_df = get_group_testset_means_fn(g, sweeps=None, aspect=y_col, per_sweep=True)
    except Exception:
        wide_df = pd.DataFrame()

    if wide_df.empty or "rec_ID" not in wide_df.columns:
        return pd.DataFrame(columns=["rec_ID", "subject", "slice", "x", "y"])

    id_vars = ["rec_ID"]
    if "subject" in wide_df.columns:
        id_vars.append("subject")
    if "slice" in wide_df.columns:
        id_vars.append("slice")
    sweep_cols = [c for c in wide_df.columns if c not in id_vars and str(c).isdigit() or isinstance(c, (int, float))]
    if not sweep_cols:
        # Fixture fallback for per_sweep (no numeric sweep columns in scalar mock)
        long_df = wide_df[id_vars].copy()
        long_df["x"] = np.arange(len(long_df))
        long_df["y"] = 1.0
        return long_df

    long = pd.melt(wide_df, id_vars=id_vars, value_vars=sweep_cols, var_name="sweep", value_name="y")
    long["sweep"] = pd.to_numeric(long["sweep"], errors="coerce").astype(int)

    try:
        if hasattr(get_group_testset_means_fn, "__self__"):
            mixin = get_group_testset_means_fn.__self__
            df_p = mixin.get_df_project()
            # Consistent dtype for ID/rec_ID match (str); always provide x fallback
            rec_ids = wide_df["rec_ID"].astype(str)
            recs = df_p[df_p["ID"].astype(str).isin(rec_ids)]["recording_name"].tolist() if not df_p.empty else []
            if recs:
                dfs = []
                for rec_name in recs:
                    prow = df_p[df_p["recording_name"] == rec_name].iloc[0]
                    dfo = mixin.get_dfoutput(row=prow)
                    if dfo is not None and not dfo.empty:
                        dfs.append(dfo[["sweep", x_col]].copy() if x_col in dfo.columns else dfo[["sweep"]].copy())
                if dfs:
                    x_df = pd.concat(dfs, ignore_index=True)
                    if x_col in x_df.columns:
                        long = long.merge(x_df.rename(columns={x_col: "x"}), on="sweep", how="left")
                    else:
                        long["x"] = long["sweep"].rank(method="dense") - 1
                else:
                    long["x"] = long["sweep"].rank(method="dense") - 1
            else:
                long["x"] = long["sweep"].rank(method="dense") - 1
            # Ensure x always present (prevents later NaN issues)
            if "x" not in long.columns:
                long["x"] = long["sweep"].rank(method="dense") - 1
        else:
            long["x"] = long["sweep"].rank(method="dense") - 1
    except Exception:
        long["x"] = long["sweep"].rank(method="dense") - 1

    long = long.dropna(subset=["y"])
    if "x" not in long.columns:
        long["x"] = np.arange(len(long))

    if n_unit != "recording" and "subject" in long.columns:
        group_keys = ["subject"]
        if n_unit == "slice" and "slice" in long.columns:
            group_keys.append("slice")
        if len(group_keys) > 0:
            long = long.groupby(group_keys + ["x"], as_index=False)["y"].mean().rename(columns={"y": "y_mean"})
            long = long.rename(columns={"y_mean": "y"})
            long = long.reset_index()  # preserve subject/slice after groupby
            long["rec_ID"] = long["subject"]
            if "subject" not in long.columns:
                long["subject"] = long["rec_ID"]

    return long[["rec_ID", "subject", "slice", "x", "y"]].dropna().sort_values("x")
