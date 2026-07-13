# ui_table.py
# TableMixin — table management and related selection/format methods
# extracted from UIsub (Phase 1 of ui mixin extraction plan).
#
# Uses self.uistate / self.config / self.uiplot on UIsub (see ui.py).
#
#   import ui_table
#   ui_table.uistate = uistate
#   ui_table.config  = config
#   ui_table.uiplot  = self.uiplot

from __future__ import annotations

import logging
import time

import pandas as pd
from PyQt5 import QtCore, QtWidgets, sip

import ui_widgets  # for TableModel, TableProjSub etc. (injected widgets)

from ui_project import df_projectTemplate

# ---------------------------------------------------------------------------
# Uses self.uistate / self.config / self.uiplot on UIsub (see ui.py).
logger = logging.getLogger(__name__)


class TableMixin:
    """Mixin that provides project table (tableProj) and stim table management.

    Host requirements (provided by UIsub or other mixins):
        - self.df_project (or get_df_project())
        - self.tableProj, self.tableStim, self.h_splitterMaster widgets
        - self.update_show(), self.zoomAuto(), self.graphRefresh(), self.graphUpdate()
        - self.get_dft(), self.get_dffilter(), self.get_df_project()
        - self.update_filter_settings(), self.update_experiment_type_radio_buttons()
        - self.update_amp_lineEdits(), self.update_slope_lineEdits()
        - self.refreshHierarchyLineEdits(), self.setButtonParse()
        - self.usage(), self.mouseoverUpdate()
        - self.connectUIstate()
        - self.uistate.* selection state, df_recs2plot etc.
    """

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
        """Rebuild self.uistate.plot.df_recs2plot from current selection (positional rows).
        Filters out unparsed rows (sweeps == "...").
        """
        if not self.uistate.plot.list_idx_select_recs:
            self.uistate.plot.df_recs2plot = None
            return
        try:
            df_p = self.get_df_project()
            df_project_selected = df_p.iloc[self.uistate.plot.list_idx_select_recs]
            self.uistate.plot.df_recs2plot = df_project_selected[df_project_selected["sweeps"] != "..."]
            if self.uistate.plot.df_recs2plot.empty:
                self.uistate.plot.df_recs2plot = None
        except Exception:
            self.uistate.plot.df_recs2plot = None

    def tableProjSelectionChanged(self, selected=None, deselected=None):
        if self.updating_tableProj:
            return
        self.usage("tableProjSelectionChanged")
        if QtWidgets.QApplication.mouseButtons() == QtCore.Qt.RightButton:
            self.tableProj.clearSelection()
        selected_indexes = self.tableProj.selectionModel().selectedRows()
        self.uistate.plot.list_idx_select_recs = [index.row() for index in selected_indexes]
        self.update_recs2plot()
        self.update_sample_checkbox()

        if self.uistate.plot.df_recs2plot is None:
            print("No parsed recordings selected.")
            self.uistate.plot.list_idx_select_stims = []
            self.update_show()
            self.zoomAuto()
            self.graphRefresh(reeval_formal_test=False)
            return

        prow = self.get_prow()

        if len(self.uistate.plot.list_idx_select_recs) == 1:
            dft_for_format = self.get_dft(row=prow)
        else:
            self.uistate.plot.df_rec_select_data = None
            self.uistate.plot.df_rec_select_time = None
            longest_sweep_prow = self.uistate.plot.df_recs2plot.loc[self.uistate.plot.df_recs2plot["sweep_duration"].idxmax()]
            self.uistate.plot.float_sweep_duration_max = longest_sweep_prow["sweep_duration"]
            dft_for_format = self.get_dft(row=longest_sweep_prow)

        if dft_for_format is not None:
            num_stims = len(dft_for_format)
            valid_stim_indices = [i for i in self.uistate.plot.list_idx_select_stims if i < num_stims]
            if not valid_stim_indices and num_stims > 0:
                valid_stim_indices = [0]
            self.uistate.plot.list_idx_select_stims = valid_stim_indices

            self.tableStimModel.setData(dft_for_format)
            model = self.tableStim.model()
            selection = QtCore.QItemSelection()
            for row_idx in self.uistate.plot.list_idx_select_stims:
                index_start = model.index(row_idx, 0)
                index_end = model.index(row_idx, model.columnCount(QtCore.QModelIndex()) - 1)
                selection.select(index_start, index_end)
            self.tableStim.selectionModel().select(selection, QtCore.QItemSelectionModel.ClearAndSelect)
            self.formatTableStimLayout(dft=dft_for_format)
        else:
            self.uistate.plot.list_idx_select_stims = []
            logger.debug("tableProjSelectionChanged: dft_for_format is None (no stims detected), clearing stim selection")

        if len(self.uistate.plot.list_idx_select_recs) == 1 and len(self.uistate.plot.list_idx_select_stims) == 1:
            self.uistate.plot.df_rec_select_time = self.get_dft(row=prow)
            self.uistate.plot.df_rec_select_data = self.get_dffilter(prow)
            self.uistate.plot.float_sweep_duration_max = prow["sweep_duration"]
        else:
            self.uistate.plot.df_rec_select_data = None
            self.uistate.plot.df_rec_select_time = None

        self.connectUIstate(disconnect=True)
        self.update_experiment_type_radio_buttons()
        df_p = self.get_df_project()
        if self.uistate.plot.list_idx_select_recs:
            bin_values = {df_p.loc[i, "bin_size"] for i in self.uistate.plot.list_idx_select_recs}
            nan_count = sum(1 for v in bin_values if pd.isna(v))
            non_nan = {v for v in bin_values if pd.notna(v)}
            uniform = (nan_count == 0 and len(non_nan) == 1) or (nan_count == len(self.uistate.plot.list_idx_select_recs))
            if uniform:
                single = non_nan.pop() if non_nan else float("nan")
                self.lineEdit_bin_size.setText("0" if pd.isna(single) else str(int(single)))
            else:
                self.lineEdit_bin_size.setText("")
        else:
            self.lineEdit_bin_size.setText("")

        self.update_filter_settings(df_p)
        self.connectUIstate()
        self.graphUpdate(reeval_formal_test=False)

        self.update_show()
        self.zoomAuto()
        self.update_amp_lineEdits()
        self.update_slope_lineEdits()
        self.refreshHierarchyLineEdits(df_p)

        t0 = time.time()
        self.mouseoverUpdate()
        print(f" - mouseoverUpdate: {round((time.time() - t0) * 1000)} ms")

    def tableUpdate(self, restore_selection: bool = True, target_idx: int | None = None):
        self.updating_tableProj = True
        df_project = self.get_df_project()
        self.tablemodel.setData(df_project)
        self.formatTableLayout()
        self.tableProj.resizeColumnsToContents()

        if restore_selection:
            self._restore_table_selection(df_project, target_idx)

        self.updating_tableProj = False
        self.setButtonParse()

    def _restore_table_selection(self, df_p: pd.DataFrame, target_idx: int | None = None) -> None:
        self.tableProj.clearSelection()
        to_select = []
        if target_idx is not None:
            if 0 <= target_idx < len(df_p):
                to_select = [target_idx]
        elif self.uistate.plot.list_idx_select_recs:
            to_select = [i for i in self.uistate.plot.list_idx_select_recs if 0 <= i < len(df_p)]
            if not to_select and len(df_p) > 0:
                to_select = [len(df_p) - 1]
        elif len(df_p) > 0:
            to_select = [len(df_p) - 1]

        if to_select:
            selection = QtCore.QItemSelection()
            for idx in to_select:
                top_left = self.tablemodel.index(idx, 0)
                bottom_right = self.tablemodel.index(idx, self.tablemodel.columnCount(QtCore.QModelIndex()) - 1)
                selection.select(top_left, bottom_right)
            self.tableProj.selectionModel().select(selection, QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
            self.tableProj.scrollTo(self.tablemodel.index(to_select[0], 0))
            self.tableProj.setFocus()
            self.uistate.plot.list_idx_select_recs = to_select
        else:
            self.uistate.plot.list_idx_select_recs = []

    def get_prow(self, dfp_idx=None):
        if dfp_idx is not None:
            dfp = self.get_df_project()
            row = dfp.loc[dfp_idx]
            return row
        if not self.uistate.plot.list_idx_select_recs:
            return None
        dfp = self.get_df_project()
        row = dfp.loc[self.uistate.plot.list_idx_select_recs[0]]
        return row

    def get_trow(self, dfp_idx=None):
        if dfp_idx is not None:
            prow = self.get_prow(dfp_idx)
            if prow is None:
                logger.debug("get_trow: get_prow(%s) returned None, returning None", dfp_idx)
                return None
            dft = self.get_dft(prow)
        else:
            if not self.uistate.plot.list_idx_select_stims:
                print("get_trow: No stim selected.")
                return None
            prow = self.get_prow()
            if prow is None:
                logger.debug("get_trow: get_prow() returned None (no recording selected), returning None")
                return None
            dft = self.get_dft(prow)
        if dft is None or len(dft) == 0:
            print("get_trow: Empty dataframe.")
            return None
        idx = self.uistate.plot.list_idx_select_stims[0] if self.uistate.plot.list_idx_select_stims else 0
        if idx < 0 or idx >= len(dft):
            idx = 0
            self.uistate.plot.list_idx_select_stims = [0]
        return dft.loc[idx]

    def setupTableProj(self):
        try:
            if hasattr(self, "tableProj"):
                self.verticalLayoutProj.removeWidget(self.tableProj)
                sip.delete(self.tableProj)

            self.tableProj = ui_widgets.TableProjSub(parent=self)
            self.verticalLayoutProj.addWidget(self.tableProj)
            self.tableProj.setObjectName("tableProj")

            if not hasattr(self, "df_project"):
                self.df_project = df_projectTemplate()
            self.tablemodel = ui_widgets.TableModel(self.df_project)
            self.tableProj.setModel(self.tablemodel)

            self.tableProj.setSortingEnabled(True)

            self.pushButtonParse.pressed.connect(self.triggerParse)
            self.tableProj.setSelectionBehavior(ui_widgets.TableProjSub.SelectRows)
            tableProj_selectionModel = self.tableProj.selectionModel()
            tableProj_selectionModel.selectionChanged.connect(self.tableProjSelectionChanged)
            if (hasattr(self, "lineEdit_hierarchy_subject") and hasattr(self, "lineEdit_hierarchy_slice")
                    and hasattr(self, "setTabOrder")):
                self.setTabOrder(self.lineEdit_hierarchy_subject, self.lineEdit_hierarchy_slice)
            self.formatTableLayout()
        except Exception as e:
            print(f"Error setting up tableProj: {e}")

    def setupTableStim(self):
        dft_init = pd.DataFrame([self.uistate.project.default_dict_t])
        self.tableStimModel = ui_widgets.TableModel(dft_init)
        self.tableStim.setModel(self.tableStimModel)
        self.tableStim.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableStim.verticalHeader().hide()
        self.formatTableStimLayout(dft_init)
        tableStim_selectionModel = self.tableStim.selectionModel()
        tableStim_selectionModel.selectionChanged.connect(self.stimSelectionChanged)

    def formatTableLayout(self):
        logger.debug("formatTableLayout")
        print("formatTableLayout")

        self.tableProj.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.tableProj.verticalHeader().hide()

        df_p = self.df_project
        header = self.tableProj.horizontalHeader()

        column_order = [
            "status",
            "recording_name",
            "subject",
            "slice",
            "groups",
            "stims",
            "sweeps",
            "sweep_duration",
        ]
        if self.uistate.project.checkBox["paired_stims"]:
            column_order.append("Tx")

        if self.uistate.project.detailedProjectTable:
            for col_name in df_p.columns:
                if col_name not in column_order:
                    column_order.append(col_name)

        col_indices = [df_p.columns.get_loc(name) for name in column_order if name in df_p.columns]

        num_columns = df_p.shape[1]
        for col in range(num_columns):
            if col in col_indices:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Interactive)
                self.tableProj.setColumnHidden(col, False)
            else:
                self.tableProj.setColumnHidden(col, True)

        self.tableProj.resizeColumnsToContents()

        for i, col_index in enumerate(col_indices):
            header.moveSection(header.visualIndex(col_index), i)

    def formatTableStimLayout(self, dft):
        if dft is None:
            dft = pd.DataFrame([self.uistate.project.default_dict_t])

        header = self.tableStim.horizontalHeader()
        column_order = [
            "stim",
            "t_stim",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_EPSP_slope_method",
            "t_EPSP_amp",
            "t_EPSP_amp_method",
            "t_volley_slope_start",
            "t_volley_slope_end",
            "t_volley_slope_method",
            "t_volley_amp",
            "t_volley_amp_method",
        ]
        if self.uistate.project.detailedTimetable:
            for col_name in dft.columns:
                if col_name not in column_order:
                    column_order.append(col_name)

        col_indices = [dft.columns.get_loc(col) for col in column_order if col in dft.columns]
        num_columns = dft.shape[1]

        for col in range(num_columns):
            if col in col_indices:
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Interactive)
                self.tableStim.setColumnHidden(col, False)
            else:
                self.tableStim.setColumnHidden(col, True)
        for i, col_index in enumerate(col_indices):
            header.moveSection(header.visualIndex(col_index), i)
        self.tableStim.resizeColumnsToContents()

    def setTableStimVisibility(self, state, initialize=False):
        """Toggle visibility of the stim table (right pane of master splitter)."""
        widget = self.h_splitterMaster.widget(1)  # Get the second widget in the splitter

        if initialize:
            widget.setVisible(state)
            return

        if state == widget.isVisible():
            return

        sizes = self.h_splitterMaster.sizes()
        if state:
            prop = self.uistate.project.settings.get("dft_width_proportion", 0.2)
            total = sizes[1] + sizes[2]
            sizes[1] = min(total, max(100, int(total * prop)))
            sizes[2] = total - sizes[1]
            widget.setVisible(True)
            self.h_splitterMaster.setSizes(sizes)
        else:
            sizes[2] += sizes[1]
            sizes[1] = 0
            widget.setVisible(False)
            self.h_splitterMaster.setSizes(sizes)

        total_size = sum(sizes)
        if total_size > 0:
            old_proportions = self.uistate.project.splitter.get("h_splitterMaster", [])
            unbounded_px = sum(size for i, size in enumerate(sizes) if i >= len(old_proportions) or type(old_proportions[i]) == float)
            proportions = []
            for i, size in enumerate(sizes):
                if i < len(old_proportions) and type(old_proportions[i]) != float:
                    proportions.append(int(size))
                else:
                    proportions.append(float(size / unbounded_px if unbounded_px > 0 else 0.0))
            self.uistate.project.splitter["h_splitterMaster"] = proportions
