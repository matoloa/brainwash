# ui_export.py
# ExportMixin — export menu setup and trigger methods for UIsub.
# Owns both the Export menu item wiring (previously in ui_menus.py) and
# the trigger/implementation methods for all export actions.
#
# Module-level singletons are injected by ui.py at startup (after all
# singletons and widget classes are created but before any UIsub instance
# is constructed):
#
#   import ui_export
#   ui_export.uistate = uistate
#   ui_export.config  = config
#   ui_export.uiplot  = uiplot

from __future__ import annotations

# ---------------------------------------------------------------------------
# Injected singletons — set by ui.py before any UIsub instance is created.
# ---------------------------------------------------------------------------
uistate = None  # type: ignore[assignment]
config = None  # type: ignore[assignment]
uiplot = None  # type: ignore[assignment]


class ExportMixin:
    """Mixin that provides all export trigger methods for UIsub.
    Menu item wiring lives in MenuMixin (ui_menus.py)."""

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
        pass  # TODO: implement

    def triggerExportSweepsXls(self):
        self.usage("triggerExportSweepsXls")
        pass  # TODO: implement

    def triggerExportSweepsIbw(self):
        self.usage("triggerExportSweepsIbw")
        pass  # TODO: implement

    # ------------------------------------------------------------------
    # Output export triggers
    # ------------------------------------------------------------------

    def triggerExportOutputCsv(self):
        self.usage("triggerExportOutputCsv")
        pass  # TODO: implement

    def triggerExportOutputXls(self):
        self.usage("triggerExportOutputXls")
        pass  # TODO: implement

    # ------------------------------------------------------------------
    # Image export triggers
    # ------------------------------------------------------------------

    def triggerExportOutputImage(self):
        self.usage("triggerExportOutputImage")
        pass  # TODO: implement
