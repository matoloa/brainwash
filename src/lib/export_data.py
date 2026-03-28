# export_data.py
# ExportMixin — export menu setup and trigger methods for UIsub.
# Owns both the Export menu item wiring (previously in ui_menus.py) and
# the trigger/implementation methods for all export actions.
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import export_data
#   export_data.uistate = uistate
#   export_data.config  = config
#   export_data.uiplot  = uiplot

from __future__ import annotations

import export_image
import pandas as pd
from PyQt5 import QtCore, QtWidgets

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]


class ExportMixin:
    """Mixin that provides all export trigger methods for UIsub.
    Menu item wiring lives in MenuMixin (ui_menus.py)."""

    def _export_status(self, msg: str):
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(msg, 5000)
        print(msg)

    def _require_selection(self) -> list[pd.Series] | None:
        if not uistate.list_idx_select_recs:
            QtWidgets.QMessageBox.warning(
                None,
                "Export Error",
                "No recordings selected for export.",
            )
            return None

        selected_rows = []
        df_project = self.get_df_project()
        for idx in uistate.list_idx_select_recs:
            if idx in df_project.index:
                selected_rows.append(df_project.loc[idx])

        if not selected_rows:
            QtWidgets.QMessageBox.warning(
                None,
                "Export Error",
                "Selected recordings could not be found in the project.",
            )
            return None

        return selected_rows

    # ------------------------------------------------------------------
    # Copy triggers
    # ------------------------------------------------------------------

    def triggerCopyProjectSummary(self):
        self.usage("triggerCopyProjectSummary")
        pass  # TODO: implement

    def triggerCopyTimepoints(self):
        self.usage("triggerCopyTimepoints")
        self.copy_dft()

    def triggerCopyOutput(self):
        self.usage("triggerCopyOutput")
        self.copy_output()

    # ------------------------------------------------------------------
    # Sweep export triggers
    # ------------------------------------------------------------------

    def triggerExportSweepsCsv(self):
        self.usage("triggerExportSweepsCsv")
        rows = self._require_selection()
        if not rows:
            return

        export_dir = self.projects_folder / "Export"
        export_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for i, p_row in enumerate(rows):
            rec_name = p_row["recording_name"]
            df_data = self.get_dfdata(p_row)
            if df_data is not None and not df_data.empty:
                out_path = export_dir / f"{rec_name}_sweeps.csv"
                cols_to_export = [c for c in ["sweep", "time", "voltage_raw", "t0", "datetime"] if c in df_data.columns]
                df_export = df_data[cols_to_export] if cols_to_export else df_data
                df_export.to_csv(out_path, index=False)
                count += 1

        self._export_status(f"Exported sweeps for {count} recording(s) to {export_dir}")

    # ------------------------------------------------------------------
    # Output export triggers
    # ------------------------------------------------------------------

    def triggerExportOutputCsv(self):
        self.usage("triggerExportOutputCsv")
        rows = self._require_selection()
        if not rows:
            return

        export_dir = self.projects_folder / "Export"
        export_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for i, p_row in enumerate(rows):
            rec_name = p_row["recording_name"]
            df_out = self.SI2m(self.get_dfoutput(p_row))
            if df_out is not None and not df_out.empty:
                out_path = export_dir / f"{rec_name}_output.csv"
                cols_to_export = [
                    c
                    for c in [
                        "stim",
                        "sweep",
                        "EPSP_slope",
                        "EPSP_slope_norm",
                        "EPSP_amp",
                        "EPSP_amp_norm",
                        "volley_amp",
                        "volley_slope",
                    ]
                    if c in df_out.columns
                ]
                df_export = df_out[cols_to_export].copy() if cols_to_export else df_out.copy()
                df_export.to_csv(out_path, index=False)
                count += 1

        self._export_status(f"Exported output for {count} recording(s) to {export_dir}")

    # ------------------------------------------------------------------
    # Image export triggers
    # ------------------------------------------------------------------

    def triggerExportOutputImage(self, template_key: str | bool = "jneurosci_1col"):
        if isinstance(template_key, bool):
            template_key = "jneurosci_1col"

        self.usage(f"triggerExportOutputImage: {template_key}")

        if hasattr(self, "tableProj"):
            self.tableProj.clearSelection()

        selected_groups = list(set(str(info["group_ID"]) for info in uistate.dict_group_show.values()))

        if not selected_groups:
            QtWidgets.QMessageBox.warning(
                None,
                "Export Error",
                "No groups are currently displayed to export.",
            )
            return

        template = export_image.JOURNAL_TEMPLATES.get(template_key)
        if not template:
            QtWidgets.QMessageBox.warning(
                None,
                "Export Error",
                f"Template '{template_key}' not found.",
            )
            return

        group_names = {str(gid): ginfo.get("group_name", str(gid)) for gid, ginfo in getattr(self, "dd_groups", {}).items()}

        figures = export_image.render_publication_figure(uistate, uiplot, template, selected_groups, group_names)

        if not figures:
            QtWidgets.QMessageBox.warning(
                None,
                "Export Error",
                "No valid data available to render for the selected template.\nEnsure that group means for amplitude or slope are visible.",
            )
            return

        export_dir = self.projects_folder / "Export"
        export_dir.mkdir(parents=True, exist_ok=True)

        for panel_name, fig in figures.items():
            out_path_png = export_dir / f"{self.projectname}_{template_key}_{panel_name}.png"
            print(f"Saved image: {out_path_png}")
            fig.savefig(out_path_png, dpi=template.dpi, bbox_inches="tight")

        self._export_status(f"Exported {len(figures)} {template.name} figures to {export_dir}")
