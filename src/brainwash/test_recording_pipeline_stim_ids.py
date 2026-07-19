"""ensure_stim_ids: dft stim column must be unique integers >= 1."""

import numpy as np
import pandas as pd

from brainwash_ui import recording_pipeline as rp


def test_stim_ids_valid_ok():
    dft = pd.DataFrame({"stim": [1, 2, 3], "t_stim": [0.1, 0.2, 0.3]})
    assert rp.stim_ids_are_valid(dft)
    out, repaired = rp.ensure_stim_ids(dft)
    assert repaired is False
    assert list(out["stim"]) == [1, 2, 3]


def test_ensure_repairs_nan_zero_and_duplicates():
    dft = pd.DataFrame(
        {
            "stim": [np.nan, 0, 1, 1],
            "t_stim": [0.4, 0.1, 0.2, 0.3],
        }
    )
    assert not rp.stim_ids_are_valid(dft)
    out, repaired = rp.ensure_stim_ids(dft)
    assert repaired is True
    assert list(out["stim"]) == [1, 2, 3, 4]
    # Ordered by t_stim
    assert list(out["t_stim"]) == [0.1, 0.2, 0.3, 0.4]


def test_ensure_missing_stim_column():
    dft = pd.DataFrame({"t_stim": [0.2, 0.1]})
    out, repaired = rp.ensure_stim_ids(dft)
    assert repaired is True
    assert list(out["stim"]) == [1, 2]
    assert list(out["t_stim"]) == [0.1, 0.2]


def test_empty_and_none():
    assert rp.ensure_stim_ids(None) == (None, False)
    empty = pd.DataFrame(columns=["stim", "t_stim"])
    out, repaired = rp.ensure_stim_ids(empty)
    assert repaired is False
    assert len(out) == 0


def test_project_stims_needs_update():
    assert rp.project_stims_needs_update(pd.NA, 2) is True
    assert rp.project_stims_needs_update(np.nan, 2) is True
    assert rp.project_stims_needs_update(None, 2) is True
    assert rp.project_stims_needs_update(2, 2) is False
    assert rp.project_stims_needs_update(2.0, 2) is False
    assert rp.project_stims_needs_update(1, 2) is True
    assert rp.project_stims_needs_update("x", 2) is True


def test_should_persist_stim_id_heal_once_per_session():
    assert rp.should_persist_stim_id_heal("r1", repaired=False, session_persisted=set()) is False
    assert rp.should_persist_stim_id_heal("r1", repaired=True, session_persisted=set()) is True
    assert rp.should_persist_stim_id_heal("r1", repaired=True, session_persisted={"r1"}) is False
    assert rp.should_persist_stim_id_heal("r2", repaired=True, session_persisted={"r1"}) is True
    assert rp.should_persist_stim_id_heal("", repaired=True, session_persisted=set()) is False
