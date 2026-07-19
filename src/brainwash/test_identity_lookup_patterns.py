"""Guard: artist lookups must not re-introduce name/suffix dual-path outside plot_identity.

Legacy string parsing for IO roles belongs only in ``plot_identity``
(``_legacy_io_role_from_text`` / ``entry_io_role``). Call sites must use role /
rec_ID helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

# Production modules that may still contain the legacy IO suffix *parser*.
ALLOWED_SUFFIX_FILES = frozenset(
    {
        "brainwash_ui/plot_identity.py",
    }
)

FORBIDDEN_SUBSTRINGS = (
    '.endswith(" IO scatter")',
    ".endswith(' IO scatter')",
    '.endswith(" IO trendline")',
    ".endswith(' IO trendline')",
    'key.startswith(rec_name)',
    "key.startswith(rec_name)",
    'disp.startswith(rec_name) or key.startswith',
)


def _iter_prod_py() -> list[Path]:
    out = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("test_") or "/test_" in rel or rel.endswith("_test.py"):
            continue
        if "legacy/" in rel or rel.startswith("legacy/"):
            continue
        if "__pycache__" in rel:
            continue
        out.append(path)
    return out


def test_no_forbidden_identity_lookup_patterns_outside_plot_identity():
    violations = []
    for path in _iter_prod_py():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_SUFFIX_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in text:
                violations.append(f"{rel}: contains {needle!r}")
    assert not violations, "Identity dual-path lookups:\n" + "\n".join(violations)


def test_entry_io_role_prefers_metadata_over_suffix():
    from brainwash_ui import plot_identity as pi

    assert pi.entry_io_role({"role": pi.ROLE_IO_SCATTER, "display_label": "x"}, "k") == pi.ROLE_IO_SCATTER
    assert pi.entry_io_role({"role": pi.ROLE_SERIES, "display_label": "rec1 raw IO scatter"}, "k") is None
    assert pi.entry_io_role({"display_label": "rec1 raw IO trendline"}, "opaque") == pi.ROLE_IO_TREND
    assert pi.entry_io_role({}, "rec|1|ax1|io_trend|...") is None
    assert pi.is_io_trendline_entry({"role": pi.ROLE_IO_TREND})
    assert not pi.is_io_trendline_entry({"role": pi.ROLE_IO_SCATTER})


def test_entry_matches_rec_name_ignores_opaque_keys():
    from brainwash_ui import plot_identity as pi

    ent = {"display_label": "slice07 - stim 1 EPSP amp", "rec_ID": 7}
    assert pi.entry_matches_rec_name(ent, "slice07", key="rec|7|ax1|series|...")
    assert not pi.entry_matches_rec_name({"display_label": ""}, "slice07", key="rec|7|ax1|series|...")
    assert pi.entry_matches_rec_name({}, "slice07", key="slice07 raw IO scatter")
    assert pi.resolve_rec_id_from_store(
        {"rec|7|...": {"rec_ID": 7, "display_label": "slice07 EPSP amp"}},
        "slice07",
    ) == 7
