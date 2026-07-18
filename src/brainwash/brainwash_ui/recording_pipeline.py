"""Pure build/migrate helpers for get_dft / get_dfoutput (no Qt; caches stay on mixin)."""

from __future__ import annotations

import analysis_v3 as analysis
import pandas as pd

_DFT_LEGACY_NORM_COLUMNS = {
    "norm_EPSP_from": "norm_output_from",
    "norm_EPSP_to": "norm_output_to",
}


def is_recording_parsed(row) -> bool:
    return str(row.get("sweeps", "...")) != "..."


def resolve_output_filter_col(filter_val) -> str:
    if pd.notna(filter_val) and filter_val and filter_val != "none":
        return str(filter_val)
    return "voltage"


def normalize_dft_dtypes(dft: pd.DataFrame) -> pd.DataFrame:
    for col in dft.columns:
        if col != "stim" and dft[col].dtype in ("int64", "int32", "float32"):
            dft[col] = dft[col].astype("float64")
    return dft


def migrate_dft_column_names(dft: pd.DataFrame) -> bool:
    if "norm_EPSP_from" not in dft.columns:
        return False
    dft.rename(columns=_DFT_LEGACY_NORM_COLUMNS, inplace=True)
    return True


def build_dft(
    dfmean: pd.DataFrame,
    *,
    default_dict_t: dict,
    filter: str,
    norm_output_from: float,
    norm_output_to: float,
    verbose: bool = False,
) -> pd.DataFrame | None:
    dft = analysis.find_events(
        dfmean=dfmean,
        default_dict_t=default_dict_t,
        filter=filter,
        verbose=verbose,
    )
    if dft.empty:
        return None
    dft["norm_output_from"], dft["norm_output_to"] = (norm_output_from, norm_output_to)
    return normalize_dft_dtypes(dft)


def backfill_volley_means_into_dft(dft: pd.DataFrame, dfoutput: pd.DataFrame) -> None:
    for i, t_row in dft.iterrows():
        stim_nr = t_row["stim"]
        sweep_rows = dfoutput[(dfoutput["stim"] == stim_nr) & dfoutput["sweep"].notna()]
        dft.at[i, "volley_amp_mean"] = sweep_rows["volley_amp"].mean()
        dft.at[i, "volley_slope_mean"] = sweep_rows["volley_slope"].mean()


def build_dfoutput_from_inputs(
    dffilter: pd.DataFrame,
    dfmean: pd.DataFrame,
    dft: pd.DataFrame | None,
    *,
    filter_val,
) -> pd.DataFrame:
    filter_col = resolve_output_filter_col(filter_val)
    dfoutput = analysis.build_dfoutput(
        dffilter=dffilter,
        dfmean=dfmean,
        dft=dft,
        filter=filter_col,
    )
    if dft is not None and not dft.empty:
        backfill_volley_means_into_dft(dft, dfoutput)
    dfoutput.reset_index(drop=True, inplace=True)
    return dfoutput


def clean_dfoutput_from_parquet(dfoutput: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    needs_repersist = False
    if "index" in dfoutput.columns:
        dfoutput.drop(columns=["index"], inplace=True)
        needs_repersist = True
    dfoutput.reset_index(drop=True, inplace=True)
    return dfoutput, needs_repersist