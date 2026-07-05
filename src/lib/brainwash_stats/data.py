import pandas as pd


def _aspect_measurement_columns(amp: bool, slope: bool, norm: bool) -> list[tuple[str, str]]:
    aspects = []
    if amp:
        aspects.append(("amp", "EPSP_amp_norm" if norm else "EPSP_amp"))
    if slope:
        aspects.append(("slope", "EPSP_slope_norm" if norm else "EPSP_slope"))
    if not aspects:
        aspects = [("amp", "EPSP_amp")]
    return aspects


def _aggregate_to_unit_level(obs_df: pd.DataFrame, n_unit: str = "subject") -> pd.DataFrame:
    """Aggregate to one value per statistical unit (mean over recs).
    Returns DataFrame with unit key(s) + 'value'. Used by all test branches.
    - 'subject': group by subject (n = unique subjects)
    - 'slice': group by (subject, slice) — each unique combination counts as 1 n
    - 'recording': pass-through (n = recordings)
    Old projects (missing columns): return as-is (caller emits statusbar warning).
    """
    if obs_df.empty or n_unit == "recording" or "value" not in obs_df.columns:
        return obs_df.copy() if not obs_df.empty else obs_df

    if n_unit == "subject":
        group_keys = ["subject"]
    elif n_unit == "slice":
        group_keys = ["subject", "slice"]
    else:
        group_keys = ["subject"]

    if not all(k in obs_df.columns for k in group_keys):
        return obs_df.copy()

    valid = obs_df[group_keys + ["value"]].dropna()
    if valid.empty:
        empty_df = pd.DataFrame({k: pd.Series(dtype=obs_df[k].dtype if k in obs_df.columns else "object") for k in group_keys})
        empty_df["value"] = pd.Series(dtype=float)
        return empty_df

    return valid.groupby(group_keys, as_index=False)["value"].mean()


def _make_group_testset_observation_accessor(get_group_testset_means_fn, use_implicit: bool):
    """Return callable that fetches group/testset observations (implicit all-sweeps when use_implicit)."""

    def fetch(g, tset, col, per_sweep=False):
        sweeps_arg = None if use_implicit else (list(tset.get("sweeps", [])) if tset else [])
        return get_group_testset_means_fn(g, sweeps_arg, aspect=col, per_sweep=per_sweep)

    return fetch
