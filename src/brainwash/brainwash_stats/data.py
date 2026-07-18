import re

import numpy as np
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


def _normalize_hierarchy_key(val) -> str | None:
    """Canonical string for subject/slice keys so 1, 1.0, '1', '1.0' count as one unit."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        if hasattr(val, "item"):
            val = val.item()
    except Exception:
        pass
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val).strip()
    if isinstance(val, int) and not isinstance(val, bool):
        return str(val)
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "<na>", "nat"):
        return None
    if re.fullmatch(r"-?\d+\.0+", s):
        return s.split(".", 1)[0]
    return s


def _unit_key_columns(n_unit: str) -> list[str]:
    """Join keys for pairing / aggregation at the chosen statistical unit."""
    if n_unit == "recording":
        return ["rec_ID"]
    if n_unit == "slice":
        return ["subject", "slice"]
    return ["subject"]


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

    valid = obs_df[group_keys + ["value"]].copy()
    for k in group_keys:
        valid[k] = valid[k].map(_normalize_hierarchy_key)
    valid["value"] = pd.to_numeric(valid["value"], errors="coerce")
    valid = valid.dropna(subset=group_keys + ["value"])
    if valid.empty:
        empty_df = pd.DataFrame({k: pd.Series(dtype=object) for k in group_keys})
        empty_df["value"] = pd.Series(dtype=float)
        return empty_df

    return valid.groupby(group_keys, as_index=False)["value"].mean()


def _format_unit_label(row: pd.Series, keys: list[str]) -> str:
    if len(keys) == 1:
        return str(row[keys[0]])
    return ", ".join(f"{k}={row[k]}" for k in keys)


def _prepare_unit_value_frame(obs_df: pd.DataFrame | None, keys: list[str]) -> pd.DataFrame:
    """Normalize keys + value for pairing; one row per unit key."""
    empty = pd.DataFrame(columns=keys + ["value"])
    if obs_df is None or obs_df.empty or "value" not in obs_df.columns:
        return empty
    if not all(k in obs_df.columns for k in keys):
        return empty
    df = obs_df[keys + ["value"]].copy()
    for k in keys:
        if k == "rec_ID":
            df[k] = df[k].map(lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else None)
        else:
            df[k] = df[k].map(_normalize_hierarchy_key)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=keys + ["value"])
    if df.empty:
        return empty
    if df.duplicated(subset=keys).any():
        df = df.groupby(keys, as_index=False)["value"].mean()
    return df.reset_index(drop=True)


def _align_paired_unit_values(
    obs1_df: pd.DataFrame | None,
    obs2_df: pd.DataFrame | None,
    n_unit: str = "subject",
) -> dict:
    """Inner-join two unit-level frames for paired tests (complete-case pairs only).

    Returns:
      v1, v2: aligned float arrays (same length = n_pairs)
      n_pairs, n_dropped: ints
      dropped: list[{unit, reason}] for incomplete units
    """
    keys = _unit_key_columns(n_unit)
    a = _prepare_unit_value_frame(obs1_df, keys)
    b = _prepare_unit_value_frame(obs2_df, keys)
    empty_out = {
        "v1": np.array([], dtype=float),
        "v2": np.array([], dtype=float),
        "n_pairs": 0,
        "n_dropped": 0,
        "dropped": [],
    }
    if a.empty and b.empty:
        return empty_out

    merged = a.merge(b, on=keys, how="outer", suffixes=("_1", "_2"), indicator=True)
    dropped: list[dict] = []
    for _, row in merged.iterrows():
        lab = _format_unit_label(row, keys)
        side = row["_merge"]
        if side == "left_only":
            dropped.append(
                {
                    "unit": lab,
                    "reason": "no finite value in test set 2 (present only in test set 1)",
                }
            )
        elif side == "right_only":
            dropped.append(
                {
                    "unit": lab,
                    "reason": "no finite value in test set 1 (present only in test set 2)",
                }
            )
        else:
            v1 = row.get("value_1")
            v2 = row.get("value_2")
            if not (np.isfinite(v1) and np.isfinite(v2)):
                dropped.append(
                    {
                        "unit": lab,
                        "reason": "non-finite value in one or both test sets",
                    }
                )

    complete = merged[merged["_merge"] == "both"].copy()
    if not complete.empty:
        ok = np.isfinite(complete["value_1"].to_numpy(dtype=float)) & np.isfinite(complete["value_2"].to_numpy(dtype=float))
        complete = complete.loc[ok]
    n_pairs = int(len(complete))
    if n_pairs == 0:
        return {
            "v1": np.array([], dtype=float),
            "v2": np.array([], dtype=float),
            "n_pairs": 0,
            "n_dropped": len(dropped),
            "dropped": dropped,
        }
    return {
        "v1": complete["value_1"].to_numpy(dtype=float),
        "v2": complete["value_2"].to_numpy(dtype=float),
        "n_pairs": n_pairs,
        "n_dropped": len(dropped),
        "dropped": dropped,
    }


def _align_multi_condition_unit_values(
    obs_dfs: list,
    n_unit: str = "subject",
    condition_labels: list[str] | None = None,
) -> dict:
    """Inner-join k≥2 unit-level frames (complete cases across all conditions).

    Used by Friedman (and similar RM nonparametrics). Returns:
      values: list[np.ndarray] — one aligned array per condition (length n_pairs)
      n_pairs, n_dropped: ints
      dropped: list[{unit, reason}]
    """
    k = len(obs_dfs)
    labels = list(condition_labels) if condition_labels and len(condition_labels) == k else [f"condition {i + 1}" for i in range(k)]
    empty_out = {
        "values": [np.array([], dtype=float) for _ in range(k)],
        "n_pairs": 0,
        "n_dropped": 0,
        "dropped": [],
    }
    if k < 2:
        return empty_out

    keys = _unit_key_columns(n_unit)
    frames = []
    for i, obs in enumerate(obs_dfs):
        df = _prepare_unit_value_frame(obs, keys)
        frames.append(df.rename(columns={"value": f"value_{i}"}))

    if all(f.empty for f in frames):
        return empty_out

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on=keys, how="outer")

    value_cols = [f"value_{i}" for i in range(k)]
    dropped: list[dict] = []
    complete_mask = []
    for idx, row in merged.iterrows():
        lab = _format_unit_label(row, keys)
        vals = [row.get(c) for c in value_cols]
        ok = all(v is not None and pd.notna(v) and np.isfinite(float(v)) for v in vals)
        if ok:
            complete_mask.append(True)
        else:
            complete_mask.append(False)
            missing = [labels[i] for i, v in enumerate(vals) if v is None or pd.isna(v) or not np.isfinite(float(v) if pd.notna(v) else np.nan)]
            if not missing:
                reason = "non-finite value in one or more conditions"
            else:
                reason = "missing or non-finite in: " + ", ".join(missing)
            dropped.append({"unit": lab, "reason": reason})

    complete = merged.loc[complete_mask].copy() if complete_mask else merged.iloc[0:0]
    n_pairs = int(len(complete))
    if n_pairs == 0:
        return {
            "values": [np.array([], dtype=float) for _ in range(k)],
            "n_pairs": 0,
            "n_dropped": len(dropped),
            "dropped": dropped,
        }
    values = [complete[c].to_numpy(dtype=float) for c in value_cols]
    return {
        "values": values,
        "n_pairs": n_pairs,
        "n_dropped": len(dropped),
        "dropped": dropped,
    }


def _make_group_testset_observation_accessor(get_group_testset_means_fn, use_implicit: bool):
    """Return callable that fetches group/testset observations (implicit all-sweeps when use_implicit)."""

    def fetch(g, tset, col, per_sweep=False):
        sweeps_arg = None if use_implicit else (list(tset.get("sweeps", [])) if tset else [])
        return get_group_testset_means_fn(g, sweeps_arg, aspect=col, per_sweep=per_sweep)

    return fetch
