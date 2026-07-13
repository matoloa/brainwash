"""Phase 6: config/uistate/uiplot live on UIsub only, not brainwash.ui module."""


def test_brainwash_ui_has_no_module_singleton_exports():
    import brainwash.ui as ui_mod

    for name in ("config", "uistate", "uiplot"):
        assert name not in ui_mod.__dict__