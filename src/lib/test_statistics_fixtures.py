"""Shared mocks for statistics characterization tests. No assertions."""

from __future__ import annotations

import pandas as pd


def make_dd_groups(*group_ids: str, show: bool = True) -> dict:
    return {gid: {"show": show, "rec_IDs": [f"rec_{gid}_{i}" for i in range(1, 3)]} for gid in group_ids}


def make_dd_testsets(*set_ids: str, sweeps: list | None = None, show: bool = True) -> dict:
    sweep_list = sweeps if sweeps is not None else [1, 2, 3]
    return {sid: {"show": show, "sweeps": sweep_list, "name": sid} for sid in set_ids}


class MinimalUistate:
    def __init__(self, io_input: str = "vamp", io_output: str = "EPSPamp"):
        self.io_input = io_input
        self.io_output = io_output


def make_scalar_accessor(
    values_by_group: dict[str, list[tuple[str, str, float]]],
):
    """values_by_group: {group_id: [(rec_ID, subject, value), ...]} for scalar (per_sweep=False) path."""

    def accessor(g, sweeps, aspect="EPSP_amp", per_sweep=False):
        rows = values_by_group.get(g, [])
        if per_sweep:
            sweep_cols = sorted(sweeps) if isinstance(sweeps, (list, tuple)) and sweeps else [1, 2, 3]
            data = {"rec_ID": [], "subject": [], "slice": []}
            for col in sweep_cols:
                data[str(col)] = []
            for rec_id, subject, val in rows:
                data["rec_ID"].append(rec_id)
                data["subject"].append(subject)
                data["slice"].append(1)
                for col in sweep_cols:
                    data[str(col)].append(val + 0.1 * col)
            return pd.DataFrame(data)
        return pd.DataFrame(
            [
                {"rec_ID": rec_id, "subject": subject, "slice": 1, "value": val}
                for rec_id, subject, val in rows
            ]
        )

    return accessor


def bind_accessor(accessor, uistate=None):
    """Attach __self__ like UI mixin methods (IO regression recovery path)."""

    class _Self:
        def get_df_project(self):
            return pd.DataFrame()

        def get_dfoutput(self, row=None):
            return pd.DataFrame()

    bound = accessor
    bound.__self__ = _Self()
    return bound