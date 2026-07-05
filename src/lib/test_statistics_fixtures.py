"""Fixtures and mocks for statistics characterization tests.

No assertions. Matches plan_statistics_refactor.md Phase 0.
Provides synthetic dd_groups, dd_testsets, mock accessor (DataFrame returning), MinimalUistate, and BoundMethodAccessor
to simulate UI mixin __self__ recovery for IO regression path.
"""

import numpy as np
import pandas as pd


def make_dd_groups(n_groups=2, n_recs_per_group=5, with_hierarchy=True):
    """Make dd_groups dict matching UI shape (with 'show', 'rec_IDs', 'group_name', optional hierarchy)."""
    dd = {}
    for g in range(1, n_groups + 1):
        rec_ids = [f"rec{g}_{i}" for i in range(1, n_recs_per_group + 1)]
        dd[g] = {
            "group_ID": g,
            "group_name": f"Group {g}",
            "show": True,
            "rec_IDs": rec_ids,
            "color": f"#{(g * 50) % 256:02x}0000",
        }
        if with_hierarchy:
            dd[g]["subjects"] = list(range(1, n_recs_per_group // 2 + 2))
    return dd


def make_dd_testsets(n_testsets=2, n_sweeps_per_set=10):
    """Make dd_testsets dict matching UI (with 'show', 'sweeps', 'set_name')."""
    dd = {}
    for s in range(1, n_testsets + 1):
        dd[s] = {
            "set_id": s,
            "set_name": f"TestSet {s}",
            "show": True,
            "sweeps": list(range(1, n_sweeps_per_set + 1)),
        }
    return dd


class MinimalUistate:
    """Stub for uistate in IO regression (provides io_input, io_output, df_project)."""

    def __init__(self):
        self.io_input = "vamp"
        self.io_output = "EPSPamp"
        self.experiment_type = "io"
        self.buttonGroup_test_n = "subject"
        # Minimal df_project for hierarchy join in get_group_testset_means
        self.df_project = pd.DataFrame(
            {
                "ID": ["rec1_1", "rec1_2", "rec2_1"],
                "subject": ["S1", "S1", "S2"],
                "slice": ["slice1", "slice2", "slice1"],
            }
        )


class BoundMethodAccessor:
    """Wraps mock accessor to simulate bound method.__self__ for IO uistate recovery in statistics.py:506."""

    def __init__(self, mock_fn, uistate=None):
        self.mock_fn = mock_fn
        self.__self__ = uistate or MinimalUistate()

    def __call__(self, *args, **kwargs):
        return self.mock_fn(*args, **kwargs)


def make_mock_accessor(dd_groups=None, dd_testsets=None, uistate=None, seed=42):
    """Returns callable that mimics UI.get_group_testset_means(group_ID, sweeps=None, aspect=..., per_sweep=False).
    Returns DataFrames with 'rec_ID', 'value' (or wide for per_sweep), + 'subject'/'slice' for n_unit.
    Uses fixed seed for reproducibility in golden tests.
    """
    np.random.seed(seed)
    if dd_groups is None:
        dd_groups = make_dd_groups()
    if dd_testsets is None:
        dd_testsets = make_dd_testsets()

    def mock_get_group_testset_means(group_ID, sweeps=None, aspect="EPSP_amp", per_sweep=False):
        if group_ID not in dd_groups:
            return pd.DataFrame(columns=["rec_ID", "value", "subject", "slice"])

        rec_ids = dd_groups[group_ID]["rec_IDs"]
        n_recs = len(rec_ids)

        if per_sweep:
            # Wide format for cluster/IO xy_pairs
            n_sweeps = len(sweeps) if sweeps and isinstance(sweeps, (list, tuple)) else 5
            cols = ["rec_ID"] + [f"{s}" for s in range(n_sweeps)]
            data = {c: np.random.normal(0, 1, n_recs) if c != "rec_ID" else rec_ids for c in cols}
            df = pd.DataFrame(data)
            df["subject"] = [f"S{i % 3 + 1}" for i in range(n_recs)]
            df["slice"] = ["slice1"] * n_recs
            return df

        # Scalar mean path (default for most tests)
        values = np.random.normal(0, 1, n_recs)
        if aspect.endswith("norm"):
            values = values * 0.8  # slight difference for norm tests
        df = pd.DataFrame(
            {
                "rec_ID": rec_ids,
                "value": values,
                "subject": [f"S{i % 3 + 1}" for i in range(n_recs)],
                "slice": ["slice1"] * n_recs,
            }
        )
        # Filter NaNs (mimics real path)
        df = df[pd.notna(df["value"])].copy()
        return df.reset_index(drop=True)

    accessor = BoundMethodAccessor(mock_get_group_testset_means, uistate)
    return accessor.mock_fn  # return the wrapped callable (statistics expects the function)


# Convenience for tests
def make_test_context(**overrides):
    """Build kwargs for compute_statistical_comparison with sensible defaults."""
    defaults = {
        "groups": [1, 2],
        "dd_groups": make_dd_groups(2, 5),
        "dd_testsets": make_dd_testsets(2, 10),
        "get_group_testset_means_fn": None,  # filled by caller with make_mock_accessor(...)
        "test_type": "t-test",
        "variant": "unpaired",
        "tails": "two-sided",
        "fdr": False,
        "norm": False,
        "amp": True,
        "slope": True,
        "ref": 0.0,
        "n_unit": "subject",
        "experiment_type": "time",
        "uistate": MinimalUistate(),
    }
    defaults.update(overrides)
    if defaults["get_group_testset_means_fn"] is None:
        defaults["get_group_testset_means_fn"] = make_mock_accessor(defaults["dd_groups"], defaults.get("dd_testsets"), defaults.get("uistate"))
    return defaults
