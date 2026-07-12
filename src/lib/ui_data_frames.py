# ui_data_frames.py
# DataFrameMixin — internal DataFrame computation layer extracted from UIsub (Phase 5 refactor).
# These methods handle all internal DataFrame caching, building, and transformation:
# means, timepoints, outputs, filters, bins, diffs, group means, and uniform timepoints.
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import ui_data_frames
#   ui_data_frames.uistate = uistate
#   ui_data_frames.config  = config
#   ui_data_frames.uiplot  = uiplot

from __future__ import annotations

import json
import re
from pathlib import Path

import analysis_v3 as analysis
import numpy as np
import pandas as pd
import parse

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]


class DataFrameMixin:
    """Mixin that provides the internal DataFrame computation layer for UIsub."""

    # ------------------------------------------------------------------
    # Stub / trivial helpers
    # ------------------------------------------------------------------

    @staticmethod
    def V2mV(df: pd.DataFrame) -> pd.DataFrame:
        """
        Converts SI units to display units for amplitude and slope columns.
        Returns a new DataFrame to avoid mutating the strictly SI cached data.
        """
        if df is None or df.empty:
            return df

        df_disp = df.copy()
        for col in ["EPSP_amp", "volley_amp", "EPSP_amp_mean", "volley_amp_mean", "EPSP_amp_SEM", "volley_amp_SEM"]:
            if col in df_disp.columns:
                df_disp[col] = df_disp[col] * 1000.0

        return df_disp

    # ------------------------------------------------------------------
    # Level-aware helpers for n_unit (recording/slice/subject)
    # ------------------------------------------------------------------

    LEVEL_RECORDING = "recording"
    LEVEL_SLICE = "slice"
    LEVEL_SUBJECT = "subject"
    VALID_LEVELS = (LEVEL_RECORDING, LEVEL_SLICE, LEVEL_SUBJECT)

    @staticmethod
    def _sanitize_for_filename(val: str | None) -> str:
        """Sanitize a subject/slice value for use in cache filenames."""
        if val is None:
            val = ""
        s = str(val)
        s = re.sub(r"[^A-Za-z0-9_.-]", "_", s)
        s = s.strip("_")
        if not s:
            s = "unknown"
        return s[:100]

    def _build_unit_series_from_rec_dfs(
        self, rec_dfs: list[pd.DataFrame], include_sem: bool = True
    ) -> pd.DataFrame:
        """Average a list of per-rec dfoutput DataFrames into a unit-level series.

        Returns a df with sweep + _mean/_SEM columns (like group means).
        Used for both global unit dfs and contextual group units.
        """
        if not rec_dfs:
            return pd.DataFrame(
                {
                    "sweep": [],
                    "EPSP_amp_norm_mean": [],
                    "EPSP_amp_norm_SEM": [],
                    "EPSP_slope_norm_mean": [],
                    "EPSP_slope_norm_SEM": [],
                    "EPSP_amp_mean": [],
                    "EPSP_amp_SEM": [],
                    "EPSP_slope_mean": [],
                    "EPSP_slope_SEM": [],
                }
            )

        concat_df = pd.concat(rec_dfs, ignore_index=True)
        base_cols = ["EPSP_amp_norm", "EPSP_slope_norm", "EPSP_amp", "EPSP_slope"]
        agg_spec = {}
        for c in base_cols:
            if c in concat_df.columns:
                agg_spec[c] = ["mean", "sem"] if include_sem else ["mean"]
        if not agg_spec:
            return pd.DataFrame({"sweep": []})
        unit_df = (
            concat_df.groupby("sweep")
            .agg(agg_spec)
            .reset_index()
        )
        unit_df.columns = [
            col[0] if col[0] == "sweep" else "_".join(col).strip().replace("sem", "SEM")
            for col in unit_df.columns.values
        ]
        return unit_df

    # ------------------------------------------------------------------
    # Recalculate all outputs
    # ------------------------------------------------------------------

    def recalculate(self, selection=None):
        # Recalculates outputs when normalization, binning, or amp halfwidth changes.
        # selection: list of df_project row indices to recalculate, or None to recalculate all.
        self.usage("recalculate")
        self.uiFreeze()
        # Any recalc that can alter groupmeans must disable the heatmap
        if hasattr(self, "turn_heatmap_off"):
            self.turn_heatmap_off()

        norm_from = uistate.lineEdit["norm_EPSP_from"]
        norm_to = uistate.lineEdit["norm_EPSP_to"]
        dt = uistate.default_dict_t
        dt["norm_output_from"] = norm_from
        dt["norm_output_to"] = norm_to
        uistate.save_cfg(projectfolder=self.dict_folders["project"])

        df_p = self.get_df_project()
        rows = df_p.iloc[selection] if selection is not None else df_p

        if selection is None:
            uiplot.unPlot()
            uiplot.unPlotGroup()
        else:
            for _, p_row in rows.iterrows():
                uiplot.unPlot(p_row["ID"])
            # Ensure unique group IDs and convert to list correctly
            affected_group_IDs = list(set([g for _, p_row in rows.iterrows() for g in self.get_groupsOfRec(p_row["ID"])]))
            for group_ID in affected_group_IDs:
                uiplot.unPlotGroup(group_ID)

        for _, p_row in rows.iterrows():
            rec = p_row["recording_name"]

            if p_row["filter"] == "savgol":
                try:
                    params_str = p_row["filter_params"]
                    params = json.loads(params_str) if pd.notna(params_str) and params_str else {}
                except Exception:
                    params = {}
                wl = int(params.get("window_length", 9))
                po = int(params.get("poly_order", 3))

                df_mean = self.get_dfmean(p_row)
                df_mean["savgol"] = analysis.addFilterSavgol(df_mean, window_length=wl, poly_order=po)
                self.df2file(df=df_mean, filename=rec, key="mean")

                df_filter = self.get_dffilter(p_row)
                df_filter["savgol"] = analysis.addFilterSavgol(df_filter, window_length=wl, poly_order=po)
                self.df2file(df=df_filter, filename=rec, key="filter")

                if pd.notna(p_row["bin_size"]):
                    df_bin = self.get_dfbin(p_row)
                    df_bin["savgol"] = analysis.addFilterSavgol(df_bin, window_length=wl, poly_order=po)
                    self.df2file(df=df_bin, filename=rec, key="bin")

            df_t = self.get_dft(p_row)
            df_t["norm_output_from"] = dt["norm_output_from"]
            df_t["norm_output_to"] = dt["norm_output_to"]
            self.set_dft(rec, df_t)
            if pd.notna(p_row["bin_size"]):
                dfbin = self.get_dfbin(p_row)
                print(dfbin)
            dfoutput = self.get_dfoutput(p_row, reset=True)
            self.persistOutput(rec, dfoutput, p_row=p_row)
            uiplot.addRow(p_row, df_t, self.get_dfmean(p_row), self.V2mV(dfoutput))
        self.tableUpdate(restore_selection=True)  # centralized restore after recalculate

        # group handling
        if selection is None:
            self.group_cache_purge()
        else:
            self.group_cache_purge(affected_group_IDs)
        # 3.4.1: invalidate sample cache on group changes (sample or testset sweeps may be affected)
        if hasattr(self, "dd_group_samples"):
            self.dd_group_samples = {}

        uiplot.hideAll()
        self.update_show(reset=(selection is None))
        self.mouseoverUpdate()
        self.uiThaw()

    # ------------------------------------------------------------------
    # Timepoints (dft) persistence
    # ------------------------------------------------------------------

    def set_dft(self, rec_name, df):  # persists df and saves it as a file
        # print(f"type: {type(df)}")
        print(f"set_dft of {rec_name}: {df}")
        self.dict_ts[rec_name] = df
        self.df2file(df=df, filename=rec_name, key="timepoints")

    # ------------------------------------------------------------------
    # Mean DataFrame
    # ------------------------------------------------------------------

    def get_dfmean(self, row):
        # returns an internal df mean for the selected file. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        persist = False

        # Guard for unparsed recordings (added via file selector but not yet parsed)
        if str(row.get("sweeps", "...")) == "...":
            print(f"get_dfmean: {recording_name} not yet parsed (sweeps=...), returning dummy")
            dfmean = pd.DataFrame(columns=["sweep", "voltage", "prim", "bis"])
            self.dict_means[recording_name] = dfmean
            return self.dict_means[recording_name]

        if recording_name in self.dict_means:  # 1: Return cached
            dfmean = self.dict_means[recording_name]
        else:
            str_mean_path = f"{self.dict_folders['cache']}/{recording_name}_mean.parquet"
            if Path(str_mean_path).exists():  # 2: Read from file
                dfmean = pd.read_parquet(str_mean_path)
            else:  # 3: Create file
                dfdata = self.get_dfdata(row=row)
                if dfdata is None:
                    print(f"get_dfmean: dfdata is None for {recording_name} (not imported)")
                    dfmean = pd.DataFrame(columns=["sweep", "voltage", "prim", "bis"])
                    self.dict_means[recording_name] = dfmean
                    return self.dict_means[recording_name]
                gain = float(row["gain"]) if pd.notna(row["gain"]) else 1.0
                if gain != 1.0:
                    dfdata = dfdata.copy()
                    dfdata["voltage_raw"] = dfdata["voltage_raw"] * gain
                dfmean, _ = parse.build_dfmean(dfdata)
                persist = True

        # if the filter is not a column in dfmean, create it
        if row["filter"] == "savgol":
            if "savgol" not in dfmean.columns:
                try:
                    params_str = row["filter_params"]
                    params = json.loads(params_str) if pd.notna(params_str) and params_str else {}
                except Exception:
                    params = {}
                window_length = int(params.get("window_length", 9))
                poly_order = int(params.get("poly_order", 3))
                dfmean["savgol"] = analysis.addFilterSavgol(df=dfmean, window_length=window_length, poly_order=poly_order)
                persist = True
        if persist:
            self.df2file(df=dfmean, filename=recording_name, key="mean")
        self.dict_means[recording_name] = dfmean
        return self.dict_means[recording_name]

    # ------------------------------------------------------------------
    # Timepoints DataFrame
    # ------------------------------------------------------------------

    def get_dft(self, row, reset=False):
        # returns an internal df t for the selected file. If it does not exist, read it from file first.
        rec = row["recording_name"]
        if str(row.get("sweeps", "...")) == "...":
            print(f"get_dft: {rec} not parsed yet")
            return None
        if rec in self.dict_ts.keys() and not reset:
            # print("returning cached dft")
            return self.dict_ts[rec]
        str_t_path = f"{self.dict_folders['timepoints']}/{rec}.parquet"
        if Path(str_t_path).exists() and not reset:
            # print("reading dft from file")
            dft = pd.read_parquet(str_t_path)
            # Migrate old column names: norm_EPSP_from/to → norm_output_from/to
            if "norm_EPSP_from" in dft.columns:
                dft.rename(
                    columns={
                        "norm_EPSP_from": "norm_output_from",
                        "norm_EPSP_to": "norm_output_to",
                    },
                    inplace=True,
                )
                self.df2file(df=dft, filename=rec, key="timepoints")  # re-persist with corrected names
            for col in dft.columns:
                if col != "stim" and dft[col].dtype in ["int64", "int32", "float32"]:
                    dft[col] = dft[col].astype("float64")
            self.dict_ts[rec] = dft
            return dft
        else:
            print("creating dft")
            default_dict_t = uistate.default_dict_t.copy()  # Default sizes
            dfmean = self.get_dfmean(row)
            dft = analysis.find_events(
                dfmean=dfmean,
                default_dict_t=default_dict_t,
                filter=row["filter"],
                verbose=False,
            )
            # TODO: Error handling!
            if dft.empty:
                print("get_dft: No stims found.")
                return None
            dft["norm_output_from"], dft["norm_output_to"] = (
                uistate.lineEdit["norm_EPSP_from"],
                uistate.lineEdit["norm_EPSP_to"],
            )
            df_p = self.get_df_project()  # update (number of) 'stims' columns
            stims = len(dft)
            df_p.loc[row["ID"] == df_p["ID"], "stims"] = stims
            self.set_df_project(df_p)
            self.tableUpdate(restore_selection=True)  # ensure selection preserved after stim count update
            # If the UI checkbox for 'timepoints_per_stim' is checked OR there's only 1 stim,
            # we assume timepoints don't need adjustment, so we cache df_t as-is.
            if uistate.checkBox["timepoints_per_stim"] or stims == 1:
                self.dict_ts[rec] = dft  # update cache
            # Otherwise, compute a uniform timepoint structure based on the current row and df_t.
            else:
                dfoutput = self.get_dfoutput(row=row, dft=dft)
                self.set_uniformTimepoints(p_row=row, dft=dft, dfoutput=dfoutput)
                dft = self.dict_ts[rec]
            for col in dft.columns:
                if col != "stim" and dft[col].dtype in ["int64", "int32", "float32"]:
                    dft[col] = dft[col].astype("float64")
            self.dict_ts[rec] = dft
            self.df2file(df=dft, filename=rec, key="timepoints")  # persist dft as parquet
            self.set_rec_status(rec)  # update status in df_project
            return dft

    # ------------------------------------------------------------------
    # Output DataFrame
    # ------------------------------------------------------------------

    def get_dfoutput(self, row, reset=False, dft=None):  # Requires df_t
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        rec = row["recording_name"]
        bin_active = pd.notna(row["bin_size"])
        cache_key = "output_bin" if bin_active else "output"
        cache_suffix = "_output_bin" if bin_active else "_output"
        if rec in self.dict_outputs and not reset:  # 1: Return cached
            return self.dict_outputs[rec]
        str_output_path = f"{self.dict_folders['cache']}/{rec}{cache_suffix}.parquet"
        if Path(str_output_path).exists() and not reset:  # 2: Read from file
            dfoutput = pd.read_parquet(str_output_path)
            # Migrate old files that had a spurious 'index' column from reset_index(inplace=True).
            if "index" in dfoutput.columns:
                dfoutput.drop(columns=["index"], inplace=True)
                dfoutput.reset_index(drop=True, inplace=True)
                self.df2file(df=dfoutput, filename=rec, key=cache_key)  # re-persist clean version
            else:
                dfoutput.reset_index(drop=True, inplace=True)
        else:  # 3: Create from scratch and persist
            print(f"creating output for {row['recording_name']}")
            dfmean = self.get_dfmean(row=row)
            if dft is None:
                dft = self.get_dft(row=row)
            if pd.notna(row["bin_size"]):
                dfinput = self.get_dfbin(row)
            else:
                dfinput = self.get_dffilter(row)
            filter_val = row.get("filter")
            filter_col = filter_val if pd.notna(filter_val) and filter_val and filter_val != "none" else "voltage"
            dfoutput = analysis.build_dfoutput(
                dffilter=dfinput,
                dfmean=dfmean,
                dft=dft,
                filter=filter_col,
            )
            if dft is None or dft.empty:
                print(f"get_dfoutput: dft None/empty for {row['recording_name']}, skipping backfill")
            else:
                # Back-fill volley means into dft from the sweep-mode rows
                for i, t_row in dft.iterrows():
                    stim_nr = t_row["stim"]
                    sweep_rows = dfoutput[(dfoutput["stim"] == stim_nr) & dfoutput["sweep"].notna()]
                    volley_amp_mean = sweep_rows["volley_amp"].mean()
                    dft.at[i, "volley_amp_mean"] = volley_amp_mean
                    dft.at[i, "volley_slope_mean"] = sweep_rows["volley_slope"].mean()
            self.set_dft(rec, dft)
            print(f"get_dfoutput: done, dfoutput.shape={dfoutput.shape}")
            dfoutput.reset_index(drop=True, inplace=True)
            # Persist the clean version to disk.
            self.df2file(df=dfoutput, filename=rec, key=cache_key)
        # Cache and return
        self.dict_outputs[rec] = dfoutput
        return dfoutput

    # ------------------------------------------------------------------
    # Raw data DataFrame
    # ------------------------------------------------------------------

    def get_dfdata(self, row):
        # returns an internal df for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        if recording_name in self.dict_datas:  # 1: Return cached
            return self.dict_datas[recording_name]
        path_data = Path(f"{self.dict_folders['data']}/{recording_name}.parquet")
        try:  # 2: Read from file - datafile should always exist
            dfdata = pd.read_parquet(path_data)
            self.dict_datas[recording_name] = dfdata
            return self.dict_datas[recording_name]
        except FileNotFoundError:
            print(f"did not find {path_data}. Not imported?")
            return None

    # ------------------------------------------------------------------
    # Filter DataFrame
    # ------------------------------------------------------------------

    def get_dffilter(self, row):
        # returns an internal df_filter for the selected recording_name. If it does not exist, read it from file first.
        recording_name = row["recording_name"]
        persist = False

        if recording_name in self.dict_filters:  # 1: Return cached
            dffilter = self.dict_filters[recording_name]
        else:
            path_filter = Path(f"{self.dict_folders['cache']}/{recording_name}_filter.parquet")
            if Path(path_filter).exists():  # 2: Read from file
                dffilter = pd.read_parquet(path_filter)
            else:  # 3: Create file
                dfdata = self.get_dfdata(row=row)
                if dfdata is None or str(row.get("sweeps", "...")) == "...":
                    print(f"get_dffilter: no data for unparsed {recording_name}")
                    dffilter = pd.DataFrame(columns=["sweep", "time", "voltage"])
                    self.dict_filters[recording_name] = dffilter
                    return dffilter
                gain = float(row["gain"]) if pd.notna(row["gain"]) else 1.0
                if gain != 1.0:
                    dfdata = dfdata.copy()
                    dfdata["voltage_raw"] = dfdata["voltage_raw"] * gain
                dffilter = parse.zeroSweeps(dfdata=dfdata, dfmean=self.get_dfmean(row=row))
                persist = True

        if row["filter"] == "savgol":
            if "savgol" not in dffilter.columns:
                try:
                    params_str = row["filter_params"]
                    params = json.loads(params_str) if pd.notna(params_str) and params_str else {}
                except Exception:
                    params = {}
                window_length = int(params.get("window_length", 9))
                poly_order = int(params.get("poly_order", 3))
                dffilter["savgol"] = analysis.addFilterSavgol(df=dffilter, window_length=window_length, poly_order=poly_order)
                persist = True

        if persist:
            self.df2file(df=dffilter, filename=recording_name, key="filter")

        # Cache and return
        self.dict_filters[recording_name] = dffilter
        return self.dict_filters[recording_name]

    # ------------------------------------------------------------------
    # Bin DataFrame
    # ------------------------------------------------------------------

    def get_dfbin(self, p_row):
        # returns an internal df_bin for the selected recording_name. If it does not exist, read it from file first.
        rec = p_row["recording_name"]
        if pd.isna(p_row["bin_size"]):
            raise ValueError(f"get_dfbin called for '{rec}' but bin_size is NaN — callers must not reach get_dfbin when binning is off.")
        persist = False

        if rec in self.dict_bins:
            df_bins = self.dict_bins[rec]
        else:
            path_bin = Path(f"{self.dict_folders['cache']}/{rec}_bin.parquet")
            if path_bin.exists():
                df_bins = pd.read_parquet(path_bin)
            else:
                bin_size = int(p_row["bin_size"])
                df_filter = self.get_dffilter(p_row)
                max_sweep = df_filter["sweep"].max()
                num_bins = (max_sweep // bin_size) + 1
                binned_data = []
                for bin_num in range(num_bins):
                    sweep_start = bin_num * bin_size
                    sweep_end = sweep_start + bin_size
                    df_bin = df_filter[(df_filter["sweep"] >= sweep_start) & (df_filter["sweep"] < sweep_end)]
                    if df_bin.empty:
                        continue
                    agg_funcs = {col: "mean" for col in df_bin.columns if col not in ["sweep", "time"]}
                    agg_funcs["time"] = "first"  # Keep the first time value as representative
                    df_bin_grouped = df_bin.groupby("time", as_index=False).agg(agg_funcs)
                    # Assign the bin number as the new sweep value
                    df_bin_grouped["sweep"] = bin_num
                    binned_data.append(df_bin_grouped)
                df_bins = pd.concat(binned_data, ignore_index=True)
                persist = True
                print(f"recalculate: {rec}, binned {df_filter['sweep'].nunique()} sweeps into {len(df_bins['sweep'].unique())} bins")

        if p_row["filter"] == "savgol":
            if "savgol" not in df_bins.columns:
                try:
                    params_str = p_row["filter_params"]
                    params = json.loads(params_str) if pd.notna(params_str) and params_str else {}
                except Exception:
                    params = {}
                window_length = int(params.get("window_length", 9))
                poly_order = int(params.get("poly_order", 3))
                df_bins["savgol"] = analysis.addFilterSavgol(df=df_bins, window_length=window_length, poly_order=poly_order)
                persist = True

        if persist:
            self.df2file(df=df_bins, filename=rec, key="bin")

        self.dict_bins[rec] = df_bins
        return df_bins

    # ------------------------------------------------------------------
    # Diff DataFrame (paired recordings)
    # ------------------------------------------------------------------

    def get_dfdiff(self, row):
        # returns an internal df output for the selected file. If it does not exist, read it from file first.
        rec_select = row["recording_name"]
        # TODO: check if row has a paired recording
        # Otherwise, find the paired recording
        rec_paired = None
        key_pair = rec_select[:-2]  # remove stim id ("_a" or "_b") from selected recording_name
        # 1: check for cached diff
        if key_pair in self.dict_diffs:
            return self.dict_diffs[key_pair]
        # 2: check for file
        if Path(f"{self.dict_folders['cache']}/{key_pair}_diff.parquet").exists():
            dfdiff = pd.read_parquet(f"{self.dict_folders['cache']}/{key_pair}_diff.parquet")
            self.dict_diffs[key_pair] = dfdiff
            return dfdiff
        # 3: build a new diff
        dfp = self.get_df_project()
        # 3.1: does the row have a saved paired recording that exists in dfp?
        if pd.notna(row["paired_recording"]):
            if row["paired_recording"] in dfp["recording_name"].values:
                rec_paired = row["paired_recording"]
        # 3.2: if not, find a recording with a matching name
        if rec_paired is None:  # set rec_paired to the first recording_name that starts with rec_paired, but isn't rec_select
            for i, row_check in dfp.iterrows():
                if row_check["recording_name"].startswith(key_pair) and row_check["recording_name"] != rec_select:
                    rec_paired = row_check["recording_name"]
                    break
        if rec_paired is None:  # if still None, return
            print("Paired recording not found.")
            return
        # 3.3: get the dfoutputs for both recordings
        row_paired = dfp[dfp["recording_name"] == rec_paired].iloc[0]
        dfp.loc[row.name, "paired_recording"] = rec_paired
        dfp.loc[row_paired.name, "paired_recording"] = rec_select
        self.set_df_project(dfp)
        dfout_select = self.get_dfoutput(row=row)
        dfout_paired = self.get_dfoutput(row=row_paired)

        # 3.4: check which of the paired recordings is Tx (the other being control)
        if pd.isna(row["Tx"]):
            print("Tx is NaN - loop should trigger!")
            row["Tx"] = False
            # default: assume Tx has the highest max EPSP_amp, or EPSP_slope if there is no EPSP_amp
            if any((dfout_select[col].max() > dfout_paired[col].max() for col in ["EPSP_amp", "EPSP_slope"] if col in dfout_select.columns)):
                row["Tx"] = True
                row_paired["Tx"] = False
                dfp.loc[row.name, "Tx"] = row["Tx"]
                dfp.loc[row_paired.name, "Tx"] = row_paired["Tx"]
                print(f"{rec_select} is Tx, {rec_paired} is control. Saving df_p...")
                self.set_df_project(dfp)
            elif not any(col in dfout_select.columns for col in ["EPSP_amp", "EPSP_slope"]):
                print("Selected recording has no measurements.")
                return
        else:
            print("Tx is not NaN")
        # 3.5: set dfi and dfc
        if row["Tx"]:
            dfi = dfout_select  # Tx output
            dfc = dfout_paired  # control output
        else:
            dfi = dfout_paired
            dfc = dfout_select
        # 3.6: build dfdiff
        dfdiff = pd.DataFrame({"sweep": dfi.sweep})
        if "EPSP_amp" in dfi.columns:
            dfdiff["EPSP_amp"] = dfi.EPSP_amp / dfc.EPSP_amp
        if "EPSP_slope" in dfi.columns:
            dfdiff["EPSP_slope"] = dfi.EPSP_slope / dfc.EPSP_slope
        self.df2file(df=dfdiff, filename=key_pair, key="diff")
        self.dict_diffs[key_pair] = dfdiff
        return dfdiff

    # ------------------------------------------------------------------
    # Global (project-wide) unit-level DataFrames (Subject / Slice)
    # These are independent of groups. Used for rec-to-subject comparisons etc.
    # Built with hierarchical averaging (slice = avg recs; subject = avg of slice means).
    # ------------------------------------------------------------------

    def _get_global_unit_cache_key(self, level: str, subject: str, slc: str | None = None) -> tuple:
        return (level, str(subject), str(slc) if slc is not None else None)

    def get_global_subject_df(self, subject: str):
        """Return (or build) the full project-wide mean series for a subject.

        Averages per-slice means (two-stage) to give equal weight to slices.
        Includes _mean and _SEM (SEM across slices).
        """
        if not hasattr(self, "dict_global_units"):
            self.dict_global_units = {}
        key = self._get_global_unit_cache_key(self.LEVEL_SUBJECT, subject)
        if key in self.dict_global_units:
            return self.dict_global_units[key]

        safe = self._sanitize_for_filename(subject)
        path = Path(f"{self.dict_folders['cache']}/Subject_{safe}_output.parquet")
        if path.exists():
            df = pd.read_parquet(str(path))
            self.dict_global_units[key] = df
            return df

        df_p = self.get_df_project()
        subj_recs = df_p[df_p["subject"].astype(str) == str(subject)]["ID"].tolist()
        if not subj_recs:
            df = pd.DataFrame(columns=["sweep", "EPSP_amp_mean", "EPSP_amp_SEM", "EPSP_slope_mean", "EPSP_slope_SEM"])
            self.df2file(df=df, filename=f"Subject_{safe}", key="output")
            self.dict_global_units[key] = df
            return df

        # Group recs by slice, build per-slice means (no sem yet)
        slice_to_dfs = {}
        for rec_id in subj_recs:
            match = df_p[df_p["ID"] == rec_id]
            if match.empty:
                continue
            p_row = match.iloc[0]
            sl = str(p_row.get("slice", "1"))
            try:
                dfo = self.get_dfoutput(row=p_row)
                slice_to_dfs.setdefault(sl, []).append(dfo)
            except Exception:
                continue

        slice_means = []
        for sl, rec_dfs in slice_to_dfs.items():
            smean = self._build_unit_series_from_rec_dfs(rec_dfs, include_sem=False)
            if not smean.empty:
                slice_means.append(smean)

        if not slice_means:
            df = pd.DataFrame(columns=["sweep", "EPSP_amp_mean", "EPSP_amp_SEM", "EPSP_slope_mean", "EPSP_slope_SEM"])
        else:
            # Average the slice means (which have _mean cols); compute SEM across slices
            concat_slices = pd.concat(slice_means, ignore_index=True)
            grouped = concat_slices.groupby("sweep")
            mean_df = grouped.mean().reset_index()
            sem_df = grouped.sem(ddof=1).reset_index()
            df = mean_df[["sweep"]].copy()
            for base in ["EPSP_amp", "EPSP_slope"]:
                for suf in ["", "_norm"]:
                    mcol = f"{base}{suf}_mean"
                    if mcol in mean_df.columns:
                        df[mcol] = mean_df[mcol]
                        scol = f"{base}{suf}_SEM"
                        if scol in sem_df.columns:
                            df[scol] = pd.to_numeric(sem_df[scol], errors="coerce").fillna(0.0)
                        else:
                            df[scol] = 0.0

        self.df2file(df=df, filename=f"Subject_{safe}", key="output")
        self.dict_global_units[key] = df
        return df

    def get_global_slice_df(self, subject: str, slc: str):
        """Return (or build) the full project-wide mean series for a (subject, slice).

        Averages the recs belonging to this slice.
        Includes _mean and _SEM (SEM across recs in the slice).
        """
        if not hasattr(self, "dict_global_units"):
            self.dict_global_units = {}
        key = self._get_global_unit_cache_key(self.LEVEL_SLICE, subject, slc)
        if key in self.dict_global_units:
            return self.dict_global_units[key]

        safe_s = self._sanitize_for_filename(subject)
        safe_sl = self._sanitize_for_filename(slc)
        path = Path(f"{self.dict_folders['cache']}/Subject_{safe_s}_-_Slice_{safe_sl}_output.parquet")
        if path.exists():
            df = pd.read_parquet(str(path))
            self.dict_global_units[key] = df
            return df

        df_p = self.get_df_project()
        slice_recs = df_p[
            (df_p["subject"].astype(str) == str(subject)) & (df_p["slice"].astype(str) == str(slc))
        ]["ID"].tolist()

        rec_dfs = []
        for rec_id in slice_recs:
            match = df_p[df_p["ID"] == rec_id]
            if match.empty:
                continue
            try:
                dfo = self.get_dfoutput(row=match.iloc[0])
                rec_dfs.append(dfo)
            except Exception:
                continue

        df = self._build_unit_series_from_rec_dfs(rec_dfs, include_sem=True)
        self.df2file(df=df, filename=f"Subject_{safe_s}_-_Slice_{safe_sl}", key="output")
        self.dict_global_units[key] = df
        return df

    def _invalidate_global_units_for_rec(self, rec_id):
        """Invalidate cached global unit dfs that include this rec (on output or hierarchy change)."""
        if not hasattr(self, "dict_global_units") or not self.dict_global_units:
            return
        df_p = self.get_df_project()
        match = df_p[df_p["ID"] == rec_id]
        if match.empty:
            self.dict_global_units.clear()
            return
        p = match.iloc[0]
        subj = str(p.get("subject", ""))
        slc = str(p.get("slice", ""))
        to_del = []
        for k in list(self.dict_global_units.keys()):
            if len(k) >= 2 and k[1] == subj:
                to_del.append(k)
            if len(k) >= 3 and k[2] == slc:
                to_del.append(k)
        for k in to_del:
            if k in self.dict_global_units:
                del self.dict_global_units[k]
        # delete files
        if subj:
            safe = self._sanitize_for_filename(subj)
            pth = Path(f"{self.dict_folders.get('cache', '.')}/Subject_{safe}_output.parquet")
            if pth.exists():
                try: pth.unlink()
                except: pass
        if subj and slc:
            safe_s = self._sanitize_for_filename(subj)
            safe_sl = self._sanitize_for_filename(slc)
            pth = Path(f"{self.dict_folders.get('cache', '.')}/Subject_{safe_s}_-_Slice_{safe_sl}_output.parquet")
            if pth.exists():
                try: pth.unlink()
                except: pass

    # ------------------------------------------------------------------
    # Group mean DataFrame
    # ------------------------------------------------------------------

    def get_dfgroupmean(self, group_ID, level: str | None = None):
        """Return group mean df at the requested level (recording/slice/subject).

        level=None or 'recording' -> classic rec-level (back-compat).
        'slice'/'subject' -> contextual: avg within unit (only group's recs), then across units.
        Uses per-level cache keys and files for isolation.
        """
        if not group_ID:
            return pd.DataFrame()
        eff_level = level or self.LEVEL_RECORDING
        if eff_level not in self.VALID_LEVELS:
            eff_level = self.LEVEL_RECORDING

        if not hasattr(self, "dict_group_means"):
            self.dict_group_means = {}
        cache_key = (group_ID, eff_level) if isinstance(group_ID, (int, str)) else group_ID
        if eff_level == self.LEVEL_RECORDING and isinstance(group_ID, (int, str)) and group_ID in self.dict_group_means:
            val = self.dict_group_means[group_ID]
            self.dict_group_means[cache_key] = val
            return val
        if cache_key in self.dict_group_means:
            if config.verbose:
                print(f"Returning cached group mean for {group_ID} level={eff_level}")
            return self.dict_group_means[cache_key]

        level_suffix = "" if eff_level == self.LEVEL_RECORDING else f"_{eff_level}"
        group_path = Path(f"{self.dict_folders['cache']}/group_{group_ID}{level_suffix}_mean.parquet")
        if group_path.exists():
            if config.verbose:
                print(f"Loading stored group mean for {group_ID} level={eff_level}")
            group_mean = pd.read_parquet(str(group_path))
            self.dict_group_means[cache_key] = group_mean
            return group_mean

        if config.verbose:
            print(f"Building new group mean for {group_ID} level={eff_level}")
        recs_in_group = self.dd_groups.get(group_ID, {}).get("rec_IDs", [])
        df_p = self.get_df_project()

        if eff_level == self.LEVEL_RECORDING:
            # original rec-level logic
            dfs = []
            for rec_ID in recs_in_group:
                matching_rows = df_p.loc[df_p["ID"] == rec_ID]
                if matching_rows.empty:
                    raise ValueError(f"rec_ID {rec_ID} not found in df_project.")
                p_row = matching_rows.iloc[0]
                df = self.get_dfoutput(row=p_row)
                dfs.append(df)
            if len(dfs) == 0:
                group_mean = pd.DataFrame(
                    {
                        "sweep": [],
                        "EPSP_amp_norm_mean": [],
                        "EPSP_amp_norm_SEM": [],
                        "EPSP_slope_norm_mean": [],
                        "EPSP_slope_norm_SEM": [],
                        "EPSP_amp_mean": [],
                        "EPSP_amp_SEM": [],
                        "EPSP_slope_mean": [],
                        "EPSP_slope_SEM": [],
                    }
                )
            else:
                group_mean = (
                    pd.concat(dfs)
                    .groupby("sweep")
                    .agg(
                        {
                            "EPSP_amp_norm": ["mean", "sem"],
                            "EPSP_slope_norm": ["mean", "sem"],
                            "EPSP_amp": ["mean", "sem"],
                            "EPSP_slope": ["mean", "sem"],
                        }
                    )
                    .reset_index()
                )
                group_mean.columns = [col[0] if col[0] == "sweep" else "_".join(col).strip().replace("sem", "SEM") for col in group_mean.columns.values]
                # sanitize SEMs (n=1 within group -> NaN from sem)
                for c in list(group_mean.columns):
                    if c.endswith("_SEM"):
                        group_mean[c] = pd.to_numeric(group_mean[c], errors="coerce").fillna(0.0)
            self.df2file(df=group_mean, filename=f"group_{group_ID}", key="mean")
        else:
            # contextual higher level: group by unit within group's recs, avg to units, then across
            unit_to_dfs = {}
            for rec_ID in recs_in_group:
                matching_rows = df_p.loc[df_p["ID"] == rec_ID]
                if matching_rows.empty:
                    continue
                p_row = matching_rows.iloc[0]
                if eff_level == self.LEVEL_SUBJECT:
                    unit_key = str(p_row.get("subject", "unknown"))
                else:  # slice
                    unit_key = (str(p_row.get("subject", "unknown")), str(p_row.get("slice", "1")))
                try:
                    dfo = self.get_dfoutput(row=p_row)
                    unit_to_dfs.setdefault(unit_key, []).append(dfo)
                except Exception:
                    continue

            unit_series = []
            for ukey, rec_dfs in unit_to_dfs.items():
                um = self._build_unit_series_from_rec_dfs(rec_dfs, include_sem=False)
                if not um.empty:
                    unit_series.append(um)

            if not unit_series:
                group_mean = pd.DataFrame(
                    {
                        "sweep": [],
                        "EPSP_amp_norm_mean": [],
                        "EPSP_amp_norm_SEM": [],
                        "EPSP_slope_norm_mean": [],
                        "EPSP_slope_norm_SEM": [],
                        "EPSP_amp_mean": [],
                        "EPSP_amp_SEM": [],
                        "EPSP_slope_mean": [],
                        "EPSP_slope_SEM": [],
                    }
                )
            else:
                concat_units = pd.concat(unit_series, ignore_index=True)
                g = concat_units.groupby("sweep")
                m = g.mean().reset_index()
                s = g.sem(ddof=1).reset_index()
                group_mean = m[["sweep"]].copy()
                for base in ["EPSP_amp", "EPSP_slope"]:
                    for suf in ["", "_norm"]:
                        mcol = f"{base}{suf}_mean"
                        if mcol in m.columns:
                            group_mean[mcol] = m[mcol]
                            scol = f"{base}{suf}_SEM"
                            if mcol in s.columns:
                                group_mean[scol] = pd.to_numeric(s[mcol], errors="coerce").fillna(0.0)
                            else:
                                group_mean[scol] = 0.0

            fname = f"group_{group_ID}{level_suffix}"
            self.df2file(df=group_mean, filename=fname, key="mean")

        self.dict_group_means[cache_key] = group_mean
        return group_mean

    def get_dfgroupmean_for_sweeps(self, group_ID, sweeps, level: str | None = None):
        """Return group mean df filtered to the given list of sweep indices.
        Supports level for n_unit-aware means.
        """
        if not group_ID:
            return pd.DataFrame()
        df = self.get_dfgroupmean(group_ID, level=level)
        if df is None or df.empty or not sweeps:
            return df if df is not None else pd.DataFrame()
        mask = df["sweep"].isin(sweeps)
        return df.loc[mask].reset_index(drop=True).copy()

    def get_group_obs_for_sweeps(self, group_ID, sweeps=None, aspect="EPSP_amp"):
        """Return a DataFrame with one row per rec in the group, columns for the requested sweeps.
        v0.16_n_stats_IO: if sweeps is None or empty, uses ALL available sweeps from each recording's dfoutput
        (implicit test set for IO mode). Used for paired t-test alignment and implicit stats.
        aspect: 'EPSP_amp' | 'EPSP_amp_norm' | 'EPSP_slope' | ...
        """
        recs = self.dd_groups.get(group_ID, {}).get("rec_IDs", [])
        if not recs:
            return pd.DataFrame()
        df_p = self.get_df_project()
        rows = []
        for rec_ID in recs:
            match = df_p.loc[df_p["ID"] == rec_ID]
            if match.empty:
                continue
            p_row = match.iloc[0]
            try:
                dfo = self.get_dfoutput(row=p_row)
            except Exception:
                continue
            if dfo is None or dfo.empty or "sweep" not in dfo.columns:
                continue
            if sweeps is None or (isinstance(sweeps, (list, tuple)) and not sweeps):
                # IO implicit: all sweeps for this recording
                dff = dfo.copy()
            else:
                dff = dfo[dfo["sweep"].isin(sweeps)]
            if dff.empty:
                continue
            # pivot-ish: one value per sweep for this rec
            val_col = aspect if aspect in dff.columns else ("EPSP_amp" if "EPSP_amp" in dff.columns else None)
            if val_col is None:
                continue
            rec_vals = {int(s): float(v) for s, v in zip(dff["sweep"], dff[val_col]) if pd.notna(v)}
            rows.append({"rec_ID": str(rec_ID), "vals": rec_vals})
        if not rows:
            return pd.DataFrame()
        # Build aligned matrix: index=rec order, columns=sweeps (only those present in all? no, caller handles)
        if sweeps is None or (isinstance(sweeps, (list, tuple)) and not sweeps):
            # For implicit all-sweeps, use union across recs or per-rec (here per-rec vals dict already handles missing)
            all_sweeps = sorted({s for r in rows for s in r["vals"]})
        else:
            all_sweeps = sorted(sweeps)
        data = []
        for r in rows:
            row = [r["rec_ID"]]
            for sw in all_sweeps:
                row.append(r["vals"].get(int(sw), np.nan))
            data.append(row)
        cols = ["rec_ID"] + [str(s) for s in all_sweeps]
        return pd.DataFrame(data, columns=cols)

    def get_group_testset_means(self, group_ID, sweeps=None, aspect="EPSP_amp", per_sweep: bool = False):
        """Return DataFrame with ['rec_ID', 'value'] (+ subject, slice after v0.16_n_stats).
        v0.16_n_stats_IO: if sweeps is None or empty (and not per_sweep), uses ALL sweeps per recording/group
        as implicit test set for IO mode. per_sweep=True (cluster) still requires explicit sweeps list.
        Always joins subject/slice from df_project (NaN for old projects; Phase 0).
        Rows sorted by rec_ID. Re-uses get_group_obs_for_sweeps internally.
        """
        if not group_ID:
            cols = (
                ["rec_ID", "value"]
                if not per_sweep
                else ["rec_ID"] + [str(s) for s in (sorted(sweeps) if isinstance(sweeps, (list, tuple)) and sweeps is not None else [])]
            )
            return pd.DataFrame(columns=cols)
        # Explicit empty list (non-IO path) returns empty; None triggers implicit all-sweeps in get_group_obs_for_sweeps
        if isinstance(sweeps, (list, tuple)) and not sweeps and not per_sweep:
            cols = ["rec_ID", "value"] if not per_sweep else ["rec_ID"]
            return pd.DataFrame(columns=cols)

        obs = self.get_group_obs_for_sweeps(group_ID, sweeps, aspect=aspect)
        if obs is None or obs.empty or "rec_ID" not in obs.columns:
            if per_sweep:
                sweep_list = sorted(sweeps) if isinstance(sweeps, (list, tuple)) and sweeps is not None else []
                return pd.DataFrame(columns=["rec_ID"] + [str(s) for s in sweep_list])
            return pd.DataFrame(columns=["rec_ID", "value"])

        if per_sweep:
            # Wide matrix (rec_ID + sweeps). Preserve for caller. Ensure consistent string dtype for rec_ID (matches xy_pairs/rec_ID join).
            out = obs.copy()
            if "rec_ID" in out.columns:
                out["rec_ID"] = out["rec_ID"].astype(str)
        else:
            # Scalar mean path (backward compatible)
            sweep_cols = [c for c in obs.columns if c != "rec_ID"]
            if not sweep_cols:
                out = pd.DataFrame(columns=["rec_ID", "value"])
            else:
                mean_vals = obs[sweep_cols].mean(axis=1, skipna=True)
                out = pd.DataFrame({"rec_ID": obs["rec_ID"].values, "value": mean_vals.values})
                out = out[pd.to_numeric(out["value"], errors="coerce").notna()].copy()
                out["value"] = pd.to_numeric(out["value"], errors="coerce")
                out = out.reset_index(drop=True)
            if "rec_ID" in out.columns:
                out["rec_ID"] = out["rec_ID"].astype(str)

        # Phase 0 (v0.16_n_stats): always join hierarchy columns (non-breaking)
        # Uses df_project.ID == rec_ID (df_project uses ID as primary key).
        df_p = self.get_df_project()
        if not df_p.empty and "subject" in df_p.columns:
            hierarchy = df_p[["ID", "subject", "slice"]].rename(columns={"ID": "rec_ID"})
            hierarchy["rec_ID"] = hierarchy["rec_ID"].astype(str)
            out = out.merge(hierarchy, on="rec_ID", how="left")
            # Ensure subject/slice are present even if no match (old projects)
            for col in ("subject", "slice"):
                if col not in out.columns:
                    out[col] = pd.NA

        return out

    # ------------------------------------------------------------------
    # Group sample DataFrame
    # ------------------------------------------------------------------

    def get_ddgroup_sample(self, group_ID):
        """Returns inner dict {test_ID: df} for group's sample means (one entry per shown testset).
        Follows exact get_dfgroupmean pattern: (1) memory, (2) parquet cache, (3) build.
        Now builds/returns dict for EVERY shown testset using real tid as key.
        Saves/loads a separate parquet per (group, test_id) so each testset uses its own sweeps.
        Mirrors update_axe_mean for mean computation per testset (different sweeps produce different means).
        """
        if not hasattr(self, "dd_group_samples"):
            self.dd_group_samples = {}

        if group_ID in self.dd_group_samples:  # 1: Return cached
            if config.verbose:
                print(f"Returning cached group sample for group {group_ID}")
            return self.dd_group_samples[group_ID]

        # 2: Read per-test parquet files for currently-shown testsets
        group_name = self.dd_groups.get(group_ID, {}).get("group_name", f"group_{group_ID}")
        inner = {}
        shown_testsets = {}
        if hasattr(self, "dd_testsets") and self.dd_testsets:
            for tid, tset in self.dd_testsets.items():
                print(f"tid: {tid}, tset: {tset}")
                if tset.get("show", False) and tset.get("sweeps"):
                    shown_testsets[str(tid)] = tset.get("sweeps")

        for test_id in shown_testsets:
            sample_path = Path(f"{self.dict_folders['cache']}/{group_name}_sample_{test_id}.parquet")
            if sample_path.exists():
                if config.verbose:
                    print(f"Loading stored group sample for group {group_ID} test {test_id}")
                df = pd.read_parquet(str(sample_path))
                inner[test_id] = df
        if inner:
            self.dd_group_samples[group_ID] = inner
            return self.dd_group_samples[group_ID]

        # 3: Build from scratch for EVERY shown testset (real tid keys)
        if config.verbose:
            print(f"Building new group sample for group {group_ID}")

        sample_rec = self.dd_groups.get(group_ID, {}).get("sample")
        if not sample_rec:
            self.dd_group_samples[group_ID] = {}
            return self.dd_group_samples[group_ID]

        if not shown_testsets:
            self.dd_group_samples[group_ID] = {}
            return self.dd_group_samples[group_ID]

        # Locate sample recording row and build df (reuse DataFrameMixin helpers)
        df_p = self.get_df_project()
        matching = df_p.loc[df_p["ID"] == sample_rec]
        if matching.empty:
            self.dd_group_samples[group_ID] = {}
            return self.dd_group_samples[group_ID]
        p_row = matching.iloc[0]

        df = self.get_dffilter(p_row)  # must use filter DF (has 'time' column); matches update_axe_mean + uistate.df_rec_select_data
        col = uistate.settings.get("filter") or "voltage"
        if col not in df.columns:
            col = "voltage"  # fallback to ensure column exists in df_sweeps
        df_t = self.get_dft(row=p_row)
        settings = uistate.settings
        mean_dfs = {}

        # Build one mean DF per shown testset (different sweeps per testset) + save per-test parquet
        for test_id, selected_sweeps in shown_testsets.items():
            df_sweeps = df[df["sweep"].isin(selected_sweeps)]
            df_mean = df_sweeps.groupby("time", as_index=False)[col].mean()

            # df_t loop for per-stim event windows + time shift to t=0 (exact mirror of update_axe_mean:320-340)
            events = []
            for i_stim, t_row in df_t.iterrows():
                stim_num = i_stim + 1
                t_stim = t_row["t_stim"]
                window_start = t_stim + settings.get("event_start", 0)
                window_end = t_stim + settings.get("event_end", 0.05)
                df_event = df_mean[(df_mean["time"] >= window_start) & (df_mean["time"] <= window_end)].copy()
                df_event["time"] = df_event["time"] - t_stim  # all times now start at 0 per stim
                df_event["stim"] = stim_num  # retain 'stim' column as required
                events.append(df_event)

            if events:
                test_df = pd.concat(events, ignore_index=True)
                mean_dfs[test_id] = test_df
                # save separate parquet per (group, test_id)
                self.df2file(df=test_df, filename=f"{group_name}_sample_{test_id}")
            else:
                mean_dfs[test_id] = pd.DataFrame()

        self.dd_group_samples[group_ID] = mean_dfs
        return self.dd_group_samples[group_ID]

    # ------------------------------------------------------------------
    # Uniform timepoints across stims
    # ------------------------------------------------------------------

    def set_uniformTimepoints(self, p_row=None, dft=None, dfoutput=None):  # NB: requires both dfoutput and df_t to be present!
        variables = [
            "t_volley_amp",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_EPSP_amp",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
        ]
        methods = [
            "t_volley_amp_method",
            "t_volley_slope_method",
            "t_EPSP_amp_method",
            "t_EPSP_slope_method",
        ]
        params = [
            "t_volley_amp_params",
            "t_volley_slope_params",
            "t_EPSP_amp_params",
            "t_EPSP_slope_params",
        ]

        def use_t_from_stim_with_max(p_row, df_t, dfoutput, column):
            # find highest EPSP_slope in df_output and apply uniform timepoints to all stims
            print(f" - use_t_from_stim_with_max called with df_t:\n{df_t}")
            precision = uistate.settings["precision"]
            if column in dfoutput.columns:
                print(f"dfoutput:\n{dfoutput}")
                idx_max_EPSP = dfoutput[column].idxmax()
                print(f"idx_max_EPSP: {idx_max_EPSP}")
                stim_max = dfoutput.loc[idx_max_EPSP, "stim"]
                print(f"stim_max: {stim_max}")
                t_template_row = df_t[df_t["stim"] == stim_max].copy()
                print(f"t_template_row: {t_template_row}")
                t_stim = round(t_template_row["t_stim"].values[0], precision)
                for var in variables:
                    t_template_row[var] = round(t_template_row[var].values[0] - t_stim, precision)
                if "stim" not in df_t.columns:
                    df_t["stim"] = None
                for i, row_t in df_t.iterrows():
                    df_t.at[i, "stim"] = i + 1  # stims numbered from 1
                    for var in variables:
                        df_t.at[i, var] = round(t_template_row[var].values[0] + row_t["t_stim"], precision)
                    for method in methods:
                        df_t.at[i, method] = f"=stim_{stim_max}"
                    for param in params:
                        df_t.at[i, param] = f"=stim_{stim_max}"
                print(f"Uniform timepoints applied to {p_row['recording_name']}.")
                self.set_dft(p_row["recording_name"], df_t)
                dfoutput = self.get_dfoutput(p_row, reset=True)
                self.persistOutput(p_row["recording_name"], dfoutput, p_row=p_row)

        if p_row is None:  # apply to all recordings
            print(f"set_uniformTimepoints for all recordings")
            for _, p_row in self.get_df_project().iterrows():
                dft = self.get_dft(p_row)
                dfoutput = self.get_dfoutput(p_row)
                use_t_from_stim_with_max(p_row, dft, dfoutput, "EPSP_slope")
        else:
            print(f"set_uniformTimepoints for {p_row['recording_name']}")
            if dft is None or dfoutput is None:
                dft = self.get_dft(p_row)
                dfoutput = self.get_dfoutput(p_row)
            use_t_from_stim_with_max(p_row, dft, dfoutput, "EPSP_slope")
