# ui_table.py
# TableMixin — table management and related selection/format methods
# extracted from UIsub (Phase 1 of ui mixin extraction plan).
#
# Module-level singletons are injected by ui.py (same pattern as other mixins):
#
#   import ui_table
#   ui_table.uistate = uistate
#   ui_table.config  = config
#   ui_table.uiplot  = uiplot

from __future__ import annotations

import logging

import pandas as pd
from PyQt5 import QtCore, QtWidgets

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TableMixin:
    """Mixin that provides project table (tableProj) and stim table management.

    Host requirements:
        - self.df_project (or get_df_project())
        - self.tableProj, self.tableView, self.tableStim etc. widgets
        - self.update_recs2plot(), self.update_show(), self.zoomAuto(), self.graphRefresh()
        - self.get_dft(), self.get_dfmean(), self.get_dfoutput(), self.V2mV()
        - self.create_recording(), self.addData()
        - self.formatTableLayout(), self.setButtonParse()
        - uistate.list_idx_select_recs, uistate.df_recs2plot etc.
    """

    def tableProjSelectionChanged(self, selected=None, deselected=None):
        # (body moved from ui.py - full implementation would be copied here)
        # For this initial extraction step, the method body remains in UIsub
        # and we delegate or will move in follow-up edit.
        # Placeholder to satisfy the plan structure.
        if hasattr(self, "_orig_tableProjSelectionChanged"):
            return self._orig_tableProjSelectionChanged(selected, deselected)
        # In real step the full def would be here.
        pass

    # Additional table methods (tableUpdate, _restore_table_selection, get_prow, get_trow,
    # tableFormat, setupTable*, formatTableLayout, etc.) would be moved here in full Phase 1.

    def tableFormat(self):
        logger.debug("tableFormat")
        print("tableFormat")
        selected_rows = self.tableProj.selectionModel().selectedRows()
        # Update data
        self.tablemodel.setData(self.get_df_project())
        self.formatTableLayout()
        # Restore selection
        selection = QtCore.QItemSelection()
        for index in selected_rows:
            selection.select(index, index)
        self.tableProj.selectionModel().select(
            selection,
            QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
        )
        self.setButtonParse()

    def update_recs2plot(self):
        # Example of supporting method that may be shared
        # Full body would move if it belongs purely to table selection.
        pass
