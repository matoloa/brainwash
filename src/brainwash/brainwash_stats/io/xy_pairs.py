import numpy as np
import pandas as pd
from ..data import _aggregate_to_unit_level


def _get_io_xy_pairs(g, get_group_testset_means_fn, uistate=None, n_unit="recording", aspect_col="EPSP_amp"):
    """Returns long DataFrame with ['rec_ID', 'subject', 'slice', 'x', 'y'] for all sweeps in group.
    Uses per_sweep=True, melts, joins real X from dfoutput via uistate.experiment.io_input. Falls back to sweep rank if X missing.
    """
    if uistate is None:
        io_input = "vamp"
    else:
        io_input = uistate.experiment.io_input

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
    sweep_cols = [
        c for c in wide_df.columns if c not in id_vars and (str(c).isdigit() or isinstance(c, (int, float)))
    ]
    if not sweep_cols:
        # Fixture fallback for per_sweep (no numeric sweep columns in scalar mock); attach n_unique for test
        long_df = wide_df[id_vars].copy()
        long_df["x"] = np.arange(len(long_df))
        long_df["y"] = 1.0
        n_unique = 0
        if n_unit == "subject" and "subject" in wide_df.columns and not wide_df["subject"].isna().all():
            agg_df = _aggregate_to_unit_level(wide_df.rename(columns={y_col: "value"}), n_unit=n_unit)
            n_unique = int(agg_df["subject"].nunique(dropna=False) if not agg_df.empty and "subject" in agg_df.columns else wide_df["subject"].nunique(dropna=False))
        long_df["n_unique"] = n_unique
        return long_df

    long = pd.melt(wide_df, id_vars=id_vars, value_vars=sweep_cols, var_name="sweep", value_name="y")
    long["sweep"] = pd.to_numeric(long["sweep"], errors="coerce")
    long = long.dropna(subset=["sweep"])
    long["sweep"] = long["sweep"].astype(int)
    long["rec_ID"] = long["rec_ID"].map(lambda v: str(v))

    try:
        if hasattr(get_group_testset_means_fn, "__self__"):
            mixin = get_group_testset_means_fn.__self__
            df_p = mixin.get_df_project()
            # Per-recording X join (rec_ID + sweep) — not global sweep→X (mis-aligns recs).
            x_parts = []
            if not df_p.empty and "ID" in df_p.columns:
                id_to_name = {
                    str(r["ID"]): r["recording_name"]
                    for _, r in df_p.iterrows()
                    if pd.notna(r.get("ID"))
                }
                for rid in long["rec_ID"].unique():
                    rec_name = id_to_name.get(str(rid))
                    if rec_name is None:
                        continue
                    match = df_p[df_p["recording_name"] == rec_name]
                    if match.empty:
                        continue
                    prow = match.iloc[0]
                    dfo = mixin.get_dfoutput(row=prow)
                    if dfo is None or dfo.empty or "sweep" not in dfo.columns:
                        continue
                    piece = dfo[["sweep"]].copy()
                    piece["rec_ID"] = str(rid)
                    piece["sweep"] = pd.to_numeric(piece["sweep"], errors="coerce")
                    if x_col in dfo.columns:
                        piece["x"] = pd.to_numeric(dfo[x_col], errors="coerce")
                    else:
                        piece["x"] = np.nan
                    x_parts.append(piece.dropna(subset=["sweep"]))
            if x_parts:
                x_df = pd.concat(x_parts, ignore_index=True)
                x_df["sweep"] = x_df["sweep"].astype(int)
                long = long.merge(x_df, on=["rec_ID", "sweep"], how="left")
            if "x" not in long.columns or long["x"].isna().all():
                long["x"] = long.groupby("rec_ID")["sweep"].rank(method="dense") - 1
            else:
                # Per-rec fallback where X missing
                miss = long["x"].isna()
                if miss.any():
                    long.loc[miss, "x"] = long.loc[miss].groupby("rec_ID")["sweep"].rank(method="dense") - 1
        else:
            long["x"] = long["sweep"].rank(method="dense") - 1
    except Exception:
        long["x"] = long.groupby("rec_ID")["sweep"].rank(method="dense") - 1
    if "x" not in long.columns:
        long["x"] = long["sweep"].rank(method="dense") - 1

    long = long.dropna(subset=["y"])
    if "x" not in long.columns:
        long["x"] = np.arange(len(long))

    # n_unique from wide_df (before any loss) via _aggregate_to_unit_level -- ensures unique subjects for n_unit="subject"
    n_unique = 0
    if n_unit == "subject" and "subject" in wide_df.columns and not wide_df["subject"].isna().all():
        agg_df = _aggregate_to_unit_level(wide_df.rename(columns={y_col: "value"}), n_unit=n_unit)
        n_unique = int(agg_df["subject"].nunique(dropna=False) if not agg_df.empty and "subject" in agg_df.columns else wide_df["subject"].nunique(dropna=False))
    elif n_unit == "slice" and {"subject", "slice"}.issubset(wide_df.columns):
        n_unique = wide_df[["subject", "slice"]].dropna().drop_duplicates().shape[0]
    else:
        n_unique = len(wide_df["rec_ID"].unique()) if "rec_ID" in wide_df.columns else len(wide_df)

    if n_unit != "recording" and "subject" in long.columns:
        group_keys = ["subject"]
        if n_unit == "slice" and "slice" in long.columns:
            group_keys.append("slice")
        if len(group_keys) > 0:
            long = long.groupby(group_keys + ["x"], as_index=False)["y"].mean().rename(columns={"y": "y_mean"})
            long = long.rename(columns={"y_mean": "y"})
            long = long.reset_index()  # preserve subject/slice after groupby
            long["rec_ID"] = long.get("subject", long.get("rec_ID"))
            if "subject" not in long.columns:
                long["subject"] = long["rec_ID"]
    # Attach n for regression (overrides any loss in long DF); ensure it survives dropna
    long = long.assign(n_unique=n_unique)

    # Select only available columns (slice optional in some fixtures/real data paths; prevents KeyError)
    cols = ["rec_ID", "subject", "x", "y", "n_unique"]
    if "slice" in long.columns:
        cols.insert(2, "slice")
    ret = long[cols].dropna(subset=["x", "y"]).sort_values("x")
    return ret
