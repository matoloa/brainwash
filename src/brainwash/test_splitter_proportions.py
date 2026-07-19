"""Unit tests for h_splitterMaster dft proportion helpers (no full Qt UI)."""

from ui_state_classes import UIstate
from ui_table import TableMixin


class _Host(TableMixin):
    def __init__(self):
        self.uistate = UIstate()
        self.uistate.project.reset()


def test_ensure_h_splitter_dft_share_restores_zero_pane():
    h = _Host()
    h.uistate.project.splitter["h_splitterMaster"] = [0.2, 0.0, 0.8, 300]
    h.uistate.project.settings["dft_width_proportion"] = 0.25
    h._ensure_h_splitter_dft_share()
    props = h.uistate.project.splitter["h_splitterMaster"]
    assert isinstance(props[1], float) and props[1] > 0.05
    assert abs(props[0] + props[1] + props[2] - 1.0) < 1e-6


def test_store_splitter_proportions_keeps_fixed_tools_px():
    h = _Host()
    h.uistate.project.splitter["h_splitterMaster"] = [0.1, 0.1, 0.8, 300]
    h._store_splitter_proportions_from_sizes("h_splitterMaster", [200, 200, 1600, 300])
    props = h.uistate.project.splitter["h_splitterMaster"]
    assert props[3] == 300  # fixed tools column stays int
    assert abs(sum(p for p in props[:3] if isinstance(p, float)) - 1.0) < 1e-6


def test_ensure_noop_when_dft_share_present():
    h = _Host()
    h.uistate.project.splitter["h_splitterMaster"] = [0.1, 0.15, 0.75, 300]
    h._ensure_h_splitter_dft_share()
    assert h.uistate.project.splitter["h_splitterMaster"][1] == 0.15
