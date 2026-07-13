"""Project DataFrame schema (no Qt / ui_project dependency)."""

from __future__ import annotations

import pandas as pd

INT_COLUMNS = ["stims", "sampling_rate", "bin_size"]


def df_projectTemplate():
    """Empty project table with v0.16_n hierarchy columns (subject/slice)."""
    df = pd.DataFrame(
        columns=[
            "ID",
            "host",
            "path",
            "status",
            "recording_name",
            "subject",
            "slice",
            "gain",
            "stims",
            "sweeps",
            "sweep_duration",
            "sweep_hz",
            "sampling_rate",
            "bin_size",
            "resets",
            "filter",
            "filter_params",
            "groups",
            "parsetimestamp",
            "channel",
            "paired_recording",
            "Tx",
            "exclude",
            "comment",
        ]
    )
    for col in INT_COLUMNS:
        df[col] = df[col].astype(pd.Int64Dtype())
    return df