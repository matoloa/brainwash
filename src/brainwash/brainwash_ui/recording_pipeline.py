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


def stim_ids_are_valid(dft: pd.DataFrame) -> bool:
    """True if every row has a unique integer stim id >= 1."""
    if dft is None or getattr(dft, "empty", True):
        return True
    if "stim" not in dft.columns:
        return False
    seen: set[int] = set()
    for v in dft["stim"].tolist():
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return False
            n = int(v)
            if n < 1 or float(n) != float(v):
                return False
            if n in seen:
                return False
            seen.add(n)
        except (TypeError, ValueError):
            return False
    return True


def should_persist_stim_id_heal(rec_name: str, *, repaired: bool, session_persisted: set | frozenset | None) -> bool:
    """True when a stim-id repair should be written to disk (once per rec per session).

    Policy: always heal in memory; persist at most once per recording name while the
    project is open. Durable log (``stim_id_heal_log`` in cfg) records the event.
    """
    if not repaired or not rec_name:
        return False
    if session_persisted is not None and str(rec_name) in session_persisted:
        return False
    return True


def ensure_stim_ids(dft: pd.DataFrame | None) -> tuple[pd.DataFrame | None, bool]:
    """Guarantee stim column is unique integers >= 1.

    If any null, non-positive, non-integer, missing column, or duplicate is found,
    sort by t_stim (when present) and renumber 1..n. Valid dfts are left unchanged
    (aside from casting stim to int).

    Returns (dft, repaired). Callers that load from disk must not re-write on every
    ``get_dft`` — use ``should_persist_stim_id_heal`` + session/project log.
    """
    if dft is None:
        return None, False
    if getattr(dft, "empty", True):
        return dft, False
    out = dft.copy()
    if stim_ids_are_valid(out):
        out["stim"] = out["stim"].astype(int)
        return out, False
    if "t_stim" in out.columns:
        out = out.sort_values("t_stim", kind="mergesort").reset_index(drop=True)
    else:
        out = out.reset_index(drop=True)
    out["stim"] = list(range(1, len(out) + 1))
    return out, True


def project_stims_needs_update(current_stims, n_dft: int) -> bool:
    """True if df_project.stims should be set to n_dft (NA, wrong, or non-int)."""
    if n_dft < 0:
        return False
    try:
        if current_stims is not None and pd.notna(current_stims) and int(current_stims) == int(n_dft):
            return False
    except (TypeError, ValueError):
        return True
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
    dft, _ = ensure_stim_ids(normalize_dft_dtypes(dft))
    return dft


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